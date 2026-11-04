#!/bin/bash
# Backs up the Judicom's whole SD card to the NAS while it runs (no need to take the card out).   Run it on the Judicom:
#     bash ~/Judicom/deploy/judicom/backup_judicom.sh
# It stops the phone for a few minutes (callers hear "Judi can't come to the phone"), freezes the main partition so nothing
# changes while it is read, and sends: the start of the card and the boot partition as they are, then the main partition with
# e2image (only the parts in use; free space as zeros, which compress to almost nothing).  The result is a complete card image
# on the NAS (/mnt/2tbdrive/judicom-backups/judicom-<date>.img.zst), checked against the SHA-256 of what was read.
# Whatever happens, the partition is unfrozen and the phone started again (and a safety timer unfreezes it after 45 minutes).
# To put a backup on a new card: docs/DEPLOYMENT.md, "Backup of the SD card".
set -euo pipefail
NAS_HOME="pi@192.168.1.2"              # the NAS on the home network: used when the Judicom is at home ...
NAS_TS="pi@100.64.0.1"               # ... otherwise over Tailscale (from the nursing home)
KEY="$HOME/.ssh/judicom_backup"         # the NAS lets this key only store and check backups (receive_backup.sh)
DEV=/dev/mmcblk0
SERVICES="judicom-phone judicom-baresip"
TIMERS="judicom-contacts-sync.timer judicom-photo-sync.timer"
# No writes to known_hosts while frozen (UpdateHostKeys=no); a transfer that stops moving gives up in about 2 minutes.
SSH_OPTS=(-i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10 -o UpdateHostKeys=no
          -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 -o ServerAliveCountMax=8)
NAS=$NAS_HOME
ssh "${SSH_OPTS[@]}" "$NAS" "check none" 2>&1 | grep -q "no such backup" || NAS=$NAS_TS
SSH=(ssh "${SSH_OPTS[@]}" "$NAS")

[ "$(hostname)" = judicom ] || { echo "Run this on the Judicom." >&2; exit 1; }
[ -f "$KEY" ] || { echo "No backup key ($KEY): see docs/DEPLOYMENT.md." >&2; exit 1; }
start2=$(cat /sys/block/mmcblk0/mmcblk0p2/start)
size2=$(cat /sys/block/mmcblk0/mmcblk0p2/size)
total=$(cat /sys/block/mmcblk0/size)
[ $((start2 + size2)) -eq "$total" ] || { echo "The main partition does not end at the end of the card: this script does not know this layout." >&2; exit 1; }
echo "The SD card: $((total / 2048)) MB; boot area $((start2 / 2048)) MB, main partition $((size2 / 2048)) MB ($(df -h --output=used / | tail -1 | tr -d ' ') in use)."
echo "The NAS ($NAS) answers: $("${SSH[@]}" "check none" 2>&1 | head -1)   (that 'no such backup' is the right answer)"
read -r -p "Back it up now? The phone is off for a few minutes. [y/N] " ok
[ "$ok" = "y" ] || { echo "Nothing done."; exit 1; }
sudo -v

work=$(mktemp -d -p "/run/user/$(id -u)")          # in memory: nothing may be written to the frozen partition
cleanup() {
  sudo /usr/sbin/fsfreeze -u / 2>/dev/null || true
  sudo mount -o remount,rw /boot/firmware 2>/dev/null || true
  sudo journalctl --flush 2>/dev/null || true                     # the log back onto the card
  [ -f "$work/guard" ] && sudo kill "$(cat "$work/guard")" 2>/dev/null || true
  sudo systemctl start $SERVICES $TIMERS || true
  rm -rf "$work"
}
trap cleanup EXIT

echo "1. Stopping the phone and the syncs ..."
sudo systemctl stop $TIMERS $SERVICES
sudo journalctl --relinquish-var                                   # the log goes to memory while the card is frozen
sync
echo "2. Freezing the partitions and sending the card to the NAS ..."
# Everything while frozen happens inside ONE root shell started before the freeze (a new sudo then could wait on the frozen disk).
sudo bash -c '
  set -euo pipefail
  trap "/usr/sbin/fsfreeze -u / 2>/dev/null; mount -o remount,rw /boot/firmware 2>/dev/null" EXIT    # unfrozen whatever happens
  ( sleep 2700; /usr/sbin/fsfreeze -u /; mount -o remount,rw /boot/firmware ) >/dev/null 2>&1 &
  echo $! > "$1/guard"
  mount -o remount,ro /boot/firmware || echo "(the boot partition stays writable; it is not being written to)" >&2
  /usr/sbin/fsfreeze -f /
  dd if="$2" bs=4M iflag=count_bytes count=$(( $3 * 512 )) status=none
  /usr/sbin/e2image -ra "$2"p2 - 2>/dev/null
' backup "$work" "$DEV" "$start2" \
  | tee >(sha256sum | cut -d' ' -f1 > "$work/sum") \
  | zstd -T0 -3 -q \
  | "${SSH[@]}" store > "$work/name"
sleep 2
name=$(cat "$work/name"); sum=$(cat "$work/sum")
echo "3. Starting the phone again ..."
sudo journalctl --flush
sudo systemctl start $SERVICES $TIMERS
echo "4. Checking the copy on the NAS: $name ..."
nas_sum=$("${SSH[@]}" "check $name")
echo "   read from the card: $sum"
echo "   the copy on the NAS: $nas_sum"
if [ "$sum" = "$nas_sum" ]; then
  "${SSH[@]}" "note $name $sum"
  echo "GOOD: the backup is complete and exact: $name"
else
  echo "BAD: the copy on the NAS does not match. Run this again." >&2
  exit 1
fi
