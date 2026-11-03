"""The hook switch and the two buttons, turned into events.   python3 -m judicom.inputs   prints them (a wiring check).

    controls = make_controls()          # the real switches (gpiozero or RPi.GPIO); make_controls(demo=True) on a PC
    for event in controls.poll():       # call often (the main loop does, 30 times a second)
        ...                             # ("lifted",)  ("hung_up",)  ("button", "left")  ("button", "right")

The hook switch has three contacts (two normally closed, one normally open, see config.py).  Each one votes on whether the handset is
up; the majority wins, so one broken or dirty contact does not fake a lift or a hang-up.  A disagreement that lasts is reported once
through `log` (a wiring fault worth fixing).  A new hook state only counts once it has lasted LIFT_SETTLE / HANG_UP_SETTLE seconds,
a button press once it has lasted BUTTON_SETTLE.  A button held down when the program starts does not count until it is let go and
pressed again.  If the handset is up when the program starts, the first poll() reports ("lifted",) once it has settled.

Without GPIO (on a PC, or --demo) the keys do it instead: l = lift / hang up the handset, 1 = left button, 2 = right button.
Time comes from `clock` (time.monotonic), which tests replace with a fake; the pins from a reader with is_low(pin), likewise.
"""
import sys
import time

from . import config

FAULT_SECONDS = 2.0           # hook contacts that disagree for this long are reported (once, until they agree again)


# ------------------------------------------------------------------ pin readers ----------------------------------------------
class GpiozeroPins:
    """Reads the pins with gpiozero (internal pull-ups on).  The debouncing is done in Controls, not here."""

    def __init__(self, pins):
        from gpiozero import Button
        self._pins = {p: Button(p, pull_up=True, bounce_time=None) for p in pins}

    def is_low(self, pin):
        return self._pins[pin].is_pressed              # with pull_up=True "pressed" means the pin is pulled LOW

    def close(self):
        for b in self._pins.values():
            b.close()


class RpiGpioPins:
    """The same with the older RPi.GPIO library."""

    def __init__(self, pins):
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for p in pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def is_low(self, pin):
        return self._gpio.input(pin) == self._gpio.LOW

    def close(self):
        self._gpio.cleanup()


def open_pins(pins):
    """A reader for the real pins, or SystemExit with what to install."""
    errors = []
    for name, cls in (("gpiozero", GpiozeroPins), ("RPi.GPIO", RpiGpioPins)):
        try:
            return cls(pins), name
        except Exception as exc:                        # noqa: BLE001 - try the next library
            errors.append("%s: %s" % (name, exc))
    sys.exit("Cannot read the GPIO pins.\n  " + "\n  ".join(errors) +
             "\nInstall a library:  sudo apt install python3-gpiozero python3-lgpio      (or use --demo on a PC)")


# ------------------------------------------------------------------ debouncing -----------------------------------------------
class Settled:
    """A yes/no reading that only changes once the new value has lasted `settle(new_value)` seconds."""

    def __init__(self, value, settle):
        self.value = value
        self._settle = settle
        self._candidate = value
        self._since = None

    def update(self, raw, t):
        """Feed the latest reading; returns True when the settled value has just changed."""
        if raw == self.value:
            self._candidate, self._since = raw, None
            return False
        if raw != self._candidate or self._since is None:
            self._candidate, self._since = raw, t
        if t - self._since >= self._settle(raw):
            self.value, self._since = raw, None
            return True
        return False


class Controls:
    """The real switches: poll() returns the events since the last call."""

    def __init__(self, reader, nc_pins=config.HOOK_NC_PINS, no_pins=config.HOOK_NO_PINS, button_pins=None,
                 pressed_on_hook=config.HOOK_PRESSED_ON_HOOK, lift_settle=config.LIFT_SETTLE, hang_up_settle=config.HANG_UP_SETTLE,
                 button_settle=config.BUTTON_SETTLE, clock=time.monotonic, log=None):
        self.reader, self.clock, self.log = reader, clock, log or (lambda msg: None)
        self.nc_pins, self.no_pins = tuple(nc_pins), tuple(no_pins)
        self.button_pins = dict(config.BUTTON_PINS if button_pins is None else button_pins)
        self.pressed_on_hook = pressed_on_hook
        self._hook = Settled(False, lambda up: lift_settle if up else hang_up_settle)     # starts "on hook"; a lifted handset is reported
        self._buttons = {name: Settled(reader.is_low(pin), lambda down: button_settle) for name, pin in self.button_pins.items()}
        self._held_at_start = {name: s.value for name, s in self._buttons.items()}
        self._disagree_since = None
        self._fault_reported = False

    @property
    def off_hook(self):
        return self._hook.value

    def hook_votes(self):
        """(contacts saying the handset is up, number of contacts)."""
        votes = []
        for pin in self.nc_pins + self.no_pins:
            pressed = (not self.reader.is_low(pin)) if pin in self.nc_pins else self.reader.is_low(pin)   # NC opens when pressed
            votes.append(pressed != self.pressed_on_hook)
        return sum(votes), len(votes)

    def poll(self):
        t = self.clock()
        events = []
        up, n = self.hook_votes()
        raw = self._hook.value if up * 2 == n else up * 2 > n       # a tie (an even number of contacts) changes nothing
        self._check_fault(up, n, t)
        if self._hook.update(raw, t):
            events.append(("lifted",) if raw else ("hung_up",))
        for name, pin in self.button_pins.items():
            s = self._buttons[name]
            if s.update(self.reader.is_low(pin), t):
                if not s.value:
                    self._held_at_start[name] = False
                elif not self._held_at_start[name]:
                    events.append(("button", name))
        return events

    def _check_fault(self, up, n, t):
        if 0 < up < n:
            if self._disagree_since is None:
                self._disagree_since = t
            elif t - self._disagree_since >= FAULT_SECONDS and not self._fault_reported:
                self._fault_reported = True
                detail = ", ".join("GPIO %d %s" % (p, "low" if self.reader.is_low(p) else "high") for p in self.nc_pins + self.no_pins)
                self.log("WARNING: the hook switch contacts disagree (%d of %d say the handset is up): %s.  Check the wiring." % (up, n, detail))
        else:
            if self._fault_reported:
                self.log("The hook switch contacts agree again.")
            self._disagree_since, self._fault_reported = None, False

    def key(self, key):
        return []

    def close(self):
        self.reader.close()


class KeyControls:
    """No GPIO: keys stand in for the switches.  l = lift / hang up, 1 = left button, 2 = right button."""

    KEYS = {"1": "left", "2": "right"}

    def __init__(self):
        self.off_hook = False

    def poll(self):
        return []

    def key(self, key):
        if key == "l":
            self.off_hook = not self.off_hook
            return [("lifted",) if self.off_hook else ("hung_up",)]
        if key in self.KEYS:
            return [("button", self.KEYS[key])]
        return []

    def close(self):
        pass


def make_controls(demo=False, log=None):
    """(controls, description)."""
    if demo:
        return KeyControls(), "keys (l = lift / hang up, 1 / 2 = buttons), no GPIO"
    pins = list(config.HOOK_NC_PINS) + list(config.HOOK_NO_PINS) + list(config.BUTTON_PINS.values())
    reader, name = open_pins(pins)
    return Controls(reader, log=log), name


# ------------------------------------------------------------------ wiring check ---------------------------------------------
def main(argv=None):
    import argparse
    from .keys import TerminalKeys
    ap = argparse.ArgumentParser(prog="python3 -m judicom.inputs", description="Print the hook switch and button events (q = quit).")
    ap.add_argument("--demo", action="store_true", help="no GPIO: l = lift / hang up, 1 / 2 = buttons")
    args = ap.parse_args(argv)
    start = time.monotonic()
    log = lambda msg: print("[%7.1f s] %s" % (time.monotonic() - start, msg), flush=True)      # noqa: E731
    controls, source = make_controls(args.demo, log)
    terminal = TerminalKeys() if TerminalKeys.available() else None
    log("Reading %s.  Handset %s.  q = quit." % (source, "UP" if controls.off_hook else "down (or not yet settled)"))
    try:
        while True:
            keys = terminal.poll() if terminal else []
            if "quit" in keys:
                break
            for event in controls.poll() + [e for k in keys for e in controls.key(k)]:
                log(" ".join(event))
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        if terminal:
            terminal.close()
        controls.close()


if __name__ == "__main__":
    main()
