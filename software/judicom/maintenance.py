"""The hidden menu and what is behind it: the maintenance shell, a way in on the Judicom itself when SSH cannot help (a new
Wi-Fi network, say), and the games.

To open the menu, with the handset on the hook and nothing going on:
  1. hold both buttons for ARM_SECONDS: a bong, and they can be let go;
  2. tap the four corners clockwise from the top left, each within KNOCK_SECONDS of the last: a higher bong each time.
Anything else (a wrong tap, too long a wait, lifting the handset, a call) ends it, without a sound.

The menu (judicom/menu.py) has a button for the shell and one for each game; touch one to open it.  The menu and the games
close when the handset is lifted or a call comes in, and the menu after MENU_SECONDS untouched.

The shell is an ordinary bash (judicom/shell.py) with a touch keyboard (judicom/keyboard.py).  "exit" goes back to the photos, and
so do SHELL_IDLE_SECONDS without a key, so that it is never left on Judi's screen.  The phone goes on working underneath: a call or
the handset takes the screen, and the shell is still there afterwards.  Messages wait until it has closed.

What is typed is never logged: it may be a password.

No pygame: it runs (and is tested) anywhere.
"""
import time

from . import config
from .keyboard import Keyboard
from .menu import Menu

BOTH = {"left", "right"}
CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))           # clockwise from the top left, as (right?, bottom?)
SHELL = "Shell"                                      # the menu's button for the shell
LAST_BONG = len(CORNERS)


def corner(x, y, size=config.CORNER_PX):
    """(right?, bottom?) of the corner this spot of the upright picture is in, or None."""
    across = 0 if x < size else 1 if x >= config.SCREEN_W - size else None
    down = 0 if y < size else 1 if y >= config.SCREEN_H - size else None
    return None if across is None or down is None else (across, down)


class Knock:
    """Follows the sequence.  update() -> the number of the bong to play now (0 = armed .. LAST_BONG = all four corners), or None."""

    def __init__(self, clock=time.monotonic, arm_seconds=config.ARM_SECONDS, knock_seconds=config.KNOCK_SECONDS):
        self.clock, self.arm_seconds, self.knock_seconds = clock, arm_seconds, knock_seconds
        self.corners = None                          # how many are done; None while not armed
        self._deadline = self._held_since = None
        self._let_go = False                         # the buttons must come up before they can arm it (again)

    @property
    def armed(self):
        return self.corners is not None

    def reset(self):
        self.corners = self._deadline = self._held_since = None
        self._let_go = False

    def update(self, ready, both_held, taps):
        now = self.clock()
        if not both_held:
            self._held_since, self._let_go = None, True
        if not ready:
            self.reset()
            return None
        if not self.armed:
            if both_held and self._let_go:
                if self._held_since is None:
                    self._held_since = now
                elif now - self._held_since >= self.arm_seconds:
                    self.corners, self._deadline, self._let_go = 0, now + self.knock_seconds, False
                    return 0
            return None
        if now >= self._deadline:
            self.reset()
            return None
        for x, y in taps:
            if corner(x, y) != CORNERS[self.corners]:
                self.reset()
                return None
            self.corners += 1
            self._deadline = now + self.knock_seconds
            done = self.corners
            if done == LAST_BONG:
                self.reset()
            return done
        return None


class Maintenance:
    """What main.py asks each frame: step() -> True when the menu, the shell or a game has just opened or closed (the screen must
    be drawn again)."""

    def __init__(self, sounds, make_shell, log=None, clock=time.monotonic, idle_seconds=config.SHELL_IDLE_SECONDS, games=None):
        """games: {menu label: make()} for each game, make() giving a new session like game.Session: step(held) -> keep open?,
        steps (0: nothing new to draw), draw() -> its small canvas, close()."""
        self.sounds, self.make_shell, self.clock, self.idle_seconds = sounds, make_shell, clock, idle_seconds
        self.games = dict(games or {})
        self.log = log or (lambda msg: None)
        self.knock = Knock(clock)
        self.keyboard = None
        self.menu = None
        self.shell = None
        self.game = self.game_name = None
        self._typed = None

    @property
    def open(self):
        """The menu, the shell or a game is open."""
        return self.menu is not None or self.shell is not None or self.game is not None

    @property
    def busy(self):
        """The screen's taps are ours: not for messages."""
        return self.open or self.knock.armed

    @property
    def needs_draw(self):
        return self.shell is not None and (self.shell.dirty or self.keyboard.dirty)

    def step(self, idle, on_hook, held, taps):
        """idle: nothing else needs the screen.  held: the names of the buttons down now.  taps: where fingers came down."""
        if self.game is not None:
            if not (idle and on_hook):
                self.close_game("ended: the handset was lifted" if not on_hook else "ended: a call")
                return True
            if not self.game.step(held):
                self.close_game("closed: no new game")
                return True
            return False
        if self.menu is not None:
            if not (idle and on_hook):
                self.close_menu("closed: the handset was lifted" if not on_hook else "closed: a call")
                return True
            for x, y in taps:
                choice = self.menu.press(x, y)
                if choice is None:
                    continue
                self.menu = None
                if choice == SHELL:
                    self._open()
                elif choice in self.games:
                    self._open_game(choice)
                else:
                    self.log("menu closed")
                return True
            if self.menu.idle:
                self.close_menu("closed: nothing touched")
                return True
            return False
        if self.shell is None:
            bong = self.knock.update(idle and on_hook, BOTH <= set(held), taps)
            if bong is None:
                return False
            self.sounds.bong(bong)
            if bong != LAST_BONG:
                return False
            self.menu = Menu([SHELL] + list(self.games), self.clock)
            self.log("menu open")
            return True
        if not self.shell.poll():
            self.close("ended")
            return True
        self.keyboard.tick()
        for x, y in taps if idle else ():
            data = self.keyboard.press(x, y)
            self._typed = self.clock()
            if data:
                self.shell.send(data)
        if self.clock() - self._typed >= self.idle_seconds:
            self.close("closed: nothing typed for %d minutes" % (self.idle_seconds // 60))
            return True
        return False

    def _open(self):
        try:
            self.shell = self.make_shell()
        except OSError as exc:
            self.log("(the maintenance shell cannot start: %s)" % exc)
            return False
        self.keyboard = Keyboard(self.clock)
        self._typed = self.clock()
        self.log("maintenance shell open")
        return True

    def _open_game(self, name):
        try:
            self.game = self.games[name]()
        except Exception as exc:                        # noqa: BLE001 - the phone is what matters: it goes on without the game
            self.log("(%s cannot start: %s)" % (name, exc))
            return False
        self.game_name = name
        self.log("%s open" % name)
        return True

    def close_menu(self, why="closed"):
        if self.menu is not None:
            self.menu = None
            self.log("menu %s" % why)

    def close_game(self, why="closed"):
        if self.game is not None:
            self.game.close()
            self.game = None
            self.log("%s %s" % (self.game_name, why))

    def close(self, why="closed"):
        self.close_menu()
        self.close_game()
        if self.shell is not None:
            self.shell.close()
            self.shell = self.keyboard = None
            self.log("maintenance shell %s" % why)
