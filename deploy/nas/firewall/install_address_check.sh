#!/bin/bash
# Installs the hourly VoIP.ms address check on the NAS.  Run it yourself, as pi, from the folder it is in:
#     bash install_address_check.sh
# It backs up what it replaces, checks the new firewall rules before loading them, and changes nothing if that check fails.
set -euo pipefail
cd "$(dirname "$0")"
for f in voipms_address_check.py voipms-address-check.service voipms-address-check.timer; do
  [ -f "$f" ] || { echo "Missing $f - run this from the folder it came in." >&2; exit 1; }
done
echo "1. What the check would do (nothing is changed yet):"
sudo python3 voipms_address_check.py --dry-run
stamp=$(date +%Y-%m-%d-%H%M)
sudo cp -p /etc/asterisk-firewall.nft "/etc/asterisk-firewall.nft.before-address-check-$stamp"
cp -p /home/pi/asterisk/config/voipms.conf "/home/pi/asterisk/config/voipms.conf.before-address-check-$stamp"
echo "2. Backups: /etc/asterisk-firewall.nft.before-address-check-$stamp and voipms.conf.before-address-check-$stamp"
echo "3. Checking the new firewall rules before loading them:"
tmp=$(mktemp)
# (written as pi: Debian does not let even root write into another user's file in /tmp)
python3 -c "import sys; sys.path.insert(0, '.'); import voipms_address_check as v; open('$tmp', 'w').write(v.nft_text(v.file_addresses(open('/etc/asterisk-firewall.nft').read())))"
sudo nft -c -f "$tmp" && echo "   the rules are valid" || { echo "   the new rules are NOT valid: nothing changed"; rm -f "$tmp"; exit 1; }
rm -f "$tmp"
sudo install -m 755 voipms_address_check.py /usr/local/sbin/voipms_address_check.py
sudo install -m 644 voipms-address-check.service voipms-address-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
echo "4. First run (turns the fixed rule into the address list, and checks the address):"
sudo systemctl start voipms-address-check.service
journalctl -u voipms-address-check -n 5 --no-pager -o cat
sudo systemctl enable --now voipms-address-check.timer
echo "5. The firewall table now:"
sudo nft list table inet asterisk_test
systemctl --no-pager list-timers voipms-address-check.timer
