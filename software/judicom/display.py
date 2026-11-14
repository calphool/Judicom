"""The screen: opens it, and puts the upright 600 x 1024 picture on the sideways-mounted panel."""
import os
import sys

import pygame

from .config import SCREEN_H as H
from .config import SCREEN_W as W


class Display:
    """`logical` is the upright 600 x 1024 surface every screen draws on.  present() turns it 90 degrees onto the panel.

    window=True  a small window for a PC (no turning).      headless=True  no screen at all (tests and snapshots).
    rotate=False for a normal portrait monitor.             flip=True       turn the other way (if the picture is upside-down).
    """

    def __init__(self, window=False, headless=False, rotate=True, flip=False):
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        elif "SDL_VIDEODRIVER" not in os.environ and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            os.environ["SDL_VIDEODRIVER"] = "kmsdrm"          # on the Judicom: straight to the screen, no desktop
        try:
            pygame.display.init()                             # video and fonts only: no audio device is opened
            pygame.font.init()
            if headless:
                self.screen = pygame.display.set_mode((W, H))
            elif window:
                self.screen = pygame.display.set_mode((450, 768))
            else:
                self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            if not headless:
                pygame.mouse.set_visible(False)
        except pygame.error as exc:
            sys.exit("Cannot open the display: %s\n(Over SSH on the Judicom the user needs to be in the 'video' and 'render' groups, "
                     "and python3-pygame must be the apt package, not the pip one.)" % exc)
        nw, nh = self.screen.get_size()
        self.size = (nw, nh)
        self.rotate = rotate and (nw > nh) and not window and not headless
        self.flip = flip
        self.logical = pygame.Surface((W, H))

    def present(self):
        out = self.logical
        if self.rotate:
            out = pygame.transform.rotate(out, -90 if self.flip else 90)       # pygame turns counter-clockwise for positive angles
        if out.get_size() != self.screen.get_size():
            out = pygame.transform.smoothscale(out, self.screen.get_size())
        self.screen.blit(out, (0, 0))
        pygame.display.flip()

    def present_small(self, small):
        """A small upright picture (the hidden game's canvas) straight onto the screen, scaled up with square pixels: turning and
        scaling the small picture is much quicker than the full-size one, which matters at 60 pictures a second."""
        out = small
        if self.rotate:
            out = pygame.transform.rotate(out, -90 if self.flip else 90)
        try:
            pygame.transform.scale(out, self.screen.get_size(), self.screen)     # straight into the screen: half the time
        except ValueError:                                                      # (only when the two pixel formats match)
            self.screen.blit(pygame.transform.scale(out, self.screen.get_size()), (0, 0))
        pygame.display.flip()

    def mapper(self):
        """A function from the upright picture's (x, y) to the screen's own, for drawing straight onto self.screen (a game drawn
        in lines needs no turning or scaling of a whole picture: much quicker, and the lines stay sharp).  The same turn as
        present(): pygame turns counter-clockwise for positive angles, so (x, y) goes to (y, W - 1 - x)."""
        sw, sh = self.screen.get_size()
        if self.rotate and not self.flip:
            kx, ky = sw / H, sh / W
            return lambda x, y: (y * kx, (W - 1 - x) * ky)
        if self.rotate:
            kx, ky = sw / H, sh / W
            return lambda x, y: ((H - 1 - y) * kx, x * ky)
        kx, ky = sw / W, sh / H
        return lambda x, y: (x * kx, y * ky)

    def show(self):
        """What has been drawn straight onto self.screen, on the screen."""
        pygame.display.flip()

    def close(self):
        from . import draw
        draw.reset()
        pygame.quit()
