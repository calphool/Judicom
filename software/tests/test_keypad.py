"""Tests for the hidden keypad: judicom/keypad.py (the knock, the keys, the number rules), its mode in judicom/machine.py, the
wiring in judicom/main.py, the touch-tone it sends during a call (judicom/calls.py), and its screen (judicom/keypad_view.py, only
with pygame).  Every number here is made up.   Run from the software folder:   python3 -m unittest -v"""
import unittest

from judicom import config
from judicom.inputs import KeyControls
from judicom.keypad import EMERGENCY, NOT_A_NUMBER, OPEN, Keypad, Knock, check_number, pretty_number
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone

TL, TR, BL, MIDDLE = (40, 40), (config.SCREEN_W - 40, 40), (40, config.SCREEN_H - 40), (300, 500)
FRANK = Party("Frank", "husband", "3125550100")


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def centre(key):
    x, y, w, h = Keypad().rects()[key]
    return (x + w // 2, y + h // 2)


class Numbers(unittest.TestCase):
    def test_when_a_number_is_complete(self):
        for digits, verdict in (("", "incomplete"), ("312", "incomplete"), ("312555012", "incomplete"), ("3125550123", "complete"),
                                ("1", "incomplete"), ("1312555012", "incomplete"), ("13125550123", "complete")):
            self.assertEqual(check_number(digits), verdict, digits)

    def test_refused(self):
        for digits in ("911", "1911", "9115"):
            self.assertEqual(check_number(digits), EMERGENCY, digits)
        for digits in ("0", "10", "11"):
            self.assertEqual(check_number(digits), NOT_A_NUMBER, digits)
        self.assertEqual(check_number("91"), "incomplete")                    # not yet: 91x could be an area code... 912 is

    def test_written_as_it_is_typed(self):
        for digits, shown in (("3", "3"), ("3125", "312-5"), ("312555", "312-555"), ("3125550123", "312-555-0123"),
                              ("1", "1"), ("1312", "1 312"), ("13125550123", "1 312-555-0123")):
            self.assertEqual(pretty_number(digits), shown)


class TheKnock(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.knock = Knock(self.clock, knock_seconds=4)

    def taps(self, *spots, gap=1.0):
        out = []
        for spot in spots:
            self.clock.t += gap
            out.append(self.knock.update(True, [spot]))
        return out

    def test_top_left_twice_then_top_right_twice(self):
        self.assertEqual(self.taps(TL, TL, TR, TR), [1, 2, 3, OPEN])
        self.assertEqual(self.knock.done, 0)                                  # ready for next time

    def test_a_wrong_tap_starts_again_without_a_sound(self):
        self.assertEqual(self.taps(TL, TR, TR), [1, None, None])
        self.assertEqual(self.taps(TL, TL, MIDDLE, TR), [1, 2, None, None])
        self.assertEqual(self.taps(TL, TL, BL), [1, 2, None])

    def test_a_third_top_left_is_a_fresh_start(self):
        self.assertEqual(self.taps(TL, TL, TL, TL, TR, TR), [1, 2, 1, 2, 3, OPEN])

    def test_too_slow(self):
        self.assertEqual(self.taps(TL, TL), [1, 2])
        self.assertEqual(self.taps(TR, gap=5.0), [None])
        self.assertEqual(self.taps(TL, TL, TR, TR, gap=3.9), [1, 2, 3, OPEN])

    def test_only_while_ready(self):
        self.taps(TL, TL)
        self.assertIsNone(self.knock.update(False, []))
        self.assertEqual(self.taps(TR, TR), [None, None])


class Keys(unittest.TestCase):
    def test_every_key_is_where_it_is_drawn(self):
        pad = Keypad()
        for key in "0123456789*#":
            self.assertEqual(pad.press(*centre(key)), key)
        self.assertEqual(pad.press(*centre("back")), "back")
        self.assertIsNone(pad.press(*TL))                                     # above the keys
        x, y, w, h = pad.rects()["1"]
        self.assertIsNone(pad.press(x + w + 5, y + 10))                       # between two keys

    def test_keys_stay_on_the_screen(self):
        for key, (x, y, w, h) in Keypad().rects().items():
            self.assertTrue(0 <= x and x + w <= config.SCREEN_W - config.SHELL_RIGHT // 2 and 250 <= y and y + h <= config.SCREEN_H,
                            key)

    def test_delete_only_while_typing(self):
        pad = Keypad()
        self.assertIsNone(pad.press(*centre("back"), in_call=True, typing=False))
        self.assertNotIn("back", [k[0] for k in pad.keys(in_call=True, typing=False)])
        enabled = {k[0]: k[6] for k in pad.keys()}
        self.assertFalse(enabled["*"] or enabled["#"])                       # greyed before a call
        self.assertTrue(all(k[6] for k in pad.keys(in_call=True, typing=False)))

    def test_a_pressed_key_lights_up_for_a_moment(self):
        clock = Clock()
        pad = Keypad(clock)
        pad.press(*centre("5"))
        self.assertTrue([k for k in pad.keys() if k[0] == "5"][0][5])
        clock.t += 1
        pad.tick()
        self.assertFalse([k for k in pad.keys() if k[0] == "5"][0][5])


class TheMode(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.ok = True
        self.m = Machine({"left": FRANK}, clock=self.clock, phone_ok=lambda: self.ok,
                         lookup=lambda d: FRANK if d == "3125550100" else Party())
        self.m.handle("lifted")

    def open(self):
        self.assertEqual(self.m.mode, Mode.LIFTED)
        self.m.handle("keypad")
        self.assertEqual(self.m.mode, Mode.KEYPAD)

    def type(self, keys):
        actions = []
        for k in keys:
            actions += self.m.handle("key", k)
        return actions

    def dial_out(self, number="3125550123"):
        self.open()
        self.assertEqual(self.type(number), [])
        self.assertEqual(self.m.mode, Mode.DIALING)                           # the last digit's tone first
        self.clock.t += 5
        return self.m.tick()

    def test_dial_tone_until_the_first_digit(self):
        self.open()
        self.assertTrue(self.m.dial_tone)
        self.type("3")
        self.assertFalse(self.m.dial_tone)
        self.type(["back"])
        self.assertTrue(self.m.dial_tone)

    def test_the_call_goes_out_by_itself(self):
        actions = self.dial_out()
        self.assertEqual(self.m.mode, Mode.CALLING)
        [(what, party)] = actions
        self.assertEqual((what, party.dial, party.label, party.tones), ("dial", "3125550123", "312-555-0123", "3"))
        self.assertTrue(self.m.keypad_showing)

    def test_the_last_digit_is_dialled_as_a_tone_first(self):
        self.open()
        self.type("312555012")
        self.type("3")
        self.assertEqual(self.m.dialing_tones, "3")
        self.assertTrue(self.m.keypad_showing)

    def test_a_number_in_the_contacts_file_gets_its_name(self):
        [(_, party)] = self.dial_out("3125550100")
        self.assertEqual((party.label, party.dial), ("Frank (husband)", "3125550100"))

    def test_one_and_eleven_digits(self):
        [(_, party)] = self.dial_out("13125550123")
        self.assertEqual((party.dial, party.label), ("13125550123", "1 312-555-0123"))

    def test_delete(self):
        self.open()
        self.type(["3", "1", "2", "back"])
        self.assertEqual(self.m.digits, "31")

    def test_star_and_hash_do_nothing_before_a_call(self):
        self.open()
        self.assertEqual(self.type(["3", "*", "#"]), [])
        self.assertEqual(self.m.digits, "3")

    def test_911_is_refused_and_says_why(self):
        self.open()
        self.type("911")
        self.assertEqual((self.m.mode, self.m.notice, self.m.digits), (Mode.KEYPAD, EMERGENCY, ""))
        self.type("3")
        self.assertEqual((self.m.notice, self.m.digits), ("", "3"))           # the notice goes at the next key

    def test_a_number_starting_with_0(self):
        self.open()
        self.type("0")
        self.assertEqual((self.m.notice, self.m.digits), (NOT_A_NUMBER, ""))

    def test_in_a_call_the_keys_send_tones(self):
        self.dial_out()
        self.m.handle("answered")
        self.assertEqual(self.m.mode, Mode.ONGOING)
        self.assertTrue(self.m.keypad_showing)
        self.assertEqual(self.type(["1", "*", "#"]), [("dtmf", "1"), ("dtmf", "*"), ("dtmf", "#")])
        self.assertEqual(self.type(["back"]), [])

    def test_keys_do_nothing_while_it_rings(self):
        self.dial_out()
        self.assertEqual(self.type("5"), [])

    def test_back_to_the_keypad_after_the_call(self):
        self.dial_out()
        self.m.handle("answered")
        self.m.handle("remote_ended")
        self.assertEqual(self.m.mode, Mode.ENDED)
        self.assertFalse(self.m.keypad_showing)                               # "Call just ended with ..." for a moment
        self.clock.t += 60
        self.m.tick()
        self.assertEqual((self.m.mode, self.m.digits, self.m.keypad_call), (Mode.KEYPAD, "", False))

    def test_back_to_the_keypad_when_nobody_answers(self):
        self.dial_out()
        self.m.handle("call_failed")
        self.clock.t += 60
        self.m.tick()
        self.assertEqual(self.m.mode, Mode.KEYPAD)

    def test_phone_not_working(self):
        self.ok = False
        self.open()
        self.type("3125550123")
        self.assertEqual(self.m.mode, Mode.OUT_OF_ORDER)
        self.clock.t += 60
        self.m.tick()
        self.assertEqual(self.m.mode, Mode.KEYPAD)

    def test_hang_up_closes_it(self):
        self.open()
        self.type("31")
        self.m.handle("hung_up")
        self.assertEqual((self.m.mode, self.m.digits), (Mode.IDLE, ""))
        self.m.handle("lifted")
        self.assertEqual(self.m.mode, Mode.LIFTED)                            # the knock is needed again

    def test_hang_up_during_a_keypad_call(self):
        self.dial_out()
        self.assertEqual(self.m.handle("hung_up"), [("hangup",)])
        self.assertEqual((self.m.mode, self.m.keypad_call), (Mode.IDLE, False))

    def test_left_alone(self):
        self.open()
        self.clock.t += config.KEYPAD_SECONDS - 1
        self.type("3")                                                        # a key starts the time again
        self.clock.t += config.KEYPAD_SECONDS - 1
        self.m.tick()
        self.assertEqual(self.m.mode, Mode.KEYPAD)
        self.clock.t += 2
        self.m.tick()
        self.assertEqual(self.m.mode, Mode.PLEASE_HANG_UP)

    def test_a_caller_is_turned_away_while_dialling(self):
        self.open()
        self.assertEqual(self.m.handle("incoming", Party("Ann")), [("reject",)])

    def test_only_with_the_handset_up(self):
        self.m.handle("hung_up")
        self.m.handle("keypad")
        self.assertEqual(self.m.mode, Mode.IDLE)


class Calls:
    def __init__(self):
        self.done = []

    def do(self, action):
        self.done.append(action)

    def poll(self):
        return []


class Sounds:
    def __init__(self):
        self.bongs, self.tones, self.digits = [], [], ""

    def update(self, dial_tone, ringing, digits=""):
        self.dial_tone, self.digits = dial_tone, digits

    def bong(self, step):
        self.bongs.append(step)

    def key_tone(self, key):
        self.tones.append(key)


class Photos:
    def start(self):
        pass

    def tick(self):
        pass

    def next(self):
        pass


class Taps:
    def __init__(self):
        self.next = []

    def poll(self):
        taps, self.next = self.next, []
        return taps


class Wiring(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.machine = Machine({"left": FRANK}, clock=self.clock)
        self.calls, self.sounds, self.taps = Calls(), Sounds(), Taps()
        self.phone = Phone(self.machine, KeyControls(), self.calls, self.sounds, Photos(), clock=self.clock, taps=self.taps)
        self.phone.step(["l"])

    def tap(self, *spots):
        for spot in spots:
            self.clock.t += 0.5
            self.taps.next = [spot]
            self.phone.step()

    def test_knock_bongs_then_keypad(self):
        self.tap(TL, TL, TR, TR)
        self.assertEqual(self.sounds.bongs, [1, 2, 3, OPEN])
        self.assertEqual(self.machine.mode, Mode.KEYPAD)
        self.assertTrue(self.phone.keypad_needs_draw)

    def test_typing_plays_each_digit_and_dials(self):
        self.tap(TL, TL, TR, TR)
        self.tap(*[centre(k) for k in "3125550123"])
        self.assertEqual(self.sounds.tones, list("312555012"))               # the last one is played by DIALING
        self.assertEqual(self.machine.mode, Mode.DIALING)
        self.clock.t += 5
        self.phone.step()
        self.assertEqual(self.calls.done[-1][0], "dial")
        self.assertEqual(self.calls.done[-1][1].dial, "3125550123")

    def test_tones_down_the_line_during_the_call(self):
        self.tap(TL, TL, TR, TR)
        self.tap(*[centre(k) for k in "3125550123"])
        self.clock.t += 5
        self.phone.step()
        self.machine.handle("answered")
        self.tap(centre("1"), centre("#"))
        self.assertEqual(self.calls.done[-2:], [("dtmf", "1"), ("dtmf", "#")])
        self.assertEqual(self.sounds.tones, list("312555012"))               # none in the handset: the call has the card

    def test_no_knock_with_the_handset_down(self):
        self.phone.step(["l"])                                                # hung up
        self.tap(TL, TL, TR, TR)
        self.assertEqual((self.sounds.bongs, self.machine.mode), ([], Mode.IDLE))


class Sending(unittest.TestCase):
    def test_dtmf_is_sndcode(self):
        import socket
        from judicom.calls import Baresip, NetstringReader
        ours, theirs = socket.socketpair()
        calls = Baresip(("127.0.0.1", 4444), lambda m: None, connect=lambda a, timeout: ours)
        try:
            calls.do(("dtmf", "5"))
            theirs.settimeout(1.0)
            import json
            [cmd] = [json.loads(m) for m in NetstringReader().feed(theirs.recv(4096))]
            self.assertEqual((cmd["command"], cmd["params"]), ("sndcode", "5"))
        finally:
            calls.close()
            theirs.close()


try:
    import pygame                                                             # noqa: F401
except ImportError:
    pygame = None


@unittest.skipIf(pygame is None, "needs pygame")
class Screen(unittest.TestCase):
    def test_every_state_draws(self):
        from types import SimpleNamespace
        from judicom import keypad_view
        surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
        pad = Keypad()
        for state in (SimpleNamespace(mode=Mode.KEYPAD, digits="", notice="", party=None),
                      SimpleNamespace(mode=Mode.KEYPAD, digits="13125550123", notice="", party=None),
                      SimpleNamespace(mode=Mode.KEYPAD, digits="", notice=EMERGENCY, party=None),
                      SimpleNamespace(mode=Mode.DIALING, digits="", notice="", party=FRANK),
                      SimpleNamespace(mode=Mode.ONGOING, digits="", notice="", party=Party(dial="3125550123", shown="312-555-0123"))):
            keypad_view.show(surf, state, pad)


if __name__ == "__main__":
    unittest.main()
