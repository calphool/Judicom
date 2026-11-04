#!/bin/bash
# Stops judicom-phone and judicom-baresip and removes them (the Judicom then no longer starts by itself).
set -euo pipefail
UNITS="judicom-photo-sync.timer judicom-photo-sync.service judicom-contacts-sync.timer judicom-contacts-sync.service"
UNITS="$UNITS judicom-phone.service judicom-baresip.service"
sudo systemctl disable --now $UNITS || true
for u in $UNITS; do sudo rm -f "/etc/systemd/system/$u"; done
sudo rm -f /etc/systemd/system/plymouth-quit.service.d/judicom-retain-splash.conf
sudo rmdir /etc/systemd/system/plymouth-quit.service.d 2>/dev/null || true
sudo rm -f /etc/systemd/journald.conf.d/90-judicom.conf && sudo systemctl restart systemd-journald     # the log in memory again
sudo systemctl daemon-reload
sudo systemctl enable getty@tty1.service                           # the login prompt on the screen again
echo "Removed.  Start things by hand again:  baresip   and   python3 -m judicom.main"
