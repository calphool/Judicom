"""Tests for deploy/judicom/copy_used_blocks.py: the copy itself, and keeping its position for the backup's progress bar.
They need Linux's file calls, so they are skipped on Windows.   Run from the software folder:   python3 -m unittest -v"""
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("copy_used_blocks",
                                              Path(__file__).resolve().parents[2] / "deploy" / "judicom" / "copy_used_blocks.py")
copier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copier)

MB = 1024 * 1024
BLOCK = 4096
BLOCKS = 10 * MB // BLOCK                  # a 10 MB "partition": three 4 MB windows, the last one short
DUMPE2FS = """Block count:              %d
Block size:               %d
  Free blocks: 1-%d
""" % (BLOCKS, BLOCK, BLOCKS - 2)          # only the first block and the last one are in use


@unittest.skipUnless(hasattr(os, "pread"), "needs Linux")
class Copy(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.device = self.dir / "partition"
        self.device.write_bytes(b"x" * (10 * MB))
        self.position = self.dir / "position"

    def copied(self, **kw):
        out = io.BytesIO()
        copier.copy(str(self.device), out, dumpe2fs_text=DUMPE2FS, **kw)
        return out.getvalue()

    def test_used_blocks_are_copied_and_free_ones_are_zeros(self):
        want = b"x" * BLOCK + bytes(10 * MB - 2 * BLOCK) + b"x" * BLOCK
        self.assertEqual(self.copied(), want)

    def test_the_position_goes_up_in_steps_and_ends_at_the_whole_size(self):
        seen = []
        self.copied(note=lambda position, total: seen.append((position, total)))
        self.assertEqual(seen, [(0, 10 * MB), (4 * MB, 10 * MB), (8 * MB, 10 * MB), (10 * MB, 10 * MB)])

    def test_keeping_the_position_does_not_change_the_copy(self):
        self.assertEqual(self.copied(note=copier.position_keeper(str(self.position))), self.copied())

    def test_the_file_holds_mb_done_and_the_whole_size(self):
        self.copied(note=copier.position_keeper(str(self.position)))
        self.assertEqual(self.position.read_text().split(), ["10", "10"])

    def test_a_shorter_number_leaves_nothing_of_a_longer_one_behind(self):
        note = copier.position_keeper(str(self.position))
        note(12345 * MB, 12345 * MB)
        note(7 * MB, 12345 * MB)
        self.assertEqual(self.position.read_text().split(), ["7", "12345"])

    def test_a_position_file_that_cannot_be_written_does_not_stop_the_copy(self):
        note = copier.position_keeper(str(self.dir / "no_such_folder" / "position"))
        self.assertEqual(self.copied(note=note), self.copied())

    def test_no_position_file_is_fine(self):
        self.assertEqual(self.copied(note=copier.position_keeper(None)), self.copied())


if __name__ == "__main__":
    unittest.main()
