"""Tests for judicom/machine.py.   Run from the software folder:   python3 -m unittest -v"""
import unittest

from judicom.machine import Machine, Mode, Party

CLARK = Party("Clark", "husband", "clark")
AMY = Party("Amy", "daughter", "amy")
SYDNEY = Party("Sydney", "granddaughter", "+15550102345")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.m = Machine(buttons={"left": CLARK, "right": AMY}, lifted_seconds=60, ring_out_seconds=30, no_answer_seconds=10,
                         call_ended_seconds=10, clock=self.clock)

    def wait(self, seconds):
        """Let time pass, ticking every 0.1 s; all the actions."""
        actions = []
        for _ in range(int(round(seconds * 10))):
            self.clock.t += 0.1
            actions += self.m.tick()
        return actions

    def go(self, *events):
        """Several events; the actions of the last one."""
        actions = []
        for e in events:
            actions = self.m.handle(*e) if isinstance(e, tuple) else self.m.handle(e)
        return actions

    def assertMode(self, mode):
        self.assertEqual(self.m.mode, mode)


class Outgoing(Base):
    def test_starts_idle(self):
        self.assertMode(Mode.IDLE)
        self.assertFalse(self.m.dial_tone)
        self.assertFalse(self.m.ringing)

    def test_lift_gives_dial_tone(self):
        self.assertEqual(self.go("lifted"), [])
        self.assertMode(Mode.LIFTED)
        self.assertTrue(self.m.dial_tone)

    def test_lift_and_hang_up(self):
        self.go("lifted", "hung_up")
        self.assertMode(Mode.IDLE)

    def test_button_dials(self):
        self.go("lifted")
        self.assertEqual(self.go(("button", "right")), [("dial", AMY)])
        self.assertMode(Mode.CALLING)
        self.assertEqual(self.m.party, AMY)
        self.assertFalse(self.m.dial_tone)

    def test_buttons_do_nothing_with_the_handset_down(self):
        self.assertEqual(self.go(("button", "left")), [])
        self.assertMode(Mode.IDLE)

    def test_unknown_button(self):
        self.go("lifted")
        self.assertEqual(self.go(("button", "middle")), [])
        self.assertMode(Mode.LIFTED)

    def test_answered_then_hang_up(self):
        self.go("lifted", ("button", "left"))
        self.go("answered")
        self.assertMode(Mode.ONGOING)
        self.assertEqual(self.go("hung_up"), [("hangup",)])
        self.assertMode(Mode.ENDED)
        self.assertEqual(self.m.party, CLARK)
        self.wait(9.9)
        self.assertMode(Mode.ENDED)
        self.wait(0.2)
        self.assertMode(Mode.IDLE)
        self.assertIsNone(self.m.party)

    def test_they_hang_up_while_handset_still_up(self):
        self.go("lifted", ("button", "left"), "answered")
        self.assertEqual(self.go("remote_ended"), [])
        self.assertMode(Mode.ENDED)
        self.wait(10.1)
        self.assertMode(Mode.PLEASE_HANG_UP)
        self.go("hung_up")
        self.assertMode(Mode.IDLE)

    def test_no_answer_in_time(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.wait(29.9), [])
        self.assertEqual(self.wait(0.2), [("hangup",)])
        self.assertMode(Mode.NO_ANSWER)
        self.assertEqual(self.m.party, CLARK)
        self.wait(10.1)
        self.assertMode(Mode.LIFTED)                           # handset still up: the arrows again
        self.assertTrue(self.m.dial_tone)

    def test_no_answer_after_hanging_up_goes_idle(self):
        self.go("lifted", ("button", "left"), "call_failed")
        self.assertMode(Mode.NO_ANSWER)
        self.go("hung_up")
        self.assertMode(Mode.NO_ANSWER)                        # the screen stays for its time
        self.wait(10.1)
        self.assertMode(Mode.IDLE)

    def test_declined_is_no_answer(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.go("remote_ended"), [])
        self.assertMode(Mode.NO_ANSWER)

    def test_lift_again_during_no_answer(self):
        self.go("lifted", ("button", "left"), "call_failed", "hung_up", "lifted")
        self.assertMode(Mode.NO_ANSWER)
        self.wait(10.1)
        self.assertMode(Mode.LIFTED)

    def test_hang_up_while_calling(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.go("hung_up"), [("hangup",)])
        self.assertMode(Mode.IDLE)
        self.assertEqual(self.wait(40), [])                    # the ring-out timer is gone

    def test_lifted_too_long(self):
        self.go("lifted")
        self.wait(59.9)
        self.assertMode(Mode.LIFTED)
        self.wait(0.2)
        self.assertMode(Mode.PLEASE_HANG_UP)
        self.assertFalse(self.m.dial_tone)
        self.assertEqual(self.go(("button", "right")), [("dial", AMY)])     # the buttons still work
        self.assertMode(Mode.CALLING)

    def test_lift_soon_after_a_call(self):
        self.go("lifted", ("button", "left"), "answered", "hung_up", "lifted")
        self.assertMode(Mode.LIFTED)

    def test_stray_call_events_are_ignored(self):
        for event in ("answered", "call_failed", "remote_ended"):
            self.assertEqual(self.go(event), [])
            self.assertMode(Mode.IDLE)

    def test_unknown_event(self):
        with self.assertRaises(ValueError):
            self.m.handle("explode")


class Incoming(Base):
    def test_ring_and_answer(self):
        self.assertEqual(self.go(("incoming", SYDNEY)), [])
        self.assertMode(Mode.INCOMING)
        self.assertTrue(self.m.ringing)
        self.assertEqual(self.m.party, SYDNEY)
        self.assertEqual(self.go("lifted"), [("answer",)])
        self.assertMode(Mode.ONGOING)
        self.assertFalse(self.m.ringing)
        self.assertEqual(self.go("hung_up"), [("hangup",)])
        self.assertMode(Mode.ENDED)
        self.assertEqual(self.m.party, SYDNEY)

    def test_caller_gives_up(self):
        self.go(("incoming", SYDNEY), "remote_ended")
        self.assertMode(Mode.IDLE)
        self.assertFalse(self.m.ringing)

    def test_ringing_does_not_time_out_by_itself(self):
        self.go(("incoming", SYDNEY))
        self.wait(120)
        self.assertMode(Mode.INCOMING)

    def test_busy_when_handset_up(self):
        self.go("lifted")
        self.assertEqual(self.go(("incoming", SYDNEY)), [("reject",)])
        self.assertMode(Mode.LIFTED)

    def test_busy_during_a_call(self):
        self.go("lifted", ("button", "left"), "answered")
        self.assertEqual(self.go(("incoming", SYDNEY)), [("reject",)])
        self.assertMode(Mode.ONGOING)
        self.assertEqual(self.m.party, CLARK)

    def test_second_incoming_while_ringing_is_busy(self):
        self.go(("incoming", SYDNEY))
        self.assertEqual(self.go(("incoming", AMY)), [("reject",)])
        self.assertEqual(self.m.party, SYDNEY)

    def test_call_back_during_ended_screen(self):
        self.go("lifted", ("button", "left"), "answered", "hung_up")
        self.assertEqual(self.go(("incoming", CLARK)), [])
        self.assertMode(Mode.INCOMING)

    def test_unknown_caller_label(self):
        self.go(("incoming", Party(dial="+15550000000")))
        self.assertEqual(self.m.party.label, "+15550000000")


class Labels(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(AMY.label, "Amy (daughter)")
        self.assertEqual(Party("Amy").label, "Amy")
        self.assertEqual(Party().label, "someone")


class Version(Base):
    def test_version_changes_with_the_mode(self):
        v = self.m.version
        self.go("lifted")
        self.assertGreater(self.m.version, v)
        v = self.m.version
        self.go(("button", "middle"))
        self.assertEqual(self.m.version, v)


if __name__ == "__main__":
    unittest.main()
