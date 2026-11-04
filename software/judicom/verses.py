"""Scripture verses for the verse screen: the list, and a shuffled deck so every verse comes once before any comes again.

THE FILE (/home/joe/verses.txt on the Judicom, a copy of /home/pi/judicom/verses.txt on the NAS), one verse or passage per line:

    Isaiah 46:4 | And even to your old age I am he; and even to hoar hairs will I carry you: ...
    Psalm 121:1-2 | I will lift up mine eyes unto the hills, from whence cometh my help. [2] My help cometh from the LORD, ...

The reference, a |, and the words (King James Version).  [2] marks where verse 2 begins inside a passage: the screen prints a small
verse number there, as a Bible page does.  Lines starting with # and empty lines are skipped; a line without a | is reported.

    python3 -m judicom.verses          the list, in the order it would be shown
"""
from __future__ import annotations

import argparse
import os
import random
import re
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Verse:
    reference: str             # "Psalm 121:1-2"
    text: str                  # with [n] where verse n begins

    @property
    def book(self) -> str:
        """'Psalm 121:1-2' -> 'Psalm', '1 Peter 5:7' -> '1 Peter'."""
        m = re.match(r"^(.*?)\s+\d+(?::\d+)?", self.reference)
        return m.group(1) if m else self.reference

    @property
    def first_verse(self) -> str:
        m = re.search(r":(\d+)", self.reference)
        return m.group(1) if m else ""

    def parts(self) -> list[tuple[str, str]]:
        """[(verse number or '', words), ...]: the first part has '' (its number is in the reference)."""
        pieces = re.split(r"\s*\[(\d+)\]\s*", self.text)
        out = [("", pieces[0].strip())]
        for i in range(1, len(pieces) - 1, 2):
            out.append((pieces[i], pieces[i + 1].strip()))
        return [(n, t) for n, t in out if t]


def parse(text: str, log=None) -> list[Verse]:
    log = log or (lambda msg: None)
    verses = []
    for n, line in enumerate((text or "").lstrip("﻿").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ref, sep, words = (p.strip() for p in line.partition("|"))
        if not sep or not ref or not words:
            log("verses line %d skipped (needs: reference | words): %s" % (n, line[:60]))
            continue
        verses.append(Verse(" ".join(ref.split()), " ".join(words.split())))
    return verses


class VerseDeck:
    """The verses file, read again when it changes, dealt out in shuffled rounds."""

    def __init__(self, path=None, rng=None, log=None):
        self.path = str(config.VERSES_FILE if path is None else path)
        self.rng = rng or random.Random()
        self.log = log or (lambda msg: None)
        self.verses: list[Verse] = []
        self._deck: list[Verse] = []
        self._last = None
        self._stamp = "unread"
        self.refresh()

    def refresh(self) -> bool:
        try:
            st = os.stat(self.path)
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            stamp = None
        if stamp == self._stamp:
            return False
        self._stamp = stamp
        if stamp is None:
            self.verses = []
        else:
            try:
                with open(self.path, encoding="utf-8", errors="replace") as fh:
                    self.verses = parse(fh.read(), self.log)
            except OSError as exc:
                self.log("cannot read %s: %s" % (self.path, exc))
                return False
            self.log("Verses: %d from %s" % (len(self.verses), self.path))
        self._deck = [v for v in self._deck if v in self.verses]       # a changed list: what is left of the round, still in it
        return True

    def next(self) -> Verse | None:
        if not self.verses:
            return None
        if not self._deck:
            self._deck = list(self.verses)
            self.rng.shuffle(self._deck)
            if len(self._deck) > 1 and self._deck[-1] == self._last:
                self._deck[0], self._deck[-1] = self._deck[-1], self._deck[0]
        self._last = self._deck.pop()
        return self._last


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m judicom.verses", description="Show the verse list in the order it would be shown.")
    ap.add_argument("file", nargs="?", default=str(config.VERSES_FILE))
    args = ap.parse_args(argv)
    deck = VerseDeck(args.file, log=print)
    for i in range(len(deck.verses)):
        v = deck.next()
        print("  %2d. %-22s %s" % (i + 1, v.reference, v.text[:70] + ("..." if len(v.text) > 70 else "")))


if __name__ == "__main__":
    main()
