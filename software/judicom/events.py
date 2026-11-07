"""Judi's upcoming events (birthdays, holidays, visits), for the info screen, with a countdown.   python3 -m judicom.events

THE FILE (/home/joe/events.txt on the Judicom, a copy of /home/pi/judicom/events.txt on the NAS), one event per line:

    12-25            | Christmas                   every year
    03-14            | Amy's birthday              every year
    2026-11-08 10:30 | Visit from Amy              once (the time may be 10:30, 14:00, 10:30 AM or 2 PM; it may be left out)
    2026-11-26       | Thanksgiving dinner at Amy's
    4th Thursday of November | Thanksgiving         every year, on a weekday of the month: 1st 2nd 3rd 4th 5th or last
    last Monday of May       | Memorial Day
    Easter                   | Easter              every year (Western Easter Sunday)
    Sunday after 1st Monday of September | Grandparents' Day     the first such weekday after a day of the kind above
    4th Sunday before 12-25  | Advent              counted back from such a day, which itself never counts (also: Fourth Sunday
                                                    Before 12/25 (Christmas)); "2nd Sunday after Easter" counts forward

Lines starting with # and empty lines are skipped; a line that cannot be read is reported and skipped.  An event that happens once
drops off when its day is over.  A yearly event on February 29 is on February 28 in other years.

ON THE SCREEN the next few events, soonest first, each with its date and how far away it is:
    Christmas            December 25  (52 days to go)
    Visit from Amy       Sunday, November 8, 10:30 AM  (5 days to go)    (within the coming week: the weekday too)
    Amy's birthday       Today!                      or   Tomorrow
Days are counted by the calendar (an event tomorrow at 8 AM is "Tomorrow" even at 11 PM tonight).
"""
from __future__ import annotations

import argparse
import datetime
import re
from dataclasses import dataclass

from . import config
from .watched_file import WatchedFile


@dataclass(frozen=True)
class Event:
    title: str
    month: int = 0
    day: int = 0
    year: int | None = None                 # None: every year
    time: datetime.time | None = None
    nth: int = 0                            # a weekday of the month: 1..5, or -1 for the last one (day is then unused) ...
    weekday: int = -1                       # ... and which weekday (0 = Monday)
    easter: bool = False                    # Easter Sunday
    after: int = -1                         # "Sunday after ...": the first such weekday (0 = Monday) after the day above
    before: int = -1                        # "Sunday before ...": the same, going back
    count: int = 1                          # "4th Sunday before ...": how many of them along

    def date_in(self, year: int) -> datetime.date | None:
        """The day of this (yearly) event in a given year; None if that year has no such day (a 5th Monday that is not there)."""
        if self.easter:
            d = easter(year)
        elif self.nth:
            d = nth_weekday(year, self.month, self.weekday, self.nth)
        else:
            d = _yearly(year, self.month, self.day)
        if d is not None and self.after >= 0:
            d += datetime.timedelta(days=(self.after - d.weekday() - 1) % 7 + 1 + 7 * (self.count - 1))   # strictly after: 1..7 days on
        if d is not None and self.before >= 0:
            d -= datetime.timedelta(days=(d.weekday() - self.before - 1) % 7 + 1 + 7 * (self.count - 1))  # strictly before
        return d

    def next_date(self, today: datetime.date) -> datetime.date | None:
        """The day this event next happens on, today included; None for a one-time event that is over."""
        if self.year is not None:
            d = datetime.date(self.year, self.month, self.day)
            return d if d >= today else None
        for year in range(today.year, today.year + 8):                  # (a 5th weekday can skip a few years)
            d = self.date_in(year)
            if d is not None and d >= today:
                return d
        return None


@dataclass(frozen=True)
class Upcoming:
    event: Event
    date: datetime.date
    days: int                                                            # 0 = today

    @property
    def title(self) -> str:
        return self.event.title

    @property
    def when(self) -> str:
        """'Today', 'Tomorrow', 'Sunday, November 8' (within the coming week the weekday too), 'December 25'; with the time if it
        has one."""
        if self.days == 0:
            text = "Today"
        elif self.days == 1:
            text = "Tomorrow"
        elif self.days < 7:
            text = "%s, %s %d" % (self.date.strftime("%A"), self.date.strftime("%B"), self.date.day)
        else:
            text = "%s %d" % (self.date.strftime("%B"), self.date.day)
        if self.event.time is not None:
            text += ", " + clock_text(self.event.time)
        return text

    @property
    def countdown(self) -> str:
        """'Today!', 'Tomorrow', '5 days to go'."""
        if self.days == 0:
            return "Today!"
        if self.days == 1:
            return "Tomorrow"
        return "%d days to go" % self.days


def clock_text(t: datetime.time) -> str:
    """10:30 AM, 2:00 PM, 12:00 PM."""
    hour = t.hour % 12 or 12
    return "%d:%02d %s" % (hour, t.minute, "AM" if t.hour < 12 else "PM")


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
               "december"]
NTH = {"1st": 1, "first": 1, "2nd": 2, "second": 2, "3rd": 3, "third": 3, "4th": 4, "fourth": 4, "5th": 5, "fifth": 5, "last": -1}
RELATIVE = re.compile(r"^(?:(%s)\s+)?(%s)\s+(before|after)\s+(.+)$" % ("|".join(k for k, v in NTH.items() if v > 0), "|".join(WEEKDAYS)),
                      re.IGNORECASE)
RULE = re.compile(r"^(%s)\s+(%s)\s+(?:of|in)\s+(%s)(?:\s+(.+))?$" % ("|".join(NTH), "|".join(WEEKDAYS), "|".join(MONTH_NAMES)),
                  re.IGNORECASE)


def nth_weekday(year: int, month: int, weekday: int, nth: int) -> datetime.date | None:
    """The nth (1..5, or -1: the last) given weekday (0 = Monday) of a month, or None if the month has no 5th one."""
    if nth == -1:
        last = (datetime.date(year + (month == 12), month % 12 + 1, 1) - datetime.timedelta(days=1))
        return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)
    first = datetime.date(year, month, 1)
    d = first + datetime.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    return d if d.month == month else None


def easter(year: int) -> datetime.date:
    """Western Easter Sunday (the Anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7                                  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(year, month, day)


def _yearly(year: int, month: int, day: int) -> datetime.date:
    if month == 2 and day == 29:
        try:
            return datetime.date(year, 2, 29)
        except ValueError:
            return datetime.date(year, 2, 28)
    return datetime.date(year, month, day)


TIME = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?$", re.IGNORECASE)


def parse_time(text: str) -> datetime.time | None:
    """'10:30', '14:00', '10:30 AM', '2 pm' -> a time; raises ValueError for anything else."""
    m = TIME.match(text.strip())
    if not m or (m.group(2) is None and m.group(3) is None):
        raise ValueError("not a time: %r" % text)
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3):
        if not 1 <= hour <= 12:
            raise ValueError("not a time: %r" % text)
        hour = hour % 12 + (12 if m.group(3).lower().startswith("p") else 0)
    return datetime.time(hour, minute)


def parse(text: str, log=None) -> list[Event]:
    log = log or (lambda msg: None)
    events = []
    for n, line in enumerate((text or "").lstrip("﻿").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        when, _, title = (part.strip() for part in line.partition("|"))
        title = " ".join(title.split())
        try:
            if not title:
                raise ValueError("no title after the |")
            after = before = -1
            count = 1
            relative = RELATIVE.match(when)
            if relative:
                weekday = WEEKDAYS.index(relative.group(2).lower())
                count = NTH[relative.group(1).lower()] if relative.group(1) else 1
                after, before = (weekday, -1) if relative.group(3).lower() == "after" else (-1, weekday)
                when = re.sub(r"\s*\([^)]*\)$", "", relative.group(4).strip())       # "12/25 (Christmas)": the note is for people
            rule = RULE.match(when)
            if rule or re.match(r"^easter(?:\s+(.+))?$", when, re.IGNORECASE):
                tail = rule.group(4) if rule else re.match(r"^easter(?:\s+(.+))?$", when, re.IGNORECASE).group(1)
                time = parse_time(tail) if tail else None
                if rule:
                    events.append(Event(title, MONTH_NAMES.index(rule.group(3).lower()) + 1, 0, None, time,
                                        NTH[rule.group(1).lower()], WEEKDAYS.index(rule.group(2).lower()), after=after, before=before,
                                        count=count))
                else:
                    events.append(Event(title, time=time, easter=True, after=after, before=before, count=count))
                continue
            if relative:
                m = re.match(r"^(\d{1,2})[-/](\d{1,2})(?:\s+(.+))?$", when)        # "Monday after 12-25": a yearly date
                if not m:
                    raise ValueError("'... before' and '... after' need a yearly day: 12-25, 4th Thursday of November or Easter")
                _yearly(2024, int(m.group(1)), int(m.group(2)))
                time = parse_time(m.group(3)) if m.group(3) else None
                events.append(Event(title, int(m.group(1)), int(m.group(2)), None, time, after=after, before=before, count=count))
                continue
            m = re.match(r"^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})(?:\s+(.+))?$", when)
            if not m:
                raise ValueError("the date must look like 12-25 (every year), 2026-11-08 (once), "
                                 "4th Thursday of November, last Monday of May, Easter, or 4th Sunday before 12-25")
            year = int(m.group(1)) if m.group(1) else None
            month, day = int(m.group(2)), int(m.group(3))
            if year is None:
                _yearly(2024, month, day)                                 # a leap year: 02-29 is fine
            else:
                datetime.date(year, month, day)
            time = parse_time(m.group(4)) if m.group(4) else None
        except ValueError as exc:
            log("events line %d skipped (%s): %s" % (n, exc, line))
            continue
        events.append(Event(title, month, day, year, time))
    return events


def upcoming(events: list[Event], now: datetime.datetime, count: int = 3) -> list[Upcoming]:
    """The next `count` events from today on, soonest first (and earlier in the day first)."""
    today = now.date()
    found = []
    for e in events:
        d = e.next_date(today)
        if d is not None:
            found.append(Upcoming(e, d, (d - today).days))
    found.sort(key=lambda u: (u.date, u.event.time or datetime.time(0, 0), u.title.lower()))
    return found[:count]


class EventList:
    """The events file, read again when it changes."""

    def __init__(self, path=None, log=None):
        self.path = str(config.EVENTS_FILE if path is None else path)
        self.log = log or (lambda msg: None)
        self.events: list[Event] = []
        self._file = WatchedFile(self.path, self.log)
        self.refresh()

    def refresh(self) -> bool:
        """Read the file again if it changed (no file: no events).  True if it did."""
        changed, text = self._file.read()
        if not changed:
            return False
        self.events = [] if text is None else parse(text, self.log)
        if text is not None:
            self.log("Events: %d from %s" % (len(self.events), self.path))
        return True

    def upcoming(self, now: datetime.datetime, count: int = config.INFO_EVENTS) -> list[Upcoming]:
        return upcoming(self.events, now, count)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.events", description="Show the next events from the events file.")
    ap.add_argument("file", nargs="?", default=str(config.EVENTS_FILE))
    ap.add_argument("-n", type=int, default=10, help="how many (default 10)")
    args = ap.parse_args(argv)
    events = EventList(args.file, print)
    for u in events.upcoming(datetime.datetime.now(), args.n):
        print("  %-32s %s  (%s)" % (u.title, u.when, u.countdown))
    if not events.events:
        print("  (no events in %s)" % args.file)


if __name__ == "__main__":
    main()
