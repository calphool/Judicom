"""Lunica (judicom/lunica.py): the acceptance list it was built to, its flight paths, capture and rescue, the bonus stage,
and the hidden menu's two columns (which came with it)."""
import math
import tempfile
import unittest
from pathlib import Path

from judicom import config, game_sound
from judicom import lunica as lu
from judicom.game import Session
from judicom.lunica import LunicaGame, Path as Flight
from judicom.menu import BACK, Menu

try:
    import pygame
except ImportError:
    pygame = None

BOTH = {"left", "right"}


def seconds(s):
    return int(round(s / lu.TICK))


def run(g, steps, held=()):
    for _ in range(steps):
        g.tick(held)


def game(stage=1):
    """A game at a stage, playing, the formation already in place and nobody attacking unless a test says so."""
    g = LunicaGame(seed=1, attract=False)
    if stage != 1:
        g.stage = stage
        g._begin_stage()
    g.state = "playing"
    g.tick()
    settle(g)
    g.attack_timer = 10 ** 6
    return g


def settle(g):
    for e in g.enemies:
        e.state = "form"
        e.x, e.y = g.slot_xy(e)
    g.stage_t = 30.0


def alive(g):
    return [e for e in g.enemies if e.alive]


class Controls(unittest.TestCase):                       # acceptance 1-6, 32
    def test_left_and_right_move_at_300_and_stop_at_once(self):
        g = game()
        x = g.px
        run(g, seconds(0.075) + seconds(0.5), {"left"})
        self.assertAlmostEqual(x - g.px, 150, delta=4)
        x = g.px
        g.tick()
        self.assertEqual(g.px, x)
        run(g, seconds(0.075) + seconds(0.5), {"right"})
        self.assertAlmostEqual(g.px - x, 150, delta=4)

    def test_never_off_the_sides_never_up_or_down(self):
        g = game()
        run(g, seconds(3), {"left"})
        self.assertEqual(g.px, lu.PLAYER_W / 2)
        run(g, seconds(3), {"right"})
        self.assertEqual(g.px, lu.W - lu.PLAYER_W / 2)
        self.assertEqual(lu.PLAYER_Y, 735)

    def test_both_held_stops_and_fires_again_and_again_two_at_most(self):
        g = game()
        for e in g.enemies:
            e.state = "gone"                            # (nothing to stop the shots)
        g.enemies[0].state = "form"
        g.enemies[0].sx = 10                            # (one left, out of the way: the stage goes on)
        x = g.px
        g.tick(BOTH)
        self.assertEqual(len(g.shots), 1)
        run(g, seconds(0.15), BOTH)
        self.assertEqual(len(g.shots), 2)
        run(g, seconds(0.5), BOTH)
        self.assertLessEqual(len(g.shots), 2)
        fired = sum(1 for e in g.take_events() if e == "fire")
        run(g, seconds(3), BOTH)
        fired += sum(1 for e in g.take_events() if e == "fire")
        self.assertGreaterEqual(fired, 4)               # held: it keeps on firing as shots leave the screen (1.5 s across)
        self.assertEqual(g.px, x)

    def test_letting_go_stops_the_firing(self):
        g = game()
        g.tick(BOTH)
        g.take_events()
        run(g, seconds(1))
        self.assertNotIn("fire", g.take_events())

    def test_only_two_buttons(self):
        g = game()
        x = g.px
        run(g, seconds(1), {"up", "fire"})
        self.assertEqual((g.px, g.shots), (x, []))


class Paths(unittest.TestCase):
    def test_a_path_is_smooth_and_walked_by_distance(self):
        p = Flight((0, 0)).curve((0, 100), (100, 100), (100, 0)).arc((150, 0), 180).done()
        x, y, _ = p.at(0)
        self.assertEqual((x, y), (0, 0))
        x, y, _ = p.at(p.length)
        self.assertAlmostEqual(x, 200, delta=0.5)
        steps = [math.hypot(p.at(d + 5)[0] - p.at(d)[0], p.at(d + 5)[1] - p.at(d)[1]) for d in range(0, int(p.length) - 5, 5)]
        self.assertTrue(all(4.5 < s <= 5.01 for s in steps))       # an even pace along it, no jumps

    def test_the_heading_follows_the_path(self):
        p = Flight((0, 0)).line((100, 0)).done()
        self.assertAlmostEqual(p.at(50)[2], 0, places=3)
        p = Flight((0, 0)).line((0, 100)).done()
        self.assertAlmostEqual(p.at(50)[2], 90, places=3)


class Entry(unittest.TestCase):                          # acceptance 7-9
    def test_groups_fly_in_on_curves_and_settle_into_a_symmetric_formation(self):
        g = LunicaGame(seed=1, attract=False)
        g.state = "playing"
        headings, complete = set(), None
        for i in range(seconds(15)):                    # (the spec: in place in about 10 to 15 seconds)
            g.tick()
            for e in g.enemies:
                if e.state == "enter":
                    headings.add(round(e.angle / 30))
            if complete is None and all(e.state == "form" for e in g.enemies if e.alive):
                complete = i * lu.TICK
        self.assertGreater(len(headings), 6)            # they turned this way and that: curves, loops
        self.assertIsNotNone(complete)
        self.assertTrue(10 <= complete <= 15, complete)
        g.shield = 10 ** 6                              # (the low ones can fly into it: kept out of it here)
        self.assertEqual(len(g.enemies), 40)
        for kind, n in (("commander", 4), ("interceptor", 16), ("scout", 20)):
            self.assertEqual(sum(1 for e in g.enemies if e.kind == kind), n)
        xs = sorted(e.sx for e in g.enemies)
        self.assertAlmostEqual(sum(xs) / len(xs), lu.FORM_X)
        rows = sorted({e.sy for e in g.enemies})
        self.assertEqual(rows, [lu.FORM_TOP + i * lu.SPACING for i in range(5)])

    def test_some_ways_in_come_down_through_the_fighters_row(self):
        for i in lu.LOW:
            crossing = [x for x, y in lu.ENTRIES[i].pts if abs(y - lu.PLAYER_Y) < lu.PLAYER_H / 2]
            self.assertTrue(crossing, i)
            self.assertGreater(max(crossing) - min(crossing), 100, i)        # across a good part of the row

    def test_a_fighter_that_sits_still_in_the_entry_gets_flown_into(self):
        hit = 0
        for seed in range(3):
            g = LunicaGame(seed=seed, attract=False)
            g.state = "playing"
            for _ in range(seconds(12)):
                g.tick()
                if g.ship == "gone":
                    hit += 1
                    break
        self.assertGreater(hit, 0)

    def test_five_groups_of_eight_one_after_another(self):
        g = LunicaGame(seed=1, attract=False)
        starts = sorted(min(e.wait for e in g.enemies if e.bonus_group == k) for k in range(5))
        self.assertEqual([round(b - a, 6) for a, b in zip(starts, starts[1:])], [lu.GROUP_GAP] * 4)
        self.assertEqual(sorted({e.bonus_group for e in g.enemies}), [0, 1, 2, 3, 4])
        self.assertTrue(all(sum(1 for e in g.enemies if e.bonus_group == k) == 8 for k in range(5)))

    def test_the_formation_sways_and_gaps_stay(self):
        g = game()
        gone = g.enemies[5]
        gone.state = "gone"
        a = [g.slot_xy(e) for e in g.enemies[:3]]
        run(g, seconds(1.3))
        b = [g.slot_xy(e) for e in g.enemies[:3]]
        self.assertNotEqual(a, b)
        self.assertFalse(gone.alive)
        run(g, seconds(5))
        self.assertFalse(gone.alive)                    # nobody moves into its place

    def test_shot_during_the_entry(self):
        g = LunicaGame(seed=1, attract=False)
        g.state = "playing"
        hits = 0
        for _ in range(seconds(12)):
            g.tick(BOTH)
            hits += sum(1 for e in g.take_events() if e in ("hit", "boss_hit", "boss_die"))
        self.assertGreater(hits, 0)


class Diving(unittest.TestCase):                         # acceptance 10-14
    def test_they_dive_on_curves_fire_and_come_back_to_their_places(self):
        g = game()
        g.attack_timer = 0.0
        g.shield = 10 ** 6
        seen_dive, fired, came_back = set(), 0, set()
        for _ in range(seconds(30)):
            n = len(g.enemy_shots)
            g.tick()
            fired += max(0, len(g.enemy_shots) - n)
            for e in g.enemies:
                if e.state == "dive":
                    seen_dive.add(e.id)
                elif e.state == "form" and e.id in seen_dive:
                    came_back.add(e.id)
        self.assertGreater(len(seen_dive), 3)
        self.assertGreater(fired, 0)
        self.assertGreater(len(came_back), 2)

    def test_never_more_divers_than_the_stage_allows(self):
        g = game()
        g.attack_timer = 0.0
        g.shield = 10 ** 6
        for _ in range(seconds(30)):
            g.tick()
            self.assertLessEqual(sum(1 for e in g.enemies if e.state in ("dive", "beam") and e.group is None) , g.max_divers)

    def test_an_enemy_shot_destroys_the_fighter(self):
        g = game()
        g.enemy_shots.append(lu.Shot(g.px, lu.PLAYER_Y - 60, 0.0, 300.0, -1))
        run(g, seconds(0.5))
        self.assertEqual((g.ship, g.lives), ("gone", lu.LIVES - 1))

    def test_a_diver_flying_into_the_fighter_destroys_both(self):
        g = game()
        e = g.enemies[-1]
        e.state, e.x, e.y = "dive", g.px, lu.PLAYER_Y - 30
        e.path = Flight((g.px, lu.PLAYER_Y - 30)).line((g.px, lu.PLAYER_Y + 200)).done()
        e.dist, e.speed = 0.0, 200.0
        run(g, seconds(0.3))
        self.assertEqual(g.ship, "gone")
        self.assertFalse(e.alive)

    def test_losing_a_fighter_keeps_the_formation_as_it_was(self):
        g = game()
        for e in g.enemies[:7]:
            e.state = "gone"
        g._lose_ship()
        run(g, seconds(lu.DESTROYED) + 2)
        self.assertEqual(g.ship, "ok")
        self.assertEqual(len(alive(g)), 33)
        self.assertGreater(g.shield, 1.5)


class Scoring(unittest.TestCase):                        # acceptance 15, 16
    def shoot(self, g, e):
        g.px = e.x
        g.shots.append(lu.Shot(e.x, e.y + 60, 0.0, -lu.SHOT_SPEED, 0))
        run(g, seconds(0.3))

    def test_points_by_kind_more_when_diving(self):
        for kind, (calm, diving) in (("scout", (50, 100)), ("interceptor", (80, 160))):
            g = game()
            e = next(o for o in g.enemies if o.kind == kind and o.sy == max(p.sy for p in g.enemies if p.kind == kind))
            for o in g.enemies:                         # (nothing else in the way of the shot)
                if o is not e:
                    o.state = "gone"
            self.shoot(g, e)
            self.assertEqual(g.score, calm, kind)
            g = game()
            e = next(o for o in g.enemies if o.kind == kind and o.sy == max(p.sy for p in g.enemies if p.kind == kind))
            for o in g.enemies:
                if o is not e:
                    o.state = "gone"
            e.state = "dive"
            e.path = Flight((e.x, e.y)).line((e.x, e.y + 1)).done()
            e.dist, e.speed = 0.0, 0.0
            self.shoot(g, e)
            self.assertEqual(g.score, diving, kind)

    def test_a_commander_takes_two_hits_and_shows_the_first(self):
        g = game()
        for o in g.enemies:
            if o.kind != "commander":
                o.state = "gone"
        c = g.enemies[[o.kind for o in g.enemies].index("commander")]
        self.shoot(g, c)
        self.assertEqual((c.hp, c.alive, g.score), (1, True, 0))
        self.assertIn("boss_hit", g.take_events())
        self.shoot(g, c)
        self.assertFalse(c.alive)
        self.assertEqual(g.score, 150)

    def test_a_commander_diving_with_two_escorts_is_worth_1600(self):
        g = game()
        c = next(o for o in g.enemies if o.kind == "commander")
        g.rng.seed(3)
        for _ in range(20):                             # (until it takes two escorts)
            settle(g)
            g._dive(c, escorts=True)
            if len(c.group) == 2:
                break
        self.assertEqual(len(c.group), 2)
        c.hp = 1
        run(g, seconds(0.2))
        self.shoot(g, c)
        self.assertEqual(g.score, 1600)


class Capture(unittest.TestCase):                        # acceptance 17-23
    def capture(self, g):
        c = next(o for o in g.enemies if o.kind == "commander")
        g._capture_dive(c)
        for _ in range(seconds(5)):
            g.tick()
            if c.state == "beam":
                break
        g.px = c.x
        return c

    def test_the_beam_catches_a_fighter_that_stays_under_it(self):
        g = game()
        c = self.capture(g)
        self.assertAlmostEqual(c.y, lu.CAPTURE_Y, delta=1)
        self.assertTrue(g.beam_on)
        run(g, seconds(1.0))
        self.assertEqual(g.ship, "rising")
        run(g, seconds(lu.RISE_SECONDS + 0.1))
        self.assertTrue(c.captive)
        self.assertEqual(g.lives, lu.LIVES - 1)
        self.assertIn("captured", g.take_events())
        run(g, seconds(lu.DESTROYED + 1))
        self.assertEqual(g.ship, "ok")                  # a fighter from the reserve

    def test_out_from_under_it_in_time_and_nothing_happens(self):
        g = game()
        c = self.capture(g)
        g.px = c.x + 150
        run(g, seconds(lu.BEAM_SECONDS + 0.5))
        self.assertFalse(c.captive)
        self.assertEqual(g.ship, "ok")
        self.assertNotEqual(c.state, "beam")

    def captured(self):
        g = game()
        c = self.capture(g)
        run(g, seconds(1.0 + lu.RISE_SECONDS + 0.2))
        run(g, seconds(lu.DESTROYED + 1))
        settle(g)
        self.assertTrue(c.captive)
        return g, c

    def test_the_caught_fighter_stays_with_its_captor(self):
        g, c = self.captured()
        run(g, seconds(2))
        x, y = g.captive_xy(c)
        self.assertAlmostEqual(x, c.x)
        self.assertLess(y, c.y)

    def test_shooting_the_captor_as_it_dives_brings_the_fighter_back_two_fighters(self):
        g, c = self.captured()
        g._dive(c, escorts=False)
        run(g, seconds(0.6))
        c.hp = 1
        g.shots.append(lu.Shot(c.x, c.y + 40, 0.0, -lu.SHOT_SPEED, 0))
        run(g, seconds(0.2))
        self.assertFalse(c.alive)
        self.assertIsNotNone(g.rescued)
        self.assertIn("rescue", g.take_events())
        run(g, seconds(4))
        self.assertTrue(g.dual)
        self.assertEqual(len(g.ships()), 2)

    def test_shot_in_the_formation_the_caught_fighter_is_lost(self):
        g, c = self.captured()
        c.hp = 1
        g.shots.append(lu.Shot(c.x, c.y + 20, 0.0, -lu.SHOT_SPEED, 0))     # (just under it: an interceptor is below)
        run(g, seconds(0.2))
        self.assertFalse(c.alive)
        self.assertIsNone(g.rescued)
        run(g, seconds(3))
        self.assertFalse(g.dual)

    def dual(self):
        g = game()
        g.dual = True
        return g

    def test_two_fighters_fire_side_by_side_two_shots_each(self):
        g = self.dual()
        for e in g.enemies:
            e.state = "gone"
        g.enemies[0].state, g.enemies[0].sx = "form", 10
        g.tick(BOTH)
        self.assertEqual(sorted(s.x for s in g.shots), [g.px, g.px + lu.PLAYER_W])
        run(g, seconds(0.5), BOTH)
        self.assertLessEqual(len(g.shots), 4)
        self.assertLessEqual(max(sum(1 for s in g.shots if s.owner == i) for i in (0, 1)), 2)

    def test_two_fighters_are_a_bigger_target_but_one_hit_loses_only_one(self):
        g = self.dual()
        x2 = g.px + lu.PLAYER_W
        g.enemy_shots.append(lu.Shot(x2, lu.PLAYER_Y - 30, 0.0, 300.0, -1))     # where one fighter alone would not be
        run(g, seconds(0.3))
        self.assertFalse(g.dual)
        self.assertEqual((g.ship, g.lives), ("ok", lu.LIVES))
        self.assertEqual(g.px, x2 - lu.PLAYER_W)        # the other (left) one carries on where it was


class Bonus(unittest.TestCase):                          # acceptance 24, 25
    def test_stage_3_is_a_bonus_stage_and_then_every_fourth(self):
        self.assertEqual([s for s in range(1, 20) if lu.is_bonus(s)], [3, 7, 11, 15, 19])

    def test_nobody_shoots_or_rams_and_they_fly_across_and_away(self):
        g = LunicaGame(seed=1, attract=False)
        g.stage = 3
        g._begin_stage()
        self.assertTrue(g.bonus)
        run(g, seconds(lu.STAGE_INTRO) + 1)
        for _ in range(seconds(40)):
            g.tick()
            self.assertEqual(g.enemy_shots, [])
            self.assertEqual(g.ship, "ok")
            if g.state != "playing":
                break
        self.assertEqual(g.state, "summary")
        self.assertEqual(g.tally[0], 0)
        self.assertEqual(g.score, 0)

    def test_points_for_hits_groups_and_a_perfect_stage(self):
        g = LunicaGame(seed=1, attract=False)
        g.stage = 3
        g._begin_stage()
        g.state = "playing"
        for e in g.enemies:                             # every one hit (as if by perfect shooting)
            e.state = "enter"
            g._hit(e)
        g.tick()
        self.assertEqual(g.state, "summary")
        self.assertEqual(g.tally, (40, 40, 5000, 10000, 4000 + 5000 + 10000))
        self.assertEqual(g.score, 19000)
        self.assertIn("perfect", g.take_events())
        run(g, seconds(lu.BONUS_SUMMARY) + 1)
        self.assertEqual((g.stage, g.state), (4, "intro"))


class Stages(unittest.TestCase):                         # acceptance 26-31
    def test_the_last_enemy_down_clears_the_stage_and_the_next_comes(self):
        g = game()
        for e in g.enemies[1:]:
            e.state = "gone"
        g._hit(g.enemies[0])
        g._hit(g.enemies[0])
        g.tick()
        self.assertEqual(g.state, "clear")
        run(g, seconds(lu.CLEAR) + 1)
        self.assertEqual((g.stage, g.state, len(alive(g))), (2, "intro", 40))

    def test_the_table(self):
        for stage, entry, dive, divers, shot, every in ((1, 150, 190, 2, 240, 2.5), (5, 190, 250, 4, 300, 1.7),
                                                        (10, 230, 310, 6, 360, 1.1), (20, 230, 310, 6, 360, 1.1)):
            g = LunicaGame(seed=1, attract=False)
            g.stage = stage
            g._new_stage()
            self.assertEqual((round(g.entry_speed, 6), round(g.dive_speed, 6), g.max_divers, round(g.shot_speed, 6),
                              round(g.attack_every, 6)), (entry, dive, divers, shot, every))

    def test_extra_fighters_at_20000_70000_then_every_70000(self):
        g = game()
        lives = g.lives
        for points, more in ((19999, 0), (1, 1), (50000, 2), (70000, 3), (69999, 3), (1, 4)):
            g._add(points)
            self.assertEqual(g.lives - lives, more, g.score)

    def test_the_last_fighter_lost_is_game_over_then_both_for_another(self):
        g = game()
        for _ in range(lu.LIVES):
            g.shield = 0
            g._lose_ship()
            run(g, seconds(lu.DESTROYED) + 2, BOTH)     # (firing as the last one goes, and still holding on)
        self.assertEqual(g.state, "over")
        run(g, seconds(lu.OVER_WAIT) + 2, BOTH)
        self.assertEqual(g.state, "over")
        g.tick()
        g.tick(BOTH)
        self.assertEqual((g.state, g.score, g.lives, g.stage), ("intro", 0, lu.LIVES, 1))

    def test_the_title_flies_a_demonstration_and_both_start(self):
        g = LunicaGame(seed=1)
        run(g, seconds(3))
        self.assertTrue(any(e.state == "enter" for e in g.enemies))
        self.assertEqual(g.take_events(), [])
        g.tick(BOTH)
        self.assertEqual(g.state, "intro")

    def test_the_title_left_alone_closes(self):
        g = LunicaGame(seed=1)
        run(g, seconds(lu.ATTRACT_IDLE) + 1)
        self.assertTrue(g.finished)

    def test_the_high_score_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            best = Path(d) / "best"
            s = Session(FakeSounds(), lambda: 100.0, best_file=best, make_game=LunicaGame, make_view=lambda: None,
                        make_sounds=game_sound.lunica_sounds)
            s.sound_maker.join()
            s.game.score = s.game.best = 31415
            s.game.state = "over"
            s.step(set())
            self.assertEqual(best.read_text().strip(), "31415")

    def test_every_event_has_a_sound(self):
        sounds = game_sound.lunica_sounds()
        for name in ("fire", "hit", "boss_hit", "boss_die", "die", "entry", "dive", "beam", "captured", "rescue", "docked",
                     "start", "stage", "bonus", "perfect", "extra", "over"):
            self.assertGreater(len(sounds[name]), 50, name)

    def test_the_tunes(self):
        self.assertAlmostEqual(game_sound.note_hz("A4"), 440.0)
        self.assertAlmostEqual(game_sound.note_hz("C5"), 523.25, places=1)
        self.assertAlmostEqual(game_sound.note_hz("G#4"), 415.30, places=1)
        caught = game_sound.CAUGHT_TUNE[0][0]
        self.assertIn(("G#5", 1), caught)                   # minor, with its raised seventh
        self.assertNotIn("C#", " ".join(n for n, _ in caught))
        self.assertEqual(caught[-1][0][0], "A")             # and home on A
        self.assertEqual(len(game_sound.START_TUNE), 3)    # three parts at once
        sounds = game_sound.lunica_sounds()
        rate = game_sound.RATE
        self.assertTrue(1.5 < len(sounds["captured"]) / rate < 2.5)
        self.assertTrue(2.5 < len(sounds["start"]) / rate <= lu.FIRST_INTRO)

    def test_a_new_game_opens_with_its_tune_and_a_longer_first_stage_screen(self):
        g = LunicaGame(seed=1)
        g.tick()
        g.tick(BOTH)
        self.assertIn("start", g.take_events())
        self.assertEqual((g.state, round(g.timer, 6)), ("intro", lu.FIRST_INTRO))
        g.stage = 1
        g._begin_stage()
        self.assertIn("stage", g.take_events())
        self.assertEqual(g.timer, lu.STAGE_INTRO)

    def test_a_long_game_of_button_mashing_runs_on_without_trouble(self):
        import random
        rng = random.Random(4)
        g = LunicaGame(seed=4, attract=False)
        held = set()
        for i in range(seconds(240)):
            if i % 40 == 0:
                held = rng.choice([set(), {"left"}, {"right"}, BOTH, BOTH])
            g.tick(held)
            if g.state == "over":
                break
        self.assertGreater(g.score, 0)


class LateSound(unittest.TestCase):
    def test_a_game_started_before_its_sound_is_ready_still_hears_its_tune(self):
        sounds, t = Recorder(), [100.0]
        s = Session(sounds, lambda: t[0], make_game=LunicaGame, make_view=lambda: None, make_sounds=lambda: {"x": 1})
        s.sound_maker.join()
        s._sound_at = t[0] + 2.0                        # (the sound not ready for 2 s)
        for held in (set(), set(), set(), BOTH, BOTH):
            t[0] += 1 / 60
            s.step(held)
        self.assertEqual(sounds.played, [])
        t[0] += 2.0
        s.step(set())
        self.assertIn("start", sounds.played)

    def test_but_not_ones_from_long_before(self):
        sounds, t = Recorder(), [100.0]
        s = Session(sounds, lambda: t[0], make_game=LunicaGame, make_view=lambda: None, make_sounds=lambda: {"x": 1})
        s.sound_maker.join()
        s._sound_at = t[0] + 10.0
        for held in (set(), set(), set(), BOTH, BOTH):
            t[0] += 1 / 60
            s.step(held)
        t[0] += 10.0
        s.step(set())
        self.assertNotIn("start", sounds.played)


class Recorder:
    def __init__(self):
        self.played = []

    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        self.played += names

    def game_off(self):
        pass


class TwoColumns(unittest.TestCase):
    """The hidden menu: one column while the buttons stay a good size, two columns from seven entries."""

    def test_six_in_one_column_seven_in_two(self):
        six = Menu(["a", "b", "c", "d", "e", "f"]).buttons()
        self.assertEqual(len({x for _, x, _, _, _ in six[:-1]}), 1)
        seven = Menu(["a", "b", "c", "d", "e", "f", "g"]).buttons()
        self.assertEqual(len({x for _, x, _, _, _ in seven[:-1]}), 2)
        self.assertEqual([lab for lab, *_ in seven[:2]], ["a", "b"])           # left to right, then down
        self.assertGreaterEqual(min(h for *_, h in seven[:-1]), 100)
        self.assertEqual(seven[-1][0], BACK)

    def test_no_two_buttons_overlap_and_all_clear_the_bezel(self):
        for n in range(1, 11):
            buttons = Menu([str(i) for i in range(n)]).buttons()
            for i, (_, x, y, w, h) in enumerate(buttons):
                self.assertGreaterEqual(y, config.SHELL_TOP)
                self.assertLessEqual(x + w, config.SCREEN_W - config.SHELL_RIGHT)
                for _, x2, y2, w2, h2 in buttons[i + 1:]:
                    self.assertFalse(x < x2 + w2 and x2 < x + w and y < y2 + h2 and y2 < y + h, n)

    def test_a_touch_finds_the_right_one_in_two_columns(self):
        menu = Menu(["a", "b", "c", "d", "e", "f", "g"])
        for label, x, y, w, h in menu.buttons():
            self.assertEqual(menu.press(x + w // 2, y + h // 2), label)


@unittest.skipIf(pygame is None, "no pygame")
class Drawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from judicom.display import Display
        cls.display = Display(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.display.close()

    def test_the_stars_fall_in_four_colours(self):
        from judicom import lunica_view as lv
        view = lv.LunicaView()
        self.assertEqual({c for *_, c, _ in view.stars} - set(lv.STAR_COLOURS), set())
        self.assertEqual(len({c for *_, c, _ in view.stars}), 4)
        self.assertTrue(all(lv.STAR_SPEED[0] <= v <= lv.STAR_SPEED[1] for *_, v in view.stars))

    def test_every_state_draws(self):
        from judicom.lunica_view import LunicaView
        view = LunicaView()
        g = LunicaGame(seed=1)
        run(g, 300)
        for state in ("attract", "intro", "playing", "clear", "over"):
            g.state = state
            canvas = view.draw(g)
            self.assertEqual(canvas.get_size(), (config.SCREEN_W // 2, config.SCREEN_H // 2))
        g.state, g.tally = "summary", (30, 40, 2000, 0, 5000)
        view.draw(g)
        self.display.present_small(view.draw(g))

    def test_the_beam_the_captive_two_fighters_and_bursts_draw(self):
        from judicom.lunica_view import LunicaView
        g = game()
        c = next(o for o in g.enemies if o.kind == "commander")
        c.state, c.beam_t, c.captive = "beam", 1.0, True
        g.dual, g.rescued = True, [100.0, 500.0]
        g.bursts = [[200, 300, 0.1, k] for k in ("enemy", "boss", "ship")]
        g.rise = [c, 300.0, float(lu.PLAYER_Y), 0.5]
        LunicaView().draw(g)


class FakeSounds:
    def game_on(self, sounds=None):
        pass

    def game_play(self, names):
        pass

    def game_off(self):
        pass


if __name__ == "__main__":
    unittest.main()
