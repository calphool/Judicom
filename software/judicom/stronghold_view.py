"""Draws Stellar Stronghold (judicom/stronghold.py) in lines, as Meteoroids is drawn (meteor_view: straight onto the screen,
a glow under each line, an afterglow behind moving things).  The rings are arcs made of short straight lines."""
import math

from . import meteor_view as mv
from . import stronghold as sh
from .meteor_view import CORE, DIM, SHIP, turned

RING_COLOURS = {"outer": (90, 150, 255), "middle": (255, 225, 80), "inner": (255, 85, 70)}
CORE_COLOUR = (190, 255, 205)
MINE_COLOUR = (90, 230, 255)
SHOT_COLOUR = (255, 140, 60)
HEXAGON = [(math.cos(math.radians(a)) * sh.CORE_R, math.sin(math.radians(a)) * sh.CORE_R) for a in range(0, 360, 60)]
STAR = [(math.cos(math.radians(a)) * (sh.MINE_R if i % 2 == 0 else sh.MINE_R * 0.45),
         math.sin(math.radians(a)) * (sh.MINE_R if i % 2 == 0 else sh.MINE_R * 0.45)) for i, a in enumerate(range(0, 360, 45))]
DIAMOND = [(sh.CANNON_SHOT_R, 0), (0, -sh.CANNON_SHOT_R), (-sh.CANNON_SHOT_R, 0), (0, sh.CANNON_SHOT_R)]


def dim(colour, k):
    return tuple(int(v * k) for v in colour)


class StrongholdView(mv.MeteorView):
    def arc(self, r, start, span, colour, cx=sh.CX, cy=sh.CY):
        n = 6                                           # an arc as six short straight lines
        pts = [(cx + math.cos(math.radians(start + span * i / n)) * r, cy + math.sin(math.radians(start + span * i / n)) * r)
               for i in range(n + 1)]
        self.line(pts, colour=colour)

    def render(self, g, surface, mapper):
        self.surface, self.map = surface, mapper
        surface.fill((0, 0, 0))
        if g.state == "boom":
            self._boom(g)
        else:
            self._stronghold(g)
        for mine in g.mines:
            grow = max(0.15, min(1.0, mine.t / sh.MINE_APPEAR))            # a new one grows in
            self.shape(STAR, g.clock * 120, mine.x, mine.y, sh.MINE_R, mine.vx, mine.vy, colour=MINE_COLOUR, k=grow)
            if int(g.clock * 6) % 2:
                self.line([(mine.x - 1, mine.y), (mine.x + 1, mine.y)], colour=(255, 255, 255), glow=False)
        for c in g.cannon_shots:
            pulse = 1.0 + 0.2 * math.sin(g.clock * 30)
            self.shape(DIAMOND, 45 * (g.clock * 4 % 2), c.x, c.y, sh.CANNON_SHOT_R + 2, colour=SHOT_COLOUR, k=pulse)
        for s in g.shots:
            self.line([(s.x - s.vx * 0.006, s.y - s.vy * 0.006), (s.x, s.y)])
        for b in g.bits:
            self.line([(b.x, b.y), (b.x - b.vx * 0.03, b.y - b.vy * 0.03)], colour=dim(CORE, max(0.0, min(1.0, b.life / 0.5))),
                      glow=False)
        if g.state in ("playing", "attract"):
            if g.state == "playing":
                self._ship(g)
        elif g.state == "destroyed" and getattr(g, "wreck", None):
            self._wreck(g)
        self._panel(g)

    def _stronghold(self, g):
        for ring in g.rings:
            colour = RING_COLOURS[ring.name]
            if ring.regrow > 0:                          # growing back: a faint dotted circle, filling in
                k = 1 - ring.regrow / sh.REGROW
                for i in range(sh.SEGMENTS):
                    self.arc(ring.r, ring.angle + i * 30 + 12, 3 + 12 * k, dim(colour, 0.5))
                continue
            for i, hp in enumerate(ring.hp):
                if hp <= 0:
                    continue
                c = (255, 255, 255) if ring.flash[i] > 0 else colour if hp == sh.SEG_HITS else dim(colour, 0.5)
                start = ring.angle + i * 360 / sh.SEGMENTS
                self.arc(ring.r, start, sh.SEG_SPAN, c)
                if hp < sh.SEG_HITS:                     # damaged: a notch in the middle
                    a = math.radians(start + sh.SEG_SPAN / 2)
                    self.line([(sh.CX + math.cos(a) * (ring.r - 4), sh.CY + math.sin(a) * (ring.r - 4)),
                               (sh.CX + math.cos(a) * (ring.r + 4), sh.CY + math.sin(a) * (ring.r + 4))], colour=c, glow=False)
        self.line(turned(HEXAGON, 0, sh.CX, sh.CY), closed=True, colour=CORE_COLOUR)
        a = math.radians(g.cannon_angle)
        self.line([(sh.CX + math.cos(a) * 6, sh.CY + math.sin(a) * 6),
                   (sh.CX + math.cos(a) * (sh.CORE_R + 6), sh.CY + math.sin(a) * (sh.CORE_R + 6))], colour=CORE_COLOUR)
        self.line(turned([(5, 0), (-3, -4), (-3, 4)], g.clock * 200, sh.CX, sh.CY), closed=True, colour=dim(CORE_COLOUR, 0.7),
                  glow=False)

    def _boom(self, g):
        """Rings of light spreading from the middle, lines flying outward, the last segments thrown clear, fading."""
        t = sh.BOOM - g.timer
        fade = max(0.0, 1 - t / sh.BOOM)
        for k in (1.0, 0.6, 0.3):
            r = 20 + 380 * t * k
            pts = [(sh.CX + math.cos(math.radians(a)) * r, sh.CY + math.sin(math.radians(a)) * r) for a in range(0, 361, 15)]
            self.line(pts, colour=dim(CORE_COLOUR, fade * k))
        for i in range(16):
            a = math.radians(i * 22.5 + 7)
            r0, r1 = 30 + 260 * t, 60 + 300 * t
            self.line([(sh.CX + math.cos(a) * r0, sh.CY + math.sin(a) * r0), (sh.CX + math.cos(a) * r1, sh.CY + math.sin(a) * r1)],
                      colour=dim(CORE, fade), glow=False)
        for r, start, name, spin in getattr(g, "flying", []):
            mid = math.radians(start + sh.SEG_SPAN / 2)
            cx, cy = math.cos(mid) * 220 * t, math.sin(mid) * 220 * t
            self.arc(r, start + spin * t, sh.SEG_SPAN * max(0.2, 1 - t / 2), dim(RING_COLOURS[name], fade), sh.CX + cx, sh.CY + cy)

    def _panel(self, g):
        if g.state == "attract":
            self.text("STELLAR", 0, 70, size=6, centre=True)
            self.text("STRONGHOLD", 0, 130, size=6, centre=True)
            for i, text in enumerate(("LEFT: ROTATE LEFT", "RIGHT: ROTATE RIGHT", "BOTH TAP: FIRE", "BOTH HOLD: THRUST")):
                self.text(text, 0, 720 + i * 34, size=3.2, colour=DIM, centre=True)
            if int(g.timer * 2) % 2 == 0:
                self.text("BOTH TO START", 0, 880, size=4, centre=True)
            self.text("HI %d" % g.best, 0, 940, size=3, colour=DIM, centre=True)
            return
        self.text("%d" % g.score, 10, 8, size=4)
        self.text("HI %d" % g.best, 0, 8, size=3, colour=DIM, centre=True)
        for i in range(max(0, min(g.lives - (g.state == "playing"), 8))):
            self.line(turned(SHIP, -90, 18 + i * 22, 58, 0.6), closed=True, colour=DIM, glow=False)
        self.text("ROUND %d" % g.round, sh.W - 10, 8, size=2.5, colour=DIM, right=True)
        if g.state == "over":
            self.text("GAME OVER", 0, 160, size=6, centre=True)
            self.text("SCORE %d" % g.score, 0, 720, size=4, centre=True)
            if g.score > g.best_at_start:
                self.text("A NEW HIGH SCORE!", 0, 770, size=3, colour=(255, 230, 160), centre=True)
            if g.timer >= sh.OVER_WAIT:
                self.text("BOTH: PLAY AGAIN", 0, 830, size=3, colour=DIM, centre=True)
                self.text("LIFT THE HANDSET TO STOP", 0, 866, size=3, colour=DIM, centre=True)

