#!/bin/bash
# Backs up the Judicom's whole SD card to the NAS while it runs (no need to take the card out).   On the Judicom:
#     bash ~/Judicom/deploy/judicom/backup_judicom.sh --trial     first: measures, and tries the freeze and its safety net
#     bash ~/Judicom/deploy/judicom/backup_judicom.sh             the backup
# ONLY AT HOME: the copy goes over the home network to the NAS (found as naspi.local, which only answers at home).  Never over Tailscale: Tailscale itself stalls
# while the card is frozen (2026-11-04).
# The phone is off for a few minutes, 25 at most (callers hear "Judi can't come to the phone").  The frozen part is backup_stream.sh: it
# unfreezes whenever it ends, a watchdog ends it after 25 minutes, and a guard unfreezes after 28 minutes whatever happens.
# The result: /mnt/2tbdrive/judicom-backups/judicom-<date>.img.zst on the NAS, checked against the SHA-256 of what was read.
# To put a backup on a new card: docs/DEPLOYMENT.md, "Backup of the SD card".
set -euo pipefail
trap 'echo "STOPPED at line $LINENO: $BASH_COMMAND" >&2' ERR
MODE=backup
case "${1:-}" in "") ;; --trial) MODE=trial ;; *) echo "usage: $0 [--trial]" >&2; exit 1 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
NAS_IP=$(getent ahostsv4 naspi.local | awk 'NR == 1 { print $1 }' || true)     # its home address: the name answers only at home
NAS="pi@$NAS_IP"
KEY="$HOME/.ssh/judicom_backup"         # the NAS lets this key only store, commit and discard (receive_backup.sh)
DEV=/dev/mmcblk0
SERVICES="judicom-phone judicom-baresip"
TIMERS="judicom-contacts-sync.timer judicom-photo-sync.timer"
SSH=(ssh -i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10 -o UpdateHostKeys=no
     -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=15 -o ServerAliveCountMax=4 "$NAS")

[ "$(hostname)" = judicom ] || { echo "Run this on the Judicom." >&2; exit 1; }
case "$NAS_IP" in
  "" | 100.*) echo "naspi.local is not on the home network here (${NAS_IP:-no answer}).  This backup only runs at home.  Nothing done." >&2; exit 1 ;;
esac
[ -f "$KEY" ] || { echo "No backup key ($KEY): see docs/DEPLOYMENT.md." >&2; exit 1; }
[ -f "$HERE/backup_stream.sh" ] || { echo "backup_stream.sh is missing next to this script." >&2; exit 1; }
answer=$("${SSH[@]}" "commit none none" 2>&1 || true)
if [[ "$answer" != *"receive_backup: commit NAME SUM"* ]]; then
  echo "The NAS cannot be reached on the home network ($NAS): ${answer:-no answer}" >&2
  echo "This backup only runs at home (over Tailscale it would stall while the card is frozen).  Nothing done." >&2
  exit 1
fi
start2=$(cat /sys/block/mmcblk0/mmcblk0p2/start)
size2=$(cat /sys/block/mmcblk0/mmcblk0p2/size)
total=$(cat /sys/block/mmcblk0/size)
[ $((start2 + size2)) -eq "$total" ] || { echo "The main partition does not end at the end of the card: this script does not know this layout." >&2; exit 1; }
echo "The SD card: $((total / 2048)) MB; boot area $((start2 / 2048)) MB, main partition $((size2 / 2048)) MB ($(df -h --output=used / | tail -1 | tr -d ' ') in use)."
echo "The NAS answers on the home network ($NAS)."
if [ "$MODE" = trial ]; then
  read -r -p "Run the trial? It reads the card for a few minutes, and turns the phone off for about a minute. [y/N] " ok
else
  read -r -p "Back it up now? The phone is off for a few minutes. [y/N] " ok
fi
[ "$ok" = "y" ] || { echo "Nothing done."; exit 1; }
sudo -v
work=$(mktemp -d -p "/run/user/$(id -u)")             # in memory: nothing may be written to the frozen partition

stopped=0
restart() {
  [ -f "$work/restarted" ] && stopped=0                    # the frozen part already started them again
  if [ "$stopped" = 1 ]; then
    sudo journalctl --flush 2>/dev/null || true         # the log back onto the card
    sudo systemctl start $SERVICES $TIMERS || true
    stopped=0
  fi
}
meter=""
stop_meter() { if [ -n "$meter" ]; then kill "$meter" 2>/dev/null || true; wait "$meter" 2>/dev/null || true; meter=""; echo; fi; }
cleanup() { stop_meter; restart; rm -rf "$work"; }
trap cleanup EXIT
show_meter() {     # how far through the main partition the copier is (it keeps that in $1), on one line.  It stays at 0% for the
  local position=$1 mb=0 total=0 a b pct bar spin='|/-\' i=0 began=$SECONDS     # first half minute, the boot area.  Touches nothing
  while :; do                                                                   # on the frozen card.  If the spinner turns but the
    if [ -r "$position" ] && read -r a b < "$position"; then mb=$a; total=$b; fi  # MB stand still, the copy is stuck.
    pct=0
    [ "$total" -eq 0 ] || pct=$(( mb * 100 / total ))
    printf -v bar '%*s' $(( pct / 5 )) ''
    printf '\r   %s [%-20s] %3d%%  %d of %d MB, %d:%02d ' "${spin:i++ % 4:1}" "${bar// /#}" "$pct" "$mb" "$total" \
           $(( (SECONDS - began) / 60 )) $(( (SECONDS - began) % 60 ))
    sleep 1
  done
}
stop() {
  sudo systemctl stop $TIMERS $SERVICES
  sudo journalctl --relinquish-var                     # the log goes to memory while the card is frozen
  stopped=1
  sync
}
stream() { sudo bash "$HERE/backup_stream.sh" "$DEV" "$start2" "$work" "$1" "${2:-}"; }

if [ "$MODE" = trial ]; then
  echo "1. Speed of the home network to the NAS ..."
  t0=$(date +%s%N); head -c 64M /dev/urandom | "${SSH[@]}" discard >/dev/null; t1=$(date +%s%N)
  speed=$(python3 -c "print(round(64 / (($t1 - $t0) / 1e9), 1))")
  echo "   $speed MB/s"
  echo "2. How big the image would be (reading the card, nothing frozen yet; a few minutes) ..."
  t0=$(date +%s%N)
  bytes=$( { sudo dd if="$DEV" bs=4M iflag=count_bytes count=$((start2 * 512)) status=none; sudo python3 -B "$HERE/copy_used_blocks.py" "${DEV}p2"; } \
           | zstd --single-thread --no-asyncio -1 -q | wc -c )
  t1=$(date +%s%N)
  read_s=$(( (t1 - t0) / 1000000000 ))
  minutes=$(python3 -c "print(round(max($read_s, $bytes / 1e6 / $speed) / 60 + 0.5, 1))")
  echo "   $(python3 -c "print(round($bytes / 1e9, 2))") GB to send; reading and packing took $read_s s"
  echo "   => a backup would freeze the card for about $minutes minutes (the watchdog stops at 30)"
  echo "3. Freezing the card for 10 seconds, with the phone stopped ..."
  stop
  stream trial > /dev/null
  [ -f "$work/unfrozen" ] && echo "   frozen and unfrozen again: OK" || { echo "   NOT unfrozen?" >&2; exit 1; }
  rm -f "$work/unfrozen" "$work/frozen"
  echo "4. Reading 200 MB of the frozen card with the copier (what failed on 2026-11-04; gives up after 3 minutes) ..."
  stream trial-read > /dev/null || true                    # judged by what it read, below
  if [ "$(cat "$work/read_bytes" 2>/dev/null)" = 209715200 ] && [ -f "$work/unfrozen" ] && [ ! -f "$work/timeout" ]; then
    echo "   read 200 MB from the frozen card, and unfrozen: OK"
  else
    echo "   the copier could not read the frozen card (read: $(cat "$work/read_bytes" 2>/dev/null || echo 0) bytes)" >&2; exit 1
  fi
  rm -f "$work/unfrozen" "$work/frozen"
  echo "5. The safety net: a copy that hangs, which the watchdog must stop (about 15 seconds) ..."
  if stream trial-watchdog > /dev/null 2>"$work/wd.err"; then echo "   the watchdog did not act?" >&2; exit 1; fi
  [ -f "$work/timeout" ] && [ -f "$work/unfrozen" ] && echo "   stopped by the watchdog and unfrozen: OK" || { cat "$work/wd.err" >&2; exit 1; }
  restart
  echo "6. Phone started again.  Trial done: if the estimate above is well under 25 minutes, the backup can go ahead."
  exit 0
fi

echo "1. Stopping the phone and the syncs ..."
stop
echo "2. Freezing the card and sending it to the NAS (a few minutes; the phone starts again as soon as the card is unfrozen) ..."
if [ -t 1 ]; then show_meter "$work/position" & meter=$!; fi
set +e
# (No tee / sha256sum in this pipe: on 2026-11-09 tee held the pipe from zstd for good while the card was frozen.  zstd's own
# checksum, tested on the NAS before the commit, finds a cut-off or damaged upload; the NAS writes the SHA-256 itself.)
stream backup "$SERVICES $TIMERS" | zstd --single-thread --no-asyncio -1 -q | "${SSH[@]}" store > "$work/name"
codes=("${PIPESTATUS[@]}")
set -e
stop_meter
sleep 2
echo "3. The phone: $([ -f "$work/restarted" ] && echo "started again" || echo "starting it again ...")"
restart
if [ "${codes[0]}" != 0 ] || [ "${codes[1]}" != 0 ] || [ "${codes[2]}" != 0 ] || [ ! -s "$work/name" ]; then
  [ -f "$work/timeout" ] && echo "The copy took longer than 25 minutes and was stopped; the card was unfrozen." >&2
  echo "The backup did not complete (exit codes: ${codes[*]}).  The card is unfrozen and the phone running again." >&2
  echo "(What reached the NAS stays a hidden, unfinished file there: it is never taken for a backup.)" >&2
  echo "How far it got, until the next backup or reboot: /run/judicom-backup-progress.log" >&2
  exit 1
fi
name=$(cat "$work/name")
echo "4. Checking the copy on the NAS (that it unpacks, with zstd's own checksum): $name ..."
if result=$("${SSH[@]}" "commit $name" 2>&1); then
  echo "   $result"
  echo "GOOD: the backup is complete and exact: $name"
else
  echo "BAD: $result" >&2
  echo "The upload stays a hidden, unfinished file on the NAS.  Run this again." >&2
  exit 1
fi
