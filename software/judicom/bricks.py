"""Brick Breaker, on the hidden menu (judicom/maintenance.py).

A paddle at the bottom, a ball, and 8 rows of 14 bricks at the top.  Keep the ball in play with the paddle and knock out every
brick; then a new wall, with a quicker ball.  Where the ball meets the paddle steers it: the middle sends it straight up, the
ends off to the side.

    Left button: paddle left.   Right button: paddle right.   Neither, or both: the paddle stays.
    Both buttons pressed together (a new press): launch the ball; after "game over", a new game.
    Lifting the handset ends it (and so does a call coming in).

The game's world is FIELD_W x FIELD_H (480 x 640); bricks_view.py draws it.  Time moves in fixed steps of TICK; within a step
the ball moves at most SUBSTEP pixels at a time, so it cannot pass through a brick however fast it goes.
No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

FIELD_W, FIELD_H = 480, 640
TICK = 1 / 60
MAX_STEPS = 6                   # at most this many steps for one update(): after a long pause it does not race to catch up
SUBSTEP = 2.0                   # the ball moves at most this far between collision checks

TOP_WALL = 40                   # the ball's ceiling: the score and lives are above it
COLS, ROWS = 14, 8
BRICK_W, BRICK_H, GAP_X, GAP_Y = 30, 12, 2, 4
WALL_TOP = 105                  # the top row's top
WALL_LEFT = (FIELD_W - (COLS * BRICK_W + (COLS - 1) * GAP_X)) // 2
WALL_BOTTOM = WALL_TOP + ROWS * BRICK_H + (ROWS - 1) * GAP_Y
POINTS = (7, 7, 5, 5, 3, 3, 1, 1)           # per row, top to bottom: red, orange, yellow, green bands

PADDLE_W, PADDLE_H, PADDLE_Y = 72, 12, 585
PADDLE_SPEED = 360.0            # pixels a second
MOVE_AFTER = 0.075              # one button held this long before the paddle moves: both pressed a little apart is a launch, not a nudge

BALL_R = 5
BALL_SPEED, BALL_MAX = 260.0, 520.0
LEVEL_SPEEDUP = 1.05            # each level's ball starts this much quicker ...
LEVEL_START_MAX = 380.0         # ... up to this
SPEEDUP_EVERY, SPEEDUP = 12, 1.08           # quicker by 8 % after every 12 bricks
OVER_THE_TOP = 1.10             # and by 10 % the first time in a level the ball gets above the wall
LAUNCH_ANGLE = 15.0             # degrees from straight up, alternately left and right
MAX_ANGLE = 60.0                # off the paddle's very end

LIVES = 3
LOST_STEPS = 60                 # the pause after a ball is lost
CLEARED_STEPS = 120             # "level cleared"
OVER_WAIT_STEPS = 60            # "game over" stays this long before both buttons start a new game ...
OVER_IDLE_STEPS = 30 * 60       # ... and the game closes itself after this long with no new game


class Ball:
    __slots__ = ("x", "y", "vx", "vy")

    def __init__(self, x, y, vx=0.0, vy=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy

    @property
    def speed(self):
        return math.hypot(self.vx, self.vy)

    def set_speed(self, speed):
        """The same direction, at this speed."""
        s = self.speed
        if s > 0:
            self.vx, self.vy = self.vx * speed / s, self.vy * speed / s


def brick_rect(col, row):
    return (WALL_LEFT + col * (BRICK_W + GAP_X), WALL_TOP + row * (BRICK_H + GAP_Y), BRICK_W, BRICK_H)


class BrickGame:
    """One game.  update(now, held) moves it on; the rest is read by bricks_view.py.  Sounds to play are collected in events
    (take_events()): "paddle", "wall", "brick0" .. "brick3" (by colour, top first), "lost", "level", "over".

    state: "ready" (the ball on the paddle), "playing", "lost" (a ball just lost), "cleared" (a level done), "over"."""

    def __init__(self, best=0, seed=None):
        self.rng = random.Random(seed)
        self.best = best
        self.events = []
        self._last, self._acc = None, 0.0
        self._both_before = True        # a press of both buttons counts only once they have been up: not one still held
        self.new_game()

    # ---- the game's course -------------------------------------------------------------------------------------------------

    def new_game(self):
        self.score, self.lives, self.level = 0, LIVES, 1
        self.best_at_start = self.best
        self.finished = False
        self._new_level()

    def _new_level(self):
        self.bricks = [[True] * COLS for _ in range(ROWS)]
        self.broken = 0                                 # bricks broken this level (the ball quickens every SPEEDUP_EVERY)
        self.over_the_top = False
        self.start_speed = min(LEVEL_START_MAX, BALL_SPEED * LEVEL_SPEEDUP ** (self.level - 1))
        self.speed = self.start_speed
        self.launch_side = 1
        self.px = (FIELD_W - PADDLE_W) / 2
        self._ready()

    def _ready(self):
        self.state, self.timer = "ready", 0
        self.ball = Ball(self.px + PADDLE_W / 2, PADDLE_Y - BALL_R - 1)
        self._one_held = 0.0

    @property
    def left(self):
        return sum(map(sum, self.bricks))

    def take_events(self):
        events, self.events = self.events, []
        return events

    def summary(self):
        return "%d points, level %d" % (self.score, self.level)

    # ---- time --------------------------------------------------------------------------------------------------------------

    def update(self, now, held):
        """Run the steps due since the last call.  held: the names of the buttons down now.  Returns the number of steps run."""
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
        held = set(held)
        both = {"left", "right"} <= held
        pressed = both and not self._both_before        # a new press of both
        self._both_before = both
        if self.state in ("ready", "playing"):
            self._paddle(held, both)
        if self.state == "ready":
            self.ball.x = self.px + PADDLE_W / 2
            if pressed:
                self._launch()
        elif self.state == "playing":
            self._move_ball()
        elif self.state == "lost":
            self.timer -= 1
            if self.timer <= 0:
                if self.lives > 0:
                    self._ready()
                else:
                    self.state, self.timer = "over", 0
                    self.events.append("over")
        elif self.state == "cleared":
            self.timer -= 1
            if self.timer <= 0:
                self.level += 1
                self._new_level()
        elif self.state == "over":
            self.timer += 1
            if pressed and self.timer >= OVER_WAIT_STEPS:
                self.new_game()
            elif self.timer >= OVER_IDLE_STEPS:
                self.finished = True

    def _paddle(self, held, both):
        one = held & {"left", "right"}
        if both or not one:
            self._one_held = 0.0
            return
        self._one_held += TICK
        if self._one_held < MOVE_AFTER:
            return
        step = PADDLE_SPEED * TICK * (-1 if "left" in one else 1)
        self.px = min(max(self.px + step, 0.0), FIELD_W - PADDLE_W)

    def _launch(self):
        a = math.radians(LAUNCH_ANGLE) * self.launch_side
        self.launch_side = -self.launch_side
        self.ball.vx, self.ball.vy = self.speed * math.sin(a), -self.speed * math.cos(a)
        self.state = "playing"
        self.events.append("paddle")

    # ---- the ball ----------------------------------------------------------------------------------------------------------

    def _move_ball(self):
        b = self.ball
        dist = b.speed * TICK
        n = max(1, math.ceil(dist / SUBSTEP))
        for _ in range(n):
            px, py = b.x, b.y
            b.x += b.vx * TICK / n
            b.y += b.vy * TICK / n
            self._walls(b)
            self._paddle_hit(b, py)
            if self._brick_hit(b, px, py) and self.left == 0:
                self.state, self.timer = "cleared", CLEARED_STEPS
                self.events.append("level")
                return
            if not self.over_the_top and b.y + BALL_R < WALL_TOP:
                self.over_the_top = True
                self._quicken(OVER_THE_TOP)
            if b.y - BALL_R > FIELD_H:                  # all of it below the bottom: lost
                self.lives -= 1
                self.state, self.timer = "lost", LOST_STEPS
                self.events.append("lost")
                return

    def _walls(self, b):
        if b.x - BALL_R < 0:
            b.x, b.vx = BALL_R, abs(b.vx)
            self.events.append("wall")
        elif b.x + BALL_R > FIELD_W:
            b.x, b.vx = FIELD_W - BALL_R, -abs(b.vx)
            self.events.append("wall")
        if b.y - BALL_R < TOP_WALL:
            b.y, b.vy = TOP_WALL + BALL_R, abs(b.vy)
            self.events.append("wall")

    def _paddle_hit(self, b, prev_y):
        """Off the paddle's top, only on the way down and only as the ball reaches it (not once it is past)."""
        if b.vy <= 0 or not (prev_y + BALL_R <= PADDLE_Y < b.y + BALL_R):
            return
        if b.x + BALL_R < self.px or b.x - BALL_R > self.px + PADDLE_W:
            return
        contact = max(-1.0, min(1.0, (b.x - (self.px + PADDLE_W / 2)) / (PADDLE_W / 2)))
        a = math.radians(contact * MAX_ANGLE)
        speed = b.speed
        b.vx, b.vy = speed * math.sin(a), -speed * math.cos(a)
        b.y = PADDLE_Y - BALL_R
        self.events.append("paddle")

    def _brick_hit(self, b, px, py):
        """The ball against the bricks near it: the one it is deepest into breaks, and the ball turns off that face.
        Returns True when a brick broke."""
        best = None
        c0 = int((b.x - BALL_R - WALL_LEFT) // (BRICK_W + GAP_X))
        c1 = int((b.x + BALL_R - WALL_LEFT) // (BRICK_W + GAP_X))
        r0 = int((b.y - BALL_R - WALL_TOP) // (BRICK_H + GAP_Y))
        r1 = int((b.y + BALL_R - WALL_TOP) // (BRICK_H + GAP_Y))
        for row in range(max(0, r0), min(ROWS - 1, r1) + 1):
            for col in range(max(0, c0), min(COLS - 1, c1) + 1):
                if not self.bricks[row][col]:
                    continue
                x, y, w, h = brick_rect(col, row)
                cx, cy = min(max(b.x, x), x + w), min(max(b.y, y), y + h)
                d2 = (b.x - cx) ** 2 + (b.y - cy) ** 2
                if d2 < BALL_R * BALL_R and (best is None or d2 < best[0]):
                    best = (d2, row, col, cx, cy)
        if best is None:
            return False
        _, row, col, cx, cy = best
        self.bricks[row][col] = False
        x, y, w, h = brick_rect(col, row)
        nx, ny = b.x - cx, b.y - cy
        if nx == 0 and ny == 0:                         # the centre got inside: judge by where it came from
            nx = (px < x) * -1 + (px > x + w) * 1
            ny = (py < y) * -1 + (py > y + h) * 1
            if nx == 0 and ny == 0:
                ny = -1 if b.vy > 0 else 1
        if abs(nx) > abs(ny):                           # a side
            if b.vx * nx < 0:
                b.vx = -b.vx
            b.x = x - BALL_R if nx < 0 else x + w + BALL_R
        elif abs(ny) > abs(nx):                         # the top or the bottom
            if b.vy * ny < 0:
                b.vy = -b.vy
            b.y = y - BALL_R if ny < 0 else y + h + BALL_R
        else:                                           # a corner, square on: back the way it came
            if b.vx * nx < 0:
                b.vx = -b.vx
            if b.vy * ny < 0:
                b.vy = -b.vy
            k = BALL_R / math.hypot(nx, ny)
            b.x, b.y = cx + nx * k, cy + ny * k
        self.score += POINTS[row]
        self.best = max(self.best, self.score)
        self.broken += 1
        self.events.append("brick%d" % (row // 2))
        if self.broken % SPEEDUP_EVERY == 0:
            self._quicken(SPEEDUP)
        return True

    def _quicken(self, factor):
        self.speed = min(BALL_MAX, self.speed * factor)
        self.ball.set_speed(self.speed)
