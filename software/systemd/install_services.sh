#!/bin/bash
# Makes the Judicom start by itself at power-on: installs and starts judicom-baresip and judicom-phone, and makes the boot picture
# go straight to the photos: the boot picture stays on the screen until the phone draws (plymouth quit --retain-splash), and there
# is no login prompt on the screen (getty@tty1 off; SSH is unchanged, and Ctrl-Alt-F2 still gives a login with a keyboard).
# Safe to run again after a git pull.
# Run on the Judicom as your normal user:  bash install_services.sh        (uninstall_services.sh takes them away again)
set -euo pipefail
cd "$(dirname "$0")"
UNITS="judicom-baresip.service judicom-phone.service"
SYNC="judicom-contacts-sync.service judicom-contacts-sync.timer"     # fetches the caller list from the NAS every 10 minutes
for u in $UNITS $SYNC plymouth-retain-splash.conf; do
  [ -f "$u" ] || { echo "Missing $u - run this from the software/systemd folder." >&2; exit 1; }
done
[ -f /home/joe/.baresip/accounts ] || echo "Note: /home/joe/.baresip/accounts is missing; judicom-baresip will not register."
[ -f /home/joe/contacts.txt ] || echo "Note: /home/joe/contacts.txt is missing; the buttons will use the demo people."

sudo cp $UNITS $SYNC /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/plymouth-quit.service.d
sudo cp plymouth-retain-splash.conf /etc/systemd/system/plymouth-quit.service.d/judicom-retain-splash.conf
sudo systemctl daemon-reload
sudo systemctl disable getty@tty1.service 2>/dev/null || true      # no login prompt on the Judicom's screen
sudo systemctl enable $UNITS judicom-contacts-sync.timer
sudo systemctl restart $UNITS judicom-contacts-sync.timer
[ -f /home/joe/.ssh/judicom_sync ] || echo "Note: /home/joe/.ssh/judicom_sync is missing; the caller list cannot be fetched (see docs/DEPLOYMENT.md)."
sleep 3
echo
systemctl --no-pager --lines=0 status $UNITS || true
systemctl --no-pager list-timers judicom-contacts-sync.timer || true
echo
echo "Logs:  journalctl -u judicom-phone -f      journalctl -u judicom-baresip -f"
