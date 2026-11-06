"""The weather screen (pygame).  home.py decides when it shows: in the rotation with the info screen and the verse, and only
when there is a weather report.

    draw_weather(surf, now, report)

    Weather                                 the title, and the place in grey
    Oskaloosa
    +------------------------------------+
    | Today                              |  the weather now: picture, temperature, words, high and low, and the chance of
    |  [cloud]   48°                     |  rain or snow when it is worth saying (RAIN_FROM percent or more)
    |            Cloudy                  |
    |            High 54°   Low 45°      |
    +------------------------------------+
    | Tomorrow     [sun]      High 45°   |  the next days, "Tomorrow" and then their weekdays (not dates: easier to follow)
    | Sunny                   Low 36°    |
    | Saturday     [rain]     ...        |
    +------------------------------------+
"""
import math

import pygame

from . import draw
from .config import AMBER, BG, CARD, INK, SOFT, WEATHER_PLACE
from .config import SCREEN_W as W
from .config import SCREEN_H as H

RAIN_FROM = 30                # say "40% chance of rain" from this many percent


# ------------------------------------------------------------------ weather icons --------------------------------------------
SUN, CLOUD, RAIN, SNOW, BOLT, MOON = (255, 205, 60), (236, 240, 244), (110, 170, 240), (250, 250, 255), (255, 214, 10), (240, 236, 200)


def _sun(surf, x, y, r):
    for i in range(8):
        a = i * math.pi / 4
        pygame.draw.line(surf, SUN, (x + math.cos(a) * r * 1.35, y + math.sin(a) * r * 1.35),
                         (x + math.cos(a) * r * 1.8, y + math.sin(a) * r * 1.8), max(3, int(r * 0.16)))
    pygame.draw.circle(surf, SUN, (int(x), int(y)), int(r))


def _cloud(surf, x, y, s, color=CLOUD):
    for dx, dy, rad in ((-0.55, 0.1, 0.45), (-0.05, -0.2, 0.6), (0.5, 0.1, 0.45)):
        pygame.draw.circle(surf, color, (int(x + dx * s), int(y + dy * s)), int(rad * s))
    pygame.draw.rect(surf, color, (int(x - 0.55 * s), int(y + 0.1 * s), int(1.05 * s), int(0.45 * s)))


def draw_weather_icon(surf, kind, cx, cy, r):
    """sun moon partly cloud fog rain snow storm, centred at (cx, cy), about 2r across."""
    if kind == "sun":
        _sun(surf, cx, cy, r * 0.6)
    elif kind == "moon":
        pygame.draw.circle(surf, MOON, (int(cx), int(cy)), int(r * 0.6))
        pygame.draw.circle(surf, CARD, (int(cx + r * 0.3), int(cy - r * 0.2)), int(r * 0.5))
    elif kind == "partly":
        _sun(surf, cx - r * 0.3, cy - r * 0.3, r * 0.4)
        _cloud(surf, cx + r * 0.1, cy + r * 0.2, r * 0.9)
    elif kind == "fog":
        _cloud(surf, cx, cy - r * 0.25, r * 0.9, (200, 206, 212))
        for i, dy in enumerate((0.45, 0.7)):
            pygame.draw.line(surf, (200, 206, 212), (cx - r * (0.8 - 0.2 * i), cy + r * dy), (cx + r * (0.8 - 0.2 * i), cy + r * dy),
                             max(3, int(r * 0.1)))
    else:
        _cloud(surf, cx, cy - r * 0.2, r)
        if kind == "rain":
            for dx in (-0.5, 0.0, 0.5):
                pygame.draw.line(surf, RAIN, (cx + dx * r, cy + r * 0.65), (cx + dx * r - r * 0.12, cy + r * 0.95), max(3, int(r * 0.07)))
        elif kind == "snow":
            for dx in (-0.5, 0.0, 0.5):
                pygame.draw.circle(surf, SNOW, (int(cx + dx * r), int(cy + r * 0.8)), max(3, int(r * 0.09)))
        elif kind == "storm":
            pts = [(cx + r * 0.05, cy + r * 0.35), (cx - r * 0.2, cy + r * 0.75), (cx + r * 0.02, cy + r * 0.75), (cx - r * 0.12, cy + r * 1.1),
                   (cx + r * 0.3, cy + r * 0.62), (cx + r * 0.08, cy + r * 0.62), (cx + r * 0.25, cy + r * 0.35)]
            pygame.draw.polygon(surf, BOLT, pts)


# ------------------------------------------------------------------ the screen -----------------------------------------------
def rain_words(percent, icon):
    """'40% chance of snow', or '' when it is small (or not given)."""
    if percent is None or percent < RAIN_FROM:
        return ""
    return "%d%% chance of %s" % (percent, "snow" if icon == "snow" else "rain")


def day_name(date, today):
    return "Tomorrow" if (date - today).days == 1 else date.strftime("%A")


def draw_weather(surf, now, report):
    surf.fill(BG)
    y = draw.centered(surf, draw.text("Weather", "bold", 72, INK, W - 40), 22)
    y = draw.centered(surf, draw.text(WEATHER_PLACE, "reg", 38, SOFT, W - 40), y) + 16

    card = pygame.Rect(24, y, W - 48, 300)
    pygame.draw.rect(surf, CARD, card, border_radius=30)
    surf.blit(draw.text("Today", "bold", 40, AMBER), (card.x + 30, card.y + 16))
    draw_weather_icon(surf, report.icon, card.x + 130, card.y + 160, 74)
    tx, tw = card.x + 262, card.right - 262 - card.x - 16
    surf.blit(draw.text("%d°" % report.temp, "bold", 110, INK), (tx, card.y + 22))
    ty = card.y + 150
    for words, kind, size, color in ((report.text, "reg", 38, INK),
                                     ("High %d°   Low %d°" % (report.high, report.low), "reg", 32, SOFT),
                                     (rain_words(report.rain, report.icon), "reg", 32, SOFT)):
        if words:
            surf.blit(draw.text(words, kind, size, color, tw), (tx, ty))
            ty += int(size * 1.25)

    days = report.days
    if not days:
        return
    box = pygame.Rect(24, card.bottom + 18, W - 48, H - 18 - card.bottom - 18)
    pygame.draw.rect(surf, CARD, box, border_radius=30)
    row_h = (box.height - 20) / len(days)
    for i, d in enumerate(days):
        top = int(box.y + 10 + i * row_h)
        mid = int(top + row_h / 2)
        if i:
            pygame.draw.line(surf, BG, (box.x + 24, top), (box.right - 24, top), 2)
        name = draw.text(day_name(d.date, now.date()), "bold", 40, INK, 236)        # (Wednesday is the longest)
        words = rain_words(d.rain, d.icon) or d.text
        small = draw.text(words, "reg", 28, SOFT, 236)
        gy = mid - (name.get_height() + small.get_height()) // 2
        surf.blit(name, (box.x + 24, gy))
        surf.blit(small, (box.x + 24, gy + name.get_height()))
        draw_weather_icon(surf, d.icon, box.x + 310, mid - 6, 34)
        hi = draw.text("High %d°" % d.high, "bold", 36, INK, 172)
        lo = draw.text("Low %d°" % d.low, "reg", 32, SOFT, 172)
        hy = mid - (hi.get_height() + lo.get_height()) // 2
        surf.blit(hi, (box.right - 22 - hi.get_width(), hy))
        surf.blit(lo, (box.right - 22 - lo.get_width(), hy + hi.get_height()))
