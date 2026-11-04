"""Tests for judicom/home.py: photos -> info screen -> photos, and the night clock.  No pygame needed (drawing is not tested
here; see test_info_view.py).   Run from the software folder:   python3 -m unittest -v"""
import datetime
import unittest

from judicom.home import INFO, NIGHT, PHOTOS, Home, in_night


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.wall = datetime.datetime(2026, 11, 3, 14, 0)

    def __call__(self):
        return self.t

    def now(self):
        return self.wall + datetime.timedelta(seconds=self.t - 1000.0)


class FakePhotos:
    """Behaves like PhotoView: a new picture every `seconds`."""

    def __init__(self, clock, seconds=15.0, have=True):
        self.clock, self.seconds, self.have = clock, seconds, have
        self.shown, self.current, self.since, self.starts = 0, None, 0.0, 0

    def _advance(self):
        if self.have:
            self.shown += 1
            self.current = "photo %d" % self.shown
        self.since = self.clock()

    def start(self):
        self.starts += 1
        self._advance()

    def next(self):
        self._advance()

    def tick(self):
        if self.clock() - self.since >= self.seconds:
            self._advance()

    def needs_redraw(self):
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.photos = FakePhotos(self.clock)
        self.home = Home(self.photos, now=self.clock.now, clock=self.clock, every=5, info_seconds=30)

    def run_for(self, seconds, step=0.5):
        modes = []
        for _ in range(int(seconds / step)):
            self.clock.t += step
            self.home.tick()
            if not modes or modes[-1] != self.home.mode:
                modes.append(self.home.mode)
        return modes


class Rotation(Base):
    def test_five_photos_then_the_info_screen_then_photos(self):
        self.home.start()
        self.assertEqual(self.home.mode, PHOTOS)
        self.run_for(74)                                   # photos 1..5 (15 s each): the fifth is still up at 74 s
        self.assertEqual((self.home.mode, self.photos.shown), (PHOTOS, 5))
        self.run_for(1.5)
        self.assertEqual(self.home.mode, INFO)
        self.assertEqual(self.photos.shown, 5)             # no sixth photo was shown first
        self.run_for(29)
        self.assertEqual(self.home.mode, INFO)
        self.run_for(1.5)
        self.assertEqual(self.home.mode, PHOTOS)
        self.assertEqual(self.photos.starts, 2)            # a fresh picture, not a fade from the old one
        self.run_for(73)                                   # (this run began at 105 s: its fifth photo ends at 180 s)
        self.assertEqual(self.home.mode, PHOTOS)
        self.run_for(2)
        self.assertEqual(self.home.mode, INFO)             # and again after five more

    def test_space_key(self):
        self.home.start()
        self.home.next()
        self.assertEqual(self.photos.shown, 2)
        self.home._go(INFO)
        self.home.next()                                   # from the info screen back to the photos
        self.assertEqual(self.home.mode, PHOTOS)

    def test_no_photos_the_info_screen_still_comes(self):
        self.photos.have = False
        self.home.start()
        self.run_for(76)
        self.assertEqual(self.home.mode, INFO)


class Night(Base):
    def test_in_night(self):
        for hm, night in [((20, 59), False), ((21, 0), True), ((23, 30), True), ((0, 0), True), ((5, 59), True), ((6, 0), False)]:
            with self.subTest(hm=hm):
                self.assertEqual(in_night(datetime.datetime(2026, 11, 3, *hm)), night)

    def test_starts_at_night_with_the_night_clock(self):
        self.clock.wall = datetime.datetime(2026, 11, 3, 23, 0)
        self.home.start()
        self.assertEqual(self.home.mode, NIGHT)
        self.assertEqual(self.photos.starts, 0)

    def test_into_the_night_and_out_again(self):
        self.clock.wall = datetime.datetime(2026, 11, 3, 20, 59, 0)
        self.home.start()
        self.assertEqual(self.run_for(61), [PHOTOS, NIGHT])
        self.clock.wall = datetime.datetime(2026, 11, 4, 5, 59, 30) - datetime.timedelta(seconds=self.clock.t - 1000.0)
        self.assertEqual(self.run_for(31), [NIGHT, PHOTOS])

    def test_the_info_screen_gives_way_to_the_night(self):
        self.clock.wall = datetime.datetime(2026, 11, 3, 20, 59, 50)
        self.home.start()
        self.home._go(INFO)
        self.run_for(11)
        self.assertEqual(self.home.mode, NIGHT)

    def test_after_a_call_at_night_the_night_clock_comes_back(self):
        self.clock.wall = datetime.datetime(2026, 11, 3, 23, 0)
        self.home.start()
        self.home.start()                                  # main.py calls start() when a call ends
        self.assertEqual(self.home.mode, NIGHT)


class Redraw(Base):
    def test_info_and_night_redraw_once_a_minute(self):
        self.clock.wall = datetime.datetime(2026, 11, 3, 23, 0, 0)
        self.home.start()
        self.assertTrue(self.home.needs_redraw())
        self.home._drawn = self.home._signature()          # as if drawn
        self.clock.t += 30
        self.assertFalse(self.home.needs_redraw())
        self.clock.t += 31
        self.assertTrue(self.home.needs_redraw())


if __name__ == "__main__":
    unittest.main()
