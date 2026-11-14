"""Meteoroids, on the hidden menu (judicom/maintenance.py).

A small ship in a field of drifting rocks, in a world that wraps round at every edge.  Shoot the rocks (big ones split in two,
then in two again), keep clear of them, and of the enemy craft that come now and then and shoot back.  When the field is clear,
a new wave with more rocks.  The ship keeps drifting after its thruster stops: there is no friction in space.

    Left: turn left (counter-clockwise).   Right: turn right.
    Both, tapped (let go within half a second): fire.   Both, held half a second or more: thrust (never a shot as well).

The world is W x H (the whole visible screen, standing upright: the wrapping does not care about the shape), y down, angles
in degrees, 0 = right, clockwise positive (so up is -90).  The game runs in fixed steps of TICK (1/120 s).
No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

W, H = 580, 988
TICK = 1 / 120
MAX_STEPS = 12

TURN_SPEED = 240.0              # degrees a second
THRUST, MAX_SPEED = 220.0, 400.0
HOLD = 0.5                      # both held this long: thrust; let go sooner: fire
# (No shortest tap: the phone's button reading already ignores bounce, inputs.BUTTON_SETTLE.  A minimum here as well threw
# away real quick taps, where the two buttons are seen down together for only a frame or so.)
SHIP_R = 11                     # the ship's collision circle
SHOT_SPEED, SHOT_LIFE, SHOTS, SHOT_GAP = 500.0, 0.9, 4, 0.1

ROCK = {"large": (35, (25, 55), 20), "medium": (20, (45, 90), 50), "small": (10, (70, 140), 100)}   # radius, speeds, points
SPLIT = {"large": "medium", "medium": "small"}

LIVES, EXTRA_EVERY = 3, 10000
DESTROYED, SAFE_R, SHIELD = 1.5, 120, 2.0       # the pause after a lost ship; room needed in the middle; blinking safe time
WAVE_PAUSE = 1.0
CRAFT = {"big": (24, 90.0, 200), "small": (14, 140.0, 1000)}    # radius, speed, points
CRAFT_SHOT_SPEED, CRAFT_SHOT_LIFE = 260.0, 1.3
OVER_WAIT, OVER_IDLE, ATTRACT_IDLE = 1.0, 30.0, 60.0


def wrap(x, y):
    return x % W, y % H


def near(ax, ay, bx, by):
    """The shortest way from a to b across the wrapping world: (dx, dy)."""
    dx, dy = (bx - ax + W / 2) % W - W / 2, (by - ay + H / 2) % H - H / 2
    return dx, dy


def rock_shape(rng, r):
    """An irregular outline, 9 to 13 corners, each 68 to 100 % of r out: [(x, y)] round the middle."""
    n = rng.randint(9, 13)
    pts = []
    for i in range(n):
        a = 2 * math.pi * (i + rng.uniform(-0.35, 0.35)) / n
        d = r * rng.uniform(0.68, 1.0)
        pts.append((math.cos(a) * d, math.sin(a) * d))
    return pts


class Thing:
    _next = 0

    def __init__(self, kind, x, y, vx=0.0, vy=0.0, r=1.0):
        Thing._next += 1
        self.id, self.kind = Thing._next, kind
        self.x, self.y, self.vx, self.vy, self.r = x, y, vx, vy, r
        self.angle, self.spin, self.shape, self.size = 0.0, 0.0, None, ""
        self.life, self.t, self.alive = 0.0, 0.0, True
        self.next_turn = self.next_fire = 0.0           # (an enemy craft's)

    def move(self, dt):
        self.x, self.y = wrap(self.x + self.vx * dt, self.y + self.vy * dt)
        self.angle += self.spin * dt
        self.t += dt


class MeteorGame:
    """One game.  update(now, held) moves it on; the rest is read by meteor_view.py.  Sounds are collected in events
    (take_events()): "fire", "bang0" / "bang1" / "bang2" (a large / medium / small rock), "die", "craft_die", "craft_fire",
    "beat0" / "beat1" (the heartbeat), "extra", "wave", "over", and the loops "thrust_on" / "_off", "craft_on" / "_off".

    state: "attract" (the title, rocks drifting by), "playing", "destroyed", "over".
    input: "none", "left", "right", "pending" (both, under HOLD), "thrust" (both, held), "wait" (until both are let go)."""

    def __init__(self, best=0, seed=None, attract=True):
        self.rng = random.Random(seed)
        self.best = best
        self.events = []
        self._last, self._acc = None, 0.0
        self.clock, self._fired_at = 0.0, -1.0          # the game's own time (never set back: a new ship's own time is)
        self._both_before = True
        self.finished = False
        self.score = 0
        self.best_at_start = best
        self.state, self.timer = "attract", 0.0
        self.wave, self.lives = 0, LIVES
        self.input, self.both_time = "wait", 0.0
        self._reset_field()
        self._new_wave(demo=True)
        self.ship.angle = -90.0
        if not attract:
            self.new_game()

    # ---- the game's course -------------------------------------------------------------------------------------------------

    def _reset_field(self):
        self.ship = Thing("ship", W / 2, H / 2, r=SHIP_R)
        self.ship.angle = -90.0
        self.shield = 0.0
        self.rocks, self.shots, self.craft_shots, self.bits = [], [], [], []
        self.craft = None
        self.thrusting = False

    def new_game(self):
        self.state, self.timer = "playing", 0.0
        self.score, self.lives, self.wave = 0, LIVES, 0
        self.best_at_start = self.best
        self.next_extra = EXTRA_EVERY
        self.input = "wait"                             # the press that started the game is not a shot or a thrust
        self._reset_field()
        self._new_wave()

    def _new_wave(self, demo=False):
        self.wave += 1
        self.wave_timer = 0.0
        quick = min(1.5, 1 + 0.05 * (self.wave - 1))
        for _ in range(min(4 + self.wave - 1, 11)):
            while True:                                 # well away from the ship
                x, y = self.rng.uniform(0, W), self.rng.uniform(0, H)
                if math.hypot(*near(self.ship.x, self.ship.y, x, y)) > 220:
                    break
            self.rocks.append(self._rock("large", x, y, quick))
        self.craft_timer = max(8.0, 22.0 - 2.0 * self.wave) * self.rng.uniform(0.8, 1.2)
        self.beat_timer, self.beat = 1.0, 0
        if not demo:
            self.events.append("wave")

    def _rock(self, size, x, y, quick=None, heading=None):
        quick = quick if quick is not None else min(1.5, 1 + 0.05 * (self.wave - 1))
        r, (lo, hi), _ = ROCK[size]
        a = heading if heading is not None else self.rng.uniform(0, 2 * math.pi)
        v = self.rng.uniform(lo, hi) * quick
        t = Thing("rock", x, y, math.cos(a) * v, math.sin(a) * v, r)
        t.size, t.shape = size, rock_shape(self.rng, r)
        t.angle, t.spin = self.rng.uniform(0, 360), self.rng.uniform(-40, 40)
        return t

    def take_events(self):
        events, self.events = self.events, []
        return events

    def loops(self):
        return (["thrust"] if self.thrusting else []) + (["craft"] if self.craft else [])

    def summary(self):
        return "%d points, wave %d" % (self.score, self.wave)

    # ---- time --------------------------------------------------------------------------------------------------------------

    def update(self, now, held):
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
        held = set(held) & {"left", "right"}
        self.clock += TICK
        both = held == {"left", "right"}
        pressed, self._both_before = both and not self._both_before, both
        dt = TICK
        if self.state == "attract":
            self.timer += dt
            if pressed:
                self.new_game()
                return
            if self.timer >= ATTRACT_IDLE:
                self.finished = True
            self.ship.angle += 40 * dt                  # the demonstration: the ship turning slowly in the middle
            for r in self.rocks:
                r.move(dt)
            return
        if self.state == "over":
            self.timer += dt
            if pressed and self.timer >= OVER_WAIT:
                self.new_game()
            elif self.timer >= OVER_IDLE:
                self.finished = True
            self._world(dt, ship=False)
            return
        if self.state == "destroyed":
            self.timer -= dt
            self._world(dt, ship=False)
            if self.timer <= 0:
                if self.lives <= 0:
                    self.state, self.timer = "over", 0.0
                    self.events.append("over")
                elif self._clear_middle():              # back in the middle, when it is safe there
                    self.state = "playing"
                    self.ship = Thing("ship", W / 2, H / 2, r=SHIP_R)
                    self.ship.angle = -90.0
                    self.shield = SHIELD
                    self.input = "wait" if held else "none"
            return
        self._controls(held, both, dt)
        self._world(dt, ship=True)

    def _clear_middle(self):
        things = self.rocks + ([self.craft] if self.craft else []) + self.craft_shots
        return all(math.hypot(*near(W / 2, H / 2, t.x, t.y)) > SAFE_R + t.r for t in things)

    # ---- the two buttons ---------------------------------------------------------------------------------------------------

    def _controls(self, held, both, dt):
        """The two-button state machine (see the class's notes)."""
        s = self.input
        if s == "wait":
            if not held:
                self.input = "none"
            return
        if s == "pending":
            if not both:                                # let go in time: a shot, however brief the press was
                self._fire()
                self.input = self._single(held)
            else:
                self.both_time += dt
                if self.both_time >= HOLD:
                    self.input = "thrust"
                    self.thrusting = True
                    self.events.append("thrust_on")
            return
        if s == "thrust":
            if not both:                                # let go: the thrust stops, and no shot
                self.thrusting = False
                self.events.append("thrust_off")
                self.input = self._single(held)
            return
        if both:
            self.input, self.both_time = "pending", dt  # (this step counts)
            return
        self.input = self._single(held)
        if self.input == "left":
            self.ship.angle -= TURN_SPEED * dt
        elif self.input == "right":
            self.ship.angle += TURN_SPEED * dt

    @staticmethod
    def _single(held):
        return "left" if held == {"left"} else "right" if held == {"right"} else "none"

    def _fire(self):
        if len(self.shots) >= SHOTS or self.clock - self._fired_at < SHOT_GAP:
            return
        self._fired_at = self.clock
        s, a = self.ship, math.radians(self.ship.angle)
        shot = Thing("shot", s.x + math.cos(a) * 14, s.y + math.sin(a) * 14,
                     s.vx + math.cos(a) * SHOT_SPEED, s.vy + math.sin(a) * SHOT_SPEED, 1.5)
        shot.life = SHOT_LIFE
        self.shots.append(shot)
        self.events.append("fire")

    # ---- one step of the world ---------------------------------------------------------------------------------------------

    def _world(self, dt, ship):
        if ship:
            s = self.ship
            if self.thrusting:
                a = math.radians(s.angle)
                s.vx += math.cos(a) * THRUST * dt
                s.vy += math.sin(a) * THRUST * dt
                v = math.hypot(s.vx, s.vy)
                if v > MAX_SPEED:
                    s.vx, s.vy = s.vx * MAX_SPEED / v, s.vy * MAX_SPEED / v
            s.move(dt)
            self.shield = max(0.0, self.shield - dt)
        for r in self.rocks:
            r.move(dt)
        for b in self.bits:
            b.move(dt)
            b.life -= dt
        self.bits = [b for b in self.bits if b.life > 0]
        self._move_shots(self.shots, dt, mine=True)
        self._move_shots(self.craft_shots, dt, mine=False)
        self._craft(dt)
        if ship:
            self._ship_hits()
        if self.state == "playing":
            self._heartbeat(dt)
            if not self.rocks:
                self.wave_timer += dt
                if self.wave_timer >= WAVE_PAUSE:
                    self._new_wave()

    def _move_shots(self, shots, dt, mine):
        for s in list(shots):
            x0, y0 = s.x, s.y
            s.move(dt)
            s.life -= dt
            if s.life <= 0:
                shots.remove(s)
                continue
            if mine:
                hit = self._swept(x0, y0, s, self.rocks + ([self.craft] if self.craft else []))
                if hit is not None:
                    shots.remove(s)
                    if hit.kind == "rock":
                        self._break(hit, by_player=True)
                    else:
                        self._craft_down(by_player=True)
            else:
                hit = self._swept(x0, y0, s, self.rocks)
                if hit is not None:
                    shots.remove(s)
                    self._break(hit, by_player=False)

    def _swept(self, x0, y0, s, targets):
        """The first target the shot's path this step passes within reach of (so a quick shot cannot skip a small rock)."""
        mx, my = s.x - x0, s.y - y0
        if abs(mx) > W / 2 or abs(my) > H / 2:          # it wrapped this step: judge from where it is now
            mx, my = 0.0, 0.0
        for t in targets:
            dx, dy = near(s.x - mx, s.y - my, t.x, t.y)  # the target from where the shot started this step
            seg = mx * mx + my * my
            k = max(0.0, min(1.0, (dx * mx + dy * my) / seg)) if seg else 0.0
            if math.hypot(dx - mx * k, dy - my * k) <= t.r + s.r:
                return t
        return None

    def _break(self, rock, by_player):
        self.rocks.remove(rock)
        sizes = ("large", "medium", "small")
        self.events.append("bang%d" % sizes.index(rock.size))
        self._burst(rock.x, rock.y, 6 if rock.size == "large" else 4)
        if by_player:
            self._add(ROCK[rock.size][2])
        nxt = SPLIT.get(rock.size)
        if nxt:
            base = math.atan2(rock.vy, rock.vx)
            for turn in (-1, 1):                        # two pieces, going off different ways
                self.rocks.append(self._rock(nxt, rock.x, rock.y, heading=base + turn * self.rng.uniform(0.4, 1.2)))

    def _burst(self, x, y, n, speed=60.0):
        for _ in range(n):
            a, v = self.rng.uniform(0, 2 * math.pi), self.rng.uniform(0.4, 1.0) * speed
            b = Thing("bit", x, y, math.cos(a) * v, math.sin(a) * v)
            b.life = 0.45
            self.bits.append(b)

    def _add(self, points):
        self.score += points
        if self.score >= self.next_extra:
            self.next_extra += EXTRA_EVERY
            self.lives += 1
            self.events.append("extra")
        self.best = max(self.best, self.score)

    def _ship_hits(self):
        s = self.ship
        if self.shield > 0:
            return
        for t in self.rocks + ([self.craft] if self.craft else []) + self.craft_shots:
            if math.hypot(*near(s.x, s.y, t.x, t.y)) < SHIP_R + t.r:
                if t.kind == "rock":
                    self._break(t, by_player=True)       # (the rock it hit breaks, and counts)
                elif t.kind == "craft":
                    self._craft_down(by_player=True)
                else:
                    self.craft_shots.remove(t)
                return self._lost()

    def _lost(self):
        s = self.ship
        self.state, self.timer = "destroyed", DESTROYED
        self.lives -= 1
        if self.thrusting:
            self.thrusting = False
            self.events.append("thrust_off")
        self.events.append("die")
        self.wreck = (s.x, s.y, s.angle, s.vx * 0.3, s.vy * 0.3, [self.rng.uniform(0.6, 1.0) for _ in range(5)])
        self.wreck_t = 0.0

    def _heartbeat(self, dt):
        """Two low notes, by turns, quicker as the rocks get fewer."""
        self.beat_timer -= dt
        if self.beat_timer <= 0 and self.rocks:
            n = len(self.rocks)
            self.beat_timer = max(0.25, min(1.0, 0.25 + n * 0.05))
            self.events.append("beat%d" % self.beat)
            self.beat ^= 1

    # ---- the enemy craft ---------------------------------------------------------------------------------------------------

    def _craft(self, dt):
        if self.state == "destroyed" and self.craft is None:
            return
        if self.craft is None:
            if self.state != "playing":
                return
            self.craft_timer -= dt
            if self.craft_timer <= 0:
                small = self.rng.random() < min(0.8, 0.15 + 0.08 * self.wave + self.score / 40000)
                kind = "small" if small else "big"
                r, v, _ = CRAFT[kind]
                d = self.rng.choice((-1, 1))
                c = Thing("craft", -r if d > 0 else W + r, self.rng.uniform(0.15, 0.85) * H, d * v, 0.0, r)
                c.size, c.next_turn, c.next_fire = kind, self.rng.uniform(0.8, 2.0), 1.0
                self.craft = c
                self.events.append("craft_on")
            return
        c = self.craft
        c.x += c.vx * dt
        c.y = (c.y + c.vy * dt) % H
        c.t += dt
        c.next_turn -= dt
        if c.next_turn <= 0:                            # now and then up or down a while, or straight on
            c.vy = self.rng.choice((-1, 0, 1)) * abs(c.vx) * 0.6
            c.next_turn = self.rng.uniform(0.8, 2.0)
        if c.x < -c.r - 2 or c.x > W + c.r + 2:         # across and gone
            self._craft_gone()
            return
        c.next_fire -= dt
        if c.next_fire <= 0 and self.state == "playing":
            c.next_fire = max(0.6, 1.4 - 0.05 * self.wave)
            if c.size == "big":
                a = self.rng.uniform(0, 2 * math.pi)
            else:                                       # at the ship, leading it a little, surer in later waves
                dx, dy = near(c.x, c.y, self.ship.x, self.ship.y)
                t = math.hypot(dx, dy) / CRAFT_SHOT_SPEED
                a = math.atan2(dy + self.ship.vy * t * 0.5, dx + self.ship.vx * t * 0.5)
                a += self.rng.gauss(0, max(0.05, 0.35 - 0.03 * self.wave))
            shot = Thing("craft_shot", c.x, c.y, math.cos(a) * CRAFT_SHOT_SPEED, math.sin(a) * CRAFT_SHOT_SPEED, 2.0)
            shot.life = CRAFT_SHOT_LIFE
            self.craft_shots.append(shot)
            self.events.append("craft_fire")
        for r in self.rocks:                            # flying into a rock ends it, for no points
            if math.hypot(*near(c.x, c.y, r.x, r.y)) < c.r + r.r:
                self._break(r, by_player=False)
                self._craft_down(by_player=False)
                return

    def _craft_down(self, by_player):
        c = self.craft
        if by_player:
            self._add(CRAFT[c.size][2])
        self._burst(c.x, c.y, 8, speed=90)
        self.events.append("craft_die")
        self._craft_gone()

    def _craft_gone(self):
        self.craft = None
        self.events.append("craft_off")
        self.craft_timer = max(6.0, 20.0 - 1.5 * self.wave) * self.rng.uniform(0.8, 1.2)
