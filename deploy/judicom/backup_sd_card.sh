#!/bin/bash
# Copies the Judicom's whole SD card, as an image, to the NAS (compressed), and checks the copy.  It only READS the card.
# The Judicom must be shut down and its card in this computer's card reader.  Run it yourself:
#     bash deploy/judicom/backup_sd_card.sh /dev/sdX          (the card's device; see lsblk)
# The image goes to pi@naspi.local:/mnt/2tbdrive/judicom-backups/judicom-<date>.img.zst, with a .sha256 file beside it.
# To put it on a card again: see docs/DEPLOYMENT.md ("Backup of the SD card").
set -euo pipefail
DEV="${1:-}"
NAS="pi@naspi.local"
DIR="/mnt/2tbdrive/judicom-backups"
[ -b "$DEV" ] || { echo "Give the card's device, e.g.  bash $0 /dev/sdb   (lsblk shows it: about 29G, the Judicom's card)" >&2; exit 1; }
case "$DEV" in /dev/sda|/dev/nvme0n1) echo "$DEV is this computer's own disk, not the card. Nothing done." >&2; exit 1;; esac
echo "This will READ (not change) this device and copy it to the NAS:"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS "$DEV"
echo
size=$(lsblk -bdno SIZE "$DEV")
[ "$size" -gt 8000000000 ] && [ "$size" -lt 70000000000 ] || { echo "That is $((size / 1000000000)) GB: not the size of the Judicom's card (about 31 GB). Nothing done." >&2; exit 1; }
read -r -p "Is this the Judicom's card? [y/N] " ok
[ "$ok" = "y" ] || { echo "Nothing done."; exit 1; }
for p in $(lsblk -lno NAME "$DEV" | tail -n +2); do                # the computer may have opened its partitions: close them
  mountpoint=$(lsblk -lno MOUNTPOINTS "/dev/$p" | head -1)
  [ -n "$mountpoint" ] && sudo umount "/dev/$p" && echo "(unmounted /dev/$p from $mountpoint)"
done
name="judicom-$(date +%Y-%m-%d-%H%M).img.zst"
ssh "$NAS" "mkdir -p $DIR"
sumfile=$(mktemp)
echo "Copying $((size / 1000000000)) GB (a few minutes; the free space compresses to almost nothing) ..."
sudo dd if="$DEV" bs=4M status=progress | tee >(sha256sum | cut -d' ' -f1 > "$sumfile") | zstd -T0 -3 -q \
  | ssh "$NAS" "cat > $DIR/$name.part && mv $DIR/$name.part $DIR/$name"
sleep 1
sum=$(cat "$sumfile"); rm -f "$sumfile"
echo "$sum  ${name%.zst}" | ssh "$NAS" "cat > $DIR/$name.sha256"
echo "Read from the card:  $sum"
echo "Checking the copy on the NAS (unpacking it there) ..."
nas_sum=$(ssh "$NAS" "zstd -dc $DIR/$name | sha256sum | cut -d' ' -f1")
echo "The copy on the NAS: $nas_sum"
if [ "$sum" = "$nas_sum" ]; then
  echo "GOOD: the copy is exact.  $NAS:$DIR/$name ($(ssh "$NAS" "du -h $DIR/$name | cut -f1"))"
  echo "Put the card back in the Judicom and switch it on."
else
  echo "BAD: the copy does not match the card. Keep the card, and run this again." >&2
  exit 1
fi
