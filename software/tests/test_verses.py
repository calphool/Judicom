"""Tests for judicom/verses.py and verse_view.py (the verse screen), and the verse list in deploy/.
The drawing tests need pygame; without it they are skipped.   Run from the software folder:   python3 -m unittest -v"""
import os
import random
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

from judicom.verses import Verse, VerseDeck, parse

EXAMPLE = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "verses.example.txt"


class Parsing(unittest.TestCase):
    def test_lines(self):
        vs = parse("# comment\nIsaiah 46:4 | And even to your old age I am he\n\nPsalm 121:1-2 | I will lift up [2] My help\n")
        self.assertEqual([v.reference for v in vs], ["Isaiah 46:4", "Psalm 121:1-2"])
        self.assertEqual(vs[1].parts(), [("", "I will lift up"), ("2", "My help")])
        self.assertEqual((vs[1].book, vs[1].first_verse), ("Psalm", "1"))
        self.assertEqual(Verse("1 Peter 5:7", "x").book, "1 Peter")

    def test_bad_lines(self):
        logged = []
        self.assertEqual(parse("no bar here\n| no reference\nIsaiah 1:1 |\n", logged.append), [])
        self.assertEqual(len(logged), 3)

    def test_the_list_in_the_repository(self):
        logged = []
        vs = parse(EXAMPLE.read_text(), logged.append)
        self.assertEqual(logged, [])
        self.assertEqual(len(vs), 50)
        self.assertEqual(len({v.reference for v in vs}), 50)          # no verse twice
        for v in vs:
            self.assertNotIn("  ", v.text)
            self.assertNotRegex(v.text, r"\s[.,;:?!]")                 # the source's stray spaces before punctuation are gone
        texts = {v.reference: v.text for v in vs}
        self.assertTrue(texts["Isaiah 46:4"].startswith("And even to your old age I am he"))
        self.assertEqual(texts["Psalm 56:3"], "What time I am afraid, I will trust in thee.")


class Deck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "verses.txt"
        self.path.write_text("".join("Psalm %d:1 | words %d\n" % (i, i) for i in range(1, 11)))

    def test_every_verse_once_before_any_again(self):
        deck = VerseDeck(self.path, random.Random(1))
        for _ in range(3):
            self.assertEqual(len({deck.next().reference for _ in range(10)}), 10)

    def test_a_round_does_not_start_with_the_last_one(self):
        deck = VerseDeck(self.path, random.Random(2))
        for _ in range(30):
            last = [deck.next() for _ in range(10)][-1]
            self.assertNotEqual(deck.next(), last)
            for _ in range(9):
                deck.next()

    def test_a_changed_list_is_read_again(self):
        deck = VerseDeck(self.path, random.Random(3))
        deck.next()
        self.path.write_text("Isaiah 41:10 | Fear thou not\n")
        os.utime(self.path, ns=(0, 10 ** 18))
        self.assertTrue(deck.refresh())
        self.assertEqual(deck.next().reference, "Isaiah 41:10")

    def test_no_file(self):
        self.assertIsNone(VerseDeck(Path(self._tmp.name) / "missing.txt").next())


@unittest.skipUnless(pygame, "pygame is not installed")
class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((600, 1024))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw, verse_view
        verse_view.reset()
        draw.reset()
        pygame.quit()

    def test_every_verse_fits_on_the_page(self):
        from judicom import verse_view
        for v in parse(EXAMPLE.read_text()):
            with self.subTest(v=v.reference):
                size, line_h, cap, cap_size, cap_w, lines, _ = verse_view.fit(v)
                self.assertGreaterEqual(size, 36)                            # still large for Judi's eyes
                self.assertLessEqual(len(lines) * line_h, verse_view.TEXT_BOTTOM - verse_view.TEXT_TOP)
                for i, line in enumerate(lines):
                    width = sum(w for _, w in line) + verse_view.font(size).size(" ")[0] * max(0, len(line) - 1)
                    self.assertLessEqual(width, verse_view.TEXT_RIGHT - verse_view.TEXT_LEFT - (cap_w if i < 2 else 0) + 1)

    def test_draws_the_page(self):
        from judicom import verse_view
        surf = pygame.Surface((600, 1024))
        verse_view.draw_verse(surf, Verse("Psalm 23:1-3", "The LORD is my shepherd; I shall not want. [2] He maketh me"))
        self.assertEqual(tuple(surf.get_at((300, 600)))[:3], verse_view.PAGE)     # the page ...
        self.assertNotEqual(tuple(surf.get_at((5, 5)))[:3], verse_view.PAGE)      # ... on the leather

    def test_small_capitals_and_verse_numbers(self):
        from judicom import verse_view
        runs = verse_view.word_runs("LORD’s", 40)
        self.assertEqual([r.text for r in runs], ["L", "ORD", "’s"])
        self.assertLess(runs[1].size, runs[0].size)
        number = verse_view.word_runs("[16]", 40)[0]
        self.assertEqual((number.text, number.color), ("16", verse_view.RED))

    def test_the_font_is_the_bundled_one(self):
        from judicom import verse_view
        self.assertTrue((verse_view.FONT_DIR / "EBGaramond.ttf").is_file())
        self.assertTrue((verse_view.FONT_DIR / "OFL.txt").is_file())


if __name__ == "__main__":
    unittest.main()
