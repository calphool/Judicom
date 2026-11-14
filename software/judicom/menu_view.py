"""Draws the hidden menu (judicom/menu.py) in the phone's own colours."""
import pygame

from . import draw
from .call_view import PANEL
from .config import BG, CARD, DARK, INK
from .menu import BACK, RIGHT

HEADING_Y = 70


def show(surf, menu):
    surf.fill(BG)
    draw.centered(surf, draw.text("What would you like?", "bold", 48, INK), HEADING_Y, (surf.get_width() - RIGHT) // 2)
    for label, x, y, w, h in menu.buttons():
        rect = pygame.Rect(x, y, w, h)
        back = label == BACK
        pygame.draw.rect(surf, CARD if back else PANEL, rect, border_radius=26)
        img = draw.text(label, "reg" if back else "bold", 38 if back else 64, INK if back else DARK, max_w=w - 48)
        draw.centered(surf, img, rect.centery - img.get_height() // 2, rect.centerx)
