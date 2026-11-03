"""The Judicom: photos while nothing is happening, the phone screens when the handset is lifted or a call comes in.

    python3 -m judicom.main                    on the Judicom: full screen, the real hook switch and buttons
    python3 -m judicom.main --demo --window    on a PC: l = lift / hang up the handset, 1 / 2 = left / right button
    python3 -m judicom.main --snapshots DIR    save a PNG of every phone screen into DIR, then stop (no screen needed)

The phone software (baresip) is not connected yet, so a call never really goes out: "Calling..." turns into "No answer." after
RING_OUT_SECONDS.  These keys pretend to be it:  y = they answer   f = the call fails   e = they hang up
i = an incoming call from the person on the right button   u = an incoming call from a number that is not in the contacts file.
Other keys: space = next photo, q or Esc = quit.  Keys are typed in the terminal that started the program, or in the window.
Needs:  sudo apt install python3-pygame python3-pil python3-gpiozero python3-lgpio alsa-utils
"""
import argparse
import signal
import sys
import time
from pathlib import Path

from . import config
from .machine import Machine, Mode, Party

SIMULATED = {"y": ("answered",), "f": ("call_failed",), "e": ("remote_ended",)}
UNKNOWN_NUMBER = "+13125550199"                 # the "u" key: a caller who is not in the contacts file
CONTACTS_CHECK_SECONDS = 5.0                    # how often the contacts file is looked at for changes


class NoCalls:
    """Stands in for the phone software until baresip is connected: says what it would have done."""

    def __init__(self, log):
        self.log = log

    def do(self, action):
        what = " ".join(a.label if isinstance(a, Party) else a for a in action)
        self.log("      (phone software not connected: would %s)" % what)


class Phone:
    """Ties the parts together, without any drawing: switches and keys -> machine -> phone software and sounds.
    The program calls step() once a frame, then draws if step() says the screen changed."""

    def __init__(self, machine, controls, calls, sounds, photos, contacts=None, log=None, clock=time.monotonic):
        self.machine, self.controls, self.calls, self.sounds, self.photos = machine, controls, calls, sounds, photos
        self.contacts, self.clock = contacts, clock
        self.log = log or (lambda msg: None)
        self._version = None
        self._buttons_changed = False
        self._checked = clock()
        if contacts is not None:
            machine.buttons = contacts.buttons()

    def simulated(self, key):
        """The pretend phone-software event for a key, or None."""
        if key in SIMULATED:
            return SIMULATED[key]
        if key == "i":                                  # the right button's person calling
            right = self.machine.buttons.get("right")
            if right is None:
                return ("incoming", UNKNOWN_NUMBER)
            if any(ch.isdigit() for ch in right.dial):
                return ("incoming", right.dial)         # by number, the way the phone software will: tests the name lookup too
            return ("incoming", right)                  # the demo people in config.py have no numbers: the person as is
        if key == "u":
            return ("incoming", UNKNOWN_NUMBER)
        return None

    def step(self, keys=()):
        """keys: key names from keys.py.  Returns True when the mode or the party changed (the whole screen must be drawn)."""
        for event in self.controls.poll():
            self._handle(event)
        for key in keys:                                # in order: "lift, then next photo" must not change the photo
            if key == "next" and self.machine.mode == Mode.IDLE:
                self.photos.next()
            sim = self.simulated(key)
            for event in self.controls.key(key) + ([sim] if sim else []):
                self._handle(event)
        for action in self.machine.tick():
            self.calls.do(action)
        self.sounds.update(self.machine.dial_tone, self.machine.ringing, self.machine.dialing_tones)
        self._check_contacts()
        changed = self.machine.version != self._version or self._buttons_changed
        self._buttons_changed = False
        if changed:
            self._version = self.machine.version
            if self.machine.mode == Mode.IDLE:
                self.photos.start()                     # back to the photos: a fresh picture, no fade from one that was not on screen
        elif self.machine.mode == Mode.IDLE:
            self.photos.tick()
        return changed

    def _check_contacts(self):
        now = self.clock()
        if self.contacts is None or now - self._checked < CONTACTS_CHECK_SECONDS:
            return
        self._checked = now
        if self.contacts.refresh():
            self.machine.buttons = self.contacts.buttons()
            self._buttons_changed = True                # the names above the arrows may have changed

    def _handle(self, event):
        if event[0] == "incoming" and len(event) > 1 and not isinstance(event[1], Party):
            if self.contacts is not None:               # the phone software gives a number: put the name to it
                self.contacts.refresh()
                event = ("incoming", self.contacts.lookup(event[1]))
            else:
                event = ("incoming", Party(dial=str(event[1])))
        self.log(" ".join(x.label if isinstance(x, Party) else str(x) for x in event))
        for action in self.machine.handle(*event):
            self.calls.do(action)


def snapshots(folder, buttons):
    """Save every phone screen as an upright PNG."""
    import pygame
    from .call_view import CallView
    from .display import Display
    display = Display(headless=True)
    view = CallView(buttons)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    left = next(iter(buttons.values()))
    shots = [("1_lifted", Mode.LIFTED, None), ("2_calling", Mode.CALLING, left), ("3_ongoing", Mode.ONGOING, left),
             ("4_no_answer", Mode.NO_ANSWER, left), ("5_ended", Mode.ENDED, left), ("6_incoming", Mode.INCOMING, Party("Hannah", "granddaughter")),
             ("7_incoming_unknown", Mode.INCOMING, Party(dial="312-555-0199")), ("8_please_hang_up", Mode.PLEASE_HANG_UP, None)]
    for name, mode, party in shots:
        view.draw(display.logical, mode, party, 0.35)
        pygame.image.save(display.logical, str(folder / (name + ".png")))
    display.close()
    return [folder / (name + ".png") for name, _, _ in shots]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.main", description="The Judicom phone.")
    ap.add_argument("folder", nargs="?", default=str(config.PHOTO_DIR), help="photo folder (default %(default)s)")
    ap.add_argument("--demo", action="store_true", help="no GPIO: l = lift / hang up, 1 / 2 = buttons")
    ap.add_argument("--speed", type=float, default=1.0, help="run the phone's timers this many times faster (for trying it out)")
    ap.add_argument("--no-sound", action="store_true", help="no dial tone and no ringer")
    ap.add_argument("--snapshots", metavar="DIR", help="save a PNG of every phone screen into DIR and stop")
    ap.add_argument("--window", action="store_true", help="small window instead of full screen (for a PC), no turning")
    ap.add_argument("--no-rotate", action="store_true", help="do not turn the picture 90 degrees (normal portrait monitor)")
    ap.add_argument("--flip", action="store_true", help="turn it the other way (use if the picture is upside-down)")
    args = ap.parse_args(argv)
    if args.speed <= 0:
        sys.exit("--speed must be above zero")
    from .contacts import Contacts
    start = time.monotonic()
    log = lambda msg: print("[%7.1f s] %s" % (time.monotonic() - start, msg), flush=True)       # noqa: E731
    contacts = Contacts(log=log)
    buttons = contacts.buttons()
    if args.snapshots:
        for path in snapshots(args.snapshots, buttons):
            print(path)
        return

    import pygame
    from .call_view import CallView
    from .display import Display
    from .inputs import make_controls
    from .keys import TerminalKeys, window_keys
    from .photo_view import PhotoView
    from .photos import PhotoDeck
    from .sound import Sounds

    clock = lambda: start + (time.monotonic() - start) * args.speed                           # noqa: E731
    controls, source = make_controls(args.demo, log)
    display = Display(window=args.window, rotate=not args.no_rotate, flip=args.flip)
    sounds = Sounds(log, enabled=not args.no_sound)
    photos = PhotoView(PhotoDeck(args.folder), log=log)
    phone = Phone(Machine(buttons, clock=clock, log=log), controls, NoCalls(log), sounds, photos, contacts, log)
    call_view = CallView(buttons)
    log("Screen %dx%d%s.  Photos: %s.  Switches: %s.  %s" % (display.size[0], display.size[1],
        ", turned 90 degrees" if display.rotate else "", args.folder, source, sounds.describe()))
    log("Pretend phone software: y = answer, f = fail, e = they hang up, i = incoming call (right button's person), "
        "u = incoming call (unknown number).  space = next photo, q = quit.")

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))              # a clean stop when a service is stopped
    terminal = TerminalKeys() if TerminalKeys.available() else None
    frames = pygame.time.Clock()
    try:
        while True:
            keys = (terminal.poll() if terminal else []) + window_keys(pygame.event.get())
            if "quit" in keys:
                break
            changed = phone.step(keys)
            mode = phone.machine.mode
            if mode == Mode.IDLE:
                if changed or photos.needs_redraw():
                    photos.draw(display.logical)
                    display.present()
            elif changed or call_view.animated(mode):
                call_view.buttons = phone.machine.buttons
                call_view.draw(display.logical, mode, phone.machine.party, time.monotonic())
                display.present()
            frames.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        sounds.close()
        controls.close()
        if terminal:
            terminal.close()
        display.close()
    print("Bye.")


if __name__ == "__main__":
    main()
