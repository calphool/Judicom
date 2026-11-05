"""Which picture comes next, and what its caption file says.

Nothing in here touches the screen, so it runs (and is tested) on any computer.  Check your own folder with:

    python3 -m judicom.photos                  (lists the folder and shows the next 10 pictures in random order)

THE FOLDER
  /home/joe/photos  (change it in judicom/config.py, or set JUDICOM_PHOTOS).  Only pictures directly inside that folder are used,
  not pictures in sub-folders.  .jpg .jpeg .png .bmp count as pictures (capital letters do not matter).  Names that start with a dot
  are ignored: a copy made from a Mac or over a network share can leave files like "._IMG_0001.jpg" behind, and they are not pictures.

THE ORDER
  A shuffled deck: every picture is shown once, in random order, before any picture is shown a second time.  The folder is looked at
  again each time the deck runs out, so pictures added by the hourly NAS sync (judicom/photo_sync.py) join the next round and
  deleted ones drop out.
  A new round never starts with the picture that ended the one before.  A picture that disappears in the middle of a round is skipped.

CAPTION FILES (optional)
  A picture IMG_0001.jpg may have a caption file IMG_0001.meta (IMG_0001.jpg.meta works too), plain text:

      people: Clark and Amy
      relationship: Your husband and your daughter
      taken: 2019-06-14

  Lines without a "word:" in front are used in the same order (people, relationship, taken).  A line that starts with # is a comment.
  No caption file, or one that cannot be read, simply means no caption.

  HOW IT READS ON THE SCREEN: however the caption was typed (by hand, or by the NAS from a family member's email), it is shown tidied the
  same way.  The file itself is never changed.
    people        each name starts with a capital ("waylyn and joe" -> "Waylyn and Joe"); names that already have capitals stay as
                  typed ("McDonald"); Judi's own name (JUDI_NAMES in config.py) becomes "You"
    relationship  starts with a capital and is said to Judi: "granddaughter" -> "Your granddaughter", "Judi's sister" / "her sister"
                  -> "Your sister"
    taken         2019-06-14, 6/14/2019, Jun 14 2019, 14 June 2019 -> "June 14, 2019";  2019-06, 6/2019, june 2019 -> "June 2019";
                  2019 -> "2019";  anything else starts with a capital ("summer 2024" -> "Summer 2024")
  In all three: extra spaces and a full stop at the end go, and ALL-CAPS typing is calmed down.
"""
from __future__ import annotations

import argparse
import datetime
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .config import JUDI_NAMES, PHOTO_DIR, PHOTO_EXTS


# ----------------------------------------------------------------------------------------------- the folder and the order
def list_photos(folder) -> list[Path]:
    """The pictures directly inside `folder`, sorted by name.  A missing or unreadable folder gives an empty list."""
    try:
        found = [p for p in Path(folder).iterdir()
                 if not p.name.startswith(".") and p.suffix.lower() in PHOTO_EXTS and p.is_file()]
    except OSError:
        return []
    return sorted(found)


class PhotoDeck:
    """Hands out the pictures of one folder in shuffled rounds.  `next()` gives a path, or None if there is no picture at all."""

    def __init__(self, folder=PHOTO_DIR, rng: random.Random | None = None):
        self.folder = Path(folder)
        self._rng = rng or random.Random()
        self._deck: list[Path] = []          # what is left of this round; the next picture is taken from the end
        self._last: Path | None = None
        self.rounds = 0                      # how many times the deck has been filled (for the log)

    @property
    def remaining(self) -> int:
        """Pictures left in the current round."""
        return len(self._deck)

    def next(self) -> Path | None:
        refilled = False
        while True:
            if not self._deck:
                if refilled or not self._refill():     # nothing in the folder (or it all vanished while we looked)
                    return None
                refilled = True
            path = self._deck.pop()
            if path.is_file():                         # the sync may have removed it since the folder was read
                self._last = path
                return path

    def _refill(self) -> bool:
        photos = list_photos(self.folder)
        if not photos:
            return False
        self._rng.shuffle(photos)
        if len(photos) > 1 and photos[-1] == self._last:   # the end of the list is shown first: keep the last picture from repeating
            photos[0], photos[-1] = photos[-1], photos[0]
        self._deck = photos
        self.rounds += 1
        return True


# ----------------------------------------------------------------------------------------------- caption files
META_KEYS = {"people": "people", "names": "people", "name": "people", "who": "people",
             "relationship": "relationship", "relationships": "relationship", "relation": "relationship",
             "taken": "taken", "date": "taken", "when": "taken", "photographed": "taken"}
META_ORDER = ("people", "relationship", "taken")


MONTHS = {m.lower(): i for i, m in enumerate(("January February March April May June July August September October November "
                                              "December").split(), 1)}
MONTHS.update({name[:3]: i for name, i in list(MONTHS.items())})
MONTHS.update({"sept": 9})

# Words that, at the start of a relationship, are said to Judi: "granddaughter" -> "Your granddaughter".
KIN = {"daughter", "son", "husband", "wife", "sister", "brother", "niece", "nephew", "cousin", "friend", "aunt", "uncle", "mother",
       "father", "mom", "dad", "child", "children", "kids", "family", "caregiver", "neighbor", "neighbour", "nurse", "pastor",
       "doctor", "sisters", "brothers", "daughters", "sons", "nieces", "nephews", "cousins", "friends", "parents", "in-laws"}


def _tidy(text: str) -> str:
    """Extra spaces, a full stop at the end and surrounding quotes go; ALL-CAPS typing becomes lower case (then capitalised)."""
    text = " ".join((text or "").split()).strip("\"'“”‘’ ").rstrip(".;,").strip()
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= 4 and all(ch.isupper() for ch in letters):
        text = text.lower()
    return text


def _cap(word: str) -> str:
    """'mary-ann' -> 'Mary-Ann', "o'brien" -> "O'Brien"; a word that already has a capital stays as it is ('McDonald')."""
    if any(ch.isupper() for ch in word):
        return word
    return re.sub(r"(^|[-'’])([a-z])", lambda m: m.group(1) + m.group(2).upper(), word)


def _shouted(word: str) -> bool:
    """A word typed in capitals ('JOE', 'GRANDSON'); one or two letters are initials ('AJ') and stay."""
    letters = [ch for ch in word if ch.isalpha()]
    return len(letters) >= 3 and all(ch.isupper() for ch in letters)


def _is_judi(word: str) -> bool:
    return word.lower().strip(",.;:!?") in {n.lower() for n in JUDI_NAMES}


def nice_people(raw: str) -> str:
    """'waylyn, judi and joe' -> 'Waylyn, You and Joe'."""
    out = []
    for word in _tidy(raw).split():
        core, tail = re.match(r"^(.*?)([,.;:!?]*)$", word).groups()
        low = core.lower()
        if low in ("and", "or", "with", "&"):
            out.append(("and" if low == "&" else low) + tail)
        elif _is_judi(core) or low == "you":
            out.append("You" + tail)
        else:
            out.append(_cap(core.lower() if _shouted(core) else core) + tail)
    return " ".join(out)


def nice_relationship(raw: str) -> str:
    """'granddaughter' -> 'Your granddaughter', "judi's sister" -> 'Your sister', "sydney's husband" -> "Sydney's husband"."""
    text = _tidy(raw)
    if not text:
        return ""
    words = [w.lower() if _shouted(w) else w for w in text.split()]
    possessive = {n.lower() + suffix for n in JUDI_NAMES for suffix in ("'s", "’s")}
    words = ["your" if w.lower().strip(",") in possessive else ("you" + w[len(w.rstrip(",")):] if _is_judi(w) else w) for w in words]
    if words[0].lower() == "her":
        words[0] = "your"
    first = words[0].lower().strip(",")
    if first in KIN or first.startswith(("grand", "great", "step")) or first.endswith(("-in-law", "-in-laws")):
        words.insert(0, "your")
    text = " ".join(words)
    return text[0].upper() + text[1:]


def nice_date(raw: str) -> str:
    """2019-06-14, 6/14/2019, Jun 14 2019, 14 June 2019 -> June 14, 2019;  2019-06, 6/2019, june 2019 -> June 2019;  2019 -> 2019;
    anything else as written, with a capital first letter (and the date as written if it is not a real date: 2019-02-31)."""
    text = _tidy(raw)
    low = text.lower().replace(",", " ")

    def day(y, m, d):
        try:
            dt = datetime.date(y, m, d)
        except ValueError:
            return None
        return "%s %d, %d" % (dt.strftime("%B"), dt.day, dt.year)

    def month(y, m):
        return "%s %d" % (datetime.date(y, m, 1).strftime("%B"), y) if 1 <= m <= 12 else None

    def year(y):
        return y + 2000 if y < 100 else y

    no = False                                             # "not this kind of date": try the next pattern
    patterns = [
        (r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", lambda g: day(int(g[0]), int(g[1]), int(g[2]))),
        (r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2}|\d{4})", lambda g: day(year(int(g[2])), int(g[0]), int(g[1]))),     # US: month first
        (r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})",
         lambda g: day(int(g[2]), MONTHS[g[0]], int(g[1])) if g[0] in MONTHS else no),
        (r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?\s+(\d{4})",
         lambda g: day(int(g[2]), MONTHS[g[1]], int(g[0])) if g[1] in MONTHS else no),
        (r"(\d{4})[-/.](\d{1,2})", lambda g: month(int(g[0]), int(g[1]))),
        (r"(\d{1,2})[-/.](\d{4})", lambda g: month(int(g[1]), int(g[0]))),
        (r"([a-z]+)\.?\s+(\d{4})", lambda g: month(int(g[1]), MONTHS[g[0]]) if g[0] in MONTHS else no),
        (r"(\d{4})", lambda g: g[0]),
    ]
    for pattern, make in patterns:
        m = re.fullmatch(pattern, " ".join(low.split()))
        if m:
            result = make(m.groups())
            if result is no:
                continue
            return result or text                          # a date that cannot be (2019-02-31): as written
    return text[:1].upper() + text[1:]


@dataclass(frozen=True)
class Caption:
    people: str = ""
    relationship: str = ""
    taken: str = ""                          # all three as written in the file; the *_text versions are what the screen shows

    @property
    def people_text(self) -> str:
        return nice_people(self.people) if self.people else ""

    @property
    def relationship_text(self) -> str:
        return nice_relationship(self.relationship) if self.relationship else ""

    @property
    def taken_text(self) -> str:
        """`taken` as it should read on the screen."""
        return nice_date(self.taken) if self.taken else ""

    def years_ago(self, today: datetime.date | None = None) -> str:
        """'1 year ago', '7 years ago' from the year in `taken` (by calendar year: December 2025 is '1 year ago' in 2026);
        '' for this year, a year still to come, or no year in it."""
        found = re.findall(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", self.taken_text)
        if not found:
            return ""
        n = (today or datetime.date.today()).year - int(found[-1])
        return "" if n <= 0 else "1 year ago" if n == 1 else "%d years ago" % n

    def __bool__(self) -> bool:
        return bool(self.people or self.relationship or self.taken)


def caption_file(photo: Path) -> Path | None:
    """The caption file belonging to a picture, if there is one."""
    photo = Path(photo)
    for cand in (photo.with_suffix(".meta"), photo.with_name(photo.name + ".meta")):
        if cand.is_file():
            return cand
    return None


def parse_caption(text: str) -> Caption:
    fields: dict[str, str] = {}
    loose: list[str] = []
    for line in text.lstrip("﻿").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z ]+?)\s*[:=]\s*(.*)$", line)
        if m and m.group(1).strip().lower() in META_KEYS:
            if m.group(2).strip():                 # "relationship:" with nothing after it means "no relationship", not a caption line
                fields[META_KEYS[m.group(1).strip().lower()]] = m.group(2).strip()
            else:
                fields.setdefault(META_KEYS[m.group(1).strip().lower()], "")
        else:
            loose.append(line)
    for key in META_ORDER:                   # lines without a label fill the gaps, in order
        if key not in fields and loose:
            fields[key] = loose.pop(0)
    return Caption(**fields)


def load_caption(photo: Path) -> Caption:
    """The caption of a picture.  No file, or a file that cannot be read, gives an empty Caption (the picture is still shown)."""
    path = caption_file(photo)
    if path is None:
        return Caption()
    try:
        return parse_caption(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return Caption()


# ----------------------------------------------------------------------------------------------- python3 -m judicom.photos
def describe(caption: Caption) -> str:
    parts = [p for p in (caption.people_text, caption.relationship_text, caption.taken_text) if p]
    return " | ".join(parts) if parts else "(no caption)"


def check_folder(folder, how_many: int = 10, rng: random.Random | None = None, out=print) -> bool:
    """Print what is in the folder and the next `how_many` pictures in the order they would be shown.  True if there are pictures."""
    folder = Path(folder)
    out("Photo folder: %s" % folder)
    if not folder.is_dir():
        out("  This folder does not exist.")
        return False
    photos = list_photos(folder)
    try:
        entries = sorted(folder.iterdir())
    except OSError as exc:
        out("  Cannot read the folder: %s" % exc)
        return False

    with_caption = sum(1 for p in photos if caption_file(p))
    out("  %d picture%s, %d with a caption file, %d without" %
        (len(photos), "" if len(photos) == 1 else "s", with_caption, len(photos) - with_caption))

    stems = {p.stem for p in photos} | {p.name for p in photos}
    orphans = [e.name for e in entries if e.suffix.lower() == ".meta" and not e.name.startswith(".") and e.stem not in stems]
    if orphans:
        out("  Caption files with no picture of that name (a spelling mistake?): " + ", ".join(orphans))
    unreadable = [p.name for p in photos if (c := caption_file(p)) and not load_caption(p)]
    if unreadable:
        out("  Pictures whose caption file is empty or unreadable: " + ", ".join(unreadable))
    others = Counter(e.suffix.lower() or "(no extension)" for e in entries
                     if e.is_file() and not e.name.startswith(".") and e.suffix.lower() not in PHOTO_EXTS and e.suffix.lower() != ".meta")
    if others:
        out("  Files that are not shown (not a picture type): " + ", ".join("%d %s" % (n, ext) for ext, n in sorted(others.items())))
    subfolders = [e.name for e in entries if e.is_dir() and not e.name.startswith(".")]
    if subfolders:
        out("  Sub-folders are not searched: " + ", ".join(subfolders))
    if not photos:
        out("  No pictures to show.")
        return False

    deck = PhotoDeck(folder, rng)
    how_many = max(how_many, 0)
    out("  Next %d, in the random order they would be shown:" % how_many)
    for i in range(how_many):
        path = deck.next()
        if path is None:
            break
        out("   %2d. %-28s %s" % (i + 1, path.name, describe(load_caption(path))))
        if i + 1 < how_many and deck.remaining == 0 and len(photos) <= how_many:
            out("       -- every picture shown once; the next round starts --")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m judicom.photos", description="Check the photo folder and show the next random picks.")
    ap.add_argument("folder", nargs="?", default=str(PHOTO_DIR), help="photo folder (default %(default)s)")
    ap.add_argument("-n", "--next", type=int, default=10, metavar="N", help="how many upcoming pictures to list (default 10)")
    args = ap.parse_args(argv)
    return 0 if check_folder(args.folder, args.next) else 1


if __name__ == "__main__":
    sys.exit(main())
