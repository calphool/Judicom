"""Brick Breaker (judicom/bricks.py): the acceptance list it was built to, the ball's collisions, and its drawing."""
import math
import random
import tempfile
import unittest
from pathlib import Path

from judicom import bricks as b
from judicom import config, game_sound
from judicom.bricks import BrickGame, brick_rect
from judicom.game import Session

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def run(game, steps, held=()):
    for _ in range(steps):
        game.tick(held)


def launched(seed=1):
    game = BrickGame(seed=seed)
    game.tick()
    game.tick(BOTH)
    assert game.state == "playing"
    return game


def aim(game, x, y, vx, vy):
    """Put the ball at x, y going vx, vy (in pixels a second)."""
    game.ball.x, game.ball.y, game.ball.vx, game.ball.vy = x, y, vx, vy


def overlaps_a_brick(game):
    ball = game.ball
    for row in range(b.ROWS):
        for col in range(b.COLS):
            if game.bricks[row][col]:
                x, y, w, h = brick_rect(col, row)
                cx, cy = min(max(ball.x, x), x + w), min(max(ball.y, y), y + h)
                if (ball.x - cx) ** 2 + (ball.y - cy) ** 2 < b.BALL_R ** 2 - 1e-6:
                    return True
    return False


class ThePaddle(unittest.TestCase):                    # acceptance 1-4
    def test_left_moves_it_left_and_right_moves_it_right(self):
        game = BrickGame(seed=1)
        x = game.px
        run(game, 30, {"left"})
        self.assertLess(game.px, x)
        x = game.px
        run(game, 30, {"right"})
        self.assertGreater(game.px, x)

    def test_at_360_pixels_a_second(self):
        game = BrickGame(seed=1)
        game.px = 0.0
        run(game, 10, {"right"})                       # past the moment's wait
        x = game.px
        run(game, 30, {"right"})
        self.assertAlmostEqual(game.px - x, b.PADDLE_SPEED * 0.5, places=6)

    def test_it_stops_when_let_go_and_when_both_are_held(self):
        game = BrickGame(seed=1)
        run(game, 20, {"left"})
        x = game.px
        run(game, 20)
        self.assertEqual(game.px, x)
        run(game, 20, BOTH)
        self.assertEqual(game.px, x)

    def test_both_pressed_a_little_apart_does_not_nudge_it(self):
        game = BrickGame(seed=1)
        x = game.px
        run(game, 4, {"left"})                          # 67 ms: inside the 75 ms allowance
        game.tick(BOTH)
        self.assertEqual(game.px, x)
        self.assertEqual(game.state, "playing")

    def test_it_stays_on_the_field(self):
        game = BrickGame(seed=1)
        run(game, 200, {"left"})
        self.assertEqual(game.px, 0)
        run(game, 300, {"right"})
        self.assertEqual(game.px, b.FIELD_W - b.PADDLE_W)


class Launching(unittest.TestCase):                    # acceptance 5, 6
    def test_before_launch_the_ball_rides_on_the_paddle(self):
        game = BrickGame(seed=1)
        run(game, 30, {"right"})
        self.assertEqual(game.state, "ready")
        self.assertAlmostEqual(game.ball.x, game.px + b.PADDLE_W / 2)
        self.assertLess(game.ball.y + b.BALL_R, b.PADDLE_Y)

    def test_both_buttons_launch_it_upward_at_15_degrees(self):
        game = launched()
        angle = math.degrees(math.atan2(abs(game.ball.vx), -game.ball.vy))
        self.assertAlmostEqual(angle, b.LAUNCH_ANGLE, places=6)
        self.assertAlmostEqual(game.ball.speed, b.BALL_SPEED, places=6)

    def test_holding_both_does_not_launch_again_and_a_new_press_is_needed(self):
        game = BrickGame(seed=1)
        game.tick()
        run(game, 5, BOTH)
        self.assertEqual(game.state, "playing")
        game.lives = 3
        game._ready()
        run(game, 30, BOTH)                             # still held from the last launch: nothing
        self.assertEqual(game.state, "ready")
        game.tick()
        game.tick(BOTH)
        self.assertEqual(game.state, "playing")

    def test_buttons_already_down_at_the_start_do_not_launch(self):
        game = BrickGame(seed=1)
        run(game, 10, BOTH)
        self.assertEqual(game.state, "ready")

    def test_launches_go_left_and_right_by_turns(self):
        game = launched()
        first = game.ball.vx
        game._ready()
        game.tick()
        game.tick(BOTH)
        self.assertLess(first * game.ball.vx, 0)


class TheBall(unittest.TestCase):                      # acceptance 7, 8, 11
    def test_the_side_walls_and_the_top_turn_it_back(self):
        game = launched()
        aim(game, 20, 300, -300, -100)
        run(game, 10)
        self.assertGreater(game.ball.vx, 0)
        self.assertGreaterEqual(game.ball.x - b.BALL_R, 0)
        aim(game, b.FIELD_W - 20, 300, 300, -100)
        run(game, 10)
        self.assertLess(game.ball.vx, 0)
        self.assertLessEqual(game.ball.x + b.BALL_R, b.FIELD_W)
        game.bricks = [[False] * b.COLS for _ in range(b.ROWS)]
        game.bricks[7][0] = True                        # keep the level going
        aim(game, 240, b.TOP_WALL + 20, 0, -300)
        run(game, 10)
        self.assertGreater(game.ball.vy, 0)
        self.assertGreaterEqual(game.ball.y - b.BALL_R, b.TOP_WALL)
        self.assertIn("wall", game.take_events())

    def bounce(self, offset):
        game = launched()
        game.px = 200.0
        aim(game, game.px + b.PADDLE_W / 2 + offset, b.PADDLE_Y - 30, 0, 300)
        run(game, 10)
        return game

    def test_the_middle_of_the_paddle_sends_it_straight_up(self):
        game = self.bounce(0)
        self.assertLess(game.ball.vy, 0)
        self.assertAlmostEqual(game.ball.vx, 0, places=6)
        self.assertIn("paddle", game.take_events())

    def test_the_ends_send_it_off_to_the_side_more_the_further_out(self):
        angles = []
        for offset in (-36, -18, 18, 36):
            game = self.bounce(offset)
            angles.append(math.degrees(math.atan2(game.ball.vx, -game.ball.vy)))
        self.assertAlmostEqual(angles[0], -60, places=4)
        self.assertAlmostEqual(angles[1], -30, places=4)
        self.assertAlmostEqual(angles[2], 30, places=4)
        self.assertAlmostEqual(angles[3], 60, places=4)

    def test_beyond_the_end_counts_as_the_end(self):
        game = self.bounce(36 + 4)
        self.assertAlmostEqual(math.degrees(math.atan2(game.ball.vx, -game.ball.vy)), 60, places=4)

    def test_the_paddle_keeps_the_speed(self):
        game = self.bounce(20)
        self.assertAlmostEqual(game.ball.speed, 300, places=6)

    def test_a_ball_going_up_through_the_paddle_is_not_turned(self):
        game = launched()
        game.px = 200.0
        aim(game, 236, b.PADDLE_Y + 3, 0, -300)
        game.tick()
        self.assertLess(game.ball.vy, 0)

    def test_a_ball_already_past_the_paddle_is_lost(self):
        game = launched()
        game.px = 200.0
        aim(game, 236, b.PADDLE_Y + 8, 0, 300)
        run(game, 30)
        self.assertEqual(game.state, "lost")

    def test_it_goes_through_a_gap_and_bounces_about_above_the_wall(self):
        game = launched()
        gap = range(5, 9)
        for row in range(b.ROWS):                       # a gap four columns wide
            for col in gap:
                game.bricks[row][col] = False
        x, _, _, _ = brick_rect(5, 0)
        aim(game, x + 8, b.WALL_BOTTOM + 20, b.BALL_SPEED * 0.447, -b.BALL_SPEED * 0.894)    # up the gap, slanting right
        score = game.score
        for _ in range(240):
            game.tick()
            if game.ball.y + b.BALL_R < b.WALL_TOP:
                break
        self.assertEqual(game.score, score)             # straight through, nothing hit
        self.assertTrue(game.over_the_top)
        run(game, 30)
        self.assertGreater(game.score, score)           # and back down onto the top row from above
        self.assertTrue(any(not game.bricks[0][c] for c in range(b.COLS) if c not in gap))     # hit from above


class Bricks(unittest.TestCase):                       # acceptance 9, 10
    def test_112_in_8_rows_of_14_centred(self):
        game = BrickGame(seed=1)
        self.assertEqual(game.left, 112)
        x0, _, _, _ = brick_rect(0, 0)
        x1, _, w, _ = brick_rect(b.COLS - 1, 0)
        self.assertEqual(x0, b.FIELD_W - (x1 + w))
        self.assertEqual(brick_rect(0, 0)[1], 105)

    def hit_from_below(self, game, col, row):
        x, y, w, h = brick_rect(col, row)
        for r in range(row + 1, b.ROWS):
            game.bricks[r][col] = False
        aim(game, x + w / 2, y + h + 20, 0, -300)
        run(game, 10)

    def test_a_hit_brick_goes_and_the_ball_turns_back(self):
        game = launched()
        self.hit_from_below(game, 3, 7)
        self.assertFalse(game.bricks[7][3])
        self.assertEqual(game.left, 111)
        self.assertGreater(game.ball.vy, 0)

    def test_points_by_colour(self):
        for row, points in enumerate((7, 7, 5, 5, 3, 3, 1, 1)):
            game = launched()
            self.hit_from_below(game, 5, row)
            self.assertEqual(game.score, points, row)
            self.assertIn("brick%d" % (row // 2), game.take_events())

    def test_a_side_hit_turns_it_sideways(self):
        game = launched()
        x, y, w, h = brick_rect(0, 7)
        game.bricks[7][1:] = [False] * (b.COLS - 1)
        game.bricks[6] = [False] * b.COLS
        aim(game, x + w + 20, y + h / 2, -300, 0.0001)
        run(game, 10)
        self.assertFalse(game.bricks[7][0])
        self.assertGreater(game.ball.vx, 0)

    def test_one_brick_at_a_time_and_never_left_inside_one(self):
        game = launched()
        aim(game, brick_rect(4, 7)[0] + 31, b.WALL_BOTTOM + 15, 0, -300)    # straight at the gap between two bricks
        run(game, 20)
        self.assertEqual(game.left, 111)
        self.assertFalse(overlaps_a_brick(game))


class NoTunnelling(unittest.TestCase):
    def test_at_top_speed_it_cannot_pass_through_a_brick(self):
        for col in range(b.COLS):
            for vx in (-100, 0, 100):
                game = launched()
                game.speed = b.BALL_MAX
                x, y, w, h = brick_rect(col, 7)
                aim(game, x + w / 2, b.WALL_BOTTOM + 10, vx, -500)
                game.ball.set_speed(b.BALL_MAX)
                run(game, 3)
                self.assertEqual(game.left, 111, (col, vx))

    def test_long_games_keep_every_rule(self):
        """Thousands of bounces with a paddle that follows the ball: the ball never ends a step inside a brick or a wall,
        never goes past the speed limit, and always keeps going up or down at a fair rate."""
        for seed in range(4):
            rng = random.Random(seed)
            game = launched(seed)
            for i in range(60 * 240):
                target = game.ball.x - b.PADDLE_W / 2 + rng.uniform(-30, 30)
                held = {"left"} if game.px > target + 3 else {"right"} if game.px < target - 3 else set()
                if game.state == "ready" and i % 10 == 0:
                    held = BOTH if (i // 10) % 2 else set()
                game.tick(held)
                if game.state == "playing":
                    ball = game.ball
                    self.assertFalse(overlaps_a_brick(game), (seed, i))
                    self.assertGreaterEqual(ball.x - b.BALL_R, -1e-9)
                    self.assertLessEqual(ball.x + b.BALL_R, b.FIELD_W + 1e-9)
                    self.assertGreaterEqual(ball.y - b.BALL_R, b.TOP_WALL - 1e-9)
                    self.assertLessEqual(ball.speed, b.BALL_MAX + 1e-6)
                    self.assertGreaterEqual(abs(ball.vy), 0.49 * ball.speed)
                if game.state == "over":
                    break
            self.assertGreater(game.score, 50, seed)


class Speed(unittest.TestCase):                        # acceptance 12
    def test_quicker_every_12_bricks(self):
        game = launched()
        game.over_the_top = True                        # leave that out of it
        game.bricks = [[False] * b.COLS for _ in range(b.ROWS)]
        game.bricks[0][b.COLS - 1] = True               # one far away, so the level goes on
        ratios = []
        for n in range(1, 25):
            col = n % (b.COLS - 1)
            game.bricks[7][col] = True
            before = game.speed
            x, y, w, h = brick_rect(col, 7)
            aim(game, x + w / 2, y + h + b.BALL_R + 1, 0, -before)
            game.tick()
            self.assertFalse(game.bricks[7][col])
            ratios.append(round(game.speed / before, 6))
        self.assertEqual(ratios[11], b.SPEEDUP)
        self.assertEqual(ratios[23], b.SPEEDUP)
        self.assertEqual([r for i, r in enumerate(ratios) if i not in (11, 23)], [1.0] * 22)

    def test_quicker_the_first_time_above_the_wall_only(self):
        game = launched()
        for row in range(b.ROWS):
            game.bricks[row][0] = False
        x, _, w, _ = brick_rect(0, 0)
        aim(game, x + w / 2, b.WALL_TOP - 20, 0, -100)
        game.ball.set_speed(game.speed)
        game.tick()
        self.assertAlmostEqual(game.speed, b.BALL_SPEED * b.OVER_THE_TOP)
        game.tick()
        self.assertAlmostEqual(game.speed, b.BALL_SPEED * b.OVER_THE_TOP)

    def test_never_past_the_top_speed_and_the_direction_is_kept(self):
        game = launched()
        aim(game, 240, 300, 300, -400)
        for _ in range(30):
            game._quicken(1.5)
        self.assertAlmostEqual(game.ball.speed, b.BALL_MAX)
        self.assertAlmostEqual(game.ball.vx / game.ball.vy, 300 / -400)

    def test_each_level_starts_a_little_quicker(self):
        game = BrickGame(seed=1)
        first = game.start_speed
        game.level = 2
        game._new_level()
        self.assertGreater(game.start_speed, first)
        game.level = 50
        game._new_level()
        self.assertLessEqual(game.start_speed, b.LEVEL_START_MAX)


class LivesAndLevels(unittest.TestCase):               # acceptance 13-17
    def lose_a_ball(self, game):
        game.px = 0.0
        aim(game, 400, b.PADDLE_Y - 20, 0, 300)
        for _ in range(60):
            game.tick()
            if game.state != "playing":
                break

    def test_missing_costs_a_life_and_the_bricks_stay_as_they_were(self):
        game = launched()
        game.bricks[0][0] = game.bricks[3][7] = False
        before = [row[:] for row in game.bricks]
        self.lose_a_ball(game)
        self.assertEqual((game.state, game.lives), ("lost", b.LIVES - 1))
        self.assertIn("lost", game.take_events())
        run(game, b.LOST_STEPS)
        self.assertEqual(game.state, "ready")
        self.assertEqual(game.bricks, before)
        game.tick()
        game.tick(BOTH)
        self.assertEqual(game.state, "playing")

    def test_the_last_ball_lost_is_game_over(self):
        game = launched()
        game.lives = 1
        self.lose_a_ball(game)
        run(game, b.LOST_STEPS)
        self.assertEqual(game.state, "over")
        self.assertIn("over", game.take_events())

    def test_every_brick_must_go_and_then_a_new_level(self):
        game = launched()
        game.bricks = [[False] * b.COLS for _ in range(b.ROWS)]
        game.bricks[7][13] = True
        self.assertEqual(game.state, "playing")
        x, y, w, h = brick_rect(13, 7)
        aim(game, x + w / 2, y + h + 20, 0, -300)
        run(game, 10)
        self.assertEqual(game.state, "cleared")
        self.assertIn("level", game.take_events())
        score, lives = game.score, game.lives
        run(game, b.CLEARED_STEPS)
        self.assertEqual((game.state, game.level, game.left), ("ready", 2, 112))
        self.assertEqual((game.score, game.lives), (score, lives))
        self.assertEqual(game.px, (b.FIELD_W - b.PADDLE_W) / 2)

    def test_after_game_over_both_buttons_start_a_new_game(self):
        game = launched()
        game.score, game.level, game.lives = 300, 4, 0
        game.state, game.timer = "over", 0
        run(game, b.OVER_WAIT_STEPS + 5, BOTH)           # held from before: nothing
        self.assertEqual(game.state, "over")
        game.tick()
        game.tick(BOTH)
        self.assertEqual((game.state, game.score, game.lives, game.level, game.left), ("ready", 0, b.LIVES, 1, 112))
        self.assertEqual(game.speed, b.BALL_SPEED)

    def test_left_alone_after_game_over_it_finishes(self):
        game = BrickGame(seed=1)
        game.state, game.timer = "over", 0
        run(game, b.OVER_IDLE_STEPS - 1)
        self.assertFalse(game.finished)
        game.tick()
        self.assertTrue(game.finished)

    def test_the_high_score_follows(self):
        game = BrickGame(best=5, seed=1)
        self.test_points = None
        game.tick()
        game.tick(BOTH)
        x, y, w, h = brick_rect(0, 0)
        for r in range(1, b.ROWS):
            game.bricks[r][0] = False
        aim(game, x + w / 2, y + h + 20, 0, -300)
        run(game, 10)
        self.assertEqual(game.best, 7)


class OnlyTwoButtons(unittest.TestCase):                # acceptance 18
    def test_the_whole_game_is_played_with_left_and_right(self):
        game = BrickGame(seed=3)
        for held in ({"up"}, {"fire"}, {"x"}):
            run(game, 10, held)
        self.assertEqual(game.state, "ready")           # nothing but left and right means anything


class Time(unittest.TestCase):
    def test_fixed_steps_whatever_the_frame_rate(self):
        a, b2 = BrickGame(seed=5), BrickGame(seed=5)
        for g in (a, b2):
            g.update(0.0, set())
        t = 0.0
        for _ in range(60):
            t += 1 / 60
            a.update(t, {"right"})
        t = 0.0
        for _ in range(24):
            t += 1 / 24
            b2.update(t, {"right"})
        self.assertLess(abs(a.px - b2.px), b.PADDLE_SPEED / 60 * 2)

    def test_a_long_pause_does_not_make_it_race(self):
        game = BrickGame(seed=1)
        game.update(0.0, set())
        self.assertEqual(game.update(5.0, set()), b.MAX_STEPS)


class ItsSession(unittest.TestCase):
    def test_its_sounds_high_score_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            sounds, t, said = FakeSounds(), [100.0], []
            s = Session(sounds, lambda: t[0], said.append, best_file=best, make_game=BrickGame,
                        make_view=lambda: None, make_sounds=game_sound.bricks_sounds)
            s.sound_maker.join()
            t[0] += config.GAME_SOUND_AFTER
            s.step(set())
            self.assertIs(sounds.sets[0], game_sound.bricks_sounds())
            s.game.score = s.game.best = 42
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "42")
            self.assertEqual(said[-1], "game over: 42 points, level 1")

    def test_every_event_has_a_sound(self):
        sounds = game_sound.bricks_sounds()
        for name in ("paddle", "wall", "brick0", "brick1", "brick2", "brick3", "lost", "level", "over"):
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

    def test_every_state_draws_at_half_the_screen(self):
        from judicom.bricks_view import BrickView
        view = BrickView()
        game = BrickGame(seed=1)
        for state in ("ready", "playing", "lost", "cleared", "over"):
            game.state, game.timer = state, 100
            canvas = view.draw(game)
            self.assertEqual(canvas.get_size(), (config.SCREEN_W // 2, config.SCREEN_H // 2))
            self.display.present_small(canvas)

    def test_the_field_is_clear_of_the_bezel_and_undistorted(self):
        from judicom import bricks_view as v
        self.assertGreaterEqual(v.sy(0) * 2, config.SHELL_TOP)
        self.assertGreaterEqual(v.sx(0) - 1, 0)                                       # the left wall line
        self.assertLessEqual((v.sx(b.FIELD_W) + 1) * 2, config.SCREEN_W - config.SHELL_RIGHT)   # and the right one
        self.assertLessEqual(v.sy(b.FIELD_H) * 2, config.SCREEN_H)
        w, h = v.sx(b.FIELD_W) - v.sx(0), v.sy(b.FIELD_H) - v.sy(0)
        self.assertAlmostEqual(w / h, b.FIELD_W / b.FIELD_H, places=2)

    def test_a_broken_brick_is_not_drawn(self):
        from judicom.bricks_view import BrickView, sx, sy
        view = BrickView()
        game = BrickGame(seed=1)
        x, y, w, h = brick_rect(5, 2)
        spot = (sx(x + w / 2), sy(y + h / 2))
        self.assertNotEqual(view.draw(game).get_at(spot)[:3], (0, 0, 0))
        game.bricks[2][5] = False
        self.assertEqual(view.draw(game).get_at(spot)[:3], (0, 0, 0))


class FakeSounds:
    def __init__(self):
        self.sets = []

    def game_on(self, sounds=None):
        self.sets.append(sounds)

    def game_play(self, names):
        pass

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
