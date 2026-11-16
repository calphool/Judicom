"""Which parts of the Judicom are on: set on the NAS's housekeeping website (Features), and read here.

The master is /home/pi/judicom/features.txt on the NAS.  The website hands each change straight to the Judicom (tools/
nas_request.py "features"), and judicom.sync fetches it every 10 minutes as well (for a change made while the Judicom was
off).  The Judicom's copy is FEATURES_FILE:

    # Which parts of the Judicom are on ...
    info = on
    jokes = off
    night_from = 21:00
    night_to = 06:00

A part not named, or no file at all, is as it always was: on, except those in OFF_UNLESS_SET (new ways of doing something,
off until turned on).  The night hours (TIMES: the
night clock, and when messages wait for the morning) are 24-hour times; not named, the usual 9 PM to 6 AM.

    features = Features()            # reads FEATURES_FILE again whenever it changes
    features.on("weather")           # True / False
No pygame here.
"""
from . import config
from .watched_file import WatchedFile

FEATURES = (     # (name, what the website calls it, what it is)
    ("info", "Upcoming events", "The day, the date, the time, and the birthdays, holidays and visits coming up with their "
                                "countdowns, now and then between the photos."),
    ("verses", "Bible verses", "A verse on a page like an old Bible, now and then between the photos."),
    ("weather", "Weather", "Today's weather and the next days', now and then between the photos."),
    ("jokes", "Jokes", "A joke and, a moment later, its punchline, now and then between the photos."),
    ("night", "Night clock", "A dark screen with only the time and the date at night.  Off: the photos all night."),
    ("games", "Hidden games", "The games on the hidden menu (the maintenance shell is always there)."),
    ("touch_calls", "Call by touch", "With the handset up, a button on the screen for everyone in the caller list, with their "
                                     "picture; the two real buttons then call nobody.  Off: the two buttons, with arrows "
                                     "pointing to them."),
)
OFF_UNLESS_SET = {"touch_calls"}
NAMES = tuple(name for name, _, _ in FEATURES)
TIMES = {"night_from": config.NIGHT_FROM, "night_to": config.NIGHT_TO}      # (hour, minute)
HEADER = ("# Which parts of the Judicom are on.  The master is /home/pi/judicom/features.txt on the NAS: change it on the\n"
          "# housekeeping website (Features).  A part not named here is on.\n")
WORDS = {"on": True, "yes": True, "off": False, "no": False}
RETIRED = {"events"}            # parts that were once switched on their own: a line for one is passed over quietly


def read_time(word):
    """'21:00' or '6:30' -> (21, 0) / (6, 30); None if it is not a time of day."""
    hour, sep, minute = word.partition(":")
    if not (sep and hour.isdigit() and minute.isdigit() and len(minute) == 2 and len(hour) <= 2):
        return None
    hour, minute = int(hour), int(minute)
    return (hour, minute) if hour < 24 and minute < 60 else None


def time_words(hm):
    """(21, 0) -> '9:00 PM'."""
    hour, minute = hm
    return "%d:%02d %s" % ((hour - 1) % 12 + 1, minute, "AM" if hour < 12 else "PM")


def parse(text, problem=None):
    """{name: on?, night_from: (h, m), ...} from the file's text.  Lines it cannot use are told to problem() and left out (so
    those parts stay on, and those hours as usual).  Night hours that start and end at the same time are left out too."""
    problem = problem or (lambda msg: None)
    states = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, word = (part.strip().lower() for part in line.partition("="))
        if name in RETIRED:
            continue
        if sep and name in TIMES and read_time(word):
            states[name] = read_time(word)
            continue
        if not sep or name not in NAMES or word not in WORDS:
            problem("line %d: %r is not '<part> = on', '<part> = off' or '<hours> = 21:00' (parts: %s; hours: %s)"
                    % (n, line, ", ".join(NAMES), ", ".join(TIMES)))
            continue
        states[name] = WORDS[word]
    if night(states)[0] == night(states)[1]:
        problem("the night starts and ends at the same time (%s): the usual hours instead" % time_words(night(states)[0]))
        for name in TIMES:
            states.pop(name, None)
    return states


def is_on(states, name):
    """Is this part on in these states (as it always was, if they do not say)?"""
    return states.get(name, name not in OFF_UNLESS_SET)


def turned_off(states):
    """The parts that are usually on and have been turned off."""
    return [n for n in NAMES if n not in OFF_UNLESS_SET and not is_on(states, n)]


def summary(states):
    """For the logs: what is not as usual ("off: jokes; on: touch_calls"), or "as usual"."""
    on = [n for n in NAMES if n in OFF_UNLESS_SET and is_on(states, n)]
    parts = (["off: " + ", ".join(turned_off(states))] if turned_off(states) else []) + (["on: " + ", ".join(on)] if on else [])
    return "; ".join(parts) or "as usual"


def night(states):
    """(from, to) of the night hours in these states."""
    return tuple(states.get(name, default) for name, default in TIMES.items())


def render(states):
    """The file's text for these states (every part named, in the website's order, then the night hours)."""
    return HEADER + "".join("%s = %s\n" % (name, "on" if is_on(states, name) else "off") for name in NAMES) + "".join(
        "%s = %02d:%02d\n" % ((name,) + tuple(states.get(name, default))) for name, default in TIMES.items())


def check(text):
    """The states in a features file handed over by the NAS; raises ValueError if any line is not right (then nothing changes)."""
    problems = []
    states = parse(text, problems.append)
    if problems:
        raise ValueError(problems[0])
    return states


def store(states, path=None):
    """Writes the Judicom's copy in one step (judicom.sync.store).  True if it changed."""
    from .sync import store as store_file
    return store_file(render(states)[len(HEADER):], str(config.FEATURES_FILE if path is None else path), HEADER)


class Features:
    def __init__(self, path=None, log=None):
        self.log = log or (lambda msg: None)
        self.file = WatchedFile(config.FEATURES_FILE if path is None else path, self.log)
        self.states = {}

    def on(self, name):
        self._refresh()
        return is_on(self.states, name)

    def night(self):
        """(from, to): the night hours, each (hour, minute)."""
        self._refresh()
        return night(self.states)

    def _refresh(self):
        changed, text = self.file.read()
        if changed:
            self.states = parse(text or "", lambda msg: self.log("features file: " + msg))
            self.log("features: %s; night %s to %s" % (summary(self.states), *(time_words(t) for t in night(self.states))))
