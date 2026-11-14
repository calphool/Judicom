"""The hidden game (judicom/game.py): the rules (the acceptance list it was built to), the knock that opens it, how it sits with
the phone, its sound and its drawing."""
import array
import tempfile
import unittest
from pathlib import Path

from judicom import config
from judicom import game as g
from judicom import game_sound
from judicom.game import Game, Session
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone
from judicom.maintenance import LAST_BONG, SHELL, Maintenance
from judicom.menu import BACK
from judicom.sound import Sounds

try:
    import pygame
except ImportError:
    pygame = None

W, H = config.SCREEN_W, config.SCREEN_H
TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT = (20, 20), (W - 20, 20), (W - 20, H - 20), (20, H - 20)
CLOCKWISE = (TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT)
BOTH = {"left", "right"}


def playing(seed=1):
    game = Game(seed=seed)
    for _ in range(g.READY_STEPS):
        game.tick()
    assert game.state == "play"
    game.fire_timer = 10 ** 9                          # quiet raiders, unless a test wants them
    game.bonus_timer = 10 ** 9
    return game


def run(game, steps, held=()):
    for _ in range(steps):
        game.tick(held)


def kill(game, keep=0):
    """Every raider but the last `keep`."""
    alive = [r for r in game.raiders if r.alive]
    for r in alive[:len(alive) - keep]:
        r.alive = False


class TheTurret(unittest.TestCase):
    def test_one_button_moves_it_that_way_after_a_moment(self):
        game = playing()
        x = game.tx
        run(game, g.MOVE_AFTER, {"right"})
        self.assertEqual(game.tx, x)                    # not yet: it may be the start of pressing both
        run(game, 10, {"right"})
        self.assertGreater(game.tx, x)
        x = game.tx
        run(game, 20, {"left"})
        self.assertLess(game.tx, x)

    def test_it_stays_on_the_field(self):
        game = playing()
        run(game, 400, {"left"})
        self.assertEqual(game.tx, g.FIELD_L)
        run(game, 400, {"right"})
        self.assertEqual(game.tx, g.FIELD_R - g.TURRET_W)

    def test_both_buttons_fire_upward_and_do_not_move_it(self):
        game = playing()
        x = game.tx
        game.tick(BOTH)
        self.assertIsNotNone(game.shot)
        self.assertEqual(game.take_events(), ["shoot"])
        y = game.shot.y
        game.tick(BOTH)
        self.assertLess(game.shot.y, y)
        self.assertEqual(game.tx, x)

    def test_one_shot_at_a_time_and_holding_fires_again_when_it_is_gone(self):
        game = playing()
        kill(game)                                      # nothing to hit: the shot flies to the top
        game.raiders[0].alive = True
        game.raiders[0].row, game.raiders[0].col = 0, 0
        game.tx = float(g.FIELD_R - g.TURRET_W)        # far from the one left
        shots = 0
        for _ in range(200):
            game.tick(BOTH)
            shots += game.take_events().count("shoot")
            self.assertLessEqual(1 if game.shot else 0, 1)
        flight = (g.TURRET_Y - 4 - g.TOP) // g.SHOT_SPEED + 1
        self.assertGreaterEqual(shots, 200 // (flight + 1))
        self.assertLessEqual(shots, 200 // flight + 1)

    def test_no_firing_while_the_wave_is_announced(self):
        game = Game(seed=1)
        game.tick(BOTH)
        self.assertIsNone(game.shot)


class TheFormation(unittest.TestCase):
    def test_55_in_5_rows_of_11(self):
        game = playing()
        self.assertEqual(len(game.raiders), 55)
        self.assertEqual({r.row for r in game.raiders}, set(range(5)))
        self.assertEqual({r.col for r in game.raiders}, set(range(11)))

    def test_it_marches_across_then_steps_down_and_turns_at_the_edge(self):
        game = playing()
        fx, fy = game.fx, game.fy
        run(game, game.march_timer)
        self.assertEqual((game.fx, game.fy), (fx + g.MARCH_DX, fy))
        drops = []
        for _ in range(20000):
            before = (game.fx, game.fy, game.direction)
            game.tick()
            if game.fy != before[1]:
                drops.append(before)
                self.assertEqual(game.fx, before[0])               # down, not across
                self.assertEqual(game.fy, before[1] + g.MARCH_DY)
                self.assertEqual(game.direction, -before[2])        # and the other way
                if len(drops) == 2:
                    break
        self.assertEqual(len(drops), 2)
        self.assertEqual([d[2] for d in drops], [1, -1])

    def test_it_never_leaves_the_field(self):
        game = playing()
        for _ in range(5000):
            game.tick()
            if game.state != "play":
                break
            for r in game.raiders:
                x, _, w, _ = game.raider_rect(r)
                self.assertGreaterEqual(x, g.FIELD_L)
                self.assertLessEqual(x + w, g.FIELD_R)

    def test_the_rows_look_different_and_swap_frames_as_they_step(self):
        game = playing()
        self.assertEqual(len({id(a) for a in g.ROW_ART}), 3)
        frame = game.frame
        run(game, game.march_timer)
        self.assertNotEqual(game.frame, frame)

    def test_a_hit_leaves_a_gap_and_the_rest_stay_where_they_were(self):
        game = playing()
        target = next(r for r in game.raiders if r.row == 4 and r.col == 5)
        others = {(r.col, r.row): game.raider_rect(r) for r in game.raiders if r is not target}
        x, y, w, h = game.raider_rect(target)
        game.shot = g.Shot(x + w // 2, y + h + 2, 0, g.SHOT_SPEED)
        game.tick()
        self.assertFalse(target.alive)
        self.assertEqual(game.score, 10)
        self.assertEqual({(r.col, r.row): game.raider_rect(r) for r in game.raiders if r is not target}, others)
        self.assertEqual(len(game.raiders), 55)

    def test_fewer_raiders_march_faster(self):
        game = playing()
        full = game.march_interval()
        kill(game, keep=20)
        twenty = game.march_interval()
        kill(game, keep=1)
        one = game.march_interval()
        self.assertGreater(full, twenty)
        self.assertGreater(twenty, one)
        self.assertGreaterEqual(one, 2)

    def test_the_steps_sound_faster_too(self):
        game = playing()
        def notes(steps):
            n = 0
            for _ in range(steps):
                game.tick()
                n += sum(1 for e in game.take_events() if e.startswith("march"))
            return n
        slow = notes(600)
        kill(game, keep=3)
        self.assertGreater(notes(600), slow * 3)


class TheirShots(unittest.TestCase):
    def test_they_fire_down_from_a_raider_with_a_clear_way_down(self):
        game = playing()
        game.fire_timer = 1
        game.tick()
        self.assertEqual(len(game.shots), 1)
        s = game.shots[0]
        lowest = [game.raider_rect(r) for r in game.raiders if r.row == 4]
        self.assertTrue(any(x <= s.x and s.x + 3 <= x + w and s.y == y + h for x, y, w, h in lowest))
        y = s.y
        game.tick()
        self.assertGreater(game.shots[0].y, y)

    def test_they_keep_firing_and_more_at_a_time_in_later_waves(self):
        game = playing()
        game.fire_timer = 1
        fired = 0
        for _ in range(1200):
            n = len(game.shots)
            game.tick()
            if game.state != "play":
                break
            fired += max(0, len(game.shots) - n)
        self.assertGreater(fired, 10)

    def test_later_waves_fire_more_often_and_more_at_once(self):
        def busiest(wave):
            game = playing()
            game.wave, game.fire_timer = wave, 1
            game.tx = -1000.0                           # out of the way: nothing ends the count early
            fired, most = 0, 0
            for _ in range(1200):
                n = len(game.shots)
                game.tick()
                fired += max(0, len(game.shots) - n)
                most = max(most, len(game.shots))
            return fired, most
        early, late = busiest(1), busiest(7)
        self.assertGreater(late[0], early[0])
        self.assertGreater(late[1], early[1])

    def test_a_shot_that_reaches_the_turret_costs_a_life(self):
        game = playing()
        game.shots = [g.Shot(int(game.tx) + 5, g.TURRET_Y - 8, 0, 2.0)]
        run(game, 5)
        self.assertEqual(game.state, "dying")
        self.assertEqual(game.lives, g.LIVES - 1)
        self.assertIn("die", game.take_events())
        self.assertEqual(game.shots, [])
        run(game, g.DYING_STEPS)
        self.assertEqual(game.state, "play")
        self.assertEqual(game.tx, g.FIELD_L + 10)       # back at the start

    def test_shelters_stop_shots_both_ways_and_wear_away(self):
        game = playing()
        sh = game.shelters[0]
        whole = sh.left
        x = sh.x + 5
        game.shots = [g.Shot(x - 1, sh.y - 10, 0, 2.0)]
        run(game, 10)
        self.assertEqual(game.shots, [])
        self.assertLess(sh.left, whole)
        self.assertEqual(game.state, "play")
        dented = sh.left
        game.tx = float(x - g.TURRET_W // 2)
        game.tick(BOTH)
        run(game, 20)
        self.assertIsNone(game.shot)
        self.assertLess(sh.left, dented)
        self.assertEqual(game.score, 0)

    def test_a_shelter_can_be_shot_right_through(self):
        game = playing()
        sh = game.shelters[1]
        game.tx = float(sh.x + 4 - g.TURRET_W // 2)
        for _ in range(3000):
            game.tick(BOTH)
            if game.score:
                break
        self.assertGreater(game.score, 0)                # a shot got through to a raider in the end

    def test_the_formation_wears_the_shelters_away_as_it_reaches_them(self):
        game = playing()
        sh = game.shelters[0]
        whole = sh.left
        game.fy = sh.y - 4 * g.ROW_STEP - 3            # the bottom row just into the shelters
        game.march_timer = 1
        game.tick()
        self.assertLess(sh.left, whole)

    def test_shots_meeting_cancel_out(self):
        game = playing()
        game.shot = g.Shot(100, 200, 0, g.SHOT_SPEED)
        game.shots = [g.Shot(99, 190, 0, 1.5)]
        game.tick()
        self.assertIsNone(game.shot)
        self.assertEqual(game.shots, [])


class TheBonusShip(unittest.TestCase):
    def test_it_comes_now_and_then_crosses_and_goes(self):
        game = playing()
        game.bonus_timer = 1
        game.tick()
        self.assertIsNotNone(game.bonus)
        self.assertIn("bonus_on", game.take_events())
        for _ in range(1000):
            game.tick()
            if game.bonus is None:
                break
        self.assertIsNone(game.bonus)
        self.assertIn("bonus_off", game.take_events())
        self.assertGreater(game.bonus_timer, 1000)

    def test_from_either_side(self):
        sides = set()
        for seed in range(20):
            game = playing(seed)
            game.bonus_timer = 1
            game.tick()
            sides.add(game.bonus[1])
        self.assertEqual(sides, {-1, 1})

    def test_hitting_it_is_worth_more(self):
        game = playing()
        game.bonus = [100.0, 1, 150]
        game.shot = g.Shot(105, g.BONUS_Y + 10, 0, g.SHOT_SPEED)
        game.tick()
        self.assertIsNone(game.bonus)
        self.assertEqual(game.score, 150)
        self.assertEqual(game.take_events(), ["bonus_off", "bonus_hit"])

    def test_not_when_few_raiders_are_left(self):
        game = playing()
        kill(game, keep=g.BONUS_MIN_LEFT - 1)
        game.bonus_timer = 1
        game.tick()
        self.assertIsNone(game.bonus)


class ScoreLivesAndWaves(unittest.TestCase):
    def test_points_by_row(self):
        game = playing()
        for row, points in zip(range(5), (30, 20, 20, 10, 10)):
            before = game.score
            r = next(r for r in game.raiders if r.row == row and r.alive)
            for other in game.raiders:
                if other.col == r.col and other.row > row:
                    other.alive = False
            x, y, w, h = game.raider_rect(r)
            game.shot = g.Shot(x + w // 2, y + h + 1, 0, g.SHOT_SPEED)
            game.tick()
            self.assertFalse(r.alive)
            self.assertEqual(game.score - before, points, row)

    def test_an_extra_turret_once(self):
        game = playing()
        game._add(g.EXTRA_LIFE_AT)
        self.assertEqual(game.lives, g.LIVES + 1)
        game._add(g.EXTRA_LIFE_AT)
        self.assertEqual(game.lives, g.LIVES + 1)
        self.assertEqual(game.take_events(), ["extra"])

    def test_the_high_score_follows_the_score(self):
        game = Game(best=100, seed=1)
        game._add(50)
        self.assertEqual(game.best, 100)
        game._add(60)
        self.assertEqual(game.best, 110)

    def test_every_raider_must_go_before_the_next_wave(self):
        game = playing()
        kill(game, keep=1)
        run(game, 50)
        self.assertEqual(game.state, "play")
        kill(game)
        game.tick()
        self.assertEqual(game.state, "cleared")
        run(game, g.CLEARED_STEPS)
        self.assertEqual((game.state, game.wave, game.left), ("ready", 2, 55))

    def test_later_waves_start_lower_and_march_faster(self):
        game = playing()
        fy, interval = game.fy, game.march_interval()
        kill(game)
        game.tick()
        run(game, g.CLEARED_STEPS)
        self.assertEqual(game.fy, fy + g.FORMATION_DROP)
        self.assertLess(game.march_interval(), interval)
        self.assertGreater(min(r.alive for r in game.raiders), 0)
        for _ in range(20):
            game.wave += 1
            game._new_wave()
        self.assertLess(game.fy + 4 * g.ROW_STEP + 10, g.SHELTER_Y)    # never down on the shelters to begin with

    def test_shelters_are_whole_again_for_a_new_wave(self):
        game = playing()
        game.shelters[0].blast(game.shelters[0].x + 5, game.shelters[0].y + 2, game.rng)
        kill(game)
        game.tick()
        run(game, g.CLEARED_STEPS)
        self.assertEqual(len({sh.left for sh in game.shelters}), 1)

    def test_losing_the_last_turret_ends_the_game(self):
        game = playing()
        game.lives = 1
        game.shots = [g.Shot(int(game.tx) + 5, g.TURRET_Y - 4, 0, 2.0)]
        run(game, 5)
        run(game, g.DYING_STEPS)
        self.assertEqual(game.state, "over")

    def test_a_raider_getting_down_to_the_turret_ends_it_whatever_the_lives(self):
        game = playing()
        game.lives = 5
        game.fy = g.TURRET_Y - 4 * g.ROW_STEP - game.raiders[-1].h + 1     # the bottom row a pixel into the turret's row
        game.march_timer = 1
        run(game, 2)
        self.assertTrue(game.invaded)
        run(game, g.DYING_STEPS)
        self.assertEqual(game.state, "over")

    def test_after_game_over_both_buttons_start_again_but_not_while_still_held(self):
        game = playing()
        game._game_over()
        run(game, g.OVER_WAIT_STEPS + 10, BOTH)          # still holding fire from the game: nothing
        self.assertEqual(game.state, "over")
        game.tick()
        game.tick(BOTH)
        self.assertEqual((game.state, game.score, game.lives, game.wave), ("ready", 0, g.LIVES, 1))

    def test_not_before_game_over_has_been_seen_a_moment(self):
        game = playing()
        game._game_over()
        game.tick()
        game.tick(BOTH)
        self.assertEqual(game.state, "over")

    def test_left_alone_after_game_over_it_finishes(self):
        game = playing()
        game._game_over()
        run(game, g.OVER_IDLE_STEPS - 1)
        self.assertFalse(game.finished)
        game.tick()
        self.assertTrue(game.finished)


class Time(unittest.TestCase):
    def test_fixed_steps_whatever_the_frame_rate(self):
        a, b = Game(seed=5), Game(seed=5)
        t = 0.0
        for _ in range(600):                            # 10 s at 60 frames
            t += 1 / 60
            a.update(t, set())
        t = 0.0
        for _ in range(250):                            # the same 10 s at 25 frames
            t += 1 / 25
            b.update(t, set())
        self.assertLessEqual(abs(a.fx - b.fx) + abs(a.fy - b.fy), g.MARCH_DX)

    def test_a_long_pause_does_not_make_it_race(self):
        game = Game(seed=1)
        game.update(0.0, set())
        self.assertEqual(game.update(5.0, set()), g.MAX_STEPS)
        self.assertEqual(game.update(5.0 + 1 / 60 + 1e-9, set()), 1)

    def test_the_same_seed_plays_the_same_game(self):
        def play(seed):
            game = playing(seed)
            game.fire_timer, game.bonus_timer = 30, 300
            for i in range(3000):
                game.tick(BOTH if i % 7 else {"left"} if i % 300 < 150 else {"right"})
            return game.score, game.lives, game.state, [sh.left for sh in game.shelters]
        self.assertEqual(play(3), play(3))

    def test_a_long_game_of_button_mashing_runs_to_the_end(self):
        import random
        rng = random.Random(9)
        game = Game(seed=9)
        held = set()
        for i in range(60 * 60 * 30):
            if i % 20 == 0:
                held = rng.choice([set(), {"left"}, {"right"}, BOTH, BOTH])
            game.tick(held)
            if game.state == "over":
                break
        self.assertEqual(game.state, "over")
        self.assertGreater(game.score, 0)


def button(maintenance, label):
    for name, x, y, w, h in maintenance.menu.buttons():
        if name == label:
            return (x + w // 2, y + h // 2)
    raise AssertionError("no %r on the menu" % label)


class TheMenu(unittest.TestCase):
    """The maintenance knock opens the hidden menu; the game is one of its buttons."""

    def setUp(self):
        self.clock, self.sounds, self.said, self.games, self.shells = Clock(), FakeSounds(), [], [], []
        self.maintenance = Maintenance(self.sounds, self.make_shell, log=self.said.append, clock=self.clock,
                                       games={"Invaders": self.make})
        self.maintenance.step(True, True, set(), [])

    def make_shell(self):
        self.shells.append(FakeShell())
        return self.shells[-1]

    def make(self):
        self.games.append(FakeSession())
        return self.games[-1]

    def knock(self, maintenance=None):
        m = maintenance or self.maintenance
        m.step(True, True, BOTH, [])
        self.clock.t += config.ARM_SECONDS
        m.step(True, True, BOTH, [])
        return [m.step(True, True, set(), [c]) for c in CLOCKWISE]

    def test_the_knock_opens_the_menu_with_rising_bongs(self):
        self.assertEqual(self.knock(), [False, False, False, True])
        self.assertEqual(self.sounds.bongs, [0, 1, 2, 3, LAST_BONG])
        self.assertIsNotNone(self.maintenance.menu)
        self.assertTrue(self.maintenance.open)
        self.assertEqual((self.shells, self.games), ([], []))
        self.assertEqual(self.said, ["menu open"])

    def test_it_offers_the_shell_the_games_and_a_way_back(self):
        self.knock()
        self.assertEqual([b[0] for b in self.maintenance.menu.buttons()], [SHELL, "Invaders", BACK])

    def test_touching_invaders_opens_the_game(self):
        self.knock()
        self.assertTrue(self.maintenance.step(True, True, set(), [button(self.maintenance, "Invaders")]))
        self.assertIsNone(self.maintenance.menu)
        self.assertEqual(len(self.games), 1)
        self.assertEqual(self.said[-1], "Invaders open")

    def test_touching_shell_opens_the_shell(self):
        self.knock()
        self.maintenance.step(True, True, set(), [button(self.maintenance, SHELL)])
        self.assertEqual((len(self.shells), self.games), (1, []))

    def test_back_goes_back_to_the_photos(self):
        self.knock()
        self.assertTrue(self.maintenance.step(True, True, set(), [button(self.maintenance, BACK)]))
        self.assertFalse(self.maintenance.open)
        self.assertEqual(self.said[-1], "menu closed")

    def test_a_touch_between_the_buttons_does_nothing(self):
        self.knock()
        self.assertFalse(self.maintenance.step(True, True, set(), [(5, 5)]))
        self.assertIsNotNone(self.maintenance.menu)

    def test_left_untouched_it_goes_back_to_the_photos(self):
        self.knock()
        self.clock.t += config.MENU_SECONDS - 1
        self.assertFalse(self.maintenance.step(True, True, set(), []))
        self.maintenance.step(True, True, set(), [(5, 5)])          # a touch, even off the buttons, keeps it
        self.clock.t += config.MENU_SECONDS - 1
        self.assertFalse(self.maintenance.step(True, True, set(), []))
        self.clock.t += 1
        self.assertTrue(self.maintenance.step(True, True, set(), []))
        self.assertFalse(self.maintenance.open)

    def test_the_handset_or_a_call_closes_it(self):
        self.knock()
        self.assertTrue(self.maintenance.step(True, False, set(), []))
        self.assertFalse(self.maintenance.open)
        self.knock_again()
        self.assertTrue(self.maintenance.step(False, True, set(), []))
        self.assertFalse(self.maintenance.open)
        self.assertEqual(self.said[-1], "menu closed: a call")

    def knock_again(self):
        self.maintenance.step(True, True, set(), [])
        self.assertEqual(self.knock(), [False, False, False, True])

    def test_the_old_game_knock_does_nothing(self):
        self.maintenance.step(True, True, BOTH, [])
        self.clock.t += config.ARM_SECONDS
        self.maintenance.step(True, True, BOTH, [])
        for c in (BOTTOM_RIGHT, BOTTOM_LEFT, TOP_LEFT, TOP_RIGHT):
            self.maintenance.step(True, True, set(), [c])
        self.assertFalse(self.maintenance.open)

    def test_without_games_only_the_shell(self):
        m = Maintenance(self.sounds, self.make_shell, clock=self.clock)
        m.step(True, True, set(), [])
        self.knock(m)
        self.assertEqual([b[0] for b in m.menu.buttons()], [SHELL, BACK])

    def test_the_buttons_fit_the_screen_and_clear_the_bezel(self):
        self.knock()
        for _, x, y, w, h in self.maintenance.menu.buttons():
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, W - config.SHELL_RIGHT)
            self.assertGreaterEqual(y, config.SHELL_TOP)
            self.assertLessEqual(y + h, H)

    def test_room_for_more_games(self):
        m = Maintenance(self.sounds, self.make_shell, clock=self.clock, games={"Invaders": self.make, "A": self.make, "B": self.make})
        m.step(True, True, set(), [])
        self.knock(m)
        buttons = m.menu.buttons()
        for (_, _, y1, _, h1), (_, _, y2, _, _) in zip(buttons, buttons[1:]):
            self.assertLessEqual(y1 + h1, y2)                 # none overlaps the next

    def test_the_buttons_reach_the_game_and_the_handset_ends_it(self):
        self.knock()
        self.maintenance.step(True, True, set(), [button(self.maintenance, "Invaders")])
        self.maintenance.step(True, True, {"left"}, [])
        self.assertEqual(self.games[0].held, [{"left"}])
        self.assertTrue(self.maintenance.step(True, False, set(), []))
        self.assertIsNone(self.maintenance.game)
        self.assertTrue(self.games[0].closed)
        self.assertEqual(self.said[-1], "Invaders ended: the handset was lifted")

    def test_a_call_ends_the_game(self):
        self.knock()
        self.maintenance.step(True, True, set(), [button(self.maintenance, "Invaders")])
        self.assertTrue(self.maintenance.step(False, True, set(), []))
        self.assertEqual(self.said[-1], "Invaders ended: a call")

    def test_the_game_can_close_itself(self):
        self.knock()
        self.maintenance.step(True, True, set(), [button(self.maintenance, "Invaders")])
        self.games[0].wants_open = False
        self.assertTrue(self.maintenance.step(True, True, set(), []))
        self.assertIsNone(self.maintenance.game)

    def test_a_game_that_cannot_start_is_only_logged(self):
        m = Maintenance(self.sounds, FakeShell, clock=self.clock, log=self.said.append, games={"Invaders": lambda: 1 / 0})
        m.step(True, True, set(), [])
        self.knock(m)
        self.assertTrue(m.step(True, True, set(), [button(m, "Invaders")]))
        self.assertFalse(m.open)
        self.assertIn("Invaders cannot start", self.said[-1])


class TheSession(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.best = Path(self.dir.name) / "best"
        self.clock, self.sounds, self.said = Clock(), FakeSounds(), []
        self.session = Session(self.sounds, self.clock, self.said.append, best_file=self.best, seed=1)
        self.session.sound_maker.join()                 # (its sounds are made in the background)

    def test_its_sound_starts_after_the_last_bong(self):
        self.session.step(set())
        self.assertEqual(self.sounds.game, [])
        self.clock.t += config.GAME_SOUND_AFTER
        self.session.step(set())
        self.assertEqual(self.sounds.game, ["on"])

    def test_the_game_s_sounds_are_played(self):
        self.clock.t += config.GAME_SOUND_AFTER
        self.session.step(set())
        game = self.session.game
        game.state = "play"
        game.march_timer = 1
        self.clock.t += 1 / 60 + 1e-6
        self.session.step(set())
        self.assertTrue(any(e.startswith("march") for e in self.sounds.played))

    def test_the_high_score_is_kept(self):
        self.session.game.best = 1230
        self.session.game.state = "over"
        self.session.step(set())
        self.assertEqual(self.best.read_text().strip(), "1230")
        again = Session(self.sounds, self.clock, best_file=self.best)
        self.assertEqual(again.game.best, 1230)

    def test_a_broken_high_score_file_counts_as_none(self):
        self.best.write_text("rubbish")
        self.assertEqual(Session(self.sounds, self.clock, best_file=self.best).game.best, 0)

    def test_closing_stops_its_sound(self):
        self.session.close()
        self.assertEqual(self.sounds.game, ["off"])

    def test_it_says_when_it_wants_to_close(self):
        self.session.game.finished = True
        self.assertFalse(self.session.step(set()))


class WithThePhone(unittest.TestCase):
    def setUp(self):
        self.clock, self.sounds, self.switches, self.photos, self.taps = Clock(), FakeSounds(), Switches(), Photos(), Taps()
        self.said, self.games = [], []
        self.machine = Machine({"left": Party("Ann", "daughter", "ann")}, clock=self.clock, phone_ok=lambda: True, log=self.said.append)
        self.maintenance = Maintenance(self.sounds, FakeShell, clock=self.clock, games={"Invaders": self.make})
        self.phone = Phone(self.machine, self.switches, NoCalls(), self.sounds, self.photos, clock=self.clock, taps=self.taps,
                           maintenance=self.maintenance, log=self.said.append)
        self.phone.step()
        self.switches.down = BOTH
        self.phone.step()
        self.clock.t += config.ARM_SECONDS
        self.phone.step()
        self.switches.down = set()
        for spot in CLOCKWISE:
            self.taps.next = [spot]
            self.phone.step()
        self.assertTrue(self.phone.menu_showing)
        self.taps.next = [button(self.maintenance, "Invaders")]
        self.phone.step()

    def make(self):
        self.games.append(FakeSession())
        return self.games[-1]

    def test_the_game_has_the_screen_and_the_photos_wait(self):
        self.assertTrue(self.phone.game_showing)
        ticks = self.photos.ticks
        self.phone.step()
        self.assertEqual(self.photos.ticks, ticks)

    def test_its_button_presses_are_not_the_phone_s(self):
        self.switches.events = [("button", "left"), ("button", "right")]
        self.said.clear()
        self.phone.step()
        self.assertEqual(self.said, [])
        self.assertEqual(self.machine.mode, Mode.IDLE)

    def test_lifting_the_handset_goes_to_the_phone_and_ends_the_game(self):
        self.switches.events, self.switches.off_hook = [("lifted",)], True
        starts = self.photos.starts
        self.assertTrue(self.phone.step())
        self.assertEqual(self.machine.mode, Mode.LIFTED)
        self.assertFalse(self.phone.game_showing)
        self.assertIsNone(self.maintenance.game)
        self.assertEqual(self.photos.starts, starts)       # the phone's screen, not the photos

    def test_a_call_stops_the_game_and_its_sound_before_the_ringer(self):
        self.phone._handle(("incoming", Party("Ann", "daughter", "ann")))
        self.phone.step()
        self.assertIsNone(self.maintenance.game)
        self.assertTrue(self.games[0].closed)

    def test_back_to_the_photos_when_it_closes_itself(self):
        self.games[0].wants_open = False
        starts = self.photos.starts
        self.assertTrue(self.phone.step())
        self.assertEqual(self.photos.starts, starts + 1)


class GameSoundOnTheSpeaker(unittest.TestCase):
    def sounds(self, **kw):
        self.made = []

        def mixer(card, log, sounds=None):
            self.made.append(FakeMixer(card))
            return self.made[-1]
        return Sounds(enabled=True, handset_card="Device", ringer_card="Headphones", make_loop=NullLoop, amp=FakeAmp(),
                      make_mixer=mixer, clock=self.clock, **kw)

    def setUp(self):
        self.t = 0.0
        self.clock = lambda: self.t

    def test_on_plays_and_off_stops(self):
        s = self.sounds()
        s.game_on()
        self.assertTrue(s.game.playing)
        self.assertTrue(s.amp.is_on)
        s.game_play(["shoot"])
        self.assertEqual(self.made[0].played, [["shoot"]])
        s.game_off()
        self.assertFalse(s.game.playing)

    def test_the_amplifier_stays_on_while_the_game_plays(self):
        s = self.sounds()
        s.game_on()
        for _ in range(10):
            self.t += 1.0
            s.update(False, False)
        self.assertTrue(s.amp.is_on)
        s.game_off()
        s.update(False, False)
        self.t += config.AMP_OFF_SECONDS + 0.1
        s.update(False, False)
        self.assertFalse(s.amp.is_on)

    def test_the_ringer_stops_it(self):
        s = self.sounds()
        s.game_on()
        s.update(False, True)
        self.assertFalse(s.game.playing)
        s.game_on()                                     # not over the ringer
        self.assertFalse(s.game.playing)

    def test_no_speaker_no_game_sound(self):
        s = Sounds(enabled=False)
        s.game_on()
        s.game_play(["shoot"])
        self.assertFalse(s.game.playing)


class TheMixer(unittest.TestCase):
    def test_sounds_add_up_and_clip(self):
        loud = array.array("h", [30000] * 10)
        voices = [[loud, 0, False], [loud, 0, False]]
        out = array.array("h")
        out.frombytes(game_sound.mix(voices, 10))
        self.assertEqual(list(out), [32767] * 10)
        self.assertEqual(voices, [])                    # both finished

    def test_a_loop_goes_round(self):
        voices = [[array.array("h", [1, 2, 3]), 0, True]]
        out = array.array("h")
        out.frombytes(game_sound.mix(voices, 7))
        self.assertEqual(list(out), [1, 2, 3, 1, 2, 3, 1])
        self.assertEqual(voices[0][1], 1)

    def test_a_short_sound_then_silence(self):
        voices = [[array.array("h", [5, 5]), 0, False]]
        out = array.array("h")
        out.frombytes(game_sound.mix(voices, 4))
        self.assertEqual(list(out), [5, 5, 0, 0])

    def test_every_event_of_the_game_has_a_sound(self):
        sounds = game_sound.make_sounds(0.3)
        for name in ("shoot", "hit", "die", "bonus_hit", "extra", "march0", "march1", "march2", "march3"):
            self.assertIn(name, sounds)
            self.assertGreater(len(sounds[name]), 100)
            self.assertLessEqual(max(map(abs, sounds[name])), int(0.3 * 32767) + 1)

    def test_the_bonus_warble_loops_without_a_click(self):
        b = game_sound.bonus_pcm(0.5)
        self.assertLess(abs(b[-1] - b[0]), 2000)

    def test_play_and_the_bonus_loop(self):
        m = game_sound.Mixer("Headphones", sounds=game_sound.make_sounds(0.3))
        m.play(["shoot", "shoot", "bonus_on", "bonus_on"])
        self.assertEqual(len(m._voices), 2)             # the same sound again starts over; one bonus warble
        m.play(["bonus_off"])
        self.assertEqual(len(m._voices), 1)

    def test_it_feeds_one_aplay_until_stopped(self):
        procs = []
        m = game_sound.Mixer("Headphones", sounds=game_sound.make_sounds(0.3),
                             popen=lambda cmd, **kw: procs.append(FakeProc(cmd)) or procs[-1])
        m.start()
        m.play(["shoot"])
        import time
        time.sleep(0.15)
        self.assertTrue(m.playing)
        m.stop()
        self.assertFalse(m.playing)
        self.assertEqual(len(procs), 1)
        self.assertIn("plughw:CARD=Headphones,DEV=0", procs[0].cmd)
        lead = int(game_sound.LEAD_SECONDS * game_sound.RATE) * 2
        self.assertGreater(len(procs[0].stdin.data), lead)          # the silence first, then the mix
        self.assertTrue(procs[0].terminated)


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
        from judicom.game_view import GameView
        view = GameView()
        game = Game(seed=1)
        for state in ("ready", "play", "dying", "cleared", "over"):
            game.state = state
            game.bonus = [50.0, 1, 100]
            game.bonus_text = [20, 300, 10]
            game.shot = g.Shot(100, 200, 0, 5)
            game.shots = [g.Shot(50, 150, k, 1.5) for k in range(3)]
            game.bursts = [[60, 80, 5]]
            canvas = view.draw(game)
            self.assertEqual(canvas.get_size(), (g.W, g.H))
            self.display.present_small(canvas)

    def test_a_raider_is_drawn_where_the_game_says(self):
        from judicom.game_view import GameView
        view = GameView()
        game = playing()
        canvas = view.draw(game)
        r = game.raiders[0]
        x, y, w, h = game.raider_rect(r)
        lit = [canvas.get_at((x + i, y + j))[:3] != (0, 0, 0) for i in range(w) for j in range(h)]
        self.assertTrue(any(lit))
        r.alive = False
        canvas = view.draw(game)
        self.assertFalse(any(canvas.get_at((x + i, y + j))[:3] != (0, 0, 0) for i in range(w) for j in range(h)))

    def test_every_choice_on_the_menu_has_its_little_picture(self):
        import re
        from judicom import menu_view
        from judicom.menu import Menu
        main = (Path(__file__).resolve().parents[1] / "judicom" / "main.py").read_text()
        games = re.findall(r'^\s+"([^"]+)": lambda: Session', main, re.M)
        self.assertEqual(games, ["Invaders", "Brick Breaker", "Mars Patrol", "Meteoroids", "Stellar Stronghold", "Lunica",
                                 "Plume Knights"])
        for label in ["Shell"] + games:
            pic = menu_view.icon(label, 80)
            self.assertEqual(pic.get_size(), (80, 80), label)
            lit = sum(1 for x in range(8, 72) for y in range(8, 72) if pic.get_at((x, y))[:3] != menu_view.BADGE)
            self.assertGreater(lit, 40, label)            # a picture, not an empty square
        self.assertIsNone(menu_view.icon("A game still to come", 80))   # (its button simply shows its name)
        surface = pygame.Surface((W, H))
        menu_view.show(surface, Menu(["Shell"] + games + ["A game still to come"]))

    def test_shelters_show_their_damage(self):
        from judicom.game_view import GameView
        view = GameView()
        game = playing()
        sh = game.shelters[0]
        canvas = view.draw(game)
        spot = (sh.x + 10, sh.y + 2)
        self.assertNotEqual(canvas.get_at(spot)[:3], (0, 0, 0))
        sh.clear(*spot)
        canvas = view.draw(game)
        self.assertEqual(canvas.get_at(spot)[:3], (0, 0, 0))


# ---- stand-ins --------------------------------------------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class FakeSounds:
    def __init__(self):
        self.bongs, self.game, self.played = [], [], []

    def update(self, dial_tone, ringing, digits=""):
        pass

    def bong(self, step):
        self.bongs.append(step)

    def beep(self):
        pass

    def game_on(self, sounds=None):
        self.game.append("on")
        self.sound_sets = getattr(self, "sound_sets", []) + [sounds]

    def game_play(self, names):
        self.played += names

    def game_off(self):
        self.game.append("off")


class FakeShell:
    dirty = False

    def poll(self):
        return True

    def close(self):
        pass


class FakeSession:
    def __init__(self):
        self.held, self.closed, self.wants_open = [], False, True

    def step(self, held):
        self.held.append(set(held))
        return self.wants_open

    def close(self):
        self.closed = True


class Switches:
    off_hook = False

    def __init__(self):
        self.down, self.events = set(), []

    def poll(self):
        events, self.events = self.events, []
        return events

    def key(self, key):
        return []

    def held(self):
        return self.down


class NoCalls:
    ready = True

    def poll(self):
        return []

    def do(self, action):
        pass


class Photos:
    starts = ticks = 0

    def start(self):
        self.starts += 1

    def tick(self):
        self.ticks += 1


class Taps:
    def __init__(self):
        self.next = []

    def poll(self):
        taps, self.next = self.next, []
        return taps


class NullLoop:
    def __init__(self, *a, **kw):
        self.playing = False

    def start(self):
        self.playing = True

    def stop(self):
        self.playing = False


class FakeAmp:
    def __init__(self):
        self.is_on = False

    def on(self):
        self.is_on = True

    def off(self):
        self.is_on = False

    def close(self):
        pass


class FakeMixer:
    def __init__(self, card):
        self.card, self.playing, self.played = card, False, []

    def start(self):
        self.playing = True

    def play(self, names):
        self.played.append(list(names))

    def stop(self):
        self.playing = False


class FakeStdin:
    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data += b
        return len(b)


class FakeProc:
    def __init__(self, cmd):
        self.cmd, self.stdin, self.terminated = cmd, FakeStdin(), False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


if __name__ == "__main__":
    unittest.main()
