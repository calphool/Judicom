"""Draws the hidden menu (judicom/menu.py) in the phone's own colours: a button for each choice, each game's with a little
picture of it on the left (ICONS, made from the game's own pictures), its name beside it."""
import math

import pygame

from . import draw
from .call_view import PANEL
from .config import BG, CARD, DARK, INK
from .menu import BACK, RIGHT

HEADING_Y = 70
BADGE = (16, 16, 24)                                 # the dark square each picture sits on
_icons = {}                                          # (label, size) -> picture, made once


def _pixels(rows, palette, k):
    """A picture from rows of characters (as the games' own), each pixel k x k."""
    s = pygame.Surface((len(rows[0]) * k, len(rows) * k), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                s.fill(palette[ch], (x * k, y * k, k, k))
    return s


def _shell(n):
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    green = (90, 230, 120)
    w = max(2, n // 18)
    pygame.draw.lines(s, green, False, [(n * 0.22, n * 0.32), (n * 0.42, n * 0.5), (n * 0.22, n * 0.68)], w)     # >
    s.fill(green, (int(n * 0.5), int(n * 0.64), int(n * 0.28), w))                                              # _
    return s


def _invaders(n):
    from .game_art import RAIDER_TOP
    from .game_view import ROW_COLOURS
    rows = RAIDER_TOP[0]
    return _pixels(rows, {"#": ROW_COLOURS[0]}, max(1, int(n * 0.75) // len(rows[0])))


def _bricks(n):
    from .bricks_view import BAND_COLOURS
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    bw, bh, gap = n // 5, max(3, n // 12), max(1, n // 40)
    for row, colour in enumerate(BAND_COLOURS):
        for col in range(4):
            s.fill(colour, (int(n * 0.1) + col * (bw + gap), int(n * 0.14) + row * (bh + gap), bw, bh))
    pygame.draw.circle(s, (240, 240, 240), (int(n * 0.58), int(n * 0.66)), max(2, n // 18))
    s.fill((240, 240, 240), (int(n * 0.3), int(n * 0.82), int(n * 0.4), max(3, n // 16)))
    return s


def _mars(n):
    from .mars_view import PALETTE, ROVER, WHEEL
    k = max(1, int(n * 0.85) // len(ROVER[0]))
    body, wheel = _pixels(ROVER, PALETTE, k), _pixels(WHEEL[0], PALETTE, k)
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    x, y = (n - body.get_width()) // 2, n // 2 - body.get_height() // 2
    s.blit(body, (x, y))
    for wx in (3, 12, 20):                           # the three wheels, as in the game
        s.blit(wheel, (x + (wx - 2) * k, y + body.get_height() - k))
    s.fill((255, 176, 96), (0, y + body.get_height() + 4 * k, n, max(2, k // 2)))          # the ground's bright line
    return s


def _meteoroids(n):
    from .meteor_view import CORE, GLOW, SHIP
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    k = n / 70

    def outline(points, angle, cx, cy, scale):
        a = math.radians(angle)
        c, si = math.cos(a) * scale, math.sin(a) * scale
        pts = [(cx + px * c - py * si, cy + px * si + py * c) for px, py in points]
        pygame.draw.lines(s, GLOW, True, pts, max(3, int(4 * k)))
        pygame.draw.lines(s, CORE, True, pts, max(1, int(2 * k)))
    rock = [(math.cos(a) * r, math.sin(a) * r) for a, r in
            zip((i * 2 * math.pi / 10 for i in range(10)), (1, .8, .95, .75, 1, .85, .7, .95, .8, .9))]
    outline(rock, 0, n * 0.66, n * 0.32, 15 * k)
    outline(SHIP, -120, n * 0.32, n * 0.66, 0.9 * k)
    return s


def _stronghold(n):
    from .meteor_view import GLOW
    from .stronghold_view import CORE_COLOUR, RING_COLOURS
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n / 2
    for (r, name, gap) in ((0.45, "outer", 40), (0.32, "middle", 160), (0.19, "inner", 280)):
        for k in range(6):                               # each ring in pieces, with one piece missing
            if k * 60 == (gap // 60) * 60:
                continue
            a0 = math.radians(k * 60 + gap % 60 + 4)
            pts = [(c + math.cos(a0 + math.radians(52) * i / 4) * r * n, c + math.sin(a0 + math.radians(52) * i / 4) * r * n)
                   for i in range(5)]
            pygame.draw.lines(s, GLOW, False, pts, max(3, n // 18))
            pygame.draw.lines(s, RING_COLOURS[name], False, pts, max(1, n // 40))
    hexagon = [(c + math.cos(math.radians(a)) * n * 0.08, c + math.sin(math.radians(a)) * n * 0.08) for a in range(0, 360, 60)]
    pygame.draw.lines(s, CORE_COLOUR, True, hexagon, max(1, n // 40))
    return s


def _lunica(n):
    from .lunica_view import COMMANDER, FIGHTER, PALETTE as LP
    k = max(2, int(n * 0.6) // len(COMMANDER[0][0]))
    boss, ship = _pixels(COMMANDER[0], LP, k), _pixels(FIGHTER[0], LP, k)
    boss = pygame.transform.rotate(boss, 180)          # (it faces down, at the fighter)
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    s.blit(boss, ((n - boss.get_width()) // 2, int(n * 0.06)))
    s.blit(ship, ((n - ship.get_width()) // 2, n - ship.get_height() - int(n * 0.04)))
    s.fill((255, 255, 170), (n // 2 - max(1, k // 2), int(n * 0.5), max(2, k), max(4, 3 * k)))     # a shot going up
    return s


ICONS = {"Shell": _shell, "Invaders": _invaders, "Brick Breaker": _bricks, "Mars Patrol": _mars, "Meteoroids": _meteoroids,
         "Stellar Stronghold": _stronghold, "Lunica": _lunica}


def icon(label, size):
    """The little picture for a menu button, size x size on its dark square; None for a choice without one."""
    if label not in ICONS:
        return None
    key = (label, size)
    if key not in _icons:
        badge = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(badge, BADGE, badge.get_rect(), border_radius=max(6, size // 7))
        pic = ICONS[label](int(size * 0.86))
        badge.blit(pic, ((size - pic.get_width()) // 2, (size - pic.get_height()) // 2))
        _icons[key] = badge
    return _icons[key]


def show(surf, menu):
    surf.fill(BG)
    draw.centered(surf, draw.text("What would you like?", "bold", 48, INK), HEADING_Y, (surf.get_width() - RIGHT) // 2)
    for label, x, y, w, h in menu.buttons():
        rect = pygame.Rect(x, y, w, h)
        back = label == BACK
        pygame.draw.rect(surf, CARD if back else PANEL, rect, border_radius=26)
        pic = None if back else icon(label, h - 20)
        if pic is None:
            img = draw.text(label, "reg" if back else "bold", 38 if back else 64, INK if back else DARK, max_w=w - 48)
            draw.centered(surf, img, rect.centery - img.get_height() // 2, rect.centerx)
            continue
        if w < h * 2.2:                                     # a button in two columns: the picture on top, the name under it
            img = draw.text(label, "bold", 30, DARK, max_w=w - 16)
            pic = icon(label, min(h - img.get_height() - 22, w - 40))
            surf.blit(pic, (rect.centerx - pic.get_width() // 2, y + 8))
            draw.centered(surf, img, y + h - 8 - img.get_height(), rect.centerx)
            continue
        surf.blit(pic, (x + 10, y + 10))
        left = x + 10 + pic.get_width() + 20                  # the name, beside the picture, in the room that is left
        img = draw.text(label, "bold", 56, DARK, max_w=x + w - 20 - left)
        surf.blit(img, (left + (x + w - 20 - left - img.get_width()) // 2, rect.centery - img.get_height() // 2))
