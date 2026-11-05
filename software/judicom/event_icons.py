"""Little cartoon pictures for the events on the info screen, chosen from the event's name.  Each holiday has its own:

    New Year's Eve -> a clock at midnight      New Year's Day -> a party hat and horn   Martin Luther King Jr. Day -> a dove
    Valentine's Day -> a heart                 Presidents' Day -> a stovepipe hat       St. Patrick's Day -> a shamrock
    Easter -> a painted egg                    Mother's Day -> a flower                 Memorial Day -> a red poppy
    Flag Day -> a flag                         Juneteenth -> a star                     Father's Day -> a tie
    Independence Day, 4th of July -> fireworks Labor Day -> a hammer and wrench         Grandparents' Day -> a rocking chair
    Columbus Day -> a sailing ship             Halloween -> a pumpkin                   All Saints Day -> a lit candle
    Veterans Day -> a medal                    Thanksgiving -> a turkey                 Christmas Eve -> a stocking
    Christmas -> a tree                        Ugly Sweater Day -> a Christmas sweater
    any birthday -> a cake       an anniversary or wedding -> two rings      Visit from ... -> a house
    and the family's own made-up days: Flagpole -> a flag going up, Morse code -> a telegraph key, Absolutely Nothing -> a hammock,
    Cat's Questions -> a cat, Backwards -> an arrow pointing back, Go To Work Naked -> a barrel, Grouch -> a grumpy smile,
    Dog Biscuit -> a bone, Sleep -> a moon, Ides of March -> a laurel wreath, Goof Off -> a paper airplane,
    Make Up Your Own Holiday -> a light bulb, April Fool -> a jester's hat, Tell A Lie -> a long nose, Lawyer -> scales,
    Pajamas -> a pajama top, Astronaut -> a rocket, No Pants -> boxer shorts, Lost Sock -> an odd sock,
    Dance Like A Chicken -> a chicken, Star War -> a ringed planet, Under Your Pillow -> a pillow hiding a rubber duck
    anything else -> a calendar page with the day of the month on it

    icon = event_icon(title, size, day)      # a transparent size x size surface (made once per kind, size and day)

Drawn with pygame shapes (no picture files) at four times the size and then shrunk, so the edges are smooth.  The choice goes
by words in the name (capitals do not matter), the first match in ICONS winning.
"""
import math

import pygame

ICONS = [                                   # (words, any of which in the title picks it, icon); the first match wins
    (("birthday",), "cake"),
    (("sweater",), "sweater"),
    (("flagpole",), "flagpole"),                          # the made-up family days
    (("morse",), "telegraph"),
    (("absolutely nothing", "nothing day"), "hammock"),
    (("your cat", "cat's", "cat day"), "cat"),
    (("backward",), "arrow"),
    (("naked",), "barrel"),
    (("grouch",), "grouch"),
    (("biscuit",), "bone"),
    (("sleep",), "moon"),
    (("ides of march",), "wreath"),
    (("goof",), "plane"),
    (("own holiday",), "bulb"),
    (("fool",), "jester"),
    (("tell a lie", "lie day"), "nose"),
    (("lawyer", "attorney"), "scales"),
    (("pajama", "pyjama"), "pajamas"),
    (("astronaut",), "rocket"),
    (("pants",), "boxers"),
    (("sock",), "sock"),
    (("chicken",), "chicken"),
    (("star war",), "planet"),
    (("pillow",), "pillow"),
    (("christmas eve", "xmas eve"), "stocking"),
    (("christmas", "xmas"), "tree"),
    (("new year's eve", "new years eve", "new year eve"), "clock"),
    (("new year",), "partyhat"),
    (("easter",), "egg"),
    (("independence", "4th of july", "fourth of july", "july 4"), "fireworks"),
    (("flag",), "flag"),
    (("memorial",), "poppy"),
    (("veteran",), "medal"),
    (("president",), "tophat"),
    (("thanksgiving",), "turkey"),
    (("halloween",), "pumpkin"),
    (("valentine",), "heart"),
    (("anniversary", "wedding"), "rings"),
    (("grandparent",), "rocker"),
    (("patrick",), "shamrock"),
    (("mother",), "flower"),
    (("father",), "tie"),
    (("luther", "mlk"), "dove"),
    (("juneteenth",), "star"),
    (("labor", "labour"), "tools"),
    (("columbus",), "ship"),
    (("all saints", "saints"), "candle"),
    (("visit",), "house"),
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


def _clock(p, day):
    for x in (24, 76):                                                        # alarm bells
        p.circle((255, 205, 70), x, 22, 11, o=2)
    p.line(LINE, (30, 86), (24, 94), 6)                                       # feet
    p.line(LINE, (70, 86), (76, 94), 6)
    p.circle((255, 205, 70), 50, 56, 36)                                      # the case
    p.circle((255, 252, 240), 50, 56, 29, o=2)                                # the face
    for i in range(12):
        a = math.radians(i * 30 - 90)
        r1 = 22 if i % 3 else 19
        pygame.draw.line(p.s, LINE, p.P(50 + math.cos(a) * r1, 56 + math.sin(a) * r1),
                         p.P(50 + math.cos(a) * 26, 56 + math.sin(a) * 26), p.R(2.5 if i % 3 == 0 else 1.5))
    p.line(LINE, (50, 56), (48.5, 40), 5)                                     # hour hand, just before twelve
    p.line((220, 60, 60), (50, 56), (50, 31), 2.8)                            # minute hand on twelve
    pygame.draw.circle(p.s, LINE, p.P(50, 56), p.R(3.5))
    for x, y, r in ((10, 6, 6), (92, 8, 5), (50, 6, 4)):                       # sparkles: midnight
        p.poly((255, 240, 150), _star_pts(x, y, r, inner=0.35), o=1.2)


def _partyhat(p, day):
    for x, y, c in ((12, 20, (240, 80, 90)), (82, 14, (90, 170, 255)), (88, 36, (255, 210, 70)), (20, 52, (150, 220, 140)),
                    (72, 50, (240, 80, 90)), (8, 80, (255, 210, 70))):
        p.rect(c, x - 2.5, y - 2.5, 5, 5, radius=1, o=1.2)                   # confetti
    cone = [(18, 84), (62, 84), (40, 16)]
    p.poly((120, 110, 230), cone)
    for x, y in ((40, 34), (32, 56), (48, 54), (26, 74), (42, 74), (56, 74)):
        pygame.draw.circle(p.s, (255, 214, 60), p.P(x, y), p.R(3.2))          # polka dots
    p.rect((255, 214, 60), 16, 80, 48, 7, radius=3, o=2)                      # the band at the bottom
    p.circle((240, 80, 90), 40, 14, 7, o=2)                                   # the pompom
    p.poly((240, 80, 90), [(62, 92), (90, 60), (97, 68), (66, 96)], o=2)      # the horn
    p.ellipse((255, 214, 60), 86, 54, 14, 18, o=2)
    for i in range(3):
        pygame.draw.line(p.s, (255, 255, 255), p.P(68 + i * 8, 87 - i * 9), p.P(72 + i * 8, 91 - i * 9), p.R(2.5))


def _dove(p, day):
    white = (250, 250, 252)
    p.poly(white, [(26, 52), (4, 42), (8, 58), (2, 66), (26, 64)])            # tail
    p.ellipse(white, 20, 46, 56, 26)                                          # body
    wing = [(36, 54), (30, 40), (26, 26), (24, 12), (34, 16), (46, 24), (56, 34), (64, 52)]
    p.poly(white, wing)                                                       # the raised wing
    pygame.draw.lines(p.s, (205, 210, 222), False, [p.P(31, 22), p.P(40, 34), p.P(46, 48)], p.R(2))
    p.circle(white, 74, 46, 11)                                               # head
    p.poly((255, 170, 60), [(83, 43), (95, 47), (83, 51)], o=1.5)             # beak
    pygame.draw.circle(p.s, LINE, p.P(76, 43), p.R(2.4))
    p.line(LINE, (88, 50), (80, 80), 5)                                       # the olive branch
    p.line((110, 140, 60), (88, 50), (80, 80), 2.5)
    for x, y, w in ((84, 58, 1), (82, 68, -1), (80, 78, 1), (86, 64, 1)):
        p.ellipse((110, 175, 80), x + (1 if w > 0 else -13), y - 3, 12, 6, o=1.5)


def _tophat(p, day):
    hat, shine = (58, 58, 66), (96, 96, 108)
    p.ellipse(hat, 8, 78, 84, 16)                                             # brim
    p.rect(hat, 27, 10, 46, 76, radius=3)                                     # the tall crown
    pygame.draw.rect(p.s, shine, pygame.Rect(*p.P(33, 14), p.R(6), p.R(52)), border_radius=p.R(3))
    p.rect((150, 40, 50), 27, 64, 46, 12, o=0)                                # band
    pygame.draw.line(p.s, LINE, p.P(27, 64), p.P(73, 64), p.R(2))
    pygame.draw.line(p.s, LINE, p.P(27, 76), p.P(73, 76), p.R(2))


def _poppy(p, day):
    p.line(LINE, (50, 56), (56, 96), 7)
    p.line((70, 150, 70), (50, 56), (56, 96), 4)
    p.ellipse((90, 170, 90), 56, 74, 22, 10, o=2)                             # leaf
    red = (225, 40, 45)
    for a in (-135, -45, 45, 135, -90):
        r = math.radians(a)
        p.circle(red, 50 + math.cos(r) * 15, 40 + math.sin(r) * 15, 18, o=2)
    for a in (-135, -45, 45, 135):                                            # petal folds
        r = math.radians(a)
        pygame.draw.circle(p.s, (245, 90, 90), p.P(50 + math.cos(r) * 20, 40 + math.sin(r) * 20), p.R(5))
    p.circle((40, 34, 36), 50, 40, 9, o=0)                                    # the dark middle
    for a in range(0, 360, 45):
        r = math.radians(a)
        pygame.draw.circle(p.s, (90, 120, 60), p.P(50 + math.cos(r) * 5, 40 + math.sin(r) * 5), p.R(1.5))


def _tools(p, day):
    steel, dark = (196, 202, 212), (150, 156, 168)
    a, b = (80, 88), (34, 28)                                                 # the wrench, lower right to upper left
    p.line(LINE, a, b, 13)
    p.line(steel, a, b, 8)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n                                                   # along the handle, toward the head
    vx, vy = -uy, ux
    p.circle(steel, 30, 23, 14)                                               # head ...
    cx, cy = 30 + ux * 4, 23 + uy * 4
    notch = [(cx + vx * 6, cy + vy * 6), (cx - vx * 6, cy - vy * 6),          # ... with the open jaw
             (cx - vx * 6 + ux * 16, cy - vy * 6 + uy * 16), (cx + vx * 6 + ux * 16, cy + vy * 6 + uy * 16)]
    pygame.draw.polygon(p.s, (0, 0, 0, 0), [p.P(*q) for q in notch])
    for i, j in ((0, 3), (1, 2), (0, 1)):
        pygame.draw.line(p.s, LINE, p.P(*notch[i]), p.P(*notch[j]), p.R(2.5))
    pygame.draw.circle(p.s, dark, p.P(70, 75), p.R(3))
    a, b = (20, 88), (62, 32)                                                 # the hammer, lower left to upper right
    p.line(LINE, a, b, 12)
    p.line((190, 130, 70), a, b, 7)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    vx, vy = uy, -ux
    cx, cy = b[0] + ux * 4, b[1] + uy * 4
    head = [(cx + vx * 20 + ux * 8, cy + vy * 20 + uy * 8), (cx + vx * 20 - ux * 8, cy + vy * 20 - uy * 8),
            (cx - vx * 12 - ux * 8, cy - vy * 12 - uy * 8), (cx - vx * 18 - ux * 2, cy - vy * 18 - uy * 2),
            (cx - vx * 12 + ux * 8, cy - vy * 12 + uy * 8)]
    p.poly(steel, head)


def _rocker(p, day):
    wood, dark = (176, 112, 60), (140, 86, 44)

    def rock(x):
        return 88 - 10 * ((x - 50) / 42.0) ** 2
    curve = [(x, rock(x)) for x in range(8, 93, 4)]
    pygame.draw.lines(p.s, LINE, False, [p.P(*q) for q in curve], p.R(9))
    pygame.draw.lines(p.s, wood, False, [p.P(*q) for q in curve], p.R(4.5))
    for q in (curve[0], curve[-1]):
        pygame.draw.circle(p.s, wood, p.P(*q), p.R(2.3))
    for top, bottom in (((30, 60), (28, rock(28))), ((68, 60), (70, rock(70))), ((66, 42), (68, 60))):
        p.line(LINE, top, bottom, 8)
        p.line(dark, top, bottom, 4)
    p.line(LINE, (30, 62), (18, 10), 9)                                       # the back, leaning
    p.line(wood, (30, 62), (18, 10), 5)
    p.line(LINE, (40, 60), (30, 14), 7)
    p.line(wood, (40, 60), (30, 14), 3.5)
    p.line(LINE, (24, 42), (70, 42), 8)                                       # arm rest
    p.line(wood, (24, 42), (70, 42), 4)
    p.rect((230, 110, 130), 26, 54, 46, 9, radius=4, o=2)                     # the seat cushion
    p.poly((120, 170, 230), [(16, 16), (34, 18), (38, 40), (22, 40)], o=2)     # a knitted throw over the back
    for y in (24, 31):
        pygame.draw.line(p.s, (180, 210, 250), p.P(20, y), p.P(35, y + 1), p.R(2))


def _ship(p, day):
    p.line(LINE, (50, 8), (50, 72), 6)                                        # mast
    p.line((140, 90, 50), (50, 8), (50, 72), 3)
    p.poly((230, 60, 60), [(50, 6), (64, 10), (50, 15)], o=1.5)               # pennant
    sail = (252, 248, 236)
    p.poly(sail, [(32, 18), (68, 18), (72, 30), (70, 42), (30, 42), (28, 30)])
    p.poly(sail, [(26, 46), (74, 46), (78, 58), (76, 68), (24, 68), (22, 58)])
    p.poly((176, 112, 60), [(8, 66), (92, 66), (80, 86), (20, 86)])            # hull
    pygame.draw.line(p.s, (130, 80, 40), p.P(14, 74), p.P(86, 74), p.R(2))
    for x in (30, 44, 58, 72):
        pygame.draw.circle(p.s, LINE, p.P(x, 79), p.R(2.2))                   # portholes
    xs = [4 + i * 2 for i in range(47)]
    waves = [(x, 88 + 3 * math.sin(x / 5.0)) for x in xs] + [(96, 98), (4, 98)]
    p.poly((80, 150, 230), waves, o=2)


def _candle(p, day):
    glow = pygame.Surface(p.s.get_size(), pygame.SRCALPHA)                     # soft light around the flame
    for r, alpha in ((22, 45), (16, 75), (11, 110)):
        pygame.draw.circle(glow, (255, 230, 140, alpha), p.P(50, 26), p.R(r))
    p.s.blit(glow, (0, 0))
    p.ellipse((235, 190, 80), 16, 82, 68, 13)                                  # the holder
    p.rect((252, 246, 228), 37, 44, 26, 44, radius=3)                          # the candle
    p.poly((252, 246, 228), [(37, 46), (44, 46), (44, 56), (40.5, 60), (37, 56)], o=0)   # a drip
    pygame.draw.circle(p.s, (252, 246, 228), p.P(40.5, 57), p.R(3.5))
    pygame.draw.line(p.s, LINE, p.P(50, 44), p.P(50, 38), p.R(2.5))            # wick
    p.poly((255, 160, 40), [(50, 12), (57, 26), (55, 34), (50, 38), (45, 34), (43, 26)], o=2)   # the flame
    p.poly((255, 240, 150), [(50, 22), (53, 30), (50, 35), (47, 30)], o=0)


def _medal(p, day):
    stripes = ((60, 90, 180), (250, 250, 250), (220, 60, 60), (250, 250, 250), (60, 90, 180))
    p.rect(LINE, 34, 4, 32, 44, o=0)
    for i, c in enumerate(stripes):                                           # the ribbon
        pygame.draw.rect(p.s, c, pygame.Rect(*p.P(36.5 + i * 5.4, 6.5), p.R(5.6), p.R(42)))
    p.poly((235, 190, 70), [(44, 44), (56, 44), (56, 54), (44, 54)], o=2)      # the loop
    p.circle((240, 195, 60), 50, 68, 25)                                       # the medal
    p.circle((250, 215, 100), 50, 68, 19, o=1.5)
    p.poly((240, 180, 40), _star_pts(50, 69, 15, inner=0.45), o=1.8)


def _stocking(p, day):
    red = (215, 50, 55)
    leg = [(34, 22), (64, 22), (64, 56), (80, 62), (90, 72), (88, 84), (78, 90), (62, 90), (46, 84), (36, 72), (34, 58)]
    p.poly(red, leg)
    toe = [(76, 62), (80, 62), (90, 72), (88, 84), (78, 90), (72, 90), (70, 76)]
    pygame.draw.polygon(p.s, (70, 160, 90), [p.P(*q) for q in toe])
    pygame.draw.lines(p.s, LINE, True, [p.P(*q) for q in leg], p.R(2.5))
    pygame.draw.line(p.s, LINE, p.P(76, 62), p.P(70, 76), p.R(2))
    pygame.draw.line(p.s, LINE, p.P(70, 76), p.P(74, 90), p.R(2))
    for x, y in ((44, 40), (54, 50), (46, 66), (58, 76)):
        p.poly((255, 255, 255), _star_pts(x, y, 4, inner=0.45), o=0)           # snowflakes
    p.rect((252, 252, 248), 28, 8, 42, 16, radius=6)                           # the white cuff
    for x in range(33, 68, 7):
        pygame.draw.circle(p.s, (225, 228, 232), p.P(x, 16), p.R(2))
    p.line(LINE, (66, 10), (78, 2), 4)                                         # hanging loop
    p.line((215, 50, 55), (66, 10), (78, 2), 2)


def _sweater(p, day):
    red, green, white = (205, 45, 55), (40, 140, 80), (250, 250, 250)
    body = [(30, 14), (42, 12), (50, 18), (58, 12), (70, 14), (92, 30), (96, 64), (82, 66), (78, 44), (76, 90), (24, 90),
            (22, 44), (18, 66), (4, 64), (8, 30)]
    p.poly(red, body)
    for y0 in (26, 70):                                                        # zigzag bands
        pygame.draw.lines(p.s, white, False, [p.P(25 + i * 5, y0 + (4 if i % 2 else 0)) for i in range(11)], p.R(3))
    pygame.draw.lines(p.s, green, False, [p.P(25 + i * 5, 80 + (4 if i % 2 else 0)) for i in range(11)], p.R(3))
    for a, b in (((7, 50), (19, 52)), ((93, 50), (81, 52))):                  # stripes on the sleeves
        pygame.draw.line(p.s, white, p.P(*a), p.P(*b), p.R(3))
    p.poly(green, [(50, 34), (60, 54), (55, 54), (63, 66), (37, 66), (45, 54), (40, 54)], o=1.8)   # a little tree on the front
    p.poly((255, 214, 60), _star_pts(50, 33, 5, inner=0.45), o=1.2)
    for x, y in ((47, 50), (54, 59), (45, 62)):
        pygame.draw.circle(p.s, (255, 214, 60), p.P(x, y), p.R(1.8))
    for x, y in ((30, 40), (70, 40), (32, 58), (68, 58)):                      # snowflakes
        for a in (0, 60, 120):
            r = math.radians(a)
            pygame.draw.line(p.s, white, p.P(x - math.cos(r) * 4, y - math.sin(r) * 4), p.P(x + math.cos(r) * 4, y + math.sin(r) * 4), p.R(1.6))
    pygame.draw.lines(p.s, LINE, True, [p.P(*q) for q in body], p.R(2.5))
    p.poly((170, 30, 42), [(40, 12), (50, 22), (60, 12), (56, 11), (50, 16), (44, 11)], o=1.8)    # the ribbed collar
    for a, b in (((22, 44), (22, 88)), ((78, 44), (78, 88))):                  # arm seams
        pygame.draw.line(p.s, (160, 30, 40), p.P(*a), p.P(*b), p.R(1.5))
    p.rect((170, 30, 42), 24, 86, 52, 6, o=2)                                   # ribbed hem
    p.poly((170, 30, 42), [(4.5, 58), (18.5, 60), (18, 66), (4, 64)], o=1.8)   # cuffs
    p.poly((170, 30, 42), [(95.5, 58), (81.5, 60), (82, 66), (96, 64)], o=1.8)


def _ring(size, k, cx, cy, r, w=7, o=2.5):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    q = _Pen(surf, k)
    pygame.draw.circle(surf, LINE, q.P(cx, cy), q.R(r + w / 2 + o))
    pygame.draw.circle(surf, (240, 195, 60), q.P(cx, cy), q.R(r + w / 2))
    pygame.draw.circle(surf, (255, 230, 140), q.P(cx - 2, cy - 2), q.R(r + w / 2 - 2.5), q.R(2))   # shine
    pygame.draw.circle(surf, LINE, q.P(cx, cy), q.R(r - w / 2))
    pygame.draw.circle(surf, (0, 0, 0, 0), q.P(cx, cy), q.R(r - w / 2 - o))
    return surf


def _rings(p, day):
    size = p.s.get_size()
    left, right = _ring(size, p.k, 36, 60, 24), _ring(size, p.k, 64, 60, 24)
    p.s.blit(left, (0, 0))
    p.s.blit(right, (0, 0))
    x, y = p.P(42, 26)
    p.s.blit(left, (x, y), pygame.Rect(x, y, p.R(16), p.R(24)))               # the left ring passes over at the top: linked
    p.poly((200, 235, 255), [(56, 30), (72, 30), (76, 24), (64, 14), (52, 24)], o=2)   # the diamond
    pygame.draw.line(p.s, (255, 255, 255), p.P(58, 24), p.P(64, 18), p.R(2))


# ------------------------------------------------------------------ the family's made-up days ---------------------------------
def _label(p, string, x, y, px, color=(255, 255, 255), kind="bold"):
    """A word or sign drawn at (x, y) (its middle), with a dark outline."""
    from . import draw
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        img = draw.text(string, kind, p.R(px), LINE)
        p.s.blit(img, img.get_rect(center=(p.P(x, y)[0] + dx * p.R(1.6), p.P(x, y)[1] + dy * p.R(1.6))))
    img = draw.text(string, kind, p.R(px), color)
    p.s.blit(img, img.get_rect(center=p.P(x, y)))


def _clipped(p, pts, paint):
    """paint(pen) fills a scratch surface; only the part inside the outline pts is kept, then the outline is drawn."""
    tmp = pygame.Surface(p.s.get_size(), pygame.SRCALPHA)
    paint(_Pen(tmp, p.k))
    mask = pygame.Surface(p.s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [p.P(*q) for q in pts])
    tmp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pygame.draw.polygon(p.s, LINE, [p.P(*q) for q in pts], p.R(5))
    p.s.blit(tmp, (0, 0))
    pygame.draw.polygon(p.s, LINE, [p.P(*q) for q in pts], p.R(2.5))


def _leaf(cx, cy, angle, length, width):
    a = math.radians(angle)
    ux, uy, vx, vy = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    pts = []
    for i in range(13):
        t = i / 12.0
        w = math.sin(math.pi * t) * width / 2
        pts.append((cx + ux * (t - 0.5) * length + vx * w, cy + uy * (t - 0.5) * length + vy * w))
    for i in range(11, 0, -1):
        t = i / 12.0
        w = math.sin(math.pi * t) * width / 2
        pts.append((cx + ux * (t - 0.5) * length - vx * w, cy + uy * (t - 0.5) * length - vy * w))
    return pts


def _flagpole(p, day):
    p.rect((200, 200, 205), 30, 10, 6, 80, radius=2, o=2)                      # the pole
    p.circle((255, 214, 60), 33, 8, 5, o=1.5)
    p.rect((150, 150, 160), 20, 86, 26, 8, radius=2, o=2)                       # its base
    pygame.draw.line(p.s, LINE, p.P(37, 10), p.P(37, 86), p.R(1.2))            # the rope
    p.poly((90, 140, 230), [(37, 44), (70, 52), (37, 62)], o=2.2)               # a pennant on its way up
    pygame.draw.circle(p.s, (255, 255, 255), p.P(46, 53), p.R(3))
    p.line(LINE, (84, 86), (84, 26), 9)                                         # the up arrow
    p.line((80, 190, 110), (84, 86), (84, 26), 5)
    p.poly((80, 190, 110), [(72, 32), (84, 14), (96, 32)], o=2)


def _telegraph(p, day):
    p.rect((176, 112, 60), 8, 70, 84, 18, radius=4)                            # wooden base
    p.rect((235, 190, 80), 22, 58, 10, 14, radius=2, o=2)                       # pivot
    p.line(LINE, (20, 62), (80, 54), 9)
    p.line((235, 190, 80), (20, 62), (80, 54), 5)                               # brass lever
    p.ellipse((70, 70, 82), 68, 44, 24, 12, o=2)                                # the knob
    p.rect((235, 190, 80), 74, 56, 6, 14, radius=1, o=1.5)                      # contact
    y = 22
    for kind, x in (("dot", 14), ("dash", 26), ("dot", 52), ("dash", 64)):      # dot dash dot dash
        if kind == "dot":
            p.circle((255, 214, 60), x, y, 5, o=2)
        else:
            p.rect((255, 214, 60), x, y - 5, 22, 10, radius=5, o=2)


def _hammock(p, day):
    p.circle((255, 214, 60), 50, 16, 9, o=2)                                    # a lazy sun
    for x in (10, 90):
        p.rect((150, 100, 55), x - 3, 28, 6, 66, radius=2, o=2)                 # the posts
    top = [(x, 44 + 22 * (1 - ((x - 50) / 38.0) ** 2)) for x in range(14, 87, 4)]
    bottom = [(x, y + 12 * (1 - ((x - 50) / 38.0) ** 2) + 2) for x, y in reversed(top)]
    p.poly((245, 150, 60), top + bottom)
    pygame.draw.lines(p.s, (255, 240, 200), False, [p.P(x, y + 7 * (1 - ((x - 50) / 38.0) ** 2) + 1) for x, y in top], p.R(3))
    for a, b in (((10, 32), (14, 44)), ((90, 32), (86, 44))):                   # the ropes
        pygame.draw.line(p.s, LINE, p.P(*a), p.P(*b), p.R(2))


def _cat(p, day):
    fur, pink = (240, 160, 70), (250, 170, 180)
    for pts in (((16, 44), (20, 12), (42, 30)), ((46, 30), (68, 12), (72, 44))):
        p.poly(fur, pts)
    for pts in (((22, 36), (23, 20), (34, 30)), ((54, 30), (65, 20), (66, 36))):
        p.poly(pink, pts, o=0)
    p.ellipse(fur, 12, 28, 64, 58)                                               # head
    for x in (32, 56):
        p.ellipse((150, 210, 110), x - 6, 46, 12, 14, o=2)                        # eyes
        p.ellipse(LINE, x - 2, 48, 4, 10, o=0)
    p.poly(pink, [(40, 62), (48, 62), (44, 67)], o=1.5)                           # nose
    pygame.draw.lines(p.s, LINE, False, [p.P(38, 72), p.P(44, 68), p.P(50, 72)], p.R(2))
    for y, d in ((62, -2), (68, 2)):                                              # whiskers
        pygame.draw.line(p.s, LINE, p.P(30, 66), p.P(8, y + d), p.R(1.5))
        pygame.draw.line(p.s, LINE, p.P(58, 66), p.P(80, y + d), p.R(1.5))
    _label(p, "?", 84, 24, 40, (255, 214, 60))


def _arrow(p, day):
    pts = [(8, 50), (44, 18), (44, 36), (90, 36), (90, 64), (44, 64), (44, 82)]
    p.poly((90, 150, 230), pts)
    pygame.draw.lines(p.s, (170, 205, 250), False, [p.P(46, 41), p.P(86, 41)], p.R(3))
    _label(p, "321", 66, 51, 18)


def _barrel(p, day):
    p.circle((250, 210, 170), 50, 20, 14)                                         # a fellow's head ...
    for x in (45, 55):
        pygame.draw.circle(p.s, LINE, p.P(x, 18), p.R(2))
    pygame.draw.arc(p.s, LINE, pygame.Rect(*p.P(43, 16), p.R(14), p.R(10)), math.pi + 0.4, 2 * math.pi - 0.4, p.R(2))
    pygame.draw.circle(p.s, (245, 150, 150), p.P(41, 24), p.R(2.5))
    pygame.draw.circle(p.s, (245, 150, 150), p.P(59, 24), p.R(2.5))
    for x in (38, 58):
        p.ellipse((250, 210, 170), x - 4, 86, 12, 8, o=2)                         # ... and his bare feet
    side = [(50 + (20 + 7 * math.sin(math.pi * i / 10.0)) * sgn, 34 + 54 * i / 10.0) for sgn in (1,) for i in range(11)]
    pts = side + [(100 - x, y) for x, y in reversed(side)]
    p.poly((176, 112, 60), pts)                                                   # ... in a barrel
    for i in (3, 5, 7):
        pygame.draw.line(p.s, (140, 86, 44), p.P(30 + i * 4 - 6, 36), p.P(30 + i * 4 - 6, 86), p.R(1.5))
    for y in (44, 76):
        w = 20 + 7 * math.sin(math.pi * (y - 34) / 54.0)
        pygame.draw.line(p.s, LINE, p.P(50 - w, y), p.P(50 + w, y), p.R(4))
    p.ellipse((140, 86, 44), 28, 30, 44, 9, o=2)                                  # the rim
    for x in (30, 70):
        p.circle((250, 210, 170), x, 33, 5, o=2)                                  # hands holding it up


def _grouch(p, day):
    p.circle((255, 210, 70), 50, 52, 40)
    for a, b in (((26, 33), (42, 35)), ((74, 33), (58, 35))):                    # bushy grouchy eyebrows ...
        p.line((120, 80, 50), a, b, 7)
    for x in (36, 64):
        pygame.draw.circle(p.s, LINE, p.P(x, 46), p.R(4.5))
    for x in (24, 76):
        pygame.draw.circle(p.s, (245, 150, 120), p.P(x, 60), p.R(6))
    pygame.draw.arc(p.s, LINE, pygame.Rect(*p.P(28, 44), p.R(44), p.R(34)), math.pi + 0.35, 2 * math.pi - 0.35, p.R(4.5))   # ... a big smile


def _bone(p, day):
    tan = (220, 175, 115)
    ends = ((18, 38), (18, 62), (82, 38), (82, 62))
    for x, y in ends:
        pygame.draw.circle(p.s, LINE, p.P(x, y), p.R(14.5))
    pygame.draw.rect(p.s, LINE, pygame.Rect(*p.P(16, 37.5), p.R(68), p.R(25)))
    for x, y in ends:
        pygame.draw.circle(p.s, tan, p.P(x, y), p.R(12))
    pygame.draw.rect(p.s, tan, pygame.Rect(*p.P(18, 40), p.R(64), p.R(20)))
    for x in (36, 50, 64):
        pygame.draw.circle(p.s, (180, 130, 80), p.P(x, 50), p.R(2.2))
    p.poly((235, 60, 90), _heart_pts(50, 18, 11), o=2)                           # with love


def _moon(p, day):
    cx, cy, R, ox, oy, r = 42, 54, 34, 60, 42, 29                                 # a crescent: one circle less another
    away = math.atan2(cy - oy, cx - ox)
    outer = [(cx + math.cos(a) * R, cy + math.sin(a) * R) for a in (away + math.radians(d) for d in range(-180, 181, 3))
             if math.hypot(cx + math.cos(a) * R - ox, cy + math.sin(a) * R - oy) > r]
    inner = [(ox + math.cos(b) * r, oy + math.sin(b) * r) for b in (away + math.radians(d) for d in range(180, -181, -3))
             if math.hypot(ox + math.cos(b) * r - cx, oy + math.sin(b) * r - cy) < R]
    p.poly((255, 220, 100), outer + inner)
    for x, y, px in ((66, 50, 18), (78, 34, 24), (88, 14, 30)):
        _label(p, "z", x, y, px)


def _wreath(p, day):
    green, light = (80, 160, 80), (120, 195, 110)
    for side in (-1, 1):
        for i in range(8):
            a = math.radians(90 + side * (24 + i * 19))                          # round from the bottom up each side
            x, y = 50 + math.cos(a) * 32, 52 + math.sin(a) * 32
            tilt = math.degrees(a) + 90 * side * -1 + side * 30
            p.poly(green if i % 2 else light, _leaf(x, y, tilt, 20, 9), o=1.8)
    p.poly((210, 50, 60), [(50, 84), (36, 96), (40, 84), (50, 82), (60, 84), (64, 96)], o=1.8)   # a ribbon
    p.circle((210, 50, 60), 50, 84, 4, o=1.5)
    _label(p, "XV", 50, 50, 28, (255, 214, 60))


def _plane(p, day):
    for i in range(6):                                                           # where it has been
        pygame.draw.circle(p.s, (220, 230, 240), p.P(6 + i * 7, 86 - i * 2 - (i * i) * 0.4), p.R(2.2))
    p.poly((205, 215, 232), [(40, 60), (92, 18), (50, 84)])
    p.poly((252, 252, 255), [(6, 46), (92, 18), (40, 60)])
    p.poly((175, 188, 210), [(40, 60), (92, 18), (42, 72)], o=1.5)


def _bulb(p, day):
    for i in range(7):                                                           # the bright idea
        a = math.radians(-180 + i * 30)
        p.line((255, 214, 60), (50 + math.cos(a) * 32, 40 + math.sin(a) * 32), (50 + math.cos(a) * 42, 40 + math.sin(a) * 42), 4)
    p.circle((255, 232, 120), 50, 40, 24)
    p.poly((255, 232, 120), [(36, 56), (64, 56), (60, 70), (40, 70)], o=0)
    pygame.draw.lines(p.s, LINE, False, [p.P(36, 57), p.P(40, 70)], p.R(2.5))
    pygame.draw.lines(p.s, LINE, False, [p.P(64, 57), p.P(60, 70)], p.R(2.5))
    pygame.draw.lines(p.s, (230, 150, 40), False, [p.P(44, 66), p.P(44, 46), p.P(48, 52), p.P(52, 46), p.P(56, 52), p.P(56, 66)], p.R(2))
    pygame.draw.ellipse(p.s, (255, 250, 220), pygame.Rect(*p.P(36, 26), p.R(10), p.R(14)))
    p.rect((180, 185, 195), 39, 70, 22, 16, radius=3)                             # the screw base
    for y in (75, 80):
        pygame.draw.line(p.s, LINE, p.P(40, y), p.P(60, y), p.R(1.5))
    p.rect((90, 90, 100), 44, 86, 12, 6, radius=3, o=2)


def _jester(p, day):
    for pts, c in ((((18, 72), (44, 72), (6, 26)), (220, 60, 70)), (((56, 72), (82, 72), (94, 26)), (90, 170, 90)),
                   (((34, 72), (66, 72), (50, 6)), (140, 90, 210))):
        a, b, tip = pts
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        curve = [a] + [(a[0] + (tip[0] - a[0]) * t + (mid[0] - a[0]) * 0.3 * math.sin(math.pi * t),
                        a[1] + (tip[1] - a[1]) * t) for t in (0.3, 0.6, 0.85)] + [tip] + \
                [(b[0] + (tip[0] - b[0]) * t, b[1] + (tip[1] - b[1]) * t) for t in (0.85, 0.6, 0.3)] + [b]
        p.poly(c, curve)
        p.circle((255, 214, 60), tip[0], tip[1], 6, o=2)                          # bells
    p.rect((255, 214, 60), 14, 68, 72, 18, radius=6)                             # the band
    for x in (26, 42, 58, 74):
        p.poly((220, 60, 70) if x % 32 == 26 % 32 else (140, 90, 210), [(x, 70), (x + 5, 77), (x, 84), (x - 5, 77)], o=0)


def _nose(p, day):
    skin = (250, 205, 165)
    p.circle(skin, 36, 52, 30)                                                   # a face ...
    for x in (28, 46):
        p.circle((255, 255, 255), x, 44, 6, o=2)
        pygame.draw.circle(p.s, LINE, p.P(x + 2, 44), p.R(3))
    pygame.draw.circle(p.s, (245, 150, 140), p.P(22, 60), p.R(5))
    pygame.draw.arc(p.s, LINE, pygame.Rect(*p.P(22, 58), p.R(22), p.R(14)), math.pi + 0.3, 2 * math.pi - 0.3, p.R(2.5))
    p.poly(skin, [(48, 50), (94, 52), (94, 56), (48, 60)])                       # ... with a nose that grew
    p.circle(skin, 93, 54, 3, o=2)
    for y in (40, 66):                                                           # still growing
        pygame.draw.line(p.s, (255, 255, 255), p.P(66, y), p.P(86, y), p.R(2.5))
    pygame.draw.rect(p.s, (120, 80, 50), pygame.Rect(*p.P(10, 18), p.R(52), p.R(10)), border_radius=p.R(4))   # hair
    pygame.draw.rect(p.s, LINE, pygame.Rect(*p.P(10, 18), p.R(52), p.R(10)), p.R(2), border_radius=p.R(4))


def _scales(p, day):
    gold = (235, 190, 80)
    p.rect(gold, 28, 84, 44, 8, radius=3)                                        # foot
    p.rect(gold, 47, 18, 6, 68, radius=2, o=2)                                   # post
    p.line(LINE, (12, 24), (88, 24), 7)
    p.line(gold, (12, 24), (88, 24), 3.5)                                         # beam
    p.circle(gold, 50, 16, 6, o=2)
    for cx in (16, 84):
        for dx in (-11, 11):
            pygame.draw.line(p.s, LINE, p.P(cx, 26), p.P(cx + dx, 60), p.R(1.6))
        bowl = [(cx - 14 + i * 28 / 12.0, 60 + math.sin(math.pi * i / 12.0) * 10) for i in range(13)]
        p.poly(gold, bowl, o=2)


def _pajamas(p, day):
    body = [(30, 14), (42, 12), (50, 30), (58, 12), (70, 14), (92, 30), (96, 64), (82, 66), (78, 44), (76, 92), (24, 92),
            (22, 44), (18, 66), (4, 64), (8, 30)]

    def stripes(q):
        q.s.fill((250, 250, 255))
        for x in range(0, 100, 12):
            pygame.draw.rect(q.s, (130, 175, 240), pygame.Rect(*q.P(x, 0), q.R(6), q.R(100)))
    _clipped(p, body, stripes)
    for pts in (((42, 12), (50, 30), (34, 26)), ((58, 12), (50, 30), (66, 26))):
        p.poly((255, 255, 255), pts, o=2)                                         # the collar
    for y in (42, 56, 70, 84):
        p.circle((240, 200, 80), 50, y, 3, o=1.5)                                 # buttons
    p.rect((130, 175, 240), 58, 40, 14, 12, radius=2, o=2)                        # pocket


def _rocket(p, day):
    for x, y in ((14, 18), (84, 30), (18, 70), (88, 76)):
        p.poly((255, 240, 150), _star_pts(x, y, 5, inner=0.4), o=1.2)
    p.poly((255, 160, 40), [(40, 74), (60, 74), (56, 86), (50, 98), (44, 86)], o=2)    # flame
    p.poly((255, 235, 140), [(44, 74), (56, 74), (50, 90)], o=0)
    for pts in (((36, 52), (22, 78), (38, 72)), ((64, 52), (78, 78), (62, 72))):
        p.poly((220, 60, 70), pts)                                                # fins
    p.poly((240, 242, 248), [(50, 4), (62, 22), (64, 74), (36, 74), (38, 22)])    # body
    p.poly((220, 60, 70), [(50, 4), (62, 22), (38, 22)], o=2)                     # nose cone
    p.circle((110, 180, 240), 50, 40, 8, o=2.5)                                   # window
    pygame.draw.circle(p.s, (210, 235, 255), p.P(47, 37), p.R(2.5))


def _boxers(p, day):
    legs = [(18, 28), (82, 28), (90, 84), (56, 86), (50, 60), (44, 86), (10, 84)]

    def hearts(q):
        q.s.fill((240, 120, 150))
        for x, y in ((28, 42), (62, 40), (40, 56), (74, 62), (22, 72), (62, 76)):
            pygame.draw.polygon(q.s, (255, 255, 255), [q.P(*v) for v in _heart_pts(x, y, 6)])
    _clipped(p, legs, hearts)
    p.rect((250, 250, 250), 16, 16, 68, 14, radius=3)                             # the waistband
    pygame.draw.line(p.s, LINE, p.P(50, 30), p.P(50, 46), p.R(2))


def _sock(p, day):
    sock = [(54, 8), (82, 8), (82, 56), (70, 78), (52, 90), (26, 92), (12, 84), (14, 70), (30, 64), (54, 54)]

    def stripes(q):
        for i, c in enumerate(((150, 100, 210), (255, 214, 60), (80, 190, 180)) * 6):
            pygame.draw.rect(q.s, c, pygame.Rect(*q.P(0, i * 9), q.R(100), q.R(9)))
    _clipped(p, sock, stripes)
    p.rect((250, 250, 250), 52, 6, 32, 10, radius=3)                              # the top
    p.ellipse((70, 60, 70), 22, 76, 9, 6, o=1.5)                                  # a hole in the toe
    _label(p, "?", 24, 30, 36, (255, 214, 60))                                    # where's the other one?


def _chicken(p, day):
    white, red, yellow = (250, 250, 250), (225, 50, 55), (255, 190, 40)
    for a, b in (((42, 76), (34, 92)), ((56, 76), (64, 92))):                     # legs, kicking out
        p.line(yellow, a, b, 3.5)
    p.poly(white, [(30, 50), (6, 24), (14, 54)])                                   # wings up: dancing
    p.poly(white, [(64, 50), (92, 30), (82, 60)])
    p.ellipse(white, 22, 44, 52, 38)                                               # body
    p.poly(white, [(24, 54), (10, 40), (12, 64)])                                  # tail
    p.circle(white, 56, 30, 12)                                                    # head
    for x, y in ((50, 17), (56, 15), (62, 17)):
        p.circle(red, x, y, 4, o=1.5)                                             # comb
    p.poly(yellow, [(66, 30), (76, 33), (66, 36)], o=1.5)                         # beak
    p.ellipse(red, 62, 36, 5, 9, o=1.2)                                           # wattle
    pygame.draw.circle(p.s, LINE, p.P(59, 27), p.R(2.4))
    for x, y in ((82, 10), (14, 84)):                                             # music notes
        p.circle(LINE, x, y + 8, 4, o=0)
        pygame.draw.line(p.s, LINE, p.P(x + 3.5, y + 8), p.P(x + 3.5, y - 6), p.R(2))
        pygame.draw.line(p.s, LINE, p.P(x + 3.5, y - 6), p.P(x + 10, y - 2), p.R(2))


def _planet(p, day):
    for x, y in ((12, 14), (86, 12), (90, 84), (10, 82), (70, 92)):
        p.poly((255, 240, 150), _star_pts(x, y, 5, inner=0.4), o=1.2)
    ring = pygame.Rect(*p.P(6, 40), p.R(88), p.R(24))
    pygame.draw.ellipse(p.s, LINE, ring.inflate(p.R(4), p.R(4)), p.R(9))
    pygame.draw.ellipse(p.s, (240, 200, 110), ring, p.R(5))
    p.circle((170, 130, 225), 50, 50, 26)                                          # the planet
    for y, c in ((40, (190, 155, 240)), (56, (150, 110, 205))):
        pygame.draw.line(p.s, c, p.P(30, y), p.P(70, y), p.R(4))
    front = p.s.subsurface(pygame.Rect(0, p.P(0, 52)[1], p.s.get_width(), p.s.get_height() - p.P(0, 52)[1]))
    r2 = ring.move(0, -p.P(0, 52)[1])                                              # the near half of the ring passes in front
    pygame.draw.ellipse(front, LINE, r2.inflate(p.R(4), p.R(4)), p.R(9))
    pygame.draw.ellipse(front, (240, 200, 110), r2, p.R(5))


def _pillow(p, day):
    p.rect((250, 250, 252), 10, 24, 80, 50, radius=18)                            # a plump pillow
    pygame.draw.circle(p.s, (200, 205, 220), p.P(50, 48), p.R(3))
    for a in (((24, 34), (40, 44)), ((76, 34), (60, 44)), ((24, 62), (40, 52)), ((76, 62), (60, 52))):
        pygame.draw.line(p.s, (215, 220, 232), p.P(*a[0]), p.P(*a[1]), p.R(1.8))
    p.ellipse((255, 214, 60), 46, 70, 34, 20)                                     # a rubber duck peeking out
    p.circle((255, 214, 60), 78, 66, 10)
    p.poly((255, 140, 40), [(86, 64), (96, 68), (86, 72)], o=1.5)
    pygame.draw.circle(p.s, LINE, p.P(80, 63), p.R(2.2))
    pygame.draw.ellipse(p.s, (255, 235, 140), pygame.Rect(*p.P(52, 74), p.R(14), p.R(6)))


DRAW = {"cake": _cake, "tree": _tree, "egg": _egg, "fireworks": _fireworks, "flag": _flag, "turkey": _turkey, "pumpkin": _pumpkin,
        "heart": _heart, "shamrock": _shamrock, "flower": _flower, "tie": _tie, "house": _house, "star": _star, "calendar": _calendar,
        "clock": _clock, "partyhat": _partyhat, "dove": _dove, "tophat": _tophat, "poppy": _poppy, "tools": _tools,
        "rocker": _rocker, "ship": _ship, "candle": _candle, "medal": _medal, "stocking": _stocking, "rings": _rings, "sweater": _sweater,
        "flagpole": _flagpole, "telegraph": _telegraph, "hammock": _hammock, "cat": _cat, "arrow": _arrow, "barrel": _barrel,
        "grouch": _grouch, "bone": _bone, "moon": _moon, "wreath": _wreath, "plane": _plane, "bulb": _bulb, "jester": _jester,
        "nose": _nose, "scales": _scales, "pajamas": _pajamas, "rocket": _rocket, "boxers": _boxers, "sock": _sock,
        "chicken": _chicken, "planet": _planet, "pillow": _pillow}
