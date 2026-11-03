JUDICOM BOOT PICTURE
====================
Shows the "Judicom phone starting up..." picture instead of the scrolling boot text.

Files
  judicom_splash_portrait.png   the picture as it looks on the portrait-mounted screen (600 x 1024) - for looking at / other uses
  theme/splash.png              the same picture turned 90 degrees (1024 x 600) so it looks upright on the sideways-mounted panel
  theme/judicom.plymouth, theme/judicom.script   the Plymouth theme (picture centred, no text, no progress bar)
  install_splash.sh / uninstall_splash.sh
  judicom_splash_native_upside_down_alternative.png   only needed if the picture comes out upside-down (see below)

Install (on the Pi, as your normal user)
  unzip judicom_splash_package.zip && cd judicom_splash
  bash install_splash.sh
  sudo reboot
The script installs Plymouth, copies the theme, adds disable_splash=1 and auto_initramfs=1 to /boot/firmware/config.txt, and adds
"quiet splash loglevel=3 logo.nologo vt.global_cursor_default=0 plymouth.ignore-serial-consoles" to /boot/firmware/cmdline.txt
(changing console=tty1 to console=tty3).  Both files are backed up first (*.before-splash).  fbcon=rotate:3 stays as it is.

What you should see: black for the first few seconds, then the picture until the system has started.

If the picture is upside-down
  sudo cp judicom_splash_native_upside_down_alternative.png /usr/share/plymouth/themes/judicom/splash.png
  sudo plymouth-set-default-theme -R judicom && sudo reboot

Undo
  bash uninstall_splash.sh && sudo reboot

Notes
  * Boot messages are hidden.  To see them again for troubleshooting, remove "quiet splash" from cmdline.txt (or run uninstall_splash.sh).
  * If the Judicom app starts on the console, make its systemd service start after plymouth-quit.service so the two don't fight over the screen.
  * Not tested on the real Pi yet - the edits to cmdline.txt/config.txt were tested on copies only.
