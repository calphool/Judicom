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


class Dialing(Base):
    TONES = Party("Clark", "husband", "clark", "5550100142")

    def setUp(self):
        super().setUp()
        self.m = Machine(buttons={"left": self.TONES, "right": AMY}, ring_out_seconds=30,
                         dialing_seconds=lambda tones: 2.0 if tones else 0.0, clock=self.clock)

    def test_digits_first_then_the_call(self):
        self.go("lifted")
        self.assertEqual(self.go(("button", "left")), [])         # nothing to the phone software yet
        self.assertMode(Mode.DIALING)
        self.assertEqual(self.m.dialing_tones, "5550100142")
        self.assertFalse(self.m.dial_tone)
        self.assertEqual(self.m.party, self.TONES)
        self.assertEqual(self.wait(1.9), [])
        self.assertEqual(self.wait(0.2), [("dial", self.TONES)])
        self.assertMode(Mode.CALLING)
        self.assertEqual(self.m.dialing_tones, "")

    def test_ring_out_counts_from_when_the_call_goes_out(self):
        self.go("lifted", ("button", "left"))
        self.wait(2.1)
        self.assertEqual(self.wait(29.8), [])
        self.assertEqual(self.wait(0.2), [("hangup",)])
        self.assertMode(Mode.NO_ANSWER)

    def test_hang_up_while_dialing_sends_nothing(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.go("hung_up"), [])
        self.assertMode(Mode.IDLE)
        self.assertEqual(self.wait(5), [])                        # and the call never goes out
        self.assertEqual(self.m.dialing_tones, "")

    def test_no_tones_goes_straight_to_calling(self):
        self.go("lifted")
        self.assertEqual(self.go(("button", "right")), [("dial", AMY)])
        self.assertMode(Mode.CALLING)

    def test_other_button_while_dialing_is_ignored(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.go(("button", "right")), [])
        self.assertEqual(self.m.party, self.TONES)
        self.assertEqual(self.wait(2.1), [("dial", self.TONES)])

    def test_incoming_while_dialing_is_busy(self):
        self.go("lifted", ("button", "left"))
        self.assertEqual(self.go(("incoming", SYDNEY)), [("reject",)])
        self.assertMode(Mode.DIALING)

    def test_real_dialing_time_is_used_by_default(self):
        from judicom.sound import dialing_seconds
        m = Machine(buttons={"left": self.TONES}, clock=self.clock)
        m.handle("lifted")
        m.handle("button", "left")
        self.clock.t += dialing_seconds("5550100142") - 0.05
        self.assertEqual(m.tick(), [])
        self.clock.t += 0.1
        self.assertEqual(m.tick(), [("dial", self.TONES)])


class ButtonsFromConfig(unittest.TestCase):
    def test_tones(self):
        from judicom.machine import buttons_from_config
        b = buttons_from_config({"a": {"name": "A", "dial": "+1 (555) 010-0142"},              # the number's own digits
                                 "b": {"name": "B", "dial": "amy"},                            # a name: no digits, no sound
                                 "c": {"name": "C", "dial": "100", "tones": "555-0100-187"},   # chosen tones, cleaned
                                 "d": {"name": "D", "dial": "5550100142", "tones": ""}})       # sound turned off
        self.assertEqual({k: p.tones for k, p in b.items()}, {"a": "15550100142", "b": "", "c": "5550100187", "d": ""})

    def test_the_real_config(self):
        from judicom.machine import buttons_from_config
        for party in buttons_from_config().values():
            self.assertTrue(party.name and party.dial)


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


class OutOfOrder(Base):
    def setUp(self):
        super().setUp()
        self.ok = True
        self.m = Machine(buttons={"left": CLARK, "right": Party("Amy", "daughter", "amy", "5")}, lifted_seconds=60,
                         ring_out_seconds=30, no_answer_seconds=10, call_ended_seconds=10, out_of_order_seconds=15,
                         clock=self.clock, phone_ok=lambda: self.ok)

    def test_a_button_while_offline_says_so_and_dials_nothing(self):
        self.ok = False
        self.assertEqual(self.go("lifted", ("button", "right")), [])
        self.assertMode(Mode.OUT_OF_ORDER)
        self.assertEqual(self.m.dialing_tones, "")                    # no touch-tones either
        self.assertFalse(self.m.dial_tone)
        self.assertEqual(self.m.party.name, "Amy")
        self.assertEqual(self.wait(14.9), [])
        self.assertMode(Mode.OUT_OF_ORDER)
        self.wait(0.2)
        self.assertMode(Mode.LIFTED)                                  # handset still up: she may try again

    def test_hung_up_during_it_goes_back_to_the_photos(self):
        self.ok = False
        self.go("lifted", ("button", "left"), "hung_up")
        self.assertMode(Mode.OUT_OF_ORDER)
        self.wait(15.1)
        self.assertMode(Mode.IDLE)

    def test_a_call_that_fails_after_the_connection_went(self):
        self.go("lifted", ("button", "left"))
        self.assertMode(Mode.CALLING)
        self.ok = False
        self.go("call_failed")
        self.assertMode(Mode.OUT_OF_ORDER)

    def test_ringing_out_after_the_connection_went(self):
        self.go("lifted", ("button", "left"))
        self.ok = False
        self.assertEqual(self.wait(30.1), [("hangup",)])
        self.assertMode(Mode.OUT_OF_ORDER)

    def test_online_failures_are_still_no_answer(self):
        self.go("lifted", ("button", "left"), "call_failed")
        self.assertMode(Mode.NO_ANSWER)

    def test_back_online_calls_again(self):
        self.ok = False
        self.go("lifted", ("button", "left"))
        self.wait(15.1)
        self.ok = True
        self.assertEqual(self.go(("button", "left")), [("dial", CLARK)])

    def test_an_incoming_call_during_it_rings(self):
        self.ok = False
        self.go("lifted", ("button", "left"), "hung_up")
        self.ok = True
        self.go(("incoming", AMY))
        self.assertMode(Mode.INCOMING)


if __name__ == "__main__":
    unittest.main()
