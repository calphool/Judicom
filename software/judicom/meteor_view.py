"""Draws Meteoroids (judicom/meteor.py) in lines, like an old vector-screen arcade machine: bright thin lines on black, each
with a faint glow, and a fainter afterglow where a moving thing just was.

It draws straight onto the screen (display.mapper() turns the upright picture's points into the screen's own), not onto a
picture that is then turned and scaled: lines are cheap even on the Pi 3 A+, and they stay sharp.  The game's world fills the
visible screen: it starts below the bezel at the top (TOP) and is W wide, short of the bezel on the right.
"""
import math

import pygame

from . import meteor as m

TOP = 36                                            # the world's top, on the upright screen (the bezel covers above)
CORE = (225, 255, 235)                              # the lines: white, a touch of green
GLOW = (34, 62, 46)
GHOST = (70, 96, 80)                                # the afterglow
DIM = (130, 160, 140)
AFTERGLOW = 0.05                                    # seconds: where a moving thing was this long ago, faintly
CORE_WIDTH, GLOW_WIDTH = 2, 5                       # a crisp core in a soft glow (anti-aliased lines looked much the same, and
                                                    # took seven times as long on the Pi 3 A+: too slow with the screen full)

SHIP = ((14, 0), (-14, -11), (-8, 0), (-14, 11))    # nose to the right; a notch at the back
FLAME = ((-9, -4), (-20, 0), (-9, 4))
BIG_CRAFT = (((-16, -8), (-10, -8), (-10, 8), (-16, 8)),            # two pods on a bar, with a cabin between: a twin-pod raider
             ((10, -8), (16, -8), (16, 8), (10, 8)),
             ((-10, -2), (-5, -2)), ((5, -2), (10, -2)), ((-10, 2), (-5, 2)), ((5, 2), (10, 2)),
             ((-5, -5), (5, -5), (7, 0), (5, 5), (-5, 5), (-7, 0)))
CRAFT_SCALE = 1.5                                   # the craft are drawn (and hit) half as big again as their outlines
SMALL_CRAFT = (((-9, 0), (0, -6), (9, 0), (0, 6)), ((-9, 0), (9, 0)), ((0, -6), (0, 6)))   # a diamond dart, crossed

# A stroke font on a 4 x 6 grid: each letter a few lines (lists of points).
FONT = {
    "A": [[(0, 6), (0, 2), (2, 0), (4, 2), (4, 6)], [(0, 4), (4, 4)]],
    "B": [[(0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)], [(3, 3), (4, 4), (4, 5), (3, 6), (0, 6)]],
    "C": [[(4, 0), (0, 0), (0, 6), (4, 6)]],
    "D": [[(0, 0), (0, 6), (2, 6), (4, 4), (4, 2), (2, 0), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(4, 0), (0, 0), (0, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 1), (4, 0), (0, 0), (0, 6), (4, 6), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(0, 0), (4, 0)], [(2, 0), (2, 6)], [(0, 6), (4, 6)]],
    "J": [[(4, 0), (4, 6), (1, 6), (0, 5), (0, 4)]],
    "K": [[(0, 0), (0, 6)], [(4, 0), (0, 3), (4, 6)]],
    "L": [[(0, 0), (0, 6), (4, 6)]],
    "M": [[(0, 6), (0, 0), (2, 3), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "O": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)]],
    "P": [[(0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]],
    "Q": [[(0, 0), (4, 0), (4, 4), (2, 6), (0, 6), (0, 0)], [(2, 4), (4, 6)]],
    "R": [[(0, 6), (0, 0), (4, 0), (4, 3), (0, 3)], [(1, 3), (4, 6)]],
    "S": [[(4, 0), (0, 0), (0, 3), (4, 3), (4, 6), (0, 6)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "U": [[(0, 0), (0, 6), (4, 6), (4, 0)]],
    "V": [[(0, 0), (2, 6), (4, 0)]],
    "W": [[(0, 0), (1, 6), (2, 4), (3, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "Y": [[(0, 0), (2, 3), (4, 0)], [(2, 3), (2, 6)]],
    "Z": [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    "0": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(4, 0), (0, 6)]],
    "1": [[(1, 1), (2, 0), (2, 6)], [(1, 6), (3, 6)]],
    "2": [[(0, 0), (4, 0), (4, 3), (0, 3), (0, 6), (4, 6)]],
    "3": [[(0, 0), (4, 0), (4, 6), (0, 6)], [(1, 3), (4, 3)]],
    "4": [[(0, 0), (0, 3), (4, 3)], [(4, 0), (4, 6)]],
    "5": [[(4, 0), (0, 0), (0, 3), (4, 3), (4, 6), (0, 6)]],
    "6": [[(4, 0), (0, 0), (0, 6), (4, 6), (4, 3), (0, 3)]],
    "7": [[(0, 0), (4, 0), (4, 6)]],
    "8": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(0, 3), (4, 3)]],
    "9": [[(4, 3), (0, 3), (0, 0), (4, 0), (4, 6), (0, 6)]],
    ":": [[(2, 1), (2, 2)], [(2, 4), (2, 5)]],
    "-": [[(1, 3), (3, 3)]],
    "/": [[(4, 0), (0, 6)]],
    "!": [[(2, 0), (2, 4)], [(2, 5.4), (2, 6)]],
    ".": [[(2, 5.4), (2, 6)]],
    "+": [[(2, 1), (2, 5)], [(0, 3), (4, 3)]],
}


def turned(points, angle, x, y, k=1.0):
    a = math.radians(angle)
    c, s = math.cos(a) * k, math.sin(a) * k
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in points]


def copies(x, y, r):
    """Where to draw a thing at x, y: itself, and again across any edge it overlaps (so it slides across, not jumps)."""
    xs = [x] + ([x + m.W] if x < r else [x - m.W] if x > m.W - r else [])
    ys = [y] + ([y + m.H] if y < r else [y - m.H] if y > m.H - r else [])
    return [(a, b) for a in xs for b in ys]


class MeteorView:
    def __init__(self):
        self.surface, self.map = None, None

    # ---- lines ----------------------------------------------------------------------------------------------------------

    def line(self, points, closed=False, colour=CORE, glow=True):
        """A line through world points: a soft glow under a sharp core."""
        if len(points) < 2:
            return
        pts = [self.map(px, py + TOP) for px, py in points]
        if glow:
            pygame.draw.lines(self.surface, GLOW, closed, pts, GLOW_WIDTH)
        pygame.draw.lines(self.surface, colour, closed, pts, CORE_WIDTH)

    def shape(self, outline, angle, x, y, r, vx=0.0, vy=0.0, closed=True, colour=CORE, k=1.0):
        """An outline (or several) round x, y, turned, on every side of the wrap it shows on; and its afterglow if it moves."""
        outlines = outline if isinstance(outline[0][0], tuple) else (outline,)
        moving = abs(vx) + abs(vy) > 30
        for cx, cy in copies(x, y, r + 2):
            for o in outlines:
                if moving:
                    self.line(turned(o, angle, cx - vx * AFTERGLOW, cy - vy * AFTERGLOW, k), closed and len(o) > 2, GHOST, glow=False)
                self.line(turned(o, angle, cx, cy, k), closed and len(o) > 2, colour)

    def text(self, s, x, y, size=3.0, colour=CORE, centre=False, right=False):
        """Stroke letters, size = world pixels per grid unit (a letter is 4 x 6 units, 6 apart)."""
        s = s.upper()
        width = (len(s) * 6 - 2) * size
        if centre:
            x = (m.W - width) / 2
        elif right:
            x -= width
        for i, ch in enumerate(s):
            for stroke in FONT.get(ch, []):
                self.line([(x + (i * 6 + px) * size, y + py * size) for px, py in stroke], colour=colour)

    # ---- a picture of the game -------------------------------------------------------------------------------------------

    def present(self, game, display):
        """Draw straight onto the screen and show it."""
        self.render(game, display.screen, display.mapper())
        display.show()

    def draw(self, game, size=(600, 1024)):
        """Onto a picture of the upright screen (for tests and snapshots)."""
        surface = pygame.Surface(size)
        self.render(game, surface, lambda x, y: (x, y))
        return surface

    def render(self, g, surface, mapper):
        self.surface, self.map = surface, mapper
        surface.fill((0, 0, 0))
        for r in g.rocks:
            self.shape(r.shape, r.angle, r.x, r.y, r.r, r.vx, r.vy)
        if g.craft is not None:
            c = g.craft
            self.shape(BIG_CRAFT if c.size == "big" else SMALL_CRAFT, 0, c.x, c.y, c.r, c.vx, c.vy, k=CRAFT_SCALE)
        for s in g.shots + g.craft_shots:
            self.line([(s.x - s.vx * 0.006, s.y - s.vy * 0.006), (s.x, s.y)], colour=CORE if s.kind == "shot" else (255, 200, 170))
        for b in g.bits:
            k = b.life / 0.45
            col = tuple(int(v * k) for v in CORE)
            self.line([(b.x, b.y), (b.x - b.vx * 0.03, b.y - b.vy * 0.03)], colour=col, glow=False)
        if g.state == "playing" or g.state == "attract":
            self._ship(g)
        elif g.state == "destroyed" and getattr(g, "wreck", None):
            self._wreck(g)
        self._panel(g)

    def _ship(self, g):
        s = g.ship
        if g.shield > 0 and int(g.shield * 8) % 2:           # blinking while it cannot be hurt
            return
        self.shape(SHIP, s.angle, s.x, s.y, 16, s.vx, s.vy)
        if g.thrusting and int(s.t * 30) % 2 == 0:            # the flame, flickering
            self.shape(FLAME, s.angle, s.x, s.y, 22, closed=False, colour=(255, 220, 160))

    def _wreck(self, g):
        """The ship's outline in pieces, drifting apart, turning, fading."""
        x, y, angle, vx, vy, spins = g.wreck
        t = m.DESTROYED - g.timer
        if t > 0.6 * 1.5:
            return
        fade = max(0.0, 1 - t / 0.9)
        col = tuple(int(v * fade) for v in CORE)
        pts = list(SHIP) + [SHIP[0]]
        for i in range(len(SHIP)):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            mx, my = (ax + bx) / 2, (ay + by) / 2
            d = math.hypot(mx, my) or 1.0
            ox, oy = x + vx * t + mx / d * 40 * t, y + vy * t + my / d * 40 * t
            spin = angle + 90 * t * spins[i]
            seg = [(ax - mx, ay - my), (bx - mx, by - my)]
            self.line(turned(seg, spin, ox + mx * 0.0, oy), colour=col, glow=False)

    def _panel(self, g):
        if g.state == "attract":
            self.text("METEOROIDS", 0, 180, size=6, centre=True)
            for i, line in enumerate(("LEFT: ROTATE LEFT", "RIGHT: ROTATE RIGHT", "BOTH TAP: FIRE", "BOTH HOLD: THRUST")):
                self.text(line, 0, 300 + i * 34, size=3.2, colour=DIM, centre=True)
            if int(g.timer * 2) % 2 == 0:
                self.text("BOTH TO START", 0, 480, size=4, centre=True)
            self.text("HI %d" % g.best, 0, 560, size=3, colour=DIM, centre=True)
            return
        self.text("%d" % g.score, 10, 8, size=4)
        self.text("HI %d" % g.best, 0, 8, size=3, colour=DIM, centre=True)
        for i in range(max(0, min(g.lives - (g.state == "playing"), 8))):      # ships to come
            self.line(turned(SHIP, -90, 18 + i * 22, 58, 0.6), closed=True, colour=DIM, glow=False)
        self.text("WAVE %d" % g.wave, m.W - 10, 8, size=2.5, colour=DIM, right=True)
        if g.state == "over":
            self.text("GAME OVER", 0, 400, size=6, centre=True)
            self.text("SCORE %d" % g.score, 0, 470, size=4, centre=True)
            if g.score > g.best_at_start:
                self.text("A NEW HIGH SCORE!", 0, 520, size=3, colour=(255, 230, 160), centre=True)
            if g.timer >= m.OVER_WAIT:
                self.text("BOTH: PLAY AGAIN", 0, 580, size=3, colour=DIM, centre=True)
                self.text("LIFT THE HANDSET TO STOP", 0, 616, size=3, colour=DIM, centre=True)
