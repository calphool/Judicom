"""The screens that take turns between runs of photos (home.py steps through them): the info screen, a verse, the weather, a joke.

Each one is a small object that home.py uses the same way:

    screen.name               "info", "verse", "weather", "joke" (home.mode while it shows)
    screen.seconds            how long it stays up
    screen.ready()            at its turn: get what it will show (the next verse, the latest weather ...).  False: nothing to
                              show now (no verses; no weather report), so its turn goes to the next screen.
    screen.draw(surf, now)    draw it (pygame is only imported here, when drawing)
    screen.signature(now)     what the drawing depends on: drawn again when this changes (the clock: once a minute)
    screen.label()            for the log: "info screen", "verse Psalm 23:1", "weather"

A new screen is a class like these, added to the list home.Home makes.  None of this needs pygame until something is drawn.
"""
import time

from . import config

INFO, VERSE, WEATHER, JOKE = "info", "verse", "weather", "joke"


class InfoScreen:
    """The day, the date, the time and the next events with their countdowns (info_view.py).  Always has something to show."""
    name = INFO

    def __init__(self, events=None, seconds=config.INFO_SECONDS):
        self.events, self.seconds = events, seconds

    def ready(self):
        if self.events is not None:
            self.events.refresh()                    # the list may have been fetched from the NAS since
        return True

    def draw(self, surf, now):
        from . import info_view
        info_view.draw_info(surf, now, self.events.upcoming(now) if self.events else [])

    def signature(self, now):
        return (now.date(), now.hour, now.minute)

    def label(self):
        return "info screen"


class VerseScreen:
    """A verse on a page like an old Bible (verse_view.py), each verse once before any comes again (verses.VerseDeck)."""
    name = VERSE

    def __init__(self, verses=None, seconds=config.VERSE_SECONDS):
        self.verses, self.seconds = verses, seconds
        self.verse = None                            # the one on the screen

    def ready(self):
        if self.verses is None:
            return False
        self.verses.refresh()                        # the list may have been fetched from the NAS since
        self.verse = self.verses.next()
        return self.verse is not None

    def draw(self, surf, now):
        from . import verse_view
        verse_view.draw_verse(surf, self.verse)

    def signature(self, now):
        return self.verse                            # a page: drawn once, it shows no clock

    def label(self):
        return "verse %s" % (self.verse.reference if self.verse else "")


class WeatherScreen:
    """Today's weather and the next days' (weather_view.py), as the report was when its turn came.  Left out without a report
    (no internet for a few hours)."""
    name = WEATHER

    def __init__(self, weather=None, seconds=config.WEATHER_SECONDS):
        self.weather, self.seconds = weather, seconds
        self.report = None                           # the one on the screen

    def ready(self):
        self.report = self.weather.current() if self.weather else None
        return self.report is not None

    def draw(self, surf, now):
        from . import weather_view
        weather_view.draw_weather(surf, now, self.report)

    def signature(self, now):
        return (self.report, now.date())             # ("Tomorrow" changes at midnight)

    def label(self):
        return "weather"


class JokeScreen:
    """A joke (joke_view.py): the setup, then the punchline PUNCHLINE_SECONDS later, on the same screen.  Every joke once before
    any comes again (jokes.JokeDeck)."""
    name = JOKE

    def __init__(self, jokes=None, seconds=config.JOKE_SECONDS, punchline_seconds=config.PUNCHLINE_SECONDS, clock=time.monotonic):
        self.jokes, self.seconds, self.punchline_seconds, self.clock = jokes, seconds, punchline_seconds, clock
        self.joke = None                             # the one on the screen
        self.shown_at = None

    def ready(self):
        if self.jokes is None:
            return False
        self.jokes.refresh()                         # the list may have been fetched from the NAS since
        self.joke, self.shown_at = self.jokes.next(), self.clock()
        return self.joke is not None

    def punchline(self):
        """Is it time for the punchline?"""
        return self.shown_at is not None and self.clock() - self.shown_at >= self.punchline_seconds

    def draw(self, surf, now):
        from . import joke_view
        joke_view.draw_joke(surf, self.joke, self.punchline())

    def signature(self, now):
        return (self.joke, self.punchline())         # drawn again once: when the punchline appears

    def label(self):
        return "joke"

