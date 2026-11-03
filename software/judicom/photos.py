"""Which picture comes next, and what its caption file says.

Nothing in here touches the screen, so it runs (and is tested) on any computer.  Check your own folder with:

    python3 -m judicom.photos                  (lists the folder and shows the next 10 pictures in random order)

THE FOLDER
  /home/joe/photos  (change it in judicom/config.py, or set JUDICOM_PHOTOS).  Only pictures directly inside that folder are used,
  not pictures in sub-folders.  .jpg .jpeg .png .bmp count as pictures (capital letters do not matter).  Names that start with a dot
  are ignored: a copy made from a Mac or over a network share can leave files like "._IMG_0001.jpg" behind, and they are not pictures.

THE ORDER
  A shuffled deck: every picture is shown once, in random order, before any picture is shown a second time.  The folder is looked at
  again each time the deck runs out, so pictures added by the twice-a-day NAS sync join the next round and deleted ones drop out.
  A new round never starts with the picture that ended the one before.  A picture that disappears in the middle of a round is skipped.

CAPTION FILES (optional)
  A picture IMG_0001.jpg may have a caption file IMG_0001.meta (IMG_0001.jpg.meta works too), plain text:

      people: Clark and Amy
      relationship: Your husband and your daughter
      taken: 2019-06-14

  'taken' may be 2019-06-14, 2019-06 or 2019 (shown as "June 14, 2019", "June 2019", "2019") or any other text, shown as it is.  Write the
  relationship the way it should read on the screen.  Lines without a "word:" in front are used in the same order (people, relationship,
  taken).  A line that starts with # is a comment.  No caption file, or one that cannot be read, simply means no caption.
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

from .config import PHOTO_DIR, PHOTO_EXTS


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


def nice_date(raw: str) -> str:
    """2019-06-14 -> June 14, 2019;  2019-06 -> June 2019;  2019 -> 2019;  anything else as it is."""
    raw = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    try:
        if m:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", raw)
        if m:
            return "%s %d" % (datetime.date(int(m.group(1)), int(m.group(2)), 1).strftime("%B"), int(m.group(1)))
    except ValueError:
        pass
    return raw


@dataclass(frozen=True)
class Caption:
    people: str = ""
    relationship: str = ""
    taken: str = ""                          # as written in the file

    @property
    def taken_text(self) -> str:
        """`taken` as it should read on the screen."""
        return nice_date(self.taken) if self.taken else ""

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
    parts = [p for p in (caption.people, caption.relationship, caption.taken_text) if p]
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
