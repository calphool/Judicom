"""The info screen and the night clock (pygame).  home.py decides when they show.  (The weather has a screen of its own:
weather_view.py.)

    draw_info(surf, now, upcoming_events)
    draw_night(surf, now)

THE INFO SCREEN   the day ("Tuesday"), the date, the time; a card "Coming up" with the next events (INFO_EVENTS of them, fewer if
                  long names leave no room), each with a little cartoon (event_icons.py: a cake for a birthday, a tree for
                  Christmas ...), its date and countdown:
                      [tree]  Christmas                       [house]  Visit from Amy
                              December 25  (52 days to go)             Sunday, November 8, 10:30 AM
                                                                       (5 days to go)
THE NIGHT CLOCK   black, with only the time and the date in dim grey.
"""
import pygame

from . import draw
from .event_icons import event_icon
from .config import AMBER, BG, CARD, INK, NIGHT_INK, NIGHT_SOFT, SOFT
from .config import SCREEN_H as H
from .config import SCREEN_W as W


ICON = 72                                    # the events' little pictures (pixels)


def clock_text(now):
    return "%d:%02d %s" % (now.hour % 12 or 12, now.minute, "AM" if now.hour < 12 else "PM")


def long_date(now):
    return "%s %d, %d" % (now.strftime("%B"), now.day, now.year)


# ------------------------------------------------------------------ the screens ----------------------------------------------
def draw_heading(surf, now):
    """The day, the date and the time at the top of the screen; returns where the cards below may start."""
    y = 26
    y = draw.centered(surf, draw.text(now.strftime("%A"), "bold", 86, INK, W - 40), y)
    y = draw.centered(surf, draw.text(long_date(now), "reg", 44, SOFT, W - 40), y)
    y = draw.centered(surf, draw.text(clock_text(now), "bold", 58, AMBER, W - 40), y + 6)
    return y + 18


def draw_info(surf, now, upcoming):
    surf.fill(BG)
    y = draw_heading(surf, now)
    ev = pygame.Rect(24, y, W - 48, H - 18 - y)
    pygame.draw.rect(surf, CARD, ev, border_radius=30)
    yy = draw.centered(surf, draw.text("Coming up", "bold", 38, AMBER), ev.y + 14) + 4
    if not upcoming:
        draw.centered(surf, draw.text("Nothing on the calendar", "reg", 36, SOFT), ev.centery - 18)
        return
    text_x = ev.x + 16 + ICON + 12                       # the words start right of the icons
    items = [_event_lines(u, ev.right - 18 - text_x) for u in upcoming]
    room = ev.bottom - 10 - yy
    heights = [sum(int(size * 1.15) for _, _, size, _ in lines) for lines in items]
    while len(items) > 1 and sum(heights) + 16 * (len(items) - 1) > room:
        items.pop()                                       # the furthest one away goes rather than squashing the rest
        heights.pop()
    gap = (room - sum(heights)) / float(len(items) + 1)
    y1 = yy + gap
    for u, lines, height in zip(upcoming, items, heights):
        yl = int(y1)
        icon = event_icon(u.title, ICON, u.date.day)
        surf.blit(icon, (ev.x + 16, yl + max(0, (min(height, 2 * ICON) - ICON) // 2)))    # level with the event's words
        for text, kind, size, color in lines:
            surf.blit(draw.text(text, kind, size, color, ev.right - 18 - text_x), (text_x, yl))
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


def _at_commas(text, kind, size, max_w):
    """Lines of text broken after its commas where it must be ("Sunday, November 8," / "10:30 AM"), so that a date is never
    split from its day number; a part still too long is word-wrapped."""
    font, lines = draw.get_font(kind, size), []
    for part in text.split(", "):
        joined = (lines[-1] + ", " + part) if lines else part
        if lines and font.size(joined)[0] <= max_w:
            lines[-1] = joined
        else:
            if lines:
                lines[-1] += ","
            lines.append(part)
    out = []
    for line in lines:
        out += draw.wrap(line, kind, size, max_w) if font.size(line)[0] > max_w else [line]
    return out


def _event_lines(u, max_w):
    """The lines of one event: its title (up to 3 lines), then when it is and the countdown (up to 2 lines)."""
    lines = [(t, "bold", 42, INK) for t in _wrapped(u.title, "bold", 42, max_w, 3)]
    if u.days <= 1:
        when = u.when.replace("Today", "Today!", 1) if u.days == 0 else u.when
        lines += [(t, "bold", 32, AMBER) for t in _wrapped(when, "bold", 32, max_w, 2)]
    else:
        both = "%s  (%s)" % (u.when, u.countdown)
        if draw.get_font("reg", 32).size(both)[0] <= max_w:
            lines.append((both, "reg", 32, SOFT))
        else:                                             # not on one line: the date, then the countdown whole beneath it
            lines += [(t, "reg", 32, SOFT) for t in _at_commas(u.when, "reg", 32, max_w)]
            lines.append(("(%s)" % u.countdown, "reg", 32, SOFT))
    return lines

def draw_night(surf, now):
    surf.fill((0, 0, 0))
    big = draw.text(clock_text(now), "bold", 150, NIGHT_INK, W - 60)
    small = draw.text("%s, %s %d" % (now.strftime("%A"), now.strftime("%B"), now.day), "reg", 46, NIGHT_SOFT, W - 60)
    y = (H - (big.get_height() + 10 + small.get_height())) // 2
    y = draw.centered(surf, big, y) + 10
    draw.centered(surf, small, y)
