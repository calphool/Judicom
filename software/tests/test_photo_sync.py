"""Tests for judicom/photo_sync.py with the real rsync, going through rrsync -ro the way the NAS does (a stand-in for ssh runs it
locally).  Skipped where rsync / rrsync are not installed.   Run from the software folder:   python3 -m unittest -v"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from judicom import photo_sync

RRSYNC = shutil.which("rrsync") or ("/usr/bin/rrsync" if os.path.exists("/usr/bin/rrsync") else None)
HAVE = bool(shutil.which("rsync") and RRSYNC)

FAKE_SSH = """#!/bin/sh
# Stands in for "ssh -i key ... pi@nas <rsync command>": runs the command through rrsync -ro, as the NAS's key line does.
[ -n "$FAKE_SSH_DOWN" ] && { echo "ssh: connect to host 100.64.0.1 port 22: Connection timed out" >&2; exit 255; }
while [ $# -gt 0 ]; do case "$1" in -l|-i|-o|-p) shift 2;; -*) shift;; *) break;; esac; done    # ssh's own options
shift                                    # the host
SSH_ORIGINAL_COMMAND="$*" exec %s -ro "$FAKE_NAS"
""" % RRSYNC


@unittest.skipUnless(HAVE, "rsync / rrsync are not installed")
class Real(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.nas, self.here = root / "nas", root / "photos"
        self.nas.mkdir()
        ssh = root / "fake_ssh"
        ssh.write_text(FAKE_SSH)
        ssh.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {"FAKE_NAS": str(self.nas)})
        self.env.start()
        self.addCleanup(self.env.stop)
        p = mock.patch.object(photo_sync, "ssh_command", lambda key=None: str(ssh))
        p.start()
        self.addCleanup(p.stop)
        self.logged = []

    def add(self, *names, folder=None):
        for n in names:
            (folder or self.nas / n).write_bytes(b"picture " + n.encode()) if folder is None else (folder / n).write_bytes(b"x")

    def sync(self, **kw):
        return photo_sync.sync(str(self.here), log=self.logged.append, **kw)

    def names(self):
        return sorted(p.name for p in self.here.iterdir())

    def test_copies_pictures_and_captions(self):
        self.add("Bryson_1.jpg", "Bryson_1.meta", "Joe And Ann.jpg")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["Bryson_1.jpg", "Bryson_1.meta", "Joe And Ann.jpg"])
        self.assertEqual((self.here / "Bryson_1.jpg").read_bytes(), b"picture Bryson_1.jpg")
        self.assertIn("3 new", self.logged[-1])
        self.assertIn("Joe And Ann.jpg", self.logged[-1])              # names with spaces
        self.assertEqual(self.sync(), 0)
        self.assertIn("unchanged: 2 picture(s)", self.logged[-1])

    def test_a_picture_removed_on_the_nas_goes_here_too(self):
        self.add("a.jpg", "b.jpg", "c.jpg")
        self.sync()
        (self.nas / "c.jpg").unlink()
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])
        self.assertIn("1 removed", self.logged[-1])

    def test_a_changed_caption_is_copied(self):
        self.add("a.jpg", "a.meta")
        self.sync()
        (self.nas / "a.meta").write_text("people: Ann\n")
        os.utime(self.nas / "a.meta", (2_000_000_000, 2_000_000_000))
        self.sync()
        self.assertEqual((self.here / "a.meta").read_text(), "people: Ann\n")
        self.assertIn("1 changed", self.logged[-1])

    def test_empty_nas_folder_changes_nothing(self):
        self.add("a.jpg", "b.jpg")
        self.sync()
        for f in self.nas.iterdir():
            f.unlink()
        self.assertEqual(self.sync(), 1)
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])
        self.assertIn("no pictures", self.logged[-1])
        self.assertEqual(self.sync(force=True), 1)                     # not even --force empties it
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])

    def test_removing_most_of_the_pictures_needs_force(self):
        self.add("a.jpg", "b.jpg", "c.jpg", "d.jpg")
        self.sync()
        for n in ("b.jpg", "c.jpg", "d.jpg"):
            (self.nas / n).unlink()
        self.assertEqual(self.sync(), 1)
        self.assertEqual(len(self.names()), 4)
        self.assertIn("would remove 3 of the 4", self.logged[-1])
        self.assertEqual(self.sync(force=True), 0)
        self.assertEqual(self.names(), ["a.jpg"])

    def test_nas_unreachable_changes_nothing(self):
        self.add("a.jpg")
        self.sync()
        with mock.patch.dict(os.environ, {"FAKE_SSH_DOWN": "1"}):
            self.assertEqual(self.sync(), 1)
        self.assertEqual(self.names(), ["a.jpg"])
        self.assertIn("timed out", self.logged[-1])

    def test_dry_run_changes_nothing(self):
        self.add("a.jpg", "a.meta")
        self.assertEqual(self.sync(dry_run=True), 0)
        self.assertFalse(self.here.exists() and any(self.here.iterdir()))
        self.assertIn("would copy 2 new file(s): a.jpg, a.meta", self.logged[-1])

    def test_no_half_copied_files_left_in_sight(self):
        self.add("a.jpg", "b.jpg")
        self.sync()
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])              # --delay-updates' temporary folder is gone

    def test_videos_and_other_formats_stay_on_the_nas(self):
        self.add("a.jpg", "a.meta", "B.JPEG", "c.PNG", "clip.mp4", "movie.MOV", "phone.heic", "anim.gif", "notes.txt")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["B.JPEG", "a.jpg", "a.meta", "c.PNG"])
        self.assertIn("3 picture(s)", self.logged[-1])

    def test_a_video_already_here_is_removed(self):
        self.add("a.jpg", "b.jpg")
        self.here.mkdir()
        (self.here / "old_clip.mp4").write_bytes(b"x" * 1000)       # copied before videos were left out
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])

    def test_a_folder_of_only_videos_counts_as_empty(self):
        self.add("a.jpg")
        self.sync()
        for f in self.nas.iterdir():
            f.unlink()
        self.add("clip.mp4")
        self.assertEqual(self.sync(), 1)                              # "no pictures": nothing removed here
        self.assertEqual(self.names(), ["a.jpg"])

    def test_a_nearly_full_card_gets_no_new_photos(self):
        self.add("a.jpg", "b.jpg")
        self.sync()
        (self.nas / "c.jpg").write_bytes(b"x" * 5000)
        GB = 1024 ** 3
        self.assertEqual(self.sync(free=lambda folder: 4 * GB + 4000, keep_free=4 * GB), 1)   # 5000 bytes would cross the floor
        self.assertEqual(self.names(), ["a.jpg", "b.jpg"])
        self.assertIn("nearly full", self.logged[-1])
        self.assertEqual(self.sync(free=lambda folder: 4 * GB + 6000, keep_free=4 * GB), 0)   # just enough room
        self.assertEqual(self.names(), ["a.jpg", "b.jpg", "c.jpg"])

    def test_photos_already_here_do_not_count_again(self):
        self.add("a.jpg", "b.jpg")
        self.sync()
        GB = 1024 ** 3
        self.assertEqual(self.sync(free=lambda folder: 4 * GB + 1, keep_free=4 * GB), 0)      # nothing new: no space needed
        self.assertIn("unchanged", self.logged[-1])

    def test_sizes_come_from_the_listing(self):
        (self.nas / "big.jpg").write_bytes(b"y" * 1234567)
        self.assertEqual(photo_sync.remote_files()["big.jpg"], 1234567)

    def test_the_key_cannot_write_to_the_nas(self):
        (self.here).mkdir()
        (self.here / "upload.jpg").write_bytes(b"x")
        ssh = photo_sync.ssh_command()
        r = subprocess.run(["rsync", "-rt", "-e", ssh, str(self.here) + "/", "pi@nas:./"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.nas / "upload.jpg").exists())
        self.assertIn("sending to read-only server is not allowed", r.stderr)


class Planning(unittest.TestCase):
    def test_pictures(self):
        self.assertTrue(photo_sync.wanted("x.meta") and photo_sync.wanted("Y.JPG") and not photo_sync.wanted("v.mp4"))
        self.assertFalse(photo_sync.wanted(".a.jpg"))
        self.assertTrue(photo_sync.is_picture("A.JPG"))
        self.assertFalse(photo_sync.is_picture("a.meta"))
        self.assertFalse(photo_sync.is_picture(".a.jpg"))

    def test_check_rules(self):
        photo_sync.check([], ["a.jpg"], ["a.jpg"])
        photo_sync.check(["a.jpg"], ["a.jpg", "b.jpg"], ["b.jpg"])     # half is allowed
        with self.assertRaises(RuntimeError):
            photo_sync.check(["a.jpg", "b.jpg"], ["a.jpg", "b.jpg", "c.jpg"], ["c.jpg"])
        with self.assertRaises(RuntimeError):
            photo_sync.check([], [], [])
        photo_sync.check(["a.meta", "b.meta", "c.meta"], ["x.jpg"], ["x.jpg"])     # captions do not count as pictures


if __name__ == "__main__":
    unittest.main()
