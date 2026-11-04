"""Tests for the NAS's mail importer (deploy/nas/jellyfin-mail-importer/import_photos.py): emails with pictures -> photo folders,
and the caption lines in the email -> a .meta file the Judicom understands.  Gmail is a stand-in; nothing leaves this computer.
Run from the software folder:   python3 -m unittest -v"""
import contextlib
import importlib.util
import io
import sys
import tempfile
import types
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

from judicom.photos import load_caption

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "jellyfin-mail-importer" / "import_photos.py"


def load_importer():
    """Import the script with small stand-ins for rapidfuzz and requests (only installed in its venv on the NAS)."""
    def extract_one(subject, folders, scorer=None, processor=None):
        for name in folders:                                  # good enough for these tests: a folder named in the subject
            if name.lower() in subject.lower():
                return name, 100, 0
        return (folders[0], 10, 0) if folders else None
    rapidfuzz = types.ModuleType("rapidfuzz")
    rapidfuzz.process = types.SimpleNamespace(extractOne=extract_one)
    rapidfuzz.fuzz = types.SimpleNamespace(WRatio=None)
    requests = types.ModuleType("requests")
    requests.post = mock.Mock(return_value=types.SimpleNamespace(status_code=204, text=""))
    with mock.patch.dict(sys.modules, {"rapidfuzz": rapidfuzz, "requests": requests}):
        spec = importlib.util.spec_from_file_location("import_photos", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


importer = load_importer()


class FakeGmail:
    """Stands in for imaplib.IMAP4_SSL("imap.gmail.com"): serves the given messages as unread."""

    def __init__(self, messages):
        self.messages = {str(i + 1).encode(): m.as_bytes() for i, m in enumerate(messages)}
        self.flags = {}

    def __call__(self, host):
        return self

    def login(self, user, password):
        pass

    def select(self, box):
        pass

    def search(self, charset, criterion):
        return "OK", [b" ".join(self.messages)]

    def fetch(self, msg_id, what):
        return "OK", [(b"", self.messages[msg_id])]

    def store(self, msg_id, op, flag):
        self.flags[msg_id] = flag

    def expunge(self):
        pass

    def logout(self):
        pass


def mail(subject, text=None, html=None, files=(("IMG_1234.jpg", b"jpeg data"),)):
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = subject, "ann@example.com", "photos@example.com"
    if text is not None:
        m.set_content(text)
    if html is not None:
        if text is None:
            m.set_content(html, subtype="html")
        else:
            m.add_alternative(html, subtype="html")
    for name, data in files:
        maintype, subtype = ("video", "quicktime") if name.endswith(".mov") else ("image", "jpeg")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return m


CAPTION = "people: Ann and Joe\nrelationship: Your daughter and son-in-law\ntaken: 2025-12-24\n"


class Importer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for folder in ("Judi", "Christmas", "Misc"):
            (self.root / folder).mkdir()
        self.judi = self.root / "Judi"

    def run_with(self, *messages, env=None):
        settings = {"GMAIL_USER": "u", "GMAIL_APP_PASSWORD": "p", "PHOTO_ROOT": str(self.root), "FALLBACK_FOLDER": "Misc"}
        settings.update(env or {})
        gmail = FakeGmail(messages)
        out = io.StringIO()
        with mock.patch.object(importer, "load_env", return_value=settings), \
                mock.patch.object(importer.imaplib, "IMAP4_SSL", gmail), contextlib.redirect_stdout(out):
            importer.main()
        return out.getvalue(), gmail

    def names(self, folder):
        return sorted(p.name for p in folder.iterdir())

    def test_caption_lines_make_a_meta_file_the_judicom_reads(self):
        log, _ = self.run_with(mail("For Judi", CAPTION))
        self.assertEqual(self.names(self.judi), ["IMG_1234.jpg", "IMG_1234.meta"])
        cap = load_caption(self.judi / "IMG_1234.jpg")             # the Judicom's own reader
        self.assertEqual((cap.people, cap.relationship, cap.taken_text),
                         ("Ann and Joe", "Your daughter and son-in-law", "December 24, 2025"))
        self.assertIn("Saved caption:", log)

    def test_without_caption_lines_nothing_changes(self):
        _, gmail = self.run_with(mail("Judi", "Merry Christmas Mom!"))
        self.assertEqual(self.names(self.judi), ["IMG_1234.jpg"])
        self.assertEqual(gmail.flags[b"1"], "\\Deleted")             # handled exactly as before

    def test_no_text_at_all(self):
        self.run_with(mail("Judi"))
        self.assertEqual(self.names(self.judi), ["IMG_1234.jpg"])

    def test_other_folders_get_no_meta(self):
        self.run_with(mail("Christmas 2025", CAPTION))
        self.assertEqual(self.names(self.root / "Christmas"), ["IMG_1234.jpg"])
        self.assertEqual(self.names(self.judi), [])

    def test_caption_folders_setting(self):
        self.run_with(mail("Christmas 2025", CAPTION), env={"CAPTION_FOLDERS": "Judi, Christmas"})
        self.assertIn("IMG_1234.meta", self.names(self.root / "Christmas"))

    def test_every_picture_of_the_email_gets_it_but_not_videos(self):
        self.run_with(mail("Judi", CAPTION, files=(("a.jpg", b"1"), ("b.png", b"2"), ("clip.mov", b"3"))))
        self.assertEqual(self.names(self.judi), ["a.jpg", "a.meta", "b.meta", "b.png", "clip.mov"])

    def test_a_renamed_picture_gets_the_matching_meta_name(self):
        (self.judi / "IMG_1234.jpg").write_bytes(b"an older picture")
        self.run_with(mail("Judi", CAPTION))
        renamed = [n for n in self.names(self.judi) if n.startswith("IMG_1234_") and n.endswith(".jpg")]
        self.assertEqual(len(renamed), 1)
        self.assertTrue((self.judi / renamed[0].replace(".jpg", ".meta")).exists())
        self.assertFalse((self.judi / "IMG_1234.meta").exists())     # the older picture's caption is not invented

    def test_an_existing_meta_is_never_replaced(self):
        (self.judi / "IMG_1234.meta").write_text("people: Someone else\n")
        self.run_with(mail("Judi", CAPTION, files=(("IMG_1234.jpg", b"x"),)))
        self.assertEqual((self.judi / "IMG_1234.meta").read_text(), "people: Someone else\n")

    def test_html_only_email(self):
        self.run_with(mail("Judi", html="<div>People: <b>Hannah</b></div><div>Relationship: Your granddaughter</div>"))
        cap = load_caption(self.judi / "IMG_1234.jpg")
        self.assertEqual((cap.people, cap.relationship), ("Hannah", "Your granddaughter"))


class Parsing(unittest.TestCase):
    def test_words_and_capitals(self):
        self.assertEqual(importer.parse_caption("Names = Frank\nRELATION: Your husband\nWhen: 2019-06"),
                         {"people": "Frank", "relationship": "Your husband", "taken": "2019-06"})

    def test_only_the_senders_own_words(self):
        text = ("Here you go!\npeople: Bryson\n\n-- \nAnn\npeople: not this\n")
        self.assertEqual(importer.parse_caption(text), {"people": "Bryson"})
        forwarded = ("taken: 2024\n---------- Forwarded message ---------\nFrom: Bob\nDate: Mon, 3 Nov 2026\n")
        self.assertEqual(importer.parse_caption(forwarded), {"taken": "2024"})
        reply = "relationship: Your sister\nOn Mon, Nov 3, 2026 at 9:00 AM Joe wrote:\n> people: someone\n"
        self.assertEqual(importer.parse_caption(reply), {"relationship": "Your sister"})

    def test_first_line_counts_and_values_are_tidied(self):
        self.assertEqual(importer.parse_caption("people:   Ann    and  Joe  \npeople: Bob"), {"people": "Ann and Joe"})
        self.assertEqual(len(importer.parse_caption("people: " + "x" * 500)["people"]), 200)

    def test_not_captions(self):
        self.assertEqual(importer.parse_caption("Peoples are great\nwho knows\nhttp://x.example/a:b"), {})


if __name__ == "__main__":
    unittest.main()
