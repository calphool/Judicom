"""The hidden keypad's screen (pygame).  What it does: judicom/keypad.py.

    keypad_view.show(surface, machine, keypad, faces)

  KEYPAD     "Dial a number" (or why a number was refused, in rose), the number as it is typed (312-555-0...), the twelve keys
             (* and # greyed: they only matter during a call), and "Delete"
  DIALING / CALLING   "Calling" and who (the name if the number is in the contacts file); the keys do nothing until answered
  ONGOING    "Speaking with" and who, in green; the keys send touch-tones down the line ("for menus")
"""
import pygame

from . import draw
from .call_view import PANEL, mix
from .config import AMBER, BG, DARK, GREEN, INK, ROSE, SOFT
from .config import SCREEN_W as W
from .keypad import LETTERS, pretty_number
from .machine import Mode

TOP = 52                         # below the bezel


def show(surf, machine, keypad, faces=None):
    surf.fill(BG)
    mode = machine.mode
    in_call, typing = mode in (Mode.DIALING, Mode.CALLING, Mode.ONGOING), mode == Mode.KEYPAD
    _heading(surf, machine, mode)
    for key, x, y, w, h, lit, enabled in keypad.keys(in_call, typing):
        rect = pygame.Rect(x, y, w, h)
        colour = AMBER if lit else PANEL if enabled else mix(PANEL, BG, 0.6)
        pygame.draw.rect(surf, colour, rect, border_radius=26)
        ink = DARK if enabled else mix(DARK, BG, 0.5)
        if key == "back":
            draw.centered(surf, draw.text("Delete", "bold", 44, ink), rect.centery - 26, rect.centerx)
            continue
        label = draw.text(key, "bold", 76, ink)
        letters = LETTERS.get(key, "")
        top = rect.centery - label.get_height() // 2 - (12 if letters else 0)
        draw.centered(surf, label, top, rect.centerx)
        if letters:
            draw.centered(surf, draw.text(letters, "reg", 26, ink), top + label.get_height() - 8, rect.centerx)


def _heading(surf, machine, mode):
    """The two lines above the keys: what is happening, and the number or who it is."""
    if mode == Mode.KEYPAD:
        if machine.notice:
            draw.block(surf, machine.notice, "bold", 40, ROSE, TOP, max_w=W - 60)
        else:
            draw.centered(surf, draw.text("Dial a number", "reg", 44, SOFT), TOP)
        if machine.digits:
            draw.centered(surf, draw.text(pretty_number(machine.digits), "bold", 76, INK, W - 40), TOP + 104)
        return
    party = machine.party
    who = party.label if party else ""
    if mode == Mode.ONGOING:
        draw.centered(surf, draw.text("Speaking with", "reg", 44, GREEN), TOP)
        draw.centered(surf, draw.text(who, "bold", 64, INK, W - 40), TOP + 62)
        draw.centered(surf, draw.text("The keys send tones (for menus)", "reg", 30, SOFT, W - 40), TOP + 146)
    else:
        draw.centered(surf, draw.text("Calling", "reg", 44, AMBER), TOP)
        draw.centered(surf, draw.text(who, "bold", 64, INK, W - 40), TOP + 62)
