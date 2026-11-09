#!/bin/bash
# The NAS's weekly backup of what the other backups miss (root's naspi-backup.timer, Sundays 06:00).
#   1. a snapshot of /home/pi (the Judicom's master lists and pictures, the Asterisk configs and passwords, the mail importer's
#      settings ...) without the caches that can be downloaded again.  Unchanged files are hard links to the previous snapshot,
#      so each one costs only what changed.  Kept: the newest KEEP_SNAPSHOTS.
#   2. a compressed copy of the NAS's own SD-card image (backup-sd-image.service writes it to the SSD, the same drive as
#      /home: one failure would take both).  Kept: the newest KEEP_SD_IMAGES.
#   3. tidies the Judicom's SD-card images (receive_backup.sh): the newest KEEP_JUDICOM, and no half-received .part files.
# Everything goes to DEST (the first 2 TB drive); the existing rsync-backup mirror copies it to the second one.
# Space: nothing is written while DEST has less than MIN_FREE_PCT percent free; the oldest snapshots go first to make room.
# Success or failure is reported to PING_URL (healthchecks.io), from /etc/naspi-backup.env (not in git).
set -euo pipefail

SETTINGS="${SETTINGS:-/etc/naspi-backup.env}"
[ -f "$SETTINGS" ] && . "$SETTINGS"
SRC="${SRC:-/home/pi}"
DEST="${DEST:-/mnt/2tbdrive}"
SD_IMAGE="${SD_IMAGE:-/mnt/1tbdrive/naspi-sd-backup.img}"
JUDICOM_DIR="${JUDICOM_DIR:-$DEST/judicom-backups}"
KEEP_SNAPSHOTS="${KEEP_SNAPSHOTS:-8}"
KEEP_SD_IMAGES="${KEEP_SD_IMAGES:-2}"
KEEP_JUDICOM="${KEEP_JUDICOM:-4}"
MIN_FREE_PCT="${MIN_FREE_PCT:-10}"
SD_ROOM_GB="${SD_ROOM_GB:-20}"           # room asked for before compressing the SD image (128 GB card, ~12 GB used)
CHECK_MOUNT="${CHECK_MOUNT:-1}"          # 0 only in tests
PING_URL="${PING_URL:-}"
SNAPS="$DEST/naspi-snapshots"
IMAGES="$DEST/naspi-sd-images"

say() { echo "naspi-backup: $*"; }
ping_hc() {                              # ping_hc "" | "/fail" | "/start"
  [ -n "$PING_URL" ] || return 0
  curl -fsS -m 10 --retry 3 -A naspi-backup -o /dev/null "$PING_URL$1" || say "could not reach PING_URL"
}
fail() { say "FAILED: $*"; ping_hc /fail; exit 1; }
trap 'fail "line $LINENO: $BASH_COMMAND"' ERR

free_pct() { df --output=avail,size -B1 "$DEST" | awk 'NR == 2 { printf "%d", $1 * 100 / $2 }'; }
free_gb() { df --output=avail -B1G "$DEST" | awk 'NR == 2 { print $1 }'; }
newest() { { ls -1d "$1"/$2 2>/dev/null || true; } | sort | tail -n 1; }
oldest_first() { { ls -1d "$1"/$2 2>/dev/null || true; } | sort; }

ping_hc /start
if [ "$CHECK_MOUNT" = 1 ]; then
  mountpoint -q "$DEST" || fail "$DEST is not mounted"
fi
mkdir -p "$SNAPS" "$IMAGES"

# ---- make room: the oldest snapshots go first, but the newest one always stays ----------------------------------------
while [ "$(free_pct)" -lt "$MIN_FREE_PCT" ]; do
  mapfile -t all < <(oldest_first "$SNAPS" '20??-??-??')
  [ "${#all[@]}" -gt 1 ] || fail "$DEST has only $(free_pct)% free (needs $MIN_FREE_PCT%); nothing more of mine to remove"
  say "only $(free_pct)% free: removing the oldest snapshot ${all[0]}"
  rm -rf -- "${all[0]}"
done

# ---- 1. the snapshot of /home/pi --------------------------------------------------------------------------------------
today="$SNAPS/${TODAY:-$(date +%F)}"
last="$(newest "$SNAPS" '20??-??-??')"
rm -rf -- "$SNAPS"/*.part
link=()
[ -n "$last" ] && [ "$last" != "$today" ] && link=(--link-dest="$last")
rsync -aHAX --numeric-ids --delete "${link[@]}" \
  --exclude=/.cache/ --exclude=/.npm/ --exclude=/.nuget/ --exclude=/.nvm/ \
  "$SRC/" "$today.part/"
rm -rf -- "$today"
mv -- "$today.part" "$today"
say "snapshot $today ($(du -sh "$today" | cut -f1) on its own; $(du -sh "$SNAPS" | cut -f1) for all)"
mapfile -t all < <(oldest_first "$SNAPS" '20??-??-??')
for ((i = 0; i < ${#all[@]} - KEEP_SNAPSHOTS; i++)); do
  say "removing old snapshot ${all[i]}"
  rm -rf -- "${all[i]}"
done

# ---- 2. the NAS's SD-card image, compressed ---------------------------------------------------------------------------
if [ -f "$SD_IMAGE" ]; then
  name="$IMAGES/naspi-sd-$(date -r "$SD_IMAGE" +%F).img.zst"
  if [ -f "$name" ]; then
    say "SD image of $(date -r "$SD_IMAGE" +%F) already copied"
  elif [ "$(free_gb)" -lt "$SD_ROOM_GB" ] || [ "$(free_pct)" -lt "$MIN_FREE_PCT" ]; then
    fail "no room for the SD image: $(free_gb) GB / $(free_pct)% free"
  else
    rm -f -- "$IMAGES"/*.part
    zstd -q -T0 -3 "$SD_IMAGE" -o "$name.part"
    zstd -q -t "$name.part"
    mv -- "$name.part" "$name"
    say "SD image copied: $name ($(du -h "$name" | cut -f1))"
  fi
  mapfile -t all < <(oldest_first "$IMAGES" 'naspi-sd-*.img.zst')
  for ((i = 0; i < ${#all[@]} - KEEP_SD_IMAGES; i++)); do
    say "removing old SD image ${all[i]}"
    rm -f -- "${all[i]}"
  done
else
  say "no SD image at $SD_IMAGE (skipped)"
fi

# ---- 3. the Judicom's images: the newest few, no leftovers --------------------------------------------------------------
if [ -d "$JUDICOM_DIR" ]; then
  find "$JUDICOM_DIR" -maxdepth 1 -name '.judicom-*.part' -mmin +1440 -print -delete | sed 's/^/naspi-backup: removed leftover /'
  mapfile -t all < <(oldest_first "$JUDICOM_DIR" 'judicom-20*.img.zst')
  for ((i = 0; i < ${#all[@]} - KEEP_JUDICOM; i++)); do
    say "removing old Judicom image ${all[i]}"
    rm -f -- "${all[i]}" "${all[i]}.sha256"
  done
fi

say "done: $(free_gb) GB ($(free_pct)%) free on $DEST"
ping_hc ""
