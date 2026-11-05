"""Tests for judicom/photo_view.py and keys.py.  They need pygame (and PIL for one test); without pygame they are skipped.
Run from the software folder:   python3 -m unittest -v"""
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")           # no screen needed
try:
    import pygame
except ImportError:
    pygame = None
try:
    import PIL.Image
except ImportError:
    PIL = None

from judicom.keys import parse_keys
from judicom.photos import Caption, PhotoDeck

if pygame:
    from judicom import draw, photo_view
    from judicom.config import BG
    from judicom.config import SCREEN_H as H
    from judicom.config import SCREEN_W as W


def setUpModule():
    if pygame:
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((W, H))


def tearDownModule():
    if pygame:
        from judicom import draw
        draw.reset()                                        # cached fonts must not outlive pygame (crash on the next init)
        pygame.quit()


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def solid(path, color, size=(400, 300)):
    s = pygame.Surface(size)
    s.fill(color)
    pygame.image.save(s, str(path))


@unittest.skipUnless(pygame, "pygame is not installed")
class Compose(unittest.TestCase):
    def test_picture_fitted_whole_on_a_darker_backdrop(self):
        for size in ((1600, 1200), (1200, 1600), (900, 900), (200, 100)):
            img = pygame.Surface(size)
            img.fill((200, 20, 20))
            out = photo_view.compose_picture(img)
            self.assertEqual(out.get_size(), (W, H))
            for got, want in zip(out.get_at((W // 2, H // 2))[:3], (200, 20, 20)):               # the middle is the picture itself
                self.assertAlmostEqual(got, want, delta=4, msg=size)                            # (smooth scaling is off by a count or two)
            corner = out.get_at((2, 2))
            self.assertLess(corner[0], 200)                                                     # the backdrop is darkened
            self.assertGreater(corner[0], 60)                                                   # ... but still the picture's colour

    def test_taken_says_how_long_ago(self):
        from judicom.photos import Caption
        import datetime
        year = datetime.date.today().year
        one = photo_view.compose_caption(Caption(taken="%d" % (year - 7)))[0]
        this = photo_view.compose_caption(Caption(taken="%d" % year))[0]
        self.assertEqual(one.get_height(), this.get_height())                                  # "Taken 2019 (7 years ago)": one line
        self.assertGreater(self.ink_width(one), self.ink_width(this) + 80)                     # ... with the years-ago words on it
        long = photo_view.compose_caption(Caption(taken="%d-06-14" % (year - 7)))[0]
        self.assertGreater(long.get_height(), one.get_height())                                # too long: "(7 years ago)" beneath

    @staticmethod
    def ink_width(band):
        xs = [x for x in range(W) if any(band.get_at((x, y))[0] > 120 for y in range(0, band.get_height(), 2))]
        return xs[-1] - xs[0] if xs else 0

    def test_photo_moves_up_out_of_the_captions_way(self):
        img = pygame.Surface((1600, 1200))
        img.fill((200, 20, 20))
        centred = photo_view.compose_picture(img)                                               # no caption: in the middle (y 287 - 737)
        raised = photo_view.compose_picture(img, band_y=758)                                    # with a caption below: higher (y 147 - 597)
        red = lambda surf, y: surf.get_at((W // 2, y))[0] > 150                                 # the picture, not the dark backdrop
        self.assertTrue(red(centred, 700) and not red(raised, 700))
        self.assertTrue(red(raised, 200) and not red(centred, 200))

    def test_loaded_photo_with_caption_leaves_the_words_clear_of_the_picture(self):
        solid(self.dir / "a.png", (200, 20, 20), (1600, 1200))
        (self.dir / "a.meta").write_text("people: Clark and Amy\nrelationship: Your husband and your daughter\ntaken: 2019-06-14\n")
        ph = photo_view.load_photo(self.dir / "a.png")
        surf = pygame.Surface((W, H))
        ph.draw(surf)
        for y in range(ph.band_y, H - 36, 10):                                                  # nothing of the red picture inside the band
            self.assertLess(surf.get_at((5, y))[0], 120, y)
        self.assertGreater(surf.get_at((W // 2, ph.band_y // 2))[0], 150)                       # the picture is above it, undisturbed

    def test_no_caption_no_band(self):
        self.assertIsNone(photo_view.compose_caption(Caption()))

    def test_caption_band_is_a_dark_strip_near_the_bottom(self):
        band, y = photo_view.compose_caption(Caption("Clark and Amy", "Your husband and your daughter", "2019-06-14"))
        self.assertEqual(band.get_width(), W)
        self.assertEqual(y + band.get_height(), H - 36)                                         # same place as in the approved mock-up
        self.assertEqual(band.get_at((3, 3)).a, 170)                                            # see-through dark strip

    def test_caption_darkens_the_bottom_of_a_drawn_photo(self):
        solid(self.dir / "a.png", (240, 240, 240), (1600, 1200))
        solid(self.dir / "b.png", (240, 240, 240), (1600, 1200))
        (self.dir / "b.meta").write_text("people: Clark and Amy\nrelationship: Your husband and your daughter\ntaken: 2019-06-14\n")
        plain, captioned = (photo_view.load_photo(self.dir / n) for n in ("a.png", "b.png"))
        a, b = pygame.Surface((W, H)), pygame.Surface((W, H))
        plain.draw(a)
        captioned.draw(b)
        row = H - 120                                                                           # inside the caption band
        self.assertGreater(a.get_at((10, row))[0], b.get_at((10, row))[0] + 50)
        self.assertEqual(a.get_at((10, 20)), b.get_at((10, 20)))                                # nothing else changed

    def test_long_names_wrap_and_fit_on_the_screen(self):
        caption = Caption("Ashlyn, Sydney, Andrew, Waylyn, Judi, Clark, Amy and Joe",
                          "Your granddaughters, your grandson, your husband, your daughter and your son-in-law", "Christmas 1998")
        band, y = photo_view.compose_caption(caption)
        self.assertGreater(y, H // 3)                                                           # never takes more than the lower two thirds
        lines = draw.wrap(caption.people, "bold", 54, W - 70)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(draw.get_font("bold", 54).size(line)[0] <= W - 70 for line in lines))

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    @unittest.skipUnless(PIL, "PIL is not installed")
    def test_phone_photo_turned_upright_by_exif(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "phone.jpg"
            im = PIL.Image.new("RGB", (800, 600), (10, 200, 10))          # stored sideways, as phones do
            exif = im.getexif()
            exif[0x0112] = 6                                              # "rotate 90 degrees clockwise to view"
            im.save(path, exif=exif)
            self.assertEqual(photo_view.load_image(path).get_size(), (600, 800))

    @unittest.skipUnless(PIL, "PIL is not installed")
    def test_big_picture_is_shrunk(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "big.jpg"
            PIL.Image.new("RGB", (4000, 3000), (1, 2, 3)).save(path)
            w, h = photo_view.load_image(path).get_size()
            self.assertLessEqual(max(w, h), 1400)
            self.assertAlmostEqual(w / float(h), 4 / 3.0, places=1)


@unittest.skipUnless(pygame, "pygame is not installed")
class View(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.clock = FakeClock()
        self.messages = []

    def view(self, **kw):
        kw.setdefault("clock", self.clock)
        kw.setdefault("log", self.messages.append)
        return photo_view.PhotoView(PhotoDeck(self.dir, random.Random(1)), **kw)

    def pictures(self, n=3):
        for i in range(n):
            solid(self.dir / ("p%d.png" % i), (40 + 60 * i, 90, 90))

    def test_start_shows_a_picture_without_fading(self):
        self.pictures()
        v = self.view()
        v.start()
        self.assertIsNotNone(v.current)
        self.assertIsNone(v.previous)
        self.assertFalse(v.animated())
        self.assertEqual(v.shown, 1)

    def test_changes_after_the_time_is_up_and_fades(self):
        self.pictures()
        v = self.view(seconds=15, fade=0.8)
        v.start()
        first, ver = v.current, v.version
        self.clock.advance(14.9)
        v.tick()
        self.assertIs(v.current, first)
        self.assertEqual(v.version, ver)
        self.clock.advance(0.2)
        v.tick()
        self.assertIsNot(v.current, first)
        self.assertIs(v.previous, first)
        self.assertTrue(v.animated())
        self.assertGreater(v.version, ver)
        self.clock.advance(0.9)
        v.tick()
        self.assertFalse(v.animated())
        self.assertIsNone(v.previous)                                 # the old picture's memory is released

    def test_the_fade_blends_the_two_pictures(self):
        solid(self.dir / "a.png", (255, 0, 0), (600, 1024))
        solid(self.dir / "b.png", (0, 0, 255), (600, 1024))
        v = self.view(seconds=15, fade=1.0)
        v.start()
        first = v.current
        v.next()
        surf = pygame.Surface((W, H))
        centre = (W // 2, H // 2)
        v.draw(surf)                                                  # the instant the new picture appears: still the old one
        self.assertEqual(surf.get_at(centre)[:3], first.surface.get_at(centre)[:3])
        self.clock.advance(0.5)
        v.draw(surf)
        r, g, b = surf.get_at(centre)[:3]
        self.assertTrue(40 < r < 215 and 40 < b < 215 and r + b > 200, (r, g, b))      # about half way
        self.clock.advance(0.6)
        v.draw(surf)
        self.assertEqual(surf.get_at(centre)[:3], v.current.surface.get_at(centre)[:3])
        self.assertEqual(v.current.surface.get_alpha(), 255)

    def test_old_caption_fades_out_then_new_one_fades_in(self):
        for name in ("a", "b"):
            solid(self.dir / (name + ".png"), (120, 120, 120), (600, 1024))
            (self.dir / (name + ".meta")).write_text("people: Person " + name + "\n")
        v = self.view(seconds=15, fade=1.0)
        v.start()
        old = v.current
        v.next()
        new = v.current
        calls = []
        real = photo_view.Photo.draw

        def spy(photo, surf, picture_alpha=255, caption_alpha=255):
            calls.append((photo, picture_alpha, caption_alpha))
            return real(photo, surf, picture_alpha, caption_alpha)
        surf = pygame.Surface((W, H))
        with mock.patch.object(photo_view.Photo, "draw", spy):
            for t, want_old, want_new in ((0.0, 255, 0), (0.25, 127, 0), (0.5, 0, 0), (0.75, 0, 127), (0.99, 0, 252)):
                self.clock.t = v.since + t
                calls.clear()
                v.draw(surf)
                got = {id(p): (pic, cap) for p, pic, cap in calls}
                self.assertAlmostEqual(got[id(old)][1], want_old, delta=3, msg=t)
                self.assertAlmostEqual(got[id(new)][1], want_new, delta=3, msg=t)
                self.assertAlmostEqual(got[id(new)][0], 255 * t, delta=3, msg=t)                 # the picture itself cross-fades throughout
        calls.clear()
        self.clock.t = v.since + 1.5                                                           # after the fade: only the new one, fully
        with mock.patch.object(photo_view.Photo, "draw", spy):
            v.draw(surf)
        self.assertEqual([(c[0] is new, c[1], c[2]) for c in calls], [(True, 255, 255)])

    # ---- the program's main loop, simulated: tick(), then draw() only when needs_redraw() says so
    def loop(self, view, seconds, frame, screen):
        end, draws = self.clock.t + seconds, 0
        while self.clock.t < end:
            view.tick()
            if view.needs_redraw():
                view.draw(screen)
                draws += 1
            self.clock.advance(frame)
        return draws

    @staticmethod
    def pixels(surface):
        return (getattr(pygame.image, "tobytes", None) or pygame.image.tostring)(surface, "RGB")

    def test_after_a_fade_nothing_of_the_old_picture_is_left(self):
        solid(self.dir / "a.png", (250, 20, 20), (600, 1024))                # red, then blue: any leftover shows
        solid(self.dir / "b.png", (20, 20, 250), (600, 1024))
        screen, ref = pygame.Surface((W, H)), pygame.Surface((W, H))
        for frame in (1 / 60.0, 1 / 30.0, 0.041, 0.05, 0.075, 0.1, 0.13, 0.2):      # a fast PC ... a slow Pi
            for offset in (0.0, 0.013, 0.027):                                      # the change can land anywhere between two frames
                v = self.view(seconds=15, fade=0.8)
                v.start()
                self.loop(v, 0.2, frame, screen)
                self.clock.advance(offset)
                v.next()
                self.loop(v, 3.0, frame, screen)
                v.current.draw(ref)
                self.assertEqual(self.pixels(screen), self.pixels(ref), "frame time %s, offset %s" % (frame, offset))

    def test_redraws_only_when_something_changes(self):
        self.pictures(2)
        screen = pygame.Surface((W, H))
        v = self.view(seconds=15, fade=0.8)
        v.start()
        draws = self.loop(v, 3.0, 1 / 30.0, screen)
        self.assertEqual(draws, 1)                                                  # one picture, no fade: drawn once, then left alone
        v.next()
        draws = self.loop(v, 0.8 + 0.2, 1 / 30.0, screen)
        self.assertTrue(24 <= draws <= 32, draws)                                   # about one per frame during the fade, plus the final one
        self.assertEqual(self.loop(v, 5.0, 1 / 30.0, screen), 0)                    # and nothing once it has settled

    def test_next_key_goes_on_straight_away(self):
        self.pictures()
        v = self.view()
        v.start()
        first = v.current
        v.next()
        self.assertIsNot(v.current, first)
        self.assertEqual(v.shown, 2)

    def test_goes_through_all_pictures_before_repeating(self):
        self.pictures(4)
        v = self.view(seconds=15)
        v.start()
        seen = [v.current.path.name]
        for _ in range(3):
            self.clock.advance(15)
            v.tick()
            seen.append(v.current.path.name)
        self.assertEqual(sorted(seen), ["p0.png", "p1.png", "p2.png", "p3.png"])

    def test_empty_folder_shows_a_message_and_recovers(self):
        v = self.view(retry_seconds=10)
        v.start()
        self.assertIsNone(v.current)
        surf = pygame.Surface((W, H))
        v.draw(surf)
        self.assertEqual(tuple(surf.get_at((3, 3)))[:3], BG)
        ver = v.version
        solid(self.dir / "new.png", (9, 9, 9))
        self.clock.advance(5)
        v.tick()
        self.assertIsNone(v.current)                                  # too early to look again
        self.clock.advance(6)
        v.tick()
        self.assertIsNotNone(v.current)                               # the sync brought a picture
        self.assertGreater(v.version, ver)

    def test_empty_folder_retries_do_not_cause_redraws(self):
        v = self.view(retry_seconds=10)
        v.start()
        ver = v.version
        for _ in range(5):
            self.clock.advance(11)
            v.tick()
        self.assertEqual(v.version, ver)

    def test_unreadable_picture_is_skipped_and_logged(self):
        self.pictures(2)
        (self.dir / "broken.jpg").write_text("this is not a picture")
        v = self.view(seconds=15)
        names = []
        v.start()
        names.append(v.current.path.name)
        for _ in range(5):
            self.clock.advance(15)
            v.tick()
            names.append(v.current.path.name)
        self.assertNotIn("broken.jpg", names)
        self.assertTrue(any("skipping broken.jpg" in m for m in self.messages))

    def test_only_a_broken_picture_does_not_loop_forever(self):
        (self.dir / "broken.jpg").write_text("nope")
        v = self.view()
        v.start()                                                     # must return
        self.assertIsNone(v.current)
        self.assertEqual(sum("skipping broken.jpg" in m for m in self.messages), 1)

    def test_picture_deleted_between_scan_and_load_is_skipped(self):
        self.pictures(3)
        v = self.view()
        v.start()
        self.dir.joinpath(v.deck._deck[-1].name).unlink()             # the sync removes the one that would come next
        v.next()
        self.assertIsNotNone(v.current)

    def test_log_line_carries_the_caption(self):
        solid(self.dir / "a.png", (1, 2, 3))
        (self.dir / "a.meta").write_text("people: Amy\nrelationship: Your daughter\ntaken: 2012-08\n")
        v = self.view()
        v.start()
        self.assertIn("a.png  [Amy | Your daughter | August 2012]", self.messages[-1])
        self.assertEqual(v.current.caption.people, "Amy")


@unittest.skipUnless(pygame, "pygame is not installed")
class Turn(unittest.TestCase):
    """The panel is 1024 x 600 but mounted sideways: the upright 600 x 1024 picture must be turned 90 degrees onto it."""

    def present(self, flip):
        from judicom.display import Display
        d = Display(headless=True, flip=flip)
        d.screen = pygame.Surface((1024, 600))                      # stands in for the panel
        d.rotate = True
        d.logical.fill((0, 0, 0))
        pygame.draw.rect(d.logical, (255, 0, 0), (0, 0, 40, 40))     # red marker: top-left of the upright picture
        pygame.draw.rect(d.logical, (0, 255, 0), (W - 40, 0, 40, 40))   # green marker: top-right of the upright picture
        d.present()
        return d.screen

    def test_upright_top_left_lands_at_the_panels_bottom_left(self):
        panel = self.present(flip=False)
        self.assertEqual(panel.get_at((5, 600 - 5))[:3], (255, 0, 0))       # top-left  -> bottom-left
        self.assertEqual(panel.get_at((5, 5))[:3], (0, 255, 0))             # top-right -> top-left
        self.assertEqual(panel.get_at((1000, 300))[:3], (0, 0, 0))

    def test_flip_turns_it_the_other_way(self):
        panel = self.present(flip=True)
        self.assertEqual(panel.get_at((1024 - 5, 5))[:3], (255, 0, 0))      # top-left  -> top-right
        self.assertEqual(panel.get_at((1024 - 5, 600 - 5))[:3], (0, 255, 0))


class Keys(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_keys(b" "), ["next"])
        self.assertEqual(parse_keys(b"\x1b[C"), ["next"])
        self.assertEqual(parse_keys(b"\x1b[A\x1b[B"), [])             # up / down arrows are ignored
        self.assertEqual(parse_keys(b"\x1b"), ["quit"])
        self.assertEqual(parse_keys(b"Q"), ["quit"])
        self.assertEqual(parse_keys(b"7a"), ["7", "a"])
        self.assertEqual(parse_keys(b"\x03\r"), [])                   # control characters are not keys


if __name__ == "__main__":
    unittest.main()
