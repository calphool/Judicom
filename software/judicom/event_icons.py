"""Little cartoon pictures for the events on the info screen, chosen from the event's name:

    Amy's birthday -> a cake         Christmas, Christmas Eve -> a tree      Easter -> a painted egg
    Independence Day, 4th of July, New Year's -> fireworks                    Flag Day, Memorial / Veterans / Presidents' Day -> a flag
    Thanksgiving -> a turkey         Halloween -> a pumpkin                   Valentine's Day, anniversary, wedding, Grandparents' Day -> a heart
    St. Patrick's Day -> a shamrock  Mother's Day -> a flower                 Father's Day -> a tie
    Visit from ... -> a house        Martin Luther King Jr. Day, Juneteenth, Labor Day, Columbus Day -> a star
    anything else -> a calendar page with the day of the month on it

    icon = event_icon(title, size, day)      # a transparent size x size surface (made once per kind, size and day)

Drawn with pygame shapes (no picture files) at four times the size and then shrunk, so the edges are smooth.  The choice goes
by words in the name (capitals do not matter), the first match in ICONS winning.
"""
import math

import pygame

ICONS = [                                   # (words, any of which in the title picks it, icon)
    (("birthday",), "cake"),
    (("christmas", "xmas"), "tree"),
    (("easter",), "egg"),
    (("independence", "4th of july", "fourth of july", "july 4", "new year"), "fireworks"),
    (("flag", "memorial", "veteran", "president"), "flag"),
    (("thanksgiving",), "turkey"),
    (("halloween",), "pumpkin"),
    (("valentine", "anniversary", "wedding", "grandparent"), "heart"),
    (("patrick",), "shamrock"),
    (("mother",), "flower"),
    (("father",), "tie"),
    (("visit",), "house"),
    (("king", "juneteenth", "labor", "columbus"), "star"),
]
LINE = (40, 34, 36)
_cache = {}


def icon_for(title):
    t = (title or "").casefold().replace("’", "'")
    for words, kind in ICONS:
        if any(w in t for w in words):
            return kind
    return "calendar"


def event_icon(title, size, day=0):
    kind = icon_for(title)
    key = (kind, size, day if kind == "calendar" else 0)
    if key not in _cache:
        k = 4 * size / 100.0                                         # drawn on a 100 x 100 grid, four times over
        big = pygame.Surface((int(100 * k), int(100 * k)), pygame.SRCALPHA)
        DRAW[kind](_Pen(big, k), day)
        _cache[key] = pygame.transform.smoothscale(big, (size, size))
    return _cache[key]


class _Pen:
    """Shapes on the 100 x 100 grid, each with a dark outline (o = its thickness), scaled onto the big surface."""

    def __init__(self, surf, k):
        self.s, self.k = surf, k

    def P(self, x, y):
        return int(x * self.k), int(y * self.k)

    def R(self, v):
        return max(1, int(v * self.k))

    def circle(self, color, x, y, r, o=2.5):
        if o:
            pygame.draw.circle(self.s, LINE, self.P(x, y), self.R(r + o))
        pygame.draw.circle(self.s, color, self.P(x, y), self.R(r))

    def ellipse(self, color, x, y, w, h, o=2.5):
        if o:
            pygame.draw.ellipse(self.s, LINE, pygame.Rect(*self.P(x - o, y - o), self.R(w + 2 * o), self.R(h + 2 * o)))
        pygame.draw.ellipse(self.s, color, pygame.Rect(*self.P(x, y), self.R(w), self.R(h)))

    def rect(self, color, x, y, w, h, radius=0, o=2.5):
        if o:
            pygame.draw.rect(self.s, LINE, pygame.Rect(*self.P(x - o, y - o), self.R(w + 2 * o), self.R(h + 2 * o)),
                             border_radius=self.R(radius + o) if radius else 0)
        pygame.draw.rect(self.s, color, pygame.Rect(*self.P(x, y), self.R(w), self.R(h)), border_radius=self.R(radius) if radius else 0)

    def poly(self, color, pts, o=2.5):
        pp = [self.P(x, y) for x, y in pts]
        if o:
            pygame.draw.polygon(self.s, LINE, pp, self.R(2 * o))
        pygame.draw.polygon(self.s, color, pp)
        if o:
            pygame.draw.polygon(self.s, LINE, pp, self.R(o))

    def line(self, color, a, b, w):
        pygame.draw.line(self.s, color, self.P(*a), self.P(*b), self.R(w))
        for p in (a, b):                                                    # round ends
            pygame.draw.circle(self.s, color, self.P(*p), self.R(w / 2.0))


def _heart_pts(cx, cy, r, n=48):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * r / 16.0, cy - y * r / 16.0))
    return pts


def _star_pts(cx, cy, r, inner=0.45, turn=-90):
    pts = []
    for i in range(10):
        a = math.radians(turn + i * 36)
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


# ------------------------------------------------------------------ the pictures ---------------------------------------------
def _cake(p, day):
    p.ellipse((235, 238, 242), 8, 80, 84, 14)                               # the plate
    p.rect((246, 170, 196), 16, 50, 68, 34, radius=6)                         # the cake
    p.rect((255, 250, 244), 16, 50, 68, 10, radius=5, o=0)                    # the icing ...
    for x in range(20, 84, 12):                                              # ... dripping down
        pygame.draw.circle(p.s, (255, 250, 244), p.P(x, 60), p.R(5))
    pygame.draw.line(p.s, (214, 120, 150), p.P(17, 72), p.P(83, 72), p.R(3))
    for x, c in ((32, (120, 190, 250)), (50, (255, 210, 80)), (68, (150, 220, 140))):
        p.rect(c, x - 3.5, 28, 7, 22, radius=2, o=2)                          # candles
        p.poly((255, 190, 40), [(x, 12), (x + 5, 22), (x, 27), (x - 5, 22)], o=1.5)   # flames
        pygame.draw.circle(p.s, (255, 240, 160), p.P(x, 22), p.R(2))


def _tree(p, day):
    p.rect((130, 86, 52), 43, 76, 14, 16, radius=2)                           # trunk
    green = (64, 170, 92)
    for top, half, bottom in ((14, 22, 42), (28, 30, 60), (44, 38, 80)):
        p.poly(green, [(50, top), (50 + half, bottom), (50 - half, bottom)])
    for x, y, c in ((40, 50, (230, 60, 60)), (60, 60, (90, 160, 250)), (36, 72, (255, 210, 60)), (64, 74, (230, 60, 60)),
                    (50, 36, (255, 210, 60))):
        p.circle(c, x, y, 4, o=1.5)
    p.poly((255, 214, 60), _star_pts(50, 13, 11), o=2)


def _egg(p, day):
    p.ellipse((190, 160, 240), 22, 8, 56, 84)
    band = [(22.5 + i * 3.5, 46 + (5 if i % 2 else -5)) for i in range(17)]
    pygame.draw.lines(p.s, (255, 255, 255), False, [p.P(*q) for q in band], p.R(5))
    pygame.draw.lines(p.s, (255, 200, 90), False, [p.P(x, y + 12) for x, y in band][1:-1], p.R(4))
    for x, y in ((38, 26), (54, 22), (46, 32), (40, 68), (58, 72), (50, 80)):
        pygame.draw.circle(p.s, (255, 140, 180), p.P(x, y), p.R(3.5))
    pygame.draw.ellipse(p.s, (230, 214, 255), pygame.Rect(*p.P(32, 16), p.R(8), p.R(16)))       # shine


def _fireworks(p, day):
    for cx, cy, r, c in ((36, 36, 26, (240, 70, 80)), (68, 54, 22, (90, 170, 255)), (40, 74, 16, (255, 210, 70))):
        for i in range(12):
            a = i * math.pi / 6
            a1, a2 = (cx + math.cos(a) * r * 0.3, cy + math.sin(a) * r * 0.3), (cx + math.cos(a) * r, cy + math.sin(a) * r)
            p.line(LINE, a1, a2, 6)
            p.line(c, a1, a2, 3.2)
            pygame.draw.circle(p.s, (255, 255, 255), p.P(*a2), p.R(2.2))
        pygame.draw.circle(p.s, (255, 255, 240), p.P(cx, cy), p.R(3))


def _flag(p, day):
    p.rect((200, 200, 205), 12, 8, 5, 88, radius=2, o=2)                      # the pole
    p.circle((255, 214, 60), 14.5, 8, 4, o=1.5)
    x0, x1, y0, h = 18, 92, 14, 52

    def wave(x):
        return 4 * math.sin((x - x0) / (x1 - x0) * 2 * math.pi)
    xs = [x0 + (x1 - x0) * i / 30.0 for i in range(31)]
    outline = [(x, y0 + wave(x)) for x in xs] + [(x, y0 + h + wave(x)) for x in reversed(xs)]
    p.poly((255, 255, 255), outline, o=2.5)
    for k in range(7):                                                        # red stripes
        if k % 2:
            continue
        a, b = y0 + h * k / 7.0, y0 + h * (k + 1) / 7.0
        pygame.draw.polygon(p.s, (210, 50, 60), [p.P(x, a + wave(x)) for x in xs] + [p.P(x, b + wave(x)) for x in reversed(xs)])
    cx1 = x0 + (x1 - x0) * 0.42
    cs = [x for x in xs if x <= cx1 + 0.01]
    pygame.draw.polygon(p.s, (40, 70, 150), [p.P(x, y0 + wave(x)) for x in cs] + [p.P(x, y0 + h * 4 / 7.0 + wave(x)) for x in reversed(cs)])
    for i in range(3):
        for j in range(2):
            x = x0 + 6 + i * 9 + (4 if j else 0)
            pygame.draw.circle(p.s, (255, 255, 255), p.P(x, y0 + 8 + j * 12 + wave(x)), p.R(2))
    pygame.draw.lines(p.s, LINE, True, [p.P(*q) for q in outline], p.R(2.5))


def _turkey(p, day):
    for i, c in enumerate(((200, 80, 50), (240, 150, 50), (250, 205, 80), (200, 80, 50), (240, 150, 50), (250, 205, 80),
                           (200, 80, 50))):
        a = math.radians(180 + 15 + i * 25)
        x, y = 50 + math.cos(a) * 26, 58 + math.sin(a) * 26
        p.circle(c, x, y, 13, o=2)                                            # the tail feathers
    p.circle((140, 90, 60), 50, 62, 22)                                       # body
    p.circle((160, 105, 70), 50, 38, 12)                                      # head
    p.poly((255, 180, 40), [(50, 40), (57, 44), (50, 47)], o=1.5)              # beak
    p.ellipse((220, 50, 60), 46, 44, 5, 11, o=1.5)                             # wattle
    for x in (45, 55):
        pygame.draw.circle(p.s, LINE, p.P(x, 35), p.R(2.5))
    for x in (42, 58):
        p.line((255, 180, 40), (x, 82), (x, 92), 3)


def _pumpkin(p, day):
    orange = (245, 140, 40)
    p.rect((110, 150, 60), 46, 10, 9, 16, radius=3, o=2)                        # stem
    for x, w in ((14, 40), (46, 40), (30, 40)):
        p.ellipse(orange, x, 24, w, 66)
    for x in (34, 66):
        pygame.draw.arc(p.s, (215, 110, 30), pygame.Rect(*p.P(x - 10, 26), p.R(20), p.R(62)), math.pi / 2, 3 * math.pi / 2, p.R(2))
    for x in (38, 62):                                                         # a friendly face
        p.poly(LINE, [(x - 6, 52), (x + 6, 52), (x, 42)], o=0)
    pts = [(30, 64), (70, 64), (64, 74), (56, 70), (50, 76), (44, 70), (36, 74)]
    p.poly(LINE, pts, o=0)


def _heart(p, day):
    p.poly((235, 60, 90), _heart_pts(50, 52, 40))
    pygame.draw.ellipse(p.s, (255, 170, 190), pygame.Rect(*p.P(26, 30), p.R(14), p.R(9)))


def _shamrock(p, day):
    green = (70, 175, 90)
    p.line(LINE, (50, 58), (62, 92), 8)
    p.line((60, 140, 70), (50, 58), (62, 92), 4.5)
    for a in (-90, 30, 150):
        r = math.radians(a)
        cx, cy = 50 + math.cos(r) * 18, 48 + math.sin(r) * 18
        pts = [(cx + (x - cx) * 1, cy + (y - cy) * 1) for x, y in _heart_pts(cx, cy, 17)]
        rot = math.radians(a + 90)                                            # each leaf points into the middle
        pts = [(cx + (x - cx) * math.cos(rot) - (y - cy) * math.sin(rot), cy + (x - cx) * math.sin(rot) + (y - cy) * math.cos(rot))
               for x, y in pts]
        p.poly(green, pts, o=2)
    pygame.draw.circle(p.s, (60, 150, 75), p.P(50, 48), p.R(4))


def _flower(p, day):
    p.line(LINE, (50, 50), (50, 94), 7)
    p.line((70, 160, 80), (50, 50), (50, 94), 4)
    p.ellipse((90, 180, 100), 52, 70, 22, 11, o=2)                              # leaf
    for i in range(6):
        a = math.radians(i * 60 - 90)
        p.circle((250, 140, 180), 50 + math.cos(a) * 17, 36 + math.sin(a) * 17, 12, o=2)
    p.circle((255, 205, 70), 50, 36, 10, o=2)


def _tie(p, day):
    blue, stripe = (60, 110, 200), (140, 180, 245)
    p.poly(blue, [(42, 26), (58, 26), (68, 74), (50, 92), (32, 74)])
    for i in range(4):
        y = 36 + i * 13
        pygame.draw.line(p.s, stripe, p.P(36, y + 8), p.P(64, y - 2), p.R(3.5))
    p.poly(blue, [(38, 8), (62, 8), (58, 27), (42, 27)])                        # the knot
    p.poly((235, 240, 245), [(20, 4), (38, 8), (42, 27), (24, 18)], o=2)         # collar
    p.poly((235, 240, 245), [(80, 4), (62, 8), (58, 27), (76, 18)], o=2)


def _house(p, day):
    p.rect((200, 90, 70), 66, 14, 10, 22, o=2)                                  # chimney
    p.rect((250, 236, 205), 20, 46, 60, 44)                                    # walls
    p.poly((210, 70, 70), [(50, 12), (90, 48), (10, 48)])                       # roof
    p.rect((130, 90, 60), 43, 64, 14, 26, radius=2, o=2)                        # door
    pygame.draw.circle(p.s, (255, 214, 60), p.P(54, 78), p.R(1.8))
    for x in (26, 63):
        p.rect((255, 220, 110), x, 56, 11, 11, o=2)                            # lit windows


def _star(p, day):
    p.poly((255, 210, 60), _star_pts(50, 54, 44, inner=0.48))
    p.poly((255, 236, 150), _star_pts(44, 44, 10, inner=0.5), o=0)


def _calendar(p, day):
    p.rect((250, 250, 248), 14, 18, 72, 74, radius=8)
    p.rect((220, 70, 70), 14, 18, 72, 20, radius=8, o=0)
    pygame.draw.rect(p.s, (220, 70, 70), pygame.Rect(*p.P(14, 30), p.R(72), p.R(8)))
    for x in (32, 68):
        p.rect((200, 200, 205), x - 3, 10, 6, 16, radius=3, o=2)
    if day:
        from . import draw
        num = draw.text(str(day), "bold", p.R(40), LINE)
        p.s.blit(num, num.get_rect(center=p.P(50, 64)))


DRAW = {"cake": _cake, "tree": _tree, "egg": _egg, "fireworks": _fireworks, "flag": _flag, "turkey": _turkey, "pumpkin": _pumpkin,
        "heart": _heart, "shamrock": _shamrock, "flower": _flower, "tie": _tie, "house": _house, "star": _star, "calendar": _calendar}
