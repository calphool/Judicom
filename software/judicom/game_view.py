"""Draws the hidden game (judicom/game.py) on its small canvas, W x H; display.present_small() scales it up to the screen."""
import pygame

from . import game as g
from . import game_art as art

BLACK = (0, 0, 0)
WHITE = (235, 235, 235)
ROW_COLOURS = ((255, 120, 220), (120, 220, 255), (120, 220, 255), (200, 240, 90), (200, 240, 90))
TURRET_COLOUR = (90, 230, 120)
SHELTER_COLOUR = (255, 150, 60)
BONUS_COLOUR = (255, 80, 80)
SHOT_COLOUR = (255, 255, 160)
TEXT, DIM = (235, 235, 235), (150, 150, 150)


def picture(rows, colour):
    """A surface from rows of '#' and '.': lit pixels in colour, the rest transparent."""
    w, h = art.size(rows)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                s.set_at((x, y), colour)
    return s


class GameView:
    def __init__(self):
        self.canvas = pygame.Surface((g.W, g.H))
        self.raiders = [[picture(f, ROW_COLOURS[r]) for f in g.ROW_ART[r]] for r in range(g.ROWS)]
        self.turret = picture(art.TURRET, TURRET_COLOUR)
        self.turret_hit = [picture(f, TURRET_COLOUR) for f in art.TURRET_HIT]
        self.bonus = picture(art.BONUS, BONUS_COLOUR)
        self.burst = picture(art.BURST, WHITE)
        self.shots = [[picture(f, SHOT_COLOUR) for f in kind] for kind in art.SHOTS]
        self._letters = {}

    def letter(self, ch, colour):
        key = (ch, colour)
        if key not in self._letters:
            self._letters[key] = picture(art.FONT.get(ch, art.FONT[" "]), colour)
        return self._letters[key]

    def text(self, s, x, y, colour=TEXT, scale=1, centre=False, right=False):
        """centre: across the middle, on a black backing (so it reads over the raiders)."""
        s = s.upper()
        width = art.text_width(s, scale)
        if centre:
            x = (g.W - width) // 2
            self.canvas.fill(BLACK, (x - 3, y - 3, width + 6, art.FONT_H * scale + 6))
        elif right:
            x -= width
        for i, ch in enumerate(s):
            pic = self.letter(ch, colour)
            if scale != 1:
                pic = pygame.transform.scale(pic, (art.FONT_W * scale, art.FONT_H * scale))
            self.canvas.blit(pic, (x + i * (art.FONT_W + 1) * scale, y))

    def draw(self, game):
        c = self.canvas
        c.fill(BLACK)
        self.text("SCORE %05d" % game.score, g.FIELD_L + 2, 15)
        self.text("HI %05d" % game.best, g.FIELD_R - 2, 15, right=True)
        if game.bonus is not None:
            c.blit(self.bonus, (int(game.bonus[0]), g.BONUS_Y))
        if game.bonus_text:
            x, points, _ = game.bonus_text
            self.text(str(points), max(g.FIELD_L, min(x, g.FIELD_R - 16)), g.BONUS_Y + 1, BONUS_COLOUR)
        if game.state != "cleared":
            for r in game.raiders:
                if r.alive:
                    x, y, _, _ = game.raider_rect(r)
                    c.blit(self.raiders[r.row][game.frame], (x, y))
        for x, y, _ in game.bursts:
            c.blit(self.burst, (x, y))
        for sh in game.shelters:
            for y, row in enumerate(sh.mask):
                start = None
                for x, v in enumerate(row + [0]):
                    if v and start is None:
                        start = x
                    elif not v and start is not None:
                        c.fill(SHELTER_COLOUR, (sh.x + start, sh.y + y, x - start, 1))
                        start = None
        if game.shot is not None:
            c.fill(WHITE, (game.shot.x, game.shot.y, 1, 4))
        for s in game.shots:
            c.blit(self.shots[s.kind][(int(s.y) // 3) % 2], (s.x, int(s.y)))
        tx = int(game.tx)
        if game.state == "dying":
            c.blit(self.turret_hit[(game.timer // 6) % 2], (tx, g.TURRET_Y))
        elif game.state != "over":
            c.blit(self.turret, (tx, g.TURRET_Y))
        c.fill(TURRET_COLOUR, (g.FIELD_L, g.GROUND_Y, g.FIELD_R - g.FIELD_L, 1))
        for i in range(max(0, min(game.lives - 1, 6))):           # the turrets still to come
            c.blit(self.turret, (g.FIELD_L + 2 + i * 16, g.GROUND_Y + 6))
        self.text("WAVE %d" % game.wave, g.FIELD_R - 2, g.GROUND_Y + 6, DIM, right=True)
        if game.state == "ready":
            self.text("WAVE %d" % game.wave, 0, 160, scale=2, centre=True)
            if game.wave == 1 and game.score == 0:
                self.text("LEFT OR RIGHT BUTTON: MOVE", 0, 186, DIM, centre=True)
                self.text("BOTH BUTTONS: FIRE", 0, 196, DIM, centre=True)
        elif game.state == "cleared":
            self.text("WAVE %d CLEARED" % game.wave, 0, 160, scale=2, centre=True)
        elif game.state == "over":
            self.text("GAME OVER", 0, 140, scale=3, centre=True)
            self.text("SCORE %d" % game.score, 0, 170, scale=2, centre=True)
            if game.score > game.best_at_start:
                self.text("A NEW HIGH SCORE!", 0, 186, BONUS_COLOUR, centre=True)
            if game.timer >= g.OVER_WAIT_STEPS:
                self.text("BOTH BUTTONS: PLAY AGAIN", 0, 206, DIM, centre=True)
                self.text("LIFT THE HANDSET TO STOP", 0, 216, DIM, centre=True)
        return c
