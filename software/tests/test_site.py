"""Tests for the site file (judicom-site.conf: where Judi lives and the names she goes by; not in git).
Each check loads judicom.config in a fresh Python, so the settings of the other tests are not touched.
Run from the software folder:   python3 -m unittest -v"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOFTWARE = Path(__file__).resolve().parents[1]
SHOW = ("import json; from judicom import config as c; print(json.dumps([c.JUDI_NAMES, c.WEATHER_PLACE, c.WEATHER_LAT, "
        "c.WEATHER_LON, c.WEATHER_TIMEZONE]))")


def settings(text):
    with tempfile.TemporaryDirectory() as d:
        site = Path(d) / "site.conf"
        if text is not None:
            site.write_text(text)
        out = subprocess.run([sys.executable, "-c", SHOW], cwd=SOFTWARE, capture_output=True, text=True, check=True,
                             env=dict(os.environ, JUDICOM_SITE=str(site))).stdout
    return json.loads(out)


class Site(unittest.TestCase):
    def test_no_file_no_weather(self):
        self.assertEqual(settings(None), [["Judi"], "", None, None, "auto"])

    def test_the_example_file(self):
        names, place, lat, lon, tz = settings((SOFTWARE / "judicom-site.example.conf").read_text())
        self.assertEqual((names, place, tz), (["Judi"], "Springfield", "auto"))
        self.assertAlmostEqual(lat, 39.8)
        self.assertAlmostEqual(lon, -89.65)

    def test_filled_in(self):
        got = settings("[judi]\nnames = Judi, Grandma ,\n[weather]\nplace = Lakeside\nlatitude = 45.5\nlongitude = -93.25\n"
                       "timezone = America/Chicago\n")
        self.assertEqual(got, [["Judi", "Grandma"], "Lakeside", 45.5, -93.25, "America/Chicago"])

    def test_bad_numbers_or_a_broken_file_mean_no_weather(self):
        self.assertEqual(settings("[weather]\nplace = X\nlatitude = north\nlongitude = 3\n")[2], None)
        self.assertEqual(settings("this is not = an ini [file\n"), [["Judi"], "", None, None, "auto"])


if __name__ == "__main__":
    unittest.main()
