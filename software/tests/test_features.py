"""Turning parts of the Judicom on and off (judicom/features.py): the file, the screens that skip their turn, the night clock,
the hidden games, judicom.sync and tools/nas_request.py.  (The website's Features page: test_admin.py.)
Run from the software folder:   python3 -m unittest -v"""
import datetime
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from judicom import config, features, sync
from judicom.features import Features
from judicom.home import INFO, JOKE, NIGHT, PHOTOS, VERSE, Home
from judicom.maintenance import SHELL, Maintenance
from tests.test_home import Clock, FakePhotos
from tests.test_maintenance import BOTH, CLOCKWISE, FakeSounds


class Fixed:
    """Features as a test sets them: everything on except those named."""

    def __init__(self, *off, night=((21, 0), (6, 0))):
        self.off, self.hours = set(off), night

    def on(self, name):
        return name not in self.off

    def night(self):
        return self.hours


class File(unittest.TestCase):
    def test_parse_and_render(self):
        said = []
        states = features.parse("# a note\njokes = off\n Weather = ON  # yes\nnight=no\nverses = maybe\ndancing = off\n\n", said.append)
        self.assertEqual(states, {"jokes": False, "weather": True, "night": False})
        self.assertEqual(len(said), 2)                              # the two lines it cannot use
        text = features.render(states)
        self.assertEqual(features.parse(text), {**{n: features.is_on(states, n) for n in features.NAMES},
                                                "night_from": (21, 0), "night_to": (6, 0)})
        self.assertIn("jokes = off\n", text)

    def test_the_night_hours(self):
        self.assertEqual(features.night({}), ((21, 0), (6, 0)))                  # the usual ones
        states = features.parse("night_from = 22:30\nnight_to = 7:00\n")
        self.assertEqual(features.night(states), ((22, 30), (7, 0)))
        text = features.render(states)
        self.assertIn("night_from = 22:30\nnight_to = 07:00\n", text)
        self.assertEqual(features.parse(text)["night_to"], (7, 0))
        self.assertIn("night_from = 21:00", features.render({}))
        for bad in ("night_from = 25:00", "night_from = 9pm", "night_from = 9:5", "night_to = :30"):
            said = []
            self.assertNotIn("night_from", features.parse(bad, said.append))
            self.assertEqual(len(said), 1, bad)
        said = []
        self.assertEqual(features.night(features.parse("night_from = 06:00\n", said.append)), ((21, 0), (6, 0)))
        self.assertIn("same time", said[0])                                      # a night of no length: the usual hours
        self.assertEqual(features.time_words((0, 5)), "12:05 AM")
        self.assertEqual(features.time_words((12, 0)), "12:00 PM")
        self.assertEqual(features.time_words((21, 30)), "9:30 PM")

    def test_check_refuses_anything_not_right(self):
        self.assertEqual(features.check("jokes = off\n"), {"jokes": False})
        for bad in ("jokes = off\nrm -rf = on\n", "jokes off\n", "jokes = sometimes\n"):
            with self.assertRaises(ValueError):
                features.check(bad)

    def test_no_file_everything_on_and_a_change_is_seen(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            said = []
            f = Features(path, said.append)
            self.assertTrue(all(f.on(n) for n in features.NAMES if n not in features.OFF_UNLESS_SET))
            features.store({"weather": False}, path)
            self.assertFalse(f.on("weather"))
            self.assertTrue(f.on("jokes"))
            self.assertIn("features: off: weather; night 9:00 PM to 6:00 AM", said)
            self.assertEqual(features.summary({}), "as usual")
            self.assertEqual(features.summary({"jokes": False, "touch_calls": True}), "off: jokes; on: touch_calls")
            self.assertTrue(path.read_text().startswith("#"))
            time.sleep(0.01)
            features.store({}, path)
            os.utime(path, ns=(time.time_ns() + 10 ** 9,) * 2)
            self.assertTrue(f.on("weather"))

    def test_every_screen_has_its_switch(self):
        from judicom.home import FEATURE, ROTATION
        self.assertEqual(set(FEATURE), set(ROTATION))
        self.assertTrue(set(FEATURE.values()) <= set(features.NAMES))


class Screens(unittest.TestCase):
    class Deck:
        def __init__(self, item):
            self.item = item

        def refresh(self):
            pass

        def next(self):
            return self.item

    def make(self, *off, night=((21, 0), (6, 0))):
        self.clock = Clock()
        self.photos = FakePhotos(self.clock)
        self.home = Home(self.photos, now=self.clock.now, clock=self.clock, every=1, info_seconds=10, awake_file=None,
                         verses=self.Deck(SimpleNamespace(reference="Psalm 23:1")),
                         jokes=self.Deck(SimpleNamespace(setup="Why?", punchline="Because.")), verse_seconds=10,
                         joke_seconds=10, features=Fixed(*off, night=night))
        self.home.start()

    def turns(self, n):
        seen = []
        for _ in range(int(n / 0.5)):
            self.clock.t += 0.5
            self.home.tick()
            if self.home.mode != PHOTOS and (not seen or seen[-1] != self.home.mode):
                seen.append(self.home.mode)
            elif self.home.mode == PHOTOS and seen and seen[-1] != PHOTOS:
                seen.append(PHOTOS)
        return [m for m in seen if m != PHOTOS]

    def test_all_on_they_take_turns(self):
        self.make()
        self.assertEqual(self.turns(150)[:3], [INFO, VERSE, JOKE])         # (no weather report here: its turn is skipped)

    def test_a_screen_turned_off_gives_its_turn_away(self):
        self.make("jokes", "verses")
        self.assertEqual(set(self.turns(150)), {INFO})
        self.make("info")
        self.assertEqual(set(self.turns(150)), {VERSE, JOKE})

    def test_all_off_only_the_photos(self):
        self.make("info", "verses", "weather", "jokes")
        self.assertEqual(self.turns(200), [])
        self.assertGreater(self.photos.shown, 10)

    def test_an_old_events_line_is_passed_over_quietly(self):
        said = []
        self.assertEqual(features.parse("info = off\nevents = on\n", said.append), {"info": False})
        self.assertEqual(said, [])
        self.assertEqual(features.check("events = off\n"), {})                  # (the NAS's file from before, still taken)
        self.assertNotIn("events", features.render({}))

    def test_night_clock_off_the_photos_all_night(self):
        self.make("night")
        self.clock.wall = datetime.datetime(2026, 11, 3, 23, 0)
        self.home.start()
        self.assertEqual(self.home.mode, PHOTOS)
        self.make()
        self.clock.wall = datetime.datetime(2026, 11, 3, 23, 0)
        self.home.start()
        self.assertEqual(self.home.mode, NIGHT)


    def at(self, hour, minute=0):
        self.clock.wall = datetime.datetime(2026, 11, 3, hour, minute) - datetime.timedelta(seconds=self.clock.t - 1000.0)
        return self.clock.now()

    def test_night_hours_set_on_the_nas(self):
        self.make(night=((22, 30), (7, 15)))
        self.assertFalse(self.home.is_night(self.at(22, 29)))
        self.assertTrue(self.home.is_night(self.at(22, 30)))
        self.assertTrue(self.home.is_night(self.at(7, 14)))
        self.assertFalse(self.home.is_night(self.at(7, 15)))
        self.make(night=((13, 0), (15, 0)))                                     # (an afternoon nap works too)
        self.assertTrue(self.home.is_night(self.at(14)))
        self.assertFalse(self.home.is_night(self.at(23)))

    def test_messages_wait_for_the_morning_even_with_the_night_clock_off(self):
        self.make("night", night=((22, 0), (6, 0)))
        self.assertFalse(self.home.is_night(self.at(23)))                       # the photos go on ...
        self.assertTrue(self.home.is_night(self.at(23), quiet=True))            # ... but it is still too late for beeps
        self.assertFalse(self.home.is_night(self.at(21), quiet=True))


class Games(unittest.TestCase):
    def menu(self, on):
        clock = Clock()
        m = Maintenance(FakeSounds(), lambda: None, clock=clock, games={"Invaders": lambda: None}, games_on=lambda: on)
        m.step(True, True, set(), [])
        m.step(True, True, BOTH, [])
        clock.t += config.ARM_SECONDS
        m.step(True, True, BOTH, [])
        for c in CLOCKWISE:
            m.step(True, True, set(), [c])
        return [label for label, *_ in m.menu.buttons()][:-1]

    def test_games_off_only_the_shell(self):
        self.assertEqual(self.menu(True), [SHELL, "Invaders"])
        self.assertEqual(self.menu(False), [SHELL])


class Fetched(unittest.TestCase):
    def test_fetched_from_the_nas(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            said = []
            self.assertEqual(sync.sync_features(lambda: "jokes = off\n", path, said.append), 0)
            self.assertEqual(features.parse(path.read_text()), {**{n: features.is_on({}, n) for n in features.NAMES}, "jokes": False,
                                                                "night_from": (21, 0), "night_to": (6, 0)})
            self.assertIn("features updated: off: jokes", said)
            self.assertEqual(sync.sync_features(lambda: "jokes = off\n", path, said.append), 0)
            self.assertIn("features unchanged: off: jokes", said)

    def test_nothing_on_the_nas_everything_on(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            self.assertEqual(sync.sync_features(lambda: "", path, lambda m: None), 0)
            self.assertEqual(features.turned_off(features.parse(path.read_text())), [])

    def test_a_bad_answer_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            features.store({"weather": False}, path)
            before = path.read_text()
            said = []
            self.assertEqual(sync.sync_features(lambda: "<html>oops</html>\n", path, said.append), 1)
            self.assertEqual(path.read_text(), before)
            self.assertTrue(said[0].startswith("features not updated"))

    def test_the_nas_serves_it(self):
        script = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "serve_list.sh"
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "serve_list.sh"
            local.write_text(script.read_text().replace("/home/pi/judicom/", d + "/"))
            env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": "features"}
            r = subprocess.run(["sh", str(local)], capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, ""))                  # none yet: everything on
            (Path(d) / "features.txt").write_text("jokes = off\n")
            r = subprocess.run(["sh", str(local)], capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, "jokes = off\n"))


class Handed(unittest.TestCase):
    """tools/nas_request.py "features", as the NAS's website sends it."""

    def run_it(self, stdin, path):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND="features", JUDICOM_FEATURES=str(path))
        tool = Path(__file__).resolve().parents[1] / "tools" / "nas_request.py"
        return subprocess.run([sys.executable, str(tool)], input=stdin, env=env, capture_output=True, timeout=30)

    def test_taken(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            r = self.run_it(features.render({"games": False}).encode(), path)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, b"ok"))
            self.assertFalse(Features(path).on("games"))

    def test_refused_if_not_right(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            r = self.run_it(b"games = off\n$(reboot) = on\n", path)
            self.assertEqual(r.returncode, 1)
            self.assertIn(b"nas_request: ", r.stderr)
            self.assertFalse(path.exists())


try:
    import pygame
except ImportError:
    pygame = None


@unittest.skipIf(pygame is None, "no pygame")
class Previews(unittest.TestCase):
    """judicom/previews.py: a picture of every part, from the example lists (and from no lists at all)."""

    def test_every_part_is_drawn(self):
        from judicom import previews
        examples = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom"
        with tempfile.TemporaryDirectory() as d:
            lists, out = Path(d) / "lists", Path(d) / "out"
            lists.mkdir()
            for n in ("events", "verses", "jokes"):
                (lists / ("%s.txt" % n)).write_text((examples / ("%s.example.txt" % n)).read_text())
            previews.make_all(lists, out, datetime.datetime(2026, 12, 20, 10, 0))
            for n in features.NAMES:
                pic = pygame.image.load(str(out / ("%s.png" % n)))
                self.assertEqual(pic.get_size(), previews.SIZE, n)
            previews.make_all(Path(d) / "nothing", out)                       # no lists: examples instead
            self.assertTrue((out / "verses.png").exists())


if __name__ == "__main__":
    unittest.main()
