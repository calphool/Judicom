#!/bin/bash
# Puts cmdline.txt and config.txt back the way they were before install_splash.sh.  Run as your normal user.
set -euo pipefail
SUDO="${SUDO-sudo}"
CMDLINE="${CMDLINE:-/boot/firmware/cmdline.txt}"
CONFIG="${CONFIG:-/boot/firmware/config.txt}"
[ -f "$CMDLINE.before-splash" ] && $SUDO cp "$CMDLINE.before-splash" "$CMDLINE" && echo "restored $CMDLINE"
[ -f "$CONFIG.before-splash" ]  && $SUDO cp "$CONFIG.before-splash"  "$CONFIG"  && echo "restored $CONFIG"
echo "Reboot to go back to the normal text boot.  (Plymouth itself can stay installed; without 'splash' on the command line it does nothing.)"
