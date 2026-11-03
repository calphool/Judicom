"""Key presses.  Needed for testing: over SSH (the terminal the program was started in), or a keyboard / the window on a PC.

Names returned: 'quit' (q or Esc), 'next' (space or right arrow), or the character itself (lower case) for any other key.
"""
import os
import select
import sys

try:
    import termios
    import tty
except ImportError:                                  # Windows: keys only through the window
    termios = tty = None


def parse_keys(data):
    """Raw bytes from a terminal -> key names."""
    keys, i = [], 0
    while i < len(data):
        rest = data[i:]
        if rest.startswith(b"\x1b[C") or rest.startswith(b"\x1bOC"):
            keys.append("next")
            i += 3
            continue
        if rest.startswith(b"\x1b[") or rest.startswith(b"\x1bO"):      # some other cursor / function key: ignore the whole sequence
            j = 2
            while j < len(rest) and not (0x40 <= rest[j] <= 0x7e):
                j += 1
            i += j + 1
            continue
        ch = chr(rest[0]).lower()
        if rest[0] == 0x1b and len(rest) == 1:
            keys.append("quit")
        elif ch == " ":
            keys.append("next")
        elif ch == "q":
            keys.append("quit")
        elif ch.isprintable():
            keys.append(ch)
        i += 1
    return keys


class TerminalKeys:
    """Single key presses from the terminal the program was started in (works over SSH).  Use only if stdin is a terminal."""

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        self.dead = False

    @staticmethod
    def available():
        return bool(termios and sys.stdin.isatty())

    def poll(self):
        keys = []
        while not self.dead and select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 64)
            if not data:
                self.dead = True
                break
            keys += parse_keys(data)
        return keys

    def close(self):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


def window_keys(events):
    """pygame events -> key names."""
    import pygame
    keys = []
    for ev in events:
        if ev.type == pygame.QUIT:
            keys.append("quit")
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                keys.append("quit")
            elif ev.key in (pygame.K_RIGHT, pygame.K_SPACE):
                keys.append("next")
            else:
                keys += parse_keys((ev.unicode or "").encode("ascii", "ignore"))
    return keys
