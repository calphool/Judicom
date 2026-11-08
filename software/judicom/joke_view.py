"""The joke screen (pygame): the setup in big letters, the punchline under it once it is time, and a jester at the bottom.

    draw_joke(surf, joke, punchline)     # joke: a jokes.Joke; punchline: False until PUNCHLINE_SECONDS have gone by

The punchline's room is kept from the start, so nothing moves when it appears.  The text size is the largest that fits both halves.
The words stay clear of the bezel, which covers the top and the right-hand edge of the screen (config.SHELL_TOP, SHELL_RIGHT).
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
SIZES = range(64, 31, -4)
LINE = 1.18                                     # line height, times the text size


def fit(joke, width=RIGHT - LEFT, height=TEXT_BOTTOM - TEXT_TOP):
    """(size, setup lines, punchline lines, gap): the largest size at which both halves fit."""
    for size in SIZES:
        setup, punch = draw.wrap(joke.setup, "bold", size, width), draw.wrap(joke.punchline, "bold", size, width)
        gap = int(size * 0.9)
        if (len(setup) + len(punch)) * int(size * LINE) + gap <= height:
            return size, setup, punch, gap
    return size, setup, punch, gap


def _background(surf):
    for y in range(0, H, 4):
        f = y / float(H)
        surf.fill(tuple(int(a + (b - a) * f) for a, b in zip(TOP_SKY, BOTTOM_SKY)), (0, y, W, 4))


def _jester(surf, x, y, size):
    """A smiling jester: a three-pointed hat with bells, a round face and a ruffled collar."""
    from .event_icons import _Pen, _oval
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
        pygame.draw.arc(big, (40, 34, 36), pygame.Rect(*p.P(ex - 5, 55), p.R(10), p.R(8)), 0.2, math.pi - 0.2, p.R(2.2))
    p.circle((240, 140, 140), 37, 66, 3.6, o=0)                                           # rosy cheeks
    p.circle((240, 140, 140), 63, 66, 3.6, o=0)
    p.poly((190, 60, 70), [(40, 66), (60, 66), (57, 73), (50, 76), (43, 73)], o=2)          # a big smile
    surf.blit(pygame.transform.smoothscale(big, (size, size)), (x, y))


def draw_joke(surf, joke, punchline):
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
    _jester(surf, CX - JESTER // 2, H - JESTER - 24, JESTER)
