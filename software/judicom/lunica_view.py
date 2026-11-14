"""Draws Lunica (judicom/lunica.py): bright pixel sprites on a star field, on a canvas half the screen each way (display.
present_small doubles it exactly).  The game's world (580 x 800) is drawn at half size below the score line.  Enemies in
flight turn to the way they go (their pictures turned in steps of 15 degrees, made once and kept).  All the pictures were
drawn for the Judicom."""
import math
import random

import pygame

from . import game_art as art
from . import lunica as lu
from .config import SCREEN_H, SCREEN_W

CANVAS_W, CANVAS_H = SCREEN_W // 2, SCREEN_H // 2
K = 0.5                                              # world to canvas
TOP = 48                                             # the world's top on the canvas (the score line above it)

PALETTE = {"w": (235, 235, 245), "c": (90, 210, 255), "b": (60, 110, 255), "r": (255, 80, 80), "y": (255, 200, 60),
           "g": (90, 230, 110), "k": (30, 120, 60), "x": (255, 60, 60), "m": (240, 90, 220), "o": (255, 150, 50),
           "d": (140, 40, 140), "e": (255, 255, 255), "t": (60, 200, 220), "u": (30, 90, 200)}
HURT = dict(PALETTE, t=(200, 120, 255), u=(120, 60, 180))                  # a commander hit once
CAUGHT = dict(PALETTE, w=(255, 130, 130), b=(170, 40, 40), c=(255, 200, 200))   # a captured fighter

FIGHTER = (("........w........",
            "........w........",
            ".......www.......",
            ".......wcw.......",
            "......wwcww......",
            "..r...wwwww...r..",
            "..w..wwwwwww..w..",
            ".www.wwbbbww.www.",
            "wwwwwwwbbbwwwwwww",
            "wwbwwwwbbbwwwwbww",
            "ww.bb.wwwww.bb.ww",
            "w...b.ww.ww.b...w",
            "......y...y......",
            "......y...y......",
            "................."),)
FIGHTER = (FIGHTER[0], FIGHTER[0][:13] + (".................", "................."))
SCOUT = (("......g......", ".....ggg.....", "....gyyyg....", "g..ggyxygg..g", "gg.ggggggg.gg", ".ggggkgkgggg.",
          "..ggg.g.ggg..", "...g..g..g...", "..g...g...g..", "......g......", "............."),
         ("......g......", ".....ggg.....", "....gyyyg....", ".g.ggyxygg.g.", "g..ggggggg..g", ".ggggkgkgggg.",
          "..ggg.g.ggg..", "..g...g...g..", ".g....g....g.", "......g......", "............."))
INTERCEPTOR = ((".......m.......", "......mmm......", ".....mmemm.....", "o...mmmmmmm...o", "oo.mmmdmdmmm.oo",
                "ooommmmmmmmmooo", "o.oommmmmmmoo.o", "o..oo.mmm.oo..o", "......m.m......", ".....m...m.....",
                "..............."),
               (".......m.......", "......mmm......", ".....mmemm.....", "....mmmmmmm....", ".o.mmmdmdmmm.o.",
                "oo.mmmmmmmmm.oo", "o..ommmmmmmo..o", "o...o.mmm.o...o", "......m.m......", ".....m...m.....",
                "..............."))
COMMANDER = (("........tt........", ".......tttt.......", "......ttxxtt......", "......tttttt......", ".uu...tyyyyt...uu.",
              "uuuu.ttyyyytt.uuuu", "uuuuuttttttttuuuuu", ".uuuuuttttttuuuuu.", "..uuu.tttttt.uuu..", "...u..tt..tt..u...",
              "......t....t......", "......y....y......", ".................."),
             ("........tt........", ".......tttt.......", "......ttxxtt......", "......tttttt......", "uu....tyyyyt....uu",
              ".uuu.ttyyyytt.uuu.", "..uuuttttttttuuu..", "...uuuttttttuuu...", "....u.tttttt.u....", "......tt..tt......",
              "......t....t......", "......y....y......", ".................."))
SPRITES = {"scout": SCOUT, "interceptor": INTERCEPTOR, "commander": COMMANDER}
STAR_COLOURS = ((235, 235, 245), (235, 235, 245), (110, 240, 130), (255, 100, 100), (110, 150, 255))   # white, green, red, blue
STAR_SPEED = (25, 70)                                # canvas pixels a second (on the screen: twice that), each its own
BURST_COLOURS = ((255, 255, 200), (255, 200, 60), (255, 110, 40), (180, 50, 50))


def picture(rows, palette=PALETTE):
    s = pygame.Surface((len(rows[0]), len(rows)), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                s.set_at((x, y), palette[ch])
    return s


def cx(x):
    return round(x * K)


def cy(y):
    return TOP + round(y * K)


class LunicaView:
    def __init__(self):
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        rng = random.Random(5)
        self.stars = [(rng.uniform(0, CANVAS_W), rng.uniform(0, CANVAS_H), rng.uniform(0, 6.28), rng.choice(STAR_COLOURS),
                       rng.uniform(*STAR_SPEED)) for _ in range(80)]
        self.fighter = [picture(f) for f in FIGHTER]
        self.caught = picture(FIGHTER[0], CAUGHT)
        self.turned = {}
        self._letters = {}

    def enemy_picture(self, e, frame):
        """Its picture, turned to its heading (in 15-degree steps; kept once made)."""
        step = round((e.angle + 90) / 15) % 24              # pictures point up; 90 = heading down the screen
        hurt = e.kind == "commander" and e.hp < lu.KINDS["commander"][1]
        key = (e.kind, frame, hurt, step)
        if key not in self.turned:
            base = picture(SPRITES[e.kind][frame], HURT if hurt else PALETTE)
            self.turned[key] = pygame.transform.rotate(base, -step * 15)
        return self.turned[key]

    def blit_centre(self, pic, x, y):
        self.canvas.blit(pic, (cx(x) - pic.get_width() // 2, cy(y) - pic.get_height() // 2))

    def text(self, s, y, colour=(240, 240, 240), scale=2, x=None, right=False):
        s = s.upper()
        width = art.text_width(s, scale)
        if x is None:
            x = cx(lu.W / 2) - width // 2
        elif right:
            x -= width
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

    def draw(self, g):
        c = self.canvas
        c.fill((0, 0, 0))
        for x, y, ph, colour, speed in self.stars:          # a sparse field of coloured stars, falling past, twinkling
            k = 0.55 + 0.45 * math.sin(g.clock * 2.3 + ph)
            c.set_at((int(x), int((y + g.clock * speed) % CANVAS_H)), tuple(int(v * k) for v in colour))
        frame = int(g.clock * 5) % 2
        for e in g.enemies:
            if e.state in ("waiting", "gone"):
                continue
            if e.state == "beam":
                self._beam(g, e)
            self.blit_centre(self.enemy_picture(e, frame), e.x, e.y)
            if e.captive:
                self.blit_centre(self.caught, *g.captive_xy(e))
        for s in g.shots:
            c.fill((255, 255, 170), (cx(s.x) - 1, cy(s.y) - 3, 2, 7))
        for s in g.enemy_shots:
            c.fill((255, 90, 140), (cx(s.x) - 1, cy(s.y) - 3, 3, 6))
        if g.rise is not None:
            x, y, spin = g.rising_xy()
            pic = pygame.transform.rotate(self.caught, -spin)
            self.blit_centre(pic, x, y)
        if g.rescued is not None:
            self.blit_centre(self.fighter[0], *g.rescued)
        if g.ship == "ok" and g.state not in ("attract", "over") and not (g.shield > 0 and int(g.shield * 8) % 2):
            for x in g.ships():
                self.blit_centre(self.fighter[frame], x, lu.PLAYER_Y)
        for x, y, t, kind in g.bursts:
            size = {"enemy": 7, "boss": 10, "ship": 14}[kind]
            k = t / (0.7 if kind == "ship" else 0.3)
            colour = BURST_COLOURS[min(3, int(k * 4))]
            r = max(1, round(size * (0.3 + k)))
            for i in range(8):                                # a ring of sparks flying out
                a = i * math.pi / 4 + t * 3
                c.fill(colour, (cx(x) + round(math.cos(a) * r) - 1, cy(y) + round(math.sin(a) * r) - 1, 2, 2))
            if k < 0.5:
                c.fill((255, 255, 255), (cx(x) - 1, cy(y) - 1, 3, 3))
        self._panel(g)
        return c

    def _beam(self, g, e):
        """The capture beam: bands of light widening down from the commander to the fighters' row, rippling."""
        top, bottom = e.y + e.h / 2, lu.PLAYER_Y + lu.PLAYER_H / 2
        half = g.beam_half(e)
        y = top
        i = 0
        while y < bottom:
            k = (y - top) / (bottom - top)
            w = 6 + (half - 6) * k
            band = (int(g.clock * 12) + i) % 3
            colour = ((120, 90, 255), (90, 220, 255), (190, 120, 255))[band]
            self.canvas.fill(colour, (cx(e.x - w), cy(y), max(1, round(2 * w * K)), 1))
            y += 6
            i += 1

    def _panel(self, g):
        self.text("%d" % g.score, 22, x=4)
        self.text("HI %d" % g.best, 22, (170, 170, 170), x=286, right=True)
        if g.state not in ("attract",):
            self.text("STAGE %d" % g.stage, 36, (150, 150, 150), scale=1)
            for i in range(max(0, min(g.lives - (g.ship == "ok"), 8))):        # fighters to come
                self.canvas.blit(self.fighter[1], (4 + i * 20, CANVAS_H - 30))
        mid = cy(430)
        if g.state == "attract":
            self.text("LUNICA", cy(250), (120, 210, 255), scale=6)
            for i, line in enumerate(("LEFT: MOVE LEFT", "RIGHT: MOVE RIGHT", "BOTH: FIRE")):
                self.text(line, cy(420) + i * 16, (190, 190, 190))
            if int(g.timer * 2) % 2 == 0:
                self.text("BOTH TO START", cy(560), (255, 220, 120))
        elif g.state == "intro":
            self.text("BONUS STAGE" if g.bonus else "STAGE %d" % g.stage, mid, (255, 220, 120), scale=3)
        elif g.state == "clear":
            self.text("STAGE CLEAR", mid, (120, 255, 160), scale=3)
        elif g.state == "summary":
            hits, total, groups, perfect, score = g.tally
            self.text("PERFECT!" if perfect else "BONUS STAGE", mid - 40, (255, 220, 120), scale=3)
            self.text("HITS %d / %d" % (hits, total), mid - 6)
            self.text("GROUPS +%d" % groups, mid + 12)
            if perfect:
                self.text("PERFECT +%d" % perfect, mid + 30, (255, 220, 120))
            self.text("BONUS %d" % score, mid + 52, (120, 255, 160))
        elif g.state == "over":
            self.text("GAME OVER", mid - 20, scale=4)
            self.text("SCORE %d" % g.score, mid + 14)
            if g.score > g.best_at_start:
                self.text("A NEW HIGH SCORE!", mid + 32, (255, 220, 120))
            if g.timer >= lu.OVER_WAIT:
                self.text("BOTH: PLAY AGAIN", mid + 56, (170, 170, 170))
                self.text("LIFT THE HANDSET TO STOP", mid + 72, (170, 170, 170))
