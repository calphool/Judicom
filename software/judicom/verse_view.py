"""The verse screen (pygame): one verse on what looks like a page of an old Bible.

    draw_verse(surf, verse)          # verse: a verses.Verse

  - a cream page with aged edges on dark leather, a fine double rule round it, and a red ribbon marker over the top
  - the book's name across the top as a running head ("PSALMS"), with a thin rule under it
  - the words in EB Garamond (judicom/fonts), set flush left, with a red drop capital, LORD and GOD in small capitals the way the KJV
    prints them, and small red verse numbers where a passage goes on to the next verse
  - the reference at the foot, in italics between two small ornaments
The text size is chosen so that the whole passage fits: short verses large, long passages smaller.
"""
import re

import pygame

from .config import FONT_DIR
from .config import SCREEN_H as H
from .config import SCREEN_W as W

LEATHER, LEATHER_DARK = (70, 32, 28), (34, 14, 12)
PAGE, PAGE_EDGE = (246, 238, 216), (214, 196, 158)
INK, RED, BROWN = (44, 30, 22), (148, 30, 26), (112, 70, 44)
RIBBON, RIBBON_DARK = (158, 22, 34), (104, 10, 22)

PAGE_RECT = pygame.Rect(24, 34, W - 48, H - 60)
TEXT_LEFT, TEXT_RIGHT = PAGE_RECT.x + 54, PAGE_RECT.right - 54
TEXT_TOP, TEXT_BOTTOM = PAGE_RECT.y + 128, PAGE_RECT.bottom - 128

_fonts = {}


def font(size, italic=False):
    key = (int(size), italic)
    if key not in _fonts:
        path = FONT_DIR / ("EBGaramond-Italic.ttf" if italic else "EBGaramond.ttf")
        try:
            _fonts[key] = pygame.font.Font(str(path), int(size))
        except (OSError, pygame.error):
            _fonts[key] = pygame.font.Font(pygame.font.match_font("dejavuserif,liberationserif,freeserif", italic=italic), int(size))
    return _fonts[key]


def reset():
    _fonts.clear()


def running_head(book):
    book = {"Psalm": "Psalms"}.get(book, book)
    return book.upper()


# ------------------------------------------------------------------ setting the words -----------------------------------------
class Run:
    """A piece of a word in one font: 'L' + 'ORD' (smaller) make LORD in small capitals."""

    def __init__(self, text, size, color=INK, raise_by=0):
        self.text, self.size, self.color, self.raise_by = text, size, color, raise_by

    def width(self):
        return font(self.size).size(self.text)[0]


SMALL_CAPS = re.compile(r"^([\"“‘(]*)(LORD|GOD)(.*)$")


def word_runs(word, size):
    """One word -> its runs.  '[2]' is a verse number; LORD / GOD (also LORD's) are set in small capitals."""
    m = re.fullmatch(r"\[(\d+)\]", word)
    if m:
        return [Run(m.group(1), max(12, size * 0.5), RED, raise_by=int(size * 0.36))]
    m = SMALL_CAPS.match(word)
    if m:
        before, caps, after = m.groups()
        runs = [Run(before, size)] if before else []
        return runs + [Run(caps[0], size), Run(caps[1:], size * 0.76)] + ([Run(after, size)] if after else [])
    return [Run(word, size)]


def layout(words, size, width, cap_lines, cap_width):
    """Lines of (runs per word): greedy, with the first cap_lines lines shortened by the drop capital."""
    space = font(size).size(" ")[0]
    lines, line, used = [], [], 0
    for word in words:
        runs = word_runs(word, size)
        w = sum(r.width() for r in runs)
        room = width - (cap_width if len(lines) < cap_lines else 0)
        if line and used + space + w > room:
            lines.append(line)
            line, used = [], 0
        used += (space if line else 0) + w
        line.append((runs, w))
    if line:
        lines.append(line)
    return lines


def fit(verse):
    """The largest size (and its layout) at which the whole passage fits between the head and the foot."""
    words = []
    for number, text in verse.parts():
        if number:
            words.append("[%s]" % number)
        words += text.split()
    first = words[0]
    lead = re.match(r"^[\"“‘(]*", first).group(0)
    cap, rest = first[len(lead):][:1], first[len(lead) + 1:]
    words = ([lead + rest] if lead + rest else []) + words[1:]
    for size in range(50, 22, -2):
        line_h = int(size * 1.32)
        cap_size = int(line_h * 2 * 0.96)
        cap_w = font(cap_size).size(cap)[0] + int(size * 0.35)
        lines = layout(words, size, TEXT_RIGHT - TEXT_LEFT, 2, cap_w)
        if len(lines) < 2:
            lines = lines + [[]]
        if len(lines) * line_h <= TEXT_BOTTOM - TEXT_TOP:
            return size, line_h, cap, cap_size, cap_w, lines, words
    return size, line_h, cap, cap_size, cap_w, lines, words


# ------------------------------------------------------------------ the page ---------------------------------------------------
def _leather(surf):
    surf.fill(LEATHER)
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(40):                                              # darker towards the edges of the screen
        a = int(150 * (1 - i / 40.0) ** 2)
        pygame.draw.rect(shade, LEATHER_DARK + (a,), (i * 3, i * 3, W - 6 * i, H - 6 * i), 3)
    surf.blit(shade, (0, 0))


def _page(surf):
    shadow = pygame.Surface((PAGE_RECT.w + 24, PAGE_RECT.h + 24), pygame.SRCALPHA)
    for i in range(12):
        pygame.draw.rect(shadow, (0, 0, 0, 12), (i, i, shadow.get_width() - 2 * i, shadow.get_height() - 2 * i), border_radius=14)
    surf.blit(shadow, (PAGE_RECT.x - 6, PAGE_RECT.y - 2))
    pygame.draw.rect(surf, PAGE, PAGE_RECT, border_radius=6)
    age = pygame.Surface(PAGE_RECT.size, pygame.SRCALPHA)
    for i in range(26):                                              # the paper yellows towards its edges
        a = int(95 * (1 - i / 26.0) ** 2)
        pygame.draw.rect(age, PAGE_EDGE + (a,), (i, i, PAGE_RECT.w - 2 * i, PAGE_RECT.h - 2 * i), 2, border_radius=6)
    surf.blit(age, PAGE_RECT.topleft)
    outer, inner = PAGE_RECT.inflate(-36, -36), PAGE_RECT.inflate(-46, -46)
    pygame.draw.rect(surf, RED, outer, 2)
    pygame.draw.rect(surf, RED, inner, 1)


def _ribbon(surf):
    x, w, top, length = TEXT_RIGHT + 10, 28, PAGE_RECT.y - 10, 200            # in the right margin, clear of the words
    pts = [(x, top), (x + w, top), (x + w, top + length), (x + w // 2, top + length - 16), (x, top + length)]
    shadow = [(px + 3, py + 3) for px, py in pts]
    pygame.draw.polygon(surf, (90, 70, 50), shadow)
    pygame.draw.polygon(surf, RIBBON, pts)
    pygame.draw.line(surf, RIBBON_DARK, (x + 4, top), (x + 4, top + length - 4), 2)
    pygame.draw.line(surf, (190, 60, 70), (x + w - 7, top), (x + w - 7, top + length - 10), 1)


def _ornament(surf, cx, cy, color=BROWN):
    """A small diamond with dots: the printer's ornament either side of the reference."""
    pygame.draw.polygon(surf, color, [(cx, cy - 6), (cx + 6, cy), (cx, cy + 6), (cx - 6, cy)])
    for dx in (-12, 12):
        pygame.draw.circle(surf, color, (cx + dx, cy), 2)


def _spaced(text, size, color, italic=False):
    """Capitals set wide apart, as in a running head."""
    f = font(size, italic)
    imgs = [f.render(ch, True, color) for ch in text]
    gap = int(size * 0.22)
    out = pygame.Surface((sum(i.get_width() for i in imgs) + gap * (len(imgs) - 1), f.get_height()), pygame.SRCALPHA)
    x = 0
    for img in imgs:
        out.blit(img, (x, 0))
        x += img.get_width() + gap
    return out


def draw_verse(surf, verse):
    _leather(surf)
    _page(surf)
    # running head
    head = _spaced(running_head(verse.book), 26, BROWN)
    surf.blit(head, (W // 2 - head.get_width() // 2, PAGE_RECT.y + 52))
    rule_y = PAGE_RECT.y + 52 + head.get_height() + 6
    pygame.draw.line(surf, BROWN, (TEXT_LEFT, rule_y), (TEXT_RIGHT, rule_y), 1)
    # the words
    size, line_h, cap, cap_size, cap_w, lines, _ = fit(verse)
    height = len(lines) * line_h
    top = TEXT_TOP + max(0, (TEXT_BOTTOM - TEXT_TOP - height) // 2)
    base_f = font(size)
    cap_f = font(cap_size)
    cap_img = cap_f.render(cap, True, RED)
    baseline_2 = top + line_h + base_f.get_ascent()                   # the drop capital stands on the second line's baseline
    surf.blit(cap_img, (TEXT_LEFT - 2, baseline_2 - cap_f.get_ascent()))
    space = base_f.size(" ")[0]
    for i, line in enumerate(lines):
        if not line:
            continue
        left = TEXT_LEFT + (cap_w if i < 2 else 0)
        gap = space                                                  # flush left, even spacing: easier to read than a narrow
                                                                     # justified column (which would gape at this size)
        x = float(left)
        baseline = top + i * line_h + base_f.get_ascent()
        for runs, w in line:
            rx = x
            for r in runs:
                f = font(r.size)
                surf.blit(f.render(r.text, True, r.color), (int(rx), baseline - f.get_ascent() - r.raise_by))
                rx += r.width()
            x += w + gap
    # the reference
    ref = font(34, italic=True).render(verse.reference, True, BROWN)
    ry = PAGE_RECT.bottom - 98
    surf.blit(ref, (W // 2 - ref.get_width() // 2, ry))
    _ornament(surf, W // 2 - ref.get_width() // 2 - 30, ry + ref.get_height() // 2 + 2)
    _ornament(surf, W // 2 + ref.get_width() // 2 + 30, ry + ref.get_height() // 2 + 2)
    _ribbon(surf)
