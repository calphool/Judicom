"""What the screen shows while no call is going on: the photos, now and then the info, verse or weather screen, and the night
clock at night.

    home = Home(PhotoView(...), events, weather)      # used exactly like a PhotoView: start(), tick(), next(), needs_redraw(), draw()

  PHOTOS  the family photos (photo_view.py).  After INFO_EVERY_PHOTOS of them have had their full time, the next screen in
          the rotation INFO -> VERSE -> WEATHER -> INFO ... (screens.py), then the photos again, starting with a fresh picture:
  INFO    the day, the date, the time and the next events with their countdowns (info_view.py), for INFO_SECONDS
  VERSE   a verse (verse_view.py: a Bible page), for VERSE_SECONDS.  Every verse comes once before any comes again.
  WEATHER today's weather and the next days' (weather_view.py), for WEATHER_SECONDS
          A screen with nothing to show (no verses; no weather report: no internet) is skipped, its turn goes to the next one.
  NIGHT   from NIGHT_FROM to NIGHT_TO: a dark screen with only the time and the date (not while the "stay awake" file
          NIGHT_PAUSE_FILE exists and is younger than NIGHT_PAUSE_HOURS: touch /home/joe/judicom-awake)
A call takes the screen whenever one comes (main.py); afterwards start() is called again and picks the right one of the three, so
after a call at night the night clock comes back.  Wall-clock time comes from `now` (datetime.now) and timers from `clock`
(time.monotonic); tests replace both.
"""
import datetime
import os
import time

from . import config
from .screens import INFO, VERSE, WEATHER, InfoScreen, VerseScreen, WeatherScreen

PHOTOS, NIGHT = "photos", "night"
ROTATION = (INFO, VERSE, WEATHER)                # the order the screens take turns in (the names of Home.screens)


def in_night(now, start=config.NIGHT_FROM, end=config.NIGHT_TO):
    t = (now.hour, now.minute)
    return (t >= start or t < end) if start > end else (start <= t < end)


class Home:
    def __init__(self, photos, events=None, weather=None, now=datetime.datetime.now, clock=time.monotonic, log=None, verses=None,
                 verse_seconds=config.VERSE_SECONDS, weather_seconds=config.WEATHER_SECONDS,
                 every=config.INFO_EVERY_PHOTOS, info_seconds=config.INFO_SECONDS, night=(config.NIGHT_FROM, config.NIGHT_TO),
                 awake_file=config.NIGHT_PAUSE_FILE, awake_hours=config.NIGHT_PAUSE_HOURS):
        self.awake_file, self.awake_hours = str(awake_file) if awake_file else None, awake_hours
        self._awake_said = None
        self.photos, self.events, self.weather, self.verses = photos, events, weather, verses
        self.screens = [InfoScreen(events, info_seconds), VerseScreen(verses, verse_seconds), WeatherScreen(weather, weather_seconds)]
        assert tuple(sc.name for sc in self.screens) == ROTATION
        self.screen = None              # the one of them showing now (None: the photos or the night clock)
        self._turn = 0                  # whose turn after the next run of photos: screens[_turn]
        self.now, self.clock = now, clock
        self.log = log or (lambda msg: None)
        self.every, self.night = every, night
        self.mode = None
        self.since = 0.0
        self._base = 0                  # photos.shown when the current run of photos began
        self._drawn = None              # what the screen showed when it was last drawn (not for the photos)
        self.version = 0

    # ---- the PhotoView interface
    def is_night(self, now):
        """Night by the clock, unless the "stay awake" file is there (and not older than awake_hours)."""
        if not in_night(now, *self.night):
            return False
        awake = False
        if self.awake_file:
            try:
                age = time.time() - os.stat(self.awake_file).st_mtime
                awake = age < self.awake_hours * 3600
            except OSError:
                pass
        if awake != self._awake_said:
            if awake or self._awake_said is not None:
                self.log("night clock %s" % ("paused (%s is there)" % self.awake_file if awake else "back"))
            self._awake_said = awake
        return not awake

    def start(self):
        """The screen is (again) ours: the night clock at night, else the photos from a fresh picture."""
        if self.is_night(self.now()):
            self._go(NIGHT)
        else:
            self._photos()

    def tick(self):
        now = self.now()
        night = self.is_night(now)
        if night and self.mode != NIGHT:
            self._go(NIGHT)
        elif not night and self.mode == NIGHT:
            self._photos()
        elif self.mode == PHOTOS:
            p = self.photos
            done = p.shown - self._base
            if done >= self.every and p.current is not None and self.clock() - p.since >= p.seconds:
                self._next_screen()                 # the last photo of the run has had its time: the next screen instead
            elif p.current is None and self.clock() - self.since >= self.every * p.seconds:
                self._next_screen()                 # no photos at all: the screens still come round
            else:
                p.tick()
        elif self.screen is not None and self.clock() - self.since >= self.screen.seconds:
            self._photos()

    def next(self):
        """The space key: the next photo, or from the info / verse / weather screen back to the photos."""
        if self.mode == PHOTOS:
            self.photos.next()
        elif self.screen is not None:
            self._photos()

    def needs_redraw(self):
        if self.mode == PHOTOS:
            return self.photos.needs_redraw()
        return self._drawn != self._signature()

    def draw(self, surf):
        if self.mode == PHOTOS:
            self.photos.draw(surf)
            return
        now = self.now()
        if self.screen is not None:
            self.screen.draw(surf, now)
        else:
            from . import info_view                 # pygame: only imported where something is drawn
            info_view.draw_night(surf, now)
        self._drawn = self._signature()

    # ---- inside
    def _signature(self):
        """What the screen showing depends on: drawn again when any of it changes (the night clock: once a minute)."""
        now = self.now()
        if self.screen is not None:
            return (self.mode, self.screen.signature(now))
        return (self.mode, now.date(), now.hour, now.minute)

    def _next_screen(self):
        """After a run of photos: the next screen in turn that has something to show (the info screen always does)."""
        for _ in self.screens:
            screen = self.screens[self._turn]
            self._turn = (self._turn + 1) % len(self.screens)
            if screen.ready():
                self._go(screen.name)
                return
        self._go(INFO)

    def _photos(self):
        self.mode, self.since, self.screen = PHOTOS, self.clock(), None
        self.version += 1
        self.photos.start()
        self._base = self.photos.shown - (1 if self.photos.current is not None else 0)    # the fresh picture is the first of the run
        self.log("-> photos")

    def _go(self, mode):
        """Show NIGHT or one of the screens (by name; it is ready() already)."""
        self.screen = next((sc for sc in self.screens if sc.name == mode), None)
        self.mode, self.since = mode, self.clock()
        self.version += 1
        self._drawn = None
        self.log("-> %s" % (self.screen.label() if self.screen else "night clock"))
