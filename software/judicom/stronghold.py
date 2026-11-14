"""Stellar Stronghold, on the hidden menu (judicom/maintenance.py).

In the middle of space, a cannon behind three rings of shield, each ring twelve segments, each ring turning its own way at
its own speed.  Shoot gaps through the rings (two hits to a segment) and get a shot through all three to the cannon: then a
bigger, quicker stronghold.  But knock out every segment of a ring and it grows back; three mines hunt the ship; and wherever
the gaps line up, the cannon can shoot out at it.

The ship and its buttons are Meteoroids' (meteor.Pilot): Left / Right turn, both tapped fire, both held thrust.

The world is meteor's: W x H, wrapping at every edge (the stronghold stays in the middle and does not wrap), y down, angles in
degrees with clockwise positive, fixed steps of TICK.  Shots move at most STEP pixels between checks, against where each
segment really is at that moment, so a shot gets to the cannon only through a real gap, and the cannon only fires through one.
No pygame here: it runs (and is tested) anywhere.
"""
import math
import random

from . import meteor as m
from .meteor import H, TICK, W, Pilot, Thing, near

CX, CY = W / 2, H / 2                               # the stronghold
START_Y = CY + 235                                  # the ship starts below it, facing it
RINGS = ((145, 1, "outer"), (105, -1, "middle"), (65, 1, "inner"))     # radius, turning way (1 = clockwise), name
SEGMENTS, SEG_SPAN = 12, 27.0                       # 12 segments a ring, each 27 of its 30 degrees: narrow gaps between
RING_HALF = 4                                       # a segment's half-thickness
SEG_HITS = 2
REGROW = 0.75                                       # a ring shot right away grows back after this long
CORE_R = 17
STEP = 2.0                                          # a shot moves at most this far between checks
SHIP_R = 11
SHOTS, SHOT_LIFE, SHOT_SPEED, MAX_SPEED = 5, 1.2, 500.0, 380.0
MINE_R, MINES = 7, 3
MINE_ACCEL, MINE_TURN, MINE_START_SPEED = 60.0, 110.0, 30.0     # (gentler than the first try: they were too eager)
MINE_AGAIN = (8.0, 12.0)                            # a mine shot down is replaced after this long
MINE_FIRST = (2.0, 5.0, 8.0)                        # a round's three mines appear this long after it starts
MINE_APPEAR = 0.6                                   # a new mine grows in, just outside the rings, over this long
MINE_LEAN = 60                                      # each comes at the ship leaning this far off to its own side
CANNON_SHOT_R, CANNON_SHOT_LIFE = 6, 2.0
POINTS = {"hit": 10, "segment": 50, "core": 1000}
LIVES, DESTROYED, SHIELD, SAFE_R = 3, 1.5, 2.0, 110
PATROL = (CX, CY - 240)                             # with no ship about, the mines go round over here: across from the start
FORCE_BACK = 4.0                                    # still not clear this long after a new ship is due: mines there go home
BOOM = 2.5                                          # the stronghold blowing up, before the next one
OVER_WAIT, OVER_IDLE, ATTRACT_IDLE = 1.0, 30.0, 60.0


def harder(round_, at1, at5, at10):
    """A setting for this round: at1 in round 1, at5 in round 5, at10 from round 10 on, in a straight line between."""
    if round_ <= 5:
        return at1 + (at5 - at1) * (round_ - 1) / 4
    return at5 + (at10 - at5) * (min(round_, 10) - 5) / 5


class Ring:
    def __init__(self, radius, way, name):
        self.r, self.way, self.name = radius, way, name
        self.angle = 0.0
        self.speed = 0.0
        self.hp = [SEG_HITS] * SEGMENTS
        self.flash = [0.0] * SEGMENTS                   # a segment just hit lights up for a moment
        self.regrow = 0.0                               # > 0: gone, growing back

    def segment_at(self, angle, slack=0.0):
        """The segment covering this direction (degrees), or None (a gap, or a segment that is gone).  slack: degrees more
        at each end (for something with a size)."""
        if self.regrow > 0:
            return None
        local = (angle - self.angle) % 360
        pitch = 360 / SEGMENTS
        i = int(local // pitch)
        for k in (i, (i - 1) % SEGMENTS, (i + 1) % SEGMENTS):        # this one, and its neighbours at either end
            if self.hp[k] <= 0:
                continue
            into = (local - k * pitch + 180) % 360 - 180            # from the segment's start, -180 .. 180
            if -slack <= into <= SEG_SPAN + slack:
                return k
        return None

    def angle_at(self, later):
        return self.angle + self.way * self.speed * later


class StrongholdGame(Pilot):
    """One game.  update(now, held) moves it on; the rest is read by stronghold_view.py.  Sounds are collected in events
    (take_events()): "fire", "hit", "segment", "regrow", "cannon", "mine", "mine_die", "die", "boom", "round", "over", and
    the loop "thrust_on" / "thrust_off".

    state: "attract" (the title, the stronghold turning), "playing", "destroyed", "boom" (the stronghold blowing up), "over"."""
    SHOTS, SHOT_LIFE, SHOT_SPEED, SHOT_R, MAX_SPEED = SHOTS, SHOT_LIFE, SHOT_SPEED, 2.0, MAX_SPEED

    def __init__(self, best=0, seed=None, attract=True):
        self.rng = random.Random(seed)
        self.best = best
        self.events = []
        self._last, self._acc = None, 0.0
        self.clock, self._fired_at = 0.0, -1.0
        self._both_before = True
        self.finished = False
        self.score, self.lives, self.round = 0, LIVES, 1
        self.best_at_start = best
        self.state, self.timer = "attract", 0.0
        self.input, self.both_time, self.thrusting = "wait", 0.0, False
        self._new_round()
        if not attract:
            self.new_game()

    def new_game(self):
        self.state, self.timer = "playing", 0.0
        self.score, self.lives, self.round = 0, LIVES, 1
        self.best_at_start = self.best
        self.input = "wait"
        self._new_round()

    def _new_round(self):
        r = self.round
        self.rings = [Ring(*spec) for spec in RINGS]
        for ring, (a1, a5, a10) in zip(self.rings, ((15, 20, 25), (22, 28, 35), (30, 38, 45))):
            ring.speed = harder(r, a1, a5, a10)
        self.mine_speed = harder(r, 95, 120, 145)
        self.cannon_every = harder(r, 1.5, 1.2, 0.9)
        self.cannon_speed = harder(r, 320, 370, 420)
        self.cannon_turn = harder(r, 120, 145, 170)
        self.cannon_lead = harder(r, 0.0, 0.3, 0.5)     # how much it allows for the ship's drift (never all of it)
        self.cannon_angle, self.cannon_wait = 90.0, 1.5
        self.mines, self.shots, self.cannon_shots, self.bits = [], [], [], []
        self.mine_wait = list(MINE_FIRST)               # the three mines come one after another
        self.mine_ping = 1.0
        self._place_ship()

    def _place_ship(self):
        self.ship = Thing("ship", CX, START_Y, r=SHIP_R)
        self.ship.angle = -90.0
        self.shield = 0.0
        if self.thrusting:
            self.thrusting = False
            self.events.append("thrust_off")

    def take_events(self):
        events, self.events = self.events, []
        return events

    def loops(self):
        return ["thrust"] if self.thrusting else []

    def summary(self):
        return "%d points, round %d" % (self.score, self.round)

    # ---- time --------------------------------------------------------------------------------------------------------------

    def update(self, now, held):
        if self._last is None:
            self._last = now
        self._acc += max(0.0, now - self._last)
        self._last = now
        steps = 0
        while self._acc >= TICK and steps < m.MAX_STEPS:
            self.tick(held)
            self._acc -= TICK
            steps += 1
        if steps == m.MAX_STEPS:
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
            self._turn_rings(dt)
            if pressed:
                self.new_game()
            elif self.timer >= ATTRACT_IDLE:
                self.finished = True
            return
        if self.state == "over":
            self.timer += dt
            self._turn_rings(dt)
            if pressed and self.timer >= OVER_WAIT:
                self.new_game()
            elif self.timer >= OVER_IDLE:
                self.finished = True
            return
        if self.state == "boom":
            self.timer -= dt
            self._bits(dt)
            if self.timer <= 0:
                self.round += 1
                self._new_round()
                self.state = "playing"
                self.input = "wait" if held else "none"
                self.events.append("round")
            return
        if self.state == "destroyed":
            self.timer -= dt
            self._world(dt, ship=False)
            if self.timer <= 0:
                if self.lives <= 0:
                    self.state, self.timer = "over", 0.0
                    self.events.append("over")
                else:
                    if self.timer < -FORCE_BACK:          # (they should have gone: send any still there back inside)
                        for mine in [mn for mn in self.mines if math.hypot(*near(CX, START_Y, mn.x, mn.y)) <= SAFE_R]:
                            self.mines.remove(mine)
                            self._mine_later()
                        self.cannon_shots = []
                    if self._safe():
                        self.state = "playing"
                        self._place_ship()
                        self.shield = SHIELD
                        self.input = "wait" if held else "none"
            return
        self._controls(held, both, dt)
        self._world(dt, ship=True)

    def _safe(self):
        return all(math.hypot(*near(CX, START_Y, t.x, t.y)) > SAFE_R for t in self.mines + self.cannon_shots)

    # ---- one step ----------------------------------------------------------------------------------------------------------

    def _world(self, dt, ship):
        self._turn_rings(dt)
        if ship:
            self._fly(dt)
            self.shield = max(0.0, self.shield - dt)
        self._move_shots(dt)
        if self.state == "boom":
            return
        self._cannon(dt)
        self._move_cannon_shots(dt)
        self._mines(dt)
        self._bits(dt)
        if ship and self.state == "playing":
            self._ship_hits()

    def _turn_rings(self, dt):
        for ring in self.rings:
            ring.angle = (ring.angle + ring.way * ring.speed * dt) % 360
            ring.flash = [max(0.0, f - dt) for f in ring.flash]
            if ring.regrow > 0:
                ring.regrow -= dt
                if ring.regrow <= 0:
                    ring.regrow = 0.0
                    ring.hp = [SEG_HITS] * SEGMENTS
                    self.events.append("regrow")

    def _bits(self, dt):
        for b in self.bits:
            b.move(dt)
            b.life -= dt
        self.bits = [b for b in self.bits if b.life > 0]

    def _burst(self, x, y, n, speed=70.0, life=0.5):
        for _ in range(n):
            a, v = self.rng.uniform(0, 2 * math.pi), self.rng.uniform(0.4, 1.0) * speed
            b = Thing("bit", x, y, math.cos(a) * v, math.sin(a) * v)
            b.life = life
            self.bits.append(b)

    # ---- what a point hits -------------------------------------------------------------------------------------------------

    def ring_hit(self, x, y, r, later=0.0):
        """The (ring, segment) a thing of radius r at x, y touches (with the rings as they will be `later` seconds on), or
        None.  Nearest the outside first: what a shot coming in meets first."""
        dx, dy = x - CX, y - CY
        d = math.hypot(dx, dy)
        if d < 1:
            return None
        angle = math.degrees(math.atan2(dy, dx))
        for ring in self.rings:
            if abs(d - ring.r) <= RING_HALF + r:
                slack = math.degrees(r / d)
                saved = ring.angle
                ring.angle = ring.angle_at(later) % 360
                k = ring.segment_at(angle, slack)
                ring.angle = saved
                if k is not None:
                    return ring, k
        return None

    def _move_shots(self, dt):
        for s in list(self.shots):
            s.life -= dt
            if s.life <= 0:
                self.shots.remove(s)
                continue
            n = max(1, math.ceil(math.hypot(s.vx, s.vy) * dt / STEP))
            for _ in range(n):                          # a little at a time: the first thing in its way is what it hits
                s.x, s.y = (s.x + s.vx * dt / n) % W, (s.y + s.vy * dt / n) % H
                if self._shot_hits(s):
                    self.shots.remove(s)
                    break

    def _shot_hits(self, s):
        hit = self.ring_hit(s.x, s.y, s.r)
        if hit is not None:
            self._damage(*hit)
            return True
        if math.hypot(s.x - CX, s.y - CY) <= CORE_R + s.r and self.state == "playing":
            self._core_down()
            return True
        for mine in self.mines:
            if math.hypot(*near(s.x, s.y, mine.x, mine.y)) <= MINE_R + s.r:
                self.mines.remove(mine)
                self._burst(mine.x, mine.y, 6)
                self.events.append("mine_die")
                self._mine_later()
                return True
        for c in self.cannon_shots:
            if math.hypot(*near(s.x, s.y, c.x, c.y)) <= CANNON_SHOT_R + s.r:
                self.cannon_shots.remove(c)
                self._burst(c.x, c.y, 4)
                return True
        return False

    def _damage(self, ring, k):
        ring.hp[k] -= 1
        ring.flash[k] = 0.15
        a = math.radians(ring.angle + (k + 0.5) * 360 / SEGMENTS)
        x, y = CX + math.cos(a) * ring.r, CY + math.sin(a) * ring.r
        if ring.hp[k] > 0:
            self._add(POINTS["hit"])
            self.events.append("hit")
            return
        self._add(POINTS["segment"])
        self._burst(x, y, 5, speed=50, life=0.4)
        self.events.append("segment")
        if not any(ring.hp):                            # the whole ring gone: it grows back
            ring.regrow = REGROW

    def _add(self, points):
        self.score += points
        self.best = max(self.best, self.score)

    # ---- the cannon --------------------------------------------------------------------------------------------------------

    def _cannon(self, dt):
        s = self.ship
        dx, dy = s.x - CX, s.y - CY                     # (the stronghold does not wrap: straight at the ship)
        t = math.hypot(dx, dy) / self.cannon_speed
        want = math.degrees(math.atan2(dy + s.vy * t * self.cannon_lead, dx + s.vx * t * self.cannon_lead))
        turn = (want - self.cannon_angle + 180) % 360 - 180
        step = self.cannon_turn * dt
        self.cannon_angle = (self.cannon_angle + max(-step, min(step, turn))) % 360
        self.cannon_wait -= dt
        if self.cannon_wait > 0 or abs(turn) > 6 or self.state != "playing":
            return
        if not self.clear_path(self.cannon_angle, self.cannon_speed, CANNON_SHOT_R):
            self.cannon_wait = 0.1                      # blocked: look again in a moment
            return
        a = math.radians(self.cannon_angle)
        shot = Thing("cannon_shot", CX + math.cos(a) * (CORE_R + 4), CY + math.sin(a) * (CORE_R + 4),
                     math.cos(a) * self.cannon_speed, math.sin(a) * self.cannon_speed, CANNON_SHOT_R)
        shot.life = CANNON_SHOT_LIFE
        self.cannon_shots.append(shot)
        self.cannon_wait = self.cannon_every
        self.events.append("cannon")

    def clear_path(self, angle, speed, r):
        """Would a shot of radius r fired from the middle now, this way, at this speed, get out past all three rings (as
        they will have turned by the time it reaches each)?"""
        a = math.radians(angle)
        d = CORE_R + 4
        while d < RINGS[0][0] + RING_HALF + r + 1:
            if self.ring_hit(CX + math.cos(a) * d, CY + math.sin(a) * d, r, later=(d - CORE_R - 4) / speed):
                return False
            d += STEP
        return True

    def _move_cannon_shots(self, dt):
        for c in list(self.cannon_shots):
            c.move(dt)
            c.life -= dt
            if c.life <= 0:
                self.cannon_shots.remove(c)

    # ---- the mines ---------------------------------------------------------------------------------------------------------

    def _mine_later(self):
        self.mine_wait.append(self.rng.uniform(*MINE_AGAIN))

    def _mines(self, dt):
        """Mines appear just outside the rings and hunt the ship, round the walls: an intact segment stops a mine as it
        stops a shot (it slides along it), so a mine gets through the rings only where they have been shot open."""
        s = self.ship
        hunting = self.state == "playing"               # no ship (just lost): they leave the start clear for the next one
        tx, ty = (s.x, s.y) if hunting else PATROL
        for i in range(len(self.mine_wait) - 1, -1, -1):
            self.mine_wait[i] -= dt
            if self.mine_wait[i] <= 0 and len(self.mines) < MINES:
                del self.mine_wait[i]
                away = math.atan2(CY - ty, CX - tx) + self.rng.uniform(-1.0, 1.0)     # round the far side from the ship
                d = RINGS[0][0] + RING_HALF + MINE_R + 6
                mine = Thing("mine", CX + math.cos(away) * d, CY + math.sin(away) * d,
                             math.cos(away) * MINE_START_SPEED, math.sin(away) * MINE_START_SPEED, MINE_R)
                mine.side = self.rng.uniform(-1, 1)     # each leans off to its own side: they spread out
                self.mines.append(mine)
        for mine in self.mines:
            mine.t += dt
            if mine.t < MINE_APPEAR:                    # still growing in: it drifts
                mine.x, mine.y = mine.x + mine.vx * dt, mine.y + mine.vy * dt
                continue
            dx, dy = near(mine.x, mine.y, tx, ty)
            dist = math.hypot(dx, dy) or 1.0
            off = MINE_LEAN * mine.side * min(1.0, dist / 200)      # aim a little to one side, less so as it closes in
            dx, dy = dx - dy / dist * off, dy + dx / dist * off
            heading = math.degrees(math.atan2(mine.vy, mine.vx))
            want = math.degrees(math.atan2(dy, dx))
            turn = (want - heading + 180) % 360 - 180
            heading += max(-MINE_TURN * dt, min(MINE_TURN * dt, turn))
            speed = min(self.mine_speed, math.hypot(mine.vx, mine.vy) + MINE_ACCEL * dt)
            h = math.radians(heading)
            mine.vx, mine.vy = math.cos(h) * speed, math.sin(h) * speed
            self._mine_step(mine, dt)
        if self.mines:
            self.mine_ping -= dt
            if self.mine_ping <= 0:
                self.mine_ping = 1.2
                self.events.append("mine")

    def _mine_step(self, mine, dt):
        """Move a mine, but not into a segment: into a wall it slides along it; a segment turning onto it pushes it off."""
        rx, ry = mine.x - CX, mine.y - CY
        rd = math.hypot(rx, ry) or 1.0
        ux, uy = rx / rd, ry / rd
        hit = self.ring_hit(mine.x, mine.y, MINE_R)
        if hit is not None:                             # a segment has turned onto it: off the ring, back the way it came
            ring = hit[0]
            clear = RING_HALF + MINE_R + 1
            rd = ring.r - clear if rd < ring.r else ring.r + clear
            mine.x, mine.y = CX + ux * rd, CY + uy * rd
        nx, ny = mine.x + mine.vx * dt, mine.y + mine.vy * dt
        hit = self.ring_hit(nx, ny, MINE_R)
        if hit is not None:
            ring = hit[0]
            radial = mine.vx * ux + mine.vy * uy
            if (rd < ring.r) == (radial > 0):           # heading into the wall: keep only the part along it
                mine.vx -= radial * ux
                mine.vy -= radial * uy
            nx, ny = mine.x + mine.vx * dt, mine.y + mine.vy * dt
            if self.ring_hit(nx, ny, MINE_R) is not None:
                nx, ny = mine.x, mine.y                 # (a corner: it waits for the ring to turn)
        mine.x, mine.y = nx % W, ny % H

    # ---- the ship hit ------------------------------------------------------------------------------------------------------

    def _ship_hits(self):
        if self.shield > 0:
            return
        s = self.ship
        if math.hypot(s.x - CX, s.y - CY) < CORE_R + SHIP_R or self.ring_hit(s.x, s.y, SHIP_R) is not None:
            return self._lost()
        for mine in self.mines:
            if math.hypot(*near(s.x, s.y, mine.x, mine.y)) < SHIP_R + MINE_R:
                self.mines.remove(mine)
                self._mine_later()
                return self._lost()
        for c in self.cannon_shots:
            if math.hypot(*near(s.x, s.y, c.x, c.y)) < SHIP_R + CANNON_SHOT_R:
                self.cannon_shots.remove(c)
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

    def _core_down(self):
        """The cannon hit: the stronghold blows up, its rings fly apart; points, a ship more, and the next one after BOOM."""
        self.state, self.timer = "boom", BOOM
        self._add(POINTS["core"])
        self.lives += 1
        self.mines, self.cannon_shots = [], []
        if self.thrusting:
            self.thrusting = False
            self.events.append("thrust_off")
        self.input = "wait"
        self.events.append("boom")
        self.flying = []                                # the segments left, flying outward
        for ring in self.rings:
            for k, hp in enumerate(ring.hp):
                if hp > 0 and ring.regrow <= 0:
                    self.flying.append((ring.r, ring.angle + k * 360 / SEGMENTS, ring.name, self.rng.uniform(-90, 90)))
        self._burst(CX, CY, 24, speed=160, life=1.2)
