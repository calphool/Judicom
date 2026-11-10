"""The hidden keypad: a touch-tone keypad on the screen, for calling any number (for the family or staff, not for Judi).

To open it, with the handset up (the "Who would you like to call?" screen, or the yellow "please hang up" one):
    tap the top left corner twice, then the top right corner twice, each tap within KEYPAD_KNOCK_SECONDS of the last:
    a bong for each tap, higher each time (the same bongs as the maintenance shell's knock).
A wrong tap or too long a wait starts the knock again, without a sound.  Hanging up closes the keypad.

On the keypad (machine.py, Mode.KEYPAD): the dial tone until the first digit, then each key's touch-tone in the handset; the call
goes out by itself as soon as the number is complete: 10 digits, or 11 starting with 1 (the phone line, Asterisk on the NAS,
calls nothing else).  "Delete" takes back the last digit.  911 is refused with "Emergency calls cannot be made from this phone"
(the line has no emergency service), and so is a number starting with 0.  During a call made from the keypad the keypad stays on
the screen, and its keys (with * and #) send touch-tones down the line, for menus ("press 1 for the pharmacy").

No pygame: keypad_view.py draws it.

    knock = Knock(); knock.update(ready, taps)  -> the bong to play now (1..4; 4 = open the keypad), or None
    pad = Keypad(); pad.press(x, y) -> "0".."9" / "*" / "#" / "back", or None;  pad.keys(in_call, typing) -> what to draw
"""
import time

from . import config
from .maintenance import corner

KNOCK = ((0, 0), (0, 0), (1, 0), (1, 0))             # top left, top left, top right, top right, as (right?, bottom?)
OPEN = len(KNOCK)                                    # the bong number of the last tap

ROWS = (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("*", "0", "#"))
LETTERS = {"2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL", "6": "MNO", "7": "PQRS", "8": "TUV", "9": "WXYZ"}
KEY_W, KEY_H, GAP_X, GAP_Y = 170, 140, 20, 16
GRID_X = (config.SCREEN_W - config.SHELL_RIGHT - (3 * KEY_W + 2 * GAP_X)) // 2 + config.SHELL_RIGHT // 2
GRID_Y = 280
BACK = (GRID_X, GRID_Y + 4 * KEY_H + 3 * GAP_Y + 24, 3 * KEY_W + 2 * GAP_X, 84)     # "Delete", the width of the grid
LIT_SECONDS = 0.15

EMERGENCY = "Emergency calls cannot be made from this phone."
NOT_A_NUMBER = "Start with the area code (or 1 and the area code)."


def check_number(digits):
    """What the keypad does with what has been typed so far:
    "incomplete" (wait for more), "complete" (call it now), or the words of a refusal (EMERGENCY / NOT_A_NUMBER)."""
    if digits in ("911", "1911") or digits.startswith("911"):
        return EMERGENCY
    if digits.startswith("0") or digits.startswith("10") or digits.startswith("11"):
        return NOT_A_NUMBER                          # no North American area code starts with 0 or 1
    need = 11 if digits.startswith("1") else 10
    return "complete" if len(digits) >= need else "incomplete"


def pretty_number(digits):
    """'312555' -> '312-555', '3125550123' -> '312-555-0123', '13125550123' -> '1 312-555-0123' (also while it is being typed)."""
    head, rest = ("1 ", digits[1:]) if digits.startswith("1") else ("", digits)
    parts = [rest[:3], rest[3:6], rest[6:]]
    return (head + "-".join(p for p in parts if p)).strip()


class Knock:
    """Follows the knock.  update() -> the number of the bong to play now (1 .. OPEN), or None."""

    def __init__(self, clock=time.monotonic, knock_seconds=config.KEYPAD_KNOCK_SECONDS):
        self.clock, self.knock_seconds = clock, knock_seconds
        self.done, self._deadline = 0, None

    def reset(self):
        self.done, self._deadline = 0, None

    def update(self, ready, taps):
        if not ready:
            self.reset()
            return None
        now = self.clock()
        if self._deadline is not None and now >= self._deadline:
            self.reset()
        bong = None
        for x, y in taps:
            if corner(x, y) != KNOCK[self.done]:
                self.reset()
                if corner(x, y) != KNOCK[0]:           # a wrong tap; but one in the top left can be the start of a new knock
                    bong = None
                    continue
            self.done += 1
            self._deadline = now + self.knock_seconds
            bong = self.done
            if self.done == OPEN:
                self.reset()
                return OPEN
        return bong


class Keypad:
    """Where the keys are, and which one a tap is on.  A pressed key lights up for LIT_SECONDS."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._lit, self._lit_at = None, 0.0
        self.dirty = True

    def rects(self):
        """{key: (x, y, w, h)}, the delete key included."""
        out = {}
        for r, row in enumerate(ROWS):
            for c, key in enumerate(row):
                out[key] = (GRID_X + c * (KEY_W + GAP_X), GRID_Y + r * (KEY_H + GAP_Y), KEY_W, KEY_H)
        out["back"] = BACK
        return out

    def press(self, px, py, in_call=False, typing=True):
        """The key at (px, py), or None.  "back" only while typing; * and # are there either way (before a call they do nothing)."""
        for key, (x, y, w, h) in self.rects().items():
            if x <= px < x + w and y <= py < y + h:
                if key == "back" and not (typing and not in_call):
                    return None
                self._lit, self._lit_at, self.dirty = key, self.clock(), True
                return key
        return None

    def tick(self):
        if self._lit is not None and self.clock() - self._lit_at >= LIT_SECONDS:
            self._lit, self.dirty = None, True

    def keys(self, in_call=False, typing=True):
        """[(key, x, y, w, h, lit, enabled), ...]: * and # are greyed until a call; "back" only while typing."""
        out = []
        for key, (x, y, w, h) in self.rects().items():
            if key == "back" and (in_call or not typing):
                continue
            enabled = in_call or key not in "*#"
            out.append((key, x, y, w, h, key == self._lit, enabled))
        return out
