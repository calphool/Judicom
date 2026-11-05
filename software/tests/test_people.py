"""Tests for the people pictures: the NAS's serve_list.sh ("people-list" / "people"), judicom.sync.sync_people, judicom/faces.py and
the call screens with a face.  The drawing tests need pygame (skipped without it).   Run from the software folder:
python3 -m unittest -v"""
import hashlib
import io
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
try:
    import pygame
except ImportError:
    pygame = None

from judicom import config, sync
from judicom.machine import Mode, Party

SERVE_LIST = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "serve_list.sh"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tar_of(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, body in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            t.addfile(info, io.BytesIO(body))
    return buf.getvalue()


class Nas(unittest.TestCase):
    """A stand-in NAS: serve_list.sh run locally on a temporary /home/pi/judicom."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.nas_dir, self.here = root / "nas", root / "people"
        self.people = self.nas_dir / "people"
        self.people.mkdir(parents=True)
        self.script = root / "serve_list.sh"
        self.script.write_text(SERVE_LIST.read_text().replace("/home/pi/judicom/", str(self.nas_dir) + "/"))
        self.logged, self.fetches = [], 0

    def ask(self, request):
        r = subprocess.run(["sh", str(self.script)], capture_output=True,
                           env={"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": request})
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def sync(self):
        def fetcher():
            self.fetches += 1
            return self.ask("people")
        return sync.sync_people(lambda: self.ask("people-list").decode(), fetcher, str(self.here), self.logged.append)

    def names(self):
        return sorted(os.listdir(self.here)) if self.here.exists() else []


class ServeAndSync(Nas):
    def test_copies_the_pictures(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        (self.people / "Frank Smith.JPG").write_bytes(b"frank")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["Ann.png", "Frank Smith.JPG"])
        self.assertEqual((self.here / "Ann.png").read_bytes(), b"ann")
        self.assertIn("new or changed: Ann.png, Frank Smith.JPG", self.logged[-1])

    def test_unchanged_fetches_nothing(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        self.sync()
        self.assertEqual(self.fetches, 1)
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.fetches, 1)                                # only the list was asked for
        self.assertIn("unchanged: 1", self.logged[-1])

    def test_changed_and_removed(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        (self.people / "Frank.png").write_bytes(b"frank")
        self.sync()
        (self.people / "Ann.png").write_bytes(b"ann, a newer picture")
        (self.people / "Frank.png").unlink()
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), ["Ann.png"])
        self.assertEqual((self.here / "Ann.png").read_bytes(), b"ann, a newer picture")
        self.assertIn("removed: Frank.png", self.logged[-1])

    def test_other_files_and_too_big_ones_stay_on_the_nas(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        (self.people / "notes.txt").write_bytes(b"x")
        (self.people / ".hidden.png").write_bytes(b"x")
        (self.people / "clip.mp4").write_bytes(b"x")
        (self.people / "sub").mkdir()
        (self.people / "sub" / "Bob.png").write_bytes(b"x")
        with open(self.people / "Huge.jpg", "wb") as fh:
            fh.truncate(config.PEOPLE_MAX_FILE + 1)
        self.sync()
        self.assertEqual(self.names(), ["Ann.png"])

    def test_no_people_folder_on_the_nas(self):
        self.people.rmdir()
        self.assertEqual(self.ask("people-list"), b"")
        self.assertEqual(self.sync(), 0)
        self.assertEqual(self.names(), [])

    def test_nas_unreachable_changes_nothing(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        self.sync()

        def down():
            raise RuntimeError("cannot reach the NAS")
        self.assertEqual(sync.sync_people(down, down, str(self.here), self.logged.append), 1)
        self.assertEqual(self.names(), ["Ann.png"])
        self.assertIn("not updated", self.logged[-1])

    def test_a_damaged_download_changes_nothing(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        lister = lambda: self.ask("people-list").decode()                           # noqa: E731
        for bad in (b"not a tar file at all" * 30, tar_of({"Ann.png": b"something else"}), tar_of({})):
            with self.subTest(bad=bad[:20]):
                self.assertEqual(sync.sync_people(lister, lambda: bad, str(self.here), self.logged.append), 1)
                self.assertEqual(self.names(), [])

    def test_no_temporary_files_left(self):
        (self.people / "Ann.png").write_bytes(b"ann")
        self.sync()
        self.assertEqual(self.names(), ["Ann.png"])


class Listing(unittest.TestCase):
    def test_only_plain_picture_names(self):
        d = "a" * 64
        text = "\n".join(["%s  ./Ann.png" % d, "%s  ./x/../../etc/passwd.png" % d, "%s  ./.hidden.jpg" % d, "%s  ./notes.txt" % d,
                          "\\%s  ./odd\\nname.png" % d, "short  ./Bob.png", "%s  ./Aunt Sue.jpeg" % d, ""])
        self.assertEqual(sync.parse_people_list(text), {"Ann.png": d, "Aunt Sue.jpeg": d})

    def test_a_tar_cannot_write_outside_or_add_files(self):
        wanted = {"Ann.png": sha(b"ann")}
        got = sync.unpack_people(tar_of({"../../Ann.png": b"ann", "evil.png": b"x"}), wanted)
        self.assertEqual(got, {"Ann.png": b"ann"})                           # by its plain name, nothing else


@unittest.skipUnless(pygame, "pygame is not installed")
class FacesAndScreens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))

    @classmethod
    def tearDownClass(cls):
        from judicom import draw
        draw.reset()
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        img = pygame.Surface((300, 200))                                     # wide: red middle, blue sides
        img.fill((0, 0, 255))
        pygame.draw.rect(img, (255, 0, 0), (50, 0, 200, 200))
        pygame.image.save(img, str(self.dir / "Ann.png"))
        self.logged = []

    def faces(self):
        from judicom.faces import Faces
        return Faces(str(self.dir), log=self.logged.append)

    def test_matched_by_name_and_cropped_square(self):
        f = self.faces()
        face = f.get("ann", 100)
        self.assertEqual(face.get_size(), (100, 100))
        self.assertEqual(tuple(face.get_at((50, 50)))[:3], (255, 0, 0))
        self.assertEqual(tuple(face.get_at((5, 50)))[:3], (255, 0, 0))     # the blue sides were cropped off
        self.assertEqual(face.get_at((0, 0))[3], 0)                          # rounded corner: transparent
        self.assertIsNone(f.get("Frank", 100))
        self.assertIsNone(f.get("", 100))

    def test_underscores_and_spaces(self):
        os.rename(self.dir / "Ann.png", self.dir / "Aunt_Sue.png")
        self.assertIsNotNone(self.faces().get("Aunt  Sue", 50))

    def test_a_broken_picture_is_skipped(self):
        (self.dir / "Bob.jpg").write_bytes(b"not a picture")
        f = self.faces()
        self.assertIsNone(f.get("Bob", 50))
        self.assertIsNone(f.get("Bob", 50))
        self.assertEqual(len(self.logged), 1)                                # said once

    def test_screens_show_the_face(self):
        from judicom.call_view import CallView
        view = CallView({"left": Party("Ann", "daughter", "ann")}, self.faces())
        surf = pygame.Surface((config.SCREEN_W, config.SCREEN_H))
        for mode in (Mode.DIALING, Mode.CALLING, Mode.ONGOING, Mode.INCOMING):
            for t in (0.0, 0.2, 0.35, 1.5):
                with self.subTest(mode=mode, t=t):
                    view.draw(surf, mode, Party("Ann", "daughter", "ann"), t)
                    self.assertEqual(tuple(surf.get_at((config.SCREEN_W // 2, 300)))[:3], (255, 0, 0))
        view.draw(surf, Mode.ENDED, Party("Ann", "daughter", "ann"), 0.35)       # the handset there, not the face
        self.assertNotEqual(tuple(surf.get_at((config.SCREEN_W // 2, 300)))[:3], (255, 0, 0))
        view.draw(surf, Mode.INCOMING, Party(dial="312-555-0199"), 0.35)        # unknown caller: the handset
        self.assertNotIn((255, 0, 0), {tuple(surf.get_at((x, y)))[:3] for x in range(0, 600, 20) for y in range(0, 1024, 20)})


if __name__ == "__main__":
    unittest.main()
