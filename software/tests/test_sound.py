"""Tests for judicom/sound.py (no sound card needed).   Run from the software folder:   python3 -m unittest -v"""
import array
import math
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from judicom import config, sound
from judicom.sound import (DTMF, RATE, Sounds, card_exists, dial_tone_pcm, dialable, dialing_seconds, digits_pcm, find_usb_card,
                           ring_pcm)


def samples(pcm):
    a = array.array("h")
    a.frombytes(pcm)
    return a


class Pcm(unittest.TestCase):
    def test_dial_tone_is_one_second_and_loops_smoothly(self):
        s = samples(dial_tone_pcm(0.12))
        self.assertEqual(len(s), RATE)
        self.assertEqual(s[0], 0)
        biggest_step = max(abs(b - a) for a, b in zip(s, s[1:]))
        self.assertLessEqual(abs(s[0] - s[-1]), biggest_step)  # the end runs into the start like any two neighbouring samples
        self.assertLessEqual(max(abs(x) for x in s), int(32767 * 0.24) + 1)

    def test_ring_then_silence(self):
        s = samples(ring_pcm(0.6))
        self.assertEqual(len(s), int((sound.RING_ON + sound.RING_OFF) * RATE))
        on = int(sound.RING_ON * RATE)
        self.assertGreater(max(abs(x) for x in s[:on]), 15000)
        self.assertEqual(max(abs(x) for x in s[on:]), 0)
        self.assertLess(abs(s[0]), 100)                        # faded in and out: no clicks
        self.assertLess(abs(s[on - 1]), 1000)


def goertzel(s, freq, rate=RATE):
    """How strong one frequency is in a piece of sound (0 .. about 1 for a full-scale sine)."""
    k = 2 * math.cos(2 * math.pi * freq / rate)
    a = b = 0.0
    for x in s:
        a, b = x / 32767.0 + k * a - b, a
    return math.sqrt(max(0.0, a * a + b * b - k * a * b)) * 2 / len(s)


def decode(pcm, on=0.08, off=0.06, rate=RATE):
    """Touch-tone sound -> the keys, the way a telephone exchange would hear them."""
    s, n_on, step, keys = samples(pcm), int(on * rate), int(on * rate) + int(off * rate), ""
    for start in range(0, len(s), step):
        piece = s[start:start + n_on]
        lo = max(sound.DTMF_ROWS, key=lambda f: goertzel(piece, f))
        hi = max(sound.DTMF_COLS, key=lambda f: goertzel(piece, f))
        keys += next(k for k, pair in DTMF.items() if pair == (lo, hi))
    return keys


class TouchTones(unittest.TestCase):
    def test_every_key_decodes_back(self):
        keys = "1234567890*#"
        self.assertEqual(decode(digits_pcm(keys, 0.15)), keys)

    def test_a_phone_number(self):
        self.assertEqual(decode(digits_pcm("+1 (555) 010-0142", 0.15)), "15550100142")

    def test_length_and_quiet_between_digits(self):
        s = samples(digits_pcm("55", 0.15))
        on, off = int(0.08 * RATE), int(0.06 * RATE)
        self.assertEqual(len(s), 2 * (on + off))
        self.assertGreater(max(abs(x) for x in s[:on]), 5000)
        self.assertEqual(max(abs(x) for x in s[on:on + off]), 0)
        self.assertLess(abs(s[0]), 200)                         # faded in: no click
        self.assertLessEqual(max(abs(x) for x in s), int(32767 * 0.3) + 1)

    def test_dialable(self):
        self.assertEqual(dialable("+1 (555) 010-0142"), "15550100142")
        self.assertEqual(dialable("frank"), "")                 # a name has no digits (not even A-D, which are not on a phone)
        self.assertEqual(dialable("ext 100"), "100")
        self.assertEqual(dialable(""), "")
        self.assertEqual(dialable(None), "")

    def test_dialing_seconds(self):
        self.assertEqual(dialing_seconds(""), 0.0)
        self.assertEqual(dialing_seconds("hello"), 0.0)
        ten = dialing_seconds("5550100142")
        self.assertAlmostEqual(ten, sound.LEAD_SECONDS + 10 * 0.14 + sound.DIALING_TAIL)
        self.assertLess(ten, 2.5)                               # quick: about a fast dialer's pace
        self.assertGreater(ten, len(digits_pcm("5550100142")) / 2.0 / RATE + sound.LEAD_SECONDS)   # longer than the sound itself


class Cards(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proc = Path(self._tmp.name)

    def cards(self, listing, playable=()):
        (self.proc / "cards").write_text(listing)
        for n in playable:
            (self.proc / ("card%d" % n)).mkdir()
            (self.proc / ("card%d" % n) / "pcm0p").mkdir()

    def test_finds_the_usb_card(self):
        self.cards(" 0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones\n"
                   "                      bcm2835 Headphones\n"
                   " 1 [Device         ]: USB-Audio - USB Audio Device\n"
                   "                      C-Media Electronics Inc. USB Audio Device at usb-3f980000.usb-1.3, full speed\n", playable=(0, 1))
        self.assertEqual(find_usb_card(str(self.proc)), "Device")

    def test_usb_card_that_cannot_play(self):
        self.cards(" 1 [Mic            ]: USB-Audio - USB Microphone\n")
        self.assertIsNone(find_usb_card(str(self.proc)))

    def test_no_cards_at_all(self):
        self.assertIsNone(find_usb_card(str(self.proc / "missing")))

    def test_card_exists(self):
        (self.proc / "Headphones").mkdir()
        self.assertTrue(card_exists("Headphones", str(self.proc)))
        self.assertFalse(card_exists("Device", str(self.proc)))


class FakeLoop:
    made = []

    def __init__(self, card, pcm, name, log, repeat=True):
        self.card, self.name, self.repeat, self.playing, self.starts, self.stops = card, name, repeat, False, 0, 0
        self.pcm = pcm
        FakeLoop.made.append(self)

    def start(self):
        self.playing = True
        self.starts += 1

    def stop(self):
        if self.playing:
            self.stops += 1
        self.playing = False


class Switching(unittest.TestCase):
    def test_only_changes_do_anything(self):
        s = Sounds(handset_card="Device", ringer_card="Headphones", make_loop=FakeLoop)
        self.assertEqual((s.dial.card, s.ring.card), ("Device", "Headphones"))
        s.update(True, False)
        s.update(True, False)
        self.assertTrue(s.dial.playing)
        self.assertFalse(s.ring.playing)
        self.assertEqual(s.dial.starts, 1)
        s.update(False, True)
        self.assertFalse(s.dial.playing)
        self.assertTrue(s.ring.playing)
        s.close()
        self.assertFalse(s.ring.playing)

    def test_digits_play_once_after_the_dial_tone_stops(self):
        s = Sounds(handset_card="Device", ringer_card="Headphones", make_loop=FakeLoop)
        order = []
        s.dial.stop = lambda: order.append("dial tone stopped")
        s.update(False, False, "555")
        self.assertTrue(s.digits.playing)
        self.assertFalse(s.digits.repeat)
        self.assertEqual(s.digits.card, "Device")               # in the handset, not the ringer speaker
        self.assertEqual(order, ["dial tone stopped"])
        self.assertEqual(s.digits.pcm, digits_pcm("555"))
        first = s.digits
        s.update(False, False, "555")
        self.assertIs(s.digits, first)                          # nothing new while the machine keeps asking for the same digits
        s.update(False, False, "")
        self.assertFalse(first.playing)

    def test_the_same_digits_again_play_again(self):
        s = Sounds(handset_card="Device", ringer_card="Headphones", make_loop=FakeLoop)
        s.update(False, False, "555")
        first = s.digits
        s.update(True, False, "")                               # hung up, lifted again ...
        s.update(False, False, "555")                           # ... and the same button
        self.assertIsNot(s.digits, first)
        self.assertTrue(s.digits.playing)

    def test_no_handset_card_no_digits(self):
        s = Sounds(enabled=False, make_loop=FakeLoop)
        s.update(False, False, "555")
        self.assertFalse(s.digits.playing)

    def test_disabled_is_silent(self):
        s = Sounds(enabled=False, make_loop=FakeLoop)
        s.update(True, True)
        self.assertFalse(s.dial.playing)
        self.assertIn("silent", s.describe())


if __name__ == "__main__":
    unittest.main()


class FakeAmp:
    def __init__(self):
        self.is_on, self.switched, self.closed = False, [], False

    def on(self):
        if not self.is_on:
            self.switched.append("on")
        self.is_on = True

    def off(self):
        if self.is_on:
            self.switched.append("off")
        self.is_on = False

    def close(self):
        self.closed = True


class Amplifier(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]
        self.amp = FakeAmp()
        self.s = Sounds(handset_card="Device", ringer_card="Headphones", make_loop=FakeLoop, amp=self.amp, clock=lambda: self.now[0])

    def later(self, seconds):
        self.now[0] += seconds
        self.s.update(*self.s._want)

    def test_on_before_the_ringer_and_off_a_moment_after_it_stops(self):
        order = []
        start = self.s.ring.start
        self.s.ring.start = lambda: (order.append(("ring", self.amp.is_on)), start())
        self.s.update(False, True)
        self.assertEqual(order, [("ring", True)])                      # the amplifier was already on when the ringer started
        self.later(30)
        self.assertTrue(self.amp.is_on)                                # on all through the ringing, gaps and all
        self.s.update(False, False)
        self.later(0.5)
        self.assertTrue(self.amp.is_on)                                # the end of the sound is not cut off
        self.later(config.AMP_OFF_SECONDS)
        self.assertFalse(self.amp.is_on)
        self.assertEqual(self.amp.switched, ["on", "off"])

    def test_message_beeps_switch_it_on_and_it_goes_off_when_they_have_played(self):
        self.s.beep()
        self.assertTrue(self.amp.is_on)
        self.s.beeps.playing = False                                   # aplay has played them and ended by itself
        self.later(0.1)
        self.later(config.AMP_OFF_SECONDS)
        self.assertFalse(self.amp.is_on)

    def test_bongs_one_after_another_keep_it_on(self):
        for step in range(5):
            self.s.bong(step)
            self.s.bongs[step].playing = False
            self.later(0.5)
        self.assertTrue(self.amp.is_on)
        self.assertEqual(self.amp.switched, ["on"])
        self.later(config.AMP_OFF_SECONDS)
        self.assertFalse(self.amp.is_on)

    def test_the_handset_sounds_leave_it_off(self):
        self.s.update(True, False)
        self.s.update(False, False, "555")
        self.assertEqual(self.amp.switched, [])

    def test_closing_switches_it_off(self):
        self.s.update(False, True)
        self.s.close()
        self.assertTrue(self.amp.closed)

    def test_no_amplifier_switch_is_fine(self):
        s = Sounds(handset_card="Device", ringer_card="Headphones", make_loop=FakeLoop)
        s.update(False, True)
        s.beep()
        s.update(False, False)

    def test_a_pin_that_cannot_be_had_is_only_logged(self):
        said = []
        with mock.patch.object(sound, "Amp", side_effect=RuntimeError("GPIO busy")):
            self.assertIsNone(sound.make_amp(said.append))
        self.assertIn("GPIO busy", said[0])
        self.assertIn("25", said[0])


class RingTestPins(unittest.TestCase):
    def pins(self, argv):
        from judicom import ring_test
        args = ring_test.parse(argv)
        return args.pin if any(pin == config.AMP_PIN for pin, _ in args.pin) else [(config.AMP_PIN, 1)] + args.pin

    def test_the_amplifier_is_switched_on_by_itself(self):
        self.assertEqual(self.pins([]), [(25, 1)])

    def test_unless_told_otherwise(self):
        self.assertEqual(self.pins(["--pin", "25=0"]), [(25, 0)])

