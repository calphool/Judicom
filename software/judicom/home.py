"""What the screen shows while no call is going on: the photos, now and then the info screen, and the night clock at night.

    home = Home(PhotoView(...), events, weather)      # used exactly like a PhotoView: start(), tick(), next(), needs_redraw(), draw()

  PHOTOS  the family photos (photo_view.py).  After INFO_EVERY_PHOTOS of them have had their full time: ...
  INFO    the day, the date, the time, the weather and the next events with their countdowns (info_view.py), for INFO_SECONDS;
          then the photos again, starting with a fresh picture
  VERSE   takes turns with INFO: after one run of photos the info screen, after the next a verse (verse_view.py: a Bible page),
          for VERSE_SECONDS.  Every verse comes once before any comes again.  No verses: always the info screen.
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

PHOTOS, INFO, NIGHT, VERSE = "photos", "info", "night", "verse"


def in_night(now, start=config.NIGHT_FROM, end=config.NIGHT_TO):
    t = (now.hour, now.minute)
    return (t >= start or t < end) if start > end else (start <= t < end)


class Home:
    def __init__(self, photos, events=None, weather=None, now=datetime.datetime.now, clock=time.monotonic, log=None, verses=None,
                 verse_seconds=config.VERSE_SECONDS,
                 every=config.INFO_EVERY_PHOTOS, info_seconds=config.INFO_SECONDS, night=(config.NIGHT_FROM, config.NIGHT_TO),
                 awake_file=config.NIGHT_PAUSE_FILE, awake_hours=config.NIGHT_PAUSE_HOURS):
        self.awake_file, self.awake_hours = str(awake_file) if awake_file else None, awake_hours
        self._awake_said = None
        self.photos, self.events, self.weather, self.verses = photos, events, weather, verses
        self.verse_seconds = verse_seconds
        self.verse = None               # the verse on the screen (VERSE)
        self._verse_next = False        # whose turn after the next run of photos: the info screen or a verse
        self.now, self.clock = now, clock
        self.log = log or (lambda msg: None)
        self.every, self.info_seconds, self.night = every, info_seconds, night
        self.mode = None
        self.since = 0.0
        self._base = 0                  # photos.shown when the current run of photos began
        self._drawn = None              # what the info / night screen showed when it was last drawn
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
                self._special()                     # the last photo of the run has had its time: info or verse instead of the next
            elif p.current is None and self.clock() - self.since >= self.every * p.seconds:
                self._special()                     # no photos at all: they still come round
            else:
                p.tick()
        elif self.mode == INFO and self.clock() - self.since >= self.info_seconds:
            self._photos()
        elif self.mode == VERSE and self.clock() - self.since >= self.verse_seconds:
            self._photos()

    def next(self):
        """The space key: the next photo, or from the info screen back to the photos."""
        if self.mode == PHOTOS:
            self.photos.next()
        elif self.mode in (INFO, VERSE):
            self._photos()

    def needs_redraw(self):
        if self.mode == PHOTOS:
            return self.photos.needs_redraw()
        return self._drawn != self._signature()

    def draw(self, surf):
        if self.mode == PHOTOS:
            self.photos.draw(surf)
            return
        from . import info_view                     # pygame: only imported where something is drawn
        now = self.now()
        if self.mode == INFO:
            report = self.weather.current() if self.weather else None
            upcoming = self.events.upcoming(now) if self.events else []
            info_view.draw_info(surf, now, report, upcoming)
        elif self.mode == VERSE:
            from . import verse_view
            verse_view.draw_verse(surf, self.verse)
        else:
            info_view.draw_night(surf, now)
        self._drawn = self._signature()

    # ---- inside
    def _signature(self):
        """What the info / night screen depends on: drawn again when any of it changes (the time once a minute)."""
        if self.mode == VERSE:
            return (self.mode, self.verse)                   # a page: drawn once, it does not show the time
        now = self.now()
        report = self.weather.current() if (self.weather and self.mode == INFO) else None
        return (self.mode, now.date(), now.hour, now.minute, report)

    def _special(self):
        """After a run of photos: the info screen and a verse take turns (always the info screen if there is no verse)."""
        verse = None
        if self._verse_next and self.verses is not None:
            self.verses.refresh()                    # the list may have been fetched from the NAS since
            verse = self.verses.next()
        self._verse_next = not self._verse_next
        if verse is None:
            self._go(INFO)
        else:
            self.verse = verse
            self._go(VERSE)

    def _photos(self):
        self.mode, self.since = PHOTOS, self.clock()
        self.version += 1
        self.photos.start()
        self._base = self.photos.shown - (1 if self.photos.current is not None else 0)    # the fresh picture is the first of the run
        self.log("-> photos")

    def _go(self, mode):
        self.mode, self.since = mode, self.clock()
        self.version += 1
        self._drawn = None
        if mode == INFO and self.events is not None:
            self.events.refresh()                    # the list may have been fetched from the NAS since
        self.log("-> %s" % {INFO: "info screen", NIGHT: "night clock", VERSE: "verse %s" % (self.verse.reference if self.verse else "")}[mode])
