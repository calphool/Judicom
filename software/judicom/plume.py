"""Plume Knights, on the hidden menu (judicom/maintenance.py).

A knight on a great golden plume-bird, in an arena of floating rocks over a molten lake.  Flap to fly; meet a rider with
your lance higher than theirs and they are unhorsed, leaving an egg: pick it up before it hatches into a new rider.  Waves
of riders on drakes (novices, veterans, elites); later the lake's fire serpent rises at anyone flying low over it, and a
wave that goes on too long brings the raptor.  Every few waves a survival wave (a bonus for losing no knight) or an egg
wave (eggs everywhere: gather them before they hatch).

    Left held: face left and speed up that way.   Right held: the same, right.
    Both pressed together: one flap (press them together again for the next).

The world is W x H (y down).  A rider's x is its middle, its y its feet; its lance is LANCE_UP above its feet, so the lower y
is the higher lance.  Fixed steps of TICK.  No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

W, H = 580, 880
TICK = 1 / 120
MAX_STEPS = 12

GRAVITY, FLAP, MAX_UP, MAX_FALL = 650.0, 170.0, 300.0, 330.0
ACCEL, MAX_SPEED, DRAG, GROUND_DRAG = 600.0, 240.0, 1.8, 4.0
FLAP_GAP = 0.10                 # a flap within this long of the last one is ignored
TURN_AFTER = 0.12               # one button turns and drives the bird once held this long on its own (the other up): so
                                # both pressed a little apart, or one let go a little early after a flap, is no turn

BODY_HW, FIG_H = 18, 52         # a rider against the rocks: its middle +- BODY_HW, its feet up FIG_H
LANCE_UP, LANCE_REACH = 47, 30  # the lance: this far above the feet, its tip this far ahead of the middle
JOUST_TOL = 8                   # lances closer than this in height: nobody wins, both bounce
BOUNCE, PAIR_COOL = 160.0, 0.2

LAVA_Y = 846                    # the molten lake's surface (feet at or below it: gone)
GROUND_Y, GROUND_T = 812, 22
PLATFORM_T = 18
ROCKS = ((230, 350, 200),                      # (left, right, top): a small high rock,
         (0, 150, 340), (470, 580, 340),       # a ledge across the sides (the arena wraps round),
         (195, 395, 470),                      # one in the middle,
         (30, 190, 620), (390, 550, 640))      # and two lower down
SPAWNS = ((290, GROUND_Y), (295, 470), (110, 620), (470, 640), (75, 340))
START = (110, 620)
RESPAWNS = ((110, 620), (470, 640), (290, GROUND_Y))

LIVES, MAX_LIVES, EXTRA_EVERY = 5, 9, 20000
DYING, SHIELD = 1.5, 2.0
INTRO, FIRST_INTRO, CLEAR = 2.0, 3.0, 2.0
OVER_WAIT, OVER_IDLE, ATTRACT_IDLE = 1.0, 30.0, 60.0
SPAWN_GAP, SPAWN_TIME = 0.7, 1.0

EGG_HW, EGG_H, EGG_GRAVITY, INCUBATE = 9, 22, 500.0, 8.0
EGG_POINTS = (250, 500, 750, 1000)
HATCH_WAIT, MOUNT_SPEED = 1.5, 220.0
SURVIVAL_BONUS, EGG_WAVE_BONUS = 3000, 3000

GUARDIAN_FROM = 4               # the fire serpent: from this wave
GRAB_REACH, GRAB_RISE, PULL = 90, 0.3, 45.0      # it strikes at feet this near the lake; pulls down this fast
ESCAPE_FLAPS, ESCAPE_WINDOW, ESCAPE_KICK = 3, 1.2, 280.0
GRAB_COOL, MISS_COOL = 4.0, 1.5

RAPTOR_SPEED, RAPTOR_ACCEL, RAPTOR_CLIMB = 300.0, 520.0, 150.0
RAPTOR_HEAD, RAPTOR_BODY = (22, 16), (68, 24)    # boxes (w, h): the head ahead of its middle by RAPTOR_NECK
RAPTOR_NECK, RAPTOR_POINTS, RAPTOR_AGAIN = 40, 1000, 15.0

CLASSES = ("novice", "veteran", "elite")
SKILL = {   # top speed, acceleration, thinking every, flap gap, aggression, evasion, keeps above the player by, aim, slips
    "novice": dict(speed=150, accel=380, react=0.55, flap_gap=0.26, aggression=0.35, evade=0.10, above=(10, 50), aim=0.4,
                   slip=0.25, points=500),
    "veteran": dict(speed=190, accel=480, react=0.35, flap_gap=0.18, aggression=0.65, evade=0.30, above=(25, 60), aim=0.7,
                    slip=0.10, points=750),
    "elite": dict(speed=230, accel=600, react=0.20, flap_gap=0.13, aggression=0.85, evade=0.60, above=(30, 70), aim=0.9,
                  slip=0.03, points=1500),
}
WAVES = {1: (3, 0, 0), 2: (4, 0, 0), 3: (3, 2, 0), 4: (3, 3, 0), 5: (2, 3, 1), 6: (2, 4, 2), 7: (1, 4, 3)}


def wave_riders(wave):
    """(novices, veterans, elites) in a wave."""
    if wave in WAVES:
        return WAVES[wave]
    k = wave - 7
    elite = min(7, 3 + (k + 1) // 2)
    novice = 1 if k < 3 else 0
    return novice, 8 - elite - novice, elite


def is_egg_wave(wave):
    return wave >= 8 and (wave - 8) % 5 == 0


def is_survival(wave):
    return wave >= 3 and (wave - 3) % 4 == 0 and not is_egg_wave(wave)


def ground(wave):
    """The lake's shore for a wave: the stretch of low ground over it (it crumbles away as the waves go on)."""
    if wave <= 3:
        return [(40, 540)]
    if wave <= 6:
        return [(100, 480)]
    return [(150, 430)]


def raptor_after(wave):
    """Seconds into a wave before the raptor comes."""
    return max(25.0, 45.0 - 2.0 * (wave - 1))


def wrap_dx(a, b):
    """b - a the short way round."""
    d = (b - a) % W
    return d - W if d > W / 2 else d


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class Body:
    """Anything that falls and lands: x (middle), y (bottom), vx, vy."""

    def __init__(self, x, y):
        self.x, self.y, self.vx, self.vy = float(x), float(y), 0.0, 0.0
        self.grounded = False


class Rider(Body):
    def __init__(self, x, y, cls=None, face=1):
        super().__init__(x, y)
        self.cls, self.face = cls, face
        self.flap_age = 9.0                 # since its last flap (the wingbeat is drawn from this)
        self.run = 0.0                      # how far its legs have run (the running picture)
        self.state = "active"
        self.spawn_t = 0.0
        self.cool = 0.0                     # after a bounce: no second meeting with the knight yet
        self.ai, self.think, self.dir, self.ty = "PATROL", 0.0, face, y - 100
        self.flap_wait, self.slipping = 0.0, False

    def boxes(self, x=None):
        """Where it can be touched: the bird's body, the knight, the lance."""
        x = self.x if x is None else x
        y = self.y
        lance = (x + 4, y - LANCE_UP - 2, LANCE_REACH - 4, 5) if self.face > 0 else (x - LANCE_REACH, y - LANCE_UP - 2,
                                                                                       LANCE_REACH - 4, 5)
        return [(x - 20, y - 34, 40, 34), (x - 8, y - 56, 16, 22), lance]

    def lance_tip(self):
        return self.x + self.face * LANCE_REACH, self.y - LANCE_UP


class Egg(Body):
    def __init__(self, x, y, hatches, incubate=INCUBATE):
        super().__init__(x, y)
        self.hatches, self.incubate = hatches, incubate
        self.timer = None                   # seconds left, once it has come to rest
        self.bounced = False

    def box(self):
        return (self.x - EGG_HW, self.y - EGG_H, EGG_HW * 2, EGG_H)


class Hatchling:
    """A knight out of an egg, waiting on foot for a drake to come down for it."""

    def __init__(self, x, y, cls):
        self.x, self.y, self.cls = x, y, cls
        self.t = 0.0
        self.mount = None                   # [x, y, side] of the drake on its way

    def box(self):
        return (self.x - 8, self.y - 24, 16, 24)


class Raptor:
    def __init__(self, side, y):
        self.face = -side                   # comes in from that side, flying across
        self.x = W + 50.0 if side > 0 else -50.0
        self.y, self.vx, self.vy = float(y), self.face * RAPTOR_SPEED * 0.7, 0.0
        self.age = 0.0

    def head(self):
        w, h = RAPTOR_HEAD
        return (self.x + self.face * RAPTOR_NECK - w / 2, self.y - h / 2, w, h)

    def body(self):
        w, h = RAPTOR_BODY
        return (self.x - w / 2, self.y - h / 2, w, h)


class PlumeGame:
    """One game.  update(now, held) moves it on; the rest is read by plume_view.py.  Sounds are collected in events
    (take_events()): "flap", "land", "joust", "bounce", "die", "lava", "egg", "egg_lost", "hatch", "spawn", "grab",
    "escape", "raptor", "raptor_die", "start", "wave", "wave_done", "bonus", "extra", "over"; the loops "serpent_on/off",
    "raptor_loop_on/off".

    state: "attract", "intro" (WAVE n), "playing", "clear" (the wave done), "over".
    The knight (self.me, a Rider): self.knight is "ok", "grabbed" (held by the serpent), "dying" (back after DYING)."""

    def __init__(self, best=0, seed=None, attract=True):
        self.rng = random.Random(seed)
        self.best = self.best_at_start = best
        self.events = []
        self._last, self._acc = None, 0.0
        self.clock = 0.0
        self._both_before = True
        self._held_for = {"left": 0.0, "right": 0.0}
        self._flapped = -1.0
        self.finished = False
        self.score, self.lives, self.wave = 0, LIVES, 1
        self.next_extra = EXTRA_EVERY
        self.state, self.timer = "attract", 0.0
        self._loops = set()
        self._setup_wave()
        self._reset_knight(START)
        if not attract:
            self.new_game()

    # ---- the course of a game ------------------------------------------------------------------------------------------

    def new_game(self):
        self.score, self.lives, self.wave = 0, LIVES, 1
        self.best_at_start = self.best
        self.next_extra = EXTRA_EVERY
        self._begin_wave(first=True)

    def _begin_wave(self, first=False):
        self.state, self.timer = "intro", FIRST_INTRO if first else INTRO
        self.events.append("start" if first else "wave")
        self._setup_wave()
        self._reset_knight(START)

    def _setup_wave(self):
        w = self.wave
        self.plats = [(x0, x1, top, top + PLATFORM_T) for x0, x1, top in ROCKS]
        self.ground = ground(w)
        self.plats += [(x0, x1, GROUND_Y, GROUND_Y + GROUND_T) for x0, x1 in self.ground]
        self.egg_wave, self.survival = is_egg_wave(w), is_survival(w)
        self.enemies, self.eggs, self.hatchlings = [], [], []
        self.runaways, self.bursts, self.popups = [], [], []
        self.chain = 0
        self.lost_one = False
        self.wave_t = 0.0
        self.raptor, self.raptor_at = None, raptor_after(w)
        self.serpent = None                 # {"x", "t", "state": "rise" / "hold" / "sink", "flaps": [...]}
        self.serpent_cool = 0.0
        self.egg_total = 0
        self.hatched = 0
        self.bonus_won = 0
        self.queue = []
        if self.egg_wave:
            spots = []
            for x0, x1, top, _ in self.plats:
                n = 3 if x1 - x0 > 180 else 2
                spots += [(x0 + (x1 - x0) * (i + 1) / (n + 1), top) for i in range(n)]
            for x, top in spots:
                e = Egg(x, top, "novice", incubate=self.rng.uniform(7.0, 14.0))
                e.grounded, e.bounced = True, True
                e.timer = e.incubate
                self.eggs.append(e)
            self.egg_total = len(self.eggs)
        else:
            n, v, e = wave_riders(w)
            self.queue = ["novice"] * n + ["veteran"] * v + ["elite"] * e
        self.spawn_timer = 0.3
        self.spawn_index = self.rng.randrange(len(SPAWNS))

    def _reset_knight(self, at):
        self.me = Rider(at[0], at[1], face=1)
        self.me.grounded = True
        self.knight = "ok"
        self.knight_timer = 0.0
        self.shield = 0.0
        self.faller = None                  # [x, y, vy] of an unhorsed knight falling

    def take_events(self):
        events, self.events = self.events, []
        return events

    def loops(self):
        return sorted(self._loops)

    def _loop(self, name, on):
        if on and name not in self._loops:
            self._loops.add(name)
            self.events.append(name + "_on")
        elif not on and name in self._loops:
            self._loops.discard(name)
            self.events.append(name + "_off")

    def summary(self):
        return "%d points, wave %d" % (self.score, self.wave)

    # ---- time --------------------------------------------------------------------------------------------------------

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
        dt = TICK
        self.clock += dt
        both = held == {"left", "right"}
        pressed, self._both_before = both and not self._both_before, both
        for b in ("left", "right"):
            self._held_for[b] = self._held_for[b] + dt if held == {b} else 0.0       # (held alone)
        if self.state == "attract":
            self.timer += dt
            if pressed:
                self.new_game()
            elif self.timer >= ATTRACT_IDLE:
                self.finished = True
            return
        if self.state == "over":
            self.timer += dt
            self._effects(dt)
            if pressed and self.timer >= OVER_WAIT:
                self.new_game()
            elif self.timer >= OVER_IDLE:
                self.finished = True
            return
        if self.state in ("intro", "clear"):
            self.timer -= dt
            self._knight(held, pressed, dt)
            self._effects(dt)
            if self.timer <= 0:
                if self.state == "intro":
                    self.state = "playing"
                else:
                    self.wave += 1
                    self._begin_wave()
            return
        self.wave_t += dt
        self._knight(held, pressed, dt)
        self._spawning(dt)
        self._enemies(dt)
        self._jousts()
        self._eggs(dt)
        self._hatchlings(dt)
        self._serpent(dt)
        self._raptor(dt)
        self._effects(dt)
        self._wave_over()

    # ---- moving and landing ------------------------------------------------------------------------------------------

    def _offsets(self, x, hw):
        return (0, -W, W) if x - hw < 0 or x + hw > W else (0,)

    def _move(self, b, dt, hw, hh):
        """Moves b by its speed through the rocks: stopped (and turned back a little) by their sides, landing on their tops,
        bumping their undersides; round the sides of the arena.  Returns (landed, bumped)."""
        nx = b.x + b.vx * dt
        for x0, x1, top, bot in self.plats:
            if b.y > top + 0.5 and b.y - hh < bot:
                for off in self._offsets(nx, hw):
                    a0, a1 = x0 + off, x1 + off
                    if nx + hw > a0 and nx - hw < a1:
                        if b.vx > 0:
                            nx = a0 - hw - 0.01
                        elif b.vx < 0:
                            nx = a1 + hw + 0.01
                        b.vx = -b.vx * 0.4
        b.x = nx % W
        ny = b.y + b.vy * dt
        landed = bumped = False
        for x0, x1, top, bot in self.plats:
            for off in self._offsets(b.x, hw):
                if b.x + hw > x0 + off and b.x - hw < x1 + off:
                    if b.vy >= 0 and b.y <= top + 0.01 and ny >= top:
                        ny, b.vy, landed = top, 0.0, True
                    elif b.vy < 0 and b.y - hh >= bot - 0.01 and ny - hh < bot:
                        ny, b.vy, bumped = bot + hh, 0.0, True
        if ny - hh < 0:                                  # the sky's roof
            ny, b.vy = float(hh), max(b.vy, 0.0)
        b.y = ny
        b.grounded = landed
        return landed, bumped

    def over_lake(self, x):
        """Nothing between x and the lake (the shore is not under it)."""
        return not any(x0 - BODY_HW <= x <= x1 + BODY_HW for x0, x1 in self.ground)

    def _fly(self, r, direction, flap, dt, speed, accel, coast=False):
        """One step of a rider's flying: the same for the knight and the riders.  coast: both buttons held, the speed kept
        as it is (in the air)."""
        was = r.grounded
        if direction:
            r.face = direction
            r.vx = max(-speed, min(speed, r.vx + direction * accel * dt))
        elif coast and not r.grounded:
            pass
        else:
            r.vx *= math.exp(-(GROUND_DRAG if r.grounded else DRAG) * dt)
        if flap:
            r.vy = max(r.vy - FLAP, -MAX_UP)
            r.flap_age = 0.0
        r.flap_age += dt
        r.vy = min(r.vy + GRAVITY * dt, MAX_FALL)
        fall = r.vy
        landed, bumped = self._move(r, dt, BODY_HW, FIG_H)
        if r.grounded:
            r.run += abs(r.vx) * dt
        return landed and not was and fall > 120, bumped

    # ---- the knight --------------------------------------------------------------------------------------------------

    def _knight(self, held, pressed, dt):
        me = self.me
        if self.knight == "dying":
            self.knight_timer -= dt
            if self.faller:
                self.faller[2] = min(self.faller[2] + GRAVITY * dt, MAX_FALL)
                self.faller[1] += self.faller[2] * dt
            if self.knight_timer <= 0:
                if self.lives > 0:
                    self._reset_knight(self._safe_spot())
                    self.shield = SHIELD
                else:
                    self._game_over()
            return
        self.shield = max(0.0, self.shield - dt)
        flap = False
        if pressed and self.clock - self._flapped >= FLAP_GAP:
            flap = True
            self._flapped = self.clock
            self.events.append("flap")
        if self.knight == "grabbed":
            if flap:
                self.serpent["flaps"].append(self.clock)
                me.flap_age = 0.0
            return
        direction = 0
        coast = held == {"left", "right"}
        if coast:
            direction = 0
        elif self._held_for["left"] >= TURN_AFTER:
            direction = -1
        elif self._held_for["right"] >= TURN_AFTER:
            direction = 1
        thud, _ = self._fly(me, direction, flap, dt, MAX_SPEED, ACCEL, coast)
        if thud:
            self.events.append("land")
        if me.y >= LAVA_Y and self.state in ("playing", "intro", "clear"):
            self._lose_knight("lava")

    def _safe_spot(self):
        def room(spot):
            return min([math.hypot(wrap_dx(spot[0], e.x), spot[1] - e.y) for e in self.enemies] or [9999])
        return max(RESPAWNS, key=room)

    def _lose_knight(self, how):
        me = self.me
        self.knight, self.knight_timer = "dying", DYING
        self.lives -= 1
        self.chain = 0
        self.lost_one = True
        self.bursts.append([me.x, me.y - 26, 0.0, "lava" if how == "lava" else "knight"])
        self.faller = None if how == "lava" else [me.x, me.y - 40, -200.0]
        if how != "lava":                                # the bird, riderless, flees
            self.runaways.append([me.x, me.y, -me.face if me.vx * me.face < 0 else me.face, 0.0, "knight"])
        self.events.append("lava" if how == "lava" else "die")
        if self.serpent and self.serpent["state"] == "hold":
            self.serpent["state"], self.serpent["t"] = "sink", 0.0
            self._loop("serpent", False)

    def _game_over(self):
        self.state, self.timer = "over", 0.0
        self.knight = "gone"
        self.events.append("over")
        self._loop("serpent", False)
        self._loop("raptor_loop", False)

    # ---- the riders ----------------------------------------------------------------------------------------------------

    def _spawning(self, dt):
        if not self.queue:
            return
        self.spawn_timer -= dt
        if self.spawn_timer > 0:
            return
        self.spawn_timer = SPAWN_GAP
        cls = self.queue.pop(0)
        x, y = SPAWNS[self.spawn_index % len(SPAWNS)]
        self.spawn_index += 1
        self._add_rider(x, y, cls)

    def _add_rider(self, x, y, cls, spawning=True):
        e = Rider(x, y, cls, face=self.rng.choice((-1, 1)))
        e.grounded = True
        e.dir = e.face
        if spawning:
            e.state, e.spawn_t = "spawning", SPAWN_TIME
            self.events.append("spawn")
        e.think = self.rng.uniform(0.1, 0.4)
        self.enemies.append(e)
        return e

    def skill(self, e, name):
        s = SKILL[e.cls][name]
        if name in ("speed", "accel"):
            return s * (1 + 0.02 * min(self.wave - 1, 10))
        return s

    def _enemies(self, dt):
        for e in list(self.enemies):
            e.cool = max(0.0, e.cool - dt)
            if e.state == "spawning":
                e.spawn_t -= dt
                if e.spawn_t <= 0:
                    e.state = "active"
                continue
            e.think -= dt
            if e.think <= 0:
                self._decide(e)
                e.think = self.skill(e, "react") * self.rng.uniform(0.7, 1.3)
            e.flap_wait -= dt
            flap = False
            if not e.slipping and e.y > e.ty + 6 and e.vy > -120 and e.flap_wait <= 0:
                flap = True
                e.flap_wait = self.skill(e, "flap_gap") * self.rng.uniform(0.8, 1.2)
            _, bumped = self._fly(e, e.dir, flap, dt, self.skill(e, "speed"), self.skill(e, "accel"))
            if bumped and e.ty < e.y:
                e.think = min(e.think, 0.1)
            if e.y >= LAVA_Y:                            # into the lake: gone, no egg
                self.enemies.remove(e)
                self.bursts.append([e.x, LAVA_Y, 0.0, "lava"])
                self.events.append("lava")

    def _decide(self, e):
        """The rider's mind, a few times a second: what to do (e.ai) and so which way to go (e.dir) and how high (e.ty)."""
        rng, me = self.rng, self.me
        e.slipping = False
        if self.over_lake(e.x) and e.y > GROUND_Y - 60 or e.y > LAVA_Y - 60:
            e.ai = "RECOVER"
            e.ty = e.y - 200
            e.slipping = rng.random() < self.skill(e, "slip")           # (and sometimes it does not flap in time)
            return
        if e.y < FIG_H + 40:
            e.ai, e.ty = "RETURN_FROM_EDGE", 260
            return
        target = self.knight == "ok" and self.state == "playing"
        if not target:
            self._patrol(e)
            return
        dx, dy = wrap_dx(e.x, me.x), me.y - e.y          # dy > 0: the knight is lower (this rider's lance higher)
        toward = 1 if dx >= 0 else -1
        aim_err = rng.gauss(0, (1 - self.skill(e, "aim")) * 60)
        coming = me.vx * -toward > 40                    # the knight heading this way
        if dy < -JOUST_TOL and abs(dx) < 150 and coming and rng.random() < self.skill(e, "evade"):
            e.ai, e.dir, e.ty = "EVADE", -toward, me.y - 60
            if rng.random() < 0.5:
                e.dir = toward                           # (or straight up past it)
            return
        if rng.random() > self.skill(e, "aggression"):
            self._patrol(e)
            return
        lo, hi = self.skill(e, "above")
        if dy > 10 and abs(dx) < 200:
            e.ai, e.dir, e.ty = "ATTACK", toward, me.y - 12 + aim_err * 0.3
        elif abs(dx) > 250:
            e.ai, e.dir, e.ty = "PURSUE", toward, me.y - rng.uniform(lo, hi) + aim_err
        else:
            e.ai, e.ty = "CLIMB", me.y - rng.uniform(lo, hi) + aim_err
            if abs(dx) > 80:
                e.dir = toward
        e.ty = max(FIG_H + 30, min(GROUND_Y - 30, e.ty))

    def _patrol(self, e):
        rng = self.rng
        if e.ai != "PATROL" or rng.random() < 0.15:
            e.ty = rng.choice((170, 300, 430, 580, 740)) + rng.uniform(-30, 30)
            if rng.random() < 0.3:
                e.dir = -e.dir
        e.ai = "PATROL"

    # ---- jousting ----------------------------------------------------------------------------------------------------

    def _jousts(self):
        me = self.me
        if self.knight != "ok":
            return
        for e in list(self.enemies):
            if e.state != "active" or e.cool > 0:
                continue
            ex = me.x + wrap_dx(me.x, e.x)               # the rider where it is nearest the knight
            if not any(overlap(a, b) for a in me.boxes() for b in e.boxes(ex)):
                continue
            height = e.y - me.y                          # > 0: the knight's lance is higher
            if height >= JOUST_TOL:
                self._unhorse(e)
            elif height <= -JOUST_TOL and self.shield <= 0:
                self._lose_knight("joust")
                return
            else:
                side = 1 if ex < me.x else -1 if ex > me.x else -me.face
                me.vx, e.vx = side * BOUNCE, -side * BOUNCE
                e.dir = -side
                e.cool = PAIR_COOL
                self.events.append("bounce")

    def _unhorse(self, e):
        self.enemies.remove(e)
        points = SKILL[e.cls]["points"]
        self._add(points, e.x, e.y - 60)
        self.bursts.append([e.x, e.y - LANCE_UP, 0.0, "joust"])
        self.events.append("joust")
        egg = Egg(e.x, e.y - 20, CLASSES[min(2, CLASSES.index(e.cls) + 1)])
        egg.vx, egg.vy = e.vx * 0.5, min(e.vy, 0.0) - 60
        self.eggs.append(egg)
        self.runaways.append([e.x, e.y, e.face, 0.0, "drake"])

    # ---- eggs and hatchlings -------------------------------------------------------------------------------------------

    def _eggs(self, dt):
        me = self.me
        for g in list(self.eggs):
            if g.timer is None:
                g.vy = min(g.vy + EGG_GRAVITY * dt, MAX_FALL)
                g.vx *= math.exp(-(6.0 if g.grounded else 0.5) * dt)
                fall = g.vy
                landed, _ = self._move(g, dt, EGG_HW, EGG_H)
                if landed and fall > 90 and not g.bounced:
                    g.vy, g.bounced, g.grounded = -fall * 0.35, True, False
                elif landed and abs(g.vx) < 5:
                    g.timer = g.incubate
                if g.y >= LAVA_Y:
                    self.eggs.remove(g)
                    self.bursts.append([g.x, LAVA_Y, 0.0, "lava"])
                    self.events.append("egg_lost")
                    continue
            else:
                g.timer -= dt
                if g.timer <= 0:
                    self.eggs.remove(g)
                    self.hatchlings.append(Hatchling(g.x, g.y, g.hatches))
                    self.hatched += 1
                    self.events.append("hatch")
                    continue
            if self.knight == "ok" and any(overlap(g.box(), b) for b in self._touch_boxes(g.x)):
                self.eggs.remove(g)
                self._collect(g.x, g.y)

    def _touch_boxes(self, near_x):
        """The knight's bird and rider (not its lance), placed nearest near_x."""
        me = self.me
        x = near_x + wrap_dx(near_x, me.x)
        return me.boxes(x)[:2]

    def _collect(self, x, y):
        points = EGG_POINTS[min(self.chain, len(EGG_POINTS) - 1)]
        self.chain += 1
        self._add(points, x, y - 30)
        self.bursts.append([x, y - 10, 0.0, "egg"])
        self.events.append("egg")

    def _hatchlings(self, dt):
        for h in list(self.hatchlings):
            h.t += dt
            if self.knight == "ok" and any(overlap(h.box(), b) for b in self._touch_boxes(h.x)):
                self.hatchlings.remove(h)
                self._collect(h.x, h.y)
                if h.mount:                              # its drake turns away
                    self.runaways.append([h.mount[0], h.mount[1], h.mount[2], 0.0, "drake"])
                continue
            if h.t >= HATCH_WAIT and h.mount is None:
                side = self.rng.choice((-1, 1))
                h.mount = [h.x - side * 200, -40.0, side]
            if h.mount:
                mx, my, side = h.mount
                dx, dy = wrap_dx(mx, h.x), h.y - my
                d = math.hypot(dx, dy)
                step = MOUNT_SPEED * dt
                if d <= step + 2:
                    self.hatchlings.remove(h)
                    e = self._add_rider(h.x, h.y, h.cls, spawning=False)
                    e.face = e.dir = side
                    continue
                h.mount = [(mx + dx / d * step) % W, my + dy / d * step, side]

    # ---- the fire serpent ----------------------------------------------------------------------------------------------

    def _serpent(self, dt):
        if self.wave < GUARDIAN_FROM:
            return
        me = self.me
        self.serpent_cool = max(0.0, self.serpent_cool - dt)
        s = self.serpent
        if s is None:
            if (self.serpent_cool <= 0 and self.knight == "ok" and self.shield <= 0 and self.over_lake(me.x)
                    and me.y > LAVA_Y - GRAB_REACH):
                self.serpent = {"x": me.x, "t": 0.0, "state": "rise", "flaps": []}
                self.events.append("grab")
            return
        s["t"] += dt
        if s["state"] == "rise":
            s["x"] += max(-150 * dt, min(150 * dt, wrap_dx(s["x"], me.x)))
            if s["t"] >= GRAB_RISE:
                if self.knight == "ok" and abs(wrap_dx(s["x"], me.x)) < 40 and me.y > LAVA_Y - GRAB_REACH - 20:
                    s["state"], s["t"] = "hold", 0.0
                    self.knight = "grabbed"
                    me.vx = me.vy = 0.0
                    self._loop("serpent", True)
                else:
                    s["state"], s["t"] = "sink", 0.0
                    self.serpent_cool = MISS_COOL
        elif s["state"] == "hold":
            me.x = s["x"]
            me.y += PULL * dt
            s["flaps"] = [t for t in s["flaps"] if self.clock - t <= ESCAPE_WINDOW]
            if len(s["flaps"]) >= ESCAPE_FLAPS:
                self.knight = "ok"
                me.vy = -ESCAPE_KICK
                s["state"], s["t"] = "sink", 0.0
                self.serpent_cool = GRAB_COOL
                self._loop("serpent", False)
                self.events.append("escape")
            elif me.y >= LAVA_Y:
                self.knight = "ok"
                self._lose_knight("lava")
                self.serpent_cool = GRAB_COOL
        elif s["t"] >= 0.5:
            self.serpent = None

    def serpent_top(self):
        """How high the serpent's head is now (None when it is under the lake)."""
        s = self.serpent
        if s is None:
            return None
        if s["state"] == "rise":
            return LAVA_Y - (GRAB_REACH + 20) * min(1.0, s["t"] / GRAB_RISE)
        if s["state"] == "hold":
            return self.me.y - 30
        return LAVA_Y - (GRAB_REACH + 20) * max(0.0, 1 - s["t"] / 0.5)

    # ---- the raptor ----------------------------------------------------------------------------------------------------

    def _raptor(self, dt):
        r, me = self.raptor, self.me
        if r is None:
            if self.wave_t >= self.raptor_at:
                side = self.rng.choice((-1, 1))
                self.raptor = Raptor(side, max(120.0, min(700.0, me.y - 26)))
                self._loop("raptor_loop", True)
                self.events.append("raptor")
            return
        r.age += dt
        dx = me.x - r.x                                  # (it does not go round the sides: it turns back)
        if r.x < -60:
            r.face = 1
        elif r.x > W + 60:
            r.face = -1
        elif dx * r.face < -120:                         # gone past the knight: round it comes
            r.face = -r.face
        r.vx = max(-RAPTOR_SPEED, min(RAPTOR_SPEED, r.vx + r.face * RAPTOR_ACCEL * dt))
        aim = (me.y - 26) if self.knight == "ok" else 300
        r.vy = max(-RAPTOR_CLIMB, min(RAPTOR_CLIMB, (aim - r.y) * 2.5))
        r.x += r.vx * dt
        r.y = max(40.0, min(LAVA_Y - 30.0, r.y + r.vy * dt))
        if self.knight != "ok":
            return
        tx, ty = me.lance_tip()
        tip = (tx - 4 if me.face > 0 else tx, ty - 2, 4, 5)
        facing = (r.x - me.x) * me.face > 0
        if facing and overlap(tip, r.head()):
            self.raptor = None
            self.raptor_at = self.wave_t + RAPTOR_AGAIN
            self._loop("raptor_loop", False)
            self._add(RAPTOR_POINTS, r.x, r.y - 30)
            self.bursts.append([r.x, r.y, 0.0, "raptor"])
            self.events.append("raptor_die")
            return
        if self.shield <= 0 and any(overlap(b, part) for b in me.boxes()[:2] for part in (r.body(), r.head())):
            self._lose_knight("raptor")

    # ---- points, effects, the end of a wave ------------------------------------------------------------------------

    def _add(self, points, x=None, y=None):
        self.score += points
        self.best = max(self.best, self.score)
        if x is not None:
            self.popups.append([x, y, 0.0, points])
        while self.score >= self.next_extra:
            self.next_extra += EXTRA_EVERY
            if self.lives < MAX_LIVES:
                self.lives += 1
                self.events.append("extra")

    def _effects(self, dt):
        for b in self.bursts:
            b[2] += dt
        self.bursts = [b for b in self.bursts if b[2] < 0.8]
        for p in self.popups:
            p[2] += dt
            p[1] -= 25 * dt
        self.popups = [p for p in self.popups if p[2] < 1.0]
        for r in self.runaways:
            r[0] += r[2] * 260 * dt
            r[1] -= 60 * dt
            r[3] += dt
        self.runaways = [r for r in self.runaways if r[3] < 2.5 and -60 < r[0] < W + 60]

    def _wave_over(self):
        if self.queue or self.enemies or self.eggs or self.hatchlings or self.knight != "ok":
            return
        self.raptor = None
        self._loop("raptor_loop", False)
        self.bonus_won = 0
        if self.survival and not self.lost_one:
            self.bonus_won = SURVIVAL_BONUS
        if self.egg_wave and self.hatched == 0:
            self.bonus_won = EGG_WAVE_BONUS
        if self.bonus_won:
            self._add(self.bonus_won)
            self.events.append("bonus")
        else:
            self.events.append("wave_done")
        self.state, self.timer = "clear", CLEAR
