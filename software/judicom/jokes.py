"""Jokes for the joke screen: the list, and a shuffled deck so every joke comes once before any comes again.

THE FILE (/home/joe/jokes.txt on the Judicom, a copy of /home/pi/judicom/jokes.txt on the NAS), one joke per line:

    Why did the scarecrow win an award? | Because he was outstanding in his field!

The setup, a |, and the punchline, which the screen shows PUNCHLINE_SECONDS after the setup.  Lines starting with # and empty lines
are skipped; a line without both halves is reported.

    python3 -m judicom.jokes          the list, in the order it would be shown
"""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from . import config
from .watched_file import WatchedFile


@dataclass(frozen=True)
class Joke:
    setup: str
    punchline: str


def parse(text: str, log=None) -> list[Joke]:
    log = log or (lambda msg: None)
    jokes = []
    for n, line in enumerate((text or "").lstrip("﻿").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        setup, sep, punchline = (p.strip() for p in line.partition("|"))
        if not sep or not setup or not punchline:
            log("jokes line %d skipped (needs: setup | punchline): %s" % (n, line[:60]))
            continue
        jokes.append(Joke(" ".join(setup.split()), " ".join(punchline.split())))
    return jokes


class JokeDeck:
    """The jokes file, read again when it changes, dealt out in shuffled rounds."""

    def __init__(self, path=None, rng=None, log=None):
        self.path = str(config.JOKES_FILE if path is None else path)
        self.rng = rng or random.Random()
        self.log = log or (lambda msg: None)
        self.jokes: list[Joke] = []
        self._deck: list[Joke] = []
        self._last = None
        self._file = WatchedFile(self.path, self.log)
        self.refresh()

    def refresh(self) -> bool:
        """Read the file again if it changed (no file: no jokes).  True if it did."""
        changed, text = self._file.read()
        if not changed:
            return False
        self.jokes = [] if text is None else parse(text, self.log)
        if text is not None:
            self.log("Jokes: %d from %s" % (len(self.jokes), self.path))
        self._deck = [j for j in self._deck if j in self.jokes]           # a changed list: what is left of the round, still in it
        return True

    def next(self) -> Joke | None:
        if not self.jokes:
            return None
        if not self._deck:
            self._deck = list(self.jokes)
            self.rng.shuffle(self._deck)
            if len(self._deck) > 1 and self._deck[-1] == self._last:      # not the same joke twice running across two rounds
                self._deck[0], self._deck[-1] = self._deck[-1], self._deck[0]
        self._last = self._deck.pop()
        return self._last


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.jokes", description="Show the joke list in the order it would be shown.")
    ap.add_argument("file", nargs="?", default=str(config.JOKES_FILE))
    args = ap.parse_args(argv)
    deck = JokeDeck(args.file, log=print)
    for i in range(len(deck.jokes)):
        j = deck.next()
        print("  %3d. %s  /  %s" % (i + 1, j.setup, j.punchline))


if __name__ == "__main__":
    main()
