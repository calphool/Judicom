"""The info screen and the night clock (pygame).  home.py decides when they show.

    draw_info(surf, now, weather_report_or_None, upcoming_events)
    draw_night(surf, now)

THE INFO SCREEN   the day ("Tuesday"), the date, the time; a card with the weather (icon, temperature, words, high and low; left out
                  when there is none); a card "Coming up" with the next events, each with its date and countdown:
                      Christmas                       Visit from Ann
                      December 25  (52 days to go)    Sunday, 10:30 AM  (5 days to go)
THE NIGHT CLOCK   black, with only the time and the date in dim grey.
"""
import math

import pygame

from . import draw
from .config import AMBER, BG, CARD, INK, NIGHT_INK, NIGHT_SOFT, SOFT, WEATHER_PLACE
from .config import SCREEN_H as H
from .config import SCREEN_W as W


def clock_text(now):
    return "%d:%02d %s" % (now.hour % 12 or 12, now.minute, "AM" if now.hour < 12 else "PM")


def long_date(now):
    return "%s %d, %d" % (now.strftime("%B"), now.day, now.year)


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


# ------------------------------------------------------------------ the screens ----------------------------------------------
def draw_info(surf, now, report, upcoming):
    surf.fill(BG)
    y = 26
    y = draw.centered(surf, draw.text(now.strftime("%A"), "bold", 86, INK, W - 40), y)
    y = draw.centered(surf, draw.text(long_date(now), "reg", 44, SOFT, W - 40), y)
    y = draw.centered(surf, draw.text(clock_text(now), "bold", 58, AMBER, W - 40), y + 6)
    y += 18
    if report is not None:
        card = pygame.Rect(24, y, W - 48, 204)
        pygame.draw.rect(surf, CARD, card, border_radius=30)
        draw_weather_icon(surf, report.icon, card.x + 125, card.centery + 6, 72)
        tx = card.x + 250
        surf.blit(draw.text("%d°" % report.temp, "bold", 96, INK), (tx, card.y + 8))
        surf.blit(draw.text(report.text, "reg", 36, INK, card.right - tx - 14), (tx, card.y + 118))
        surf.blit(draw.text("High %d°   Low %d°" % (report.high, report.low), "reg", 31, SOFT, card.right - tx - 14),
                  (tx, card.y + 160))
        surf.blit(draw.text(WEATHER_PLACE, "reg", 26, SOFT), (card.x + 30, card.y + 12))
        y = card.bottom + 18
    ev = pygame.Rect(24, y, W - 48, H - 18 - y)
    pygame.draw.rect(surf, CARD, ev, border_radius=30)
    yy = draw.centered(surf, draw.text("Coming up", "bold", 38, AMBER), ev.y + 14) + 4
    if not upcoming:
        draw.centered(surf, draw.text("Nothing on the calendar", "reg", 36, SOFT), ev.centery - 18)
        return
    items = [_event_lines(u, ev.width - 60) for u in upcoming]
    room = ev.bottom - 10 - yy
    heights = [sum(int(size * 1.15) for _, _, size, _ in lines) for lines in items]
    while len(items) > 1 and sum(heights) + 16 * (len(items) - 1) > room:
        items.pop()                                       # the furthest one away goes rather than squashing the rest
        heights.pop()
    gap = (room - sum(heights)) / float(len(items) + 1)
    y1 = yy + gap
    for lines, height in zip(items, heights):
        yl = int(y1)
        for text, kind, size, color in lines:
            surf.blit(draw.text(text, kind, size, color, ev.width - 60), (ev.x + 30, yl))
            yl += int(size * 1.15)
        y1 += height + gap


def _wrapped(text, kind, size, max_w, max_lines):
    """Up to max_lines lines of text; the last ends in '...' if the text was longer."""
    lines = draw.wrap(text, kind, size, max_w)
    if len(lines) <= max_lines:
        return lines
    last = lines[max_lines - 1]
    while last and draw.get_font(kind, size).size(last + "\u2026")[0] > max_w:
        last = last[:-1].rstrip()
    return lines[:max_lines - 1] + [last + "\u2026"]


def _event_lines(u, max_w):
    """The lines of one event: its title (up to 2 lines), then when it is and the countdown (up to 2 lines)."""
    lines = [(t, "bold", 42, INK) for t in _wrapped(u.title, "bold", 42, max_w, 2)]
    if u.days <= 1:
        when = u.when.replace("Today", "Today!", 1) if u.days == 0 else u.when
        lines += [(t, "bold", 32, AMBER) for t in _wrapped(when, "bold", 32, max_w, 2)]
    else:
        lines += [(t, "reg", 32, SOFT) for t in _wrapped("%s  (%s)" % (u.when, u.countdown), "reg", 32, max_w, 2)]
    return lines

def draw_night(surf, now):
    surf.fill((0, 0, 0))
    big = draw.text(clock_text(now), "bold", 150, NIGHT_INK, W - 60)
    small = draw.text("%s, %s %d" % (now.strftime("%A"), now.strftime("%B"), now.day), "reg", 46, NIGHT_SOFT, W - 60)
    y = (H - (big.get_height() + 10 + small.get_height())) // 2
    y = draw.centered(surf, big, y) + 10
    draw.centered(surf, small, y)
