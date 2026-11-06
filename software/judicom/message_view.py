"""The message screen: the sender's face at the top, and what they say in a speech bubble coming from it (judicom/messages.py).

    message_view.show(surface, message, faces, more)        # more: how many are waiting after this one
    level = message_view.pulse(seconds)                     # the words at the bottom breathe: when this changes,
    message_view.show_hint(surface, more, level)            # ... only they are drawn again

The letters are as big as will fit, so a short message is very big.  Someone with no picture gets their first letter in a circle.
"""
import math

import pygame

from . import draw
from .config import BG, INK, SOFT
from .config import SCREEN_H as H
from .config import SCREEN_W as W

PAPER = (253, 250, 240)
WORDS = (32, 40, 44)
FRAME = (232, 235, 238)
FACE = 300
FACE_TOP = 92
BUBBLE_X, BUBBLE_TOP, BUBBLE_BOTTOM = 26, 446, 930
BUBBLE_MIN = 190                   # a very short message still gets a proper bubble
TAIL = 44                          # the point of the bubble reaches this far up towards the face
PAD = 34
SIZES = range(68, 28, -2)          # the biggest letters first
SPACING = 1.22
TEXT_W = W - 2 * BUBBLE_X - 2 * PAD
HINT_Y = H - 62
HINT_TOP = BUBBLE_BOTTOM + 2       # the strip drawn again: below anything the bubble can reach
HINT_GLOW = (255, 226, 130)        # the words go from SOFT to this and back
HINT_BOB = 8                       # pixels they rise as they brighten: one for each level, so the steps cannot be seen
HINT_SECONDS = 2.4                 # slow enough to be calm; the screen is drawn 2 * HINT_BOB times in this


def fitted(text):
    """(size, lines): the biggest letters that fit in the bubble."""
    height = BUBBLE_BOTTOM - BUBBLE_TOP - 2 * PAD
    for size in SIZES:
        lines = draw.wrap(text, "bold", size, TEXT_W)
        widest = max(draw.get_font("bold", size).size(line)[0] for line in lines)
        if len(lines) * size * SPACING <= height and widest <= TEXT_W:
            break
    return size, lines


def show_face(surf, sender, faces):
    cx = W // 2
    picture = faces.get(sender, FACE) if faces else None
    if picture is None:
        pygame.draw.circle(surf, PAPER, (cx, FACE_TOP + FACE // 2), FACE // 2)
        draw.centered(surf, draw.text(sender[:1].upper(), "bold", 170, BG), FACE_TOP + 45)
        return
    pygame.draw.rect(surf, FRAME, (cx - FACE // 2 - 10, FACE_TOP - 10, FACE + 20, FACE + 20), border_radius=42)
    surf.blit(picture, (cx - FACE // 2, FACE_TOP))


def show_bubble(surf, text):
    cx = W // 2
    size, lines = fitted(text)
    line = int(size * SPACING)
    height = max(len(lines) * line + 2 * PAD, BUBBLE_MIN)
    pygame.draw.polygon(surf, PAPER, [(cx - 44, BUBBLE_TOP + 4), (cx + 44, BUBBLE_TOP + 4), (cx, BUBBLE_TOP - TAIL)])
    pygame.draw.rect(surf, PAPER, (BUBBLE_X, BUBBLE_TOP, W - 2 * BUBBLE_X, height), border_radius=38)
    y = BUBBLE_TOP + (height - len(lines) * line) // 2
    for words in lines:
        img = draw.text(words, "bold", size, WORDS, max_w=TEXT_W)           # max_w: a single very long word
        draw.centered(surf, img, y + (line - img.get_height()) // 2)
        y += line


def pulse(t):
    """Seconds -> how far through its breath the hint is: 0 (resting) to HINT_BOB (brightest)."""
    return round(HINT_BOB * (0.5 - 0.5 * math.cos(2 * math.pi * t / HINT_SECONDS)))


def show_hint(surf, more=0, level=0):
    words = "Touch the screen for the next message" if more else "Touch the screen when you have read this"
    color = tuple(a + (b - a) * level // HINT_BOB for a, b in zip(SOFT, HINT_GLOW))
    surf.fill(BG, (0, HINT_TOP, W, H - HINT_TOP))
    draw.centered(surf, draw.text(words, "reg", 28, color, max_w=W - 40), HINT_Y - level)


def show(surf, message, faces=None, more=0, level=0):
    surf.fill(BG)
    draw.centered(surf, draw.text(message.sender, "bold", 54, INK, max_w=W - 40), 18)
    show_face(surf, message.sender, faces)
    show_bubble(surf, message.text)
    show_hint(surf, more, level)
