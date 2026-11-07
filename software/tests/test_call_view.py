"""Tests for judicom/call_view.py.  They need pygame; without it they are skipped.   Run from the software folder:   python3 -m unittest -v"""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

from judicom.machine import Mode, Party

if pygame:
    from judicom.call_view import CallView
    from judicom.config import BG, BUTTON_X, LIFTED_FACE_PX, YELLOW
    from judicom.config import SCREEN_H as H
    from judicom.config import SCREEN_W as W

FRANK = Party("Frank", "husband", "frank")
ANN = Party("Ann", "daughter", "ann")


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


@unittest.skipUnless(pygame, "pygame is not installed")
class Screens(unittest.TestCase):
    def setUp(self):
        self.view = CallView({"left": FRANK, "right": ANN})
        self.surf = pygame.Surface((W, H))

    def drawn(self, mode, party=None, t=0.35):
        self.surf.fill((255, 0, 255))                           # magenta: anything left of it was not drawn
        self.view.draw(self.surf, mode, party, t)
        return self.surf

    def test_every_phone_mode_fills_the_screen(self):
        for mode in Mode:
            if mode == Mode.IDLE:
                continue
            with self.subTest(mode=mode):
                s = self.drawn(mode, FRANK)
                for x, y in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1), (W // 2, H // 2)):
                    self.assertNotEqual(tuple(s.get_at((x, y)))[:3], (255, 0, 255))

    def test_idle_is_not_drawn_here(self):
        with self.assertRaises(ValueError):
            self.view.draw(self.surf, Mode.IDLE, None, 0)

    def test_please_hang_up_is_yellow(self):
        s = self.drawn(Mode.PLEASE_HANG_UP)
        self.assertEqual(tuple(s.get_at((5, 5)))[:3], YELLOW)

    def test_call_screens_on_the_teal(self):
        for mode in (Mode.LIFTED, Mode.CALLING, Mode.ONGOING, Mode.INCOMING, Mode.NO_ANSWER, Mode.ENDED):
            with self.subTest(mode=mode):
                self.assertEqual(tuple(self.drawn(mode, FRANK).get_at((5, 5)))[:3], BG)

    def pictures(self, *names):
        class Faces:
            asked = []

            def get(self, name, size):
                Faces.asked.append((name, size))
                if name not in names:
                    return None
                face = pygame.Surface((size, size))
                face.fill((255, 0, 0))
                return face
        self.view.faces = Faces()
        return Faces

    def red_at(self, x, y):
        return tuple(self.surf.get_at((x, y)))[:3] == (255, 0, 0)

    def face_spot(self, side):
        return BUTTON_X[side], H - 40 - 150 - 16 - 62 - 44 - 14 - LIFTED_FACE_PX // 2     # the middle of the picture, arrows at rest

    def test_the_picture_of_whoever_is_on_each_button_is_over_the_arrow(self):
        asked = self.pictures("Frank", "Ann")
        self.drawn(Mode.LIFTED, t=0)
        self.assertEqual(asked.asked[:2], [("Frank", LIFTED_FACE_PX), ("Ann", LIFTED_FACE_PX)])
        self.assertTrue(self.red_at(*self.face_spot("left")))
        self.assertTrue(self.red_at(*self.face_spot("right")))

    def test_someone_without_a_picture_just_has_the_name(self):
        self.pictures("Ann")
        self.drawn(Mode.LIFTED, t=0)
        self.assertFalse(self.red_at(*self.face_spot("left")))
        self.assertTrue(self.red_at(*self.face_spot("right")))

    def test_the_question_makes_room_only_for_pictures(self):
        def top_of_the_question():
            return next(y for y in range(H) if tuple(self.surf.get_at((W // 2, y)))[:3] != BG or
                        any(tuple(self.surf.get_at((x, y)))[:3] != BG for x in range(0, W, 4)))
        self.drawn(Mode.LIFTED, t=0)
        without = top_of_the_question()
        self.pictures("Frank", "Ann")
        self.drawn(Mode.LIFTED, t=0)
        self.assertLess(top_of_the_question(), without)

    def test_the_pictures_clear_the_question_and_each_other(self):
        self.pictures("Frank", "Ann")
        self.drawn(Mode.LIFTED, t=0)
        top = self.face_spot("left")[1] - LIFTED_FACE_PX // 2
        self.assertTrue(all(tuple(self.surf.get_at((x, top - 8)))[:3] == BG for x in range(0, W, 2)))
        self.assertLess(BUTTON_X["left"] + LIFTED_FACE_PX // 2, BUTTON_X["right"] - LIFTED_FACE_PX // 2)

    def test_only_the_arrows_move(self):
        self.pictures("Frank", "Ann")
        low, high = self.drawn(Mode.LIFTED, t=0.227).copy(), self.drawn(Mode.LIFTED, t=0.682).copy()     # the two ends of the bob
        arrows_top = H - 40 - 150
        for y in range(0, arrows_top, 3):
            for x in range(0, W, 3):
                self.assertEqual(low.get_at((x, y)), high.get_at((x, y)), (x, y))
        self.assertTrue(any(low.get_at((x, y)) != high.get_at((x, y)) for x in range(0, W, 3) for y in range(arrows_top, H)))

    def test_preload_reads_the_button_pictures(self):
        asked = self.pictures()
        asked.asked = []
        self.view.preload()
        self.assertEqual(asked.asked, [("Frank", LIFTED_FACE_PX), ("Ann", LIFTED_FACE_PX)])

    def test_arrows_point_at_the_buttons(self):
        s = self.drawn(Mode.LIFTED)
        for cx in BUTTON_X.values():
            self.assertNotEqual(tuple(s.get_at((cx, H - 80)))[:3], BG)     # the arrow's stem
        self.assertEqual(tuple(s.get_at((W // 2, H - 80)))[:3], BG)        # nothing between the two arrows

    def test_a_button_with_nobody_set_up_has_no_arrow(self):
        self.view = CallView({"left": FRANK})
        s = self.drawn(Mode.LIFTED)
        self.assertEqual(tuple(s.get_at((BUTTON_X["right"], H - 80)))[:3], BG)

    def test_words_follow_the_party(self):
        a = self.view.words(Mode.CALLING, FRANK)
        self.assertIs(self.view.words(Mode.CALLING, FRANK), a)             # kept while nothing changes
        b = self.view.words(Mode.CALLING, ANN)
        self.assertIsNot(a, b)

    def test_long_names_stay_on_the_screen(self):
        long = Party("Bartholomew-Christopher Montgomery-Smythe", "great-grandson-in-law", "x")
        for mode in (Mode.CALLING, Mode.ONGOING, Mode.ENDED, Mode.NO_ANSWER, Mode.INCOMING):
            with self.subTest(mode=mode):
                words = self.view.words(mode, long)
                self.assertLessEqual(words.get_width(), W)
                self.assertLess(words.get_height(), 520)
                self.drawn(mode, long)

    def test_unknown_caller_shows_the_number(self):
        unknown = self.view.words(Mode.INCOMING, Party(dial="312-555-0199"))
        hidden = self.view.words(Mode.INCOMING, Party())
        self.assertGreater(unknown.get_height(), hidden.get_height())      # "unknown caller:" and the number, or just "unknown caller"
        self.assertLessEqual(unknown.get_width(), W)

    def test_animated_modes(self):
        self.assertTrue(CallView.animated(Mode.LIFTED))
        self.assertTrue(CallView.animated(Mode.INCOMING))
        self.assertFalse(CallView.animated(Mode.ENDED))
        self.assertFalse(CallView.animated(Mode.PLEASE_HANG_UP))

    def test_incoming_moves(self):
        a = pygame.image.tostring(self.drawn(Mode.INCOMING, FRANK, t=0.1), "RGB")
        b = pygame.image.tostring(self.drawn(Mode.INCOMING, FRANK, t=0.15), "RGB")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
