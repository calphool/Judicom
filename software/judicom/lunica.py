"""Lunica, on the hidden menu (judicom/maintenance.py).

Waves of alien craft swoop in along curving paths and settle into a formation at the top (4 commanders, 16 interceptors, 20
scouts); then they break away in ones, twos and threes to dive at the fighter at the bottom, shooting, and climb back.  A
commander may stop half-way down and shine a capture beam: a fighter caught in it is carried off (a fighter lost).  Shoot
that commander down while it dives and the captured fighter comes back and docks beside yours: two fighters, two streams
of shots.  Every fourth stage from the third is a bonus stage: nobody shoots, shoot as many as you can.

    Left: move left.   Right: move right.   Both held: stop, and fire again and again (at most 2 shots up per fighter).

The world is W x H (y down); the fighter's middle is at y PLAYER_Y.  Fixed steps of TICK.  The flight paths are joined cubic
Bezier curves and arcs (Path); every enemy follows one, its picture turned to the way it goes.
No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

W, H = 580, 800
TICK = 1 / 120
MAX_STEPS = 12

PLAYER_Y, PLAYER_W, PLAYER_H = 735, 34, 30
PLAYER_SPEED = 300.0
ONE_BUTTON_AFTER = 0.075        # one button moves the fighter once held this long: both pressed a little apart is a "both"
SHOT_W, SHOT_H, SHOT_SPEED = 4, 14, 500.0
SHOTS_EACH, SHOT_GAP = 2, 0.15

KINDS = {                       # size, hits, points (in formation, diving)
    "scout": ((26, 24), 1, (50, 100)),
    "interceptor": ((30, 26), 1, (80, 160)),
    "commander": ((36, 30), 2, (150, 400)),
}
ESCORTED = (400, 800, 1600)     # a commander shot down diving with 0, 1 or 2 of its escorts still with it
ROWS = (("commander", 4), ("interceptor", 8), ("interceptor", 8), ("scout", 10), ("scout", 10))
SPACING, FORM_X, FORM_TOP = 42, W / 2, 115
SWAY, BOB = 15, 5               # the formation sways this far side to side and bobs this far up and down
GROUP_GAP, MEMBER_GAP = 1.2, 0.22                # (members 0.22 s apart: about 33 pixels, clear of each other)
ENTRY_PACE = 1.6                # the ways in are flown at this many times the stage's entry speed: 3 to 4.5 s a group, the
                                # whole formation in place in about 12 s

CAPTURE_Y, BEAM_SECONDS, BEAM_HOLD = 390, 3.0, 0.4
BEAM_HALF = 52                  # the beam's half-width at the fighter's row
RISE_SECONDS = 1.6              # a caught fighter rising to its captor
LIVES, MAX_LIVES = 3, 9
EXTRA_AT, EXTRA_EVERY = (20000, 70000), 70000
DESTROYED, SHIELD, SAFE_X = 1.2, 2.0, 70
CLEAR, STAGE_INTRO, BONUS_SUMMARY = 1.2, 1.6, 3.5
FIRST_INTRO = 3.2               # a new game's "STAGE 1" stays while its opening tune plays
BONUS_HIT, BONUS_GROUP, BONUS_PERFECT = 100, 1000, 10000
OVER_WAIT, OVER_IDLE, ATTRACT_IDLE = 1.0, 30.0, 60.0


def harder(stage, at1, at5, at10):
    """A setting for this stage: at1 at stage 1, at5 at 5, at10 from 10 on, in a straight line between."""
    if stage <= 5:
        return at1 + (at5 - at1) * (stage - 1) / 4
    return at5 + (at10 - at5) * (min(stage, 10) - 5) / 5


def is_bonus(stage):
    return stage >= 3 and (stage - 3) % 4 == 0


# ---- flight paths ------------------------------------------------------------------------------------------------------------

class Path:
    """A smooth path: cubic Bezier curves and circular arcs joined end to end, walked by distance along it.

        Path((x, y)).curve((c1x, c1y), (c2x, c2y), (x, y)).arc((cx, cy), sweep_degrees)...
    An arc starts where the path is and goes round the centre given (positive sweep: clockwise on the screen)."""

    def __init__(self, start):
        self.pts = [tuple(start)]

    def curve(self, c1, c2, end, n=20):
        p0 = self.pts[-1]
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.pts.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                                  for a, b, c, d in zip(p0, c1, c2, end)))
        return self

    def arc(self, centre, sweep):
        x0, y0 = self.pts[-1]
        r = math.hypot(x0 - centre[0], y0 - centre[1])
        a0 = math.atan2(y0 - centre[1], x0 - centre[0])
        n = max(4, int(abs(sweep) / 10))
        for i in range(1, n + 1):
            a = a0 + math.radians(sweep) * i / n
            self.pts.append((centre[0] + math.cos(a) * r, centre[1] + math.sin(a) * r))
        return self

    def line(self, end):
        return self.curve(self.pts[-1], end, end, n=6)

    def done(self):
        self.lengths = [0.0]
        for (ax, ay), (bx, by) in zip(self.pts, self.pts[1:]):
            self.lengths.append(self.lengths[-1] + math.hypot(bx - ax, by - ay))
        self.length = self.lengths[-1]
        return self

    def at(self, d):
        """(x, y, heading in degrees) at distance d along it."""
        if d <= 0:
            i = 0
        elif d >= self.length:
            i = len(self.pts) - 2
        else:
            lo, hi = 0, len(self.lengths) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if self.lengths[mid] <= d:
                    lo = mid
                else:
                    hi = mid
            i = lo
        (ax, ay), (bx, by) = self.pts[i], self.pts[i + 1]
        seg = self.lengths[i + 1] - self.lengths[i] or 1.0
        k = max(0.0, min(1.0, (d - self.lengths[i]) / seg))
        return ax + (bx - ax) * k, ay + (by - ay) * k, math.degrees(math.atan2(by - ay, bx - ax))

    def moved(self, dx, dy=0.0, mirror=False):
        """The same path shifted (and mirrored left to right if asked)."""
        p = Path((0, 0))
        p.pts = [((W - x) if mirror else x) + dx for x, _ in self.pts]
        p.pts = [(x, y + dy) for x, (_, y) in zip(p.pts, self.pts)]
        return p.done()


def _entries():
    """The library of ways in (each group's half takes one, the other half its mirror).  Each ends somewhere in the upper
    half, from where the enemy flies to its place in the formation.  Two of them (LOW) sweep right down through the
    fighter's row on the way: they can fly into it, so it has to move out of their way."""
    return [
        Path((170, -30)).curve((170, 160), (60, 300), (150, 400)).arc((230, 400), 300).curve((260, 300), (280, 260), (290, 230)).done(),
        Path((120, -30)).curve((120, 260), (40, 640), (170, 745)).curve((260, 815), (400, 790), (450, 660))      # down to the
            .curve((500, 520), (380, 430), (330, 380)).curve((300, 340), (290, 290), (290, 240)).done(),            # fighters' row
        Path((380, -30)).curve((380, 200), (70, 190), (80, 380)).curve((90, 520), (330, 520), (330, 380)).curve((330, 300), (300, 260), (290, 240)).done(),
        Path((-30, 560)).curve((120, 560), (180, 745), (300, 742)).curve((430, 740), (500, 640), (440, 520))       # in low, an S
            .curve((400, 440), (330, 380), (300, 320)).curve((285, 290), (285, 260), (290, 240)).done(),            # through the row
        Path((120, -30)).curve((120, 160), (180, 260), (250, 300)).arc((290, 340), 280).curve((240, 300), (260, 260), (280, 230)).done(),
    ]


LOW = (1, 3)                    # the ways in that come down through the fighters' row


def _bonus_paths():
    """Five ways across for a bonus stage: each goes in and out again (a loop, crossing arcs, an S, a spiral, a figure 8)."""
    return [
        Path((150, -30)).curve((150, 200), (120, 300), (200, 380)).arc((270, 380), 360).curve((330, 460), (420, 480), (610, 470)).done(),
        Path((-30, 120)).curve((200, 160), (380, 400), (610, 640)).done(),
        Path((-30, 300)).curve((180, 300), (180, 520), (290, 520)).curve((400, 520), (400, 300), (610, 300)).done(),
        Path((290, -30)).curve((290, 120), (200, 200), (200, 300)).arc((290, 300), 300).arc((290, 330), 300).curve((200, 380), (100, 450), (-30, 470)).done(),
        Path((-30, 380)).curve((80, 380), (150, 300), (220, 300)).arc((220, 360), 360).curve((280, 300), (300, 300), (360, 300)).arc((360, 360), -360).curve((420, 300), (500, 300), (610, 280)).done(),
    ]


ENTRIES = _entries()
BONUS_PATHS = _bonus_paths()


def dive_path(kind, x, y, px, side, loop):
    """A diving attack from (x, y) at a fighter at px: a hook up and outward, a curving dive, then either out through the
    bottom (to come back in from the top) or, with loop, a loop near the bottom and a climb back.  side: -1 / 1."""
    s = side
    p = Path((x, y)).curve((x, y - 50), (x + s * 70, y - 50), (x + s * 70, y + 10))
    low = 560 if kind == "commander" else 600
    p.curve((x + s * 70, y + 200), (px - s * 120, low - 140), (px, low))
    if loop:
        p.arc((px + s * 55, low), 300 * s).curve((px + s * 80, low - 160), (x, y + 160), (x, y + 60))
    else:
        p.curve((px + s * 60, low + 120), (px + s * 90, H - 20), (px + s * 90, H + 40))
    return p.done()


def capture_path(x, y, px, side):
    """A commander's way down to where it shines its beam, above the fighter."""
    s = side
    return (Path((x, y)).curve((x, y - 40), (x + s * 60, y - 40), (x + s * 60, y + 20))
            .curve((x + s * 60, y + 180), (px, CAPTURE_Y - 140), (px, CAPTURE_Y)).done())


# ---- the things ----------------------------------------------------------------------------------------------------------------

class Enemy:
    _next = 0

    def __init__(self, kind, slot, sx, sy):
        Enemy._next += 1
        self.id, self.kind, self.slot = Enemy._next, kind, slot
        self.sx, self.sy = sx, sy                       # its place in the formation (before the sway)
        self.w, self.h = KINDS[kind][0]
        self.hp = KINDS[kind][1]
        self.x, self.y, self.angle = sx, -60.0, 90.0
        self.state = "waiting"          # waiting, enter, join, form, dive, beam, gone
        self.path, self.dist, self.speed = None, 0.0, 0.0
        self.wait, self.fire_at = 0.0, []
        self.group = None               # the commander leading it (an escort), or its escorts (a commander)
        self.captive = False            # a commander carrying a caught fighter
        self.beam_t, self.held, self.to_beam = 0.0, 0.0, False
        self.bonus_group = None
        self.exits = False              # its path takes it off the bottom: back in from the top afterwards

    @property
    def alive(self):
        return self.state != "gone"


class Shot:
    __slots__ = ("x", "y", "vx", "vy", "owner")

    def __init__(self, x, y, vx, vy, owner):
        self.x, self.y, self.vx, self.vy, self.owner = x, y, vx, vy, owner


class LunicaGame:
    """One game.  update(now, held) moves it on; the rest is read by lunica_view.py.  Sounds are collected in events
    (take_events()): "fire", "hit", "boss_hit", "boss_die", "die", "entry", "dive", "captured", "rescue", "docked",
    "start" (a new game), "stage", "bonus", "perfect", "extra", "over", and the loop "beam_on" / "beam_off".

    state: "attract", "intro" (STAGE n), "playing", "clear" (stage cleared), "summary" (a bonus stage's tally), "over".
    The fighter: self.ship is "ok", "gone" (destroyed: back after DESTROYED, when the middle is clear), "rising" (caught)."""

    def __init__(self, best=0, seed=None, attract=True):
        self.rng = random.Random(seed)
        self.best = best
        self.events = []
        self._last, self._acc = None, 0.0
        self.clock = 0.0
        self._both_before = True
        self.finished = False
        self.score, self.lives, self.stage = 0, LIVES, 1
        self.best_at_start = best
        self.state, self.timer = "attract", 0.0
        self.extras = list(EXTRA_AT)
        self._reset_player()
        self._new_stage(demo=True)
        if not attract:
            self.new_game()

    # ---- the course of a game ------------------------------------------------------------------------------------------

    def new_game(self):
        self.score, self.lives, self.stage = 0, LIVES, 1
        self.best_at_start = self.best
        self.extras = list(EXTRA_AT)
        self._reset_player()
        self._begin_stage(first=True)

    def _reset_player(self):
        self.px = W / 2
        self.ship = "ok"
        self.dual = False
        self.shield = 0.0
        self.ship_timer = 0.0
        self.rise = None                    # (commander, from x, from y, t) while a caught fighter rises
        self.rescued = None                 # [x, y] of a freed fighter on its way down to dock
        self._held_for = {"left": 0.0, "right": 0.0}
        self._fired = -1.0

    def _begin_stage(self, first=False):
        self.state, self.timer = "intro", FIRST_INTRO if first else STAGE_INTRO
        self.events.append("start" if first else "stage")       # a game's first stage: its opening tune
        self._new_stage()

    def _new_stage(self, demo=False):
        st = self.stage
        self.bonus = is_bonus(st) and not demo
        self.entry_speed = harder(st, 150, 190, 230)
        self.dive_speed = harder(st, 190, 250, 310)
        self.max_divers = round(harder(st, 2, 4, 6))
        self.shot_speed = harder(st, 240, 300, 360)
        self.attack_every = harder(st, 2.5, 1.7, 1.1)
        self.max_enemy_shots = round(harder(st, 4, 7, 11))
        self.aim = harder(st, 0.0, 0.4, 0.8)
        self.enemies, self.shots, self.enemy_shots, self.bursts = [], [], [], []
        self.stage_t = 0.0
        self.attack_timer = 3.0
        self.beam_on = False
        self.bonus_hits, self.bonus_groups = 0, [0] * 5
        slots = []
        for row, (kind, n) in enumerate(ROWS):
            for i in range(n):
                slots.append((kind, FORM_X + (i - (n - 1) / 2) * SPACING, FORM_TOP + row * SPACING))
        by_kind = {k: [s for s in slots if s[0] == k] for k in KINDS}
        order = [("scout", 8), ("commander", 4), ("interceptor", 4), ("interceptor", 8), ("interceptor", 4), ("scout", 4),
                 ("scout", 8)]
        groups, taken = [[] for _ in range(5)], {k: 0 for k in KINDS}
        plan = ((0, 0), (1, 1), (1, 2), (2, 3), (3, 4), (3, 5), (4, 6))
        for g, o in plan:
            kind, n = order[o]
            picks = sorted(by_kind[kind], key=lambda s: abs(s[1] - FORM_X))[taken[kind]:taken[kind] + n]
            taken[kind] += n
            groups[g] += picks
        for g, members in enumerate(groups):
            members.sort(key=lambda s: s[1])
            path = (BONUS_PATHS if self.bonus else ENTRIES)[(g + st) % 5]
            for i, (kind, sx, sy) in enumerate(members):
                e = Enemy(kind, len(self.enemies), sx, sy)
                left = i < len(members) / 2
                e.path = path if left else path.moved(0, mirror=True)
                e.wait = 0.8 + g * GROUP_GAP + (i % (len(members) // 2 or 1)) * MEMBER_GAP
                e.speed = self.entry_speed * ENTRY_PACE
                if self.bonus:
                    e.hp = 1                            # (in a bonus stage one hit does for any of them)
                e.bonus_group = g
                self.enemies.append(e)

    def take_events(self):
        events, self.events = self.events, []
        return events

    def loops(self):
        return ["beam"] if self.beam_on else []

    def summary(self):
        return "%d points, stage %d" % (self.score, self.stage)

    def ships(self):
        """The fighters' middles (x) now: one, or two side by side."""
        if self.ship != "ok":
            return []
        return [self.px, self.px + PLAYER_W] if self.dual else [self.px]

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
            self._held_for[b] = self._held_for[b] + dt if b in held else 0.0
        if self.state == "attract":
            self.timer += dt
            self._enemies(dt, demo=True)
            if self.stage_t > 22:                       # the demonstration: a new wave now and then
                self._new_stage(demo=True)
            if pressed:
                self.new_game()
            elif self.timer >= ATTRACT_IDLE:
                self.finished = True
            return
        if self.state == "over":
            self.timer += dt
            self._enemies(dt, demo=True)
            if pressed and self.timer >= OVER_WAIT:
                self.new_game()
            elif self.timer >= OVER_IDLE:
                self.finished = True
            return
        if self.state in ("intro", "clear", "summary"):
            self.timer -= dt
            if self.state == "intro":
                self._player(held, dt)
            self._bursts(dt)
            if self.timer <= 0:
                if self.state == "intro":
                    self.state = "playing"
                else:
                    self.stage += 1
                    self._begin_stage()
            return
        self._player(held, dt)
        self._enemies(dt)
        self._move_shots(dt)
        self._bursts(dt)
        self._after(dt)

    # ---- the fighter ---------------------------------------------------------------------------------------------------

    def _player(self, held, dt):
        if self.ship == "gone":
            self.ship_timer -= dt
            if self.ship_timer <= 0 and self.lives > 0 and self._clear_to_return():
                self.ship, self.px, self.shield = "ok", W / 2, SHIELD
            return
        if self.ship == "rising":
            self._rising(dt)
            return
        self.shield = max(0.0, self.shield - dt)
        if held == {"left", "right"}:                   # both: stop, and fire whenever it can
            if self.clock - self._fired >= SHOT_GAP:
                fired = False
                for i, x in enumerate(self.ships()):
                    if sum(1 for s in self.shots if s.owner == i) < SHOTS_EACH:
                        self.shots.append(Shot(x, PLAYER_Y - PLAYER_H / 2, 0.0, -SHOT_SPEED, i))
                        fired = True
                if fired:
                    self._fired = self.clock
                    self.events.append("fire")
            return
        width = PLAYER_W * (2 if self.dual else 1)
        if self._held_for["left"] >= ONE_BUTTON_AFTER and "right" not in held:
            self.px -= PLAYER_SPEED * dt
        elif self._held_for["right"] >= ONE_BUTTON_AFTER and "left" not in held:
            self.px += PLAYER_SPEED * dt
        self.px = max(PLAYER_W / 2, min(W - width + PLAYER_W / 2, self.px))

    def _clear_to_return(self):
        near = [e for e in self.enemies if e.alive and e.state in ("dive", "beam") and e.y > PLAYER_Y - 200]
        return not near and not any(abs(s.x - W / 2) < SAFE_X and s.y > PLAYER_Y - 120 for s in self.enemy_shots)

    def _lose_ship(self, which=None):
        """A fighter hit.  With two, only that one goes (the other carries on alone)."""
        if self.shield > 0:
            return
        x = self.ships()[which or 0]
        self.bursts.append([x, PLAYER_Y, 0.0, "ship"])
        self.events.append("die")
        if self.dual:
            self.dual = False
            if which == 0:
                self.px += PLAYER_W                     # the right-hand one is left
            return
        self.ship, self.ship_timer = "gone", DESTROYED
        self.lives -= 1
        self.shots = [s for s in self.shots if s.y < PLAYER_Y - 200]
        if self.lives <= 0:
            self._game_over()

    def _game_over(self):
        self.state, self.timer = "over", 0.0
        self.events.append("over")
        if self.beam_on:
            self.beam_on = False
            self.events.append("beam_off")

    # ---- the enemies ---------------------------------------------------------------------------------------------------

    def slot_xy(self, e):
        t = self.clock
        return e.sx + SWAY * math.sin(t * 2 * math.pi / 5), e.sy + BOB * math.sin(t * 2 * math.pi / 3)

    def _enemies(self, dt, demo=False):
        self.stage_t += dt
        for e in self.enemies:
            if e.state == "waiting":
                e.wait -= dt
                if e.wait <= 0:
                    e.state, e.dist = "enter", 0.0
                    if e.slot % 8 == 0 and not demo:
                        self.events.append("entry")
            if e.state in ("enter", "dive"):
                self._fly(e, dt, demo)
            elif e.state == "join":
                self._join(e, dt)
            elif e.state == "form":
                e.x, e.y = self.slot_xy(e)
                e.angle = 90.0
            elif e.state == "beam":
                self._beam(e, dt)
        if self.state == "playing" and not self.bonus and not demo:
            self._attacks(dt)

    def _fly(self, e, dt, demo):
        e.dist += e.speed * dt
        e.x, e.y, e.angle = e.path.at(e.dist)
        while e.fire_at and e.dist >= e.fire_at[0]:
            e.fire_at.pop(0)
            self._enemy_fire(e)
        if e.dist >= e.path.length:
            if self.bonus and e.state == "enter":       # a bonus stage's enemies just leave
                e.state = "gone"
                return
            if e.exits:                                 # out of the bottom: back in from the top, over its place
                e.x, e.y = self.slot_xy(e)[0], -40.0
                e.exits = False
            if e.to_beam:
                e.to_beam = False
                e.state, e.beam_t = "beam", 0.0
                self.beam_on = True
                self.events.append("beam_on")
                return
            e.state = "join"
            if e.group and e.kind != "commander":       # the formation broken up: an escort goes home on its own
                e.group = None
            if e.kind == "commander":
                e.group = None

    def _join(self, e, dt):
        tx, ty = self.slot_xy(e)
        dx, dy = tx - e.x, ty - e.y
        d = math.hypot(dx, dy)
        step = max(self.entry_speed, 150) * dt
        if d <= step:
            e.x, e.y, e.state, e.angle = tx, ty, "form", 90.0
            return
        e.x += dx / d * step
        e.y += dy / d * step
        want = math.degrees(math.atan2(dy, dx)) if d > 30 else 90.0
        turn = (want - e.angle + 180) % 360 - 180
        e.angle += max(-400 * dt, min(400 * dt, turn))

    def _attacks(self, dt):
        """Now and then one, two or three leave the formation to dive (fewer when firing would leave no way out)."""
        if any(e.state in ("waiting", "enter") for e in self.enemies) and self.stage_t < 12:
            return
        divers = [e for e in self.enemies if e.state in ("dive", "beam")]
        home = [e for e in self.enemies if e.state == "form"]
        if not home:
            return
        quick = 0.5 if len([e for e in self.enemies if e.alive]) <= 3 else 1.0     # the last few: no dawdling
        self.attack_timer -= dt
        if self.attack_timer > 0 or len(divers) >= self.max_divers:
            return
        self.attack_timer = self.attack_every * self.rng.uniform(0.8, 1.2) * quick
        e = self.rng.choice(home)
        if self.ship != "ok":
            return
        commanders = [c for c in home if c.kind == "commander"]
        can_capture = (not self.dual and self.ship == "ok" and self.rescued is None and not self.beam_on
                       and not any(c.captive for c in self.enemies) and self.stage >= 1)
        if commanders and self.rng.random() < 0.35:
            e = self.rng.choice(commanders)
            if can_capture and not e.captive and self.rng.random() < 0.4:
                return self._capture_dive(e)
            return self._dive(e, escorts=True)
        self._dive(e, escorts=False)

    def _dive(self, e, escorts):
        side = -1 if e.sx < FORM_X else 1
        loop = e.kind != "scout" and self.rng.random() < 0.6
        px = self.px if self.ship == "ok" else W / 2
        group = [e]
        if escorts:                                     # a commander may bring one or two from the row below
            below = [o for o in self.enemies if o.state == "form" and o.kind == "interceptor"
                     and abs(o.sy - (e.sy + SPACING)) < 1 and abs(o.sx - e.sx) <= SPACING * 1.5]
            group += self.rng.sample(below, min(len(below), self.rng.randint(0, 2)))
            e.group = group[1:]
        elif e.kind == "interceptor" and self.rng.random() < 0.5:      # or two interceptors side by side
            pair = [o for o in self.enemies if o.state == "form" and o.kind == "interceptor" and o.sy == e.sy
                    and abs(o.sx - e.sx - side * SPACING) < 1]
            group += pair[:1]
        base = dive_path(e.kind, e.x, e.y, px, side, loop)
        for o in group:
            o.state, o.dist, o.speed = "dive", 0.0, self.dive_speed
            o.path = base.moved(o.x - e.x, o.y - e.y)
            o.exits = not loop
            o.fire_at = sorted(self.rng.uniform(0.25, 0.55) * o.path.length for _ in range(self.rng.randint(1, 2)))
            if o is not e:
                o.group = e
        self.events.append("dive")

    def _capture_dive(self, e):
        side = -1 if e.sx < FORM_X else 1
        e.state, e.dist, e.speed = "dive", 0.0, self.dive_speed * 0.8
        e.path = capture_path(e.x, e.y, self.px, side)
        e.to_beam, e.exits, e.fire_at = True, False, []
        self.events.append("dive")

    def _beam(self, e, dt):
        """Hovering, beam down: a fighter under it long enough is caught."""
        e.beam_t += dt
        e.angle = 90.0
        if self.ship == "ok" and self.shield <= 0 and not self.dual and abs(self.px - e.x) < self.beam_half(e):
            e.held += dt
            if e.held >= BEAM_HOLD and self.rise is None:
                self._caught(e)
                return
        else:
            e.held = 0.0
        if e.beam_t >= BEAM_SECONDS:
            self._beam_end(e)

    def beam_half(self, e):
        grow = min(1.0, e.beam_t / 0.6)                 # the beam opens out at first
        return BEAM_HALF * grow

    def _beam_end(self, e):
        e.state = "join"
        e.held = 0.0
        if self.beam_on:
            self.beam_on = False
            self.events.append("beam_off")

    def _caught(self, e):
        self.ship = "rising"
        self.rise = [e, self.px, float(PLAYER_Y), 0.0]
        e.state, e.beam_t = "beam", BEAM_SECONDS - 0.01  # it stays until the fighter is up with it
        self.events.append("captured")

    def _rising(self, dt):
        e, x0, y0, t = self.rise
        t += dt
        self.rise[3] = t
        e.beam_t = min(e.beam_t, BEAM_SECONDS - 0.01)
        if not e.alive:                                 # its captor shot down while it rose: back down, free
            self.ship, self.rise = "ok", None
            return
        if t >= RISE_SECONDS:
            e.captive = True
            self.rise = None
            self._beam_end(e)
            self.ship, self.ship_timer = "gone", DESTROYED
            self.lives -= 1
            if self.lives <= 0:
                self._game_over()

    def captive_xy(self, e):
        """A caught fighter rides just above its captor."""
        return e.x, e.y - e.h / 2 - PLAYER_H / 2 - 2

    def rising_xy(self):
        e, x0, y0, t = self.rise
        k = min(1.0, t / RISE_SECONDS)
        tx, ty = self.captive_xy(e)
        return x0 + (tx - x0) * k, y0 + (ty - y0) * k, t * 540

    # ---- shots ---------------------------------------------------------------------------------------------------------

    def _enemy_fire(self, e):
        if len(self.enemy_shots) >= self.max_enemy_shots or e.y > PLAYER_Y - 150 or e.y < 0 or self.ship != "ok":
            return
        t = (PLAYER_Y - e.y) / self.shot_speed
        vx = max(-110.0, min(110.0, (self.px - e.x) / t * self.aim))
        self.enemy_shots.append(Shot(e.x, e.y + e.h / 2, vx, self.shot_speed, -1))

    def _move_shots(self, dt):
        for s in list(self.shots):
            y0 = s.y
            s.y += s.vy * dt
            if s.y < -SHOT_H:
                self.shots.remove(s)
                continue
            if self._shot_hits(s, y0):
                self.shots.remove(s)
        for s in list(self.enemy_shots):
            s.x += s.vx * dt
            s.y += s.vy * dt
            if s.y > H + 10:
                self.enemy_shots.remove(s)
                continue
            for i, x in enumerate(self.ships()):
                if abs(s.x - x) < PLAYER_W / 2 - 3 and abs(s.y - PLAYER_Y) < PLAYER_H / 2 - 2:
                    self.enemy_shots.remove(s)
                    self._lose_ship(i)
                    break

    def _shot_hits(self, s, y0):
        """The player's shot, swept from y0 up to s.y, against the enemies and any caught fighter."""
        top, bottom = s.y - SHOT_H / 2, y0 + SHOT_H / 2
        for e in self.enemies:
            if not e.alive or e.state == "waiting":
                continue
            if e.captive:
                cx, cy = self.captive_xy(e)
                if abs(s.x - cx) < PLAYER_W / 2 and top < cy + PLAYER_H / 2 and bottom > cy - PLAYER_H / 2:
                    e.captive = False                   # the caught fighter, shot: lost
                    self.bursts.append([cx, cy, 0.0, "ship"])
                    self.events.append("die")
                    return True
            if abs(s.x - e.x) < e.w / 2 + SHOT_W / 2 and top < e.y + e.h / 2 and bottom > e.y - e.h / 2:
                self._hit(e)
                return True
        return False

    def _hit(self, e):
        e.hp -= 1
        if e.hp > 0:
            self.events.append("boss_hit")
            return
        attacking = e.state in ("dive", "beam", "join")
        if self.bonus:
            self._add(BONUS_HIT)
            self.bonus_hits += 1
            self.bonus_groups[e.bonus_group] += 1
        elif e.kind == "commander" and e.state == "dive":
            with_it = [o for o in (e.group if isinstance(e.group, list) else []) if o.alive and o.state == "dive" and o.group is e]
            self._add(ESCORTED[min(2, len(with_it))])
        else:
            self._add(KINDS[e.kind][2][1 if attacking else 0])
        if isinstance(e.group, list):                   # a commander's escorts carry on, each on its own
            for o in e.group:
                if o.group is e:
                    o.group = None
        if e.captive:
            self._free(e)
        if self.beam_on and e.state == "beam":
            self.beam_on = False
            self.events.append("beam_off")
        e.state = "gone"
        self.bursts.append([e.x, e.y, 0.0, "boss" if e.kind == "commander" else "enemy"])
        self.events.append("boss_die" if e.kind == "commander" else "hit")

    def _free(self, e):
        """Its captor shot down: diving, the caught fighter comes home (two fighters); in the formation, it is lost."""
        e.captive = False
        x, y = self.captive_xy(e)
        if e.state == "dive" and self.ship == "ok" and not self.dual:
            self.rescued = [x, y]
            self.events.append("rescue")
        else:
            self.bursts.append([x, y, 0.0, "ship"])

    def _add(self, points):
        self.score += points
        self.best = max(self.best, self.score)
        while self.extras and self.score >= self.extras[0]:
            self.extras.pop(0)
            if not self.extras:
                self.extras.append(self.score - self.score % EXTRA_EVERY + EXTRA_EVERY)
            if self.lives < MAX_LIVES:
                self.lives += 1
                self.events.append("extra")

    def _bursts(self, dt):
        for b in self.bursts:
            b[2] += dt
        self.bursts = [b for b in self.bursts if b[2] < (0.7 if b[3] == "ship" else 0.3)]

    # ---- after each step: collisions, a freed fighter, the end of a stage --------------------------------------------

    def _after(self, dt):
        if self.rescued is not None:
            self._dock(dt)
        if not self.bonus:
            for e in self.enemies:                       # a diving enemy into the fighter: both gone
                if e.state not in ("dive", "join", "beam", "enter"):
                    continue
                for i, x in enumerate(self.ships()):
                    if abs(e.x - x) < (e.w + PLAYER_W) / 2 * 0.7 and abs(e.y - PLAYER_Y) < (e.h + PLAYER_H) / 2 * 0.7:
                        if self.shield <= 0:
                            if e.captive:
                                e.captive = False
                            e.state = "gone"
                            self.bursts.append([e.x, e.y, 0.0, "enemy"])
                            self._lose_ship(i)
                        break
        if self.state != "playing":
            return
        if all(not e.alive for e in self.enemies) and self.rise is None:
            self.enemy_shots = []
            if self.beam_on:
                self.beam_on = False
                self.events.append("beam_off")
            if self.bonus:
                groups = sum(1 for n in self.bonus_groups if n == 8)
                self._add(groups * BONUS_GROUP)
                perfect = self.bonus_hits == len(self.enemies)
                if perfect:
                    self._add(BONUS_PERFECT)
                self.tally = (self.bonus_hits, len(self.enemies), groups * BONUS_GROUP, BONUS_PERFECT if perfect else 0,
                              self.bonus_hits * BONUS_HIT + groups * BONUS_GROUP + (BONUS_PERFECT if perfect else 0))
                self.state, self.timer = "summary", BONUS_SUMMARY
                self.events.append("perfect" if perfect else "bonus")
            else:
                self.state, self.timer = "clear", CLEAR

    def _dock(self, dt):
        if self.ship != "ok":                           # no fighter to dock with: it is lost
            self.rescued = None
            return
        x, y = self.rescued
        right = self.px + PLAYER_W <= W - PLAYER_W / 2
        tx = self.px + PLAYER_W if right else self.px - PLAYER_W
        dx, dy = tx - x, PLAYER_Y - y
        d = math.hypot(dx, dy)
        step = 260 * dt
        if d <= step:
            self.rescued = None
            self.dual = True
            if not right:
                self.px -= PLAYER_W
            self.events.append("docked")
            return
        self.rescued = [x + dx / d * step, y + dy / d * step]
