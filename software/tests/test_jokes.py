"""Tests for the joke screen: judicom/jokes.py (the list and the deck), screens.JokeScreen (the punchline's timing), its place in the
rotation (home.py), the drawing (joke_view.py, needs pygame) and the list itself (deploy/nas/judicom/jokes.example.txt).
Run from the software folder:   python3 -m unittest -v"""
import os
import random
import re
import tempfile
import unittest
from pathlib import Path

from judicom import config
from judicom.jokes import Joke, JokeDeck, parse
from judicom.screens import JOKE, JokeScreen

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

EXAMPLE = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "jokes.example.txt"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class List(unittest.TestCase):
    def test_setup_and_punchline(self):
        self.assertEqual(parse("# a comment\n\nWhy?  |  Because!\n"), [Joke("Why?", "Because!")])

    def test_a_line_without_both_halves_is_reported(self):
        said = []
        self.assertEqual(parse("No bar here\nWhy? |\n| Because!\n", said.append), [])
        self.assertEqual(len(said), 3)

    def test_every_joke_once_before_any_comes_again(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "jokes.txt"
            path.write_text("".join("Q%d? | A%d!\n" % (i, i) for i in range(10)))
            deck = JokeDeck(path, rng=random.Random(1))
            first = [deck.next() for _ in range(10)]
            self.assertEqual(len(set(first)), 10)
            second = [deck.next() for _ in range(10)]
            self.assertEqual(set(second), set(first))
            self.assertNotEqual(first[-1], second[0])

    def test_no_file_no_jokes(self):
        self.assertIsNone(JokeDeck("/no/such/jokes.txt").next())


class Timing(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()

        class Deck:
            def refresh(self):
                pass

            def next(self):
                return Joke("Why?", "Because!")
        self.screen = JokeScreen(Deck(), clock=self.clock)

    def test_the_punchline_waits(self):
        self.assertTrue(self.screen.ready())
        self.assertFalse(self.screen.punchline())
        self.clock.t += config.PUNCHLINE_SECONDS - 0.1
        self.assertFalse(self.screen.punchline())
        self.clock.t += 0.1
        self.assertTrue(self.screen.punchline())

    def test_it_is_drawn_again_when_the_punchline_comes_and_only_then(self):
        self.screen.ready()
        before = self.screen.signature(None)
        self.clock.t += 3
        self.assertEqual(self.screen.signature(None), before)
        self.clock.t += config.PUNCHLINE_SECONDS
        self.assertNotEqual(self.screen.signature(None), before)

    def test_each_joke_starts_without_its_punchline(self):
        self.screen.ready()
        self.clock.t += 60
        self.screen.ready()
        self.assertFalse(self.screen.punchline())

    def test_the_whole_joke_has_time_to_be_read(self):
        self.assertGreaterEqual(config.JOKE_SECONDS - config.PUNCHLINE_SECONDS, 15)

    def test_no_list_no_joke_screen(self):
        self.assertFalse(JokeScreen(None).ready())


class Rotation(unittest.TestCase):
    def test_a_joke_comes_round_after_the_weather(self):
        from judicom.home import ROTATION
        self.assertEqual(ROTATION[-1], JOKE)
        self.assertEqual(ROTATION.index(JOKE), ROTATION.index("weather") + 1)

    def test_home_shows_it_and_reveals_the_punchline(self):
        from judicom import home as home_mod

        class Photos:
            shown, current, seconds, since = 0, None, 15.0, 0.0

            def start(self):
                pass

            def tick(self):
                pass

            def needs_redraw(self):
                return False

        class Deck:
            def refresh(self):
                pass

            def next(self):
                return Joke("Why?", "Because!")
        import datetime
        clock = Clock()
        home = home_mod.Home(Photos(), now=lambda: datetime.datetime(2026, 11, 7, 12, 0), clock=clock, jokes=Deck(), awake_file=None)
        home._turn = home_mod.ROTATION.index(JOKE)
        home.start()
        clock.t += home.every * Photos.seconds
        home.tick()
        self.assertEqual(home.mode, JOKE)
        home._drawn = home._signature()
        self.assertFalse(home.needs_redraw())
        clock.t += config.PUNCHLINE_SECONDS
        self.assertTrue(home.needs_redraw())
        clock.t += config.JOKE_SECONDS
        home.tick()
        self.assertEqual(home.mode, home_mod.PHOTOS)


class TheList(unittest.TestCase):
    """The jokes that go to Judi: about a hundred, none twice, short enough to read, and none on the subjects kept out."""

    def setUp(self):
        self.jokes = parse(EXAMPLE.read_text(encoding="utf-8"))

    def test_about_a_hundred_and_none_twice(self):
        self.assertTrue(95 <= len(self.jokes) <= 120, len(self.jokes))
        self.assertEqual(len({j.setup.lower() for j in self.jokes}), len(self.jokes))
        self.assertEqual(len({j.punchline.lower() for j in self.jokes}), len(self.jokes))

    def test_short_enough_to_read(self):
        for j in self.jokes:
            self.assertLessEqual(len(j.setup) + len(j.punchline), 120, j)

    def test_none_on_the_subjects_kept_out(self):
        kept_out = r"\b(forget\w*|forgot\w*|memory|remember\w*|old|age|aging|doctors?|nurses?|hospitals?|dies?|died|dead|death|grave\w*|" \
                   r"skeletons?|ghosts?|fat|diet\w*|weight|money|broke|cash|teeth|dentures?|wine|beer|drunk)\b"
        for j in self.jokes:
            self.assertIsNone(re.search(kept_out, (j.setup + " " + j.punchline).lower()), j)


@unittest.skipUnless(pygame, "pygame is not installed")
class Drawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw
        draw.reset()
        pygame.quit()

    def drawn(self, joke, punchline):
        from judicom.joke_view import draw_joke
        surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
        draw_joke(surf, joke, punchline)
        return surf

    def test_the_setup_stays_put_when_the_punchline_appears(self):
        from judicom.joke_view import TEXT_TOP, fit
        joke = Joke("What do you call a cow in an earthquake?", "A milkshake!")
        before, after = self.drawn(joke, False), self.drawn(joke, True)
        size, setup, _, _ = fit(joke)
        for y in range(0, TEXT_TOP + len(setup) * int(size * 1.18) + 40, 3):
            for x in range(0, config.SCREEN_W, 5):
                self.assertEqual(before.get_at((x, y)), after.get_at((x, y)), (x, y))
        self.assertNotEqual(pygame.image.tostring(before, "RGB"), pygame.image.tostring(after, "RGB"))

    def test_every_joke_on_the_list_fits_in_big_letters(self):
        from judicom.joke_view import TEXT_BOTTOM, TEXT_TOP, fit
        for joke in parse(EXAMPLE.read_text(encoding="utf-8")):
            size, setup, punch, gap = fit(joke)
            self.assertGreaterEqual(size, 48, joke)
            self.assertLessEqual((len(setup) + len(punch)) * int(size * 1.18) + gap, TEXT_BOTTOM - TEXT_TOP, joke)

    def test_the_jester_stands_in_the_middle(self):
        from judicom.joke_view import CX, _jester
        surf = pygame.Surface((config.SCREEN_W, 300), pygame.SRCALPHA)
        _jester(surf, CX - 120, 0, 240)
        xs = [x for x in range(config.SCREEN_W) for y in range(0, 300, 4) if surf.get_at((x, y))[3] > 0]
        self.assertLessEqual(abs((min(xs) + max(xs)) / 2 - CX), 6)

    def test_nothing_under_the_bezel(self):
        from judicom.joke_view import LEFT, RIGHT, TEXT_TOP
        self.assertLessEqual(RIGHT, config.SCREEN_W - config.SHELL_RIGHT)
        self.assertGreater(TEXT_TOP, config.SHELL_TOP)
        self.assertGreater(LEFT, 0)


if __name__ == "__main__":
    unittest.main()
