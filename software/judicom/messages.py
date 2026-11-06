"""Messages sent to Judi from the housekeeping website (See Judicom Now): a speech bubble with the sender's face, three beeps.

    /home/joe/messages/<id>.json           waiting to be read: {"id", "from", "text"}.  tools/nas_request.py puts them here.
    /home/joe/messages/read/<id>.json      read, with "read_at": the newest KEEP_READ are kept, so the website can say when.

They are files so that a restart loses nothing.  A message is shown when nothing else is going on, which main.py says by what it
gives tick():

  - a call, or the handset being up, comes first: the message waits (or goes away and comes back afterwards, without beeping again);
  - at night (Home.is_night) it waits for the morning, so nobody is woken by the beeps, and the screen stays dark;
  - two at once: the oldest first, the next when that one is finished with, each with its own beeps;
  - it stays until a touch, a button or the handset.  A touch counts only after TOUCH_GUARD seconds, so that a hand already
    resting on the glass cannot take a message away before it has been seen.

No pygame: it runs (and is tested) anywhere.
"""
import datetime
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import config

MAX_TEXT = 200                     # characters: what fits on the screen in letters Judi can read
MAX_NAME = 40
MAX_WAITING = 20                   # unread messages; more are refused
KEEP_READ = 50
TOUCH_GUARD = 3.0                  # seconds
SCAN_SECONDS = 1.0                 # how often the folder is looked at
ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")


@dataclass(frozen=True)
class Message:
    id: str
    sender: str
    text: str


def clean_text(text):
    """One line of ordinary characters: no control characters, and no emoji (the screen's fonts have none: they show as boxes)."""
    return " ".join("".join(c for c in " ".join(text.split())
                            if ord(c) <= 0xFFFF and not 0xFE00 <= ord(c) <= 0xFE0F and unicodedata.category(c)[0] != "C").split())


def parse(raw):
    """The bytes or text of a message file -> Message.  ValueError if it is not a good one."""
    try:
        data = json.loads(raw)
        message_id, sender, text = data["id"], clean_text(data["from"]), clean_text(data["text"])
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("not a message: %s" % exc) from exc
    if not isinstance(message_id, str) or not ID.match(message_id):
        raise ValueError("a message needs a proper id")
    if not sender or len(sender) > MAX_NAME:
        raise ValueError("a message needs the name of who sent it")
    if not text or len(text) > MAX_TEXT:
        raise ValueError("a message has 1 to %d characters" % MAX_TEXT)
    return Message(message_id, sender, text)


def waiting_files(folder):
    """The unread message files, oldest first (the ids start with the date and time)."""
    try:
        return sorted(p for p in Path(folder).iterdir() if p.suffix == ".json" and not p.name.startswith("."))
    except OSError:
        return []


def write_file(path, text):
    """All of it or nothing: the phone program looks in this folder every second."""
    tmp = path.with_name(".tmp-" + path.name)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def deliver(raw, folder=None):
    """A message arrives (from tools/nas_request.py).  ValueError if it is not a good one or there are too many waiting."""
    folder = Path(config.MESSAGES_DIR if folder is None else folder)
    message = parse(raw)
    folder.mkdir(parents=True, exist_ok=True)
    if len(waiting_files(folder)) >= MAX_WAITING:
        raise ValueError("%d messages are already waiting for Judi" % MAX_WAITING)
    write_file(folder / (message.id + ".json"), json.dumps({"id": message.id, "from": message.sender, "text": message.text}))
    return message


def statuses(folder=None):
    """{id: when it was read, or None while it is waiting}, for the website."""
    folder = Path(config.MESSAGES_DIR if folder is None else folder)
    found = {p.stem: None for p in waiting_files(folder)}
    for p in waiting_files(folder / "read"):
        try:
            found[p.stem] = json.loads(p.read_text(encoding="utf-8")).get("read_at")
        except (OSError, ValueError, AttributeError):
            pass
    return found


class Postbox:
    """What main.py asks each frame.  `can_show`: False keeps messages away for now (at night).

    changed = postbox.tick(idle)    # idle: nothing else needs the screen.  True when the screen must be drawn again
    postbox.showing, postbox.more   # the Message on the screen (or None), and how many more are waiting after it
    postbox.take_beep()             # True once for each message when it first appears
    postbox.touched()               # a finger came down
    postbox.finish()                # a button or the handset: done with the message on the screen
    """

    def __init__(self, folder=None, can_show=lambda: True, clock=time.monotonic, now=datetime.datetime.now, log=None):
        self.folder = Path(config.MESSAGES_DIR if folder is None else folder)
        self.can_show, self.clock, self.now = can_show, clock, now
        self.log = log or (lambda msg: None)
        self.showing = None
        self._drawn = (None, 0)            # what the screen showed at the last tick
        self._since = 0.0
        self._waiting = {}               # file name -> Message, oldest first
        self._scanned = None
        self._beeped = set()               # ids: beeps once only, even if a call sends the message away and it comes back
        self._beep = False
        self._done = set()                 # ids finished with whose file could not be moved (a full card): not shown again

    @property
    def more(self):
        return max(0, len(self._waiting) - (1 if self.showing else 0))

    def tick(self, idle):
        self._scan()
        if self.showing and (not idle or not self.can_show() or self.showing not in self._waiting.values()):
            self.showing = None
        if self.showing is None and idle and self._waiting and self.can_show():
            self.showing = next(iter(self._waiting.values()))
            self._since = self.clock()
            self.log("message from %s: %s" % (self.showing.sender, self.showing.text))
            if self.showing.id not in self._beeped:
                self._beeped.add(self.showing.id)
                self._beep = True
        drawn = (self.showing, self.more if self.showing else 0)            # against the last tick, so finish() counts too
        changed, self._drawn = drawn != self._drawn, drawn
        return changed

    def take_beep(self):
        beep, self._beep = self._beep, False
        return beep

    def touched(self):
        if self.showing and self.clock() - self._since >= TOUCH_GUARD:
            self.finish()

    def finish(self):
        """The message on the screen has been read: it moves to read/, and the next tick() shows the next one."""
        message, self.showing = self.showing, None
        if message is None:
            return
        self.log("message from %s read" % message.sender)
        self._done.add(message.id)
        self._waiting = {name: m for name, m in self._waiting.items() if m != message}
        read = self.folder / "read"
        try:
            read.mkdir(exist_ok=True)
            write_file(read / (message.id + ".json"), json.dumps({"id": message.id, "from": message.sender, "text": message.text,
                                                                  "read_at": self.now().isoformat(timespec="seconds")}))
            (self.folder / (message.id + ".json")).unlink()
            for old in waiting_files(read)[:-KEEP_READ]:
                old.unlink()
        except OSError as exc:
            self.log("(cannot file the message as read: %s)" % exc)

    def _scan(self):
        now = self.clock()
        if self._scanned is not None and now - self._scanned < SCAN_SECONDS:
            return
        self._scanned = now
        found = {}
        for path in waiting_files(self.folder):
            if path.name in self._waiting:
                found[path.name] = self._waiting[path.name]
                continue
            try:
                message = parse(path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError) as exc:
                self.log("(the message %s cannot be shown: %s)" % (path.name, exc))
                try:
                    path.rename(path.with_name(".bad-" + path.name))        # left to look at; not tried again every second
                except OSError:
                    pass
                continue
            if message.id not in self._done:
                found[path.name] = message
        self._waiting = found
