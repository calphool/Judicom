"""Tests for deploy/nas/backup/naspi_backup.sh (the NAS's weekly backup), run on temporary folders.  A stand-in curl records
the pings instead of sending them.   Run from the software folder:   python3 -m unittest -v"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "backup" / "naspi_backup.sh"
NEEDS = all(shutil.which(t) for t in ("bash", "rsync", "zstd"))


@unittest.skipUnless(NEEDS, "needs bash, rsync and zstd")
class Backup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.src, self.dest, self.bin = t / "home", t / "2tb", t / "bin"
        for d in (self.src / ".cache", self.src / ".npm", self.src / "judicom", self.dest / "judicom-backups", self.bin):
            d.mkdir(parents=True)
        (self.src / "judicom" / "contacts.txt").write_text("555-555-0100 | Someone\n")
        (self.src / ".cache" / "big").write_text("cache")
        (self.src / ".npm" / "pkg").write_text("npm")
        self.sd = t / "sd.img"
        self.sd.write_bytes(b"\0" * 100000 + b"system")
        self.pings = t / "pings"
        (self.bin / "curl").write_text('#!/bin/bash\necho "${@: -1}" >> "%s"\n' % self.pings)
        (self.bin / "curl").chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, today="2026-11-15", **extra):
        env = dict(os.environ, PATH="%s:%s" % (self.bin, os.environ["PATH"]), SETTINGS="/nonexistent", SRC=str(self.src),
                   DEST=str(self.dest), SD_IMAGE=str(self.sd), CHECK_MOUNT="0", PING_URL="https://hc.example/abc", TODAY=today,
                   MIN_FREE_PCT="0", SD_ROOM_GB="0")
        env.update(extra)
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)

    def snaps(self):
        return sorted(p.name for p in (self.dest / "naspi-snapshots").iterdir())

    def pinged(self):
        return self.pings.read_text().split() if self.pings.exists() else []

    def test_first_run(self):
        r = self.run_it()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        snap = self.dest / "naspi-snapshots" / "2026-11-15"
        self.assertEqual((snap / "judicom" / "contacts.txt").read_text(), "555-555-0100 | Someone\n")
        self.assertFalse((snap / ".cache").exists() or (snap / ".npm").exists())         # caches are left out
        images = list((self.dest / "naspi-sd-images").iterdir())
        self.assertEqual(len(images), 1)
        self.assertEqual(subprocess.run(["zstd", "-dc", str(images[0])], capture_output=True).stdout, self.sd.read_bytes())
        self.assertEqual(self.pinged(), ["https://hc.example/abc/start", "https://hc.example/abc"])

    def test_unchanged_files_are_shared_between_weeks(self):
        self.run_it("2026-11-15")
        (self.src / "judicom" / "events.txt").write_text("new\n")
        self.assertEqual(self.run_it("2026-11-22").returncode, 0)
        a, b = (self.dest / "naspi-snapshots" / d / "judicom" / "contacts.txt" for d in ("2026-11-15", "2026-11-22"))
        self.assertEqual(a.stat().st_ino, b.stat().st_ino)                                # a hard link: no new space
        self.assertFalse((self.dest / "naspi-snapshots" / "2026-11-15" / "judicom" / "events.txt").exists())
        self.assertIn("SD image of", self.run_it("2026-11-22").stdout)                      # the same image: not copied twice

    def test_keeps_the_newest_eight(self):
        for day in range(1, 11):
            self.assertEqual(self.run_it("2026-10-%02d" % day).returncode, 0)
        self.assertEqual(self.snaps(), ["2026-10-%02d" % d for d in range(3, 11)])

    def test_too_little_space_removes_old_snapshots_then_fails_and_says_so(self):
        for day in ("2026-11-01", "2026-11-08"):
            self.run_it(day)
        self.pings.unlink()
        r = self.run_it("2026-11-15", MIN_FREE_PCT="101")                                 # never enough
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.snaps(), ["2026-11-08"])                                     # the newest one always stays
        self.assertEqual(self.pinged(), ["https://hc.example/abc/start", "https://hc.example/abc/fail"])
        self.assertIn("nothing more of mine to remove", r.stdout)

    def test_a_failure_is_reported(self):
        r = self.run_it(SRC=str(self.src / "missing"))
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.pinged()[-1], "https://hc.example/abc/fail")
        self.assertNotIn("2026-11-15", self.snaps())                                       # no half snapshot passed off as one


if __name__ == "__main__":
    unittest.main()
