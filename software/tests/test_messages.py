"""Tests for judicom/messages.py, the screen it draws, what main.py does with it, and tools/nas_request.py.
Run from the software folder:   python3 -m unittest -v"""
import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

from judicom import messages, sound
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone
from judicom.messages import TOUCH_GUARD, Message, Postbox
from judicom.touch import Taps

ONE = "20261106-120000-aaaaaa"
TWO = "20261106-120100-bbbbbb"
NOON = datetime.datetime(2026, 11, 6, 12, 0, 0)


def good(message_id=ONE, sender="Ann", text="Hi Mom"):
    return json.dumps({"id": message_id, "from": sender, "text": text})


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.clock = Clock()
        self.day = True

    def box(self):
        return Postbox(self.dir, can_show=lambda: self.day, clock=self.clock, now=lambda: NOON)

    def later(self, seconds=2.0):
        self.clock.t += seconds


class Cleaning(unittest.TestCase):
    def test_spaces_and_line_breaks_become_single_spaces(self):
        self.assertEqual(messages.clean_text("  Hi\r\n\n  Mom\t! "), "Hi Mom !")

    def test_emoji_and_control_characters_go(self):
        self.assertEqual(messages.clean_text("Love you \U0001F60A\U0001F468‍\U0001F469 ❤️\x07 Mom"), "Love you ❤ Mom")

    def test_accents_stay(self):
        self.assertEqual(messages.clean_text("Café — olé"), "Café — olé")


class Parsing(unittest.TestCase):
    def test_a_good_one(self):
        self.assertEqual(messages.parse(good()), Message(ONE, "Ann", "Hi Mom"))

    def test_bad_ones(self):
        for raw in ("", "nonsense", "[]", "{}", '{"id": 1, "from": "Ann", "text": "x"}', '{"id": "%s", "from": 3, "text": "x"}' % ONE,
                    good(message_id="../../etc/passwd"), good(message_id="x"), good(sender=""), good(sender="x" * 41), good(text=""),
                    good(text="   "), good(text="\U0001F60A"), good(text="x" * 201)):
            with self.assertRaises(ValueError, msg=raw):
                messages.parse(raw)

    def test_200_characters_is_allowed(self):
        self.assertEqual(len(messages.parse(good(text="x" * 200)).text), 200)


class Delivering(Folder):
    def test_it_lands_as_a_file_with_nothing_left_over(self):
        messages.deliver(good(), self.dir)
        self.assertEqual([p.name for p in self.dir.iterdir()], [ONE + ".json"])
        self.assertEqual(messages.parse((self.dir / (ONE + ".json")).read_text()).text, "Hi Mom")

    def test_the_folder_is_made_if_needed(self):
        messages.deliver(good(), self.dir / "new")
        self.assertEqual(messages.statuses(self.dir / "new"), {ONE: None})

    def test_a_bad_one_leaves_nothing(self):
        with self.assertRaises(ValueError):
            messages.deliver("nonsense", self.dir)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_too_many_waiting_are_refused(self):
        for n in range(messages.MAX_WAITING):
            messages.deliver(good("20261106-120000-%06x" % n), self.dir)
        with self.assertRaises(ValueError):
            messages.deliver(good(TWO), self.dir)


class Showing(Folder):
    def test_nothing_to_show(self):
        box = self.box()
        self.assertFalse(box.tick(True))
        self.assertIsNone(box.showing)
        self.assertFalse(box.take_beep())

    def test_it_shows_and_beeps_once(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        self.assertTrue(box.tick(True))
        self.assertEqual(box.showing.text, "Hi Mom")
        self.assertTrue(box.take_beep())
        self.assertFalse(box.take_beep())
        self.assertFalse(box.tick(True))

    def test_a_message_arriving_later_is_noticed_within_a_second_or_so(self):
        box = self.box()
        box.tick(True)
        messages.deliver(good(), self.dir)
        self.assertFalse(box.tick(True))
        self.later()
        self.assertTrue(box.tick(True))

    def test_it_waits_while_something_else_has_the_screen(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        self.assertFalse(box.tick(False))
        self.assertIsNone(box.showing)
        self.assertFalse(box.take_beep())
        self.assertTrue(box.tick(True))
        self.assertTrue(box.take_beep())

    def test_a_call_sends_it_away_and_it_comes_back_without_beeping_again(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        box.take_beep()
        box.tick(False)
        self.assertIsNone(box.showing)
        self.assertTrue(box.tick(True))
        self.assertEqual(box.showing.id, ONE)
        self.assertFalse(box.take_beep())

    def test_at_night_it_waits_for_the_morning_in_silence(self):
        messages.deliver(good(), self.dir)
        self.day = False
        box = self.box()
        box.tick(True)
        self.assertIsNone(box.showing)
        self.assertFalse(box.take_beep())
        self.day = True
        box.tick(True)
        self.assertEqual(box.showing.id, ONE)
        self.assertTrue(box.take_beep())

    def test_one_left_unread_at_nightfall_goes_dark_and_comes_back_quietly(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        box.take_beep()
        self.day = False
        box.tick(True)
        self.assertIsNone(box.showing)
        self.day = True
        box.tick(True)
        self.assertEqual(box.showing.id, ONE)
        self.assertFalse(box.take_beep())

    def test_oldest_first_each_with_its_beeps(self):
        messages.deliver(good(TWO, text="second"), self.dir)
        messages.deliver(good(ONE, text="first"), self.dir)
        box = self.box()
        box.tick(True)
        self.assertEqual((box.showing.text, box.more), ("first", 1))
        box.take_beep()
        box.finish()
        self.assertTrue(box.tick(True))
        self.assertEqual((box.showing.text, box.more), ("second", 0))
        self.assertTrue(box.take_beep())

    def test_a_second_message_does_not_push_the_first_off_but_changes_the_hint(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        box.take_beep()
        messages.deliver(good(TWO), self.dir)
        self.later()
        self.assertTrue(box.tick(True))
        self.assertEqual((box.showing.id, box.more), (ONE, 1))
        self.assertFalse(box.take_beep())

    def test_a_restart_loses_nothing(self):
        messages.deliver(good(), self.dir)
        self.box().tick(True)
        box = self.box()
        box.tick(True)
        self.assertEqual(box.showing.id, ONE)

    def test_a_bad_file_is_set_aside_and_does_not_stop_the_good_ones(self):
        (self.dir / "20261106-110000-cccccc.json").write_text("nonsense")
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        self.assertEqual(box.showing.id, ONE)
        self.assertTrue((self.dir / ".bad-20261106-110000-cccccc.json").exists())

    def test_a_message_removed_by_hand_goes_from_the_screen(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        (self.dir / (ONE + ".json")).unlink()
        self.later()
        self.assertTrue(box.tick(True))
        self.assertIsNone(box.showing)


class Finishing(Folder):
    def showing(self):
        messages.deliver(good(), self.dir)
        box = self.box()
        box.tick(True)
        return box

    def test_a_touch_too_soon_does_nothing(self):
        box = self.showing()
        self.later(TOUCH_GUARD - 0.1)
        box.touched()
        self.assertIsNotNone(box.showing)

    def test_a_touch_after_the_guard_finishes_it(self):
        box = self.showing()
        self.later(TOUCH_GUARD)
        box.touched()
        self.assertIsNone(box.showing)

    def test_finishing_counts_at_once_and_records_when(self):
        box = self.showing()
        box.finish()
        self.assertEqual(messages.statuses(self.dir), {ONE: "2026-11-06T12:00:00"})
        self.assertFalse((self.dir / (ONE + ".json")).exists())

    def test_it_is_not_shown_again(self):
        box = self.showing()
        box.finish()
        self.later()
        box.tick(True)
        self.assertIsNone(box.showing)

    def test_a_card_that_cannot_be_written_does_not_bring_it_back(self):
        box = self.showing()
        with mock.patch.object(messages, "write_file", side_effect=OSError("full")):
            box.finish()
        self.later()
        box.tick(True)
        self.assertIsNone(box.showing)

    def test_finishing_with_nothing_showing_is_harmless(self):
        self.box().finish()

    def test_only_the_newest_read_ones_are_kept(self):
        box = self.box()
        for n in range(messages.KEEP_READ + 3):
            messages.deliver(good("20261106-120000-%06x" % n), self.dir)
            self.later()
            box.tick(True)
            box.finish()
        kept = messages.statuses(self.dir)
        self.assertEqual(len(kept), messages.KEEP_READ)
        self.assertNotIn("20261106-120000-000000", kept)


# ---- with the rest of the program
class Controls:
    def __init__(self):
        self.events = []

    def poll(self):
        events, self.events = self.events, []
        return events

    def key(self, key):
        return []


class Calls:
    def __init__(self):
        self.done = []

    def poll(self):
        return []

    def do(self, action):
        self.done.append(action)


class Sounds:
    def __init__(self):
        self.beeps = 0

    def update(self, dial_tone, ringing, digits=""):
        pass

    def beep(self):
        self.beeps += 1


class Photos:
    def __init__(self):
        self.starts = self.ticks = self.nexts = 0

    def start(self):
        self.starts += 1

    def tick(self):
        self.ticks += 1

    def next(self):
        self.nexts += 1


class FakeTaps:
    def __init__(self):
        self.tap = False

    def poll(self):                                 # like touch.Taps: where fingers came down (here: the middle, once)
        tap, self.tap = self.tap, False
        return [(300, 500)] if tap else []


class WithThePhone(Folder):
    def setUp(self):
        super().setUp()
        self.controls, self.calls, self.sounds, self.photos, self.taps = Controls(), Calls(), Sounds(), Photos(), FakeTaps()
        self.ann = Party("Ann", "daughter", "ann")
        self.machine = Machine({"left": self.ann}, clock=self.clock)
        self.postbox = self.box()
        self.phone = Phone(self.machine, self.controls, self.calls, self.sounds, self.photos, clock=self.clock,
                           postbox=self.postbox, taps=self.taps)
        self.phone.step()

    def arrive(self):
        messages.deliver(good(), self.dir)
        self.later()
        return self.phone.step()

    def event(self, *event):
        self.controls.events.append(event)
        return self.phone.step()

    def test_it_takes_the_screen_from_the_photos_with_three_beeps(self):
        self.assertTrue(self.arrive())
        self.assertEqual(self.phone.message.text, "Hi Mom")
        self.assertEqual(self.sounds.beeps, 1)

    def test_the_photos_stand_still_and_space_does_nothing_meanwhile(self):
        self.arrive()
        ticks, starts = self.photos.ticks, self.photos.starts
        self.assertFalse(self.phone.step(["next"]))
        self.assertEqual((self.photos.ticks, self.photos.starts, self.photos.nexts), (ticks, starts, 0))

    def test_a_touch_brings_back_a_fresh_photo(self):
        self.arrive()
        self.later(TOUCH_GUARD)
        starts = self.photos.starts
        self.taps.tap = True
        self.assertTrue(self.phone.step())
        self.assertIsNone(self.phone.message)
        self.assertEqual(self.photos.starts, starts + 1)

    def test_the_t_key_is_a_touch(self):
        self.arrive()
        self.later(TOUCH_GUARD)
        self.phone.step(["t"])
        self.assertIsNone(self.phone.message)

    def test_a_button_finishes_it_and_calls_nobody(self):
        self.arrive()
        self.event("button", "left")
        self.assertIsNone(self.phone.message)
        self.assertEqual(self.machine.mode, Mode.IDLE)
        self.assertEqual(self.calls.done, [])

    def test_lifting_the_handset_finishes_it_and_gives_the_dial_tone_screen(self):
        self.arrive()
        self.event("lifted")
        self.assertIsNone(self.phone.message)
        self.assertEqual(self.machine.mode, Mode.LIFTED)
        self.assertEqual(messages.statuses(self.dir)[ONE], "2026-11-06T12:00:00")

    def test_with_the_handset_up_it_waits_until_it_is_back(self):
        self.event("lifted")
        self.arrive()
        self.assertIsNone(self.phone.message)
        self.assertEqual(self.sounds.beeps, 0)
        self.event("hung_up")
        self.assertEqual(self.phone.message.text, "Hi Mom")
        self.assertEqual(self.sounds.beeps, 1)

    def test_a_call_takes_the_screen_and_the_message_comes_back_unread(self):
        self.arrive()
        self.event("incoming", self.ann)
        self.assertEqual(self.machine.mode, Mode.INCOMING)
        self.assertIsNone(self.phone.message)
        self.event("lifted")                                # answering is not reading
        self.assertEqual(messages.statuses(self.dir)[ONE], None)
        self.event("answered")
        self.event("remote_ended")
        self.event("hung_up")
        self.later(60)
        self.phone.step()
        self.assertEqual(self.machine.mode, Mode.IDLE)
        self.assertEqual(self.phone.message.id, ONE)
        self.assertEqual(self.sounds.beeps, 1)

    def test_without_a_postbox_all_is_as_before(self):
        phone = Phone(Machine({}, clock=self.clock), Controls(), Calls(), Sounds(), Photos(), clock=self.clock)
        phone.step()
        self.assertIsNone(phone.message)


class Beeps(unittest.TestCase):
    def test_three_and_quiet_between(self):
        pcm = sound.beeps_pcm()
        on, off = int(sound.BEEP_ON * sound.RATE) * 2, int(sound.BEEP_OFF * sound.RATE) * 2
        self.assertEqual(len(pcm), (on + off) * 3)
        for n in range(3):
            start = n * (on + off)
            self.assertTrue(any(pcm[start:start + on]))
            self.assertFalse(any(pcm[start + on:start + on + off]))

    def loop(self):
        made = []

        class Loop:
            def __init__(self, card, pcm, name, log, repeat=True):
                self.name, self.repeat, self.starts, self.stops = name, repeat, 0, 0
                made.append(self)

            def start(self):
                self.starts += 1

            def stop(self):
                self.stops += 1
        return Loop, made

    def test_they_play_once_on_the_ringer_card(self):
        loop, made = self.loop()
        sounds = sound.Sounds(handset_card="Device", ringer_card="Headphones", make_loop=loop)
        sounds.beep()
        beeps = next(m for m in made if m.name == "message beeps")
        self.assertEqual((beeps.repeat, beeps.starts), (False, 1))

    def test_not_over_the_ringer_and_the_ringer_stops_them(self):
        loop, made = self.loop()
        sounds = sound.Sounds(handset_card="Device", ringer_card="Headphones", make_loop=loop)
        beeps = next(m for m in made if m.name == "message beeps")
        sounds.update(False, True)
        self.assertEqual(beeps.stops, 1)
        sounds.beep()
        self.assertEqual(beeps.starts, 0)

    def test_no_card_is_fine(self):
        sound.Sounds(enabled=False).beep()


class TouchPanel(unittest.TestCase):
    def devices(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / "devices"
        path.write_text(text)
        return str(path)

    def taps(self, fingers):
        class Panel:
            closed = False

            def __init__(self, path, flip=False):
                pass

            def poll(self):
                value = fingers.pop(0)
                if isinstance(value, Exception):
                    raise value
                return value

            def close(self):
                Panel.closed = True
        block = 'N: Name="Panel"\nH: Handlers=event3\nB: ABS=%x\n' % (1 << 0x35 | 1 << 0x36)
        return Taps(devices=self.devices(block), open_panel=Panel)

    def test_a_tap_counts_once_however_long_the_finger_stays(self):
        taps, now = self.reconnecting(self.devices(self.panel_block(3)), [[{}, {0: (1, 1)}, {0: (2, 2)}, {}, {1: (3, 3)}]])
        seen = []
        for _ in range(5):
            seen.append(taps.poll())
            now[0] += 1.0
        self.assertEqual(seen, [[], [(1, 1)], [], [], [(3, 3)]])

    def timed(self, script):
        """script: (seconds, what the panel gives).  Returns the taps seen."""
        taps, now = self.reconnecting(self.devices(self.panel_block(3)), [[fingers for _, fingers in script]])
        seen = []
        for t, _ in script:
            now[0] = t
            seen += taps.poll()
        return seen

    def test_a_press_reported_twice_is_one_tap(self):                # as recorded on 2026-11-06
        self.assertEqual(self.timed([(20.23, {0: (80, 70)}), (20.33, {}), (20.43, {0: (77, 72)}), (20.70, {})]), [(80, 70)])

    def test_the_longest_echo_recorded_and_a_third_report(self):
        self.assertEqual(self.timed([(23.02, {0: (506, 949)}), (23.13, {}), (23.29, {0: (506, 950)}), (23.60, {})]), [(506, 949)])
        self.assertEqual(self.timed([(39.08, {0: (69, 959)}), (39.19, {}), (39.29, {0: (67, 959)}), (39.49, {}), (39.56, {0: (53, 959)}),
                                     (39.69, {})]), [(69, 959)])

    def test_the_real_taps_recorded_all_count(self):
        script = []
        for t, place in ((21.58, (534, 73)), (23.02, (506, 949)), (24.44, (67, 916))):
            script += [(t, {0: place}), (t + 0.1, {}), (t + 0.2, {0: place}), (t + 0.5, {})]
        self.assertEqual(self.timed(script), [(534, 73), (506, 949), (67, 916)])

    def test_the_same_spot_again_after_a_moment_is_a_new_tap(self):
        self.assertEqual(self.timed([(1.0, {0: (10, 10)}), (1.1, {}), (1.4, {0: (10, 10)})]), [(10, 10), (10, 10)])

    def test_the_next_key_along_is_never_an_echo(self):
        self.assertEqual(self.timed([(1.0, {0: (30, 700)}), (1.1, {}), (1.15, {0: (90, 700)})]), [(30, 700), (90, 700)])

    def test_a_second_finger_is_a_tap_of_its_own(self):
        taps = self.taps([{0: (1, 1)}, {0: (1, 1), 1: (5, 5)}, {1: (5, 5)}])
        self.assertEqual([taps.poll() for _ in range(3)], [[(1, 1)], [(5, 5)], []])

    def test_no_panel_means_no_taps(self):
        taps = Taps(devices=self.devices('N: Name="Keyboard"\nH: Handlers=kbd event1\nB: EV=3\n'))
        self.assertFalse(taps.poll())

    def test_no_device_list_is_fine(self):
        self.assertFalse(Taps(devices="/no/such/file").poll())

    def test_a_panel_that_comes_loose_does_not_stop_the_phone(self):
        taps = self.taps([OSError("gone")])
        self.assertFalse(taps.poll())
        self.assertFalse(taps.poll())

    def reconnecting(self, devices, opened, log=None):
        """A Taps with a clock of its own; `opened` is a list of what the panel gives, and each opening uses the next one."""
        class Panel:
            def __init__(self, path, flip=False):
                self.path, self.script = path, opened.pop(0)

            def poll(self):
                value = self.script.pop(0)
                if isinstance(value, Exception):
                    raise value
                return value

            def close(self):
                pass
        now = [0.0]
        return Taps(log=log, devices=devices, open_panel=Panel, clock=lambda: now[0]), now

    PANEL = 'N: Name="Panel"\nH: Handlers=event%d\nB: ABS=%x\n'

    def panel_block(self, event):
        return self.PANEL % (event, 1 << 0x35 | 1 << 0x36)

    def test_a_panel_that_comes_loose_comes_back_by_itself_even_as_another_device(self):
        said = []
        devices = self.devices(self.panel_block(3))
        taps, now = self.reconnecting(devices, [[OSError("gone")], [{0: (7, 8)}]], said.append)
        self.assertEqual(taps.poll(), [])
        self.assertIsNone(taps.panel)
        now[0] = 4.9
        self.assertEqual(taps.poll(), [])                              # not yet
        self.assertIsNone(taps.panel)
        Path(devices).write_text(self.panel_block(5))                  # USB gives it a new number
        now[0] = 5.0
        self.assertEqual(taps.poll(), [(7, 8)])
        self.assertEqual(taps.panel.path, "/dev/input/event5")
        self.assertEqual(said[-1], "touch screen: Panel (/dev/input/event5)")

    def test_a_finger_held_through_a_dropout_is_a_new_tap_afterwards(self):
        taps, now = self.reconnecting(self.devices(self.panel_block(3)), [[{0: (1, 1)}, OSError("gone")], [{0: (1, 1)}]])
        self.assertEqual(taps.poll(), [(1, 1)])
        self.assertEqual(taps.poll(), [])
        now[0] = 5.0
        self.assertEqual(taps.poll(), [(1, 1)])

    def test_a_panel_plugged_in_after_the_start_is_found(self):
        devices = self.devices('N: Name="Keyboard"\nH: Handlers=kbd event1\nB: EV=3\n')
        taps, now = self.reconnecting(devices, [[{0: (2, 3)}]])
        self.assertEqual(taps.poll(), [])
        Path(devices).write_text(self.panel_block(4))
        now[0] = 5.0
        self.assertEqual(taps.poll(), [(2, 3)])

    def test_looking_again_and_again_says_so_once(self):
        said = []
        taps, now = self.reconnecting(self.devices('N: Name="Keyboard"\nH: Handlers=kbd event1\nB: EV=3\n'), [], said.append)
        for t in (5.0, 10.0, 15.0):
            now[0] = t
            taps.poll()
        self.assertEqual(len(said), 1)


@unittest.skipIf(pygame is None, "pygame is not installed")
class Screen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((600, 1024))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw
        draw.reset()
        pygame.quit()

    def surface(self, *args, **kw):
        from judicom import message_view
        s = pygame.Surface((600, 1024))
        message_view.show(s, *args, **kw)
        return s

    def test_the_hint_breathes_from_resting_to_brightest_and_back(self):
        from judicom import message_view as view
        seen = [view.pulse(i * view.HINT_SECONDS / 200) for i in range(201)]
        self.assertEqual((seen[0], max(seen), min(seen), seen[-1]), (0, view.HINT_BOB, 0, 0))
        self.assertEqual(seen[100], view.HINT_BOB)
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(seen, seen[1:])))

    def test_the_hint_is_drawn_again_without_touching_the_rest_of_the_screen(self):
        from judicom import message_view as view
        message = Message("20261106-120000-abcdef", "Ann", "word " * 40)
        resting, bright = self.surface(message), self.surface(message)
        view.show_hint(bright, 0, view.HINT_BOB)
        top = pygame.Rect(0, 0, 600, view.HINT_TOP)
        self.assertEqual(pygame.image.tobytes(resting.subsurface(top), "RGB"), pygame.image.tobytes(bright.subsurface(top), "RGB"))
        self.assertNotEqual(pygame.image.tobytes(resting, "RGB"), pygame.image.tobytes(bright, "RGB"))

    def test_the_hint_comes_back_to_exactly_what_it_was(self):
        from judicom import message_view as view
        message = Message("20261106-120000-abcdef", "Ann", "Hi Mom")
        first, again = self.surface(message, more=1), self.surface(message, more=1)
        view.show_hint(again, 1, view.HINT_BOB)
        view.show_hint(again, 1, 0)
        self.assertEqual(pygame.image.tobytes(first, "RGB"), pygame.image.tobytes(again, "RGB"))

    def test_the_longest_bubble_stays_above_the_strip_that_is_drawn_again(self):
        from judicom import message_view as view
        size, lines = view.fitted("word " * 40)
        self.assertLessEqual(view.BUBBLE_TOP + len(lines) * int(size * view.SPACING) + 2 * view.PAD, view.HINT_TOP)
        self.assertGreaterEqual(view.HINT_Y - view.HINT_BOB, view.HINT_TOP)

    def test_short_words_are_bigger_than_long_ones(self):
        from judicom import message_view
        self.assertGreater(message_view.fitted("Hi Mom!")[0], message_view.fitted("word " * 40)[0])

    def test_the_longest_message_stays_inside_the_bubble_at_a_readable_size(self):
        from judicom import message_view
        size, lines = message_view.fitted("word " * 40)
        self.assertGreaterEqual(size, 30)
        self.assertLessEqual(len(lines) * size * message_view.SPACING, message_view.BUBBLE_BOTTOM - message_view.BUBBLE_TOP)

    def test_it_draws_with_and_without_a_face_and_with_awkward_text(self):
        for text in ("Hi", "x" * 200, "word " * 40):
            self.surface(Message(ONE, "Ann", text))

    def test_a_picture_is_used_when_there_is_one(self):
        class Faces:
            def get(self, name, size):
                face = pygame.Surface((size, size))
                face.fill((200, 0, 0))
                return face
        self.assertEqual(self.surface(Message(ONE, "Ann", "Hi"), Faces()).get_at((300, 200))[:3], (200, 0, 0))


class Requests(Folder):
    """tools/nas_request.py, run as the forced command would run it."""

    def run_it(self, request, stdin=b""):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND=request, JUDICOM_MESSAGES=str(self.dir))
        tool = Path(__file__).resolve().parents[1] / "tools" / "nas_request.py"
        return subprocess.run([sys.executable, str(tool)], input=stdin, env=env, capture_output=True, timeout=30)

    def test_a_message_arrives(self):
        result = self.run_it("message", good().encode())
        self.assertEqual((result.returncode, result.stdout.strip()), (0, b"ok"))
        self.assertEqual(messages.statuses(self.dir), {ONE: None})

    def test_a_bad_message_says_why_and_leaves_nothing(self):
        result = self.run_it("message", b"nonsense")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"nas_request: ", result.stderr)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_it_reports_what_has_been_read(self):
        messages.deliver(good(), self.dir)
        self.assertEqual(json.loads(self.run_it("messages").stdout), {ONE: None})

    def test_nothing_else_may_be_asked_for(self):
        for request in ("id", "cat /etc/passwd", "screen; id", "message extra"):
            result = self.run_it(request)
            self.assertEqual((result.returncode, result.stdout), (1, b""), request)


if __name__ == "__main__":
    unittest.main()
