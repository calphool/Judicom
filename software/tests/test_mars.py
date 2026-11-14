"""Mars Patrol (judicom/mars.py): the acceptance list it was built to, the button rules, fairness, and its drawing."""
import tempfile
import unittest
from pathlib import Path

from judicom import config, game_sound
from judicom import mars as m
from judicom.game import Session
from judicom.mars import MarsGame, Shot, Thing, autopilot, make_section

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def game(**kw):
    g = MarsGame(seed=1, attract=False, **kw)
    g.tick()                                            # the buttons seen up
    return g


def run(g, steps, held=()):
    for _ in range(steps):
        g.tick(held)


def seconds(s):
    return int(round(s / m.TICK))


def clear(g):
    """Nothing ahead: flat, no craters, no hazards, no visitors."""
    g.gaps, g.things, g.flyers, g.pending_air, g.enemy_shots = [], [], [], [], []
    for i in range(int(g.x // m.STEP) - 200, int(g.x // m.STEP) + 2000):
        g.heights[i] = m.GROUND_Y
    g._add_section = lambda index: None
    g._next = "none"                                    # (no next course made either)


def jump(g):
    g.tick(BOTH)
    g.tick()


class Driving(unittest.TestCase):                      # acceptance 1-5
    def test_it_drives_on_by_itself_and_the_world_scrolls(self):
        g = game()
        x = g.x
        run(g, seconds(1))
        self.assertAlmostEqual(g.x - x, m.NORMAL, delta=2)
        self.assertEqual(g.screen_x(g.x), m.PLAYER_X)          # the rover stays put on the screen; the world moves

    def test_left_slower_right_faster_neither_cruising(self):
        g = game()
        clear(g)
        run(g, seconds(1), {"left"})
        self.assertAlmostEqual(g.speed, m.SLOW)
        run(g, seconds(1), {"right"})
        self.assertAlmostEqual(g.speed, m.FAST)
        run(g, seconds(1))
        self.assertAlmostEqual(g.speed, m.NORMAL)

    def test_never_stops_or_turns_back(self):
        g = game()
        clear(g)
        x = g.x
        run(g, seconds(5), {"left"})
        self.assertGreater(g.x - x, m.SLOW * 4.5)

    def test_speed_changes_take_about_200_ms(self):
        g = game()
        clear(g)
        run(g, seconds(0.075) + 1, {"right"})
        self.assertLess(g.speed, m.NORMAL + 20)
        run(g, seconds(0.05), {"right"})
        self.assertTrue(m.NORMAL < g.speed < m.FAST)
        run(g, seconds(0.2), {"right"})
        self.assertAlmostEqual(g.speed, m.FAST)
        run(g, seconds(0.075 + 0.15), {"left"})         # all the way from fast to slow (after Left counts) ...
        self.assertGreater(g.speed, m.SLOW + 20)
        run(g, seconds(0.06), {"left"})
        self.assertAlmostEqual(g.speed, m.SLOW)         # ... takes about 200 ms

    def test_both_held_keeps_the_speed(self):
        g = game()
        clear(g)
        run(g, seconds(1), {"right"})
        run(g, seconds(1), BOTH)
        self.assertAlmostEqual(g.speed, m.FAST)

    def test_both_pressed_a_little_apart_does_not_change_the_speed(self):
        g = game()
        clear(g)
        run(g, seconds(0.06), {"left"})                 # inside the 75 ms allowance
        g.tick(BOTH)
        self.assertAlmostEqual(g.speed, m.NORMAL)
        self.assertFalse(g.grounded)                    # a jump


class JumpingAndFiring(unittest.TestCase):              # acceptance 6-12
    def test_both_fires_forward_and_up_and_jumps_from_the_ground(self):
        g = game()
        clear(g)
        g.tick(BOTH)
        self.assertEqual((len(g.shots), len(g.ups)), (1, 1))
        self.assertFalse(g.grounded)
        self.assertEqual(g.take_events()[-2:], ["fire", "jump"])

    def test_in_the_air_both_fires_again_but_does_not_jump_again(self):
        g = game()
        clear(g)
        jump(g)
        run(g, seconds(0.2))
        vy = g.vy
        g.tick(BOTH)
        self.assertEqual(len(g.ups), 2)
        self.assertAlmostEqual(g.vy, vy + m.GRAVITY * m.TICK)      # the jump goes on as it was

    def test_holding_both_fires_once(self):
        g = game()
        clear(g)
        run(g, seconds(2), BOTH)
        self.assertEqual(len([e for e in g.take_events() if e == "fire"]), 1)
        self.assertTrue(g.grounded)                     # landed, and no second jump while still held

    def test_shots_no_quicker_than_every_120_ms_but_a_jump_is_never_refused(self):
        g = game()
        clear(g)
        jump(g)
        g.tick(BOTH)                                    # 2 steps after the first: cooling down
        self.assertEqual(len(g.ups), 1)
        g.tick()
        run(g, seconds(0.12))
        g.tick(BOTH)
        self.assertEqual(len(g.ups), 2)
        g2 = game()
        clear(g2)
        g2.cooldown = 1.0                               # the weapons still cooling down ...
        g2.tick(BOTH)
        self.assertFalse(g2.grounded)                   # ... the jump happens all the same
        self.assertEqual(g2.ups, [])

    def test_after_landing_a_new_press_jumps_again(self):
        g = game()
        clear(g)
        jump(g)
        run(g, seconds(1.1))
        self.assertTrue(g.grounded)
        g.tick(BOTH)
        self.assertFalse(g.grounded)

    def test_the_jump(self):
        g = game()
        clear(g)
        y = g.yb
        jump(g)
        top, t = y, 0
        while not g.grounded:
            g.tick()
            top, t = min(top, g.yb), t + 1
        self.assertAlmostEqual(t * m.TICK, m.AIRTIME, delta=0.03)
        self.assertAlmostEqual(y - top, m.JUMP_V ** 2 / 2 / m.GRAVITY, delta=3)

    def test_faster_jumps_further(self):
        lengths = []
        for held in ({"left"}, set(), {"right"}):
            g = game()
            clear(g)
            run(g, seconds(1), held)
            x = g.x
            g.tick(BOTH)
            while not g.grounded:
                g.tick(held)
            lengths.append(g.x - x)
        self.assertAlmostEqual(lengths[0], 93, delta=6)
        self.assertAlmostEqual(lengths[1], 167, delta=6)
        self.assertAlmostEqual(lengths[2], 260, delta=8)


class Craters(unittest.TestCase):                       # acceptance 13, 14
    def crater(self, g, width, ahead=150):
        x = g.x + m.CAR_W / 2 + ahead
        g.gaps = [[x, x + width]]
        return x

    def test_jumped_in_good_time_it_is_crossed(self):
        g = game()
        clear(g)
        x = self.crater(g, 120)
        while g.x + m.CAR_W / 2 < x - 20:
            g.tick()
        jump(g)
        run(g, seconds(1.5))
        self.assertEqual(g.state, "playing")
        self.assertIn(m.POINTS["crater"], (g.score,))

    def test_driven_into_it_is_a_lost_rover(self):
        g = game()
        clear(g)
        self.crater(g, 60)
        run(g, seconds(1.5))
        self.assertEqual(g.state, "destroyed")

    def test_even_at_top_speed_a_small_crater_cannot_be_driven_over(self):
        g = game()
        clear(g)
        run(g, seconds(0.5), {"right"})
        self.crater(g, 55, ahead=100)
        run(g, seconds(1.5), {"right"})
        self.assertEqual(g.state, "destroyed")

    def test_a_wide_crater_needs_speed(self):
        for held, survives in ((set(), False), ({"right"}, True)):
            g = game()
            clear(g)
            run(g, seconds(0.5), held)
            x = self.crater(g, 190, ahead=200)
            while g.x + m.CAR_W / 2 < x - 30:
                g.tick(held)
            g.tick(BOTH)
            run(g, seconds(1.5), held)
            self.assertEqual(g.state == "playing", survives, held)


class Hazards(unittest.TestCase):                       # acceptance 15-18
    def test_a_forward_shot_breaks_a_rock(self):
        g = game()
        clear(g)
        rock = Thing("rock", g.x + m.CAR_W + 120, 18, 14, 1)
        rock.size = "small"
        g.things = [rock]
        g.tick(BOTH)
        run(g, seconds(0.5))
        self.assertEqual(rock.hp, 0)
        self.assertEqual(g.score, m.POINTS["small"])

    def test_a_large_rock_takes_several(self):
        g = game()
        clear(g)
        rock = Thing("rock", g.x + m.CAR_W + 200, 34, 30, 3)
        rock.size = "large"
        g.things = [rock]
        g.tick(BOTH)
        g.tick()
        run(g, seconds(0.6))
        self.assertEqual(rock.hp, 2)

    def test_the_shot_only_goes_so_far(self):
        g = game()
        clear(g)
        g.tick(BOTH)
        run(g, seconds(1))
        self.assertEqual(g.shots, [])

    def test_hitting_a_rock_or_a_mine_is_a_lost_rover(self):
        for kind, w, h in (("rock", 26, 22), ("mine", 12, 10), ("rover", 40, 22)):
            g = game()
            clear(g)
            t = Thing(kind, g.x + m.CAR_W + 60, w, h, 5)
            t.size = "medium"
            g.things = [t]
            run(g, seconds(1))
            self.assertEqual(g.state, "destroyed", kind)

    def test_an_upward_shot_brings_down_a_flyer(self):
        g = game()
        clear(g)
        g.flyers = [Thing("scout", m.PLAYER_X + 38, 20, 10, 1, y=200)]
        g.tick(BOTH)
        run(g, seconds(0.5))
        self.assertEqual(g.flyers, [])
        self.assertEqual(g.score, m.POINTS["scout"])

    def test_a_dropped_shot_on_the_rover_is_a_lost_rover(self):
        g = game()
        clear(g)
        g.enemy_shots = [Shot(g.x + m.CAR_W / 2 + 63, 400, 0.0, 200.0, kind="drop")]    # where the rover will be
        run(g, seconds(1))
        self.assertEqual(g.state, "destroyed")

    def test_falling_things_belong_to_the_ground_so_speed_gets_out_of_the_way(self):
        for held, survives in ((set(), False), ({"left"}, True)):
            g = game()
            clear(g)
            g.enemy_shots = [Shot(g.x + m.CAR_W / 2 + 160, 300, 0.0, 170.0, kind="drop")]  # on the rover at cruising speed
            run(g, seconds(1.5), held)
            self.assertEqual(g.state == "playing", survives, held)

    def test_a_crater_bomb_makes_a_new_crater_ahead(self):
        g = game()
        clear(g)
        g.course = 2
        wx = g.x + 500
        g.enemy_shots = [Shot(wx, m.GROUND_Y - 20, 0.0, 200.0, kind="bomb", crater=True)]
        run(g, 20)
        self.assertEqual(len(g.gaps), 1)
        self.assertAlmostEqual(g.gaps[0][0], wx, delta=3)

    def test_but_not_too_close_to_the_rover(self):
        g = game()
        clear(g)
        g.course = 2
        g.enemy_shots = [Shot(g.x + m.CAR_W + 100, m.GROUND_Y - 20, 0.0, 200.0, kind="bomb", crater=True)]
        run(g, 20)
        self.assertEqual(g.gaps, [])

    def test_nothing_is_dropped_by_a_crater_or_while_the_rover_is_in_the_air(self):
        g = game()
        clear(g)
        g.gaps = [[g.x + 600, g.x + 680]]
        self.assertFalse(g._fair_drop(g.x + 650))
        self.assertFalse(g._fair_drop(g.x + 680 + 250))    # where the rover lands, past the crater
        self.assertTrue(g._fair_drop(g.x + 680 + 400))
        jump(g)
        self.assertFalse(g._fair_drop(g.x + 680 + 400))

    def test_one_attack_drone_at_a_time(self):
        g = game()
        clear(g)
        g.pending_air = [(g.x, "attack", 0.5), (g.x + 1, "attack", 0.5)]
        run(g, 2)
        self.assertEqual(sum(f.kind == "attack" for f in g.flyers), 1)
        self.assertTrue(any(k == "attack" for _, k, _ in g.pending_air))


class Background(unittest.TestCase):                    # acceptance 19
    @unittest.skipIf(pygame is None, "no pygame")
    def test_the_layers_scroll_at_different_speeds(self):
        from judicom import mars_view
        speeds = [f for f, *_ in mars_view.LAYERS]
        self.assertEqual(speeds, sorted(speeds))
        self.assertEqual(speeds, [0.15, 0.35, 0.60])


class Courses(unittest.TestCase):                       # acceptance 20-23
    def test_sections_are_the_same_every_time(self):
        a, b = make_section(0, 2, 3, 1000), make_section(0, 2, 3, 1000)
        self.assertEqual(a.gaps, b.gaps)
        self.assertEqual([(t.kind, t.x) for t in a.things], [(t.kind, t.x) for t in b.things])
        self.assertEqual(a.flyers, b.flyers)

    def test_each_course_brings_its_own_and_later_ones_more(self):
        def kinds(course):
            out = set()
            for k in range(m.CHECKPOINTS):
                s = make_section(0, course, k, 0)
                out |= {t.kind for t in s.things} | ({"crater"} if s.gaps else set()) | {f[1] for f in s.flyers}
            return out
        self.assertNotIn("bomber", kinds(0))
        self.assertIn("bomber", kinds(2))
        self.assertIn("mine", kinds(2))
        self.assertTrue({"rover", "turret"} & kinds(3))
        self.assertGreaterEqual(len(kinds(4)), len(kinds(0)) + 3)

    def test_every_section_starts_and_ends_flat_and_clear(self):
        for course in range(5):
            for k in range(m.CHECKPOINTS):
                s = make_section(1, course, k, 0)
                for x in list(range(0, m.RUN_IN, 8)) + list(range(m.SECTION - m.RUN_OUT + 8, m.SECTION, 8)):
                    self.assertEqual(s.heights.get(x // m.STEP, m.GROUND_Y), m.GROUND_Y, (course, k, x))
                for g in s.gaps:
                    self.assertTrue(m.RUN_IN <= g[0] and g[1] <= m.SECTION - m.RUN_OUT, (course, k, g))

    def test_craters_never_too_wide_to_jump_at_top_speed(self):
        for cycle in range(4):
            for course in range(5):
                for k in range(m.CHECKPOINTS):
                    for a, b in make_section(cycle, course, k, 0).gaps:
                        self.assertLess(b - a + 40, m.FAST * m.AIRTIME)

    def test_a_checkpoint_scores_and_says_so(self):
        g = game()
        clear(g)
        g.x = g.course_x0 + m.SECTION - 50
        run(g, seconds(0.5))
        self.assertEqual(g.checkpoint, 1)
        self.assertEqual(g.score, m.POINTS["checkpoint"])
        self.assertIn("checkpoint", g.take_events())
        self.assertEqual(g.message, "CHECKPOINT 2")

    def test_a_lost_rover_starts_again_at_the_last_checkpoint_as_it_was(self):
        g = game(air=False)
        while g.checkpoint < 2:
            g.tick(autopilot(g))
        start = g.course_x0 + 2 * m.SECTION
        layout = sorted((t.kind, t.x) for t in g.things if t.x >= start)
        g._destroyed()
        run(g, seconds(m.DESTROYED_SECONDS) + 2)
        self.assertEqual(g.state, "playing")
        self.assertEqual(g.lives, m.LIVES - 1)
        self.assertAlmostEqual(g.x, start + 40, delta=4)
        self.assertEqual(sorted((t.kind, t.x) for t in g.things if t.x >= start), layout)

    def test_finishing_a_course_gives_a_time_bonus_and_the_next_course(self):
        g = game(air=False)
        g.x = g.course_x0 + m.CHECKPOINTS * m.SECTION - 30
        g.checkpoint = m.CHECKPOINTS - 1
        g.course_time = 10.0                            # far quicker than the target
        score = g.score
        run(g, 30)
        self.assertEqual(g.course, 1)
        target = m.SECTION * m.CHECKPOINTS / m.TARGET_SPEED
        self.assertGreaterEqual(g.score - score, int((target - 10.5) * 100))
        self.assertIn("course", g.take_events())

    def test_after_the_fifth_course_a_big_bonus_and_round_again_harder(self):
        g = game(air=False)
        g.course = 4
        g.x = g.course_x0 + m.CHECKPOINTS * m.SECTION - 30
        g.checkpoint = m.CHECKPOINTS - 1
        g.course_time = 10 ** 6                         # no time bonus
        run(g, 30)
        self.assertEqual((g.cycle, g.course), (1, 0))
        self.assertEqual(g.score, m.POINTS["course"])

    def test_the_next_course_is_ready_before_it_comes_into_view(self):
        g = game(air=False)
        g.x = g.course_x0 + m.CHECKPOINTS * m.SECTION - 900
        g.checkpoint = m.CHECKPOINTS - 1
        g.tick()
        self.assertIsNotNone(g._next)


class LivesAndTheEnd(unittest.TestCase):                # acceptance 24-26
    def test_three_rovers_then_game_over(self):
        g = game()
        for _ in range(m.LIVES):
            g._destroyed()
            run(g, seconds(m.DESTROYED_SECONDS) + 2)
        self.assertEqual(g.state, "over")
        self.assertIn("over", g.take_events())

    def test_both_buttons_after_game_over_a_new_game_but_not_still_held(self):
        g = game()
        g.score = 500
        g.state, g.timer = "over", 0.0
        run(g, seconds(m.OVER_WAIT) + 5, BOTH)
        self.assertEqual(g.state, "over")
        g.tick()
        g.tick(BOTH)
        self.assertEqual((g.state, g.score, g.lives, g.course), ("playing", 0, m.LIVES, 0))

    def test_an_extra_rover_at_10000(self):
        g = game()
        g._add(m.EXTRA_LIFE_EVERY)
        self.assertEqual(g.lives, m.LIVES + 1)
        self.assertIn("extra", g.take_events())

    def test_the_title_and_its_demonstration_then_both_buttons_to_play(self):
        g = MarsGame(seed=1)
        self.assertEqual(g.state, "attract")
        run(g, seconds(3))
        self.assertGreater(g.x, 400)                    # the demonstration drives
        self.assertEqual(g.score, 0)
        self.assertEqual([e for e in g.take_events() if not e.endswith("_on")], [])     # quietly
        g.tick(BOTH)
        self.assertEqual(g.state, "playing")
        self.assertIn("music_on", g.take_events())

    def test_the_title_left_alone_closes(self):
        g = MarsGame(seed=1)
        run(g, seconds(m.ATTRACT_IDLE) + 1)
        self.assertTrue(g.finished)

    def test_only_two_buttons(self):
        g = game()
        clear(g)
        run(g, 30, {"up", "fire", "a"})
        self.assertAlmostEqual(g.speed, m.NORMAL)
        self.assertTrue(g.grounded)


class DrivenThrough(unittest.TestCase):
    """The autopilot drives the courses: proof that every course can be driven through by someone who plays well."""

    def drive(self, air, minutes, max_deaths):
        g = MarsGame(seed=1, air=air, attract=False)
        deaths = []
        for _ in range(seconds(60 * minutes)):
            was = g.state
            g.tick(autopilot(g) if g.state == "playing" else set())
            if g.state == "destroyed" and was == "playing":
                deaths.append((g.cycle, g.course, g.checkpoint))
                g.lives = 99
        self.assertLessEqual(len(deaths), max_deaths, deaths)
        self.assertGreater(len(set(deaths)), len(deaths) - 1 - max_deaths // 2, "the same place again and again: %s" % deaths)
        return g

    def test_the_ground_of_two_whole_rounds_without_a_crash(self):
        g = self.drive(air=False, minutes=13, max_deaths=0)
        self.assertGreaterEqual(g.cycle, 2)

    def test_with_the_flyers_too(self):
        g = self.drive(air=True, minutes=7, max_deaths=3)
        self.assertGreaterEqual(g.cycle, 1)


class ItsSession(unittest.TestCase):
    def test_sound_loops_and_high_score(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            sounds, t, said = FakeSounds(), [100.0], []
            s = Session(sounds, lambda: t[0], said.append, best_file=best, make_game=MarsGame, make_view=lambda: None,
                        make_sounds=game_sound.mars_sounds)
            s.sound_maker.join()
            for held in (set(), set(), BOTH, BOTH):     # straight from the title into a game, before there is sound
                t[0] += 1 / 60
                s.step(held)
            self.assertEqual(s.game.state, "playing")
            for _ in range(20):
                t[0] += 1 / 60
                s.step(set())
            t[0] += config.GAME_SOUND_AFTER
            s.step(set())
            self.assertIn("music_on", sounds.played)    # the tune it asked for before the sound came on
            self.assertFalse([p for p in sounds.played if p.startswith("engine")])     # no engine sound (taken out)
            s.game.score = s.game.best = 4321
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "4321")

    def test_every_event_has_a_sound(self):
        sounds = game_sound.mars_sounds()
        for name in ("fire", "jump", "land", "rock", "boom", "die", "bomb", "checkpoint", "course", "over", "extra", "music"):
            self.assertGreater(len(sounds[name]), 50, name)


@unittest.skipIf(pygame is None, "no pygame")
class Drawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from judicom.display import Display
        cls.display = Display(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.display.close()

    def test_every_state_draws(self):
        from judicom.mars_view import MarsView
        view = MarsView()
        g = MarsGame(seed=1)
        run(g, 200)
        for state in ("attract", "playing", "destroyed", "over"):
            g.state = state
            canvas = view.draw(g)
            self.assertEqual(canvas.get_size(), (config.SCREEN_W // 2, config.SCREEN_H // 2))
            self.display.present_small(canvas)

    def test_everything_draws(self):
        from judicom.mars_view import MarsView
        view = MarsView()
        g = game()
        x = g.x
        g.gaps = [[x + 330, x + 420]]
        g.things = [Thing("rock", x + 480, 26, 22, 2), Thing("mine", x + 560, 12, 10), Thing("buried", x + 600, 12, 4),
                    Thing("rover", x + 640, 40, 22), Thing("turret", x + 700, 24, 20, 2)]
        g.things[0].size = "medium"
        g.flyers = [Thing("scout", 500, 20, 10, y=150), Thing("attack", 620, 22, 14, y=220), Thing("bomber", 380, 36, 14, y=80)]
        g.enemy_shots = [Shot(x + 500, 300, kind="bomb"), Shot(x + 300, 250, kind="drop"), Shot(x + 500, 450, kind="ground")]
        g.bursts = [[300, 300, 0.1, k] for k in ("small", "rock", "air", "bomb", "car")]
        view.draw(g)

    def test_the_band_is_clear_of_the_bezel(self):
        from judicom import mars_view as v
        self.assertGreaterEqual(v.LEFT, 0)
        self.assertLessEqual((v.LEFT + 288) * 2, config.SCREEN_W - config.SHELL_RIGHT)
        self.assertGreaterEqual(v.BAND_Y * 2, config.SHELL_TOP)


class FakeSounds:
    def __init__(self):
        self.played = []

    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        self.played += names

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
