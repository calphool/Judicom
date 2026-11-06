"""Tests for judicom/weather.py (no internet needed).   Run from the software folder:   python3 -m unittest -v"""
import io
import json
import unittest
import urllib.parse

from judicom import weather

ANSWER = {"current": {"temperature_2m": 59.5, "weather_code": 3, "is_day": 1},
          "daily": {"time": ["2026-11-05", "2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09", "2026-11-10"],
                    "temperature_2m_max": [69.6, 45.2, 54, 64, 67, 60], "temperature_2m_min": [53.9, 36, 35, 42, 47, 44],
                    "weather_code": [3, 73, 0, 61, 95, 45], "precipitation_probability_max": [13, 70, 0, 55, 80, None]}}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Parsing(unittest.TestCase):
    def test_report(self):
        r = weather.parse(ANSWER, 5.0)
        self.assertEqual((r.temp, r.high, r.low, r.icon, r.text), (60, 70, 54, "cloud", "Cloudy"))

    def test_the_next_five_days(self):
        r = weather.parse(ANSWER, 5.0)
        self.assertEqual(r.rain, 13)
        self.assertEqual([(d.date.day, d.high, d.low, d.icon, d.rain) for d in r.days],
                         [(6, 45, 36, "snow", 70), (7, 54, 35, "sun", 0), (8, 64, 42, "rain", 55), (9, 67, 47, "storm", 80),
                          (10, 60, 44, "fog", None)])

    def test_a_forecast_with_a_gap_keeps_the_days_before_it(self):
        daily = dict(ANSWER["daily"], temperature_2m_max=[69.6, 45, None, 64, 67, 60])
        r = weather.parse(dict(ANSWER, daily=daily), 0)
        self.assertEqual((r.temp, len(r.days)), (60, 1))
        old = {"current": ANSWER["current"], "daily": {"temperature_2m_max": [69.6], "temperature_2m_min": [53.9]}}
        self.assertEqual((weather.parse(old, 0).days, weather.parse(old, 0).rain), ((), None))      # today only: still a report

    def test_night_and_unknown_codes(self):
        night = dict(ANSWER, current={"temperature_2m": 40, "weather_code": 0, "is_day": 0})
        self.assertEqual(weather.parse(night, 0).icon, "moon")
        odd = dict(ANSWER, current={"temperature_2m": 40, "weather_code": 42})
        self.assertEqual((weather.parse(odd, 0).icon, weather.parse(odd, 0).text), ("cloud", "Cloudy"))

    def test_every_code_has_an_icon_the_screen_draws(self):
        for code, (icon, text) in weather.CODES.items():
            self.assertIn(icon, {"sun", "moon", "partly", "cloud", "fog", "rain", "snow", "storm"})
            self.assertTrue(text)

    def test_url_asks_for_springfield_in_fahrenheit(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(weather.url()).query)
        self.assertEqual(q["temperature_unit"], ["fahrenheit"])
        self.assertEqual(q["timezone"], ["America/Chicago"])
        self.assertAlmostEqual(float(q["latitude"][0]), 39.80)
        self.assertEqual(q["forecast_days"], ["6"])                             # today and the next five
        self.assertIn("precipitation_probability_max", q["daily"][0])

    def test_fetch(self):
        def opener(request, timeout):
            self.assertIn("api.open-meteo.com", request.full_url)
            return io.BytesIO(json.dumps(ANSWER).encode())
        self.assertEqual(weather.fetch(opener, lambda: 7.0).temp, 60)


class Freshness(unittest.TestCase):
    def setUp(self):
        self.clock, self.logged = Clock(), []
        self.answers = []

        def fetcher():
            a = self.answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return weather.parse(a, self.clock())
        self.w = weather.Weather(fetcher, self.clock, self.logged.append, every=1800, stale=3 * 3600)

    def test_none_until_fetched(self):
        self.assertIsNone(self.w.current())
        self.answers.append(ANSWER)
        self.assertTrue(self.w.update())
        self.assertEqual(self.w.current().temp, 60)

    def test_failures_keep_the_last_report_until_it_is_stale(self):
        self.answers += [ANSWER, OSError("Network is unreachable"), OSError("Network is unreachable")]
        self.w.update()
        self.clock.t += 3600
        self.assertFalse(self.w.update())
        self.assertEqual(self.w.current().temp, 60)                   # an hour old: still shown
        self.clock.t += 3 * 3600
        self.w.update()
        self.assertIsNone(self.w.current())                            # 4 hours old: not shown
        self.assertEqual(len(self.logged), 1)                         # the failure is said once
        self.answers.append(ANSWER)
        self.w.update()
        self.assertIn("available again", self.logged[-1])

    def test_a_strange_answer_is_a_failure_not_a_crash(self):
        self.answers.append({"something": "else"})
        self.assertFalse(self.w.update())
        self.assertIsNone(self.w.current())


if __name__ == "__main__":
    unittest.main()
