"""Tests for judicom/photos.py.   Run from the software folder:   python3 -m unittest -v"""
import io
import random
import re
import tempfile
import unittest
from pathlib import Path

from judicom import photos
from judicom.photos import Caption, PhotoDeck, list_photos, load_caption, nice_date, parse_caption


class Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def add(self, *names, text=""):
        for n in names:
            (self.dir / n).write_text(text)

    def names(self, paths):
        return [p.name for p in paths]


class ListPhotos(Folder):
    def test_only_pictures_directly_in_the_folder(self):
        self.add("a.jpg", "b.JPEG", "c.Png", "d.bmp", "notes.txt", "a.meta", "movie.mp4", "photo.heic", ".hidden.jpg", "._a.jpg")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "deep.jpg").write_text("")
        (self.dir / "folder.jpg").mkdir()                       # a folder that happens to be called .jpg
        self.assertEqual(self.names(list_photos(self.dir)), ["a.jpg", "b.JPEG", "c.Png", "d.bmp"])

    def test_missing_or_empty_folder(self):
        self.assertEqual(list_photos(self.dir / "nope"), [])
        self.assertEqual(list_photos(self.dir), [])


class Deck(Folder):
    def test_no_pictures_gives_none(self):
        self.assertIsNone(PhotoDeck(self.dir).next())
        self.assertIsNone(PhotoDeck(self.dir / "missing").next())

    def test_every_picture_once_per_round(self):
        self.add(*["p%02d.jpg" % i for i in range(12)])
        deck = PhotoDeck(self.dir, random.Random(1))
        for _ in range(4):
            round_ = [deck.next().name for _ in range(12)]
            self.assertEqual(sorted(round_), ["p%02d.jpg" % i for i in range(12)])
        self.assertEqual(deck.rounds, 4)

    def test_order_really_is_random(self):
        self.add(*["p%02d.jpg" % i for i in range(12)])
        orders = set()
        for seed in range(20):
            deck = PhotoDeck(self.dir, random.Random(seed))
            orders.add(tuple(deck.next().name for _ in range(12)))
        self.assertGreater(len(orders), 15)                      # 20 seeds, almost surely 20 different orders

    def test_same_seed_same_order(self):
        self.add(*["p%02d.jpg" % i for i in range(8)])
        d1, d2 = PhotoDeck(self.dir, random.Random(5)), PhotoDeck(self.dir, random.Random(5))
        self.assertEqual([d1.next() for _ in range(20)], [d2.next() for _ in range(20)])

    def test_new_round_never_starts_with_the_last_picture(self):
        for count in (2, 3, 4, 7):
            folder = self.dir / ("n%d" % count)
            folder.mkdir()
            for i in range(count):
                (folder / ("p%d.jpg" % i)).write_text("")
            for seed in range(300):
                deck = PhotoDeck(folder, random.Random(seed))
                shown = [deck.next().name for _ in range(count * 6)]
                for a, b in zip(shown, shown[1:]):
                    self.assertNotEqual(a, b, "back-to-back repeat with %d pictures, seed %d" % (count, seed))

    def test_one_picture_is_shown_over_and_over(self):
        self.add("only.jpg")
        deck = PhotoDeck(self.dir)
        self.assertEqual([deck.next().name for _ in range(3)], ["only.jpg"] * 3)

    def test_new_pictures_join_the_next_round_not_this_one(self):
        self.add("a.jpg", "b.jpg", "c.jpg")
        deck = PhotoDeck(self.dir, random.Random(3))
        first = deck.next().name                                 # the round begins: the folder is read now
        self.add("d.jpg")                                        # the sync adds a picture in the middle of the round
        this_round = [first] + [deck.next().name for _ in range(2)]
        self.assertEqual(sorted(this_round), ["a.jpg", "b.jpg", "c.jpg"])
        next_round = [deck.next().name for _ in range(4)]
        self.assertEqual(sorted(next_round), ["a.jpg", "b.jpg", "c.jpg", "d.jpg"])

    def test_picture_removed_mid_round_is_skipped(self):
        self.add(*["p%d.jpg" % i for i in range(5)])
        deck = PhotoDeck(self.dir, random.Random(9))
        deck.next()                                              # fills the deck
        victim = deck._deck[-1]                                  # the one that would come next
        victim.unlink()
        shown = [deck.next().name for _ in range(3)]
        self.assertNotIn(victim.name, shown)
        self.assertEqual(len(set(shown)), 3)

    def test_folder_emptied_mid_round(self):
        self.add("a.jpg", "b.jpg")
        deck = PhotoDeck(self.dir, random.Random(0))
        deck.next()
        for p in self.dir.glob("*.jpg"):
            p.unlink()
        self.assertIsNone(deck.next())
        self.add("c.jpg")                                        # and it recovers when pictures come back
        self.assertEqual(deck.next().name, "c.jpg")


class NiceDate(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(nice_date("2019-06-14"), "June 14, 2019")
        self.assertEqual(nice_date("2019-6-4"), "June 4, 2019")
        self.assertEqual(nice_date("2012-08"), "August 2012")
        self.assertEqual(nice_date("2016"), "2016")
        self.assertEqual(nice_date("  Christmas 1998 "), "Christmas 1998")
        self.assertEqual(nice_date("2019-02-31"), "2019-02-31")      # not a real date: shown as written
        self.assertEqual(nice_date("2019-13"), "2019-13")


class Captions(Folder):
    def test_labelled_lines(self):
        c = parse_caption("people: Frank and Ann\nrelationship: Your husband and your daughter\ntaken: 2019-06-14\n")
        self.assertEqual((c.people, c.relationship, c.taken, c.taken_text),
                         ("Frank and Ann", "Your husband and your daughter", "2019-06-14", "June 14, 2019"))

    def test_other_words_and_case_and_equals(self):
        c = parse_caption("Names = Hannah\nRelation: Your granddaughter\nDATE: 2023-03")
        self.assertEqual((c.people, c.relationship, c.taken_text), ("Hannah", "Your granddaughter", "March 2023"))

    def test_unlabelled_lines_fill_in_order(self):
        c = parse_caption("Ann\nYour daughter\n2012-08\n")
        self.assertEqual((c.people, c.relationship, c.taken), ("Ann", "Your daughter", "2012-08"))

    def test_mixed_labelled_and_unlabelled(self):
        c = parse_caption("taken: 2016\nFrank\nYour husband")
        self.assertEqual((c.people, c.relationship, c.taken), ("Frank", "Your husband", "2016"))

    def test_comments_blank_lines_and_bom(self):
        c = parse_caption("﻿# who is in it\n\npeople: Ann\n  \n# end\n")
        self.assertEqual((c.people, c.relationship, c.taken), ("Ann", "", ""))

    def test_label_with_nothing_after_it_is_not_shown_as_text(self):
        c = parse_caption("people: Ann\nrelationship:\ntaken: 2016\n")
        self.assertEqual((c.people, c.relationship, c.taken), ("Ann", "", "2016"))
        c = parse_caption("people:\nrelationship: Your daughter\n")
        self.assertEqual((c.people, c.relationship), ("", "Your daughter"))
        self.assertFalse(parse_caption("people:\nrelationship:\ntaken:\n"))

    def test_empty_means_no_caption(self):
        self.assertFalse(parse_caption(""))
        self.assertFalse(parse_caption("# just a comment\n"))
        self.assertTrue(parse_caption("people: Ann"))

    def test_file_lookup_both_names(self):
        self.add("a.jpg", "b.jpg", "c.jpg")
        self.add("a.meta", text="people: A")
        self.add("b.jpg.meta", text="people: B")
        self.assertEqual(load_caption(self.dir / "a.jpg").people, "A")
        self.assertEqual(load_caption(self.dir / "b.jpg").people, "B")
        self.assertEqual(load_caption(self.dir / "c.jpg"), Caption())

    def test_unreadable_caption_file_does_not_hide_the_picture(self):
        self.add("a.jpg")
        (self.dir / "a.meta").write_bytes(b"people: Am\xffy\n")      # not valid UTF-8
        self.assertEqual(load_caption(self.dir / "a.jpg").people, "Am�y")
        (self.dir / "b.jpg").write_text("")
        (self.dir / "b.meta").mkdir()                                # exists but is a folder: is_file() says no
        self.assertEqual(load_caption(self.dir / "b.jpg"), Caption())


class CheckCommand(Folder):
    def run_check(self, folder=None, n=10):
        buf = io.StringIO()
        ok = photos.check_folder(folder or self.dir, n, random.Random(1), out=lambda s: print(s, file=buf))
        return ok, buf.getvalue()

    def test_reports_problems(self):
        self.add("a.jpg", "b.jpg", "c.jpg", "phone.heic", "phone2.HEIC", "typo.meta", "._a.jpg")
        self.add("a.meta", text="people: Ann")
        self.add("c.jpg.meta", text="# nothing here")
        (self.dir / "2019").mkdir()
        ok, out = self.run_check()
        self.assertTrue(ok)
        self.assertIn("3 pictures, 2 with a caption file, 1 without", out)
        self.assertIn("typo.meta", out)                          # no picture called typo
        self.assertIn("c.jpg", out.split("empty or unreadable:")[1].splitlines()[0])
        self.assertIn("2 .heic", out)
        self.assertIn("Sub-folders are not searched: 2019", out)
        self.assertIn("Ann", out)

    def test_missing_and_empty(self):
        ok, out = self.run_check(self.dir / "nope")
        self.assertFalse(ok)
        self.assertIn("does not exist", out)
        ok, out = self.run_check()
        self.assertFalse(ok)
        self.assertIn("No pictures to show", out)

    def test_lists_requested_count(self):
        self.add(*["p%02d.jpg" % i for i in range(30)])
        ok, out = self.run_check(n=7)
        numbered = [line for line in out.splitlines() if re.match(r"^\s+\d+\. \S", line)]
        self.assertEqual(len(numbered), 7)


if __name__ == "__main__":
    unittest.main()
