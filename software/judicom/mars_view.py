"""Draws Mars Patrol (judicom/mars.py).

The canvas is half the screen each way (display.present_small() doubles it exactly).  The screen stands upright and the game is
wide, so the game's 800 x 600 world is a band across it at SCALE (288 x 216 on the canvas, 576 x 432 on the screen), and the
sky goes on above it (the score and the course's progress are up there) and the ground below.  Everything was drawn for the
Judicom: the pictures are rows of characters, each a colour (see PALETTE).
"""
import math
import random

import pygame

from . import game_art as art
from . import mars as m
from .config import SCREEN_H, SCREEN_W, SHELL_RIGHT

CANVAS_W, CANVAS_H = SCREEN_W // 2, SCREEN_H // 2
SCALE = 288 / m.W                                    # 0.36
LEFT = (CANVAS_W - SHELL_RIGHT // 2 - 288) // 2      # clear of the bezel on the right
BAND_Y = 190                                         # the world's top on the canvas

PALETTE = {"#": (215, 215, 225), "d": (120, 120, 140), "c": (90, 205, 235), "g": (250, 220, 90), "a": (240, 80, 80),
           "r": (160, 110, 90), "R": (205, 150, 120), "m": (90, 90, 90), "x": (255, 70, 60), "e": (215, 75, 70),
           "E": (130, 40, 40), "s": (90, 220, 240), "p": (230, 90, 220), "P": (150, 50, 150), "b": (120, 200, 90), "B": (70, 130, 60),
           "w": (90, 90, 105), "W": (170, 170, 185)}
SKY_TOP, SKY_LOW = (12, 6, 26), (58, 22, 52)
GROUND, GROUND_DARK, GROUND_LINE, PIT = (192, 88, 44), (128, 52, 28), (255, 176, 96), (22, 8, 18)
STARS_SPEED = 0.04                                   # the stars drift by at this much of the ground's speed: the farthest of all
LAYERS = (                                           # far to near: how fast it moves, colour, its line's height and roughness
    (0.15, (62, 30, 72), 262, 18, 1),
    (0.35, (86, 36, 54), 340, 10, 2),
    (0.60, (112, 46, 42), 405, 6, 3),
)

ROVER = ("...a........g...........",
         "...d........g...........",
         "...d...ccccccc..........",
         "...d..cc.....cc.........",
         "..####################..",
         ".#####################gg",
         ".dddddddddddddddddddddd.")
WHEEL = ((".www.", "wWwWw", "wwWww", "wWwWw", ".www."),
         (".www.", "wwWww", "wWwWw", "wwWww", ".www."))
ROCKS = {"small": (".rrr...", "rRrrr..", "rrrrrr.", "rrrrrrr", ".rrrrr."),
         "medium": ("..rrrr...", ".rRrrrr..", "rRRrrrrr.", "rrrrrrrrr", "rrrrrrrrr", "rrrrrrrrr", ".rrrrrrr.", "..rrrrr.."),
         "large": ("....rrrr....", "..rRRrrrrr..", ".rRRrrrrrrr.", "rRRrrrrrrrrr", "rrrrrrrrrrrr", "rrrrrrrrrrrr",
                   "rrrrrrrrrrrr", "rrrrrrrrrrrr", ".rrrrrrrrrr.", "..rrrrrrrr..", "...rrrrrr...")}
MINE = (("..x.", ".mm.", "mmmm", "mmmm"), ("....", ".mm.", "mmmm", "mmmm"))
BURIED = ("..x.", "mmmm")
CRAWLER = ("....eeeee.....", "...eeeeeee....", "..ee.E.E.ee...", ".eeeeeeeeeeee.", "eeeeeeeeeeeeee", "e.EE.EE.EE.EE.",
           ".E..E..E..E...")
TURRET = ("gg.......", "eeeee....", "..eeeee..", ".eeeeeee.", "eeeeeeeee", "eeeeeeeee", "EE.EEE.EE")
SCOUT = ("....ssssss....",                        # a little winged drone
         "..ssssssssss..",
         ".sssxssssxsss.",
         "ssssssssssssss",
         "s.ssssssssss.s",
         "...ss....ss...",
         "..ss......ss..",
         ".s..........s.")
ATTACK = (".....pppppp.....",                     # an attack drone, claws down
          "...pppppppppp...",
          "..pppxxppxxppp..",
          ".pppppppppppppp.",
          "pppppppppppppppp",
          "p.PPP.PPPP.PPP.p",
          "..PP..PPPP..PP..",
          ".PP....PP....PP.",
          "PP............PP",
          "P..............P")
BOMBER = ("........bbbbbbbbbb........",           # a bomber, lit windows, bomb bay underneath
          ".....bbbbbbbbbbbbbbbb.....",
          "...bbbbgbbbgbbbgbbbgbbb...",
          ".bbbbbbbbbbbbbbbbbbbbbbbb.",
          "bbbbbbbbbbbbbbbbbbbbbbbbbb",
          "bb.bb.bb.bb.bb.bb.bb.bb.bb",
          ".BBBBBBBBBBBBBBBBBBBBBBBB.",
          "....BB....BBBBBB....BB....",
          ".....B.....B..B.....B.....",
          "..........................")
FLYERS = {"scout": SCOUT, "attack": ATTACK, "bomber": BOMBER}


KEY = (255, 0, 255)                                  # the "see-through" colour of the background strips


def fast(surface, key=None):
    """The surface in the screen's own pixel format (much quicker to draw), with a see-through colour if key.  The Pi 3 A+
    needs this: blending a large picture pixel by pixel took over 30 ms; this way, a millisecond or two."""
    try:
        out = surface.convert() if surface.get_flags() & pygame.SRCALPHA == 0 else surface.convert_alpha()
    except pygame.error:                                 # no screen yet (some tests): as it is
        out = surface
    if key is not None:
        out.set_colorkey(key, pygame.RLEACCEL)
    return out


def picture(rows, palette=PALETTE):
    w, h = len(rows[0]), len(rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                s.set_at((x, y), palette[ch])
    return fast(s)


def sy(y):
    return BAND_Y + round(y * SCALE)


def sx(x):
    """A screen x of the game (0 .. 800) on the canvas."""
    return LEFT + round(x * SCALE)


class MarsView:
    def __init__(self):
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self.backdrop = self._backdrop()
        self.stars = self._stars()
        self.layers = [(f, self._layer(colour, top, rough, seed)) for f, colour, top, rough, seed in LAYERS]
        self.strata = self._strata()
        self.rover = picture(ROVER)
        self.wheels = [picture(w) for w in WHEEL]
        self.rocks = {k: picture(v) for k, v in ROCKS.items()}
        self.mines = [picture(f) for f in MINE]
        self.buried = picture(BURIED)
        self.crawler, self.turret = picture(CRAWLER), picture(TURRET)
        self.flyers = {k: picture(v) for k, v in FLYERS.items()}
        self.life = pygame.transform.scale(self.rover, (12, 4))
        self._letters = {}

    # ---- what does not move, or moves slowly ------------------------------------------------------------------------------

    def _backdrop(self):
        """The sky from top to bottom (the stars and the moons are drawn over it: _stars, _moons)."""
        s = pygame.Surface((CANVAS_W, CANVAS_H))
        for y in range(CANVAS_H):
            t = min(1.0, y / (BAND_Y + 130))
            s.fill(tuple(int(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_LOW)), (0, y, CANVAS_W, 1))
        return fast(s)

    def _moons(self):
        """Mars's two little moons, in front of the stars."""
        pygame.draw.circle(self.canvas, (205, 195, 180), (220, 112), 6)          # Phobos
        pygame.draw.circle(self.canvas, (150, 140, 128), (218, 110), 5)
        pygame.draw.circle(self.canvas, (200, 190, 175), (70, 150), 2)           # Deimos

    def _stars(self):
        """The stars, twice the band wide and joining end to end, so they can drift past as the rover goes."""
        width, height = 576, BAND_Y + 110
        s = pygame.Surface((width, height))
        s.fill(KEY)
        rng = random.Random(7)
        for _ in range(280):
            x, y = rng.randrange(width), rng.randrange(20, height)
            v = rng.randrange(110, 255)
            s.set_at((x, y), (v, v, min(255, v + 20)))
        return fast(s, KEY)

    def _layer(self, colour, top, rough, seed):
        """A strip of hills twice the band's width that joins up end to end (so it can scroll round).  Only as tall as it
        shows (from its highest peak down to below the lowest ground): (surface, its top on the canvas)."""
        width, bottom = 576, sy(m.GROUND_Y + 40)
        rng = random.Random(seed)
        waves = [(k, rng.uniform(0.5, 1.0) * rough * (6 - k) / 2, rng.uniform(0, 6.28)) for k in (1, 2, 3, 5)]
        ys = [BAND_Y + round((top + 2 * sum(a * math.sin(2 * math.pi * k * x / width + p) for k, a, p in waves)) * SCALE)
              for x in range(width)]
        y0 = min(ys)
        s = pygame.Surface((width, bottom - y0))
        s.fill(KEY)
        for x, y in enumerate(ys):
            s.fill(colour, (x, y - y0, 1, bottom - y))
        return fast(s, KEY), y0

    def _strata(self):
        """The ground's deep layers, with stones, scrolling with the ground (twice the band wide, joining end to end)."""
        width, top = 576, sy(m.GROUND_Y + 40)
        rng = random.Random(11)
        s = pygame.Surface((width, CANVAS_H - top))
        s.fill(GROUND)
        for i, y in enumerate(range(0, CANVAS_H - top, 9)):
            s.fill(GROUND_DARK if i % 2 else (150, 64, 32), (0, y, width, 4))
        for _ in range(160):
            x, y = rng.randrange(width), rng.randrange(CANVAS_H - top)
            s.fill((96, 40, 24), (x, y, rng.choice((1, 2)), 1))
        return fast(s), top

    # ---- text --------------------------------------------------------------------------------------------------------------

    def text(self, s, y, colour=(240, 240, 240), scale=1, x=None, right=False, backing=False):
        s = s.upper()
        width = art.text_width(s, scale)
        if x is None:
            x = LEFT + 144 - width // 2
        elif right:
            x -= width
        if backing:
            self.canvas.fill((0, 0, 0), (x - 3, y - 3, width + 6, art.FONT_H * scale + 6))
        for i, ch in enumerate(s):
            key = (ch, colour, scale)
            if key not in self._letters:
                pic = pygame.Surface((art.FONT_W * scale, art.FONT_H * scale), pygame.SRCALPHA)
                for gy, row in enumerate(art.FONT.get(ch, art.FONT[" "])):
                    for gx, c in enumerate(row):
                        if c == "#":
                            pic.fill(colour, (gx * scale, gy * scale, scale, scale))
                self._letters[key] = pic
            self.canvas.blit(self._letters[key], (x + i * (art.FONT_W + 1) * scale, y))

    # ---- a picture of the game ---------------------------------------------------------------------------------------------

    def draw(self, g):
        c = self.canvas
        c.blit(self.backdrop, (0, 0))
        travelled = g.x * SCALE
        off = -int(travelled * STARS_SPEED) % self.stars.get_width()        # the stars drift slowly by (the moons stay)
        c.blit(self.stars, (off - self.stars.get_width(), 0))
        c.blit(self.stars, (off, 0))
        self._moons()
        c.set_clip((LEFT, 0, 288, CANVAS_H))
        for factor, (strip, y0) in self.layers:
            off = -int(travelled * factor) % strip.get_width()
            c.blit(strip, (LEFT + off - strip.get_width(), y0))
            c.blit(strip, (LEFT + off, y0))
        self._ground(g)
        self._things(g)
        if g.state not in ("destroyed", "over"):
            self._rover(g)
        self._shots(g)
        self._bursts(g)
        c.set_clip(None)
        self._panel(g)
        return c

    def _ground(self, g):
        c = self.canvas
        strip, top = self.strata
        runs, start, last = [], 0, None
        for col in range(289):                            # one column of canvas pixels at a time, in runs of the same
            wx = g.world_x(col / SCALE)
            gap = g.gap_at(wx) is not None
            key = (sy(g.ground(wx)), gap)
            if key != last:
                if last is not None:
                    runs.append((start, col, last))
                start, last = col, key
        runs.append((start, 289, last))
        for a, b, (y, gap) in runs:
            if not gap:
                x, w = LEFT + a, b - a
                c.fill(GROUND, (x, y, w, top - y))
                c.fill(GROUND_LINE, (x, y, w, 1))
                c.fill(GROUND_DARK, (x, y + 3, w, 1))
        off = -int(g.x * SCALE) % strip.get_width()
        c.blit(strip, (LEFT + off - strip.get_width(), top))
        c.blit(strip, (LEFT + off, top))
        for a, b, (y, gap) in runs:                       # craters last: deep, dark holes through all of it
            if gap:
                c.fill(PIT, (LEFT + a, y - 1, b - a, 34))
                c.fill(GROUND_DARK, (LEFT + a, y + 33, b - a, 3))

    def _rover(self, g):
        c = self.canvas
        x, base = sx(m.PLAYER_X), sy(g.yb)
        c.blit(self.rover, (x, base - 12))
        frame = int(g.wheel) % 2
        for i, wx in enumerate(m.WHEELS):              # each wheel on the ground under it (a little give: suspension)
            dy = 0
            if g.grounded:
                dy = max(-1, min(1, sy(g.ground(g.x + wx) - m.CLEARANCE) - base))
            c.blit(self.wheels[frame], (x + round(wx * SCALE) - 2, base - 5 + dy))

    def _things(self, g):
        c = self.canvas
        blink = int(g.course_time * 4) % 2
        for t in g.things:
            if t.hp <= 0:
                continue
            rx, ry, rw, rh = g.thing_rect(t)
            if t.kind == "rock":
                pic = self.rocks[t.size]
            elif t.kind == "mine":
                pic = self.mines[blink]
            elif t.kind == "buried":
                pic = self.buried
            elif t.kind == "rover":
                pic = self.crawler
            else:
                pic = self.turret
            c.blit(pic, (sx(rx), sy(ry + rh) - pic.get_height()))
        for f in g.flyers:
            pic = self.flyers[f.kind]
            c.blit(pic, (sx(f.x) - pic.get_width() // 2, sy(f.y) - pic.get_height() // 2))

    def _shots(self, g):
        c = self.canvas
        for s in g.shots:
            c.fill((255, 240, 120), (sx(g.screen_x(s.x)), sy(s.y), 3, 1))
        for s in g.ups:
            c.fill((255, 255, 255), (sx(s.x), sy(s.y), 1, 3))
        for e in g.enemy_shots:
            x, y = sx(g.screen_x(e.x)), sy(e.y)
            if e.kind == "bomb":
                c.fill((200, 200, 210), (x, y - 2, 2, 3))
                c.fill((255, 80, 60), (x, y + 1, 2, 1))
            else:
                c.fill((255, 110, 60) if e.kind == "drop" else (255, 70, 70), (x, y, 2, 2))

    def _bursts(self, g):
        c = self.canvas
        for x, y, t, kind in g.bursts:
            size = {"small": 3, "rock": 6, "air": 6, "bomb": 5, "car": 12}[kind]
            r = max(1, round(size * min(1.0, t / 0.25 + 0.3)))
            colour = (255, 230, 120) if t < 0.15 else (255, 140, 60) if t < 0.3 else (160, 70, 50)
            pygame.draw.circle(c, colour, (sx(x), sy(y)), r, 1 if r > 3 else 0)
            if kind == "car":
                rng = random.Random(int(x))
                for _ in range(10):
                    a, d = rng.uniform(0, 6.28), rng.uniform(4, 22) * min(1.0, t / 0.6 + 0.2)
                    c.fill(PALETTE["#"] if rng.random() < 0.5 else PALETTE["d"],
                           (sx(x) + round(math.cos(a) * d), sy(y) - abs(round(math.sin(a) * d)), 2, 2))

    def _panel(self, g):
        """Above the band: the score, the course, how far along it, the rovers left; and the title or 'game over'."""
        if g.state == "attract":
            self.text("MARS PATROL", 34, (255, 150, 80), scale=4)
            self.text("LEFT: SLOW   RIGHT: FAST", 70)
            self.text("BOTH: JUMP / FIRE", 80)
            if int(g.timer * 2) % 2 == 0:
                self.text("PRESS BOTH BUTTONS TO START", 100, (255, 220, 120))
            self.text("HI %d" % g.best, 120, (170, 170, 170))
            return
        self.text("SCORE %d" % g.score, 24, scale=2, x=LEFT + 2)
        self.text("HI %d" % g.best, 24, (170, 170, 170), scale=2, x=LEFT + 286, right=True)
        name = "%d. %s" % (g.course + 1, m.COURSES[g.course]) + ("  (ROUND %d)" % (g.cycle + 1) if g.cycle else "")
        self.text(name, 44, (255, 170, 100))
        bar_y, c = 56, self.canvas
        c.fill((70, 50, 80), (LEFT + 2, bar_y, 284, 3))
        c.fill((255, 150, 80), (LEFT + 2, bar_y, round(284 * g.progress), 3))
        for k in range(1, m.CHECKPOINTS):
            c.fill((240, 240, 240), (LEFT + 2 + round(284 * k / m.CHECKPOINTS), bar_y - 2, 1, 7))
        for i in range(max(0, min(g.lives - 1, 8))):
            c.blit(self.life, (LEFT + 2 + i * 16, 66))
        if g.state == "over":
            mid = sy(150)
            self.text("GAME OVER", mid, scale=4, backing=True)
            self.text("SCORE %d" % g.score, mid + 28, scale=2, backing=True)
            if g.score > g.best_at_start:
                self.text("A NEW HIGH SCORE!", mid + 44, (255, 220, 120), backing=True)
            if g.timer >= m.OVER_WAIT:
                self.text("BOTH BUTTONS: PLAY AGAIN", mid + 56, (190, 190, 190), backing=True)
                self.text("LIFT THE HANDSET TO STOP", mid + 66, (190, 190, 190), backing=True)
        elif g.message_t > 0:
            self.text(g.message, sy(40), (255, 230, 140), backing=True)
