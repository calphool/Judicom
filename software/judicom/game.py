"""The hidden game, "Invaders" in the hidden menu (judicom/maintenance.py).

A formation of 55 raiders (5 rows of 11) marches from side to side, a step down at each edge, faster as fewer are left, and
shoots down at the turret at the bottom.  Four shelters between them wear away where they are hit.  Now and then a bonus ship
crosses the top.  Clearing a formation brings the next, lower and quicker; the game ends when the last turret is lost or a
raider gets down to the turret.

    Left button: move left.   Right button: move right.   Both together: fire (held: fire again as soon as the shot is gone).
    Lifting the handset ends the game (and so does a call coming in).  After "game over", both buttons start a new one.

Everything is on a small canvas of W x H pixels (game_view.py draws it; the display scales it up 3 times).  The game moves on
in fixed steps of TICK seconds, whatever the drawing does: update() runs as many steps as the time since the last call needs.
No pygame here: it runs (and is tested) anywhere.
"""
import random

from . import game_art as art

W, H = 200, 341                 # the canvas: 1/3 of the 600 x 1024 screen
TICK = 1 / 60                   # one step of the game
MAX_STEPS = 6                   # at most this many steps for one update() (after a long pause the game does not race to catch up)

FIELD_L, FIELD_R = 4, 192       # where things may be across (the screen's bezel covers a little of the right edge)
BONUS_Y = 34
FORMATION_Y = 56                # the top row of the first formation
FORMATION_DROP = 7              # each later formation starts this much lower ...
FORMATION_LOWEST = 6            # ... for this many formations, then stays there
COLS, ROWS = 11, 5
COL_STEP, ROW_STEP, CELL = 15, 14, 12
MARCH_DX, MARCH_DY = 2, 7       # a step across; the step down at an edge
SHELTER_Y = 256
TURRET_Y = 290                  # the turret's top
GROUND_Y = 302                  # the line under the turret
TOP = 28                        # the player's shot goes this high

LIVES = 3
EXTRA_LIFE_AT = 1500            # one extra turret at this score
TURRET_SPEED = 1.2              # pixels a step while a button is held
MOVE_AFTER = 5                  # one button must be held this many steps before the turret moves (both together = fire)
SHOT_SPEED = 5                  # the player's shot, pixels a step
POINTS = (30, 20, 20, 10, 10)   # per row, top to bottom
BONUS_POINTS = (50, 100, 150, 300)
BONUS_SPEED = 0.75
BONUS_EVERY = (1200, 1800)      # steps between bonus ships (20-30 s)
BONUS_MIN_LEFT = 8              # no bonus ship when fewer raiders are left

READY_STEPS, CLEARED_STEPS, DYING_STEPS = 120, 90, 100
BURST_STEPS = 16
OVER_WAIT_STEPS = 60            # "game over" stays this long before both buttons can start a new game ...
OVER_IDLE_STEPS = 30 * 60       # ... and the game closes itself after this long with no new game

ROW_ART = (art.RAIDER_TOP, art.RAIDER_MIDDLE, art.RAIDER_MIDDLE, art.RAIDER_LOW, art.RAIDER_LOW)
TURRET_W, TURRET_H = art.size(art.TURRET)
BONUS_W, BONUS_H = art.size(art.BONUS)


class Raider:
    __slots__ = ("col", "row", "alive", "w", "h", "dx")

    def __init__(self, col, row):
        self.col, self.row, self.alive = col, row, True
        self.w, self.h = art.size(ROW_ART[row][0])
        self.dx = (CELL - self.w) // 2                 # centred in its cell


class Shelter:
    """A shelter's pixels: mask[y][x] is 1 where it still stands."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.mask = art.barrier_mask()
        self.h, self.w = len(self.mask), len(self.mask[0])

    def solid(self, px, py):
        x, y = px - self.x, py - self.y
        return 0 <= y < self.h and 0 <= x < self.w and self.mask[y][x] == 1

    def blast(self, px, py, rng, radius=2):
        """Knock out the pixels around a hit, raggedly."""
        for y in range(py - radius - 1, py + radius + 2):
            for x in range(px - radius, px + radius + 1):
                d = abs(x - px) + abs(y - py)
                if d <= radius or (d == radius + 1 and rng.random() < 0.5):
                    self.clear(x, y)

    def clear(self, px, py):
        x, y = px - self.x, py - self.y
        if 0 <= y < self.h and 0 <= x < self.w:
            self.mask[y][x] = 0

    def clear_rect(self, x0, y0, w, h):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.clear(x, y)

    @property
    def left(self):
        return sum(map(sum, self.mask))


class Shot:
    __slots__ = ("x", "y", "kind", "speed")

    def __init__(self, x, y, kind, speed):
        self.x, self.y, self.kind, self.speed = x, y, kind, speed


class Game:
    """One game.  update(now, held) moves it on; the rest is read by game_view.py.  Sounds to play are collected in events
    (take_events()): "shoot", "hit", "die", "march0" .. "march3", "bonus_on", "bonus_off", "bonus_hit", "extra"."""

    def __init__(self, best=0, seed=None):
        self.rng = random.Random(seed)
        self.best = best
        self.events = []
        self._last, self._acc = None, 0.0
        self.new_game()

    # ---- the game's course -------------------------------------------------------------------------------------------------

    def new_game(self):
        self.score, self.lives, self.wave = 0, LIVES, 1
        self.best_at_start = self.best
        self.extra_given = False
        self.state, self.timer = "ready", READY_STEPS
        self.finished = False                           # the game is over and no one started another: close it
        self.invaded = False
        self._release_seen = False
        self._new_wave()

    def _new_wave(self):
        self.raiders = [Raider(c, r) for r in range(ROWS) for c in range(COLS)]
        width = (COLS - 1) * COL_STEP + CELL
        self.fx = FIELD_L + (FIELD_R - FIELD_L - width) // 2
        self.fy = FORMATION_Y + FORMATION_DROP * min(self.wave - 1, FORMATION_LOWEST)
        self.direction, self.frame, self.march_note = 1, 0, 0
        self.march_timer = self.march_interval()
        gap = (FIELD_R - FIELD_L) / 4
        self.shelters = [Shelter(int(FIELD_L + gap * i + (gap - 22) / 2), SHELTER_Y) for i in range(4)]
        self.shots = []                                 # the raiders' shots
        self.shot = None                                # the player's: one at a time
        self.bursts = []                                # [x, y, steps left]
        self.bonus = None                               # [x, direction, points]
        self.bonus_text = None                          # [x, points, steps left]: the points where the bonus ship was hit
        self.bonus_timer = self.rng.randint(*BONUS_EVERY)
        self.fire_timer = 60
        self._place_turret()

    def _place_turret(self):
        self.tx = float(FIELD_L + 10)
        self._one_held = 0

    @property
    def left(self):
        return sum(1 for r in self.raiders if r.alive)

    def march_interval(self):
        """Steps between two steps of the formation: fewer raiders, quicker; later formations quicker still."""
        quicker = max(0.55, 0.9 ** (self.wave - 1))
        return max(2, int(self.left * 0.85 * quicker) + 2)

    def raider_rect(self, r):
        return (self.fx + r.col * COL_STEP + r.dx, self.fy + r.row * ROW_STEP, r.w, r.h)

    def take_events(self):
        events, self.events = self.events, []
        return events

    def summary(self):
        return "%d points, wave %d%s" % (self.score, self.wave, ", a raider got down" if self.invaded else "")

    # ---- time --------------------------------------------------------------------------------------------------------------

    def update(self, now, held):
        """Run the steps due since the last call.  held: the names of the buttons down now ("left", "right").
        Returns the number of steps run (0: nothing changed)."""
        if self._last is None:
            self._last = now
        self._acc += max(0.0, now - self._last)
        self._last = now
        steps = 0
        while self._acc >= TICK and steps < MAX_STEPS:
            self.tick(held)
            self._acc -= TICK
            steps += 1
        if steps == MAX_STEPS:
            self._acc = 0.0
        return steps

    def tick(self, held=()):
        """One step of the game."""
        held = set(held)
        for b in self.bursts:
            b[2] -= 1
        self.bursts = [b for b in self.bursts if b[2] > 0]
        if self.bonus_text:
            self.bonus_text[2] -= 1
            if self.bonus_text[2] <= 0:
                self.bonus_text = None
        if self.state == "ready":
            self._controls(held, can_fire=False)
            self.timer -= 1
            if self.timer <= 0:
                self.state = "play"
        elif self.state == "play":
            self._controls(held, can_fire=True)
            self._move_shot()
            self._move_raider_shots()
            if self.state == "play":
                self._march()
                self._raiders_fire()
                self._move_bonus()
            if self.state == "play" and self.left == 0:
                self._end_wave()
        elif self.state == "dying":
            self.timer -= 1
            if self.timer <= 0:
                if self.lives <= 0:
                    self._game_over()
                else:
                    self.state = "play"
                    self._place_turret()
        elif self.state == "cleared":
            self.timer -= 1
            if self.timer <= 0:
                self.wave += 1
                self._new_wave()
                self.state, self.timer = "ready", READY_STEPS
        elif self.state == "over":
            self.timer += 1
            if not held:
                self._release_seen = True
            if self._release_seen and held >= {"left", "right"} and self.timer >= OVER_WAIT_STEPS:
                self.new_game()
            elif self.timer >= OVER_IDLE_STEPS:
                self.finished = True

    def _controls(self, held, can_fire):
        both = {"left", "right"} <= held
        if both:
            self._one_held = 0
            if can_fire and self.shot is None:
                self.shot = Shot(int(self.tx) + TURRET_W // 2, TURRET_Y - 4, 0, SHOT_SPEED)
                self.events.append("shoot")
            return
        if len(held & {"left", "right"}) == 1:
            self._one_held += 1
            if self._one_held > MOVE_AFTER:
                step = -TURRET_SPEED if "left" in held else TURRET_SPEED
                self.tx = min(max(self.tx + step, FIELD_L), FIELD_R - TURRET_W)
        else:
            self._one_held = 0

    # ---- the player's shot -------------------------------------------------------------------------------------------------

    def _move_shot(self):
        s = self.shot
        if s is None:
            return
        for _ in range(s.speed):                       # a pixel at a time: nothing is skipped over
            s.y -= 1
            if self._shot_hits(s):
                self.shot = None
                return
            if s.y < TOP:
                self.shot = None
                return

    def _shot_hits(self, s):
        """The player's shot (a line 4 high at s.x, s.y) against everything; True when it is used up."""
        if self.bonus is not None:
            bx = self.bonus[0]
            if bx <= s.x < bx + BONUS_W and BONUS_Y <= s.y < BONUS_Y + BONUS_H:
                points = self.bonus[2]
                self._add(points)
                self.bonus_text = [int(bx), points, 60]
                self.bonus = None
                self.events += ["bonus_off", "bonus_hit"]
                return True
        for r in self.raiders:
            if r.alive:
                x, y, w, h = self.raider_rect(r)
                if x <= s.x < x + w and y <= s.y < y + h:
                    r.alive = False
                    self.bursts.append([x + w // 2 - 5, y, BURST_STEPS])
                    self._add(POINTS[r.row])
                    self.events.append("hit")
                    return True
        for sh in self.shelters:
            for dy in range(4):
                if sh.solid(s.x, s.y + dy):
                    sh.blast(s.x, s.y + dy, self.rng)
                    return True
        for o in self.shots:
            if o.x <= s.x < o.x + art.SHOT_W and o.y <= s.y < o.y + art.SHOT_H:
                self.shots.remove(o)
                self.bursts.append([o.x - 4, o.y, 8])
                return True
        return False

    def _add(self, points):
        self.score += points
        if not self.extra_given and self.score >= EXTRA_LIFE_AT:
            self.extra_given = True
            self.lives += 1
            self.events.append("extra")
        if self.score > self.best:
            self.best = self.score

    # ---- the raiders -------------------------------------------------------------------------------------------------------

    def _march(self):
        self.march_timer -= 1
        if self.march_timer > 0:
            return
        self.march_timer = self.march_interval()
        alive = [r for r in self.raiders if r.alive]
        if not alive:
            return
        rects = [self.raider_rect(r) for r in alive]
        lo, hi = min(x for x, _, _, _ in rects), max(x + w for x, _, w, _ in rects)
        if (self.direction > 0 and hi + MARCH_DX > FIELD_R) or (self.direction < 0 and lo - MARCH_DX < FIELD_L):
            self.fy += MARCH_DY
            self.direction = -self.direction
        else:
            self.fx += MARCH_DX * self.direction
        self.frame ^= 1
        self.events.append("march%d" % self.march_note)
        self.march_note = (self.march_note + 1) % 4
        for r in alive:                                 # they wear the shelters away as they reach them
            x, y, w, h = self.raider_rect(r)
            for sh in self.shelters:
                if y + h > sh.y and y < sh.y + sh.h:
                    sh.clear_rect(x, y, w, h)
            if y + h > TURRET_Y:
                self.invaded = True
                self._lose(all_of_them=True)
                return

    def _raiders_fire(self):
        self.fire_timer -= 1
        most = min(3 + (self.wave - 1) // 2, 6)
        if self.fire_timer > 0 or len(self.shots) >= most:
            return
        base = max(18, 64 - 6 * (self.wave - 1))
        self.fire_timer = self.rng.randint(base // 2, base)
        lowest = {}                                     # each column's lowest raider: the one with a clear way down
        for r in self.raiders:
            if r.alive and (r.col not in lowest or r.row > lowest[r.col].row):
                lowest[r.col] = r
        if not lowest:
            return
        middle = self.tx + TURRET_W / 2
        if self.rng.random() < 0.4:                     # often the column over the turret
            r = min(lowest.values(), key=lambda r: abs(self.raider_rect(r)[0] + r.w / 2 - middle))
        else:
            r = lowest[self.rng.choice(sorted(lowest))]
        x, y, w, h = self.raider_rect(r)
        speed = 1.5 + 0.1 * min(self.wave - 1, 5)
        self.shots.append(Shot(x + w // 2 - 1, y + h, self.rng.randrange(len(art.SHOTS)), speed))

    def _move_raider_shots(self):
        keep = []
        for s in self.shots:
            gone = False
            old = int(s.y)
            s.y += s.speed
            for y in range(old + 1, int(s.y) + 1):     # a pixel at a time
                tip = y + art.SHOT_H - 1
                hit = next((sh for sh in self.shelters if sh.solid(s.x + 1, tip)), None)
                if hit is not None:
                    hit.blast(s.x + 1, tip, self.rng)
                    gone = True
                    break
                if (self.tx < s.x + art.SHOT_W and s.x < self.tx + TURRET_W and TURRET_Y < tip + 1 and y < TURRET_Y + TURRET_H):
                    gone = True
                    self._lose()
                    break
                if tip >= GROUND_Y:
                    gone = True
                    break
            if self.state != "play":
                return
            if not gone:
                keep.append(s)
        self.shots = keep

    def _lose(self, all_of_them=False):
        self.lives = 0 if all_of_them else self.lives - 1
        self.state, self.timer = "dying", DYING_STEPS
        self.shots, self.shot = [], None
        if self.bonus is not None:
            self.bonus = None
            self.events.append("bonus_off")
        self.events.append("die")

    # ---- the bonus ship ----------------------------------------------------------------------------------------------------

    def _move_bonus(self):
        if self.bonus is None:
            self.bonus_timer -= 1
            if self.bonus_timer <= 0:
                self.bonus_timer = self.rng.randint(*BONUS_EVERY)
                if self.left >= BONUS_MIN_LEFT:
                    d = self.rng.choice((-1, 1))
                    x = float(FIELD_L - BONUS_W) if d > 0 else float(FIELD_R)
                    self.bonus = [x, d, self.rng.choice(BONUS_POINTS)]
                    self.events.append("bonus_on")
            return
        self.bonus[0] += BONUS_SPEED * self.bonus[1]
        if self.bonus[0] > FIELD_R or self.bonus[0] < FIELD_L - BONUS_W:
            self.bonus = None
            self.events.append("bonus_off")

    # ---- between formations, and the end -----------------------------------------------------------------------------------

    def _end_wave(self):
        self.state, self.timer = "cleared", CLEARED_STEPS
        self.shots, self.shot = [], None
        if self.bonus is not None:
            self.bonus = None
            self.events.append("bonus_off")

    def _game_over(self):
        self.state, self.timer = "over", 0
        self._release_seen = False


def _invaders_view():
    from .game_view import GameView
    return GameView()


def _invaders_sounds():
    from .game_sound import invaders_sounds
    return invaders_sounds()


def read_best(path):
    try:
        return max(0, int(path.read_text().strip()))
    except (OSError, ValueError):
        return 0


class Session:
    """A game on the Judicom: the game, its sound (Sounds.game_on / game_play / game_off) and the high score kept in a file.
    maintenance.py makes one when the game is chosen on the hidden menu, calls step() every frame and close() at the end.

    Any game will do (Invaders, the default, or Brick Breaker: judicom/bricks.py) that has: update(now, held) -> steps run,
    take_events(), state ("over" when the game is over), score, best, finished, summary(); with make_view() giving its drawing
    (draw(game) -> a canvas for display.present_small) and make_sounds() its sounds ({event name: samples})."""

    def __init__(self, sounds, clock, log=None, best_file=None, seed=None, make_game=None, make_view=None, make_sounds=None):
        from . import config
        self.sounds, self.clock = sounds, clock
        self.log = log or (lambda msg: None)
        self.best_file = config.GAME_BEST_FILE if best_file is None else best_file
        self.make_view, self.make_sounds = make_view or _invaders_view, make_sounds or _invaders_sounds
        self.game = (make_game or Game)(best=read_best(self.best_file), seed=seed)
        self._sound_at = clock() + config.GAME_SOUND_AFTER
        self._sound = False
        self._sound_set = None                          # made in the background: it takes a second or two on the Pi
        import threading
        self.sound_maker = threading.Thread(target=self._make_sounds, name="game sounds", daemon=True)
        self.sound_maker.start()
        self._was = self.game.state
        self.steps = 0                                  # steps run by the last step(): 0 = nothing to draw again
        self._opened, self._frames = clock(), 0
        self._view = None

    def step(self, held):
        """One frame.  Returns False when the game wants to close (no new game after "game over")."""
        now = self.clock()
        self._frames += 1
        if not self._sound and now >= self._sound_at and self._sound_set is not None:
            self._sound = True
            self.sounds.game_on(self._sound_set)
            if hasattr(self.game, "loops"):             # loops it asked for before there was sound
                self.sounds.game_play([name + "_on" for name in self.game.loops()])
        self.steps = self.game.update(now, held)
        events = self.game.take_events()
        if self._sound:
            self.sounds.game_play(events)
        state = self.game.state
        if state != self._was:
            if state == "over":
                self.log("game over: %s" % self.game.summary())
                self._save_best()
            elif self._was == "over":
                self.log("game: a new game")
            self._was = state
        return not self.game.finished

    def _make_sounds(self):
        try:
            self._sound_set = self.make_sounds()
        except Exception as exc:                        # noqa: BLE001 - no sound is no reason to stop the game
            self.log("(no game sound: %s)" % exc)

    def _save_best(self):
        if self.game.best > read_best(self.best_file):
            try:
                self.best_file.write_text("%d\n" % self.game.best)
            except OSError as exc:
                self.log("(the game's high score cannot be kept: %s)" % exc)

    def draw(self):
        """The game's picture now (a W x H canvas, for display.present_small)."""
        if self._view is None:
            self._view = self.make_view()
        return self._view.draw(self.game)

    def present(self, display):
        """Show the game now: a game drawn in lines draws straight onto the screen (its view has present()); the others give
        a small canvas for display.present_small()."""
        if self._view is None:
            self._view = self.make_view()
        if hasattr(self._view, "present"):
            self._view.present(self.game, display)
        else:
            display.present_small(self._view.draw(self.game))

    def close(self):
        self._save_best()
        self.sounds.game_off()
        seconds = self.clock() - self._opened
        if seconds >= 1:
            self.log("game: %.0f s, %.1f frames a second" % (seconds, self._frames / seconds))
