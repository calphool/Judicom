#!/bin/sh
# What the Judicom's backup key may do on the NAS, and nothing else.  Its line in /home/pi/.ssh/authorized_keys is
#     restrict,command="/home/pi/judicom/receive_backup.sh" ssh-ed25519 ... judicom-backup
#   store            receive a backup into a hidden, unfinished file (.judicom-<date-time>.img.zst.part); prints its name.
#                    Refused when the backup drive has less than 40 GB free.
#   commit NAME SUM  only if that file's SHA-256 is SUM and it unpacks without error: give it its real name, write NAME.sha256
#                    beside it, and keep the newest 5.  So an upload that was cut off never looks like a backup.
#   discard          read what comes in and throw it away (prints how many bytes): the backup's speed test
# It cannot read, change or remove anything else.  Unfinished files older than 4 hours are removed at the next store.
set -eu
DIR="${JUDICOM_BACKUP_DIR:-/mnt/2tbdrive/judicom-backups}"
KEEP=5
MIN_FREE_GB=40
NAME_RE='^judicom-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}\.img\.zst$'
set -f                                     # the request is split into words, never expanded into file names ...
set -- ${SSH_ORIGINAL_COMMAND:-}
set +f                                     # ... and file-name patterns are on again (needed to keep the newest 5)
case "${1:-}" in
  store)
    [ $# -eq 1 ] || { echo "receive_backup: store takes nothing more" >&2; exit 1; }
    mkdir -p "$DIR"
    free=$(df -Pk "$DIR" | awk 'NR == 2 { print int($4 / 1048576) }')
    [ "$free" -ge "$MIN_FREE_GB" ] || { echo "receive_backup: only $free GB free on the backup drive (need $MIN_FREE_GB)" >&2; exit 1; }
    find "$DIR" -maxdepth 1 -name '.judicom-*.part' -mmin +240 -delete
    name="judicom-$(date +%Y-%m-%d-%H%M%S).img.zst"
    while [ -e "$DIR/.$name.part" ] || [ -e "$DIR/$name" ]; do          # never two uploads under one name
      sleep 1
      name="judicom-$(date +%Y-%m-%d-%H%M%S).img.zst"
    done
    : > "$DIR/.$name.part"
    cat > "$DIR/.$name.part"
    echo "$name" ;;
  commit)
    [ $# -eq 3 ] && printf '%s\n' "$2" | grep -Eq "$NAME_RE" && printf '%s\n' "$3" | grep -Eq '^[0-9a-f]{64}$' \
      && [ -f "$DIR/.$2.part" ] || { echo "receive_backup: commit NAME SUM (of an unfinished upload)" >&2; exit 1; }
    part="$DIR/.$2.part"
    have=$(sha256sum "$part" | cut -d' ' -f1)
    [ "$have" = "$3" ] || { echo "receive_backup: the upload's SHA-256 is $have, not $3: kept unfinished" >&2; exit 1; }
    zstd -tq "$part" || { echo "receive_backup: the upload does not unpack: kept unfinished" >&2; exit 1; }
    mv "$part" "$DIR/$2"
    printf '%s  %s\n' "$3" "$2" > "$DIR/$2.sha256"
    ls -1t "$DIR"/judicom-*.img.zst | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old" "$old.sha256"; done
    echo "committed $2" ;;
  discard)
    [ $# -eq 1 ] || exit 1
    wc -c | tr -d ' ' ;;
  *)
    echo "receive_backup: only 'store', 'commit NAME SUM' or 'discard' may be asked for" >&2
    exit 1 ;;
esac
