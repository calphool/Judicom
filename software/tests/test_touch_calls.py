"""Calling by touch (features.py "touch_calls"): the touch buttons on the choose-who-to-call screen, their places
(call_grid.py), the machine's "call" event, the phone's taps, the caller list, and the drawing.
Run from the software folder:   python3 -m unittest -v"""
import tempfile
import unittest
from pathlib import Path

from judicom import call_grid, config, features
from judicom.contacts import Contacts
from judicom.inputs import KeyControls
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone
from tests.test_keypad import TL, TR, Calls, Clock, Photos, Sounds, Taps
from tests.test_keypad import OPEN

FRANK = Party("Frank", "husband", "2125550142", "2125550142")
ANN = Party("Ann", "daughter", "3125550187", "3125550187")
HANNAH = Party("Hannah", "granddaughter", "3125550123", "3125550123")

try:
    import pygame
except ImportError:
    pygame = None


def middle(rect):
    x, y, w, h = rect
    return (x + w // 2, y + h // 2)


class Grid(unittest.TestCase):
    def test_columns_by_how_many(self):
        for n, cols in ((1, 1), (6, 1), (7, 2), (12, 2), (13, 3), (21, 3)):
            rects = call_grid.tiles(n)
            self.assertEqual(len(rects), n)
            self.assertEqual(len({r[2] for r in rects}), 1)
            self.assertEqual(round((call_grid.RIGHT - call_grid.LEFT + call_grid.GAP) / (rects[0][2] + call_grid.GAP)), cols, n)
        self.assertEqual(len(call_grid.tiles(30)), call_grid.MOST)
        self.assertEqual(call_grid.tiles(0), [])

    def test_inside_the_room_apart_and_clear_of_the_knock_and_bezel(self):
        for n in range(1, call_grid.MOST + 1):
            rects = call_grid.tiles(n)
            for i, (x, y, w, h) in enumerate(rects):
                self.assertGreaterEqual(y, max(call_grid.TOP, config.CORNER_PX), n)
                self.assertLessEqual(y + h, call_grid.BOTTOM, n)
                self.assertGreaterEqual(x, 0)
                self.assertLessEqual(x + w, config.SCREEN_W - config.SHELL_RIGHT, n)
                self.assertGreaterEqual(h, 60, n)                              # still a size a finger can find
                for (x2, y2, w2, h2) in rects[i + 1:]:
                    self.assertFalse(x < x2 + w2 and x2 < x + w and y < y2 + h2 and y2 < y + h, n)

    def test_hit(self):
        rects = call_grid.tiles(6)
        for i, r in enumerate(rects):
            self.assertEqual(call_grid.hit(rects, *middle(r)), i)
        self.assertIsNone(call_grid.hit(rects, 5, 5))
        self.assertIsNone(call_grid.hit(rects, 300, config.SCREEN_H - 20))     # below them: nothing


class TheCall(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.machine = Machine({"left": FRANK, "right": ANN}, clock=self.clock, dialing_seconds=lambda tones: 0)

    def test_a_touch_calls_them_like_a_button(self):
        self.machine.handle("lifted")
        self.assertEqual(self.machine.handle("call", HANNAH), [("dial", HANNAH)])
        self.assertEqual((self.machine.mode, self.machine.party), (Mode.CALLING, HANNAH))

    def test_only_on_the_who_would_you_like_to_call_screen(self):
        self.assertEqual(self.machine.handle("call", HANNAH), [])                # handset down
        self.machine.handle("lifted")
        self.clock.t += config.LIFTED_SECONDS + 1
        self.machine.tick()
        self.assertEqual(self.machine.mode, Mode.PLEASE_HANG_UP)
        self.assertEqual(self.machine.handle("call", HANNAH), [])                # the yellow screen has no touch buttons
        self.assertEqual(self.machine.handle("button", "left"), [("dial", FRANK)])   # (the real buttons still work there)

    def test_the_phone_cannot_call_out(self):
        self.machine.phone_ok = lambda: False
        self.machine.handle("lifted")
        self.assertEqual(self.machine.handle("call", HANNAH), [])
        self.assertEqual(self.machine.mode, Mode.OUT_OF_ORDER)


class People:
    def __init__(self, people):
        self._people = people

    def people(self):
        return list(self._people)

    def buttons(self):
        return {"left": FRANK, "right": ANN}

    def refresh(self):
        return False

    def lookup(self, number):
        return Party(dial=number)


class Taps_(unittest.TestCase):
    def make(self, on, people=(FRANK, ANN, HANNAH)):
        self.clock = Clock()
        self.machine = Machine({}, clock=self.clock)
        self.calls, self.sounds, self.taps = Calls(), Sounds(), Taps()
        self.phone = Phone(self.machine, KeyControls(), self.calls, self.sounds, Photos(), People(people), clock=self.clock,
                           taps=self.taps, touch_calls=lambda: on)
        self.phone.step(["l"])
        self.rects = call_grid.tiles(len(people))

    def tap(self, spot):
        self.clock.t += 0.5
        self.taps.next = [spot]
        self.phone.step()

    def test_on_a_tap_calls_that_person(self):
        self.make(True)
        self.tap(middle(self.rects[2]))
        self.assertEqual(self.machine.party, HANNAH)
        self.assertEqual(self.machine.mode, Mode.DIALING)

    def test_off_a_tap_on_the_heading_does_nothing(self):
        self.make(False)
        self.tap((300, 300))
        self.assertEqual(self.machine.mode, Mode.LIFTED)

    def test_off_a_tap_on_a_picture_name_or_arrow_calls_that_button(self):
        for key, person, spots in (("left", FRANK, ((171, 600), (171, 740), (171, 950))),
                                   ("right", ANN, ((429, 600), (429, 740), (429, 950)))):
            for spot in spots:
                self.make(False)
                self.tap(spot)
                self.assertEqual((self.machine.mode, self.machine.party), (Mode.DIALING, person), (key, spot))

    def test_off_between_the_two_nothing(self):
        self.make(False)
        self.tap((300, 740))
        self.assertEqual(self.machine.mode, Mode.LIFTED)

    def test_off_only_on_the_who_would_you_like_to_call_screen(self):
        self.make(False)
        self.clock.t += config.LIFTED_SECONDS + 1
        self.phone.step()
        self.assertEqual(self.machine.mode, Mode.PLEASE_HANG_UP)
        self.tap((171, 740))
        self.assertEqual((self.machine.mode, self.calls.done), (Mode.PLEASE_HANG_UP, []))

    def test_between_the_buttons_nothing(self):
        self.make(True)
        self.tap((300, config.SCREEN_H - 60))
        self.assertEqual(self.machine.mode, Mode.LIFTED)

    def test_the_keypad_knock_still_works(self):
        self.make(True)
        for spot in (TL, TL, TR, TR):
            self.tap(spot)
        self.assertEqual(self.sounds.bongs[-1], OPEN)
        self.assertEqual(self.machine.mode, Mode.KEYPAD)

    def test_off_the_areas_are_over_the_buttons_below_the_heading_and_the_knock(self):
        areas = call_grid.button_areas({"left": FRANK, "right": ANN})
        for key, (x, y, w, h) in areas.items():
            self.assertTrue(x <= config.BUTTON_X[key] < x + w, key)
            self.assertGreater(y, config.CORNER_PX)
            self.assertEqual(y + h, config.SCREEN_H)
        self.assertLessEqual(areas["left"][0] + areas["left"][2], areas["right"][0] - call_grid.AREA_GAP)
        self.assertEqual(call_grid.button_areas({}), {})

    def test_on_the_real_buttons_call_nobody(self):
        self.make(True)
        self.phone.step(["1"])
        self.phone.step(["2"])
        self.assertEqual((self.machine.mode, self.machine.party, self.calls.done), (Mode.LIFTED, None, []))
        self.clock.t += config.LIFTED_SECONDS + 1
        self.phone.step()
        self.assertEqual(self.machine.mode, Mode.PLEASE_HANG_UP)
        self.phone.step(["1"])                                                   # not on the yellow screen either
        self.assertEqual(self.calls.done, [])

    def test_off_the_real_buttons_call_as_always(self):
        self.make(False)
        self.phone.step(["1"])
        self.assertEqual(self.machine.party, FRANK)


class CallerList(unittest.TestCase):
    def test_everyone_with_a_name_in_the_files_order(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "contacts.txt"
            path.write_text("312-555-0187 | Ann | daughter | right\n212-555-0142 | Frank | husband | left\n"
                            "312-555-0123 | Hannah\n312-555-0100 |\n")
            self.assertEqual([p.name for p in Contacts(path).people()], ["Ann", "Frank", "Hannah"])

    def test_no_file_the_demo_people(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(Contacts(Path(d) / "none.txt").people()), len(config.BUTTONS))


class Switch(unittest.TestCase):
    def test_off_unless_turned_on(self):
        self.assertFalse(features.is_on({}, "touch_calls"))
        self.assertTrue(features.is_on({}, "jokes"))
        self.assertIn("touch_calls = off", features.render({}))
        self.assertTrue(features.parse(features.render({"touch_calls": True}))["touch_calls"])
        self.assertEqual(features.turned_off({}), [])                         # (it is not "turned off": it was never on)
        self.assertEqual(features.turned_off({"jokes": False}), ["jokes"])

    def test_an_older_file_without_it_leaves_it_off(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "features.txt"
            path.write_text("info = on\njokes = on\n")
            self.assertFalse(features.Features(path).on("touch_calls"))


@unittest.skipIf(pygame is None, "no pygame")
class Drawing(unittest.TestCase):
    def draw(self, people, touch=True, faces=None):
        from judicom.call_view import CallView
        surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
        view = CallView({"left": FRANK, "right": ANN}, faces)
        view.touch, view.people = touch, people
        view.draw(surf, Mode.LIFTED, None, 0.2)
        return surf

    def test_each_person_gets_a_white_button_where_the_grid_says(self):
        for n in (1, 3, 6, 9, 14, 21):
            people = [Party("Person %d" % i, "friend") for i in range(n)]
            surf = self.draw(people)
            for x, y, w, h in call_grid.tiles(n):
                self.assertEqual(surf.get_at((x + w // 2, y + 3))[:3], (255, 255, 255), n)

    def test_the_heading_says_plainly_what_to_do_in_two_big_lines(self):
        from judicom import call_view, draw
        self.assertEqual(call_view.TOUCH_HEADING, "Touch the person you would like to call")
        width = call_grid.RIGHT - call_grid.LEFT
        size = 56
        while len(draw.wrap(call_view.TOUCH_HEADING, "bold", size, width)) > 2:
            size -= 2
        self.assertGreaterEqual(size, 40)
        self.draw([FRANK, ANN])

    def test_off_the_heading_says_press_or_touch_in_three_lines_at_most(self):
        from judicom import call_view, draw
        self.assertEqual(call_view.BUTTONS_HEADING, "Press or touch the person you would like to call")
        size = 72
        while len(draw.wrap(call_view.BUTTONS_HEADING, "bold", size, config.SCREEN_W - 40)) > 3:
            size -= 2
        self.assertGreaterEqual(size, 48)

    def test_off_or_nobody_the_screen_as_before(self):
        from judicom.config import BG
        surf = self.draw([FRANK, ANN], touch=False)
        x, y, w, h = call_grid.tiles(2)[0]
        self.assertEqual(surf.get_at((x + 3, y + h // 2))[:3], BG)              # (the left edge: clear of the words)
        self.draw([])

    def test_a_picture_round_or_the_initials(self):
        from judicom.faces import Faces
        with tempfile.TemporaryDirectory() as d:
            pic = pygame.Surface((200, 200))
            pic.fill((200, 0, 0))
            pygame.image.save(pic, str(Path(d) / "Ann.png"))
            faces = Faces(folder=d)
            round_ = faces.get("Ann", 100, radius=50)
            self.assertEqual(round_.get_at((50, 50))[:3], (200, 0, 0))
            self.assertEqual(round_.get_at((8, 20))[3], 0)                     # outside the circle: clear
            self.assertNotEqual(faces.get("Ann", 100).get_at((8, 20))[3], 0)   # (inside the rounded square one)
            surf = self.draw([ANN, HANNAH], faces=faces)
            x, y, w, h = call_grid.tiles(2)[0]
            r, g, b = surf.get_at((x + 10 + (h - 20) // 2, y + h // 2))[:3]
            self.assertTrue(r > 190 and g < 10 and b < 10)                     # Ann's picture (smoothed a little)


if __name__ == "__main__":
    unittest.main()
