"""Tests for judicom/inputs.py (no GPIO needed).   Run from the software folder:   python3 -m unittest -v"""
import unittest

from judicom.inputs import Controls, KeyControls, Settled

NC1, NC2, NO, LEFT, RIGHT = 17, 27, 22, 23, 24


class FakePins:
    """Pins that are low or high as the test says.  Starts with the handset down and no button pressed."""

    def __init__(self):
        self.low = set()
        self.closed = False
        self.hang_up()

    def is_low(self, pin):
        return pin in self.low

    def set(self, pin, low):
        (self.low.add if low else self.low.discard)(pin)

    def hang_up(self):          # handset in the cradle presses the switch: NC contacts open (high), NO contact closed (low)
        self.set(NC1, False), self.set(NC2, False), self.set(NO, True)

    def lift(self):
        self.set(NC1, True), self.set(NC2, True), self.set(NO, False)

    def close(self):
        self.closed = True


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.pins, self.clock, self.logged = FakePins(), Clock(), []
        self.c = self.make()

    def make(self, **kw):
        args = dict(nc_pins=(NC1, NC2), no_pins=(NO,), button_pins={"left": LEFT, "right": RIGHT}, pressed_on_hook=True,
                    lift_settle=0.1, hang_up_settle=0.5, button_settle=0.05, clock=self.clock, log=self.logged.append)
        args.update(kw)
        return Controls(self.pins, **args)

    def run_for(self, seconds, step=0.01):
        """Poll every `step` seconds for `seconds`; all the events."""
        events = []
        end = self.clock.t + seconds
        while self.clock.t < end - 1e-9:
            self.clock.t += step
            events += self.c.poll()
        return events


class Hook(Base):
    def test_nothing_happens_at_rest(self):
        self.assertEqual(self.run_for(2), [])
        self.assertFalse(self.c.off_hook)

    def test_lift_and_hang_up(self):
        self.pins.lift()
        self.assertEqual(self.run_for(0.2), [("lifted",)])
        self.assertTrue(self.c.off_hook)
        self.pins.hang_up()
        self.assertEqual(self.run_for(0.4), [])                 # not yet: a hang-up must last HANG_UP_SETTLE
        self.assertEqual(self.run_for(0.2), [("hung_up",)])
        self.assertFalse(self.c.off_hook)

    def test_short_lift_is_ignored(self):
        self.pins.lift()
        self.assertEqual(self.run_for(0.05), [])
        self.pins.hang_up()
        self.assertEqual(self.run_for(1), [])

    def test_jostle_in_the_cradle_does_not_hang_up(self):
        self.pins.lift()
        self.run_for(0.2)
        for _ in range(5):                                      # down for 0.3 s, up for 0.1 s, five times
            self.pins.hang_up()
            self.assertEqual(self.run_for(0.3), [])
            self.pins.lift()
            self.assertEqual(self.run_for(0.1), [])
        self.assertTrue(self.c.off_hook)

    def test_bouncing_contacts_while_lifting(self):
        for i in range(8):                                      # contact bounce: up/down every 10 ms, then up for good
            (self.pins.lift if i % 2 == 0 else self.pins.hang_up)()
            self.assertEqual(self.run_for(0.01), [])
        self.pins.lift()
        self.assertEqual(self.run_for(0.2), [("lifted",)])

    def test_handset_up_at_start_is_reported(self):
        self.pins.lift()
        self.c = self.make()
        self.assertEqual(self.run_for(0.2), [("lifted",)])

    def test_one_bad_contact_is_outvoted(self):
        self.pins.set(NC1, True)                                # NC1 stuck closed: it says "up" with the handset down
        self.assertEqual(self.run_for(1), [])
        self.pins.lift()
        self.assertEqual(self.run_for(0.2), [("lifted",)])
        self.pins.hang_up()
        self.pins.set(NC1, True)
        self.assertEqual(self.run_for(1), [("hung_up",)])

    def test_disagreement_is_reported_once_and_cleared(self):
        self.pins.set(NO, False)                                # NO contact broken (never closes)
        self.run_for(1.5)
        self.assertEqual(self.logged, [])
        self.run_for(1)
        self.assertEqual(len(self.logged), 1)
        self.assertIn("disagree", self.logged[0])
        self.assertIn("GPIO 22 high", self.logged[0])
        self.run_for(5)
        self.assertEqual(len(self.logged), 1)
        self.pins.hang_up()
        self.run_for(0.1)
        self.assertIn("agree again", self.logged[-1])

    def test_switch_mounted_the_other_way(self):
        self.pins.lift()                                       # with pressed_on_hook=False this pin pattern means "handset down"
        self.c = self.make(pressed_on_hook=False)
        self.assertEqual(self.run_for(1), [])
        self.pins.hang_up()
        self.assertEqual(self.run_for(0.2), [("lifted",)])

    def test_tie_between_two_contacts_changes_nothing(self):
        self.c = self.make(nc_pins=(NC1,), no_pins=(NO,))
        self.pins.set(NC1, True)                                # NC1 says up, NO says down
        self.assertEqual(self.run_for(1), [])
        self.pins.set(NO, False)                                # both say up
        self.assertEqual(self.run_for(0.2), [("lifted",)])
        self.pins.set(NO, True)                                 # tie again: stays up
        self.assertEqual(self.run_for(1), [])
        self.assertTrue(self.c.off_hook)


class Buttons(Base):
    def test_press_counts_once(self):
        self.pins.set(LEFT, True)
        self.assertEqual(self.run_for(1), [("button", "left")])
        self.pins.set(LEFT, False)
        self.assertEqual(self.run_for(1), [])
        self.pins.set(RIGHT, True)
        self.assertEqual(self.run_for(0.1), [("button", "right")])

    def test_bounce_is_one_press(self):
        for i in range(6):                                      # bouncing every 10 ms never settles ...
            self.pins.set(LEFT, i % 2 == 0)
            self.assertEqual(self.run_for(0.01), [])
        self.pins.set(LEFT, True)
        self.assertEqual(self.run_for(0.2), [("button", "left")])   # ... so the press counts once it holds steady
        for i in range(6):                                      # bouncing on the way up is not another press
            self.pins.set(LEFT, i % 2 == 1)
            self.assertEqual(self.run_for(0.01), [])
        self.pins.set(LEFT, False)
        self.run_for(0.2)
        self.pins.set(LEFT, True)
        self.assertEqual(self.run_for(0.2), [("button", "left")])   # ... a new press is a new event

    def test_held_at_start_needs_a_new_press(self):
        self.pins.set(LEFT, True)
        self.c = self.make()
        self.assertEqual(self.run_for(1), [])
        self.pins.set(LEFT, False)
        self.assertEqual(self.run_for(0.2), [])
        self.pins.set(LEFT, True)
        self.assertEqual(self.run_for(0.2), [("button", "left")])

    def test_close(self):
        self.c.close()
        self.assertTrue(self.pins.closed)


class SettledValue(unittest.TestCase):
    def test_settle_time_depends_on_the_new_value(self):
        s = Settled(False, lambda v: 1.0 if v else 0.0)
        self.assertFalse(s.update(True, 0.0))
        self.assertTrue(s.update(True, 1.0))
        self.assertTrue(s.update(False, 1.0))                   # back to False at once


class Keys(unittest.TestCase):
    def test_keys_stand_in_for_the_switches(self):
        k = KeyControls()
        self.assertEqual(k.key("l"), [("lifted",)])
        self.assertTrue(k.off_hook)
        self.assertEqual(k.key("1"), [("button", "left")])
        self.assertEqual(k.key("2"), [("button", "right")])
        self.assertEqual(k.key("x"), [])
        self.assertEqual(k.key("l"), [("hung_up",)])
        self.assertEqual(k.poll(), [])


if __name__ == "__main__":
    unittest.main()
