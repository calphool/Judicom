"""Tests for judicom/events.py.   Run from the software folder:   python3 -m unittest -v"""
import datetime
import tempfile
import unittest
from pathlib import Path

from judicom.events import Event, EventList, clock_text, parse, parse_time, upcoming

NOW = datetime.datetime(2026, 11, 3, 21, 30)          # a Tuesday evening

FILE = """# Judi's events
12-25            | Christmas
03-14            | Amy's birthday
2026-11-08 10:30 | Visit from Amy
2026-11-04 2 PM  | Hair appointment
2026-10-31       | Halloween party
11-03            | Clark's birthday
"""


class Parsing(unittest.TestCase):
    def test_lines(self):
        events = parse(FILE)
        self.assertEqual(len(events), 6)
        self.assertIn(Event("Christmas", 12, 25), events)
        self.assertIn(Event("Visit from Amy", 11, 8, 2026, datetime.time(10, 30)), events)
        self.assertIn(Event("Hair appointment", 11, 4, 2026, datetime.time(14, 0)), events)

    def test_times(self):
        for text, t in [("10:30", (10, 30)), ("14:00", (14, 0)), ("10:30 AM", (10, 30)), ("2 pm", (14, 0)),
                        ("12 PM", (12, 0)), ("12:15 am", (0, 15)), ("9:05p.m.", (21, 5))]:
            with self.subTest(text=text):
                self.assertEqual(parse_time(text), datetime.time(*t))
        for bad in ("noon", "25:00", "13 PM", "10"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_time(bad)

    def test_bad_lines_are_reported_and_skipped(self):
        logged = []
        events = parse("Christmas | 12-25\n02-30 | No such day\n12-25 |\n2026-11-08 noon | Lunch\n12-25 | ok\n", logged.append)
        self.assertEqual([e.title for e in events], ["ok"])
        self.assertEqual(len(logged), 4)
        self.assertIn("line 1", logged[0])

    def test_clock_text(self):
        self.assertEqual(clock_text(datetime.time(10, 30)), "10:30 AM")
        self.assertEqual(clock_text(datetime.time(0, 5)), "12:05 AM")
        self.assertEqual(clock_text(datetime.time(12, 0)), "12:00 PM")
        self.assertEqual(clock_text(datetime.time(14, 0)), "2:00 PM")


class Countdown(unittest.TestCase):
    def test_soonest_first_with_countdowns(self):
        up = upcoming(parse(FILE), NOW, 4)
        self.assertEqual([(u.title, u.countdown) for u in up],
                         [("Clark's birthday", "Today!"), ("Hair appointment", "Tomorrow"),
                          ("Visit from Amy", "5 days to go"), ("Christmas", "52 days to go")])

    def test_when(self):
        up = {u.title: u for u in upcoming(parse(FILE), NOW, 10)}
        self.assertEqual(up["Christmas"].when, "December 25")
        self.assertEqual(up["Visit from Amy"].when, "Sunday, November 8, 10:30 AM")
        later = upcoming(parse("2026-11-20 10:30 | Dentist\n"), NOW)[0]
        self.assertEqual((later.when, later.countdown), ("November 20, 10:30 AM", "17 days to go"))
        self.assertEqual(up["Hair appointment"].when, "Tomorrow, 2:00 PM")
        self.assertEqual(up["Clark's birthday"].when, "Today")
        self.assertEqual(up["Amy's birthday"].when, "March 14")
        self.assertEqual(up["Amy's birthday"].countdown, "131 days to go")

    def test_a_past_one_time_event_drops_off_and_yearly_ones_come_round(self):
        titles = [u.title for u in upcoming(parse(FILE), NOW, 10)]
        self.assertNotIn("Halloween party", titles)
        up = upcoming(parse("11-02 | Yesterday's birthday\n"), NOW)
        self.assertEqual((up[0].date, up[0].countdown), (datetime.date(2027, 11, 2), "364 days to go"))

    def test_calendar_days_not_hours(self):
        late = datetime.datetime(2026, 11, 3, 23, 59)
        self.assertEqual(upcoming(parse("2026-11-04 08:00 | Breakfast\n"), late)[0].countdown, "Tomorrow")

    def test_leap_day(self):
        up = upcoming(parse("02-29 | Leap day birthday\n"), datetime.datetime(2027, 1, 1))
        self.assertEqual(up[0].date, datetime.date(2027, 2, 28))
        up = upcoming(parse("02-29 | Leap day birthday\n"), datetime.datetime(2028, 1, 1))
        self.assertEqual(up[0].date, datetime.date(2028, 2, 29))

    def test_same_day_earlier_time_first(self):
        up = upcoming(parse("2026-11-05 15:00 | Later\n2026-11-05 09:00 | Earlier\n"), NOW)
        self.assertEqual([u.title for u in up], ["Earlier", "Later"])

    def test_nothing(self):
        self.assertEqual(upcoming([], NOW), [])


class File(unittest.TestCase):
    def test_reads_and_rereads(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.txt"
            ev = EventList(path)
            self.assertEqual(ev.events, [])
            path.write_text("12-25 | Christmas\n")
            self.assertTrue(ev.refresh())
            self.assertEqual(ev.upcoming(NOW)[0].title, "Christmas")
            self.assertFalse(ev.refresh())


if __name__ == "__main__":
    unittest.main()


class Holidays(unittest.TestCase):
    """The moving holidays, checked against the real calendar."""

    def dates(self, line, years):
        e = parse(line + " | x\n")[0]
        return [e.date_in(y) for y in years]

    def test_easter(self):
        from judicom.events import easter
        known = {2024: (3, 31), 2025: (4, 20), 2026: (4, 5), 2027: (3, 28), 2028: (4, 16), 2030: (4, 21), 2038: (4, 25)}
        for year, (m, d) in known.items():
            with self.subTest(year=year):
                self.assertEqual(easter(year), datetime.date(year, m, d))

    def test_weekday_rules(self):
        cases = [("4th Thursday of November", {2024: 28, 2025: 27, 2026: 26, 2027: 25}),      # Thanksgiving
                 ("last Monday of May", {2024: 27, 2025: 26, 2026: 25, 2027: 31}),             # Memorial Day
                 ("1st Monday of September", {2024: 2, 2025: 1, 2026: 7}),                     # Labor Day
                 ("3rd Monday of January", {2025: 20, 2026: 19, 2027: 18}),                    # Martin Luther King Jr. Day
                 ("2nd Sunday of May", {2025: 11, 2026: 10, 2027: 9}),                         # Mother's Day
                 ("third sunday in june", {2025: 15, 2026: 21})]                               # Father's Day (any capitals, "in")
        for rule, days in cases:
            for year, day in days.items():
                with self.subTest(rule=rule, year=year):
                    self.assertEqual(parse(rule + " | x\n")[0].date_in(year).day, day)

    def test_a_missing_5th_weekday_skips_to_a_year_that_has_one(self):
        e = parse("5th Friday of February | Rare\n")[0]
        self.assertIsNone(e.date_in(2026))
        self.assertEqual(e.date_in(2036), datetime.date(2036, 2, 29))         # February 2036 has five Fridays
        self.assertIsNone(e.next_date(datetime.date(2026, 1, 1)))              # more than 8 years away: not listed, no hang

    def test_rules_with_a_time_and_in_the_countdown(self):
        up = upcoming(parse("4th Thursday of November 1 PM | Thanksgiving dinner\nEaster | Easter\n"), NOW)
        self.assertEqual((up[0].title, up[0].when, up[0].countdown), ("Thanksgiving dinner", "November 26, 1:00 PM", "23 days to go"))
        self.assertEqual(up[1].date, datetime.date(2027, 3, 28))

    def test_grandparents_day_the_sunday_after_labor_day(self):
        e = parse("Sunday after 1st Monday of September | Grandparents' Day\n")[0]
        known = {2024: 8, 2025: 7, 2026: 13, 2027: 12, 2030: 8}                  # (2025: Labor Day Sept 1, Sunday Sept 7)
        for year, day in known.items():
            with self.subTest(year=year):
                self.assertEqual(e.date_in(year), datetime.date(year, 9, day))

    def test_after_is_strictly_after(self):
        e = parse("Monday after 1st Monday of September | Next Monday\n")[0]
        self.assertEqual(e.date_in(2026), datetime.date(2026, 9, 14))            # a week after Labor Day, not the same day
        self.assertEqual(parse("Monday after Easter | Easter Monday\n")[0].date_in(2026), datetime.date(2026, 4, 6))
        self.assertEqual(parse("Friday after 4th Thursday of November | Black Friday\n")[0].date_in(2026),
                         datetime.date(2026, 11, 27))
        self.assertEqual(parse("Sunday after 12-25 | Sunday after Christmas\n")[0].date_in(2026), datetime.date(2026, 12, 27))

    def test_bad_rules_are_reported(self):
        logged = []
        self.assertEqual(parse("6th Monday of May | x\n4th Funday of November | y\nlast Monday of Smarch | z\n", logged.append), [])
        self.assertEqual(len(logged), 3)

    def test_the_example_list_reads_cleanly(self):
        logged = []
        example = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "events.example.txt"
        events = parse(example.read_text(), logged.append)
        self.assertEqual(logged, [])
        self.assertGreaterEqual(len(events), 21)
        self.assertTrue(all(e.next_date(NOW.date()) for e in events))      # every one of them comes round
