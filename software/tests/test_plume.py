"""Plume Knights (judicom/plume.py): the acceptance list it was built to (numbered as in its specification), and its drawing."""
import tempfile
import unittest
from pathlib import Path

from judicom import config, game_sound
from judicom import plume as pk
from judicom.game import Session
from judicom.plume import Egg, Hatchling, PlumeGame

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def seconds(s):
    return int(round(s / pk.TICK))


def run(g, steps, held=()):
    for _ in range(steps):
        g.tick(held)


def game(wave=1):
    """A game at a wave, playing, nobody yet come (unless a test lets them)."""
    g = PlumeGame(seed=1, attract=False)
    if wave != 1:
        g.wave = wave
        g._begin_wave()
    g.state = "playing"
    g.queue, g.spawn_timer = ["novice"], 10 ** 6          # one still to come (some day): the wave goes on
    g.raptor_at = 10 ** 6
    g.tick()                                            # (both let go since the start)
    g.take_events()
    return g


def in_the_air(g, x=440, y=300):
    g.me.x, g.me.y, g.me.vx, g.me.vy, g.me.grounded = float(x), float(y), 0.0, 0.0, False


def flaps(g, n, every, then=()):
    """n flaps, `every` seconds apart (both pressed for a moment each time)."""
    for _ in range(n):
        run(g, 3, BOTH)
        run(g, seconds(every) - 3, then)


def rider(g, cls, x, y):
    e = g._add_rider(x, y, cls, spawning=False)
    e.think = 10 ** 6                                   # standing still unless a test moves it
    e.grounded = False
    return e


def hold(g, e):
    """Keeps a rider where it is (no flying) for a test of what touching it does."""
    e.think = 10 ** 6
    e.dir, e.ty, e.vx, e.vy = 0, e.y, 0.0, 0.0


class Controls(unittest.TestCase):                                   # 1-9, 35
    def test_1_2_left_and_right_turn_at_once_and_speed_up_with_inertia(self):
        g = game()
        in_the_air(g)
        run(g, seconds(pk.TURN_AFTER) + 1, {"left"})
        self.assertEqual(g.me.face, -1)
        run(g, seconds(0.2), {"left"})
        self.assertAlmostEqual(g.me.vx, -0.2 * pk.ACCEL, delta=10)       # speeding up, not a set speed
        run(g, seconds(1.0), {"left"})
        self.assertAlmostEqual(g.me.vx, -pk.MAX_SPEED, delta=1)
        run(g, seconds(pk.TURN_AFTER) + 1, {"right"})
        self.assertEqual(g.me.face, 1)                                   # turned at once,
        self.assertLess(g.me.vx, -140)                                   # still sliding left

    def test_3_both_together_is_one_flap_not_a_turn(self):
        g = game()
        in_the_air(g)
        g.me.face = 1
        run(g, seconds(0.04), {"left"})                                  # a little apart: still a flap
        vy = g.me.vy
        run(g, 1, BOTH)
        self.assertEqual(g.take_events().count("flap"), 1)
        self.assertEqual(g.me.face, 1)
        self.assertAlmostEqual(g.me.vy - vy, -pk.FLAP + pk.GRAVITY * pk.TICK, delta=0.1)

    def test_one_button_left_down_a_moment_after_a_flap_is_no_turn(self):
        g = game()
        in_the_air(g, y=200)
        g.me.face = 1
        for _ in range(5):                                               # flaps, letting go of right a little late
            run(g, seconds(0.1), BOTH)
            run(g, seconds(0.1), {"right"})
            run(g, seconds(0.05))
        g.me.face = -1
        run(g, seconds(0.15), BOTH)
        run(g, seconds(0.1), {"right"})                                  # 100 ms of right alone, after both: no turn
        self.assertEqual(g.me.face, -1)
        run(g, seconds(0.03), {"right"})                                 # held on past 120 ms: now it turns
        self.assertEqual(g.me.face, 1)

    def test_a_quick_touch_of_one_button_is_no_turn(self):
        g = game()
        in_the_air(g, y=200)
        g.me.face, g.me.vx = 1, 100.0
        run(g, seconds(0.1), {"left"})
        run(g, 2)
        self.assertEqual(g.me.face, 1)
        self.assertGreater(g.me.vx, 75)                                  # (only the air's drag: no push back)

    def test_4_5_again_and_again_flaps_but_held_is_one(self):
        g = game()
        in_the_air(g)
        run(g, seconds(1.0), BOTH)
        self.assertEqual(g.take_events().count("flap"), 1)
        run(g, 2)
        flaps(g, 5, 0.2)
        self.assertEqual(g.take_events().count("flap"), 5)

    def test_a_flap_too_soon_after_the_last_is_ignored(self):
        g = game()
        in_the_air(g)
        run(g, 2, BOTH)
        run(g, 2, {"left"})
        run(g, 2, BOTH)
        self.assertEqual(g.take_events().count("flap"), 1)

    def test_6_7_8_climb_hover_fall(self):
        g = game()
        in_the_air(g, y=300)
        flaps(g, 16, 0.125)                                              # eight a second: up
        self.assertLess(g.me.y, 300 - 150)
        in_the_air(g, y=300)
        g.me.vy = pk.FLAP / 2                                            # (level on average: falling as it flaps)
        flaps(g, 12, 0.26)                                               # about four a second: about level
        self.assertAlmostEqual(g.me.y, 300, delta=60)
        in_the_air(g, y=300)
        run(g, seconds(0.6))                                             # none: down
        self.assertGreater(g.me.y, 400)
        self.assertLessEqual(g.me.vy, pk.MAX_FALL)

    def test_both_held_keeps_the_speed_and_the_way_it_faces(self):
        g = game()
        in_the_air(g, y=200)
        g.me.vx, g.me.face = 200.0, 1
        run(g, seconds(0.3), BOTH)
        self.assertGreater(g.me.vx, 150)
        self.assertEqual(g.me.face, 1)

    def test_9_let_go_and_it_slows_gently(self):
        g = game()
        in_the_air(g, y=150)
        g.me.vx = 240.0
        for i in range(seconds(1.1)):
            g.me.y, g.me.vy = 150.0, 0.0                                  # (kept up in the air)
            g.tick()
            if i == seconds(0.1):
                self.assertGreater(g.me.vx, 190)
        self.assertTrue(20 < g.me.vx < 100)

    def test_35_only_two_buttons(self):
        g = game()
        in_the_air(g)
        before = (g.me.vx, g.me.face)
        run(g, 30, {"up", "fire", "hook"})
        self.assertEqual((g.me.vx, g.me.face), before)


class Arena(unittest.TestCase):                                      # 10-12, 22
    def test_10_round_the_sides(self):
        g = game()
        in_the_air(g, x=575, y=150)
        g.me.vx = 200.0
        run(g, seconds(0.1), BOTH)
        self.assertLess(g.me.x, 30)
        self.assertGreater(g.me.vx, 150)
        in_the_air(g, x=5, y=150)
        g.me.vx = -200.0
        run(g, seconds(0.1), BOTH)
        self.assertGreater(g.me.x, 550)

    def test_11_lands_on_a_rock_and_flies_off_again(self):
        g = game()
        in_the_air(g, x=110, y=500)
        run(g, seconds(1.0))
        self.assertTrue(g.me.grounded)
        self.assertEqual(g.me.y, 620)
        run(g, 2, BOTH)
        run(g, 5)
        self.assertLess(g.me.y, 620)
        self.assertFalse(g.me.grounded)

    def test_12_the_underside_and_the_sides_of_a_rock_stop_it(self):
        g = game()
        in_the_air(g, x=295, y=560)                                      # under the middle rock (its underside at 488)
        flaps(g, 8, 0.1)
        self.assertGreaterEqual(g.me.y - pk.FIG_H, 488 - 0.5)
        in_the_air(g, x=150, y=500)                                      # level with it, flying at its side
        g.me.vx = 200.0
        run(g, seconds(0.3), BOTH)
        self.assertLessEqual(g.me.x + pk.BODY_HW, 195.5)
        self.assertLess(g.me.vx, 50)

    def test_the_sky_has_a_roof(self):
        g = game()
        in_the_air(g, x=440, y=100)
        flaps(g, 10, 0.1)
        self.assertGreaterEqual(g.me.y - pk.FIG_H, 0)

    def test_22_the_shore_crumbles_as_the_waves_go_on(self):
        widths = [sum(b - a for a, b in pk.ground(w)) for w in (1, 4, 7, 20)]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertGreater(widths[0], widths[2])
        g = game(7)
        self.assertTrue(g.over_lake(60))
        self.assertFalse(game(1).over_lake(60))

    def test_into_the_lake_is_a_knight_lost(self):
        g = game(7)
        in_the_air(g, x=60, y=700)
        lives = g.lives
        run(g, seconds(1.0))
        self.assertEqual(g.lives, lives - 1)
        self.assertIn("lava", g.take_events())


class Riders(unittest.TestCase):                                     # 13-15
    def test_13_they_come_one_after_another_at_the_glowing_places(self):
        g = game()
        g._setup_wave()
        g.raptor_at = 10 ** 6
        g.me.x = 200                                                    # (off the spawning places)
        run(g, seconds(0.35))
        self.assertEqual(len(g.enemies), 1)
        self.assertEqual(g.enemies[0].state, "spawning")
        self.assertIn((g.enemies[0].x, g.enemies[0].y), [(float(x), float(y)) for x, y in pk.SPAWNS])
        run(g, seconds(pk.SPAWN_GAP))
        self.assertEqual(len(g.enemies), 2)
        run(g, seconds(pk.SPAWN_GAP))
        self.assertEqual(len(g.enemies), 3)
        self.assertEqual(len({(e.x, e.y) for e in g.enemies if e.state == "spawning"}), len(
            [e for e in g.enemies if e.state == "spawning"]))

    def test_14_they_fly_by_the_same_rules(self):
        g = game(3)
        g.shield = 10 ** 6
        g.queue, g.spawn_timer = ["novice", "veteran", "elite"], 0.1
        run(g, seconds(8))
        self.assertTrue(g.enemies)
        for e in g.enemies:
            self.assertEqual(e.state, "active")
            self.assertLessEqual(e.vy, pk.MAX_FALL)
            self.assertGreaterEqual(e.vy, -pk.MAX_UP)
            self.assertLessEqual(abs(e.vx), g.skill(e, "speed") + 1)
        self.assertTrue(any(e.flap_age < 1.0 for e in g.enemies))
        self.assertIn("ATTACK", {e.ai for e in g.enemies} | self._states_seen(g))

    def _states_seen(self, g):
        seen = set()
        for _ in range(seconds(10)):
            g.tick()
            seen |= {e.ai for e in g.enemies}
        return seen

    def test_15_the_better_they_are_the_more_they_get_above_the_knight(self):
        above = {}
        for cls in pk.CLASSES:
            total = 0
            for seed in range(4):
                g = game()
                g.rng.seed(seed)
                g.shield = 10 ** 6
                in_the_air(g, x=440, y=420)
                e = g._add_rider(110, 620, cls, spawning=False)
                for _ in range(seconds(12)):
                    g.me.x, g.me.y, g.me.vx, g.me.vy = 440.0, 420.0, 0.0, 0.0      # the knight hangs still
                    g.tick()
                    if e not in g.enemies:
                        break
                    if g.me.y - e.y >= pk.JOUST_TOL and abs(pk.wrap_dx(e.x, g.me.x)) < 150:
                        total += 1
            above[cls] = total
        self.assertLess(above["novice"], above["veteran"])
        self.assertLess(above["veteran"], above["elite"])

    def test_the_settings_grow_with_the_class(self):
        for name in ("speed", "accel", "aggression", "evade", "aim"):
            values = [pk.SKILL[c][name] for c in pk.CLASSES]
            self.assertEqual(values, sorted(values), name)
        self.assertEqual([pk.SKILL[c]["speed"] for c in pk.CLASSES], [150, 190, 230])
        self.assertEqual([pk.SKILL[c]["points"] for c in pk.CLASSES], [500, 750, 1500])


class Jousting(unittest.TestCase):                                   # 16-18
    def meet(self, lift):
        """The knight and a novice face to face, the knight `lift` higher."""
        g = game()
        in_the_air(g, x=300, y=300)
        e = rider(g, "novice", 330, 300 + lift)
        hold(g, e)
        g.me.face, e.face = 1, -1
        g._jousts()
        return g, e

    def test_16_higher_lance_wins(self):
        g, e = self.meet(12)
        self.assertNotIn(e, g.enemies)
        self.assertEqual(g.score, 500)
        self.assertEqual(len(g.eggs), 1)
        self.assertIn("joust", g.take_events())
        self.assertTrue(g.runaways)                                     # its drake flies off

    def test_17_lower_lance_loses(self):
        g, e = self.meet(-12)
        self.assertIn(e, g.enemies)
        self.assertEqual((g.knight, g.lives), ("dying", pk.LIVES - 1))
        self.assertIn("die", g.take_events())

    def test_18_level_lances_bounce_apart_once(self):
        g, e = self.meet(5)
        self.assertIn(e, g.enemies)
        self.assertEqual(g.knight, "ok")
        self.assertLess(g.me.vx, 0)
        self.assertGreater(e.vx, 0)
        self.assertEqual(g.take_events(), ["bounce"])
        e.x, g.me.x = 330.0, 300.0
        g._jousts()
        self.assertEqual(g.take_events(), [])                           # not again while they are still touching
        e.cool = 0
        g._jousts()
        self.assertEqual(g.take_events(), ["bounce"])

    def test_only_the_bodies_and_lance_count_not_the_whole_picture(self):
        g = game()
        in_the_air(g, x=300, y=300)
        e = rider(g, "novice", 300 + 45, 300 - 40)                      # the corners of their pictures overlap
        hold(g, e)
        g.me.face, e.face = -1, 1
        g._jousts()
        self.assertEqual((g.knight, len(g.enemies)), ("ok", 1))

    def test_while_shining_after_coming_back_nothing_unhorses_the_knight(self):
        g, e = self.meet(0)
        g = game()
        g.shield = 1.0
        in_the_air(g, x=300, y=300)
        e = rider(g, "elite", 330, 260)
        hold(g, e)
        g._jousts()
        self.assertEqual((g.knight, g.lives), ("ok", pk.LIVES))

    def test_across_the_side_too(self):
        g = game()
        in_the_air(g, x=5, y=300)
        e = rider(g, "novice", 570, 320)
        hold(g, e)
        g.me.face = -1
        g._jousts()
        self.assertNotIn(e, g.enemies)


class Eggs(unittest.TestCase):                                       # 19-21
    def test_19_an_egg_falls_bounces_and_rests_on_a_rock(self):
        g = game()
        g.me.x = 470                                                    # (out of the way)
        g.eggs.append(Egg(110, 450, "veteran"))
        ys = []
        for _ in range(seconds(2)):
            g._eggs(pk.TICK)
            ys.append(g.eggs[0].y)
        self.assertEqual(ys[-1], 620)
        self.assertTrue(g.eggs[0].bounced)
        self.assertLess(min(ys[ys.index(620):]), 620)                   # up again a little after it first lands
        self.assertIsNotNone(g.eggs[0].timer)

    def test_20_eggs_picked_up_in_a_row_are_worth_more(self):
        g = game()
        got = []
        for i in range(6):
            in_the_air(g, x=300, y=150)
            g.eggs.append(Egg(300, 150, "veteran"))
            before = g.score
            g._eggs(pk.TICK)
            got.append(g.score - before)
        self.assertEqual(got, [250, 500, 750, 1000, 1000, 1000])
        g._lose_knight("joust")
        g.knight = "ok"
        g.eggs.append(Egg(g.me.x, g.me.y, "veteran"))
        before = g.score
        g._eggs(pk.TICK)
        self.assertEqual(g.score - before, 250)                         # back to the start after a knight lost
        g.chain = 3
        g._setup_wave()
        self.assertEqual(g.chain, 0)                                    # and in a new wave

    def test_21_left_alone_it_hatches_and_a_rider_one_class_better_rides_again(self):
        g = game()
        g.me.x = 470
        egg = Egg(110, 620, "veteran")
        egg.grounded, egg.bounced = True, True
        g.eggs.append(egg)
        run(g, seconds(0.1))
        self.assertIsNotNone(egg.timer)
        run(g, seconds(pk.INCUBATE))
        self.assertEqual(len(g.hatchlings), 1)
        self.assertIn("hatch", g.take_events())
        run(g, seconds(pk.HATCH_WAIT + 0.1))
        self.assertIsNotNone(g.hatchlings[0].mount)                     # its drake on the way
        run(g, seconds(5))
        self.assertEqual([e.cls for e in g.enemies], ["veteran"])

    def test_a_knight_on_foot_can_be_picked_up_too(self):
        g = game()
        g.hatchlings.append(Hatchling(110.0, 620.0, "elite"))
        g.hatchlings[0].mount = [200.0, 300.0, 1]
        g.me.x, g.me.y = 110.0, 620.0
        g._hatchlings(pk.TICK)
        self.assertEqual((g.hatchlings, g.score), ([], 250))
        self.assertTrue(g.runaways)                                     # its drake turns away

    def test_into_the_lake_an_egg_is_gone_for_good(self):
        g = game(7)
        g.eggs.append(Egg(60, 700, "elite"))
        run(g, seconds(1.0))
        self.assertEqual(g.eggs, [])
        self.assertIn("egg_lost", g.take_events())
        self.assertEqual(g.hatchlings, [])

    def test_an_elite_egg_hatches_an_elite(self):
        g = game()
        in_the_air(g, x=300, y=300)
        e = rider(g, "elite", 330, 320)
        hold(g, e)
        g._jousts()
        self.assertEqual(g.eggs[0].hatches, "elite")


class Serpent(unittest.TestCase):                                    # 23, 24
    def low(self, wave=pk.GUARDIAN_FROM):
        g = game(wave)
        in_the_air(g, x=50, y=pk.LAVA_Y - 60)
        return g

    def hover(self, g, secs, every=0.25):
        for _ in range(int(secs / every)):
            run(g, 3, BOTH)
            run(g, seconds(every) - 3)

    def test_23_it_rises_at_a_knight_low_over_the_lake(self):
        g = self.low()
        run(g, 2)
        self.assertIn("grab", g.take_events())
        run(g, seconds(pk.GRAB_RISE + 0.05))
        self.assertEqual(g.knight, "grabbed")
        y = g.me.y
        run(g, seconds(0.3))
        self.assertGreater(g.me.y, y)                                   # pulled down

    def test_not_in_the_first_waves_nor_over_the_shore(self):
        g = self.low(wave=1)
        run(g, seconds(0.5))
        self.assertIsNone(g.serpent)
        g = game(pk.GUARDIAN_FROM)
        in_the_air(g, x=290, y=pk.GROUND_Y - 30)
        run(g, 2)
        self.assertIsNone(g.serpent)

    def test_24_three_quick_flaps_break_free(self):
        g = self.low()
        run(g, seconds(pk.GRAB_RISE + 0.05))
        self.assertEqual(g.knight, "grabbed")
        flaps(g, 3, 0.2)
        self.assertEqual(g.knight, "ok")
        self.assertLess(g.me.vy, -100)
        self.assertIn("escape", g.take_events())
        self.assertGreater(g.serpent_cool, 0)
        g.me.y = pk.LAVA_Y - 60
        run(g, 2)
        self.assertNotEqual(g.knight, "grabbed")                        # not straight away again

    def test_too_slow_and_into_the_lake(self):
        g = self.low()
        run(g, seconds(pk.GRAB_RISE + 0.05))
        flaps(g, 3, 0.7)                                                # three, but not within 1.2 s
        run(g, seconds(3))
        self.assertEqual(g.lives, pk.LIVES - 1)
        self.assertIn("serpent_off", g.take_events())


class Raptor(unittest.TestCase):                                     # 25, 26
    def test_25_a_wave_that_goes_on_too_long_brings_it(self):
        g = game()
        g.raptor_at = pk.raptor_after(1)
        rider(g, "novice", 110, 300)
        run(g, seconds(pk.raptor_after(1) - 1))
        self.assertIsNone(g.raptor)
        run(g, seconds(1.1))
        self.assertIsNotNone(g.raptor)
        self.assertIn("raptor", g.take_events())
        self.assertLess(pk.raptor_after(10), pk.raptor_after(1))

    def raptor(self, face_knight, dy=0, dx=2):
        g = game()
        rider(g, "novice", 110, 200)
        in_the_air(g, x=200, y=400)
        g.me.face = 1 if face_knight else -1
        r = pk.Raptor(1, 0)
        r.face = -1
        tip_x, tip_y = g.me.lance_tip()
        r.x, r.y = tip_x + pk.RAPTOR_NECK + dx, tip_y + dy                # its head on the lance's tip
        g.raptor = r
        g._raptor(0.0)
        return g

    def test_26_the_lance_in_its_head_brings_it_down(self):
        g = self.raptor(True)
        self.assertIsNone(g.raptor)
        self.assertEqual((g.score, g.knight), (pk.RAPTOR_POINTS, "ok"))
        self.assertIn("raptor_die", g.take_events())

    def test_but_its_body_is_death(self):
        g = self.raptor(True, dy=40, dx=-12)                            # lower: the lance misses, its head meets the bird
        self.assertEqual(g.knight, "dying")
        g = self.raptor(False)
        self.assertEqual(g.knight, "dying")

    def test_it_chases(self):
        g = game()
        rider(g, "novice", 110, 200)
        in_the_air(g, x=400, y=300)
        g.raptor = pk.Raptor(-1, 600)
        g.shield = 10 ** 6
        for _ in range(seconds(2)):
            g.me.x, g.me.y = 400.0, 300.0
            g._raptor(pk.TICK)
        self.assertLess(abs(g.raptor.y - (300 - 26)), 40)
        self.assertGreater(g.raptor.x, 100)


class Waves(unittest.TestCase):                                      # 27-34
    def test_27_the_wave_ends_only_when_riders_eggs_and_knights_on_foot_are_all_gone(self):
        g = game()
        g.queue = []
        g.eggs.append(Egg(110, 620, "veteran"))
        g.eggs[0].timer = 100.0
        g.me.x = 470
        run(g, 5)
        self.assertEqual(g.state, "playing")
        g.eggs = []
        g.hatchlings.append(Hatchling(110, 620, "veteran"))
        run(g, 5)
        self.assertEqual(g.state, "playing")
        g.hatchlings = []
        run(g, 2)
        self.assertEqual(g.state, "clear")
        self.assertIn("wave_done", g.take_events())
        run(g, seconds(pk.CLEAR + 0.1))
        self.assertEqual((g.state, g.wave), ("intro", 2))

    def test_28_the_table_and_beyond(self):
        self.assertEqual([pk.wave_riders(w) for w in range(1, 8)],
                         [(3, 0, 0), (4, 0, 0), (3, 2, 0), (3, 3, 0), (2, 3, 1), (2, 4, 2), (1, 4, 3)])
        elites = [pk.wave_riders(w)[2] for w in range(7, 30)]
        self.assertEqual(elites, sorted(elites))
        self.assertTrue(all(sum(pk.wave_riders(w)) == 8 for w in range(8, 30)))
        g = game(12)
        e = rider(g, "novice", 100, 100)
        self.assertGreater(g.skill(e, "speed"), pk.SKILL["novice"]["speed"])

    def test_29_egg_waves_now_and_then(self):
        self.assertEqual([w for w in range(1, 30) if pk.is_egg_wave(w)], [8, 13, 18, 23, 28])
        g = game(8)
        g._setup_wave()
        self.assertEqual(g.queue, [])
        self.assertGreater(len(g.eggs), 10)
        self.assertTrue(all(e.timer is not None and e.timer < pk.INCUBATE * 2 for e in g.eggs))

    def test_every_egg_gathered_is_a_bonus(self):
        g = game(8)
        g.eggs, g.egg_total, g.queue = [], 12, []
        before = g.score
        run(g, 2)
        self.assertEqual(g.score - before, pk.EGG_WAVE_BONUS)
        self.assertIn("bonus", g.take_events())

    def test_survival_waves_pay_for_losing_nobody(self):
        self.assertEqual([w for w in range(1, 16) if pk.is_survival(w)], [3, 7, 11, 15])
        g = game(3)
        g.queue = []
        run(g, 2)
        self.assertEqual(g.score, pk.SURVIVAL_BONUS)
        g = game(3)
        g.lost_one, g.queue = True, []
        run(g, 2)
        self.assertEqual(g.score, 0)

    def test_30_five_knights(self):
        self.assertEqual(game().lives, 5)

    def test_31_a_knight_lost_leaves_the_wave_as_it_was(self):
        g = game()
        riders = [rider(g, "novice", x, 200) for x in (100, 300)]
        g.eggs.append(Egg(470, 640, "veteran"))
        g._lose_knight("joust")
        run(g, seconds(pk.DYING + 0.1))
        self.assertEqual(g.knight, "ok")
        self.assertEqual([e for e in g.enemies], riders)
        self.assertEqual(len(g.eggs) + len(g.hatchlings), 1)
        self.assertGreater(g.shield, 0)
        self.assertIn((g.me.x, g.me.y), [(float(x), float(y)) for x, y in pk.RESPAWNS])
        self.assertEqual((g.me.vx, g.me.vy), (0.0, 0.0))

    def test_32_another_knight_every_20000(self):
        g = game()
        g._add(19990)
        self.assertEqual(g.lives, 5)
        g._add(20)
        self.assertEqual(g.lives, 6)
        g._add(20000)
        self.assertEqual(g.lives, 7)

    def test_33_the_last_knight_lost_is_game_over_then_both_for_another(self):
        g = game()
        rider(g, "novice", 300, 100)
        g.lives = 1
        g._lose_knight("joust")
        run(g, seconds(pk.DYING + 0.1))
        self.assertEqual(g.state, "over")
        self.assertIn("over", g.take_events())
        run(g, seconds(pk.OVER_WAIT))
        run(g, 2, BOTH)
        self.assertEqual((g.state, g.lives, g.score, g.wave), ("intro", 5, 0, 1))

    def test_34_the_high_score_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            s = Session(FakeSounds(), lambda: 100.0, best_file=best, make_game=PlumeGame, make_view=lambda: None,
                        make_sounds=lambda: {})
            s.sound_maker.join()
            s.game.score = s.game.best = 27182
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "27182")

    def test_the_title_both_starts_and_left_alone_closes(self):
        g = PlumeGame(seed=1)
        g.tick()
        g.tick(BOTH)
        self.assertEqual(g.state, "intro")
        self.assertIn("start", g.take_events())
        g = PlumeGame(seed=1)
        run(g, seconds(pk.ATTRACT_IDLE + 0.1))
        self.assertTrue(g.finished)

    def test_every_event_has_a_sound(self):
        sounds = game_sound.plume_sounds()
        for name in ("flap", "land", "joust", "bounce", "die", "lava", "egg", "egg_lost", "hatch", "spawn", "grab", "escape",
                     "raptor", "raptor_die", "start", "wave", "wave_done", "bonus", "extra", "over", "serpent",
                     "raptor_loop"):
            self.assertGreater(len(sounds[name]), 50, name)
        self.assertEqual(len(game_sound.PLUME_TUNE), 3)
        self.assertLessEqual(len(sounds["start"]) / game_sound.RATE, pk.FIRST_INTRO)

    def test_a_long_game_of_button_mashing_runs_on_without_trouble(self):
        import random
        rng = random.Random(4)
        g = PlumeGame(seed=4, attract=False)
        held = set()
        for i in range(seconds(240)):
            if i % 15 == 0:
                held = rng.choice([set(), {"left"}, {"right"}, BOTH, set(), BOTH])
            g.tick(held)
            if g.state == "over":
                break
        self.assertGreater(g.score, 0)

    def test_many_waves_run_through(self):
        """A knight that cannot be unhorsed, hunting from above: it gets through the waves, egg waves and all."""
        g = PlumeGame(seed=7, attract=False)
        held = set()
        for i in range(seconds(400)):
            if i % 6 == 0:
                held = _pilot(g, held)
            g.shield, g.lives = 1.0, 5
            g.tick(held)
        self.assertGreater(g.wave, 9)


def _pilot(g, last):
    me = g.me
    targets = [(e.x, e.y - 40) for e in g.enemies if e.state == "active"]
    targets += [(x.x, x.y) for x in g.eggs] + [(h.x, h.y) for h in g.hatchlings] or [(290, 400)]
    tx, ty = min(targets, key=lambda t: abs(pk.wrap_dx(me.x, t[0])) + abs(t[1] - me.y))
    dx = pk.wrap_dx(me.x, tx)
    if me.y > ty and me.vy > -150 and last != BOTH:
        return BOTH
    if abs(dx) > 10:
        return {"right"} if dx > 0 else {"left"}
    return set()


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
        from judicom.plume_view import PlumeView
        view = PlumeView()
        g = PlumeGame(seed=1)
        view.draw(g)
        g.new_game()
        run(g, seconds(4))
        for state in ("intro", "playing", "clear", "over"):
            g.state = state
            canvas = view.draw(g)
            self.assertEqual(canvas.get_size(), (config.SCREEN_W // 2, config.SCREEN_H // 2))
        self.display.present_small(view.draw(g))

    def test_everything_in_the_arena_draws(self):
        from judicom.plume_view import PlumeView
        g = game(5)
        rider(g, "elite", 3, 300)                                       # across the side
        s = g._add_rider(110, 620, "novice")
        s.spawn_t = 0.2
        g.eggs.append(Egg(300, 470, "veteran"))
        g.eggs[0].timer = 1.0
        g.hatchlings.append(Hatchling(470, 640, "elite"))
        g.hatchlings[0].mount = [400.0, 500.0, -1]
        g.raptor = pk.Raptor(1, 300)
        g.serpent = {"x": 60.0, "t": 0.1, "state": "rise", "flaps": []}
        g.runaways.append([200.0, 300.0, 1, 0.1, "drake"])
        g.bursts = [[200, 300, 0.1, k] for k in ("joust", "knight", "egg", "lava", "raptor")]
        g.popups.append([300, 300, 0.1, 750])
        g.faller = [300.0, 300.0, 0.0]
        PlumeView().draw(g)

    def test_a_rider_facing_left_is_the_mirror_of_one_facing_right(self):
        from judicom.plume_view import PlumeView
        view = PlumeView()
        a = view.pic(("knight", "knight"), lambda: __import__("judicom.plume_view").plume_view.knight_picture("knight"), 1)
        b = view.pic(("knight", "knight"), lambda: __import__("judicom.plume_view").plume_view.knight_picture("knight"), -1)
        w = a.get_width()
        self.assertTrue(all(a.get_at((x, 3)) == b.get_at((w - 1 - x, 3)) for x in range(w)))

    def test_the_lance_is_drawn_where_it_strikes(self):
        from judicom import plume_view as pv
        pic = pv.knight_picture("knight")
        tip_row = pv.SPRITE_H - 1 - round(pk.LANCE_UP * pv.K)
        lit = [x for x in range(pv.SPRITE_W) for y in (tip_row - 1, tip_row, tip_row + 1) if pic.get_at((x, y))[3]]
        self.assertGreaterEqual(max(lit) - pv.MIDDLE, round(pk.LANCE_REACH * pv.K) - 1)


class FakeSounds:
    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        pass

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
