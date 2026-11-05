"""Tests for judicom/event_icons.py (the little pictures beside the events) and the info screen with them.  The drawing tests need
pygame (skipped without it).   Run from the software folder:   python3 -m unittest -v"""
import datetime
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

if pygame:
    from judicom import event_icons


@unittest.skipUnless(pygame, "pygame is not installed")
class Choosing(unittest.TestCase):
    def test_names(self):
        for title, kind in (("Amy's birthday", "cake"), ("JOE'S BIRTHDAY", "cake"), ("Christmas", "tree"), ("Christmas Eve", "tree"),
                            ("Easter", "egg"), ("Independence Day", "fireworks"), ("4th of July picnic", "fireworks"),
                            ("New Year's Day", "fireworks"), ("Flag Day", "flag"), ("Memorial Day", "flag"),
                            ("Veterans Day", "flag"), ("Presidents' Day", "flag"), ("Thanksgiving", "turkey"),
                            ("Halloween", "pumpkin"), ("Valentine’s Day", "heart"), ("Grandparents' Day", "heart"),
                            ("Clark and Judi's anniversary", "heart"), ("St. Patrick's Day", "shamrock"), ("Mother's Day", "flower"),
                            ("Father's Day", "tie"), ("Visit from Amy", "house"), ("Martin Luther King Jr. Day", "star"),
                            ("Juneteenth", "star"), ("Labor Day", "star"), ("Dentist", "calendar"), ("", "calendar")):
            with self.subTest(title=title):
                self.assertEqual(event_icons.icon_for(title), kind)

    def test_a_birthday_on_christmas_is_still_a_cake(self):
        self.assertEqual(event_icons.icon_for("Christmas birthday party"), "cake")


@unittest.skipUnless(pygame, "pygame is not installed")
class Drawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((10, 10))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw
        draw.reset()
        pygame.quit()

    def test_every_picture_draws_something_inside_its_square(self):
        for kind in event_icons.DRAW:
            with self.subTest(kind=kind):
                title = {"calendar": "Dentist"}.get(kind) or next(w[0] for w, k in event_icons.ICONS if k == kind)
                img = event_icons.event_icon(title, 84, 20)
                self.assertEqual(img.get_size(), (84, 84))
                opaque = sum(1 for x in range(0, 84, 3) for y in range(0, 84, 3) if img.get_at((x, y))[3] > 200)
                self.assertGreater(opaque, 60)                               # a real picture, not a speck
                self.assertEqual(img.get_at((0, 0))[3], 0)                   # on a clear background

    def test_made_once(self):
        self.assertIs(event_icons.event_icon("Easter", 84), event_icons.event_icon("Easter Sunday", 84))
        self.assertIsNot(event_icons.event_icon("Dentist", 84, 3), event_icons.event_icon("Dentist", 84, 4))   # the day shows

    def test_info_screen_with_icons(self):
        from judicom import events, info_view
        from judicom.config import CARD, SCREEN_H, SCREEN_W
        now = datetime.datetime(2026, 11, 5, 10, 15)
        evs = events.parse("12-24 | Christmas Eve\n4th Thursday of November | Thanksgiving\n2026-11-20 | Dentist appointment")
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        info_view.draw_info(surf, now, None, events.upcoming(evs, now, 3))
        strip = {tuple(surf.get_at((x, y)))[:3] for x in range(46, 130, 4) for y in range(300, SCREEN_H - 40, 4)}
        self.assertGreater(len(strip - {CARD}), 20)                          # pictures down the left of the events card


if __name__ == "__main__":
    unittest.main()
