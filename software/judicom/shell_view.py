"""Draws the maintenance shell: bash's screen at the top, the touch keyboard (judicom/keyboard.py) under it."""
import pygame

from . import config, draw

CELL_W, CELL_H = 10, 19
FONT_SIZE = 16
LEFT, TOP = 0, 4
BLACK, TEXT = (0, 0, 0), (225, 225, 225)
KEY, KEY_ON, KEY_EDGE = (52, 56, 64), (120, 150, 210), (20, 22, 26)
MAX_GLYPHS = 1500

COLOURS = {"black": (0, 0, 0), "red": (224, 96, 96), "green": (112, 214, 144), "brown": (224, 196, 96), "blue": (120, 150, 240),
           "magenta": (214, 130, 214), "cyan": (110, 210, 220), "white": (235, 235, 235)}


def colour(name, default):
    """A pyte colour: "default", a name, or six hex digits."""
    if name in COLOURS:
        return COLOURS[name]
    try:
        return tuple(bytes.fromhex(name)) if len(name) == 6 else default
    except ValueError:
        return default


class ShellView:
    def __init__(self):
        path = pygame.font.match_font("dejavusansmono,liberationmono,freemono")
        self.font = pygame.font.Font(path, FONT_SIZE)
        self.glyphs = {}

    def glyph(self, char, fg):
        key = (char, fg)
        if key not in self.glyphs:
            if len(self.glyphs) >= MAX_GLYPHS:
                self.glyphs.clear()
            try:
                self.glyphs[key] = self.font.render(char, True, fg)
            except (pygame.error, ValueError, UnicodeError):           # a character the font cannot do
                self.glyphs[key] = self.font.render("?", True, fg)
        return self.glyphs[key]

    def cell(self, surface, x, y, cell, invert=False):
        fg, bg = colour(cell.fg, TEXT), colour(cell.bg, BLACK)
        if cell.reverse != invert:
            fg, bg = bg, fg
        px, py = LEFT + x * CELL_W, TOP + y * CELL_H
        if bg != BLACK:
            surface.fill(bg, (px, py, CELL_W, CELL_H))
        if cell.data.strip():
            surface.blit(self.glyph(cell.data, fg), (px, py))

    def draw(self, surface, shell, keyboard):
        surface.fill(BLACK)
        screen = shell.screen
        for y in range(screen.lines):
            for x, cell in screen.buffer[y].items():
                if x < screen.columns:
                    self.cell(surface, x, y, cell)
        cursor = screen.cursor
        if not cursor.hidden and cursor.y < screen.lines:
            x = min(cursor.x, screen.columns - 1)
            self.cell(surface, x, cursor.y, screen.buffer[cursor.y][x], invert=True)
            if not screen.buffer[cursor.y][x].data.strip():
                surface.fill(TEXT, (LEFT + x * CELL_W, TOP + cursor.y * CELL_H, CELL_W, CELL_H))
        shell.dirty = False
        for label, x, y, w, h, lit in keyboard.keys():
            pygame.draw.rect(surface, KEY_ON if lit else KEY, (x + 2, y + 2, w - 4, h - 4), border_radius=7)
            pygame.draw.rect(surface, KEY_EDGE, (x + 2, y + 2, w - 4, h - 4), width=1, border_radius=7)
            font = draw.get_font("reg", 28 if len(label) == 1 else 18)
            text = font.render("" if label == "Space" else label, True, TEXT)
            surface.blit(text, text.get_rect(center=(x + w // 2, y + h // 2)))
        keyboard.dirty = False
