"""The Judicom: photos (now and then the info screen; the night clock at night) while nothing is happening, the phone screens
when the handset is lifted or a call comes in.

    python3 -m judicom.main                    on the Judicom: full screen, the real hook switch and buttons
    python3 -m judicom.main --demo --window    on a PC: l = lift / hang up the handset, 1 / 2 = left / right button
    python3 -m judicom.main --snapshots DIR    save a PNG of every phone screen into DIR, then stop (no screen needed)

Calls go through baresip (start it first: see judicom/calls.py); if it is not running, or cannot reach the PBX, the phone still
works and a button shows "The phone is not working." straight away.  --no-calls leaves baresip alone.

A message from the housekeeping website (judicom/messages.py) takes the screen from the photos, and gives it back when it has been
read.  It is not one of the machine's modes: the machine goes on as ever, so a call or the handset simply takes the screen from it.
The maintenance shell (judicom/maintenance.py) is the same kind of thing, and needs a touch screen and python3-pyte; so is the
hidden menu that opens it, and the games behind that menu (judicom/game.py), drawn at 60 frames a second while one is on.
The hidden keypad (judicom/keypad.py) is one of the machine's modes; its secret knock and its keys are taps on the touch screen.

These keys pretend to be the phone software (useful on a PC):
y = they answer   f = the call fails   e = they hang up
i = an incoming call from the person on the right button   u = an incoming call from a number that is not in the contacts file.
Other keys: space = next photo, t = a touch of the screen, q or Esc = quit.  Keys are typed in the terminal that started the program, or in the window.
Needs:  sudo apt install python3-pygame python3-pil python3-gpiozero python3-lgpio python3-pyte alsa-utils
"""
import argparse
import datetime
import signal
import sys
import time
from pathlib import Path

from . import config
from .calls import NoCalls
from .keypad import OPEN, Keypad, Knock
from .machine import Machine, Mode, Party

SIMULATED = {"y": ("answered",), "f": ("call_failed",), "e": ("remote_ended",)}
UNKNOWN_NUMBER = "+13125550199"                 # the "u" key: a caller who is not in the contacts file
CONTACTS_CHECK_SECONDS = 5.0                    # how often the contacts file is looked at for changes
SHELL_DRAW_SECONDS = 0.1                        # the maintenance shell is drawn at most this often: the phone comes first
FPS, GAME_FPS = 30, 60                          # frames a second: usually, and while the hidden game is on


class Phone:
    """Ties the parts together, without any drawing: switches and keys -> machine -> phone software and sounds.
    The program calls step() once a frame, then draws if step() says the screen changed."""

    def __init__(self, machine, controls, calls, sounds, photos, contacts=None, log=None, clock=time.monotonic, postbox=None,
                 taps=None, maintenance=None):
        self.machine, self.controls, self.calls, self.sounds, self.photos = machine, controls, calls, sounds, photos
        self.contacts, self.clock, self.postbox, self.taps, self.maintenance = contacts, clock, postbox, taps, maintenance
        self.log = log or (lambda msg: None)
        self._version = None
        self._buttons_changed = False
        self._checked = clock()
        self.keypad, self.keypad_knock = Keypad(clock), Knock(clock)
        if contacts is not None:
            machine.buttons = contacts.buttons()
            machine.lookup = contacts.lookup            # a number dialled on the keypad: their name, if they are in the list

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
        taps = self.taps.poll() if self.taps else []
        touched = bool(taps)
        for event in self.controls.poll() + self.calls.poll():
            if event[0] == "button" and self.game_showing:
                continue                                # the game's controls: nothing for the phone (nor its log)
            self._handle(event)
        for key in keys:                                # in order: "lift, then next photo" must not change the photo
            touched = touched or key == "t"
            if key == "next" and self.machine.mode == Mode.IDLE and not self.message and not self.shell_showing:
                self.photos.next()
            sim = self.simulated(key)
            for event in self.controls.key(key) + ([sim] if sim else []):
                self._handle(event)
        key_tones = self._keypad(taps)
        for action in self.machine.tick():
            self.calls.do(action)
        self.sounds.update(self.machine.dial_tone, self.machine.ringing, self.machine.dialing_tones)
        for key in key_tones:                           # after update(): the dial tone has let the handset's card go
            self.sounds.key_tone(key)
        self._check_contacts()
        changed = self.machine.version != self._version or self._buttons_changed
        self._buttons_changed = False
        idle, busy = self.machine.mode == Mode.IDLE, False
        if self.maintenance is not None:
            changed = self.maintenance.step(idle, not self.controls.off_hook, self.controls.held(), taps) or changed
            busy = self.maintenance.busy
        if self.postbox is not None:
            if touched and not busy:
                self.postbox.touched()
            changed = self.postbox.tick(idle and not busy) or changed
            if self.postbox.take_beep():
                self.sounds.beep()
        if changed:
            self._version = self.machine.version
            if idle and not self.message and not self.shell_showing:
                self.photos.start()                     # back to the photos: a fresh picture, no fade from one that was not on screen
        elif idle and not self.message and not self.shell_showing:
            self.photos.tick()
        return changed

    def _keypad(self, taps):
        """The hidden keypad: its knock while the handset is up, then its keys.  Returns the keys whose touch-tone to play now."""
        mode, tones = self.machine.mode, []
        if mode in (Mode.LIFTED, Mode.PLEASE_HANG_UP):
            bong = self.keypad_knock.update(self.machine.off_hook, taps)
            if bong is not None:
                self.sounds.bong(bong)
            if bong == OPEN:
                self._handle(("keypad",))
            return tones
        self.keypad_knock.reset()
        if self.machine.keypad_showing:
            in_call, typing = mode in (Mode.DIALING, Mode.CALLING, Mode.ONGOING), mode == Mode.KEYPAD
            for x, y in taps:
                key = self.keypad.press(x, y, in_call, typing)
                if key is None:
                    continue
                self._handle(("key", key))
                if self.machine.mode == Mode.KEYPAD and key.isdigit():
                    tones.append(key)                   # (the digit that completes the number is played by DIALING)
        self.keypad.tick()
        return tones

    @property
    def keypad_needs_draw(self):
        return self.machine.keypad_showing and self.keypad.dirty

    @property
    def message(self):
        """The message on the screen, or None."""
        return self.postbox.showing if self.postbox is not None else None

    @property
    def shell_showing(self):
        """The maintenance shell or the game has the screen (the shell stays open behind a call, without it)."""
        return self.maintenance is not None and self.maintenance.open and self.machine.mode == Mode.IDLE

    @property
    def game_showing(self):
        """A hidden game has the screen."""
        return self.maintenance is not None and self.maintenance.game is not None and self.machine.mode == Mode.IDLE

    @property
    def menu_showing(self):
        """The hidden menu has the screen."""
        return self.maintenance is not None and self.maintenance.menu is not None and self.machine.mode == Mode.IDLE

    def _check_contacts(self):
        now = self.clock()
        if self.contacts is None or now - self._checked < CONTACTS_CHECK_SECONDS:
            return
        self._checked = now
        if self.contacts.refresh():
            self.machine.buttons = self.contacts.buttons()
            self._buttons_changed = True                # the names above the arrows may have changed

    def _handle(self, event):
        if event[0] in ("lifted", "button") and self.message:
            self.postbox.finish()                       # and the handset or button goes on to do what it always does
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
    from . import message_view
    from .faces import Faces
    from .messages import Message
    display = Display(headless=True)
    view = CallView(buttons, Faces())
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    left = next(iter(buttons.values()))
    shots = [("1_lifted", Mode.LIFTED, None), ("2_calling", Mode.CALLING, left), ("3_ongoing", Mode.ONGOING, left),
             ("4_no_answer", Mode.NO_ANSWER, left), ("5_ended", Mode.ENDED, left), ("6_incoming", Mode.INCOMING, Party("Hannah", "granddaughter")),
             ("7_incoming_unknown", Mode.INCOMING, Party(dial="312-555-0199")), ("8_please_hang_up", Mode.PLEASE_HANG_UP, None),
             ("9_out_of_order", Mode.OUT_OF_ORDER, left)]
    for name, mode, party in shots:
        view.draw(display.logical, mode, party, 0.35)
        pygame.image.save(display.logical, str(folder / (name + ".png")))
    message_view.show(display.logical, Message("", left.name or "Ann", "Hi Mom! We will come by on Sunday after church. Love you!"), Faces())
    pygame.image.save(display.logical, str(folder / "10_message.png"))
    from types import SimpleNamespace
    from . import keypad_view
    from .keypad import EMERGENCY, Keypad
    pad = Keypad()
    keypads = [("11_keypad", SimpleNamespace(mode=Mode.KEYPAD, digits="312555", notice="", party=None)),
               ("12_keypad_refused", SimpleNamespace(mode=Mode.KEYPAD, digits="", notice=EMERGENCY, party=None)),
               ("13_keypad_calling", SimpleNamespace(mode=Mode.CALLING, digits="", notice="", party=Party(dial="3125550123", shown="312-555-0123"))),
               ("14_keypad_call", SimpleNamespace(mode=Mode.ONGOING, digits="", notice="", party=Party(dial="3125550123", shown="312-555-0123")))]
    for name, state in keypads:
        keypad_view.show(display.logical, state, pad, Faces())
        pygame.image.save(display.logical, str(folder / (name + ".png")))
    display.close()
    return ([folder / (name + ".png") for name, _, _ in shots] + [folder / "10_message.png"] +
            [folder / (name + ".png") for name, _ in keypads])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.main", description="The Judicom phone.")
    ap.add_argument("folder", nargs="?", default=str(config.PHOTO_DIR), help="photo folder (default %(default)s)")
    ap.add_argument("--demo", action="store_true", help="no GPIO: l = lift / hang up, 1 / 2 = buttons")
    ap.add_argument("--speed", type=float, default=1.0, help="run the phone's timers this many times faster (for trying it out)")
    ap.add_argument("--no-sound", action="store_true", help="no dial tone and no ringer")
    ap.add_argument("--no-calls", action="store_true", help="do not use baresip (the keys y / f / e / i / u pretend to be it)")
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
    from .sound import make_amp
    sounds = Sounds(log, enabled=not args.no_sound, amp=None if args.demo or args.no_sound else make_amp(log))
    from .events import EventList
    from .home import Home
    from .weather import Weather
    weather = None
    if config.WEATHER_LAT is None or config.WEATHER_LON is None:
        log("no weather screen: no [weather] latitude / longitude in %s" % config.SITE_FILE)
    else:
        weather = Weather(log=log)
        weather.start()                                  # in the background: never holds the screen up
    from .jokes import JokeDeck
    from .verses import VerseDeck
    photos = Home(PhotoView(PhotoDeck(args.folder), log=log), EventList(log=log), weather, log=log,    # photos, info / verse / weather
                  verses=VerseDeck(log=log), jokes=JokeDeck(log=log))                                 # screens, night clock
    if args.no_calls:
        calls = NoCalls(log)
    else:
        from .calls import Baresip
        calls = Baresip(log=log)
    from . import message_view
    from .faces import Faces
    from .messages import Postbox
    from .touch import Taps
    faces = Faces(log=log)
    postbox = Postbox(can_show=lambda: not photos.is_night(datetime.datetime.now()), log=log)
    taps = None if args.demo or args.window else Taps(log, flip=args.flip)
    maintenance = shell_view = None
    if taps is not None:
        try:
            from . import menu_view
            from .game import Session
            from .maintenance import Maintenance
            from .shell import Shell
            from .shell_view import ShellView
            from .bricks import BrickGame
            from .bricks_view import BrickView
            from .game_sound import bricks_sounds, mars_sounds
            from .mars import MarsGame
            from .mars_view import MarsView
            games = {                                                                   # the hidden menu's games, in its order
                "Invaders": lambda: Session(sounds, time.monotonic, log),
                "Brick Breaker": lambda: Session(sounds, time.monotonic, log, best_file=config.BRICKS_BEST_FILE,
                                                 make_game=BrickGame, make_view=BrickView, make_sounds=bricks_sounds),
                "Mars Patrol": lambda: Session(sounds, time.monotonic, log, best_file=config.MARS_BEST_FILE,
                                               make_game=MarsGame, make_view=MarsView, make_sounds=mars_sounds),
            }
            maintenance = Maintenance(sounds, lambda: Shell(log=log), log=log, games=games)
            shell_view = ShellView()
        except ImportError as exc:                       # the phone is what matters: it goes on without the shell
            log("(no maintenance shell: %s - sudo apt install python3-pyte)" % exc)
    phone = Phone(Machine(buttons, clock=clock, log=log, phone_ok=lambda: calls.ready), controls, calls, sounds, photos, contacts,
                  log, postbox=postbox, taps=taps, maintenance=maintenance)
    call_view = CallView(buttons, faces)
    call_view.preload()
    from . import keypad_view
    log("Screen %dx%d%s.  Photos: %s.  Switches: %s.  %s" % (display.size[0], display.size[1],
        ", turned 90 degrees" if display.rotate else "", args.folder, source, sounds.describe()))
    log("Pretend phone software: y = answer, f = fail, e = they hang up, i = incoming call (right button's person), "
        "u = incoming call (unknown number).  space = next photo, q = quit.")

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))              # a clean stop when a service is stopped
    terminal = TerminalKeys() if TerminalKeys.available() else None
    frames = pygame.time.Clock()
    hint_level = None
    shell_drawn = 0.0
    try:
        while True:
            keys = (terminal.poll() if terminal else []) + window_keys(pygame.event.get())
            if "quit" in keys:
                break
            changed = phone.step(keys)
            mode = phone.machine.mode
            if phone.game_showing:
                if changed or maintenance.game.steps:
                    display.present_small(maintenance.game.draw())
            elif phone.menu_showing:
                if changed:
                    menu_view.show(display.logical, maintenance.menu)
                    display.present()
            elif phone.shell_showing:
                now = time.monotonic()
                if changed or (maintenance.needs_draw and now - shell_drawn >= SHELL_DRAW_SECONDS):
                    shell_view.draw(display.logical, maintenance.shell, maintenance.keyboard)
                    display.present()
                    shell_drawn = now
            elif phone.message:
                level = message_view.pulse(time.monotonic())
                if changed:
                    message_view.show(display.logical, phone.message, faces, postbox.more, level)
                    display.present()
                elif level != hint_level:
                    message_view.show_hint(display.logical, postbox.more, level)
                    display.present()
                hint_level = level
            elif phone.machine.keypad_showing:
                if changed or phone.keypad_needs_draw:
                    keypad_view.show(display.logical, phone.machine, phone.keypad, faces)
                    phone.keypad.dirty = False
                    display.present()
            elif mode == Mode.IDLE:
                if changed or photos.needs_redraw():
                    photos.draw(display.logical)
                    display.present()
            elif changed or call_view.animated(mode):
                call_view.buttons = phone.machine.buttons
                call_view.draw(display.logical, mode, phone.machine.party, time.monotonic())
                display.present()
            frames.tick(GAME_FPS if phone.game_showing else FPS)
    except KeyboardInterrupt:
        pass
    finally:
        if maintenance:
            maintenance.close()
        calls.close()
        if taps:
            taps.close()
        if weather:
            weather.stop()
        sounds.close()
        controls.close()
        if terminal:
            terminal.close()
        display.close()
    print("Bye.")


if __name__ == "__main__":
    main()
