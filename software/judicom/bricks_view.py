"""Draws Brick Breaker (judicom/bricks.py).

The canvas is CANVAS_W x CANVAS_H, half the screen each way, so display.present_small() doubles it exactly: crisp, square
pixels.  The game's 480 x 640 world is drawn on it at SCALE, so it shows 540 x 720 on the screen, undistorted, clear of the
bezel (which covers the top and the right edge of the screen).  SCALE is 9/16 so that the bricks' spacing (32 x 16) lands on
whole pixels (18 x 9) and every gap between them is the same.
"""
import pygame

from . import bricks as b
from . import game_art as art
from .config import SCREEN_H, SCREEN_W, SHELL_RIGHT, SHELL_TOP

CANVAS_W, CANVAS_H = SCREEN_W // 2, SCREEN_H // 2
SCALE = 9 / 16
LEFT = (CANVAS_W - SHELL_RIGHT // 2 - round(b.FIELD_W * SCALE)) // 2       # (with a wall line a pixel wide each side)
TOP = SHELL_TOP // 2 + (CANVAS_H - SHELL_TOP // 2 - round(b.FIELD_H * SCALE)) // 2

BLACK, WHITE, GREY, DIM = (0, 0, 0), (240, 240, 240), (110, 110, 110), (150, 150, 150)
BAND_COLOURS = ((230, 60, 60), (245, 140, 40), (240, 215, 60), (70, 200, 90))       # rows 1-2, 3-4, 5-6, 7-8


def sx(x):
    return LEFT + round(x * SCALE)


def sy(y):
    return TOP + round(y * SCALE)


class BrickView:
    def __init__(self):
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self.brick_w, self.brick_h = round(b.BRICK_W * SCALE), round(b.BRICK_H * SCALE)
        self._letters = {}

    def text(self, s, y, colour=WHITE, scale=2, x=None, right=False):
        """Pixel letters (game_art.FONT); centred across the field unless x is given."""
        s = s.upper()
        width = art.text_width(s, scale)
        if x is None:
            x = sx(b.FIELD_W / 2) - width // 2
            self.canvas.fill(BLACK, (x - 3, y - 3, width + 6, art.FONT_H * scale + 6))
        elif right:
            x -= width
        for i, ch in enumerate(s):
            key = (ch, colour, scale)
            if key not in self._letters:
                glyph = art.FONT.get(ch, art.FONT[" "])
                pic = pygame.Surface((art.FONT_W * scale, art.FONT_H * scale), pygame.SRCALPHA)
                for gy, row in enumerate(glyph):
                    for gx, c in enumerate(row):
                        if c == "#":
                            pic.fill(colour, (gx * scale, gy * scale, scale, scale))
                self._letters[key] = pic
            self.canvas.blit(self._letters[key], (x + i * (art.FONT_W + 1) * scale, y))

    def draw(self, game):
        c = self.canvas
        c.fill(BLACK)
        top, left, right = sy(b.TOP_WALL), sx(0), sx(b.FIELD_W)
        c.fill(GREY, (left - 1, top - 1, right - left + 2, 1))                   # the walls: top, left, right
        c.fill(GREY, (left - 1, top, 1, sy(b.FIELD_H) - top))
        c.fill(GREY, (right, top, 1, sy(b.FIELD_H) - top))
        self.text("SCORE %d" % game.score, sy(12), x=left + 2)
        self.text("HI %d" % game.best, sy(12), x=right - 2, right=True)
        for row in range(b.ROWS):
            colour = BAND_COLOURS[row // 2]
            for col in range(b.COLS):
                if game.bricks[row][col]:
                    x, y, _, _ = b.brick_rect(col, row)
                    c.fill(colour, (sx(x), sy(y), self.brick_w, self.brick_h))
        c.fill(WHITE, (sx(game.px), sy(b.PADDLE_Y), round(b.PADDLE_W * SCALE), round(b.PADDLE_H * SCALE)))
        if game.state in ("ready", "playing"):
            pygame.draw.circle(c, WHITE, (sx(game.ball.x), sy(game.ball.y)), max(2, round(b.BALL_R * SCALE)))
        for i in range(max(0, min(game.lives, 6))):
            c.fill(DIM, (left + 2 + i * 18, sy(b.FIELD_H) + 6, 14, 4))           # balls left, under the field
        self.text("LEVEL %d" % game.level, sy(b.FIELD_H) + 4, DIM, scale=1, x=right - 2, right=True)
        mid = sy(400)
        if game.state == "ready" and game.level == 1 and game.score == 0 and game.lives == b.LIVES:
            self.text("BOTH BUTTONS: LAUNCH", mid)
            self.text("LEFT OR RIGHT: MOVE", mid + 16, DIM, scale=1)
        elif game.state == "ready" and game.left == b.ROWS * b.COLS and game.level > 1:
            self.text("LEVEL %d" % game.level, mid, scale=3)
        elif game.state == "cleared":
            self.text("LEVEL %d CLEARED" % game.level, mid, scale=2)
        elif game.state == "over":
            self.text("GAME OVER", mid - 30, scale=4)
            self.text("SCORE %d" % game.score, mid + 2, scale=2)
            if game.score > game.best_at_start:
                self.text("A NEW HIGH SCORE!", mid + 20, (240, 215, 60), scale=1)
            if game.timer >= b.OVER_WAIT_STEPS:
                self.text("BOTH BUTTONS: PLAY AGAIN", mid + 36, DIM, scale=1)
                self.text("LIFT THE HANDSET TO STOP", mid + 46, DIM, scale=1)
        return c
