"""Tests for judicom/watched_file.py (a file read again only when it changes).   Run from the software folder:
python3 -m unittest -v"""
import os
import tempfile
import unittest
from pathlib import Path

from judicom.watched_file import WatchedFile


class Reading(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "list.txt"
        self.logged = []

    def write(self, text, mtime):
        self.path.write_text(text, encoding="utf-8")
        os.utime(self.path, (mtime, mtime))

    def test_read_once_then_again_only_when_changed(self):
        self.write("one", 1000)
        f = WatchedFile(self.path, self.logged.append)
        self.assertEqual(f.read(), (True, "one"))
        self.assertEqual(f.read(), (False, None))
        self.write("two", 2000)
        self.assertEqual(f.read(), (True, "two"))
        self.assertFalse(f.missing)

    def test_same_time_but_a_different_size_is_a_change(self):
        self.write("one", 1000)
        f = WatchedFile(self.path)
        f.read()
        self.write("one more", 1000)
        self.assertEqual(f.read(), (True, "one more"))

    def test_no_file_is_said_once_and_coming_back_is_noticed(self):
        f = WatchedFile(self.path)
        self.assertEqual(f.read(), (True, None))                  # the first read: no file
        self.assertTrue(f.missing)
        self.assertEqual(f.read(), (False, None))                 # still none: nothing new
        self.write("back", 1000)
        self.assertEqual(f.read(), (True, "back"))
        self.path.unlink()
        self.assertEqual(f.read(), (True, None))                  # gone again

    def test_bytes_that_are_not_utf8_do_not_stop_it(self):
        self.path.write_bytes(b"caf\xe9 | x")
        self.assertEqual(WatchedFile(self.path).read(), (True, "caf� | x"))

    def test_a_file_that_cannot_be_read_keeps_the_old_text(self):
        self.path.mkdir()                                         # there, but not a readable file
        f = WatchedFile(self.path, self.logged.append)
        self.assertEqual(f.read(), (False, None))
        self.assertIn("Cannot read", self.logged[0])
        self.assertEqual(f.read(), (False, None))                 # not said again until it changes
        self.assertEqual(len(self.logged), 1)


if __name__ == "__main__":
    unittest.main()
