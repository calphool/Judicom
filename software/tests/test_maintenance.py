"""The maintenance shell: the sequence that opens it, the keyboard, a real bash on a pseudo-terminal, and how it sits with the phone."""
import importlib.util
import os
import time
import unittest

from judicom import config
from judicom.inputs import Controls, KeyControls
from judicom.keyboard import KEY_H, Keyboard
from judicom.machine import Machine, Mode, Party
from judicom.main import Phone
from judicom.maintenance import LAST_BONG, Knock, Maintenance, corner
from judicom.sound import BONG_HZ, Sounds, bong_pcm

try:
    import pygame
except ImportError:
    pygame = None
HAVE_PYTE = importlib.util.find_spec("pyte") is not None
if HAVE_PYTE:
    from judicom.shell import Shell

W, H = config.SCREEN_W, config.SCREEN_H
TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT = (20, 20), (W - 20, 20), (W - 20, H - 20), (20, H - 20)
CLOCKWISE = (TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT)
BOTH = {"left", "right"}


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Corners(unittest.TestCase):
    def test_the_four_corners(self):
        self.assertEqual([corner(*c) for c in CLOCKWISE], [(0, 0), (1, 0), (1, 1), (0, 1)])

    def test_anywhere_else_is_no_corner(self):
        for spot in ((W // 2, 20), (20, H // 2), (W // 2, H // 2), (W - 20, H // 2)):
            self.assertIsNone(corner(*spot))


class Sequence(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.knock = Knock(self.clock)
        self.knock.update(True, False, [])            # the buttons are up to begin with

    def arm(self):
        self.assertIsNone(self.knock.update(True, True, []))
        self.clock.t += config.ARM_SECONDS
        self.assertEqual(self.knock.update(True, True, []), 0)
        self.knock.update(True, False, [])

    def tap(self, spot):
        return self.knock.update(True, False, [spot])

    def test_the_whole_sequence(self):
        self.arm()
        self.assertEqual([self.tap(c) for c in CLOCKWISE], [1, 2, 3, LAST_BONG])
        self.assertFalse(self.knock.armed)

    def test_too_short_a_hold_arms_nothing(self):
        self.knock.update(True, True, [])
        self.clock.t += config.ARM_SECONDS - 0.1
        self.assertIsNone(self.knock.update(True, True, []))
        self.assertIsNone(self.knock.update(True, False, []))
        self.clock.t += 5
        self.assertIsNone(self.knock.update(True, True, []))
        self.assertFalse(self.knock.armed)

    def test_corners_without_the_buttons_do_nothing(self):
        self.assertEqual([self.tap(c) for c in CLOCKWISE], [None] * 4)

    def test_not_with_the_handset_up(self):
        self.knock.update(False, True, [])
        self.clock.t += 10
        self.assertIsNone(self.knock.update(False, True, []))
        self.assertFalse(self.knock.armed)

    def test_a_hold_that_began_with_the_handset_up_must_be_let_go_first(self):
        self.knock.update(False, True, [])
        self.knock.update(True, True, [])
        self.clock.t += 10
        self.assertIsNone(self.knock.update(True, True, []))
        self.assertFalse(self.knock.armed)

    def test_buttons_already_down_when_the_program_starts_do_not_count(self):
        knock = Knock(self.clock)
        knock.update(True, True, [])
        self.clock.t += 10
        self.assertIsNone(knock.update(True, True, []))

    def test_the_wrong_corner_ends_it_silently(self):
        self.arm()
        self.tap(TOP_LEFT)
        self.assertIsNone(self.tap(BOTTOM_RIGHT))
        self.assertFalse(self.knock.armed)
        self.assertIsNone(self.tap(TOP_RIGHT))

    def test_anticlockwise_is_wrong(self):
        self.arm()
        self.tap(TOP_LEFT)
        self.assertIsNone(self.tap(BOTTOM_LEFT))
        self.assertFalse(self.knock.armed)

    def test_a_tap_in_the_middle_ends_it(self):
        self.arm()
        self.assertIsNone(self.tap((W // 2, H // 2)))
        self.assertFalse(self.knock.armed)

    def test_too_slow_ends_it(self):
        self.arm()
        self.tap(TOP_LEFT)
        self.clock.t += config.KNOCK_SECONDS
        self.assertIsNone(self.tap(TOP_RIGHT))
        self.assertFalse(self.knock.armed)

    def test_each_corner_gives_more_time(self):
        self.arm()
        for spot, bong in zip(CLOCKWISE, (1, 2, 3, 4)):
            self.clock.t += config.KNOCK_SECONDS - 1
            self.assertEqual(self.tap(spot), bong)

    def test_lifting_the_handset_ends_it(self):
        self.arm()
        self.tap(TOP_LEFT)
        self.knock.update(False, False, [])
        self.assertFalse(self.knock.armed)

    def test_still_holding_after_it_ended_does_not_arm_again(self):
        self.assertIsNone(self.knock.update(True, True, []))
        self.clock.t += config.ARM_SECONDS
        self.assertEqual(self.knock.update(True, True, []), 0)
        self.knock.update(True, True, [(W // 2, H // 2)])         # wrong: over
        self.clock.t += 10
        self.assertIsNone(self.knock.update(True, True, []))
        self.assertIsNone(self.knock.update(True, True, []))
        self.assertFalse(self.knock.armed)


class Keys(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.keyboard = Keyboard(self.clock)

    def press(self, name):
        for label, x, y, w, h, _ in self.keyboard.keys():
            if label == name:
                return self.keyboard.press(x + w // 2, y + h // 2)
        self.fail("no key %r" % name)

    def test_every_row_fills_the_screen_and_ends_at_the_bottom(self):
        for symbols in (False, True):
            self.keyboard.symbols = symbols
            keys = self.keyboard.keys()
            rows = {}
            for _, x, y, w, h, _ in keys:
                rows[y] = rows.get(y, 0) + w
            self.assertEqual(set(rows.values()), {W - config.SHELL_RIGHT})
            self.assertEqual(max(rows) + KEY_H, H)

    def test_the_terminal_ends_above_the_keyboard(self):
        self.assertLessEqual(config.SHELL_TOP + config.SHELL_ROWS * 19, self.keyboard.top)

    def test_the_terminal_stops_short_of_the_right_bezel(self):
        self.assertLessEqual(config.SHELL_COLUMNS * 10, W - config.SHELL_RIGHT)

    def test_a_letter(self):
        self.assertEqual(self.press("q"), b"q")

    def test_shift_counts_for_one_key(self):
        self.assertEqual(self.press("Shift"), b"")
        self.assertEqual(self.press("Q"), b"Q")
        self.assertEqual(self.press("q"), b"q")

    def test_ctrl_c_is_byte_3(self):
        self.press("Ctrl")
        self.assertEqual(self.press("c"), b"\x03")
        self.assertEqual(self.press("c"), b"c")

    def test_the_special_keys(self):
        for name, data in (("Enter", b"\r"), ("Bksp", b"\x7f"), ("Tab", b"\t"), ("Esc", b"\x1b"), ("Space", b" "),
                           ("↑", b"\x1b[A"), ("←", b"\x1b[D"), ("PgDn", b"\x1b[6~"), ("|", b"|")):
            self.assertEqual(self.press(name), data)

    def test_the_symbols_stay_until_sym_is_pressed_again(self):
        self.press("Sym")
        self.assertEqual(self.press("!"), b"!")
        self.assertEqual(self.press("\\"), b"\\")
        self.press("Sym")
        self.assertEqual(self.press("q"), b"q")

    def test_everything_a_shell_needs_can_be_typed(self):
        typed = set()
        for symbols in (False, True):
            self.keyboard.symbols = symbols
            for label, x, y, w, h, _ in self.keyboard.keys():
                if len(label) == 1:
                    typed.add(label)
        self.assertLessEqual(set("abcdefghijklmnopqrstuvwxyz0123456789-/.|~!@#$%^&*()`_=+[]{};:'\",<>?\\"), typed)

    def test_above_the_keyboard_types_nothing(self):
        self.assertEqual(self.keyboard.press(300, 100), b"")

    def test_a_pressed_key_lights_up_for_a_moment(self):
        self.press("q")
        self.keyboard.dirty = False
        self.assertTrue([k for k in self.keyboard.keys() if k[0] == "q"][0][5])
        self.clock.t += 0.2
        self.keyboard.tick()
        self.assertTrue(self.keyboard.dirty)
        self.assertFalse([k for k in self.keyboard.keys() if k[0] == "q"][0][5])


@unittest.skipUnless(HAVE_PYTE, "pyte is not installed")
class RealBash(unittest.TestCase):
    def shell(self):
        shell = Shell(columns=60, rows=10, command=("/bin/bash", "--norc", "--noprofile"))
        self.addCleanup(shell.close)
        return shell

    def text(self, shell):
        return "\n".join(shell.screen.display)

    def until(self, shell, wanted, seconds=5.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            alive = shell.poll()
            if wanted in self.text(shell) or not alive:
                break
            time.sleep(0.01)
        return self.text(shell)

    def test_a_command_and_its_answer(self):
        shell = self.shell()
        shell.send(b"echo $((6 * 7))\r")
        self.assertIn("\n42", self.until(shell, "\n42"))

    def test_it_is_a_real_terminal_of_the_right_size(self):
        shell = self.shell()
        shell.send(b"tty; stty size; echo TERM=$TERM done\r")
        text = self.until(shell, "done\n")
        self.assertIn("/dev/pts/", text)
        self.assertIn("10 60", text)
        self.assertIn("TERM=linux", text)

    def test_it_has_a_clean_environment_at_home(self):
        os.environ["SDL_VIDEODRIVER"] = "dummy-test"
        self.addCleanup(os.environ.pop, "SDL_VIDEODRIVER")
        shell = self.shell()
        shell.send(b"echo at=$PWD sdl=[$SDL_VIDEODRIVER] end\r")
        text = self.until(shell, "end\n")
        self.assertIn("at=" + os.path.expanduser("~"), text.replace("\n", ""))
        self.assertIn("sdl=[]", text)

    def test_pipes_behave(self):
        shell = self.shell()                          # Python ignores SIGPIPE; with that inherited this would fill the screen with errors
        shell.send(b"yes | head -1; echo status=${PIPESTATUS[0]} end\r")
        self.assertIn("status=141", self.until(shell, "end\n"))

    def test_exit_ends_it(self):
        shell = self.shell()
        shell.send(b"exit\r")
        end = time.monotonic() + 5
        while shell.poll() and time.monotonic() < end:
            time.sleep(0.01)
        self.assertFalse(shell.alive)

    def test_exit_ends_it_with_a_job_still_running(self):
        shell = self.shell()
        shell.send(b"sleep 30 & disown; exit\r")
        end = time.monotonic() + 5
        while shell.poll() and time.monotonic() < end:
            time.sleep(0.01)
        self.assertFalse(shell.alive)

    def test_closing_hangs_up(self):
        shell = self.shell()
        pid = shell.pid
        shell.poll()
        shell.close()
        end = time.monotonic() + 3
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.02)
        self.fail("bash is still there")

    def test_a_flood_of_text_is_read_a_little_at_a_time_and_ctrl_c_stops_it(self):
        shell = self.shell()
        shell.send(b"yes\r")
        time.sleep(0.2)
        started = time.monotonic()
        for _ in range(5):
            shell.poll()
        self.assertLess(time.monotonic() - started, 1.0)
        shell.send(b"\x03echo stopped-now\r")
        self.assertIn("\nstopped-now", self.until(shell, "\nstopped-now", 20))

    def test_nano_style_screens_work(self):
        shell = self.shell()
        shell.send(b"printf '\\033[2J\\033[5;10HMIDDLE\\033[10;1H'\r")
        end = time.monotonic() + 5
        while shell.screen.display[4][9:15] != "MIDDLE" and time.monotonic() < end:
            shell.poll()
            time.sleep(0.01)
        self.assertEqual(shell.screen.display[4][9:15], "MIDDLE")

    def test_a_terminal_question_gets_an_answer(self):
        shell = self.shell()
        shell.send(b"printf '\\033[6n'; read -rs -d R answer; echo; echo \"got${answer:1}R end\"\r")
        self.assertRegex(self.until(shell, "got["), r"got\[\d+;\d+R end")

    def test_a_screen_that_breaks_closes_the_shell_and_not_the_phone(self):
        said = []
        shell = Shell(columns=60, rows=10, log=said.append, command=("/bin/bash", "--norc", "--noprofile"))
        self.addCleanup(shell.close)

        def boom(data):
            raise RuntimeError("pyte")
        shell.stream.feed = boom
        shell.send(b"echo hello\r")
        end = time.monotonic() + 5
        while shell.poll() and time.monotonic() < end:
            time.sleep(0.01)
        self.assertFalse(shell.alive)
        self.assertIn("pyte", said[-1])


class FakeShell:
    def __init__(self):
        self.sent, self.closed, self.ended, self.dirty = [], False, False, False

    def poll(self):
        return not self.ended

    def send(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class FakeSounds:
    def __init__(self):
        self.bongs, self.beeps = [], 0

    def update(self, dial_tone, ringing, digits=""):
        pass

    def bong(self, step):
        self.bongs.append(step)

    def beep(self):
        self.beeps += 1


class Opened(unittest.TestCase):
    def setUp(self):
        self.clock, self.sounds, self.said, self.shells = Clock(), FakeSounds(), [], []
        self.maintenance = Maintenance(self.sounds, self.make, log=self.said.append, clock=self.clock)
        self.maintenance.step(True, True, set(), [])

    def make(self):
        self.shells.append(FakeShell())
        return self.shells[-1]

    def open(self):
        self.maintenance.step(True, True, BOTH, [])
        self.clock.t += config.ARM_SECONDS
        self.maintenance.step(True, True, BOTH, [])
        results = [self.maintenance.step(True, True, set(), [c]) for c in CLOCKWISE]
        self.assertEqual(results, [False, False, False, True])
        return self.shells[-1]

    def key(self, label):
        for name, x, y, w, h, _ in self.maintenance.keyboard.keys():
            if name == label:
                return (x + 5, y + 5)

    def test_a_rising_bong_for_each_step_and_then_the_shell(self):
        self.open()
        self.assertEqual(self.sounds.bongs, [0, 1, 2, 3, 4])
        self.assertTrue(self.maintenance.open)

    def test_keys_reach_the_shell_and_are_not_logged(self):
        shell = self.open()
        self.maintenance.step(True, True, set(), [self.key("s")])
        self.assertEqual(shell.sent, [b"s"])
        self.assertFalse([line for line in self.said if "s" == line.strip()])
        self.assertEqual(self.said, ["maintenance shell open"])

    def test_taps_do_not_type_while_a_call_has_the_screen(self):
        shell = self.open()
        self.maintenance.step(False, True, set(), [self.key("s")])
        self.assertEqual(shell.sent, [])

    def test_bash_ending_closes_it(self):
        shell = self.open()
        shell.ended = True
        self.assertTrue(self.maintenance.step(True, True, set(), []))
        self.assertFalse(self.maintenance.open)

    def test_it_closes_itself_when_nothing_is_typed(self):
        shell = self.open()
        self.clock.t += config.SHELL_IDLE_SECONDS - 1
        self.assertFalse(self.maintenance.step(True, True, set(), []))
        self.clock.t += 1
        self.assertTrue(self.maintenance.step(True, True, set(), []))
        self.assertTrue(shell.closed)
        self.assertFalse(self.maintenance.open)

    def test_typing_keeps_it_open(self):
        self.open()
        self.clock.t += config.SHELL_IDLE_SECONDS - 1
        self.maintenance.step(True, True, set(), [self.key("s")])
        self.clock.t += config.SHELL_IDLE_SECONDS - 1
        self.assertFalse(self.maintenance.step(True, True, set(), []))
        self.assertTrue(self.maintenance.open)

    def test_a_shell_that_cannot_start_is_only_logged(self):
        def fails():
            raise OSError("out of ptys")
        self.maintenance.make_shell = fails
        self.maintenance.step(True, True, BOTH, [])
        self.clock.t += config.ARM_SECONDS
        self.maintenance.step(True, True, BOTH, [])
        self.assertEqual([self.maintenance.step(True, True, set(), [c]) for c in CLOCKWISE], [False] * 4)
        self.assertFalse(self.maintenance.open)
        self.assertIn("out of ptys", self.said[-1])

    def test_it_can_be_opened_again(self):
        self.open().ended = True
        self.maintenance.step(True, True, set(), [])
        self.maintenance.step(True, True, set(), [])              # the buttons are seen to be up
        self.open()
        self.assertEqual(len(self.shells), 2)


@unittest.skipUnless(HAVE_PYTE, "pyte is not installed")
class TheWholeWay(unittest.TestCase):
    def test_tapping_out_exit_on_the_keys_closes_a_real_bash(self):
        clock, said = Clock(), []
        maintenance = Maintenance(FakeSounds(), lambda: Shell(command=("/bin/bash", "--norc", "--noprofile")), log=said.append, clock=clock)
        self.addCleanup(maintenance.close)
        maintenance.step(True, True, set(), [])
        maintenance.step(True, True, BOTH, [])
        clock.t += config.ARM_SECONDS
        maintenance.step(True, True, BOTH, [])
        for spot in CLOCKWISE:
            maintenance.step(True, True, set(), [spot])
        self.assertTrue(maintenance.open)
        for label in ("e", "x", "i", "t", "Enter"):
            key = [k for k in maintenance.keyboard.keys() if k[0] == label][0]
            maintenance.step(True, True, set(), [(key[1] + 5, key[2] + 5)])
        end = time.monotonic() + 5
        while maintenance.open and time.monotonic() < end:
            maintenance.step(True, True, set(), [])
            time.sleep(0.01)
        self.assertFalse(maintenance.open)
        self.assertEqual(said, ["maintenance shell open", "maintenance shell ended"])


class Switches:
    off_hook = False

    def __init__(self):
        self.down = set()

    def poll(self):
        return []

    def key(self, key):
        return []

    def held(self):
        return self.down


class NoCalls:
    def poll(self):
        return []

    def do(self, action):
        pass


class Photos:
    starts = ticks = 0

    def start(self):
        self.starts += 1

    def tick(self):
        self.ticks += 1


class Taps:
    def __init__(self):
        self.next = []

    def poll(self):
        taps, self.next = self.next, []
        return taps


class Box:
    showing, touches, offered = None, 0, None

    def touched(self):
        self.touches += 1

    def tick(self, idle):
        self.offered = idle
        return False

    def take_beep(self):
        return False


class WithThePhone(unittest.TestCase):
    def setUp(self):
        self.clock, self.sounds, self.switches, self.photos, self.taps, self.box = Clock(), FakeSounds(), Switches(), Photos(), Taps(), Box()
        self.shell = FakeShell()
        self.machine = Machine({"left": Party("Amy", "daughter", "amy")}, clock=self.clock, phone_ok=lambda: True)
        self.maintenance = Maintenance(self.sounds, lambda: self.shell, clock=self.clock)
        self.phone = Phone(self.machine, self.switches, NoCalls(), self.sounds, self.photos, clock=self.clock, postbox=self.box,
                           taps=self.taps, maintenance=self.maintenance)
        self.phone.step()

    def arm(self):
        self.switches.down = BOTH
        self.phone.step()
        self.clock.t += config.ARM_SECONDS
        self.phone.step()
        self.switches.down = set()

    def open(self):
        self.arm()
        results = []
        for spot in CLOCKWISE:
            self.taps.next = [spot]
            results.append(self.phone.step())
        return results

    def test_the_screen_changes_when_it_opens_and_the_photos_stop(self):
        self.assertEqual(self.open(), [False, False, False, True])
        self.assertTrue(self.phone.shell_showing)
        ticks = self.photos.ticks
        self.phone.step()
        self.assertEqual(self.photos.ticks, ticks)

    def test_back_to_the_photos_when_it_ends(self):
        self.open()
        starts = self.photos.starts
        self.shell.ended = True
        self.assertTrue(self.phone.step())
        self.assertFalse(self.phone.shell_showing)
        self.assertEqual(self.photos.starts, starts + 1)

    def test_messages_wait_for_it(self):
        self.assertTrue(self.box.offered)
        self.open()
        self.phone.step()
        self.assertFalse(self.box.offered)

    def test_a_tap_of_the_sequence_is_not_a_tap_on_a_message(self):
        self.open()
        self.assertEqual(self.box.touches, 0)

    def test_a_tap_on_a_message_still_counts_otherwise(self):
        self.taps.next = [(300, 300)]
        self.phone.step()
        self.assertEqual(self.box.touches, 1)

    def test_a_call_takes_the_screen_and_gives_it_back(self):
        self.open()
        self.phone._handle(("incoming", Party("Amy", "daughter", "amy")))
        self.assertNotEqual(self.machine.mode, Mode.IDLE)
        self.assertFalse(self.phone.shell_showing)
        self.assertTrue(self.maintenance.open)
        self.phone._handle(("remote_ended",))
        self.clock.t += 60
        for _ in range(3):
            self.phone.step()
            self.clock.t += 60
        self.assertEqual(self.machine.mode, Mode.IDLE)
        self.assertTrue(self.phone.shell_showing)

    def test_the_handset_lifted_during_the_sequence_ends_it(self):
        self.arm()
        self.switches.off_hook = True
        self.taps.next = [TOP_LEFT]
        self.phone.step()
        self.assertFalse(self.maintenance.knock.armed)
        self.assertEqual(self.sounds.bongs, [0])


class HeldButtons(unittest.TestCase):
    def test_held_says_what_is_down_now(self):
        class Pins:
            low = set()

            def is_low(self, pin):
                return pin in self.low
        pins, clock = Pins(), Clock()
        controls = Controls(pins, nc_pins=(), no_pins=(1,), button_pins={"left": 2, "right": 3}, clock=clock)
        self.assertEqual(controls.held(), set())
        pins.low = {2, 3}
        controls.poll()
        clock.t += 1
        controls.poll()
        self.assertEqual(controls.held(), BOTH)

    def test_no_switches_nothing_held(self):
        self.assertEqual(KeyControls().held(), set())


class Bongs(unittest.TestCase):
    def sounds(self):
        made = []

        class Loop:
            def __init__(self, card, pcm, name, log, repeat=True):
                self.name, self.starts, self.stops, self.repeat = name, 0, 0, repeat
                made.append(self)

            def start(self):
                self.starts += 1

            def stop(self):
                self.stops += 1
        return Sounds(enabled=True, handset_card="h", ringer_card="r", make_loop=Loop), made

    def test_each_step_is_higher_and_stays_in_range(self):
        self.assertEqual(sorted(BONG_HZ), list(BONG_HZ))
        self.assertEqual(len(BONG_HZ), LAST_BONG + 1)
        data = bong_pcm(0)
        self.assertEqual(len(data) % 2, 0)
        self.assertGreater(len(data), 1000)

    def test_a_bong_plays_once_and_cuts_off_the_last(self):
        sounds, _ = self.sounds()
        sounds.bong(0)
        sounds.bong(1)
        self.assertEqual(sounds.bongs[0].starts, 1)
        self.assertEqual(sounds.bongs[0].stops, 1)
        self.assertEqual(sounds.bongs[1].starts, 1)
        self.assertFalse(sounds.bongs[0].repeat)

    def test_no_bong_over_the_ringer(self):
        sounds, _ = self.sounds()
        sounds.update(False, True)
        sounds.bong(0)
        self.assertEqual(sounds.bongs[0].starts, 0)

    def test_the_ringer_cuts_off_a_bong(self):
        sounds, _ = self.sounds()
        sounds.bong(2)
        sounds.update(False, True)
        self.assertEqual(sounds.bongs[2].stops, 1)

    def test_no_ringer_card_no_trouble(self):
        Sounds(enabled=False).bong(0)


@unittest.skipUnless(pygame and HAVE_PYTE, "needs pygame and pyte")
class Screen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((W, H))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw
        draw.reset()
        pygame.quit()

    def test_it_draws_text_colours_and_odd_characters_and_clears_the_flags(self):
        import pyte
        from judicom.shell_view import ShellView

        class Fake:
            screen = pyte.Screen(config.SHELL_COLUMNS, config.SHELL_ROWS)
            dirty = True
        pyte.ByteStream(Fake.screen).feed("plain \033[31mred\033[0m \033[7mreverse\033[0m \033[38;5;208mcolour\033[0m 中文 \U0001F600\r\n".encode())
        surface, keyboard = pygame.Surface((W, H)), Keyboard()
        ShellView().draw(surface, Fake, keyboard)
        self.assertFalse(Fake.dirty)
        self.assertFalse(keyboard.dirty)
        self.assertNotEqual(surface.get_at((W // 2 + 30, keyboard.top + 8))[:3], (0, 0, 0))     # a key
        self.assertTrue(any(surface.get_at((x, y))[:3] != (0, 0, 0) for x in range(60) for y in range(config.SHELL_TOP, config.SHELL_TOP + 19)))


if __name__ == "__main__":
    unittest.main()
