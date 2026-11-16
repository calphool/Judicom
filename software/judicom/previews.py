"""Little pictures of what each part of the Judicom looks like, for the housekeeping website's Features page.

    python3 -m judicom.previews LISTS OUT       LISTS: the folder with events.txt, verses.txt, jokes.txt, contacts.txt and people/ (the NAS's masters)
                                                OUT:   where to write info.png, events.png ... (one per judicom/features.py part)

Each is drawn by the Judicom's own drawing code, from the same lists, at half the screen's size (300 x 512): the info screen
with the events coming up now, the first verse, the first joke with its punchline, the night clock at this minute, the hidden
menu, and the "Who would you like to call?" screen with a touch button for each caller.  The weather is an example (the NAS does not fetch a forecast).  A separate program, so the website itself never loads
pygame; it runs this again when the pictures are a few minutes old.
"""
import argparse
import datetime
import os
import sys
import time
from pathlib import Path

from . import config, features

SIZE = (config.SCREEN_W // 2, config.SCREEN_H // 2)


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def example_weather(now):
    from .weather import Day, Report
    today = now.date()
    days = tuple(Day(today + datetime.timedelta(days=i), hi, lo, icon, text, rain) for i, (hi, lo, icon, text, rain) in enumerate(
        ((58, 41, "partly", "Partly cloudy", 10), (52, 38, "rain", "Rain", 70), (49, 33, "cloud", "Cloudy", 20)), 1))
    return Report(temp=54, high=61, low=42, icon="sun", text="Mostly clear", fetched=time.monotonic(), rain=0, days=days)


def draw(name, lists, now):
    """The full-size picture of one part (a pygame Surface, upright 600 x 1024)."""
    import pygame
    surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
    lists = Path(lists)
    if name == "info":
        from . import events, info_view
        evs = events.parse(_read(lists / "events.txt"))
        info_view.draw_info(surf, now, events.upcoming(evs, now, config.INFO_EVENTS))
    elif name == "verses":
        from . import verse_view, verses
        found = verses.parse(_read(lists / "verses.txt"))
        verse_view.draw_verse(surf, found[0] if found else verses.Verse("Psalm 118:24",
                                                                        "This is the day which the LORD hath made; we will "
                                                                        "rejoice and be glad in it."))
    elif name == "weather":
        from . import weather_view
        weather_view.draw_weather(surf, now, example_weather(now))
    elif name == "jokes":
        from . import joke_view, jokes
        found = jokes.parse(_read(lists / "jokes.txt"))
        joke_view.draw_joke(surf, found[0] if found else jokes.Joke("Why did the cookie go to the doctor?",
                                                                    "Because it felt crummy!"), True)
    elif name == "night":
        from . import info_view
        info_view.draw_night(surf, now)
    elif name == "games":
        from . import menu_view
        from .maintenance import SHELL
        from .menu import Menu
        menu_view.show(surf, Menu([SHELL] + [label for label in menu_view.ICONS if label != SHELL]))
    elif name == "touch_calls":
        from .call_view import CallView
        from .contacts import parse
        from .faces import Faces
        from .machine import Mode
        people, buttons = parse(_read(lists / "contacts.txt"))
        view = CallView(buttons, Faces(folder=str(lists / "people")))
        view.touch, view.people = True, [p for p in people.values() if p.name]
        view.draw(surf, Mode.LIFTED, None, 0.0)
    else:
        raise ValueError("no picture of %r" % name)
    return surf


def make_all(lists, out, now=None):
    """Writes OUT/<part>.png for every part (each written in one step, so the website never sends half of one)."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    now = now or datetime.datetime.now()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in features.NAMES:
        small = pygame.transform.smoothscale(draw(name, lists, now), SIZE)
        tmp = out / (".%s.png" % name)
        pygame.image.save(small, str(tmp))
        os.replace(tmp, out / ("%s.png" % name))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.previews", description=__doc__.splitlines()[0])
    ap.add_argument("lists")
    ap.add_argument("out")
    args = ap.parse_args(argv)
    make_all(args.lists, args.out)
    sys.exit(0)


if __name__ == "__main__":
    main()
