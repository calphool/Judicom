"""Text drawing helpers shared by all screens (pygame)."""
import pygame

from .config import SCREEN_W as W

_font_paths = {}
_fonts = {}
_texts = {}


def reset():
    """Forget the cached fonts and texts.  Must be called when pygame is shut down: a font kept from before pygame.quit() crashes
    the program (segmentation fault) if pygame is started again and the font is used."""
    _font_paths.clear()
    _fonts.clear()
    _texts.clear()
    from . import joke_view                                  # its kept pictures were made with these fonts
    joke_view.reset()


def _find_fonts():
    if not _font_paths:
        pygame.font.init()
        _font_paths["bold"] = pygame.font.match_font("dejavusans,liberationsans,freesans,arial", bold=True)   # None -> built-in font
        _font_paths["reg"] = pygame.font.match_font("dejavusans,liberationsans,freesans,arial")


def get_font(kind, size):
    _find_fonts()
    key = (kind, int(size))
    if key not in _fonts:
        _fonts[key] = pygame.font.Font(_font_paths[kind], int(size))
    return _fonts[key]


def text(string, kind, size, color, max_w=None):
    """A rendered line of text (cached).  With max_w the size shrinks until it fits."""
    size = max(10, int(size))
    key = (string, kind, size, color, max_w)
    img = _texts.get(key)
    if img is None:
        img = get_font(kind, size).render(string, True, color)
        while max_w and img.get_width() > max_w and size > 12:
            size -= 2
            img = get_font(kind, size).render(string, True, color)
        if len(_texts) > 400:
            _texts.clear()
        _texts[key] = img
    return img


def wrap(string, kind, size, max_w):
    """Split a sentence into lines that fit max_w pixels."""
    font, lines, cur = get_font(kind, size), [], ""
    for word in string.split():
        trial = (cur + " " + word).strip()
        if cur and font.size(trial)[0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def block(surf, string, kind, size, color, y, max_w=W - 60, cx=W // 2, spacing=1.15):
    """Centred, word-wrapped text.  Returns the y below it."""
    for line in wrap(string, kind, size, max_w):
        img = text(line, kind, size, color)
        surf.blit(img, (cx - img.get_width() // 2, y))
        y += int(size * spacing)
    return y


def centered(surf, img, y, cx=W // 2):
    """Blit an image centred on cx.  Returns the y below it."""
    surf.blit(img, (cx - img.get_width() // 2, y))
    return y + img.get_height()
