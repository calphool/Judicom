"""Tests for judicom/sound.py (no sound card needed).   Run from the software folder:   python3 -m unittest -v"""
import array
import tempfile
import unittest
from pathlib import Path

from judicom import sound
from judicom.sound import RATE, Sounds, card_exists, dial_tone_pcm, find_usb_card, ring_pcm


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
    def __init__(self, card, pcm, name, log):
        self.card, self.name, self.playing, self.starts = card, name, False, 0

    def start(self):
        self.playing = True
        self.starts += 1

    def stop(self):
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

    def test_disabled_is_silent(self):
        s = Sounds(enabled=False, make_loop=FakeLoop)
        s.update(True, True)
        self.assertFalse(s.dial.playing)
        self.assertIn("silent", s.describe())


if __name__ == "__main__":
    unittest.main()
