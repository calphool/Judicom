"""Meteoroids (judicom/meteor.py): the acceptance list it was built to, the two-button state machine, and its drawing."""
import math
import tempfile
import unittest
from pathlib import Path

from judicom import config, game_sound
from judicom import meteor as m
from judicom.game import Session
from judicom.meteor import MeteorGame, Thing

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def seconds(s):
    return int(round(s / m.TICK))


def run(g, steps, held=()):
    for _ in range(steps):
        g.tick(held)


def game(rocks=False):
    """A game going, the buttons seen up; with no rocks unless asked (and no enemy craft soon)."""
    g = MeteorGame(seed=1, attract=False)
    g.tick()
    if not rocks:
        g.rocks = []
        g.wave_timer = -10 ** 6                         # (no new wave while a test runs)
    g.craft_timer = 10 ** 6
    return g


def tap(g, length=0.2):
    run(g, seconds(length), BOTH)
    g.tick()


class Turning(unittest.TestCase):                       # acceptance 1, 2, 7
    def test_left_turns_counter_clockwise_and_right_clockwise_at_240_a_second(self):
        g = game()
        a = g.ship.angle
        run(g, seconds(0.5), {"left"})
        self.assertAlmostEqual(g.ship.angle - a, -120, delta=1)
        run(g, seconds(0.5), {"right"})
        self.assertAlmostEqual(g.ship.angle - a, 0, delta=1)

    def test_turning_does_not_change_the_way_it_drifts(self):
        g = game()
        g.ship.vx, g.ship.vy = 50.0, 0.0
        run(g, seconds(1), {"left"})
        self.assertEqual((g.ship.vx, g.ship.vy), (50.0, 0.0))

    def test_no_turning_while_both_are_held(self):
        g = game()
        a = g.ship.angle
        run(g, seconds(1), BOTH)
        self.assertEqual(g.ship.angle, a)


class FireAndThrust(unittest.TestCase):                 # acceptance 3, 4, 5, 6, 8
    def test_a_tap_fires_one_shot_when_let_go(self):
        g = game()
        run(g, seconds(0.2), BOTH)
        self.assertEqual(g.shots, [])                   # not yet: it may become a thrust
        g.tick()
        self.assertEqual(len(g.shots), 1)
        self.assertFalse(g.thrusting)

    def test_the_briefest_tap_fires_even_when_the_buttons_overlap_for_one_frame(self):
        """The game reads the buttons once a frame (about 40 a second on the Pi): two thumbs that overlap for just one frame
        are a tap all the same."""
        g = game()
        t = 0.0
        g.update(t, set())
        for held in ({"left"}, BOTH, {"right"}, set()):
            t += 0.025
            g.update(t, held)
        self.assertEqual(len(g.shots), 1)

    def test_letting_go_of_one_button_is_letting_go(self):
        g = game()
        run(g, seconds(0.2), BOTH)
        g.tick({"left"})
        self.assertEqual(len(g.shots), 1)

    def test_the_shot_goes_where_the_ship_points_plus_its_drift(self):
        g = game()
        g.ship.angle, g.ship.vx, g.ship.vy = 0.0, 30.0, 10.0
        tap(g)
        s = g.shots[0]
        self.assertAlmostEqual(s.vx, 30 + m.SHOT_SPEED)
        self.assertAlmostEqual(s.vy, 10)

    def test_a_hold_thrusts_and_never_fires(self):
        g = game()
        run(g, seconds(0.49), BOTH)
        self.assertFalse(g.thrusting)
        run(g, seconds(0.02), BOTH)
        self.assertTrue(g.thrusting)
        self.assertIn("thrust_on", g.take_events())
        run(g, seconds(1), BOTH)
        g.tick()
        self.assertEqual(g.shots, [])
        self.assertFalse(g.thrusting)
        self.assertIn("thrust_off", g.take_events())

    def test_thrust_pushes_the_way_it_points_and_the_drift_goes_on(self):
        g = game()
        g.ship.angle = 0.0
        run(g, seconds(0.5 + 1.0), BOTH)                # half a second to start, then a second of thrust
        self.assertAlmostEqual(g.ship.vx, m.THRUST * 1.0, delta=m.THRUST * 0.03)
        self.assertAlmostEqual(g.ship.vy, 0, delta=0.01)
        v = g.ship.vx
        run(g, seconds(2))
        self.assertAlmostEqual(g.ship.vx, v)            # no friction

    def test_turning_about_and_thrusting_slows_then_reverses(self):
        g = game()
        g.ship.angle, g.ship.vx = 180.0, 100.0          # drifting right, facing left
        run(g, seconds(0.5 + 0.3), BOTH)
        self.assertTrue(0 < g.ship.vx < 100)
        run(g, seconds(0.5), BOTH)
        self.assertLess(g.ship.vx, 0)

    def test_never_faster_than_400(self):
        g = game()
        run(g, seconds(5), BOTH)
        self.assertAlmostEqual(math.hypot(g.ship.vx, g.ship.vy), m.MAX_SPEED, delta=0.5)

    def test_four_shots_at_most_and_not_quicker_than_100_ms(self):
        g = game()
        for _ in range(8):
            tap(g, 0.04)
        self.assertLessEqual(len(g.shots), 4)
        g2 = game()
        tap(g2, 0.04)
        tap(g2, 0.04)                                   # 6 steps (50 ms) after the first: too soon
        self.assertEqual(len(g2.shots), 1)

    def test_shots_last_0_9_s(self):
        g = game()
        tap(g)
        run(g, seconds(0.85))
        self.assertEqual(len(g.shots), 1)
        run(g, seconds(0.1))
        self.assertEqual(g.shots, [])

    def test_buttons_still_held_from_the_start_do_nothing(self):
        g = MeteorGame(seed=1)
        g.tick()
        run(g, 3, BOTH)                                 # starts the game ...
        self.assertEqual(g.state, "playing")
        run(g, seconds(1), BOTH)                        # ... and the same press goes on: no thrust, no shot
        g.tick()
        self.assertEqual((g.shots, g.thrusting), ([], False))


class Wrapping(unittest.TestCase):                      # acceptance 9, 11
    def test_the_ship_comes_back_on_the_other_side_of_every_edge(self):
        for vx, vy in ((300, 0), (-300, 0), (0, 300), (0, -300)):
            g = game()
            g.ship.vx, g.ship.vy = float(vx), float(vy)
            run(g, seconds(m.H / 300 + 0.2))
            self.assertTrue(0 <= g.ship.x < m.W and 0 <= g.ship.y < m.H)
            self.assertEqual((g.ship.vx, g.ship.vy), (vx, vy))

    def test_rocks_wrap_too_and_keep_going(self):
        g = game()
        r = g._rock("large", m.W - 5, m.H - 5)
        g.rocks = [r]
        vx, vy = r.vx, r.vy
        run(g, seconds(30))
        self.assertTrue(0 <= r.x < m.W and 0 <= r.y < m.H)
        self.assertEqual((r.vx, r.vy), (vx, vy))

    def test_distances_go_the_short_way_round(self):
        self.assertEqual(m.near(5, 5, m.W - 5, m.H - 5), (-10, -10))


class Rocks(unittest.TestCase):                         # acceptance 10, 12-15
    def test_each_rock_its_own_shape_9_to_13_corners(self):
        g = game(rocks=True)
        shapes = [tuple(r.shape) for r in g.rocks]
        self.assertEqual(len(set(shapes)), len(shapes))
        for r in g.rocks:
            self.assertTrue(9 <= len(r.shape) <= 13)
            for x, y in r.shape:
                self.assertTrue(0.67 * r.r <= math.hypot(x, y) <= r.r + 1e-9)

    def test_they_drift_at_their_own_speeds(self):
        g = game(rocks=True)
        self.assertEqual(len(g.rocks), 4)
        speeds = [math.hypot(r.vx, r.vy) for r in g.rocks]
        self.assertTrue(all(25 <= v <= 55 for v in speeds))
        self.assertEqual(len(set(speeds)), 4)

    def shoot(self, g, rock):
        g.rocks = [rock]
        g.ship.angle = math.degrees(math.atan2(rock.y - g.ship.y, rock.x - g.ship.x))
        tap(g)
        run(g, seconds(0.6))

    def test_large_to_two_medium_to_two_small_to_nothing_with_the_points(self):
        for size, pieces, points in (("large", "medium", 20), ("medium", "small", 50), ("small", None, 100)):
            g = game()
            rock = g._rock(size, g.ship.x, g.ship.y - 150)
            rock.vx = rock.vy = 0.0
            self.shoot(g, rock)
            self.assertEqual(g.score, points, size)
            if pieces:
                self.assertEqual([r.size for r in g.rocks], [pieces, pieces])
                a, b = g.rocks
                self.assertNotAlmostEqual(math.atan2(a.vy, a.vx), math.atan2(b.vy, b.vx), places=1)
            else:
                self.assertEqual(g.rocks, [])

    def test_a_quick_shot_cannot_skip_a_small_rock(self):
        g = game()
        g.ship.vx = 400.0                               # shot speed 900 a second: 7.5 pixels a step
        rock = g._rock("small", g.ship.x + 100, g.ship.y)
        rock.vx = rock.vy = 0.0
        g.ship.angle = 0.0
        self.shoot(g, rock)
        self.assertEqual(g.score, 100)

    def test_one_shot_one_rock(self):
        g = game()
        a, b = g._rock("small", g.ship.x, g.ship.y - 100), g._rock("small", g.ship.x, g.ship.y - 101)
        for r in (a, b):
            r.vx = r.vy = 0.0
        g.rocks = [a, b]
        g.ship.angle = -90.0
        tap(g)
        run(g, seconds(0.5))
        self.assertEqual(len(g.rocks), 1)


class Lives(unittest.TestCase):                         # acceptance 16-18, 26
    def crash(self, g):
        g.shield = 0.0                                  # (a ship just back is safe for 2 s)
        r = g._rock("large", g.ship.x, g.ship.y)
        g.rocks = [r]
        g.tick()

    def test_a_rock_destroys_the_ship_and_a_life_goes(self):
        g = game()
        self.crash(g)
        self.assertEqual((g.state, g.lives), ("destroyed", m.LIVES - 1))
        self.assertIn("die", g.take_events())

    def test_back_in_the_middle_still_and_upright_and_blinking_safe_for_2_s(self):
        g = game()
        g.ship.x, g.ship.vx = 50.0, 120.0
        self.crash(g)
        g.rocks = []
        run(g, seconds(m.DESTROYED) + 1)
        s = g.ship
        self.assertEqual((g.state, s.x, s.y, s.vx, s.vy, s.angle), ("playing", m.W / 2, m.H / 2, 0.0, 0.0, -90.0))
        self.assertAlmostEqual(g.shield, m.SHIELD, delta=0.02)
        g.rocks = [g._rock("large", s.x, s.y)]
        run(g, seconds(1))
        self.assertEqual(g.state, "playing")            # safe ...
        g.rocks[0].x, g.rocks[0].y, g.rocks[0].vx, g.rocks[0].vy = s.x, s.y, 0.0, 0.0
        run(g, seconds(1.1))
        self.assertEqual(g.state, "destroyed")          # ... for 2 s only

    def test_not_back_while_a_rock_is_in_the_middle(self):
        g = game()
        self.crash(g)
        rock = g._rock("large", m.W / 2, m.H / 2)
        rock.vx, rock.vy = 0.0, 0.0
        g.rocks = [rock]
        run(g, seconds(m.DESTROYED) + 30)
        self.assertEqual(g.state, "destroyed")
        g.rocks = []
        g.tick()
        self.assertEqual(g.state, "playing")

    def test_a_new_ship_can_fire_at_once(self):
        """(It once could not, for as long as the last ship had lived: the time between shots was the ship's own.)"""
        g = game()
        run(g, seconds(20))
        tap(g)
        self.crash(g)
        g.rocks = []
        run(g, seconds(m.DESTROYED) + 2)
        self.assertEqual(g.state, "playing")
        g.shots = []
        tap(g)
        self.assertEqual(len(g.shots), 1)

    def test_and_so_can_the_next_game(self):
        g = game()
        run(g, seconds(20))
        tap(g)
        g.new_game()
        g.tick()
        g.shots = []
        tap(g)
        self.assertEqual(len(g.shots), 1)

    def test_an_enemy_shot_destroys_the_ship(self):
        g = game()
        shot = Thing("craft_shot", g.ship.x + 30, g.ship.y, -260.0, 0.0, 2.0)
        shot.life = 1.0
        g.craft_shots = [shot]
        run(g, seconds(0.3))
        self.assertEqual(g.state, "destroyed")

    def test_the_last_life_ends_the_game_and_both_start_another(self):
        g = game()
        for _ in range(m.LIVES):
            self.crash(g)
            g.rocks = []
            run(g, seconds(m.DESTROYED) + 2)
        self.assertEqual(g.state, "over")
        run(g, seconds(m.OVER_WAIT) + 5, BOTH)          # still held: nothing
        self.assertEqual(g.state, "over")
        g.tick()
        g.tick(BOTH)
        self.assertEqual((g.state, g.score, g.lives, g.wave), ("playing", 0, m.LIVES, 1))

    def test_an_extra_ship_every_10000(self):
        g = game()
        g._add(10000)
        g._add(10000)
        self.assertEqual(g.lives, m.LIVES + 2)


class Waves(unittest.TestCase):                         # acceptance 19, 22
    def test_a_clear_field_brings_a_bigger_wave_after_a_moment(self):
        g = game(rocks=True)
        g.wave_timer = 0.0
        g.rocks = []
        run(g, seconds(m.WAVE_PAUSE) - 2)
        self.assertEqual(g.rocks, [])
        run(g, 3)
        self.assertEqual((g.wave, len(g.rocks)), (2, 5))

    def test_later_waves_more_and_quicker_but_not_without_end(self):
        g = game(rocks=True)
        for _ in range(30):
            g.rocks = []
            g._new_wave()
        self.assertEqual(len(g.rocks), 11)
        self.assertTrue(all(math.hypot(r.vx, r.vy) <= 55 * 1.5 + 1e-6 for r in g.rocks))

    def test_new_rocks_keep_away_from_the_ship(self):
        for seed in range(10):
            g = MeteorGame(seed=seed, attract=False)
            for r in g.rocks:
                self.assertGreater(math.hypot(*m.near(g.ship.x, g.ship.y, r.x, r.y)), 200)

    def test_the_heartbeat_quickens_as_the_rocks_get_fewer(self):
        def beats(n):
            g = game()
            g.rocks = [g._rock("small", 10 + i * 30, 30) for i in range(n)]
            for r in g.rocks:
                r.vx = r.vy = 0.0
            run(g, seconds(5))
            return sum(1 for e in g.take_events() if e.startswith("beat"))
        self.assertGreater(beats(1), beats(12))


class EnemyCraft(unittest.TestCase):                   # acceptance 20, 21
    def test_one_comes_now_and_then_crosses_and_goes(self):
        g = game()
        g.craft_timer = 0.01
        run(g, 3)
        self.assertIsNotNone(g.craft)
        self.assertIn("craft_on", g.take_events())
        run(g, seconds(1))
        self.assertIsNotNone(g.craft)
        g.craft_timer = 0.0
        run(g, seconds(15))
        self.assertIn("craft_off", g.take_events())

    def test_the_small_one_shoots_at_the_ship(self):
        g = game()
        g.rng.seed(5)
        c = Thing("craft", 100, 100, 0.0, 0.0, 9)
        c.size, c.next_turn, c.next_fire = "small", 10.0, 0.0
        g.craft = c
        g.wave = 20                                     # (at its surest)
        g.tick()
        s = g.craft_shots[0]
        aim = math.atan2(g.ship.y - 100, g.ship.x - 100)
        self.assertLess(abs(math.atan2(s.vy, s.vx) - aim), 0.25)

    def test_shooting_one_down_scores(self):
        for size, points in (("big", 200), ("small", 1000)):
            g = game()
            c = Thing("craft", g.ship.x, g.ship.y - 120, 0.0, 0.0, m.CRAFT[size][0])
            c.size, c.next_turn, c.next_fire = size, 10.0, 10.0
            g.craft = c
            g.ship.angle = -90.0
            tap(g)
            run(g, seconds(0.4))
            self.assertEqual(g.score, points)
            self.assertIsNone(g.craft)

    def test_a_rock_takes_one_down_for_no_points(self):
        g = game()
        c = Thing("craft", 100, 100, 0.0, 0.0, 16)
        c.size, c.next_turn, c.next_fire = "big", 10.0, 10.0
        g.craft = c
        r = g._rock("large", 100, 100)
        g.rocks = [r]
        g.tick()
        self.assertIsNone(g.craft)
        self.assertEqual(g.score, 0)

    def test_more_often_in_later_waves(self):
        g = game(rocks=True)
        early = None
        for wave in (1, 10):
            g.wave = wave - 1
            g.rocks = []
            g._new_wave()
            early = early or g.craft_timer
        self.assertLess(g.craft_timer, early)


class Others(unittest.TestCase):                        # acceptance 25, 28, and the title
    def test_only_two_buttons(self):
        g = game()
        a = g.ship.angle
        run(g, seconds(1), {"up", "fire"})
        self.assertEqual((g.ship.angle, g.shots, g.thrusting), (a, [], False))

    def test_the_title_turns_the_ship_and_drifts_rocks_and_both_start(self):
        g = MeteorGame(seed=1)
        a, x = g.ship.angle, g.rocks[0].x
        run(g, seconds(1))
        self.assertNotEqual(g.ship.angle, a)
        self.assertNotEqual(g.rocks[0].x, x)
        self.assertEqual(g.take_events(), [])           # quietly
        g.tick(BOTH)
        self.assertEqual(g.state, "playing")

    def test_the_title_left_alone_closes(self):
        g = MeteorGame(seed=1)
        run(g, seconds(m.ATTRACT_IDLE) + 1)
        self.assertTrue(g.finished)

    def test_the_high_score_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            s = Session(FakeSounds(), lambda: 100.0, best_file=best, make_game=MeteorGame, make_view=lambda: None,
                        make_sounds=game_sound.meteor_sounds)
            s.sound_maker.join()
            s.game.score = s.game.best = 7770
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "7770")

    def test_every_event_has_a_sound(self):
        sounds = game_sound.meteor_sounds()
        for name in ("fire", "bang0", "bang1", "bang2", "die", "craft_die", "craft_fire", "beat0", "beat1", "extra", "wave",
                     "over", "thrust", "craft"):
            self.assertGreater(len(sounds[name]), 50, name)


@unittest.skipIf(pygame is None, "no pygame")
class Drawing(unittest.TestCase):                      # acceptance 23
    @classmethod
    def setUpClass(cls):
        from judicom.display import Display
        cls.display = Display(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.display.close()

    def test_every_state_draws_in_lines_on_black(self):
        from judicom.meteor_view import MeteorView
        view = MeteorView()
        g = MeteorGame(seed=1)
        run(g, 100)
        for state in ("attract", "playing", "destroyed", "over"):
            g.state = state
            if state == "destroyed":
                g._lost()
            pic = view.draw(g)
            self.assertEqual(pic.get_at((300, 1000))[:3], (0, 0, 0))
        view.present(g, self.display)

    def test_something_on_an_edge_shows_on_both_sides(self):
        from judicom.meteor_view import MeteorView, TOP
        g = game()
        r = g._rock("large", 2.0, 400.0)
        r.vx = r.vy = 0.0
        g.rocks = [r]
        pic = MeteorView().draw(g)
        lit = lambda x0, x1: any(pic.get_at((x, y))[:3] != (0, 0, 0) for x in range(x0, x1) for y in range(400 + TOP - 40, 400 + TOP + 40))   # noqa: E731
        self.assertTrue(lit(0, 40))
        self.assertTrue(lit(m.W - 40, m.W))

    def test_the_screen_mapping_matches_the_turned_picture(self):
        """Drawing straight onto the sideways screen must put each point where turning the upright picture would."""
        from judicom.display import Display
        d = Display(headless=True)
        try:
            for flip in (False, True):
                d.rotate, d.flip = True, flip
                d.screen = pygame.Surface((config.SCREEN_H, config.SCREEN_W))
                upright = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
                upright.set_at((10, 20), (255, 255, 255))
                turned = pygame.transform.rotate(upright, -90 if flip else 90)
                x, y = d.mapper()(10, 20)
                self.assertEqual(turned.get_at((round(x), round(y)))[:3], (255, 255, 255), flip)
        finally:
            d.rotate = False


class FakeSounds:
    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        pass

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
