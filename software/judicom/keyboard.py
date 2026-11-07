"""The touch keyboard of the maintenance shell: where the keys are, and what they type.  No pygame: shell_view.py draws it.

    keyboard = Keyboard()
    keyboard.press(x, y)        # the bytes that key types, b"" for none (Shift and the like only change the next key)
    keyboard.keys()             # [(label, x, y, w, h, lit), ...] to draw
    keyboard.tick()             # call often: a pressed key lights up for a moment
    keyboard.dirty              # it must be drawn again; the view clears it

Ten keys across, as on a phone.  Shift and Ctrl count for the next key.  Sym swaps three rows for punctuation until pressed again.
"""
import time

from . import config

UNIT, KEY_H = config.SCREEN_W // 10, 62
LIT_SECONDS = 0.12

SPECIAL = {"Esc": b"\x1b", "Tab": b"\t", "Enter": b"\r", "Bksp": b"\x7f", "Space": b" ",
           "←": b"\x1b[D", "↓": b"\x1b[B", "↑": b"\x1b[A", "→": b"\x1b[C",        # the arrows
           "PgUp": b"\x1b[5~", "PgDn": b"\x1b[6~", "Home": b"\x1b[1~", "End": b"\x1b[4~"}             # as TERM=linux has them

DIGITS = list("1234567890")
LETTERS = [list("qwertyuiop"), list("asdfghjkl") + ["Bksp"], ["Shift"] + list("zxcvbnm-/")]
SYMBOLS = [list("!@#$%^&*()"), list("`~_=+[]{}") + ["Bksp"], ["Shift"] + list(";:'\",<>?\\")]
BOTTOM = ["Esc", "Tab", "Ctrl", "Sym", ("Space", 3), ".", ("Enter", 2)]
ARROWS = ["←", "↓", "↑", "→", "PgUp", "PgDn", "Home", "End", "|", "~"]


class Keyboard:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.top = config.SCREEN_H - 6 * KEY_H
        self.shift = self.ctrl = self.symbols = False
        self.dirty = True
        self._lit = self._lit_until = None

    def _rows(self):
        return [DIGITS] + (SYMBOLS if self.symbols else LETTERS) + [BOTTOM, ARROWS]

    def _layout(self):
        """(name of the key, x, y, w, h) for every key."""
        for r, row in enumerate(self._rows()):
            x = 0
            for key in row:
                name, units = key if isinstance(key, tuple) else (key, 1)
                yield name, x, self.top + r * KEY_H, units * UNIT, KEY_H
                x += units * UNIT

    def label(self, name):
        return name.upper() if self.shift and len(name) == 1 and name.isalpha() else name

    def keys(self):
        on = {"Shift": self.shift, "Ctrl": self.ctrl, "Sym": self.symbols}
        return [(self.label(name), x, y, w, h, name == self._lit or on.get(name, False)) for name, x, y, w, h in self._layout()]

    def press(self, px, py):
        for name, x, y, w, h in self._layout():
            if x <= px < x + w and y <= py < y + h:
                self._lit, self._lit_until, self.dirty = name, self.clock() + LIT_SECONDS, True
                return self._type(name)
        return b""

    def _type(self, name):
        if name == "Shift":
            self.shift = not self.shift
            return b""
        if name == "Ctrl":
            self.ctrl = not self.ctrl
            return b""
        if name == "Sym":
            self.symbols = not self.symbols
            return b""
        data = SPECIAL.get(name) or self.label(name).encode()
        if self.ctrl and len(data) == 1 and 0x40 <= data.upper()[0] <= 0x5f:
            data = bytes([data.upper()[0] & 0x1f])                       # Ctrl-C is byte 3
        self.shift = self.ctrl = False
        return data

    def tick(self):
        if self._lit is not None and self.clock() >= self._lit_until:
            self._lit, self.dirty = None, True
