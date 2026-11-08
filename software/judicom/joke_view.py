"""The joke screen (pygame): the setup in big letters, the punchline under it once it is time, and a jester at the bottom who
laughs at it.

    draw_joke(surf, joke, punchline, laugh=None)
        joke       a jokes.Joke
        punchline  False until PUNCHLINE_SECONDS have gone by
        laugh      None, or how far into his laugh the jester is (seconds, 0 .. LAUGH_SECONDS): he bounces and rocks with his
                   mouth wide open, and "Ha!"s pop up beside him.  The screen (screens.JokeScreen) starts it LAUGH_DELAY_SECONDS
                   after the punchline, and redraws only LAUGH_FPS times a second while it lasts.

The punchline's room is kept from the start, so nothing moves when it appears.  The text size is the largest that fits both halves.
The words stay clear of the bezel, which covers the top and the right-hand edge of the screen (config.SHELL_TOP, SHELL_RIGHT).
Everything but the jester is drawn once and kept, so a laughing frame only puts the jester (and his "Ha!"s) on a copy of it.
"""
import math

import pygame

from . import config, draw
from .config import SCREEN_H as H
from .config import SCREEN_W as W

TOP_SKY, BOTTOM_SKY = (255, 238, 170), (255, 205, 120)
INK, PUNCH, SOFT = (54, 38, 30), (170, 40, 90), (150, 100, 60)
LEFT, RIGHT = 36, W - config.SHELL_RIGHT - 36
CX = (LEFT + RIGHT) // 2
TEXT_TOP, TEXT_BOTTOM = config.SHELL_TOP + 90, H - 300
JESTER = 240                                    # its square, at the bottom
JESTER_Y = H - JESTER - 24
SIZES = range(64, 31, -4)
LINE = 1.18                                     # line height, times the text size
BOUNCES_PER_SECOND, ROCKS_PER_SECOND = 3.0, 1.5
BOUNCE_PX, ROCK_DEGREES = 16, 9
HA_EVERY = 0.4                                  # a new "Ha!" this often, left and right in turn

_kept = {}                                      # what is drawn once: the page for a (joke, punchline), the two jester faces


def fit(joke, width=RIGHT - LEFT, height=TEXT_BOTTOM - TEXT_TOP):
    """(size, setup lines, punchline lines, gap): the largest size at which both halves fit."""
    for size in SIZES:
        setup, punch = draw.wrap(joke.setup, "bold", size, width), draw.wrap(joke.punchline, "bold", size, width)
        gap = int(size * 0.9)
        if (len(setup) + len(punch)) * int(size * LINE) + gap <= height:
            return size, setup, punch, gap
    return size, setup, punch, gap


def reset():
    """Forget what was kept (pygame shut down)."""
    _kept.clear()


def _background(surf):
    for y in range(0, H, 4):
        f = y / float(H)
        surf.fill(tuple(int(a + (b - a) * f) for a, b in zip(TOP_SKY, BOTTOM_SKY)), (0, y, W, 4))


def _page(joke, punchline):
    """The screen without the jester, drawn once for each joke and each half of it."""
    key = ("page", joke, punchline)
    if key not in _kept:
        for old in [k for k in _kept if k[0] == "page"]:
            del _kept[old]
        surf = pygame.Surface((W, H))
        _background(surf)
        draw.centered(surf, draw.text("Here's a joke!", "bold", 34, SOFT), config.SHELL_TOP + 22, CX)
        size, setup, punch, gap = fit(joke)
        step = int(size * LINE)
        block = (len(setup) + len(punch)) * step + gap
        y = TEXT_TOP + max(0, (TEXT_BOTTOM - TEXT_TOP - block) // 2)
        for line in setup:
            draw.centered(surf, draw.text(line, "bold", size, INK), y, CX)
            y += step
        y += gap
        if punchline:
            for line in punch:
                draw.centered(surf, draw.text(line, "bold", size, PUNCH), y, CX)
                y += step
        _kept[key] = surf
    return _kept[key]


def jester(size, laughing=False):
    """A jester's face (transparent, size x size): a three-pointed hat with bells, a ruffled collar, and a smile, or a wide-open
    laughing mouth."""
    key = ("jester", size, laughing)
    if key in _kept:
        return _kept[key]
    from .event_icons import LINE as OUTLINE, _Pen
    k = 4 * size / 100.0
    big = pygame.Surface((int(100 * k), int(100 * k)), pygame.SRCALPHA)
    p = _Pen(big, k)
    colours = ((210, 50, 60), (255, 214, 60), (120, 70, 190), (60, 160, 90))
    for i, cx in enumerate(range(22, 80, 11)):                                            # the ruffled collar
        p.circle(colours[i % 4], cx, 86, 8)
    p.circle((245, 210, 180), 50, 60, 21)                                                 # the face
    for side, colour in ((-1, (210, 50, 60)), (0, (120, 70, 190)), (1, (60, 160, 90))):  # the hat's three points
        tip = (50 + side * 36, 12 + abs(side) * 10)
        p.poly(colour, [(50 + side * 8 - 12, 44), tip, (50 + side * 8 + 12, 44)])
        p.circle((255, 214, 60), tip[0], tip[1], 5)                                      # its bell
    p.rect((255, 214, 60), 27, 39, 46, 9, radius=4)                                       # the band
    for ex in (42, 58):                                                                   # happy closed eyes
        if laughing:                                                                      # squeezed shut: ^ ^
            p.line(OUTLINE, (ex - 5, 58), (ex, 54), 2.4)
            p.line(OUTLINE, (ex, 54), (ex + 5, 58), 2.4)
        else:
            pygame.draw.arc(big, OUTLINE, pygame.Rect(*p.P(ex - 5, 55), p.R(10), p.R(8)), 0.2, math.pi - 0.2, p.R(2.2))
    p.circle((240, 140, 140), 37, 66, 3.6, o=0)                                           # rosy cheeks
    p.circle((240, 140, 140), 63, 66, 3.6, o=0)
    if laughing:                                                                          # the mouth wide open, a tongue in it
        mouth = [(38, 64), (62, 64), (60, 72), (55, 78), (50, 79), (45, 78), (40, 72)]
        p.poly((150, 40, 55), mouth, o=2)
        p.poly((235, 110, 120), [(43, 75), (50, 71), (57, 75), (55, 78), (50, 79), (45, 78)], o=0)
    else:
        p.poly((190, 60, 70), [(40, 66), (60, 66), (57, 73), (50, 76), (43, 73)], o=2)      # a big smile
    _kept[key] = pygame.transform.smoothscale(big, (size, size))
    return _kept[key]


def pose(t):
    """(how far up, how far over in degrees) the laughing jester is, t seconds into his laugh."""
    up = abs(math.sin(math.pi * BOUNCES_PER_SECOND * t)) * BOUNCE_PX
    return up, math.sin(2 * math.pi * ROCKS_PER_SECOND * t) * ROCK_DEGREES


def _has(surf, t):
    """The "Ha!"s: one starts every HA_EVERY seconds, left and right of him in turn, and rises and fades over two turns."""
    newest = int(t / HA_EVERY)
    for n in (newest - 1, newest):
        if n < 0:
            continue
        age = (t - n * HA_EVERY) / (2 * HA_EVERY)                                         # 0 .. 1
        img = draw.text("Ha!", "bold", 44, PUNCH).copy()
        img.set_alpha(int(255 * (1 - age)))
        side = -1 if n % 2 == 0 else 1
        x = CX + side * (JESTER // 2 + 40) - img.get_width() // 2
        surf.blit(img, (x, JESTER_Y + 70 - int(age * 50) + (n % 3) * 12))


def draw_joke(surf, joke, punchline, laugh=None):
    surf.blit(_page(joke, punchline), (0, 0))
    if laugh is None:
        surf.blit(jester(JESTER), (CX - JESTER // 2, JESTER_Y))
        return
    up, degrees = pose(laugh)
    face = pygame.transform.rotozoom(jester(JESTER, laughing=True), degrees, 1.0)
    surf.blit(face, (CX - face.get_width() // 2, JESTER_Y + JESTER // 2 - face.get_height() // 2 - int(up)))
    _has(surf, laugh)
