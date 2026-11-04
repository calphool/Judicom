"""The weather for the info screen: Open-Meteo (free, no account), fetched in the background every 30 minutes.

    weather = Weather(log=log); weather.start()       # a background thread keeps it fresh
    now = weather.current()                            # a Report, or None (not fetched yet, or older than WEATHER_STALE)

Nothing here ever holds the screen up: a slow or missing internet connection only means no weather on the info screen.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import config

URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes (what Open-Meteo reports) -> (icon, words)
CODES = {0: ("sun", "Clear"), 1: ("sun", "Mostly clear"), 2: ("partly", "Partly cloudy"), 3: ("cloud", "Cloudy"),
         45: ("fog", "Foggy"), 48: ("fog", "Foggy"),
         51: ("rain", "Light drizzle"), 53: ("rain", "Drizzle"), 55: ("rain", "Drizzle"), 56: ("rain", "Freezing drizzle"),
         57: ("rain", "Freezing drizzle"), 61: ("rain", "Light rain"), 63: ("rain", "Rain"), 65: ("rain", "Heavy rain"),
         66: ("rain", "Freezing rain"), 67: ("rain", "Freezing rain"), 71: ("snow", "Light snow"), 73: ("snow", "Snow"),
         75: ("snow", "Heavy snow"), 77: ("snow", "Snow"), 80: ("rain", "Rain showers"), 81: ("rain", "Rain showers"),
         82: ("rain", "Heavy showers"), 85: ("snow", "Snow showers"), 86: ("snow", "Snow showers"),
         95: ("storm", "Thunderstorms"), 96: ("storm", "Thunderstorms"), 99: ("storm", "Thunderstorms")}


@dataclass(frozen=True)
class Report:
    temp: int                  # degrees F, rounded
    high: int
    low: int
    icon: str                  # sun moon partly cloud fog rain snow storm
    text: str                  # "Partly cloudy"
    fetched: float             # time.monotonic() when it came


def parse(data: dict, fetched: float) -> Report:
    """Open-Meteo's answer -> a Report.  Raises KeyError / ValueError / TypeError on anything unexpected."""
    cur, daily = data["current"], data["daily"]
    icon, text = CODES.get(int(cur["weather_code"]), ("cloud", "Cloudy"))
    if not cur.get("is_day", 1):                     # after dark: a moon instead of the sun
        icon = {"sun": "moon", "partly": "cloud"}.get(icon, icon)
    return Report(round(float(cur["temperature_2m"])), round(float(daily["temperature_2m_max"][0])),
                  round(float(daily["temperature_2m_min"][0])), icon, text, fetched)


def url() -> str:
    query = {"latitude": config.WEATHER_LAT, "longitude": config.WEATHER_LON, "current": "temperature_2m,weather_code,is_day",
             "daily": "temperature_2m_max,temperature_2m_min", "temperature_unit": "fahrenheit",
             "timezone": config.WEATHER_TIMEZONE, "forecast_days": 1}
    return URL + "?" + urllib.parse.urlencode(query)


def fetch(opener=urllib.request.urlopen, clock=time.monotonic) -> Report:
    with opener(urllib.request.Request(url(), headers={"User-Agent": "judicom-photo-frame"}), timeout=20) as resp:
        return parse(json.loads(resp.read().decode("utf-8")), clock())


class Weather:
    def __init__(self, fetcher=fetch, clock=time.monotonic, log=None, every=config.WEATHER_EVERY, stale=config.WEATHER_STALE):
        self.fetcher, self.clock, self.every, self.stale = fetcher, clock, every, stale
        self.log = log or (lambda msg: None)
        self._report = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._failing = False

    def update(self):
        """One fetch (the thread calls this; tests call it directly)."""
        try:
            report = self.fetcher()
        except Exception as exc:                     # noqa: BLE001 - no internet, a changed answer, ...: just no fresh weather
            if not self._failing:
                self.log("weather not available: %s" % exc)
                self._failing = True
            return False
        with self._lock:
            self._report = report
        if self._failing:
            self.log("weather available again")
            self._failing = False
        return True

    def current(self) -> Report | None:
        with self._lock:
            r = self._report
        if r is None or self.clock() - r.fetched > self.stale:
            return None
        return r

    def start(self):
        def run():
            while not self._stop.is_set():
                ok = self.update()
                self._stop.wait(self.every if ok else min(self.every, 300))     # after a failure try again sooner
        threading.Thread(target=run, name="weather", daemon=True).start()

    def stop(self):
        self._stop.set()
