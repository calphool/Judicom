#!/bin/sh
# Installs (or updates) the Judicom housekeeping website on the NAS.  Run on the NAS as pi:
#     bash /home/pi/Judicom/deploy/nas/admin/install_admin.sh
# It needs this repository at /home/pi/Judicom (git clone https://github.com/calphool/Judicom.git /home/pi/Judicom) and
# python3-flask + python3-pil (already there on the NAS).  Later updates:  cd ~/Judicom && git pull && sudo systemctl restart judicom-admin
set -eu
[ -f /home/pi/Judicom/deploy/nas/admin/judicom_admin.py ] || { echo "the repository is not at /home/pi/Judicom" >&2; exit 1; }
python3 -c "import flask, PIL" || { echo "needs: sudo apt install python3-flask python3-pil" >&2; exit 1; }
sudo install -m 644 /home/pi/Judicom/deploy/nas/admin/judicom-admin.service /etc/systemd/system/judicom-admin.service
sudo systemctl daemon-reload
sudo systemctl enable --now judicom-admin.service
sudo systemctl restart judicom-admin.service
sleep 3
systemctl --no-pager --lines=0 status judicom-admin.service | head -3
echo "Open http://naspi.local:8080 (home) or http://100.64.0.1:8080 (Tailscale)."
