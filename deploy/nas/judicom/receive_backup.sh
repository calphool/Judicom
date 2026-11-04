#!/bin/sh
# What the Judicom's backup key may do on the NAS, and nothing else.  Its line in /home/pi/.ssh/authorized_keys is
#     restrict,command="/home/pi/judicom/receive_backup.sh" ssh-ed25519 ... judicom-backup
#   store            save what comes in as a new backup, judicom-<date-time>.img.zst (never over an old one); prints its name.
#                    Keeps the newest 5.  Refused when the backup drive has less than 40 GB free.
#   check NAME       unpack that backup and print its SHA-256 (to compare with what the Judicom read)
#   note NAME SUM    write NAME.sha256 beside it
#   discard          read what comes in and throw it away (prints how many bytes): the backup's speed test
# It cannot read, change or remove anything else.
set -eu
DIR="${JUDICOM_BACKUP_DIR:-/mnt/2tbdrive/judicom-backups}"
KEEP=5
MIN_FREE_GB=40
NAME_RE='^judicom-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}\.img\.zst$'
set -f                                     # the request is split into words, never expanded into file names
set -- ${SSH_ORIGINAL_COMMAND:-}
set +f                                     # file-name patterns back on (needed to keep the newest 5)
case "${1:-}" in
  store)
    [ $# -eq 1 ] || { echo "receive_backup: store takes nothing more" >&2; exit 1; }
    mkdir -p "$DIR"
    free=$(df -Pk "$DIR" | awk 'NR == 2 { print int($4 / 1048576) }')
    [ "$free" -ge "$MIN_FREE_GB" ] || { echo "receive_backup: only $free GB free on the backup drive (need $MIN_FREE_GB)" >&2; exit 1; }
    find "$DIR" -maxdepth 1 -name '.judicom-*.part' -mmin +240 -delete            # leftovers of a broken earlier upload
    name="judicom-$(date +%Y-%m-%d-%H%M%S).img.zst"
    cat > "$DIR/.$name.part"
    mv "$DIR/.$name.part" "$DIR/$name"
    ls -1t "$DIR"/judicom-*.img.zst | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old" "$old.sha256"; done
    echo "$name" ;;
  discard)
    [ $# -eq 1 ] || exit 1
    wc -c | tr -d ' ' ;;                                        # a speed test: reads what comes in, keeps nothing
  check)
    [ $# -eq 2 ] && printf '%s\n' "$2" | grep -Eq "$NAME_RE" && [ -f "$DIR/$2" ] || { echo "receive_backup: no such backup" >&2; exit 1; }
    zstd -dc "$DIR/$2" | sha256sum | cut -d' ' -f1 ;;
  note)
    [ $# -eq 3 ] && printf '%s\n' "$2" | grep -Eq "$NAME_RE" && [ -f "$DIR/$2" ] \
      && printf '%s\n' "$3" | grep -Eq '^[0-9a-f]{64}$' || { echo "receive_backup: note NAME SUM" >&2; exit 1; }
    printf '%s  %s\n' "$3" "${2%.zst}" > "$DIR/$2.sha256" ;;
  *)
    echo "receive_backup: only 'store', 'check NAME', 'note NAME SUM' or 'discard' may be asked for" >&2
    exit 1 ;;
esac
