"""Judi's upcoming events (birthdays, holidays, visits), for the info screen, with a countdown.   python3 -m judicom.events

THE FILE (/home/joe/events.txt on the Judicom, a copy of /home/pi/judicom/events.txt on the NAS), one event per line:

    12-25            | Christmas                   every year
    03-14            | Amy's birthday              every year
    2026-11-08 10:30 | Visit from Amy              once (the time may be 10:30, 14:00, 10:30 AM or 2 PM; it may be left out)
    2026-11-26       | Thanksgiving dinner at Amy's

Lines starting with # and empty lines are skipped; a line that cannot be read is reported and skipped.  An event that happens once
drops off when its day is over.  A yearly event on February 29 is on February 28 in other years.

ON THE SCREEN the next few events, soonest first, each with its date and how far away it is:
    Christmas            December 25  (52 days to go)
    Visit from Amy       Sunday, 10:30 AM  (5 days to go)          (within the coming week: the weekday)
    Amy's birthday       Today!                      or   Tomorrow
Days are counted by the calendar (an event tomorrow at 8 AM is "Tomorrow" even at 11 PM tonight).
"""
from __future__ import annotations

import argparse
import datetime
import re
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Event:
    title: str
    month: int
    day: int
    year: int | None = None                 # None: every year
    time: datetime.time | None = None

    def next_date(self, today: datetime.date) -> datetime.date | None:
        """The day this event next happens on, today included; None for a one-time event that is over."""
        if self.year is not None:
            d = datetime.date(self.year, self.month, self.day)
            return d if d >= today else None
        for year in (today.year, today.year + 1):
            d = _yearly(year, self.month, self.day)
            if d >= today:
                return d
        return None                                                      # (cannot happen)


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
        """'Today', 'Tomorrow', 'Sunday' (within the coming week the weekday says it), 'December 25'; with the time if it has one."""
        if self.days == 0:
            text = "Today"
        elif self.days == 1:
            text = "Tomorrow"
        elif self.days < 7:
            text = self.date.strftime("%A")
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
            m = re.match(r"^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})(?:\s+(.+))?$", when)
            if not m:
                raise ValueError("the date must look like 12-25 (every year) or 2026-11-08 (once)")
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
        self._stamp = "unread"
        self.refresh()

    def refresh(self) -> bool:
        import os
        try:
            st = os.stat(self.path)
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            stamp = None
        if stamp == self._stamp:
            return False
        self._stamp = stamp
        if stamp is None:
            self.events = []
            return True
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                self.events = parse(fh.read(), self.log)
        except OSError as exc:
            self.log("cannot read %s: %s" % (self.path, exc))
            return False
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
