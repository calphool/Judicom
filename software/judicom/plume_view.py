"""Draws Plume Knights (judicom/plume.py) on a canvas half the screen each way (display.present_small doubles it exactly).
The arena (580 x 880) is drawn at half size below the score line; the rocks, the hills and the sky are drawn once a wave
(the shore crumbles between waves) and kept.  Each rider is two pictures, its mount and its knight, so a mount can fly off
alone; all are drawn facing right and turned round when they face left.  All the pictures were drawn for the Judicom."""
import math
import random

import pygame

from . import game_art as art
from . import plume as pk
from .config import SCREEN_H, SCREEN_W

CANVAS_W, CANVAS_H = SCREEN_W // 2, SCREEN_H // 2
K = 0.5
TOP = 48
SPRITE_W, SPRITE_H, MIDDLE = 32, 28, 15     # the riders' pictures; MIDDLE: the column at the rider's x (facing right)

PALETTE = {"y": (255, 200, 60), "o": (205, 130, 30), "w": (225, 230, 240), "s": (140, 150, 170), "l": (205, 200, 185),
           "e": (255, 255, 255), "b": (60, 110, 255), "c": (90, 210, 255), "k": (20, 20, 30), "r": (240, 120, 40),
           "Y": (255, 240, 170)}
ARMOUR = {"knight": ((225, 230, 240), (140, 150, 170), (60, 110, 255)),          # (armour, its shadow, the plume)
          "novice": ((230, 60, 60), (140, 30, 30), (255, 200, 60)),
          "veteran": ((165, 170, 180), (95, 100, 110), (230, 60, 60)),
          "elite": ((175, 95, 235), (100, 50, 150), (255, 255, 255))}
DRAKE = {"novice": ((40, 120, 55), (100, 185, 95), (25, 70, 35)),                # (body, belly and horn, wings)
         "veteran": ((35, 140, 140), (110, 215, 200), (20, 85, 90)),
         "elite": ((85, 40, 120), (160, 95, 200), (50, 20, 75))}

KNIGHT = ("............bb..................",       # the knight, from the top of the picture; its lance at rows 3-4
          "...........bwws.................",
          "...........wkks.................",
          "...........swwslllllllllllllllle",
          "..........swwwwssssssssssssss...",
          "..........swwws.................",
          "..........swwws.................",
          "...........sws..................",
          "..........bbbb..................",
          "..........bbbb..................",
          "............s...................")

PLUME_BIRD = ("................................",   # the knight's bird (its tail a fan of plumes), without its wing
              "..c...c.........................",
              ".cbc.cbc........................",
              ".cbc.cbc.c......................",
              "..bb.bb.cbc.....................",
              "c..bbbb..bb...........bb........",
              "cbc.bbb.bb..........yyyb........",
              ".bbb.bbbb..........yyykyrrr.....",
              "...bbbbbb..........yyyyy........",
              "....bbbb...........yyy..........",
              ".....bbyyyyyyyyy...yyy..........",
              "......yyyyyyyyyyyyyyy...........",
              ".....yyyyyyyyyyyyyyyy...........",
              ".....yyyyyyyyyyyyyyy............",
              "......yyyyyyyyyyyyyy............",
              ".......oyyyyyyyyyyo.............",
              ".........oooooooooo.............",
              "................................")
DRAKE_BODY = ("................................",   # a drake (g body, G belly, spines and horns; k its eye), no wing
              "................................",
              "................................",
              "................................",
              "......................G.G.......",
              ".....................GgggG......",
              ".....................ggkggg.....",
              ".....................gggggggG...",
              "......................gg.GGG....",
              ".....................gg.........",
              "......G.G.G.G.......gg..........",
              ".....ggggggggggggggggg..........",
              "g...gggggggggggggggggg..........",
              "gg.ggggGGGGGGGGGgggggg..........",
              ".ggg..ggGGGGGGGggggg............",
              "..........ggggggggg.............",
              "................................",
              "................................")
WINGS = {   # the wing, over the bird: raised, level, lowered (o: the edge, y: the feathers; on a drake both its wing colour)
    "up": ((1, "......o........................."), (2, ".....oyo........................"),
           (3, "....oyyo........................"), (4, "....oyyyo......................."),
           (5, ".....oyyyo......................"), (6, "......oyyyo....................."),
           (7, ".......oyyyo...................."), (8, "........oyyyo..................."),
           (9, ".........oyyyo.................."), (10, "..........oyyo.................")),
    "mid": ((10, ".......ooooooooo................"), (11, ".....oyyyyyyyyyyo..............."),
            (12, "....oyyyyyyyyyyo................"), (13, "......ooooooooo.................")),
    "down": ((12, "..........oyyyo................."), (13, ".........oyyyo.................."),
             (14, "........oyyyo..................."), (15, ".......oyyyo...................."),
             (16, "......oyyyo....................."), (17, ".....oyyyo......................"),
             (18, ".....oyyo......................."), (19, "......oo........................")),
}
DRAKE_WINGS = {    # a drake's wing: leathery (m its ribs and edge, M the skin between)
    "up": ((2, ".....m.........................."), (3, "....mMm........................."),
           (4, "...mMMMm........................"), (5, "...mMMMMm......................."),
           (6, "....mMMMMm......................"), (7, ".....mMMMMm....................."),
           (8, "......mMMMMm...................."), (9, ".......mMMMMMm.................."),
           (10, "........mmmmmmm.................")),
    "mid": ((10, ".....mmmmmmmmm.................."), (11, "...mMMMMMMMMMm.................."),
            (12, "..m.m.m.mMMMm...................")),
    "down": ((12, "...........mMMm................."), (13, "..........mMMm.................."),
             (14, ".........mMMm..................."), (15, "........mMMm...................."),
             (16, ".......mMMm....................."), (17, "......mMm......................"),
             (18, "......m.m.......................")),
}
FLAP_FRAMES = ("up", "mid", "down", "mid")          # a wingbeat, FLAP_FRAME seconds each
FLAP_FRAME = 0.06
RUN_STEP = 7                                        # world pixels run for each picture of the legs

RAPTOR_BODY = (".........................................cc.....",   # the raptor: d body, c crest, r beak, k eye
               "........................................cddd.....",
               "....................................dddddddkd.....",
               "d...............................ddddddddddddrrrrrr",
               "dd.......ddddddddddddddddddddddddddddddddddrrrr...",
               ".dddddddddddddddddddddddddddddddddddddddd.........",
               "...ddddddddddddddddddddddddddcccdd................",
               ".......ddddddddddddddddddddd......................",
               "...............dd...dd............................",
               "...............d.....d............................")
RAPTOR_BODY_TOP = 8             # the body's first row in the picture (the wings above and below it)
RAPTOR_WINGS = (("..........w.......................................",          # raised
                 "..........ww......................................",
                 "...........www....................................",
                 "...........wwww...................................",
                 "............wwwww.................................",
                 "............wwwwww................................",
                 ".............wwwwwww..............................",
                 ".............wwwwwwww.............................",
                 "..............wwwwwwwww...........................",
                 "..............wwwwwwwwww..........................",
                 "...............wwwwwwwwwww........................",
                 "................wwwwwwwwwwww......................"),
                ("................wwwwwwwwwwww......................",          # lowered (from the body's 4th row)
                 "................wwwwwwwww.........................",
                 "...............wwwwwwww...........................",
                 "...............wwwwwww............................",
                 "..............wwwwww..............................",
                 "..............wwwww...............................",
                 ".............wwww.................................",
                 ".............www..................................",
                 "............ww....................................",
                 "............w....................................."))
RAPTOR_W, RAPTOR_H = 50, 26
RAPTOR_MIDDLE = 24
RAPTOR_COLOURS = {"d": (62, 40, 74), "w": (84, 56, 100), "c": (255, 90, 60), "r": (255, 200, 60),
                  "k": (255, 255, 120)}
RAPTOR_EDGE = (120, 220, 255)

BURST_COLOURS = ((255, 255, 210), (255, 210, 80), (255, 120, 40), (170, 50, 40))
EGG_COLOURS = ((150, 240, 220), (190, 240, 150), (255, 220, 120), (255, 140, 80))   # fresh, ..., nearly hatched
LAVA = ((255, 120, 20), (255, 70, 20), (210, 40, 20), (255, 190, 60))
ROCK, ROCK_TOP, ROCK_DARK = (110, 95, 90), (165, 150, 135), (60, 50, 50)
SKY_TOP, SKY_LOW = (6, 6, 26), (40, 16, 40)
HILLS = (32, 20, 46)


KEY = (255, 0, 255)                                 # the see-through colour of the quick pictures


def keyed(pic, like):
    """pic (drawn with see-through pixels) made quick to draw: in like's pixel format, with KEY see-through (run-length
    coded).  Blending pixel by pixel is what the Pi 3 A+ cannot afford at 60 pictures a second."""
    out = pygame.Surface(pic.get_size()).convert(like)
    out.fill(KEY)
    out.blit(pic, (0, 0))
    out.set_colorkey(KEY, pygame.RLEACCEL)
    return out


def cx(x):
    return round(x * K)


def cy(y):
    return TOP + round(y * K)


def picture(rows, palette, start=0, size=(SPRITE_W, SPRITE_H), into=None):
    s = into or pygame.Surface(size, pygame.SRCALPHA)
    for y, row in enumerate(rows, start):
        for x, ch in enumerate(row):
            if ch in palette:
                s.set_at((x, y), palette[ch])
    return s


def legs(s, colour, kind, frame):
    """The legs, drawn in lines from the hips to the feet (the feet at the bottom row)."""
    hips = ((12, 17), (16, 17)) if kind == "bird" else ((11, 16), (16, 16))
    width = 1 if kind == "bird" else 2                 # (a drake's legs are sturdier)
    bottom = SPRITE_H - 1
    if frame == "tuck":                             # flying: tucked back under the body
        feet = ((8, 21), (12, 21)) if kind == "bird" else ((7, 19), (12, 19))
        for (hx, hy), (fx, fy) in zip(hips, feet):
            pygame.draw.line(s, colour, (hx, hy), (fx, fy), width)
        return
    swing = {"stand": (0, 0), "run0": (-4, 4), "run1": (-1, 1), "run2": (4, -4), "run3": (1, -1)}[frame]
    for (hx, hy), d in zip(hips, swing):
        knee = (hx + 2 + d // 2, (hy + bottom) // 2 - (2 if d > 0 else 0))
        foot = (hx + d, bottom)
        pygame.draw.line(s, colour, (hx, hy), knee, width)
        pygame.draw.line(s, colour, knee, foot, width)
        pygame.draw.line(s, colour, foot, (foot[0] + 2, bottom))          # toes, forward


def mount_picture(kind, wing, leg):
    """A mount (kind "knight": the plume-bird; or a rider class: its drake), facing right."""
    if kind == "knight":
        s = picture(PLUME_BIRD, PALETTE)
        legs(s, PALETTE["r"], "bird", leg)
        return picture([r for _, r in WINGS[wing]], PALETTE, WINGS[wing][0][0], into=s)
    body, belly, wings = DRAKE[kind]
    s = picture(DRAKE_BODY, {"g": body, "G": belly, "k": (255, 230, 60)})
    legs(s, body, "drake", leg)
    rows = DRAKE_WINGS[wing]
    return picture([r for _, r in rows], {"m": wings, "M": tuple(min(255, c + 45) for c in wings)}, rows[0][0], into=s)


def knight_picture(kind):
    armour, shadow, plume = ARMOUR[kind]
    return picture(KNIGHT, {"w": armour, "s": shadow, "b": plume, "k": (20, 20, 30), "l": PALETTE["l"], "e": PALETTE["e"]})


def pose(r):
    """(wing, legs) for a rider now."""
    if r.grounded:
        if abs(r.vx) > 15:
            return "mid", "run%d" % (int(r.run / RUN_STEP) % 4)
        return "mid", "stand"
    if r.flap_age < FLAP_FRAME * len(FLAP_FRAMES):
        return FLAP_FRAMES[int(r.flap_age / FLAP_FRAME)], "tuck"
    return ("up" if r.vy > 120 else "mid"), "tuck"


class PlumeView:
    def __init__(self):
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self._pics = {}
        self._letters = {}
        self._back, self._back_key = None, None
        rng = random.Random(9)
        self.stars = [(rng.uniform(0, CANVAS_W), rng.uniform(TOP, TOP + 250), rng.uniform(0, 6.28)) for _ in range(40)]
        self.bubbles = [(rng.uniform(0, 290), rng.uniform(0, 3), rng.uniform(0.8, 2.0)) for _ in range(10)]

    def pic(self, key, make, face=1):
        k = (key, face)
        if k not in self._pics:
            p = make()
            self._pics[k] = keyed(p if face > 0 else pygame.transform.flip(p, True, False), self.canvas)
        return self._pics[k]

    def put(self, pic, x, y, face=1, middle=MIDDLE):
        """A picture with its middle column at world x and its bottom at world y; again across the side if it is near it."""
        width = pic.get_width()
        left = cx(x) - (middle if face > 0 else width - middle)
        top = cy(y) - pic.get_height()
        self.canvas.blit(pic, (left, top))
        if left < 0:
            self.canvas.blit(pic, (left + cx(pk.W), top))
        elif left + width > cx(pk.W):
            self.canvas.blit(pic, (left - cx(pk.W), top))

    def rider(self, r, kind, blink=False):
        if blink:
            return
        wing, leg = pose(r)
        self.put(self.pic(("mount", kind, wing, leg), lambda: mount_picture(kind, wing, leg), r.face), r.x, r.y, r.face)
        self.put(self.pic(("knight", kind), lambda: knight_picture(kind), r.face), r.x, r.y, r.face)

    # ---- the arena ---------------------------------------------------------------------------------------------------

    def background(self, g):
        key = tuple(g.plats)
        if key == self._back_key:
            return self._back
        s = pygame.Surface((CANVAS_W, CANVAS_H))
        for y in range(CANVAS_H):                            # the sky, darkest at the top
            k = min(1.0, max(0.0, (y - TOP) / (cy(pk.LAVA_Y) - TOP)))
            s.fill(tuple(int(a + (b - a) * k) for a, b in zip(SKY_TOP, SKY_LOW)), (0, y, CANVAS_W, 1))
        rng = random.Random(4)
        for x, y, _ in self.stars:
            s.set_at((int(x), int(y)), (90, 90, 120))
        base = cy(pk.LAVA_Y)                                 # far hills and a broken tower, dark against the sky
        heights = [0.0] * CANVAS_W
        for i in range(3):
            phase, period, amp = rng.uniform(0, 6.3), rng.uniform(40, 110), rng.uniform(12, 30)
            for x in range(CANVAS_W):
                heights[x] += amp * (0.5 + 0.5 * math.sin(x / period * 6.28 + phase))
        for x in range(CANVAS_W):
            s.fill(HILLS, (x, int(base - 40 - heights[x]), 1, int(40 + heights[x])))
        s.fill(HILLS, (215, base - 150, 22, 150))
        for i in range(4):
            s.fill(HILLS, (213 + i * 7, base - 156, 4, 6))
        s.fill(SKY_LOW, (223, base - 128, 3, 6))
        for x0, x1, top, bot in g.plats:
            ground = top == pk.GROUND_Y
            self._rock(s, x0, x1, top, (pk.LAVA_Y + 30) if ground else bot, rng, ground)
        self._back, self._back_key = s.convert(self.canvas), key
        return self._back

    def _rock(self, s, x0, x1, top, bot, rng, ground):
        """A floating rock: a light top edge, rough sides, and a ragged underside hanging down."""
        left, right, t, b = cx(x0), cx(x1), cy(top), cy(bot)
        for x in range(left, right):
            edge = min(x - left, right - 1 - x)
            hang = b - t if ground else (b - t) + (rng.randint(0, 4) if edge > 2 else 0) - (2 if edge < 2 else 0)
            s.fill(ROCK, (x, t, 1, max(2, hang)))
            if not ground and rng.random() < 0.25:
                s.fill(ROCK_DARK, (x, t + rng.randint(3, max(3, hang - 1)), 1, 1))
            s.fill(ROCK_TOP, (x, t, 1, 2))
        if ground:
            for i in range(0, right - left, 5):
                s.fill(ROCK_DARK, (left + i + rng.randint(0, 3), t + rng.randint(4, b - t - 2), 2, 1))

    LAVA_FRAMES = 24                                    # the lake's waves, drawn once and played round and round

    def lava(self, g):
        if not hasattr(self, "_lava"):
            self._lava = [keyed(self._lava_frame(i / self.LAVA_FRAMES * 2 * math.pi), self.canvas)
                          for i in range(self.LAVA_FRAMES)]
        top = cy(pk.LAVA_Y)
        self.canvas.blit(self._lava[int(g.clock * 4) % self.LAVA_FRAMES], (0, top - 3))
        for bx, ph, speed in self.bubbles:               # bubbles rising and bursting
            k = (g.clock * speed / 3 + ph) % 1.0
            if k < 0.6:
                r = 1 + int(k * 3)
                pygame.draw.circle(self.canvas, LAVA[3], (int(bx), top + 10 - int(k * 12)), r, 1)

    @staticmethod
    def _lava_frame(t):
        """The lake from 3 pixels above its surface down: one moment of its rolling waves (t: 0 to 2 pi, round)."""
        s = pygame.Surface((CANVAS_W, CANVAS_H - cy(pk.LAVA_Y) + 3), pygame.SRCALPHA)
        for x in range(CANVAS_W):
            wave = 1.2 * math.sin(x * 0.18 + t * 2) + 0.8 * math.sin(x * 0.07 - t)
            y = 3 + round(wave)
            s.fill(LAVA[3], (x, y, 1, 1))
            s.fill(LAVA[0], (x, y + 1, 1, 3))
            s.fill(LAVA[1], (x, y + 4, 1, 5))
            s.fill(LAVA[2], (x, y + 9, 1, s.get_height()))
        return s

    # ---- the picture -------------------------------------------------------------------------------------------------

    def draw(self, g):
        c = self.canvas
        c.blit(self.background(g), (0, 0))
        for x, y, ph in self.stars:
            if math.sin(g.clock * 1.7 + ph) > 0.6:
                c.set_at((int(x), int(y)), (200, 200, 240))
        if g.state == "attract":
            self.lava(g)
            self._panel(g)
            return c
        for e in g.enemies:
            if e.state == "spawning":
                self._spawning(e)
            else:
                self.rider(e, e.cls)
        for egg in g.eggs:
            self._egg(g, egg)
        for h in g.hatchlings:
            self._hatchling(g, h)
        for x, y, face, t, kind in g.runaways:
            mount = "knight" if kind == "knight" else "novice"
            wing = FLAP_FRAMES[int(t / FLAP_FRAME) % 4]
            self.put(self.pic(("mount", mount, wing, "tuck"), lambda: mount_picture(mount, wing, "tuck"), face), x, y, face)
        me = g.me
        if g.knight in ("ok", "grabbed"):
            self.rider(me, "knight", blink=g.shield > 0 and int(g.shield * 8) % 2 == 1)
        if g.faller:
            x, y, _ = g.faller
            pic = self.pic(("knight", "knight"), lambda: knight_picture("knight"))
            turned = pygame.transform.rotate(pic, int(g.knight_timer * 400) % 360 // 45 * 45)
            c.blit(turned, (cx(x) - turned.get_width() // 2, cy(y) - turned.get_height() // 2))
        if g.raptor:
            self._raptor(g)
        self._serpent(g)
        self.lava(g)
        self._bursts(g)
        for x, y, t, points in g.popups:
            self.text("%d" % points, cy(y), (255, 240, 170), scale=1, x=cx(x) - art.text_width("%d" % points, 1) // 2)
        self._panel(g)
        return c

    def _spawning(self, e):
        """A rider rising out of a ring of light where it appears."""
        k = 1 - e.spawn_t / pk.SPAWN_TIME
        x, y = cx(e.x), cy(e.y)
        r = 3 + int(10 * min(1, k * 2))
        colour = (180, 140, 255) if int(k * 12) % 2 else (120, 220, 255)
        pygame.draw.ellipse(self.canvas, colour, (x - r, y - 3, r * 2, 5), 1)
        if k > 0.35:                                    # the rider coming up out of it, in three steps
            show = min(3, 1 + int((k - 0.35) / 0.22))
            mount = self.pic(("mount", e.cls, "mid", "stand"), lambda: mount_picture(e.cls, "mid", "stand"), e.face)
            knight = self.pic(("knight", e.cls), lambda: knight_picture(e.cls), e.face)
            h = SPRITE_H * show // 3
            left = x - (MIDDLE if e.face > 0 else SPRITE_W - MIDDLE)
            for p in (mount, knight):
                self.canvas.blit(p, (left, y - h), (0, 0, SPRITE_W, h))

    def _egg(self, g, egg):
        x, y = cx(egg.x), cy(egg.y)
        if egg.timer is None:
            colour = EGG_COLOURS[0]
        else:
            k = 1 - egg.timer / egg.incubate
            colour = EGG_COLOURS[min(3, int(k * 4))]
            if egg.timer < 2.0 and int(egg.timer * 8) % 2:                  # about to hatch: pulsing
                colour = (255, 255, 255)
        pygame.draw.ellipse(self.canvas, colour, (x - 4, y - 11, 9, 11))
        pygame.draw.ellipse(self.canvas, tuple(c // 2 for c in colour), (x - 4, y - 11, 9, 11), 1)
        if int(g.clock * 3 + egg.x) % 3 == 0:
            self.canvas.set_at((x - 1, y - 8), (255, 255, 255))
        else:
            self.canvas.fill((255, 255, 255), (x - 2, y - 9, 1, 2))

    def _hatchling(self, g, h):
        """A knight on foot, waving, while its drake comes down for it."""
        armour, shadow, plume = ARMOUR[h.cls]
        x, y = cx(h.x), cy(h.y)
        c = self.canvas
        c.fill(plume, (x, y - 13, 2, 1))
        c.fill(armour, (x - 1, y - 12, 3, 3))
        c.fill(shadow, (x - 2, y - 9, 5, 5))
        c.fill(armour, (x - 1, y - 4, 1, 4))
        c.fill(armour, (x + 1, y - 4, 1, 4))
        arm = -3 if int(h.t * 4) % 2 else -1
        c.fill(armour, (x + 3, y - 9 + arm, 1, 3))
        if h.mount:
            mx, my, side = h.mount
            wing = FLAP_FRAMES[int(g.clock / FLAP_FRAME) % 4]
            self.put(self.pic(("mount", h.cls, wing, "tuck"), lambda: mount_picture(h.cls, wing, "tuck"), side), mx, my, side)

    def _raptor(self, g):
        r = g.raptor
        frame = int(r.age * 6) % 2
        pic = self.pic(("raptor", frame), lambda: self._raptor_picture(frame), r.face)
        w = pic.get_width()
        left = cx(r.x) - (RAPTOR_MIDDLE if r.face > 0 else w - RAPTOR_MIDDLE)
        self.canvas.blit(pic, (left, cy(r.y) - (RAPTOR_BODY_TOP + 3)))           # its head level with its y

    @staticmethod
    def _raptor_picture(frame):
        """Raised or lowered wings (w) behind the body, a bright edge along each wing's front."""
        s = pygame.Surface((RAPTOR_W, RAPTOR_H), pygame.SRCALPHA)
        wing = RAPTOR_WINGS[frame]
        start = RAPTOR_BODY_TOP - len(wing) + 1 if frame == 0 else RAPTOR_BODY_TOP + 3
        picture(wing, RAPTOR_COLOURS, start, into=s)
        for y, row in enumerate(wing, start):
            ends = [x for x, ch in enumerate(row) if ch == "w"]
            if ends:
                s.set_at((ends[-1], y), RAPTOR_EDGE)
        picture(RAPTOR_BODY, RAPTOR_COLOURS, RAPTOR_BODY_TOP, into=s)
        return s

    def _serpent(self, g):
        top = g.serpent_top()
        if top is None:
            return
        x0, base, head = cx(g.serpent["x"]), cy(pk.LAVA_Y) + 6, cy(top)
        c = self.canvas
        y = base
        while y > head:                                  # its body: scales swaying as it rises
            sway = round(2.5 * math.sin(y * 0.4 + g.clock * 9))
            c.fill((200, 50, 30), (x0 - 3 + sway, y - 2, 7, 3))
            c.fill((255, 200, 60), (x0 - 1 + sway, y - 2, 3, 1))
            y -= 3
        jaw = 2 if g.serpent["state"] == "hold" else 1 + int(g.clock * 10) % 3
        c.fill((220, 60, 30), (x0 - 5, head - 3, 11, 6))
        c.fill((255, 240, 120), (x0 - 4, head - 2, 2, 2))
        c.fill((255, 240, 120), (x0 + 3, head - 2, 2, 2))
        c.fill((120, 20, 10), (x0 - 4, head + 3, 9, jaw))
        if g.knight == "grabbed" and int(g.clock * 6) % 2 == 0:
            self.text("FLAP TO ESCAPE!", cy(g.me.y) - 46, (255, 230, 120), scale=1)

    def _bursts(self, g):
        c = self.canvas
        for x, y, t, kind in g.bursts:
            size = {"joust": 8, "knight": 12, "egg": 5, "lava": 6, "raptor": 16}[kind]
            k = t / 0.8
            if kind == "egg":
                colour = (255, 255, 160) if int(t * 20) % 2 else (150, 240, 220)
            elif kind == "lava":
                colour = LAVA[min(3, int(k * 4))]
            else:
                colour = BURST_COLOURS[min(3, int(k * 4))]
            r = max(1, round(size * (0.3 + k)))
            for i in range(8):
                a = i * math.pi / 4 + t * 3
                c.fill(colour, (cx(x) + round(math.cos(a) * r) - 1, cy(y) + round(math.sin(a) * r) - 1, 2, 2))
            if k < 0.4:
                c.fill((255, 255, 255), (cx(x) - 1, cy(y) - 1, 3, 3))

    # ---- words -------------------------------------------------------------------------------------------------------

    def text(self, s, y, colour=(240, 240, 240), scale=2, x=None, right=False):
        s = s.upper()
        width = art.text_width(s, scale)
        if x is None:
            x = cx(pk.W / 2) - width // 2
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

    def _panel(self, g):
        self.text("%d" % g.score, 22, x=4)
        self.text("HI %d" % g.best, 26, (170, 170, 170), scale=1)
        if g.state != "attract":
            self.text("WAVE %d" % g.wave, 26, (170, 170, 170), scale=1, x=286, right=True)
            lives = max(0, min(g.lives - (g.knight in ("ok", "grabbed")), 8))
            icon = self.pic("life", self._life_icon)
            for i in range(lives):                       # knights to come
                self.canvas.blit(icon, (4 + i * 16, CANVAS_H - 18))
        mid = cy(330)
        if g.state == "attract":
            self.text("PLUME", cy(150), (255, 200, 60), scale=6)
            self.text("KNIGHTS", cy(150) + 40, (255, 200, 60), scale=5)
            for i, line in enumerate(("LEFT: FLY LEFT", "RIGHT: FLY RIGHT", "BOTH: FLAP", "", "FLAP TO FLY",
                                      "HIGHER LANCE WINS")):
                self.text(line, cy(420) + i * 16, (190, 190, 190))
            if int(g.timer * 2) % 2 == 0:
                self.text("BOTH TO START", cy(640), (255, 220, 120))
        elif g.state == "intro":
            self.text("WAVE %d" % g.wave, mid, (255, 220, 120), scale=3)
            note = ("EGG WAVE" if g.egg_wave else "SURVIVAL WAVE" if g.survival else
                    "BEWARE THE FIRE SERPENT" if g.wave == pk.GUARDIAN_FROM else "")
            if note:
                self.text(note, mid + 30, (190, 190, 190))
            if g.egg_wave:
                self.text("GATHER THEM BEFORE THEY HATCH", mid + 46, (150, 150, 150), scale=1)
        elif g.state == "clear":
            self.text("WAVE %d COMPLETE" % g.wave, mid, (120, 255, 160))
            if g.bonus_won:
                why = "ALL EGGS" if g.egg_wave else "SURVIVAL"
                self.text("%s BONUS %d" % (why, g.bonus_won), mid + 20, (255, 220, 120))
        elif g.state == "over":
            self.text("GAME OVER", mid - 20, scale=4)
            self.text("SCORE %d" % g.score, mid + 14)
            if g.score > g.best_at_start:
                self.text("A NEW HIGH SCORE!", mid + 32, (255, 220, 120))
            else:
                self.text("HIGH SCORE %d" % g.best, mid + 32, (170, 170, 170))
            if g.timer >= pk.OVER_WAIT:
                self.text("BOTH: PLAY AGAIN", mid + 56, (170, 170, 170))
                self.text("LIFT THE HANDSET TO STOP", mid + 72, (170, 170, 170))

    @staticmethod
    def _life_icon():
        """A knight to come: the bird and knight, small."""
        s = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
        s.blit(mount_picture("knight", "mid", "stand"), (0, 0))
        s.blit(knight_picture("knight"), (0, 0))
        return pygame.transform.scale(s, (SPRITE_W // 2, SPRITE_H // 2))      # (no blending: it is made see-through)
