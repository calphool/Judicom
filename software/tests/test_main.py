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
        self.digits = ""

    def update(self, dial_tone, ringing, digits=""):
        self.state = (dial_tone, ringing)
        self.digits = digits


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

    def test_dialing_tones_then_the_call_goes_out(self):
        clark = Party("Clark", "husband", "clark", "5550100142")
        self.machine.buttons["left"] = clark
        self.phone.step(["l", "1"])
        self.assertEqual(self.machine.mode, Mode.DIALING)
        self.assertEqual(self.sounds.digits, "5550100142")
        self.assertEqual(self.sounds.state, (False, False))     # the dial tone stopped for the digits
        self.assertEqual(self.calls.done, [])                   # nothing goes to the phone software while the digits play
        self.clock.t += 3
        self.phone.step()
        self.assertEqual(self.calls.done, [("dial", clark)])
        self.assertEqual(self.sounds.digits, "")
        self.assertEqual(self.machine.mode, Mode.CALLING)

    def test_next_photo_only_on_the_photo_screen(self):
        self.phone.step(["next"])
        self.assertEqual(self.photos.nexts, 1)
        self.phone.step(["l", "next"])
        self.assertEqual(self.photos.nexts, 1)


class FakeContacts:
    def __init__(self):
        self.people = {"5155550187": AMY_FILE}
        self.left = CLARK_FILE
        self.changed = False
        self.refreshes = 0

    def buttons(self):
        return {"left": self.left, "right": AMY_FILE}

    def refresh(self):
        self.refreshes += 1
        changed, self.changed = self.changed, False
        return changed

    def lookup(self, number):
        from judicom.contacts import normalize, pretty
        return self.people.get(normalize(number)) or Party(dial=pretty(number))


CLARK_FILE = Party("Clark", "husband", "6415550142", "6415550142")
AMY_FILE = Party("Amy", "daughter", "5155550187", "5155550187")


class WithContacts(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.machine = Machine({}, clock=self.clock)
        self.calls, self.sounds, self.photos, self.contacts = Calls(), Sounds(), Photos(), FakeContacts()
        self.phone = Phone(self.machine, KeyControls(), self.calls, self.sounds, self.photos, self.contacts, clock=self.clock)

    def test_buttons_come_from_the_contacts(self):
        self.assertEqual(self.machine.buttons["left"], CLARK_FILE)

    def test_incoming_number_gets_its_name(self):
        self.phone.step()
        self.phone._handle(("incoming", "sip:+15155550187@pbx"))
        self.assertEqual(self.machine.party, AMY_FILE)

    def test_unknown_number_shows_the_number(self):
        self.phone.step(["u"])
        self.assertEqual(self.machine.mode, Mode.INCOMING)
        self.assertEqual(self.machine.party.label, "(515) 555-0199")

    def test_i_key_is_the_right_button_person_calling(self):
        self.phone.step(["i"])
        self.assertEqual(self.machine.party, AMY_FILE)

    def test_a_changed_file_reaches_the_buttons_and_the_screen(self):
        self.phone.step()
        self.assertFalse(self.phone.step())
        self.contacts.left = Party("Grandpa", "husband", "6415550142", "6415550142")
        self.contacts.changed = True
        self.clock.t += 2
        self.assertFalse(self.phone.step())                         # not looked at yet: every few seconds only
        self.clock.t += 4
        self.assertTrue(self.phone.step())                          # redraw: the names above the arrows may have changed
        self.assertEqual(self.machine.buttons["left"].name, "Grandpa")

    def test_without_contacts_a_number_is_still_shown(self):
        phone = Phone(Machine({}, clock=self.clock), KeyControls(), Calls(), Sounds(), Photos(), clock=self.clock)
        phone._handle(("incoming", "+15155550199"))
        self.assertEqual(phone.machine.party.label, "+15155550199")


if __name__ == "__main__":
    unittest.main()
