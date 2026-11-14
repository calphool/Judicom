"""Mars Patrol, on the hidden menu (judicom/maintenance.py).

A six-wheeled rover drives on by itself across Mars, left to right, over five courses (Martian Plains, Red Highlands, Crater
Fields, Rocky Escarpment, Hostile Territory), each of CHECKPOINTS sections; then round again, harder.  Craters must be jumped,
rocks, mines and ground enemies jumped or shot, and the drones and bombers overhead shot down or dodged.

    Left button: slower.   Right button: faster.   Neither: cruising speed.   (The rover never stops or turns back.)
    Both together (a new press): fire forward and up; on the ground, also jump.  In the air, only fire: no double jumps.
    The faster the rover, the longer the jump: wide craters need speed.

The world is W x H (800 x 600) and runs in fixed steps of TICK (1/120 s).  World x grows to the right without end; the rover's
left side is always PLAYER_X from the screen's left edge, so a thing at world x is at screen x - self.x + PLAYER_X.  y is the
same on the screen and in the world (down is +).  Flying things live in screen coordinates; what they drop belongs to the world
(it falls on a place on the ground), so the rover's speed takes it towards a falling bomb or past it.

Every section is made from a seed (cycle, course, section), so a section plays out the same each time it is driven, and after a
lost rover play goes on from the start of the section (the last checkpoint) with its hazards as they were.  autopilot() drives
the title screen's demonstration, and the tests use it to show that every course can be driven through.
No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

W, H = 800, 600
TICK = 1 / 120
MAX_STEPS = 12                  # at most this many steps for one update() (after a long pause it does not race to catch up)

PLAYER_X = 200                  # the rover's left side, on the screen
CAR_W, CAR_H = 64, 34
CLEARANCE = 4
WHEELS = (8, 32, 56)            # wheel centres from the rover's left side
GROUND_Y = 470                  # level ground
STEP = 8                        # the terrain's heights are kept every STEP pixels

SLOW, NORMAL, FAST = 100.0, 180.0, 280.0
SPEED_CHANGE = (FAST - SLOW) / 0.2      # pixels a second, each second: from one speed to another in about 200 ms
ONE_BUTTON_AFTER = 0.075        # one button counts (slower / faster) once held this long: both a little apart are a "both"
JUMP_V, GRAVITY = 420.0, 900.0
AIRTIME = 2 * JUMP_V / GRAVITY  # 0.93 s on level ground
LAND_SLACK = 8                  # a rover this far below the ground's level has hit a crater's wall, not landed
FALL_DEPTH = 40                 # this far down a crater: lost
FIRE_COOLDOWN = 0.12
DROP_CLEAR, DROP_CLEAR_AFTER = 150, 300  # nothing is dropped this close before a crater or a ground hazard, or this close after it
                                        # (where the rover lands from jumping it: it needs a moment to change speed)
SHOT_SPEED, SHOT_RANGE = 500.0, 220.0   # forward: in the world
UP_SPEED = 600.0

SECTION = 2600                  # a section, from one checkpoint to the next
CHECKPOINTS = 5                 # sections in a course
RUN_IN, RUN_OUT = 420, 360      # flat and clear at the start and the end of every section
COURSES = ("MARTIAN PLAINS", "RED HIGHLANDS", "CRATER FIELDS", "ROCKY ESCARPMENT", "HOSTILE TERRITORY")
TARGET_SPEED = 200.0            # a course's target time is its length at this speed (a little quicker each cycle)

LIVES = 3
EXTRA_LIFE_EVERY = 10000
POINTS = {"small": 100, "medium": 150, "large": 200, "mine": 50, "rover": 150, "turret": 150, "scout": 100, "attack": 200,
          "bomber": 300, "crater": 50, "checkpoint": 100, "course": 5000}
ROCKS = {"small": (18, 14, 1), "medium": (26, 22, 2), "large": (34, 30, 3)}     # width, height, hits
DESTROYED_SECONDS = 1.6         # the rover breaking up, then a pause
MESSAGE_SECONDS = 2.0
OVER_WAIT, OVER_IDLE, ATTRACT_IDLE = 1.0, 30.0, 60.0


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Thing:
    """A thing on the ground (world x of its left side; it stands on the ground) or in the air (screen x, y of its middle)."""

    def __init__(self, kind, x, w, h, hp=1, vx=0.0, y=0.0, vy=0.0):
        self.kind, self.x, self.w, self.h, self.hp = kind, float(x), w, h, hp
        self.vx, self.y, self.vy = vx, float(y), vy
        self.t, self.next_fire, self.active, self.size = 0.0, 0.0, False, ""
        self.path, self.x0, self.y0, self.delay = "line", self.x, self.y, 0.0     # a flyer's way of flying (see flight())


class Section:
    """One section's ground things, craters and flying visitors, made from its seed."""

    def __init__(self, x0, heights, gaps, things, flyers):
        self.x0, self.heights, self.gaps, self.things, self.flyers = x0, heights, gaps, things, flyers


def make_section(cycle, course, index, x0):
    """The section `index` (0 ..) of course `course` (0 .. 4) in cycle `cycle`, starting at world x0."""
    rng = random.Random("%d/%d/%d" % (cycle, course, index))
    hard = course + 5 * cycle                                   # 0, 1, 2 ...
    heights = {}
    gaps, things, flyers = [], [], []
    level = [0.0]

    def put(xa, xb, f):
        """Heights from xa to xb by f(fraction along) -> offset from level ground (up is -)."""
        i0, i1 = int(xa // STEP), int(math.ceil(xb / STEP))
        for i in range(i0, i1 + 1):
            t = _clamp((i * STEP - xa) / max(1.0, xb - xa), 0.0, 1.0)
            heights[i] = GROUND_Y + f(t)

    def flat(xa, xb):
        lv = level[0]
        put(xa, xb, lambda t: lv)

    def bumps(xa, xb):
        lv, pts = level[0], [rng.uniform(-3, 3) for _ in range(int((xb - xa) // 48) + 2)]
        put(xa, xb, lambda t: lv + pts[int(t * (len(pts) - 1))] * math.sin(math.pi * ((t * (len(pts) - 1)) % 1)))

    def slope(xa, xb, to):
        lv = level[0]
        put(xa, xb, lambda t: lv + (to - lv) * (1 - math.cos(math.pi * t)) / 2)
        level[0] = to

    def hill(xa, xb, a):
        lv = level[0]
        put(xa, xb, lambda t: lv - a * math.sin(math.pi * t))

    x, end = x0 + RUN_IN, x0 + SECTION - RUN_OUT
    flat(x0, x)
    menu = _menu(course, cycle)
    while True:
        kind = rng.choice(menu)
        need = 700                                              # the longest beat, with room to get back to level ground
        if x + need > end:
            break
        gap_after = rng.uniform(150, 300) * max(0.6, 1 - 0.04 * hard)
        if kind == "bumps":
            n = rng.uniform(200, 400)
            bumps(x, x + n)
            x += n
        elif kind == "hill":
            a = rng.uniform(14, 34 + 6 * (course >= 3))
            n = max(a * math.pi / 0.35, rng.uniform(220, 420))
            hill(x, x + n, a if rng.random() < 0.6 else -a * 0.7)
            x += n
        elif kind == "slope":
            to = _clamp(level[0] + rng.choice((-1, 1)) * rng.uniform(20, 45), -70.0, 35.0)
            steep = 0.42 if course >= 3 else 0.3
            n = max(abs(to - level[0]) * math.pi / 2 / steep, 120)
            slope(x, x + n, to)
            x += n
        elif kind == "crater":
            w = rng.uniform(55, 85) if course == 0 or rng.random() < 0.5 else rng.uniform(100, 140)
            flat(x, x + w + 220)
            gaps.append([x + 60, x + 60 + w])
            x += w + 220
        elif kind == "big_crater":
            w = min(190.0, rng.uniform(150, 175) + 3 * hard)
            flat(x, x + w + 560)                                # a long run-up: time to get up to speed
            gaps.append([x + 400, x + 400 + w])
            x += w + 560
        elif kind == "double":
            w1, w2, zone = rng.uniform(55, 95), rng.uniform(55, 95), rng.uniform(230, 280)
            flat(x, x + w1 + zone + w2 + 220)
            gaps.append([x + 60, x + 60 + w1])
            gaps.append([x + 60 + w1 + zone, x + 60 + w1 + zone + w2])
            x += w1 + zone + w2 + 220
        elif kind in ("small", "medium", "large"):
            rw, rh, hp = ROCKS[kind]
            flat(x, x + rw + 200)
            t = Thing("rock", x + 60, rw, rh, hp + (cycle > 0 and kind != "small"))
            t.size = kind
            things.append(t)
            x += rw + 200
        elif kind == "rolling":
            size = rng.choice(("small", "medium"))
            rw, rh, hp = ROCKS[size]
            flat(x, x + 480)
            t = Thing("rock", x + 420, rw, rh, hp, vx=-50.0 * min(1.5, 1 + 0.06 * hard))
            t.size = size
            things.append(t)
            x += 480 + rw
        elif kind == "mines":
            flat(x, x + 360)
            if rng.random() < 0.5:                              # two close together: one jump clears both
                things += [Thing("mine", x + 60, 12, 10), Thing("mine", x + 100, 12, 10)]
            else:                                               # or far enough apart to land between
                things += [Thing("mine", x + 60, 12, 10), Thing("buried", x + 300, 12, 4)]
            x += 360
        elif kind == "rover":                                   # drives at the rover: jump it or shoot it (it does not shoot:
            flat(x, x + 560)                                    # a shot to jump, then the rover itself, would come too close)
            things.append(Thing("rover", x + 520, 40, 22, 1, vx=-70.0 * min(1.4, 1 + 0.05 * hard)))
            x += 600
        elif kind == "turret":
            flat(x, x + 200)
            things.append(Thing("turret", x + 100, 24, 20, 2))
            x += 200
        flat(x, x + gap_after)
        x += gap_after
    slope(x, end, 0.0) if abs(level[0]) > 0.5 else flat(x, end)
    flat(end, x0 + SECTION)
    # the flying visitors, by where the rover is when they come
    air = _air_menu(course)
    fx = x0 + RUN_IN + rng.uniform(0, 300)
    every = max(520.0, 1000 - 60 * hard)
    while air and fx < x0 + SECTION - 400:
        flyers.append((fx, rng.choice(air), rng.random()))
        fx += rng.uniform(every, every * 1.5)
    return Section(x0, heights, gaps, things, flyers)


def _menu(course, cycle):
    menus = (
        ("bumps", "crater", "crater", "small", "small", "hill"),
        ("hill", "hill", "medium", "large", "rolling", "crater", "small", "bumps"),
        ("crater", "double", "big_crater", "mines", "mines", "crater", "bumps", "small"),
        ("slope", "slope", "large", "rover", "turret", "mines", "crater", "hill", "medium"),
        ("double", "big_crater", "large", "rolling", "mines", "rover", "turret", "slope", "hill", "crater"),
    )
    return menus[course]


def _air_menu(course):
    return (("scouts",), ("scouts", "attack"), ("bomber", "scouts", "bomber"), ("attack", "bomber", "scouts"),
            ("attack", "bomber", "scouts", "attack"))[course]


class Shot:
    __slots__ = ("x", "y", "vx", "vy", "ay", "start", "kind", "crater")

    def __init__(self, x, y, vx=0.0, vy=0.0, kind="", ay=0.0, crater=False):
        self.x, self.y, self.vx, self.vy, self.ay, self.kind, self.crater = x, y, vx, vy, ay, kind, crater
        self.start = x


class MarsGame:
    """One game.  update(now, held) moves it on; the rest is read by mars_view.py.  Sounds to play are collected in events
    (take_events()): "fire", "jump", "land", "rock", "boom", "die", "bomb", "checkpoint", "course", "over", "extra", and the
    tune's loop, "music_on" / "music_off".  (No engine sound: it was tried, and taken out.)

    state: "attract" (the title and a demonstration drive), "playing", "destroyed" (the rover just lost), "over".
    air=False leaves out the flying visitors (for tests of the ground)."""

    def __init__(self, best=0, seed=None, air=True, attract=True):
        self.best, self.air = best, air
        self.rng = random.Random(seed)
        self.events = []
        self._last, self._acc = None, 0.0
        self._both_before = True                        # a press of both counts only after both have been up
        self._real_before = True                        # (the same for the real buttons during the demonstration)
        self._held_for = {"left": 0.0, "right": 0.0}
        self.finished = False
        self.score = 0
        self.best_at_start = best
        if attract:
            self._start(attract=True)
        else:
            self.new_game()

    # ---- the game's course -------------------------------------------------------------------------------------------------

    def new_game(self):
        self.events.append("music_on")
        self._start(attract=False)

    def _start(self, attract):
        self.state = "attract" if attract else "playing"
        self._both_before = True
        self.timer = 0.0
        self.score, self.lives, self.cycle, self.course = 0, LIVES, 0, 0
        self.best_at_start = self.best
        self.next_extra = EXTRA_LIFE_EVERY
        self.course_x0 = 0.0
        self.course_time = 0.0
        self.message, self.message_t = (COURSES[0], 3.0) if not attract else ("", 0.0)
        self._begin_at(0)

    def _begin_at(self, index):
        """Drive on from checkpoint `index` of the current course: that section made afresh, the rover at its start."""
        self.checkpoint = index
        x0 = self.course_x0 + index * SECTION
        self.sections = {}
        self._next = None
        self.heights = {}
        self.gaps, self.things, self.flyers, self.pending_air = [], [], [], []
        self.shots, self.ups, self.enemy_shots, self.bursts = [], [], [], []
        self._add_section(index)
        self.x = x0 + 40.0                              # the rover's left side, in the world
        self.speed = self.target = NORMAL
        self.grounded, self.vy = True, 0.0
        self.yb = self.ground(self.x + CAR_W / 2) - CLEARANCE      # the rover's bottom
        self.cooldown = 0.0
        self.takeoff_x = None
        self.wheel = 0.0

    def _add_section(self, index):
        if index in self.sections:
            return
        x0 = self.course_x0 + index * SECTION
        self.sections[index] = self._take(make_section(self.cycle, self.course, index, x0))

    def _next_course(self):
        """(cycle, course) after this one."""
        return (self.cycle + 1, 0) if self.course == len(COURSES) - 1 else (self.cycle, self.course + 1)

    def _take(self, s):
        self.heights.update(s.heights)
        self.gaps += [list(g) for g in s.gaps]
        self.things += [_copy(t) for t in s.things]
        self.pending_air += list(s.flyers)
        return s

    @property
    def course_length(self):
        return SECTION * CHECKPOINTS

    @property
    def progress(self):
        """How far along the current course, 0 .. 1."""
        return _clamp((self.x - self.course_x0) / self.course_length, 0.0, 1.0)

    def take_events(self):
        events, self.events = self.events, []
        return events

    def loops(self):
        """The looping sounds that should be on now (for a sound that starts late: Session asks)."""
        if self.state == "playing":
            return ["music"]
        return ["music"] if self.state == "destroyed" else []

    def summary(self):
        return "%d points, course %d%s" % (self.score, self.course + 1, ", cycle %d" % (self.cycle + 1) if self.cycle else "")

    # ---- the ground --------------------------------------------------------------------------------------------------------

    def ground(self, x):
        """The ground's height (screen y) at world x."""
        i = int(x // STEP)
        a, b = self.heights.get(i, GROUND_Y), self.heights.get(i + 1, GROUND_Y)
        return a + (b - a) * (x / STEP - i)

    def gap_at(self, x):
        for g in self.gaps:
            if g[0] <= x <= g[1]:
                return g
        return None

    def screen_x(self, wx):
        return wx - self.x + PLAYER_X

    def world_x(self, sx):
        return sx + self.x - PLAYER_X

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
        held = set(held)
        if self.state == "attract":
            both = {"left", "right"} <= held
            pressed, self._real_before = both and not self._real_before, both
            if pressed:
                self.new_game()
                return
            self.timer += TICK
            if self.timer >= ATTRACT_IDLE:
                self.finished = True
            self._buttons(autopilot(self), demo=True)
            self._world()
            return
        if self.state == "over":
            pressed = self._buttons(held)
            self.timer += TICK
            if pressed and self.timer >= OVER_WAIT:
                self.new_game()
            elif self.timer >= OVER_IDLE:
                self.finished = True
            return
        if self.state == "destroyed":
            self._buttons(held)
            self.timer -= TICK
            self._bursts()
            if self.timer <= 0:
                self.lives -= 1
                if self.lives <= 0:
                    self.state, self.timer = "over", 0.0
                    self.events += ["music_off", "over"]
                else:
                    self._begin_at(self.checkpoint)
                    self.state = "playing"
                    self.message, self.message_t = "CHECKPOINT %d" % (self.checkpoint + 1) if self.checkpoint else COURSES[self.course], 1.5
            return
        self._buttons(held)
        self._world()

    def _buttons(self, held, demo=False):
        """Speed from one button, fire (and jump) on a new press of both.  Returns True on a new press of both."""
        both = {"left", "right"} <= held
        pressed = both and not self._both_before
        self._both_before = both
        for b in ("left", "right"):
            self._held_for[b] = self._held_for[b] + TICK if b in held else 0.0
        if self.state not in ("playing", "attract") or (self.state == "attract" and not demo):
            return pressed
        if both:
            self.target = self.speed                    # both held: the speed stays as it is
        elif self._held_for["left"] >= ONE_BUTTON_AFTER:
            self.target = SLOW
        elif self._held_for["right"] >= ONE_BUTTON_AFTER:
            self.target = FAST
        elif "left" not in held and "right" not in held:
            self.target = NORMAL
        if pressed:
            if self.cooldown <= 0:
                self._fire()
            if self.grounded:
                self.grounded, self.vy = False, -JUMP_V
                self.yb -= 1
                self.takeoff_x = self.x + CAR_W / 2
                self._event("jump")
        return pressed

    def _event(self, name):
        if self.state != "attract":
            self.events.append(name)

    def _fire(self):
        self.cooldown = FIRE_COOLDOWN
        front = self.x + CAR_W
        self.shots.append(Shot(front, self.yb - 5, SHOT_SPEED))          # low: it must hit a small rock or a mine
        self.ups.append(Shot(PLAYER_X + 38, self.yb - CAR_H, 0.0, -UP_SPEED))
        self._event("fire")

    # ---- one step of the world ---------------------------------------------------------------------------------------------

    def _world(self):
        dt = TICK
        self.cooldown -= dt
        self.course_time += dt
        if self.message_t > 0:
            self.message_t -= dt
        # speed, smoothly
        d = self.target - self.speed
        self.speed += _clamp(d, -SPEED_CHANGE * dt, SPEED_CHANGE * dt)
        self.x += self.speed * dt
        self.wheel = (self.wheel + self.speed * dt / 6) % 4
        self._sections()
        cx = self.x + CAR_W / 2
        if self.grounded:
            if self.gap_at(cx):
                self.grounded, self.vy = False, 0.0     # over the edge
                self.takeoff_x = None
            else:
                self.yb = self.ground(cx) - CLEARANCE
        else:
            self.vy += GRAVITY * dt
            self.yb += self.vy * dt
            level = self.ground(cx) - CLEARANCE
            g = self.gap_at(cx)
            if g is None and self.yb >= level:
                if self.yb - level <= LAND_SLACK:
                    self._land(level)
                else:
                    return self._destroyed()            # into a crater's far wall
            elif g is not None and self.yb > level + FALL_DEPTH:
                return self._destroyed()                # down a crater
        self._move_things(dt)
        self._move_air(dt)
        self._move_shots(dt)
        self._bursts()
        if self.state == "playing" or self.state == "attract":
            self._hits()
        self._checkpoints()

    def _land(self, level):
        self.yb, self.vy, self.grounded = level, 0.0, True
        self._event("land")
        if self.takeoff_x is not None:
            cleared = [g for g in self.gaps if self.takeoff_x < g[0] and g[1] < self.x + CAR_W / 2]
            for g in cleared:
                if len(g) == 2:
                    g.append(True)                      # counted once
                    self._add(POINTS["crater"])
        self.takeoff_x = None

    def _sections(self):
        index = int((self.x - self.course_x0) // SECTION)
        if (self.x - self.course_x0) % SECTION > SECTION - 1000:
            if index + 1 < CHECKPOINTS:
                self._add_section(index + 1)
            elif self._next is None:                    # the next course's first section, before it comes into view
                cycle, course = self._next_course()
                self._next = self._take(make_section(cycle, course, 0, self.course_x0 + self.course_length))
        # forget what is well behind
        behind = self.x - 600
        self.gaps = [g for g in self.gaps if g[1] > behind]
        self.things = [t for t in self.things if t.x + t.w > behind and t.hp > 0]
        if len(self.heights) > 3000:
            self.heights = {i: y for i, y in self.heights.items() if i * STEP > behind}

    def _checkpoints(self):
        index = int((self.x - self.course_x0) // SECTION)
        if index > self.checkpoint and self.state != "destroyed":
            if index >= CHECKPOINTS:
                self._course_done()
            else:
                self.checkpoint = index
                self._add(POINTS["checkpoint"])
                self._event("checkpoint")
                self.message, self.message_t = "CHECKPOINT %d" % (index + 1), MESSAGE_SECONDS

    def _course_done(self):
        target = self.course_length / TARGET_SPEED * (0.97 ** self.cycle)
        bonus = int(max(0.0, target - self.course_time) * 100)
        self._add(bonus)
        text = "TIME BONUS %d" % bonus
        if self.course == len(COURSES) - 1:
            self._add(POINTS["course"])
            text = "ALL COURSES! +%d" % (POINTS["course"] + bonus)
        self.cycle, self.course = self._next_course()
        self._event("course")
        self.course_x0 += self.course_length
        self.course_time = 0.0
        self.checkpoint = 0
        self.sections = {0: self._next or self._take(make_section(self.cycle, self.course, 0, self.course_x0))}
        self._next = None
        self.message, self.message_t = "%s - %s" % (text, COURSES[self.course]), 3.0

    def _add(self, points):
        if self.state == "attract":
            return
        self.score += points
        if self.score >= self.next_extra:
            self.next_extra += EXTRA_LIFE_EVERY
            self.lives += 1
            self.events.append("extra")
        self.best = max(self.best, self.score)

    # ---- ground things -----------------------------------------------------------------------------------------------------

    def _move_things(self, dt):
        for t in self.things:
            sx = self.screen_x(t.x)
            if not t.active and sx < W:
                t.active = True
                t.next_fire = 0.0 if t.kind == "rover" else 0.6
            if not t.active:
                continue
            t.t += dt
            if t.vx:
                t.x += t.vx * dt
                if self.gap_at(t.x + t.w / 2):          # a rolling rock or a rover into a crater: gone
                    t.hp = 0
                    continue
            if t.kind == "turret" and PLAYER_X + CAR_W + 150 < sx < W - 30:
                t.next_fire -= dt
                if t.next_fire <= 0:
                    self._ground_shot(t)
                    t.next_fire = 2.6 * max(0.6, 1 - 0.05 * (self.course + 5 * self.cycle))

    def _ground_shot(self, t):
        self.enemy_shots.append(Shot(t.x - 4, self.ground(t.x) - 14, -220.0, kind="ground"))

    # ---- the air -----------------------------------------------------------------------------------------------------------

    def _move_air(self, dt):
        hard = self.course + 5 * self.cycle
        quick = min(1.6, 1 + 0.06 * hard)
        while self.pending_air and self.pending_air[0][0] <= self.x:
            at, kind, r = self.pending_air.pop(0)
            if kind in ("attack", "bomber") and any(f.kind == kind for f in self.flyers):
                self.pending_air.append((at + 400, kind, r))        # one of each at a time: this one comes a little later
                self.pending_air.sort(key=lambda p: p[0])
                continue
            if self.air:
                self._spawn(kind, r, quick)
        for f in self.flyers:
            f.t += dt
            f.x, f.y = flight(f, f.t)
            f.next_fire -= dt
            if f.kind == "attack" and ATTACK_ARRIVE < f.t < ATTACK_LEAVE and f.next_fire <= 0 and self._fair_drop(self.world_x(f.x)):
                self.enemy_shots.append(Shot(self.world_x(f.x), f.y + f.h / 2, 0.0, 170.0 * quick, kind="drop"))
                f.next_fire = 1.6 / quick
            elif f.kind == "bomber" and f.next_fire <= 0 and 150 < f.x < 760 and self._fair_drop(self.world_x(f.x)):
                crater = self.course >= 2 and (int(f.t * 10) % 2 == 0)
                self.enemy_shots.append(Shot(self.world_x(f.x), f.y + f.h / 2, 0.0, 40.0, kind="bomb", ay=280.0, crater=crater))
                f.next_fire = 1.9 / quick
        self.flyers = [f for f in self.flyers if f.hp > 0 and f.t < 40 and not (f.x < -80 and f.t > 1)]

    def _fair_drop(self, wx):
        """Nothing is dropped where it would fall on or by a crater or a ground hazard (one thing to deal with at a time), nor
        while the rover is in the air (where it cannot change its speed to get out of the way)."""
        return self.grounded and (all(g[1] < wx - DROP_CLEAR_AFTER or g[0] > wx + DROP_CLEAR for g in self.gaps)
                and all(t.x + t.w < wx - DROP_CLEAR_AFTER or t.x > wx + DROP_CLEAR for t in self.things if t.hp > 0))

    def _spawn(self, kind, r, quick):
        """r (0 .. 1, from the section's seed) picks the height and the way it flies."""
        if kind == "scouts":                            # two or three, one behind the other along the same path
            path = SCOUT_PATHS[int(r * 997) % len(SCOUT_PATHS)]
            for i in range(2 + (r > 0.5)):
                f = Thing("scout", W + 40, 40, 20, 1, vx=-150.0 * quick, y=110 + 80 * r)
                f.path, f.x0, f.y0, f.delay = path, W + 40, f.y, 0.45 * i
                f.t = -f.delay
                f.x, f.y = flight(f, f.t)
                self.flyers.append(f)
        elif kind == "attack":                          # swoops in, circles or figures-of-eight over the rover, then away
            f = Thing("attack", W + 40, 44, 28, 2, vx=-120.0 * quick, y=170 + 60 * r)
            f.path, f.x0, f.y0 = ATTACK_PATHS[int(r * 991) % len(ATTACK_PATHS)], W + 40, f.y
            f.next_fire = ATTACK_ARRIVE
            f.x, f.y = flight(f, 0.0)
            self.flyers.append(f)
        elif kind == "bomber":                          # big and slow, rising and falling a little
            f = Thing("bomber", W + 60, 72, 28, 2, vx=-85.0 * quick, y=80 + 20 * r)
            f.path, f.x0, f.y0 = "bob", W + 60, f.y
            f.next_fire = 0.8
            self.flyers.append(f)

    # ---- shots -------------------------------------------------------------------------------------------------------------

    def _move_shots(self, dt):
        for s in self.shots:
            s.x += s.vx * dt
        self.shots = [s for s in self.shots if s.x - s.start < SHOT_RANGE and s.y < self.ground(s.x)]
        for s in self.ups:
            s.y += s.vy * dt
        self.ups = [s for s in self.ups if s.y > -10]
        keep = []
        for s in self.enemy_shots:
            s.vy += s.ay * dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            if s.kind == "ground":
                if s.y > self.ground(s.x) or self.screen_x(s.x) < -20:
                    continue
            else:                                       # bombs and drones' shots: world x too
                if s.y >= self.ground(s.x) and not self.gap_at(s.x):
                    self._impact(s, s.x)
                    continue
                if s.y > H or self.screen_x(s.x) < -20:
                    continue
            keep.append(s)
        self.enemy_shots = keep

    def _impact(self, s, wx):
        """A bomb or a drone's shot reaching the ground: a burst there, and a crater for a crater bomb, where that is fair."""
        self.bursts.append([self.screen_x(wx), self.ground(wx), 0.0, "bomb"])
        self._event("bomb")
        if s.kind == "bomb" and s.crater:
            front = self.x + CAR_W
            w = 60.0
            clear = all(abs(g[0] - wx) > 200 and abs(g[1] - wx) > 200 for g in self.gaps)
            clear = clear and all(abs(t.x - wx) > 160 for t in self.things)
            flat = abs(self.ground(wx - 40) - self.ground(wx + w + 40)) < 2
            if wx > front + 260 and clear and flat:
                self.gaps.append([wx, wx + w])
                self.gaps.sort(key=lambda g: g[0])
        if abs(self.screen_x(wx) - (PLAYER_X + CAR_W / 2)) < CAR_W / 2 + 4 and self.grounded:
            self._destroyed()                           # right on the rover

    # ---- what hits what ----------------------------------------------------------------------------------------------------

    def car_rect(self):
        """The rover's box on the screen (a little inside its picture)."""
        return (PLAYER_X + 4, self.yb - CAR_H + 6, CAR_W - 8, CAR_H - 6)

    def thing_rect(self, t):
        if t.kind in ("scout", "attack", "bomber"):
            return (t.x - t.w / 2, t.y - t.h / 2, t.w, t.h)
        return (self.screen_x(t.x), self.ground(t.x + t.w / 2) - t.h, t.w, t.h)

    def _hits(self):
        car = self.car_rect()
        for s in list(self.shots):                      # forward shots: ground things, ground shots
            for t in self.things:
                if t.hp > 0 and t.kind != "buried" and _inside(self.screen_x(s.x), s.y, self.thing_rect(t)):
                    self._damage(t, ground=True)
                    self.shots.remove(s)
                    break
            else:
                for e in self.enemy_shots:
                    if e.kind == "ground" and abs(e.x - s.x) < 10 and abs(e.y - s.y) < 8:
                        self.enemy_shots.remove(e)
                        self.shots.remove(s)
                        self.bursts.append([self.screen_x(s.x), s.y, 0.0, "small"])
                        break
        for s in list(self.ups):                        # upward shots: flyers, bombs, drones' shots
            hit = next((f for f in self.flyers if f.hp > 0 and _inside(s.x, s.y, self.thing_rect(f), 3)), None)
            if hit is not None:
                self._damage(hit, ground=False)
                self.ups.remove(s)
                continue
            e = next((e for e in self.enemy_shots if e.kind != "ground" and abs(self.screen_x(e.x) - s.x) < 6 and abs(e.y - s.y) < 8), None)
            if e is not None:
                self.enemy_shots.remove(e)
                self.ups.remove(s)
                self.bursts.append([self.screen_x(e.x), e.y, 0.0, "small"])
        for t in self.things:                           # the rover against ground things
            if t.hp > 0 and _overlap(car, self.thing_rect(t)):
                return self._destroyed()
        for e in self.enemy_shots:
            if _overlap(car, (self.screen_x(e.x) - 3, e.y - 3, 6, 6)):
                return self._destroyed()

    def _damage(self, t, ground):
        t.hp -= 1
        if t.hp > 0:
            self.bursts.append([self.screen_x(t.x) + t.w / 2 if ground else t.x, (self.ground(t.x) - t.h / 2) if ground else t.y, 0.0, "small"])
            return
        if ground:
            self.bursts.append([self.screen_x(t.x) + t.w / 2, self.ground(t.x) - t.h / 2, 0.0, "rock"])
            self._add(POINTS[t.size] if t.kind == "rock" else POINTS.get(t.kind, 50))
            self._event("rock")
        else:
            self.bursts.append([t.x, t.y, 0.0, "air"])
            self._add(POINTS[t.kind])
            self._event("boom")

    def _destroyed(self):
        if self.state == "attract":                     # the demonstration just starts its drive again
            self._begin_at(0)
            return
        self.state, self.timer = "destroyed", DESTROYED_SECONDS
        self.bursts.append([PLAYER_X + CAR_W / 2, self.yb - CAR_H / 2, 0.0, "car"])
        self.events.append("die")

    def _bursts(self):
        for b in self.bursts:
            b[2] += TICK
        self.bursts = [b for b in self.bursts if b[2] < (1.2 if b[3] == "car" else 0.45)]


# ---- how the flyers fly --------------------------------------------------------------------------------------------------

SCOUT_PATHS = ("wave", "loops", "figure8", "swoop", "zigzag")
ATTACK_PATHS = ("figure8", "circle", "figure8", "loops")
ATTACK_ARRIVE, ATTACK_LEAVE = 2.2, 8.0          # an attack drone's time over the rover (it drops its shots then)
HOVER_X = 420                                   # ... round about here


def flight(f, t):
    """Where flyer f is (screen x, y of its middle) t seconds after it came: its path, round an anchor drifting left.
    Never lower than y 300 (well above a jumping rover)."""
    p, ph = f.path, 0.0
    if f.kind == "attack":                      # in to HOVER_X, round and round there, then off to the left quickly
        if t < ATTACK_ARRIVE:
            cx = f.x0 + (HOVER_X - f.x0) * (1 - (1 - t / ATTACK_ARRIVE) ** 2)
        elif t < ATTACK_LEAVE:
            cx = HOVER_X
        else:
            cx = HOVER_X - 260 * (t - ATTACK_LEAVE) ** 1.3
        s = min(1.0, t / ATTACK_ARRIVE)         # the pattern grows as it arrives
        if p == "circle":
            return cx + 90 * s * math.sin(1.6 * t), f.y0 + 55 * s * math.cos(1.6 * t)
        if p == "loops":
            return cx + 70 * s * math.cos(2.4 * t), f.y0 + 60 * s * math.sin(2.4 * t)
        return cx + 120 * s * math.sin(1.3 * t), f.y0 + 50 * s * math.sin(2.6 * t)          # a figure of eight
    x = f.x0 + f.vx * t
    if p == "wave":
        y = f.y0 + 40 * math.sin(2.4 * t + ph)
    elif p == "zigzag":
        y = f.y0 + 45 * (2 * abs((t * 0.9) % 2 - 1) - 1)
    elif p == "loops":                          # loop-the-loops as it goes (circling faster than it goes along: real loops)
        x += 55 * math.cos(3.6 * t + math.pi / 2)
        y = f.y0 + 55 * math.sin(3.6 * t + math.pi / 2) - 55
    elif p == "figure8":                        # figures of eight, drifting slowly across
        x = f.x0 + f.vx * 0.55 * t + 110 * math.sin(1.5 * t) - 0
        y = f.y0 + 45 * math.sin(3.0 * t)
    elif p == "swoop":                          # dives down across the middle of the screen and climbs away
        across = min(1.0, max(0.0, (f.x0 - x) / (W + 120)))
        y = f.y0 + 105 * math.sin(math.pi * across)
    elif p == "bob":
        y = f.y0 + 12 * math.sin(1.1 * t)
    else:
        y = f.y0
    return x, min(300.0, max(40.0, y))


def _copy(t):
    c = Thing(t.kind, t.x, t.w, t.h, t.hp, t.vx, t.y, t.vy)
    c.size = t.size
    return c


def _inside(x, y, rect, pad=0):
    rx, ry, rw, rh = rect
    return rx - pad <= x <= rx + rw + pad and ry - pad <= y <= ry + rh + pad


def _overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


# ---- the autopilot (the demonstration, and the tests' driver) ----------------------------------------------------------------

def obstacles(game):
    """What the rover must be off the ground for, ahead: [(from, to, speed)] in world x of the rover's middle, nearest first.
    speed: how the obstacle itself moves (0 for craters and still things)."""
    out = []
    for g in game.gaps:
        out.append([g[0] - 2, g[1] + 6, 0.0])
    for t in game.things:
        if t.hp > 0:
            out.append([t.x - CAR_W / 2 - 6, t.x + t.w + CAR_W / 2 + 6, t.vx if t.active else 0.0])
    for e in game.enemy_shots:
        if e.kind == "ground":
            out.append([e.x - CAR_W / 2 - 8, e.x + CAR_W / 2 + 8, e.vx])
    cx = game.x + CAR_W / 2
    out = sorted((o for o in out if o[1] > cx), key=lambda o: o[0])
    merged = []
    for o in out:
        if merged and o[0] - merged[-1][1] < 30 and o[2] == merged[-1][2] == 0:
            merged[-1][1] = max(merged[-1][1], o[1])
        else:
            merged.append(o)
    return merged


def autopilot(game):
    """The buttons a good driver would press now."""
    cx = game.x + CAR_W / 2
    ahead = obstacles(game)
    want, urgent = NORMAL, False
    for a, b, v in ahead[:2]:
        if a - cx < 700 and (b - a) + 40 > (NORMAL - v) * AIRTIME:
            want = FAST                                 # too wide for cruising speed: hold Right (in the air too)
            urgent = urgent or a - cx < 350             # (close: no time to slow down for anything else first)
    speed = {"right"} if want == FAST else set()
    for e in game.enemy_shots:                          # a bomb or a drone's shot about to come down on the rover
        if e.kind == "ground" or e.vy <= 0 or not game.grounded:
            continue

        def when(depth):                                # seconds until it is down to this y
            fall = max(0.0, depth - e.y)
            return (-e.vy + math.sqrt(e.vy * e.vy + 2 * e.ay * fall)) / e.ay if e.ay else fall / e.vy
        times = (when(game.yb - CAR_H + 6), when((game.yb * 2 - CAR_H) / 2), when(game.ground(e.x)))     # roof .. ground

        def travel(v, t):                               # how far the rover goes in t seconds when it changes to speed v
            wait = min(t, ONE_BUTTON_AFTER) if v != NORMAL else 0.0
            ramp = min(t - wait, abs(v - game.speed) / SPEED_CHANGE)
            return game.speed * wait + (game.speed + v) / 2 * ramp + v * max(0.0, t - wait - ramp)

        def room(v):                                    # how far clear of it the rover stays, at speed v
            return min(abs(e.x - (cx + travel(v, t))) for t in times) - CAR_W / 2
        if room(game.speed) < 10 and not urgent and getattr(game, "_dodging", (None,))[0] not in game.enemy_shots:
            best = max((SLOW, NORMAL, FAST), key=room)
            game._dodging = (e, {"left"} if best == SLOW else {"right"} if best == FAST else set())    # decide once ...
    dodge = getattr(game, "_dodging", None)
    if dodge and dodge[0] in game.enemy_shots and not urgent:
        speed = dodge[1]                                # ... and keep to it until it is down
    if game.grounded and ahead:
        a, b, v = ahead[0]
        reach = (game.speed - v) * AIRTIME
        if a - cx <= max(4.0, (reach - (b - a)) / 2):
            return {"left", "right"}                    # jump (and fire)
    if not game.grounded:
        if game.vy < 0 and int(game.course_time * 10) % 2 == 0:
            return {"left", "right"}                    # fire on the way up (both held keeps the speed; never held at landing)
        return {"right"} if game.speed > NORMAL + 5 else set()     # keep the speed it jumped at
    return speed
