"""Shows the family photos on the Judicom screen, nothing else.   python3 -m judicom.photo_show

    python3 -m judicom.photo_show                 full screen on the Judicom, pictures from /home/joe/photos
    python3 -m judicom.photo_show --window        a small window on a PC (no turning)

Keys (typed into the terminal you started it from, or on a keyboard): space or right arrow = next picture, q or Esc = quit.
Ctrl-C also quits.  Needs:  sudo apt install python3-pygame python3-pil
"""
import argparse
import signal
import sys
import time
from pathlib import Path

from . import config
from .keys import TerminalKeys, window_keys
from .photos import PhotoDeck


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.photo_show", description="Show the family photos.")
    ap.add_argument("folder", nargs="?", default=str(config.PHOTO_DIR), help="photo folder (default %(default)s)")
    ap.add_argument("--seconds", type=float, default=config.PHOTO_SECONDS, help="seconds per picture (default %(default)s)")
    ap.add_argument("--window", action="store_true", help="small window instead of full screen (for a PC), no turning")
    ap.add_argument("--no-rotate", action="store_true", help="do not turn the picture 90 degrees (normal portrait monitor)")
    ap.add_argument("--flip", action="store_true", help="turn it the other way (use if the picture is upside-down)")
    args = ap.parse_args(argv)
    if args.seconds <= 0:
        sys.exit("--seconds must be above zero")

    import pygame
    from .display import Display
    from .photo_view import PhotoView

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Note: python3-pil is not installed, so phone photos may come out sideways (sudo apt install python3-pil).")

    if not Path(args.folder).is_dir():
        print("Note: the photo folder %s does not exist (yet); the screen will say so and keep looking." % args.folder)
    display = Display(window=args.window, rotate=not args.no_rotate, flip=args.flip)
    start = time.monotonic()
    log = lambda msg: print("[%7.1f s] %s" % (time.monotonic() - start, msg), flush=True)      # noqa: E731
    view = PhotoView(PhotoDeck(args.folder), seconds=args.seconds, log=log)
    print("Screen %dx%d%s.  Folder: %s.  %g seconds per picture.  Space = next picture, q = quit."
          % (display.size[0], display.size[1], ", turned 90 degrees" if display.rotate else "", args.folder, args.seconds))

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))              # a clean stop when a service is stopped
    terminal = TerminalKeys() if TerminalKeys.available() else None
    clock = pygame.time.Clock()
    running = True
    try:
        view.start()
        while running:
            for key in (terminal.poll() if terminal else []) + window_keys(pygame.event.get()):
                if key == "quit":
                    running = False
                elif key == "next":
                    view.next()
            view.tick()
            if view.needs_redraw():
                view.draw(display.logical)
                display.present()
            clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        if terminal:
            terminal.close()
        display.close()
    print("Bye.")


if __name__ == "__main__":
    main()
