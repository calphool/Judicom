#!/bin/bash
# The frozen part of backup_judicom.sh (run by it as root; never needed by hand).  Writes the card image to its standard output:
# the start of the card and the boot partition as they are (dd), then the main partition's used blocks (e2image -ra; free space as
# zeros), while the main partition is frozen so that nothing changes during the copy.
#
#     backup_stream.sh DEVICE START_SECTOR_OF_PARTITION_2 STATE_DIR [backup|trial|trial-read|trial-watchdog] ["UNITS TO START"]
#
# SAFETY: the partition is unfrozen whenever this script ends, however it ends (done, error, Ctrl-C, killed by TERM).
#   - a watchdog started BEFORE the freeze ends the copy after MAX_SECONDS, so this script always ends;
#   - a separate guard unfreezes after GUARD_SECONDS even if this script itself were killed with -9.
# Nothing in here writes to the frozen partition: no sudo, no logging; STATE_DIR must be in memory (/run/user/...).
#   trial            freeze for 10 seconds, send nothing, unfreeze          (to see that freezing and unfreezing work)
#   trial-read       freeze, read 200 MB of the main partition with the copier, unfreeze (3-minute watchdog)
# The main partition is read by copy_used_blocks.py (used blocks from dumpe2fs, free ones as zeros: what e2image -ra makes).
# Not e2image: its "is this mounted?" check creates /.ismount-test-file, which waits forever on a frozen root (2026-11-04); a
# loop device does not hide the mount, and device-mapper refuses a mounted partition.
# The units named last are started again by this script itself as soon as the card is unfrozen (no sudo needed afterwards).
#   trial-watchdog   freeze, pretend the copy hangs, let the watchdog end it (to see that the safety net works)
set -uo pipefail
DEV="$1"; START="$2"; STATE="$3"; MODE="${4:-backup}"; UNITS="${5:-}"
FSFREEZE="${FSFREEZE:-/usr/sbin/fsfreeze}"
REMOUNT_BOOT="${REMOUNT_BOOT:-mount -o remount}"
COPIER="${COPIER:-python3 -B $(cd "$(dirname "$0")" && pwd)/copy_used_blocks.py}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
JOURNALCTL="${JOURNALCTL:-journalctl}"
BOOT="${BOOT:-/boot/firmware}"
MAX_SECONDS="${MAX_SECONDS:-900}"            # the copy gives up after 15 minutes ...
GUARD_SECONDS="${GUARD_SECONDS:-1200}"       # ... and the partition is unfrozen after 20 minutes whatever happens
[ "$MODE" = trial-watchdog ] && MAX_SECONDS="${TRIAL_MAX_SECONDS:-15}"
[ "$MODE" = trial-read ] && MAX_SECONDS="${TRIAL_READ_MAX_SECONDS:-180}"
export PYTHONDONTWRITEBYTECODE=1                 # python must not try to write .pyc files onto the frozen card

frozen=0
unfreeze() {
  if [ "$frozen" = 1 ]; then
    $FSFREEZE -u / 2>/dev/null
    echo "unfrozen" > "$STATE/unfrozen"
    frozen=0
  fi
  $REMOUNT_BOOT,rw "$BOOT" 2>/dev/null
  if [ -n "$UNITS" ]; then
    $JOURNALCTL --flush 2>/dev/null
    $SYSTEMCTL start $UNITS 2>/dev/null && echo "restarted" > "$STATE/restarted"
    UNITS=""
  fi
}
finish() {
  local code=$?
  [ -n "${copy:-}" ] && kill -TERM "$copy" 2>/dev/null
  pkill -TERM -P "${copy:-0}" 2>/dev/null
  unfreeze
  [ -n "${watchdog:-}" ] && kill "$watchdog" 2>/dev/null
  [ -n "${guard:-}" ] && kill "$guard" 2>/dev/null
  exit "$code"
}
trap finish EXIT
trap 'echo "stopped" > "$STATE/stopped"; exit 130' INT TERM HUP PIPE

# the guard: a separate process, so even this script being killed outright cannot leave the partition frozen
( exec -a judicom-backup-guard bash -c "sleep $GUARD_SECONDS; $FSFREEZE -u / 2>/dev/null; $REMOUNT_BOOT,rw $BOOT 2>/dev/null" ) \
  </dev/null >/dev/null 2>&1 &
guard=$!
echo "$guard" > "$STATE/guard"

$REMOUNT_BOOT,ro "$BOOT" 2>/dev/null || echo "(the boot partition stays writable; nothing writes to it)" >&2
$FSFREEZE -f / || { echo "could not freeze the main partition" >&2; exit 1; }
frozen=1
echo "frozen" > "$STATE/frozen"

case "$MODE" in
  backup)         ( dd if="$DEV" bs=4M iflag=direct,count_bytes count=$(( START * 512 )) status=none && $COPIER "${DEV}p2" ) & ;;
  trial)          ( sleep 10 ) & ;;
  # (the copier gets "broken pipe" when head has its 200 MB: expected; what counts is how much was read)
  trial-read)     ( set +o pipefail; $COPIER "${DEV}p2" 2>/dev/null | head -c 209715200 | wc -c > "$STATE/read_bytes" ) & ;;
  trial-watchdog) ( sleep 100000 ) & ;;
  *)              echo "unknown mode $MODE" >&2; exit 1 ;;
esac
copy=$!
( sleep "$MAX_SECONDS"; echo "timeout" > "$STATE/timeout"; pkill -TERM -P "$copy"; kill -TERM "$copy" ) >/dev/null 2>&1 &
watchdog=$!
wait "$copy"
code=$?
[ -f "$STATE/timeout" ] && { echo "the copy took longer than $MAX_SECONDS s and was stopped" >&2; exit 124; }
exit "$code"
