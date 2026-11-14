"""The hidden menu: what the maintenance knock opens (judicom/maintenance.py).  A big button for each thing behind it (the
shell, the games), and "Back to the photos".  Touch one to open it.  No pygame: menu_view.py draws it.

    menu = Menu(["Shell", "Invaders"], clock)
    menu.buttons()     [(label, x, y, w, h), ...]  in the upright 600 x 1024 picture; the last one is BACK
    menu.press(x, y)   the label touched, BACK, or None
    menu.idle          nothing touched for MENU_SECONDS: back to the photos
"""
import time

from . import config

BACK = "Back to the photos"
TOP = 190                        # the first button's top (the heading is above it)
BUTTON_H, GAP = 150, 36
RIGHT = config.SHELL_RIGHT       # the bezel covers the right edge
WIDE = 460
BACK_W, BACK_H = 380, 100
BACK_BOTTOM = 60                 # "Back to the photos" sits this far above the bottom


class Menu:
    def __init__(self, labels, clock=time.monotonic, seconds=None):
        self.labels, self.clock = list(labels), clock
        self.seconds = config.MENU_SECONDS if seconds is None else seconds
        self._touched = clock()

    def buttons(self):
        middle = (config.SCREEN_W - RIGHT) // 2
        back_y = config.SCREEN_H - BACK_BOTTOM - BACK_H
        n = max(1, len(self.labels))
        h = min(BUTTON_H, (back_y - GAP - TOP - (n - 1) * GAP) // n)          # more buttons: lower ones, all still above "Back"
        out = [(label, middle - WIDE // 2, TOP + i * (h + GAP), WIDE, h) for i, label in enumerate(self.labels)]
        out.append((BACK, middle - BACK_W // 2, back_y, BACK_W, BACK_H))
        return out

    def press(self, x, y):
        self._touched = self.clock()
        for label, bx, by, w, h in self.buttons():
            if bx <= x < bx + w and by <= y < by + h:
                return label
        return None

    @property
    def idle(self):
        return self.clock() - self._touched >= self.seconds
