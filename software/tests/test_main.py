"""Tests for the Phone in judicom/main.py: switches and keys -> machine -> phone software, sounds and photos (no pygame needed).
Run from the software folder:   python3 -m unittest -v"""
import unittest

from judicom.inputs import KeyControls
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone

CLARK = Party("Clark", "husband", "clark")
AMY = Party("Amy", "daughter", "amy")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Calls:
    def __init__(self):
        self.done = []

    def do(self, action):
        self.done.append(action)


class Sounds:
    def __init__(self):
        self.state = (False, False)

    def update(self, dial_tone, ringing):
        self.state = (dial_tone, ringing)


class Photos:
    def __init__(self):
        self.starts = self.ticks = self.nexts = 0

    def start(self):
        self.starts += 1

    def tick(self):
        self.ticks += 1

    def next(self):
        self.nexts += 1


class PhoneTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.machine = Machine({"left": CLARK, "right": AMY}, clock=self.clock)
        self.calls, self.sounds, self.photos = Calls(), Sounds(), Photos()
        self.phone = Phone(self.machine, KeyControls(), self.calls, self.sounds, self.photos)

    def test_first_step_starts_the_photos(self):
        self.assertTrue(self.phone.step())
        self.assertEqual(self.photos.starts, 1)
        self.assertFalse(self.phone.step())
        self.assertEqual(self.photos.ticks, 1)

    def test_a_whole_call(self):
        self.phone.step()
        self.assertTrue(self.phone.step(["l"]))
        self.assertEqual(self.machine.mode, Mode.LIFTED)
        self.assertEqual(self.sounds.state, (True, False))
        self.assertEqual(self.photos.ticks, 0)                   # the photos wait while they are not on the screen
        self.phone.step(["2"])
        self.assertEqual(self.calls.done, [("dial", AMY)])
        self.assertEqual(self.sounds.state, (False, False))
        self.phone.step(["y"])
        self.assertEqual(self.machine.mode, Mode.ONGOING)
        self.phone.step(["l"])
        self.assertEqual(self.calls.done[-1], ("hangup",))
        self.assertEqual(self.machine.mode, Mode.ENDED)
        self.clock.t += 11
        self.assertTrue(self.phone.step())
        self.assertEqual(self.machine.mode, Mode.IDLE)
        self.assertEqual(self.photos.starts, 2)                  # back to the photos with a fresh picture

    def test_timeout_actions_reach_the_phone_software(self):
        self.phone.step(["l", "1"])
        self.clock.t += 31
        self.phone.step()
        self.assertEqual(self.calls.done, [("dial", CLARK), ("hangup",)])
        self.assertEqual(self.machine.mode, Mode.NO_ANSWER)

    def test_incoming_rings(self):
        self.phone.step(["i"])
        self.assertEqual(self.machine.mode, Mode.INCOMING)
        self.assertEqual(self.sounds.state, (False, True))
        self.phone.step(["l"])
        self.assertEqual(self.calls.done, [("answer",)])
        self.assertEqual(self.sounds.state, (False, False))

    def test_next_photo_only_on_the_photo_screen(self):
        self.phone.step(["next"])
        self.assertEqual(self.photos.nexts, 1)
        self.phone.step(["l", "next"])
        self.assertEqual(self.photos.nexts, 1)


if __name__ == "__main__":
    unittest.main()
