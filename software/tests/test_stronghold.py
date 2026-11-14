"""Stellar Stronghold (judicom/stronghold.py): the acceptance list it was built to, the rings, the cannon, the mines."""
import math
import tempfile
import unittest
from pathlib import Path

from judicom import config, game_sound
from judicom import stronghold as sh
from judicom.game import Session
from judicom.meteor import Thing
from judicom.stronghold import CX, CY, StrongholdGame

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def seconds(s):
    return int(round(s / sh.TICK))


def run(g, steps, held=()):
    for _ in range(steps):
        g.tick(held)


def game():
    """A game going, the buttons seen up, no mines out yet, the cannon quiet unless a test wants it."""
    g = StrongholdGame(seed=1, attract=False)
    g.tick()
    g.mine_wait = [10 ** 6]
    g.cannon_wait = 10 ** 6
    return g


def tap(g):
    run(g, seconds(0.15), BOTH)
    g.tick()


def still(g):
    for ring in g.rings:
        ring.speed = 0.0


def aim_at(g, x, y):
    g.ship.angle = math.degrees(math.atan2(y - g.ship.y, x - g.ship.x))


def seg_mid(g, ring, k):
    """The middle of segment k of a ring, now."""
    a = math.radians(ring.angle + k * 30 + sh.SEG_SPAN / 2)
    return CX + math.cos(a) * ring.r, CY + math.sin(a) * ring.r


class TheShip(unittest.TestCase):                       # acceptance 1-7, 32 (the controls are Meteoroids'; a few checks)
    def test_starts_below_facing_up_and_still(self):
        g = game()
        s = g.ship
        self.assertEqual((s.x, s.y, s.angle, s.vx, s.vy), (CX, CY + 235, -90.0, 0.0, 0.0))

    def test_turns_fires_on_a_tap_thrusts_on_a_hold_and_drifts(self):
        g = game()
        run(g, seconds(0.5), {"left"})
        self.assertAlmostEqual(g.ship.angle, -90 - 120, delta=1)
        run(g, seconds(0.5), {"right"})
        g.ship.angle = 180.0                            # (facing away from the stronghold)
        tap(g)
        self.assertEqual(len(g.shots), 1)
        run(g, seconds(1.0), BOTH)
        g.tick()
        self.assertEqual(len(g.shots), 1)               # the hold was thrust, not a shot
        v = g.ship.vx
        self.assertLess(v, -50)
        run(g, seconds(0.5))
        self.assertEqual(g.ship.vx, v)

    def test_top_speed_380_and_five_shots(self):
        g = game()
        g.ship.angle = 180.0
        run(g, seconds(5), BOTH)
        self.assertAlmostEqual(math.hypot(g.ship.vx, g.ship.vy), 380, delta=0.5)
        g2 = game()
        g2.ship.angle = 180.0
        for _ in range(8):
            tap(g2)
        self.assertEqual(len(g2.shots), 5)

    def test_wraps(self):
        g = game()
        g.ship.x, g.ship.y, g.ship.vx = sh.W - 2, 30.0, 200.0
        run(g, seconds(0.1))
        self.assertLess(g.ship.x, 30)

    def test_only_two_buttons(self):
        g = game()
        run(g, seconds(1), {"up", "a"})
        self.assertEqual((g.ship.angle, g.shots, g.thrusting), (-90.0, [], False))


class TheRings(unittest.TestCase):                      # acceptance 8-14
    def test_three_rings_of_twelve_turning_their_own_ways(self):
        g = game()
        self.assertEqual([len(r.hp) for r in g.rings], [12, 12, 12])
        before = [r.angle for r in g.rings]
        run(g, seconds(1))
        turned = [(r.angle - b + 180) % 360 - 180 for r, b in zip(g.rings, before)]
        self.assertAlmostEqual(turned[0], 15, places=3)       # outer: clockwise
        self.assertAlmostEqual(turned[1], -22, places=3)      # middle: the other way
        self.assertAlmostEqual(turned[2], 30, places=3)       # inner: clockwise
        self.assertEqual((g.rings[0].r, g.rings[1].r, g.rings[2].r), (145, 105, 65))

    def test_the_stronghold_never_moves(self):
        g = game()
        run(g, seconds(3))
        self.assertEqual((sh.CX, sh.CY), (CX, CY))

    def test_two_hits_to_a_segment_and_the_gap_turns_with_its_ring(self):
        g = game()
        still(g)
        outer = g.rings[0]
        k = 3                                           # (ring angle 0: segment 3 is straight below, 90 .. 117 degrees)
        x, y = seg_mid(g, outer, k)
        aim_at(g, x, y)
        tap(g)
        run(g, seconds(0.3))
        self.assertEqual(outer.hp[k], 1)
        self.assertEqual(g.score, sh.POINTS["hit"])
        self.assertIn("hit", g.take_events())
        tap(g)
        run(g, seconds(0.3))
        self.assertEqual(outer.hp[k], 0)
        self.assertEqual(g.score, sh.POINTS["hit"] + sh.POINTS["segment"])
        self.assertIsNone(outer.segment_at(math.degrees(math.atan2(y - CY, x - CX))))
        outer.speed = 15.0
        run(g, seconds(2))                              # the gap goes round with the ring
        self.assertIsNotNone(outer.segment_at(math.degrees(math.atan2(y - CY, x - CX))))
        self.assertIsNone(outer.segment_at(math.degrees(math.atan2(y - CY, x - CX)) + 30))

    def test_a_ring_shot_right_away_grows_back_and_the_others_stay(self):
        g = game()
        still(g)
        g.rings[1].hp[5] = 0
        outer = g.rings[0]
        outer.hp = [0] * 11 + [1]
        x, y = seg_mid(g, outer, 11)
        g.ship.x, g.ship.y = x + (x - CX) * 0.4, y + (y - CY) * 0.4
        aim_at(g, x, y)
        tap(g)
        run(g, seconds(0.2))
        self.assertGreater(outer.regrow, 0)
        self.assertEqual(g.score, sh.POINTS["segment"])         # the points all the same
        run(g, seconds(sh.REGROW))
        self.assertEqual(outer.hp, [2] * 12)
        self.assertIn("regrow", g.take_events())
        self.assertEqual(g.rings[1].hp[5], 0)                   # the middle ring as it was


class Shots(unittest.TestCase):                         # acceptance 15-17
    def test_blocked_by_a_segment(self):
        g = game()
        still(g)
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(1))
        self.assertEqual(g.state, "playing")
        self.assertEqual(g.rings[0].hp[3], 1)           # straight up from below: the outer ring's segment 3 took it

    def test_through_gaps_to_the_cannon_only_when_they_line_up(self):
        g = game()
        still(g)
        for ring in g.rings:
            ring.hp[3] = 0                              # a gap straight below, in all three
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(1))
        self.assertEqual(g.state, "boom")
        self.assertEqual(g.score, sh.POINTS["core"])

    def test_a_gap_that_turns_away_while_the_shot_flies_stops_it(self):
        g = game()
        still(g)
        for ring in g.rings:
            ring.hp[3] = 0
        g.rings[2].speed = 300.0                        # the inner gap whirls away before the shot gets there
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(1))
        self.assertEqual(g.state, "playing")

    def test_one_segment_a_shot(self):
        g = game()
        still(g)
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(1))
        self.assertEqual(sum(2 - h for r in g.rings for h in r.hp), 1)

    def test_a_shot_through_a_ring_s_corner_does_not_slip_between_checks(self):
        g = game()
        still(g)
        g.ship.vy = -380.0                              # coming in quick: the shot goes 880 pixels a second, 7 a step
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(1))
        self.assertEqual(sum(2 - h for r in g.rings for h in r.hp), 1)


class Mines(unittest.TestCase):                         # acceptance 18-20
    def test_three_come_out_one_after_another_and_hunt_the_ship(self):
        g = StrongholdGame(seed=2, attract=False)
        g.cannon_wait = 10 ** 6
        g.ship.x, g.ship.y = 60.0, 60.0
        g.shield = 10 ** 6
        closest = {}
        for _ in range(seconds(20)):
            g.tick()
            for mn in g.mines:
                closest[mn.id] = min(closest.get(mn.id, 1e9), math.hypot(*sh.near(mn.x, mn.y, 60, 60)))
        self.assertEqual(len(g.mines), 3)
        self.assertEqual(len(closest), 3)
        self.assertTrue(all(d < 40 for d in closest.values()), closest)     # every one gets to the ship

    def test_they_spread_out(self):
        g = StrongholdGame(seed=3, attract=False)
        g.cannon_wait, g.shield = 10 ** 6, 10 ** 6
        run(g, seconds(10))
        pts = [(mn.x, mn.y) for mn in g.mines]
        self.assertEqual(len(set((round(x), round(y)) for x, y in pts)), 3)

    def test_they_appear_just_outside_the_rings_across_from_the_ship_and_grow_in(self):
        g = game()
        g.mine_wait = [0.0]
        g.tick()
        mine = g.mines[0]
        d = math.hypot(mine.x - CX, mine.y - CY)
        self.assertGreater(d, sh.RINGS[0][0] + sh.RING_HALF + sh.MINE_R)
        self.assertLess(d, sh.RINGS[0][0] + 40)
        self.assertLess(mine.y, CY)                     # (the ship is below)

    def test_an_intact_segment_is_a_wall_to_a_mine(self):
        """However long they hunt a ship sitting in the middle, no mine is ever in a segment, nor inside an unbroken ring."""
        g = StrongholdGame(seed=4, attract=False)
        g.cannon_wait, g.shield = 10 ** 6, 10 ** 6
        g.ship.x, g.ship.y, g.thrusting = CX, CY, False
        g._fly = lambda dt: None                        # (the ship stays put, in the middle)
        for _ in range(seconds(30)):
            g.tick()
            for mn in g.mines:
                self.assertIsNone(g.ring_hit(mn.x, mn.y, sh.MINE_R - 0.5))
                if mn.t > sh.MINE_APPEAR:
                    self.assertGreater(math.hypot(mn.x - CX, mn.y - CY), sh.RINGS[0][0])
        self.assertEqual(len(g.mines), 3)

    def test_but_a_shot_open_gap_lets_one_through(self):
        g = game()
        still(g)
        outer = g.rings[0]
        for k in (2, 3, 4):                             # a wide gap below, in the outer ring only
            outer.hp[k] = 0
        g.ship.x, g.ship.y = CX, CY + 125               # between the outer and the middle ring, shielded
        g.shield = 10 ** 6
        g._fly = lambda dt: None
        mine = Thing("mine", CX, CY + 230, 0.0, -60.0, sh.MINE_R)
        mine.side, mine.t = 0.0, 1.0
        g.mines = [mine]
        closest = 1e9
        for _ in range(seconds(4)):
            g.tick()
            closest = min(closest, math.hypot(mine.x - CX, mine.y - CY))
        self.assertLess(closest, outer.r - sh.RING_HALF)          # in through the gap

    def test_a_segment_turning_onto_a_mine_pushes_it_off(self):
        g = game()
        outer = g.rings[0]
        mine = Thing("mine", CX, CY + outer.r, 0.0, 0.0, sh.MINE_R)       # right in the ring, where a segment is
        mine.side, mine.t = 0.0, 1.0
        g.mines = [mine]
        g.mine_speed = 0.0
        g.tick()
        self.assertIsNone(g.ring_hit(mine.x, mine.y, sh.MINE_R - 0.5))

    def test_a_shot_downs_one_for_no_points_and_another_comes_later(self):
        g = game()
        mine = Thing("mine", g.ship.x + 120, g.ship.y, 0.0, 0.0, sh.MINE_R)
        mine.side, mine.t = 0.0, 1.0
        g.mines = [mine]
        g.mine_speed = 0.0
        g.ship.angle = 0.0
        g.mine_wait = []
        tap(g)
        run(g, seconds(0.4))
        self.assertEqual((g.mines, g.score), ([], 0))
        self.assertEqual(len(g.mine_wait), 1)
        self.assertTrue(sh.MINE_AGAIN[0] - 0.5 <= g.mine_wait[0] <= sh.MINE_AGAIN[1])

    def test_a_mine_destroys_the_ship(self):
        g = game()
        mine = Thing("mine", g.ship.x + 40, g.ship.y, -60.0, 0.0, sh.MINE_R)     # coming at it
        mine.side, mine.t = 0.0, 1.0
        g.mines = [mine]
        run(g, seconds(1))
        self.assertEqual(g.lives, sh.LIVES - 1)


GAP = 90 + sh.SEG_SPAN / 2                              # the middle of segment 3, straight below (when the rings are at 0)


def below_the_gap(g):
    """Every ring's segment 3 gone, the rings still, and the ship out beyond the middle of that gap."""
    still(g)
    for ring in g.rings:
        ring.hp[3] = 0
    a = math.radians(GAP)
    g.ship.x, g.ship.y = CX + math.cos(a) * 235, CY + math.sin(a) * 235


class TheCannon(unittest.TestCase):                    # acceptance 21-23
    def test_it_turns_towards_the_ship_at_its_own_pace(self):
        g = game()
        g.cannon_angle = 0.0
        run(g, seconds(0.25))
        self.assertAlmostEqual(g.cannon_angle, 30.0, delta=1)       # 120 a second, towards straight down (90)
        run(g, seconds(1))
        self.assertAlmostEqual(g.cannon_angle, 90.0, delta=0.5)

    def test_it_does_not_fire_through_its_shields(self):
        g = game()
        still(g)
        g.cannon_wait = 0.0
        run(g, seconds(3))
        self.assertEqual(g.cannon_shots, [])

    def test_it_fires_through_a_gap_that_lines_up(self):
        g = game()
        below_the_gap(g)
        g.cannon_angle, g.cannon_wait = GAP, 0.0
        g.tick()
        self.assertEqual(len(g.cannon_shots), 1)
        self.assertIn("cannon", g.take_events())

    def test_its_check_allows_for_the_rings_turning_while_its_shot_flies(self):
        g = game()
        still(g)
        for ring in g.rings:
            ring.hp[3] = 0
        self.assertTrue(g.clear_path(GAP, 320, sh.CANNON_SHOT_R))
        g.rings[0].speed = 400.0                        # the outer gap will have gone by the time the shot gets there
        self.assertFalse(g.clear_path(GAP, 320, sh.CANNON_SHOT_R))

    def test_its_shot_destroys_the_ship(self):
        g = game()
        below_the_gap(g)
        g.cannon_angle, g.cannon_wait = GAP, 0.0
        run(g, seconds(1.2))
        self.assertEqual(g.lives, sh.LIVES - 1)

    def test_the_edge_of_a_gap_is_not_clear(self):
        g = game()
        below_the_gap(g)
        self.assertFalse(g.clear_path(90.0, 320, sh.CANNON_SHOT_R))    # the inner ring's next segment grazes it there


class Rounds(unittest.TestCase):                        # acceptance 24-30
    def win(self, g):
        still(g)
        for ring in g.rings:
            ring.hp[3] = 0
        g.ship.x, g.ship.y = CX, CY + 235
        aim_at(g, CX, CY)
        tap(g)
        run(g, seconds(0.8))

    def test_the_cannon_hit_a_big_bang_points_a_ship_and_a_harder_round_with_whole_rings(self):
        g = game()
        g.rings[1].hp[7] = 1
        self.win(g)
        self.assertEqual((g.state, g.score, g.lives), ("boom", 1000, sh.LIVES + 1))
        self.assertIn("boom", g.take_events())
        self.assertTrue(g.flying)
        self.assertEqual((g.mines, g.cannon_shots), ([], []))
        run(g, seconds(sh.BOOM) + 1)
        self.assertEqual((g.state, g.round), ("playing", 2))
        self.assertEqual([r.hp for r in g.rings], [[2] * 12] * 3)
        self.assertGreater(g.rings[0].speed, 15)
        self.assertGreater(g.mine_speed, 95)
        self.assertLess(g.cannon_every, 1.5)
        self.assertGreater(g.cannon_speed, 320)

    def test_the_table(self):
        g = game()
        for round_, outer, middle, inner, mine, every, speed in ((1, 15, 22, 30, 95, 1.5, 320), (5, 20, 28, 38, 120, 1.2, 370),
                                                                 (10, 25, 35, 45, 145, 0.9, 420), (30, 25, 35, 45, 145, 0.9, 420)):
            g.round = round_
            g._new_round()
            self.assertEqual([round(r.speed, 6) for r in g.rings], [outer, middle, inner])
            self.assertEqual((round(g.mine_speed, 6), round(g.cannon_every, 6), round(g.cannon_speed, 6)), (mine, every, speed))

    def test_a_lost_ship_leaves_the_shields_as_they_were(self):
        g = game()
        g.rings[0].hp[2] = 0
        g.rings[2].hp[9] = 1
        g._lost()
        run(g, seconds(sh.DESTROYED) + 2)
        self.assertEqual(g.state, "playing")
        self.assertEqual((g.rings[0].hp[2], g.rings[2].hp[9]), (0, 1))
        self.assertEqual((g.ship.x, g.ship.y, g.ship.angle), (CX, CY + 235, -90.0))
        self.assertGreater(g.shield, 1.9)

    def test_a_new_ship_comes_even_when_the_mines_were_round_the_start(self):
        """(It once never came: the mines went on hunting where the lost ship had been, by the start, so it was never clear.)"""
        g = game()
        for k in range(3):                              # three mines right round the start, coming at the ship
            a = math.radians(k * 120)
            mine = Thing("mine", g.ship.x + math.cos(a) * 30, g.ship.y + math.sin(a) * 30, -math.cos(a) * 60,
                         -math.sin(a) * 60, sh.MINE_R)
            mine.side, mine.t = 0.0, 1.0
            g.mines.append(mine)
        run(g, seconds(0.5))
        self.assertEqual(g.lives, sh.LIVES - 1)
        for _ in range(seconds(sh.DESTROYED + sh.FORCE_BACK + 1)):
            g.tick()
            if g.state == "playing":
                break
        self.assertEqual(g.state, "playing")            # a new ship, with the mines well away from it
        self.assertTrue(all(math.hypot(*sh.near(CX, sh.START_Y, mn.x, mn.y)) > sh.SAFE_R for mn in g.mines))

    def test_with_no_ship_the_mines_go_off_across_from_the_start(self):
        g = game()
        mine = Thing("mine", CX + 200, sh.START_Y, -60.0, 0.0, sh.MINE_R)
        mine.side, mine.t = 0.0, 1.0
        g.mines = [mine]
        g._lost()
        g.timer = 100.0                                 # (the pause after the loss held on, while it is watched)
        run(g, seconds(5))
        self.assertGreater(math.hypot(*sh.near(CX, sh.START_Y, mine.x, mine.y)), 300)

    def test_touching_the_rings_is_a_lost_ship(self):
        g = game()
        still(g)
        g.ship.vy = -200.0
        run(g, seconds(1))
        self.assertEqual(g.lives, sh.LIVES - 1)

    def test_the_last_ship_then_game_over_then_both_for_another(self):
        g = game()
        for _ in range(sh.LIVES):
            g.shield = 0
            g._lost()
            run(g, seconds(sh.DESTROYED) + 2)
        self.assertEqual(g.state, "over")
        run(g, seconds(sh.OVER_WAIT) + 2, BOTH)
        self.assertEqual(g.state, "over")
        g.tick()
        g.tick(BOTH)
        self.assertEqual((g.state, g.score, g.lives, g.round), ("playing", 0, sh.LIVES, 1))


class Others(unittest.TestCase):
    def test_the_title_turns_the_rings_and_both_start(self):
        g = StrongholdGame(seed=1)
        a = g.rings[0].angle
        run(g, seconds(1))
        self.assertNotEqual(g.rings[0].angle, a)
        g.tick(BOTH)
        self.assertEqual(g.state, "playing")

    def test_the_title_left_alone_closes(self):
        g = StrongholdGame(seed=1)
        run(g, seconds(sh.ATTRACT_IDLE) + 1)
        self.assertTrue(g.finished)

    def test_the_high_score_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            s = Session(FakeSounds(), lambda: 100.0, best_file=best, make_game=StrongholdGame, make_view=lambda: None,
                        make_sounds=game_sound.stronghold_sounds)
            s.sound_maker.join()
            s.game.score = s.game.best = 4560
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "4560")

    def test_every_event_has_a_sound(self):
        sounds = game_sound.stronghold_sounds()
        for name in ("fire", "thrust", "hit", "segment", "regrow", "mine", "mine_die", "cannon", "die", "boom", "round", "over"):
            self.assertGreater(len(sounds[name]), 50, name)


@unittest.skipIf(pygame is None, "no pygame")
class Drawing(unittest.TestCase):                      # acceptance 31
    @classmethod
    def setUpClass(cls):
        from judicom.display import Display
        cls.display = Display(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.display.close()

    def test_every_state_draws_in_lines_on_black(self):
        from judicom.stronghold_view import StrongholdView
        view = StrongholdView()
        g = StrongholdGame(seed=1)
        run(g, 100)
        g.rings[0].hp[1] = 1
        g.rings[1].regrow = 0.4
        for state in ("attract", "playing", "destroyed", "boom", "over"):
            if state == "destroyed":
                g._lost()
            if state == "boom":
                g._core_down()
                run(g, 30)
            g.state = state
            pic = view.draw(g)
            self.assertEqual(pic.get_at((5, 1000))[:3], (0, 0, 0))
        view.present(g, self.display)


class FakeSounds:
    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        pass

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
