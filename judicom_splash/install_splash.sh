#!/bin/bash
# Installs the Judicom boot picture on Raspberry Pi OS (Lite or Desktop).  Run from this folder as your normal user:  bash install_splash.sh
# Everything it changes is backed up first; uninstall_splash.sh puts it back.
set -euo pipefail
cd "$(dirname "$0")"

SUDO="${SUDO-sudo}"                                   # (SUDO="" is only for testing)
CMDLINE="${CMDLINE:-/boot/firmware/cmdline.txt}"
CONFIG="${CONFIG:-/boot/firmware/config.txt}"
THEME_DIR="/usr/share/plymouth/themes/judicom"

for f in theme/judicom.plymouth theme/judicom.script theme/splash.png; do
  [ -f "$f" ] || { echo "Missing $f - run this script from the unzipped folder." >&2; exit 1; }
done
[ -f "$CMDLINE" ] && [ -f "$CONFIG" ] || { echo "Cannot find $CMDLINE / $CONFIG" >&2; exit 1; }

if [ -z "${TEST_ONLY:-}" ]; then
  $SUDO apt-get install -y plymouth plymouth-themes
  $SUDO mkdir -p "$THEME_DIR"
  $SUDO cp theme/judicom.plymouth theme/judicom.script theme/splash.png "$THEME_DIR/"
fi

# --- back up, then edit config.txt ---
[ -f "$CONFIG.before-splash" ] || $SUDO cp "$CONFIG" "$CONFIG.before-splash"
for line in "disable_splash=1" "auto_initramfs=1"; do      # no rainbow square at power-on; use the initramfs (Plymouth lives in it)
  grep -qx "$line" "$CONFIG" || echo "$line" | $SUDO tee -a "$CONFIG" >/dev/null
done

# --- back up, then edit cmdline.txt (it must stay ONE line) ---
[ -f "$CMDLINE.before-splash" ] || $SUDO cp "$CMDLINE" "$CMDLINE.before-splash"
line="$(tr '\n' ' ' < "$CMDLINE" | sed 's/[[:space:]]*$//')"
for opt in quiet splash loglevel=3 logo.nologo vt.global_cursor_default=0 plymouth.ignore-serial-consoles; do
  case " $line " in *" $opt "*) ;; *) line="$line $opt" ;; esac
done
line="$(printf '%s' "$line" | sed 's/\(^\| \)console=tty1\( \|$\)/\1console=tty3\2/')"   # keep boot text off the visible console
printf '%s\n' "$line" | $SUDO tee "$CMDLINE" >/dev/null

if [ -z "${TEST_ONLY:-}" ]; then
  $SUDO plymouth-set-default-theme -R judicom          # makes it the default and rebuilds the initramfs (takes a minute)
fi
echo
echo "Done.  cmdline.txt now reads:"; cat "$CMDLINE"
echo "Reboot to see it:  sudo reboot"
