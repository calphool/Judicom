"""Tests for judicom/weather.py (no internet needed).   Run from the software folder:   python3 -m unittest -v"""
import io
import json
import unittest
import urllib.parse

from judicom import weather

ANSWER = {"current": {"temperature_2m": 59.5, "weather_code": 3, "is_day": 1},
          "daily": {"temperature_2m_max": [69.6], "temperature_2m_min": [53.9]}}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Parsing(unittest.TestCase):
    def test_report(self):
        r = weather.parse(ANSWER, 5.0)
        self.assertEqual((r.temp, r.high, r.low, r.icon, r.text), (60, 70, 54, "cloud", "Cloudy"))

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
