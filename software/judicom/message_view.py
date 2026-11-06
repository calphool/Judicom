"""The message screen: the sender's face at the top, and what they say in a speech bubble coming from it (judicom/messages.py).

    message_view.show(surface, message, faces, more)        # more: how many are waiting after this one

The letters are as big as will fit, so a short message is very big.  Someone with no picture gets their first letter in a circle.
"""
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


def show(surf, message, faces=None, more=0):
    surf.fill(BG)
    draw.centered(surf, draw.text(message.sender, "bold", 54, INK, max_w=W - 40), 18)
    show_face(surf, message.sender, faces)
    show_bubble(surf, message.text)
    hint = "Touch the screen for the next message" if more else "Touch the screen when you have read this"
    draw.centered(surf, draw.text(hint, "reg", 28, SOFT, max_w=W - 40), H - 66)
