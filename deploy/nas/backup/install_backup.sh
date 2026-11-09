#!/bin/bash
# Installs the weekly NAS backup (run on the NAS from this folder):  bash install_backup.sh
set -euo pipefail
cd "$(dirname "$0")"
sudo install -m 755 naspi_backup.sh /usr/local/sbin/naspi_backup.sh
sudo install -m 644 naspi-backup.service naspi-backup.timer /etc/systemd/system/
[ -f /etc/naspi-backup.env ] || sudo install -m 600 naspi-backup.env.example /etc/naspi-backup.env
sudo systemctl daemon-reload
sudo systemctl enable --now naspi-backup.timer
systemctl list-timers naspi-backup.timer --no-pager
