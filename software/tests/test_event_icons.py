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
        for title, kind in (("Ann's birthday", "cake"), ("JOE'S BIRTHDAY", "cake"), ("Christmas", "tree"), ("Christmas Eve", "stocking"),
                            ("Easter", "egg"), ("Independence Day", "fireworks"), ("4th of July picnic", "fireworks"),
                            ("New Year's Day", "partyhat"), ("New Year’s Eve", "clock"), ("Flag Day", "flag"), ("Memorial Day", "poppy"),
                            ("Veterans Day", "medal"), ("Presidents' Day", "tophat"), ("Thanksgiving", "turkey"),
                            ("Halloween", "pumpkin"), ("Valentine’s Day", "heart"), ("Grandparents' Day", "rocker"),
                            ("Frank and Judi's anniversary", "rings"), ("St. Patrick's Day", "shamrock"), ("Mother's Day", "flower"),
                            ("Father's Day", "tie"), ("Visit from Ann", "house"), ("Martin Luther King Jr. Day", "dove"),
                            ("Juneteenth", "star"), ("Labor Day", "tools"), ("Columbus Day", "ship"), ("All Saints Day", "candle"),
                            ("Ugly Sweater Day", "sweater"), ("Ugly Christmas Sweater Day", "sweater"),
                            ("Dentist", "calendar"), ("", "calendar")):
            with self.subTest(title=title):
                self.assertEqual(event_icons.icon_for(title), kind)

    def test_every_holiday_on_the_list_has_its_own_picture(self):
        holidays = ("New Year's Day", "Martin Luther King Jr. Day", "Presidents' Day", "Memorial Day", "Juneteenth", "Independence Day",
                    "Labor Day", "Columbus Day", "Veterans Day", "Thanksgiving", "Christmas", "Valentine's Day", "St. Patrick's Day",
                    "Easter", "Mother's Day", "Flag Day", "Father's Day", "Grandparents' Day", "Halloween", "All Saints Day",
                    "Christmas Eve", "New Year's Eve")
        kinds = [event_icons.icon_for(h) for h in holidays]
        self.assertEqual(len(set(kinds)), len(holidays))
        self.assertNotIn("calendar", kinds)

    def test_the_familys_made_up_days_each_have_their_own_picture(self):
        days = ("Ugly Sweater Day", "Run It Up the Flagpole Day", "Teach Yourself Morse Code Day", "Absolutely Nothing Day",
                "Answer Your Cat's Questions Day", "Backwards Day", "Go To Work Naked Day", "Make A Grouch Happy Day",
                "Dog Biscuit Appreciation Day", "International Day Of Sleep", "The Ides of March", "International Goof Off Day",
                "Make Up Your Own Holiday Day", "April Fool's Day", "Okay To Tell A Lie Day", "Lawyer Appreciation Day",
                "Wear Pajamas Today Day", "Pretend You Are An Astronaut Day", "No Pants Day", "Lost Sock Remembrance Day",
                "Dance Like A Chicken Day", "Talk Like A Star War Character Day", "Put Something Funny Under Your Pillow Day",
                "Hug A Cat Day", "Eat All Your Veggies Day", "Don't Panic Day", "Pandemonium Day", "Insurance Agent Appreciation Day",
                "Musical Instrument Day", "Go For A Walk Day", "Lazy Day", "Dad Joke Day", "No Rhyme Or Reason Day",
                "Rock Collection Day", "Talk Like A Pirate Day", "Stupid Question Day", "Mad Hatter Day", "Unexplained Event Day",
                "Wear Something Crazy Day", "Howl At The Moon Night", "Deviled Eggs Day", "Chaos Never Ends Day",
                "Clean The Refrigerator Day", "National Absurdity Celebration Day", "Black Friday", "International Monkey Day")
        kinds = [event_icons.icon_for(d) for d in days]
        self.assertEqual(len(set(kinds)), len(days), kinds)
        self.assertNotIn("calendar", kinds)
        holidays = {event_icons.icon_for(h) for h in ("Flag Day", "Christmas Eve", "Juneteenth", "Memorial Day")}
        self.assertFalse(holidays & set(kinds))                                  # and none borrowed from a real holiday

    def test_the_church_year_and_the_last_few_days_each_have_their_own_picture(self):
        days = {"Epiphany": "crownstar", "Ash Wednesday": "ashes", "Palm Sunday": "palm", "Good Friday": "cross", "Pentecost": "flames", "Day of Pentecost": "flames", "Advent Begins": "adventwreath",
                "First Sunday of Advent": "adventwreath", "Sadie Hawkins Day": "lasso", "Pearl Harbor Day": "anchor", "Christmas Card Day": "xmascard", "Christmas Carol Day": "carolbook",
                "Pearl Harbor Remembrance Day": "anchor"}
        for title, kind in days.items():
            with self.subTest(title=title):
                self.assertEqual(event_icons.icon_for(title), kind)

    def test_christmas_itself_keeps_its_tree(self):
        self.assertEqual(event_icons.icon_for("Christmas"), "tree")
        self.assertEqual(event_icons.icon_for("Carol's birthday"), "cake")

    def test_an_adventure_is_not_advent(self):
        self.assertEqual(event_icons.icon_for("Adventure at the zoo"), "calendar")

    def test_black_friday_is_not_good_friday(self):
        self.assertEqual(event_icons.icon_for("Black Friday"), "bag")

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

    def test_a_long_name_is_shown_whole(self):
        from judicom import events, info_view
        now = datetime.datetime(2027, 5, 24, 10, 0)
        up = events.upcoming(events.parse("05-29 | Put Something Funny Under Your Pillow Day"), now, 1)[0]
        lines = [text for text, kind, size, color in info_view._event_lines(up, 600 - 48 - 16 - 72 - 12 - 18)]
        self.assertEqual(" ".join(lines[:3]), "Put Something Funny Under Your Pillow Day")      # three lines, no "..."

    def test_info_screen_with_icons(self):
        from judicom import events, info_view
        from judicom.config import CARD, SCREEN_H, SCREEN_W
        now = datetime.datetime(2026, 11, 5, 10, 15)
        evs = events.parse("12-24 | Christmas Eve\n4th Thursday of November | Thanksgiving\n2026-11-20 | Dentist appointment")
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        info_view.draw_info(surf, now, events.upcoming(evs, now, 3))
        strip = {tuple(surf.get_at((x, y)))[:3] for x in range(46, 130, 4) for y in range(300, SCREEN_H - 40, 4)}
        self.assertGreater(len(strip - {CARD}), 20)                          # pictures down the left of the events card


    def test_the_info_screen_has_room_for_five_events(self):
        from judicom import events, info_view
        from judicom.config import CARD, SCREEN_H, SCREEN_W
        now = datetime.datetime(2026, 11, 5, 10, 15)
        evs = events.parse("11-11 | Veterans Day\n11-20 | Pie Day\n4th Thursday of November | Thanksgiving\n"
                           "12-18 | Ugly Sweater Day\n12-25 | Christmas\n12-31 | New Year's Eve")
        surf = pygame.Surface((SCREEN_W, SCREEN_H))
        info_view.draw_info(surf, now, events.upcoming(evs, now, 5))
        rows = [y for y in range(200, SCREEN_H - 30) if any(tuple(surf.get_at((x, y)))[:3] != CARD for x in range(48, 120, 6))]
        icons = sum(1 for a, b in zip(rows, rows[1:]) if b - a > 8) + 1          # separate pictures down the left
        self.assertEqual(icons, 5)


@unittest.skipUnless(pygame, "pygame is not installed")
class WeatherScreen(unittest.TestCase):
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

    def report(self, days=5):
        from judicom.weather import Day, Report
        t = datetime.date(2026, 11, 5)
        icons = ("partly", "sun", "rain", "storm", "snow")
        return Report(31, 38, 22, "snow", "Light snow", 0.0, 70,
                      tuple(Day(t + datetime.timedelta(days=i + 1), 40 + i, 20 + i, icons[i], "words", 10 * i) for i in range(days)))

    def test_words(self):
        from judicom import weather_view
        self.assertEqual(weather_view.rain_words(70, "snow"), "70% chance of snow")
        self.assertEqual(weather_view.rain_words(40, "rain"), "40% chance of rain")
        self.assertEqual(weather_view.rain_words(10, "rain"), "")
        self.assertEqual(weather_view.rain_words(None, "rain"), "")
        today = datetime.date(2026, 11, 5)
        self.assertEqual(weather_view.day_name(datetime.date(2026, 11, 6), today), "Tomorrow")
        self.assertEqual(weather_view.day_name(datetime.date(2026, 11, 7), today), "Saturday")

    def test_today_and_five_days(self):
        from judicom import weather_view
        from judicom.config import BG, SCREEN_H, SCREEN_W
        for n in (5, 0):
            with self.subTest(days=n):
                surf = pygame.Surface((SCREEN_W, SCREEN_H))
                weather_view.draw_weather(surf, datetime.datetime(2026, 11, 5, 10, 15), self.report(n))
                lower = {tuple(surf.get_at((x, y)))[:3] for x in range(40, SCREEN_W - 40, 8) for y in range(560, SCREEN_H - 40, 8)}
                if n:
                    self.assertGreater(len(lower - {BG}), 10)            # the forecast card, with words and pictures
                else:
                    self.assertEqual(lower, {BG})                       # no forecast came: only today's card


if __name__ == "__main__":
    unittest.main()
