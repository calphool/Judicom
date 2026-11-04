#!/bin/bash
# Makes the Judicom start by itself at power-on: installs and starts judicom-baresip and judicom-phone.
# Run on the Judicom as your normal user:  bash install_services.sh        (uninstall_services.sh takes them away again)
set -euo pipefail
cd "$(dirname "$0")"
UNITS="judicom-baresip.service judicom-phone.service"
for u in $UNITS; do
  [ -f "$u" ] || { echo "Missing $u - run this from the software/systemd folder." >&2; exit 1; }
done
[ -f /home/joe/.baresip/accounts ] || echo "Note: /home/joe/.baresip/accounts is missing; judicom-baresip will not register."
[ -f /home/joe/contacts.txt ] || echo "Note: /home/joe/contacts.txt is missing; the buttons will use the demo people."

sudo cp $UNITS /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now $UNITS
sleep 3
echo
systemctl --no-pager --lines=0 status $UNITS || true
echo
echo "Logs:  journalctl -u judicom-phone -f      journalctl -u judicom-baresip -f"
