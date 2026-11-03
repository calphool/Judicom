"""What the phone is doing: which screen shows, when the dial tone and the ringer are on, and what the call software must do.
No pygame, no GPIO, no SIP: events go in, actions come out, so all of it can be tested anywhere.

    machine = Machine()
    actions = machine.handle("lifted")              # from inputs.py: lifted, hung_up, button (with "left" / "right")
    actions = machine.handle("incoming", party)     # from the call software: incoming (with a Party), answered, call_failed, remote_ended
    actions = machine.tick()                        # call often: the timed changes
    machine.mode, machine.party, machine.dial_tone, machine.ringing, machine.dialing_tones

Actions are tuples for the call software:  ("dial", party)  ("answer",)  ("hangup",)  ("reject",)

THE MODES (what the screen shows)
  IDLE         family photos (later also the info screen and the night clock)
  LIFTED       handset up: arrows down to the two buttons, dial tone (for LIFTED_SECONDS, then PLEASE_HANG_UP)
  DIALING      a button was pressed: its touch-tones play in the handset (screen: "Calling ...") -> CALLING when they are done.
               Only then is the number given to the phone software.  A button with no tones goes straight to CALLING.
  CALLING      "Calling Ann (daughter)..."          -> ONGOING when answered; NO_ANSWER after RING_OUT_SECONDS or if the call fails
  NO_ANSWER    "No answer."  for NO_ANSWER_SECONDS  -> LIFTED if the handset is still up, else IDLE
  INCOMING     the ringer and "Incoming call from ..." -> ONGOING when the handset is lifted; IDLE if the caller gives up
  ONGOING      "Speaking with ..."                  -> ENDED when either side hangs up
  ENDED        "Call just ended with ..." for CALL_ENDED_SECONDS -> IDLE, or PLEASE_HANG_UP if the handset is still up
  PLEASE_HANG_UP  yellow: "Please put the handset back on the phone."  (the buttons still work)

Incoming calls are only taken while the handset is down and no call is going on; otherwise they are rejected (busy).
Time comes from `clock` (time.monotonic), which tests replace with a fake.
"""
import enum
import time
from dataclasses import dataclass

from . import config
from .sound import dialable, dialing_seconds


class Mode(enum.Enum):
    IDLE = "idle"
    LIFTED = "lifted"
    DIALING = "dialing"
    CALLING = "calling"
    NO_ANSWER = "no answer"
    INCOMING = "incoming"
    ONGOING = "ongoing"
    ENDED = "ended"
    PLEASE_HANG_UP = "please hang up"


@dataclass(frozen=True)
class Party:
    """Someone on the other end.  name / relationship may be empty for an unknown caller (then the number is shown).
    tones: the touch-tone digits heard in the handset when calling them ("" = none)."""
    name: str = ""
    relationship: str = ""
    dial: str = ""
    tones: str = ""

    @property
    def label(self):
        """'Ann (daughter)', 'Ann', or the number."""
        if self.name and self.relationship:
            return "%s (%s)" % (self.name, self.relationship)
        return self.name or self.dial or "someone"


def buttons_from_config(buttons=None):
    """The two buttons' people.  Without "tones" the digits of "dial" are played (none if it has no digits)."""
    return {key: Party(b.get("name", ""), b.get("relationship", ""), b.get("dial", ""), dialable(b.get("tones", b.get("dial", ""))))
            for key, b in (config.BUTTONS if buttons is None else buttons).items()}


class Machine:
    def __init__(self, buttons=None, lifted_seconds=config.LIFTED_SECONDS, ring_out_seconds=config.RING_OUT_SECONDS,
                 no_answer_seconds=config.NO_ANSWER_SECONDS, call_ended_seconds=config.CALL_ENDED_SECONDS,
                 dialing_seconds=dialing_seconds, clock=time.monotonic, log=None):
        self.dialing_seconds = dialing_seconds          # tones -> how long dialing them takes
        self.buttons = buttons if buttons is not None else buttons_from_config()
        self.timeouts = {Mode.LIFTED: lifted_seconds, Mode.CALLING: ring_out_seconds,
                         Mode.NO_ANSWER: no_answer_seconds, Mode.ENDED: call_ended_seconds}
        self.clock, self.log = clock, log or (lambda msg: None)
        self.off_hook = False
        self.party = None
        self.mode = Mode.IDLE
        self.mode_since = clock()
        self.version = 0                               # goes up with every change of mode or party: time to redraw

    # ---- what the rest of the program asks ----
    @property
    def dial_tone(self):
        return self.mode == Mode.LIFTED

    @property
    def ringing(self):
        return self.mode == Mode.INCOMING

    @property
    def dialing_tones(self):
        """The touch-tones to play now ("" when not dialing)."""
        return self.party.tones if self.mode == Mode.DIALING else ""

    def seconds_in_mode(self):
        return self.clock() - self.mode_since

    # ---- events ----
    def handle(self, event, arg=None):
        """One event; returns the actions for the call software (a list, often empty)."""
        handler = getattr(self, "_on_" + event, None)
        if handler is None:
            raise ValueError("unknown event %r" % event)
        actions = handler(arg)
        return actions or []

    def tick(self):
        """The timed changes; returns actions like handle()."""
        if self.mode == Mode.DIALING:
            if self.seconds_in_mode() < self.dialing_seconds(self.party.tones):
                return []
            self._go(Mode.CALLING)
            return [("dial", self.party)]
        limit = self.timeouts.get(self.mode)
        if limit is None or self.seconds_in_mode() < limit:
            return []
        if self.mode == Mode.LIFTED:
            self._go(Mode.PLEASE_HANG_UP)
        elif self.mode == Mode.CALLING:
            self.log("      nobody picked up in %g s" % limit)
            self._go(Mode.NO_ANSWER)
            return [("hangup",)]
        elif self.mode == Mode.NO_ANSWER:
            self._go(Mode.LIFTED if self.off_hook else Mode.IDLE)
        elif self.mode == Mode.ENDED:
            self._go(Mode.PLEASE_HANG_UP if self.off_hook else Mode.IDLE)
        return []

    def _on_lifted(self, _):
        self.off_hook = True
        if self.mode == Mode.INCOMING:
            self._go(Mode.ONGOING)
            return [("answer",)]
        if self.mode in (Mode.IDLE, Mode.ENDED):
            self._go(Mode.LIFTED)
        # NO_ANSWER: its screen stays up and then turns into LIFTED by itself

    def _on_hung_up(self, _):
        self.off_hook = False
        if self.mode == Mode.DIALING:
            self._go(Mode.IDLE)                         # nothing was sent to the phone software yet: nothing to hang up
            return None
        if self.mode == Mode.CALLING:
            self._go(Mode.IDLE)
            return [("hangup",)]
        if self.mode == Mode.ONGOING:
            self._go(Mode.ENDED)
            return [("hangup",)]
        if self.mode in (Mode.LIFTED, Mode.PLEASE_HANG_UP):
            self._go(Mode.IDLE)
        # NO_ANSWER, ENDED: their screen stays up for its time, then IDLE

    def _on_button(self, key):
        party = self.buttons.get(key)
        if party is None:
            self.log("      (no one is set up for the %s button)" % key)
            return None
        if self.mode in (Mode.LIFTED, Mode.PLEASE_HANG_UP) and self.off_hook:
            self.party = party
            if self.dialing_seconds(party.tones) > 0:
                self._go(Mode.DIALING)                  # the dial action comes from tick() once the tones are done
                return None
            self._go(Mode.CALLING)
            return [("dial", party)]
        self.log("      (%s button ignored: %s)" % (key, self.mode.value))
        return None

    def _on_incoming(self, party):
        if self.off_hook or self.mode not in (Mode.IDLE, Mode.NO_ANSWER, Mode.ENDED):
            self.log("      incoming call from %s rejected: busy" % (party.label if party else "someone"))
            return [("reject",)]
        self.party = party or Party()
        self._go(Mode.INCOMING)

    def _on_answered(self, _):
        if self.mode == Mode.CALLING:
            self._go(Mode.ONGOING)
        else:
            self.log("      (answered ignored: %s)" % self.mode.value)

    def _on_call_failed(self, _):
        if self.mode == Mode.CALLING:
            self._go(Mode.NO_ANSWER)
        else:
            self.log("      (call_failed ignored: %s)" % self.mode.value)

    def _on_remote_ended(self, _):
        if self.mode == Mode.CALLING:
            self._go(Mode.NO_ANSWER)                   # they declined
        elif self.mode == Mode.ONGOING:
            self._go(Mode.ENDED)
        elif self.mode == Mode.INCOMING:
            self.log("      the caller gave up")
            self._go(Mode.IDLE)
        else:
            self.log("      (remote_ended ignored: %s)" % self.mode.value)

    def _go(self, mode):
        self.mode, self.mode_since = mode, self.clock()
        self.version += 1
        if mode in (Mode.IDLE, Mode.LIFTED, Mode.PLEASE_HANG_UP):
            self.party = None
        self.log("-> %s%s" % (mode.value.upper(), " - " + self.party.label if self.party else ""))


# ------------------------------------------------------------------ try it without a screen ---------------------------------
def main(argv=None):
    """Drive the machine from the real switches (or keys) and print what it does.  Simulated call software: keys y = they answer,
    f = call fails, e = they hang up, i = incoming call."""
    import argparse
    from .inputs import make_controls
    from .keys import TerminalKeys
    ap = argparse.ArgumentParser(prog="python3 -m judicom.machine", description=main.__doc__)
    ap.add_argument("--demo", action="store_true", help="no GPIO: l = lift / hang up, 1 / 2 = buttons")
    ap.add_argument("--speed", type=float, default=1.0, help="run the timers this many times faster")
    args = ap.parse_args(argv)
    start = time.monotonic()
    clock = lambda: start + (time.monotonic() - start) * args.speed                         # noqa: E731
    log = lambda msg: print("[%7.1f s] %s" % (time.monotonic() - start, msg), flush=True)   # noqa: E731
    controls, source = make_controls(args.demo, log)
    machine = Machine(clock=clock, log=log)
    sim = {"y": ("answered",), "f": ("call_failed",), "e": ("remote_ended",),
           "i": ("incoming", Party("Hannah", "granddaughter", "+15550102345"))}
    terminal = TerminalKeys() if TerminalKeys.available() else None
    log("Switches: %s.  Call software is simulated: y = answer, f = fail, e = they hang up, i = incoming.  q = quit." % source)
    tone = ring = False
    try:
        while True:
            keys = terminal.poll() if terminal else []
            if "quit" in keys:
                break
            events = controls.poll() + [e for k in keys for e in controls.key(k)] + [sim[k] for k in keys if k in sim]
            for event in events:
                log(" ".join(x.label if isinstance(x, Party) else str(x) for x in event))
                for action in machine.handle(*event):
                    log("      call software: %s" % " ".join(a.label if isinstance(a, Party) else a for a in action))
            for action in machine.tick():
                log("      call software: %s" % " ".join(action))
            if machine.dial_tone != tone or machine.ringing != ring:
                tone, ring = machine.dial_tone, machine.ringing
                log("      dial tone %s, ringer %s" % ("ON" if tone else "off", "ON" if ring else "off"))
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        if terminal:
            terminal.close()
        controls.close()


if __name__ == "__main__":
    main()
