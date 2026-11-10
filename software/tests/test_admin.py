"""Tests for deploy/nas/admin/judicom_admin.py (the housekeeping website), with Flask's test client and temporary folders.
Skipped where Flask or Pillow is not installed.   Run from the software folder:   python3 -m unittest -v"""
import contextlib
import importlib.util
import io
import json
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest import mock

try:
    import flask  # noqa: F401
    from PIL import Image
    HAVE = True
except ImportError:
    HAVE = False

ADMIN = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "admin" / "judicom_admin.py"
if HAVE:
    spec = importlib.util.spec_from_file_location("judicom_admin", ADMIN)
    admin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admin)

CONTACTS = """# number | name | relationship | button
212-555-0142 | Frank | husband  | left
312-555-0187 | Ann   | daughter | right
312-555-0123 | Hannah | granddaughter
"""
EVENTS = """# Judi's events.
# One per line.

# ---- holidays
12-25 | Christmas
4th Thursday of November | Thanksgiving

# ---- family
04-22 | Ann's birthday
"""


def picture(w, h, color=(200, 30, 30), fmt="JPEG"):
    out = io.BytesIO()
    Image.new("RGB", (w, h), color).save(out, format=fmt)
    return out.getvalue()


@unittest.skipUnless(HAVE, "Flask / Pillow are not installed")
class Site(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.j, self.photos, self.trash = root / "judicom", root / "Photos" / "Judi", root / "deleted"
        self.j.mkdir()
        self.photos.mkdir(parents=True)
        (self.j / "contacts.txt").write_text(CONTACTS)
        (self.j / "events.txt").write_text(EVENTS)
        self.applied = root / "applied"
        apply = root / "fake_apply.sh"
        apply.write_text("#!/bin/sh\necho applied >> %s\n" % self.applied)
        apply.chmod(0o755)
        self.now = [1000.0]
        self.passwords_tried = []

        def check(user, password):
            self.passwords_tried.append((user, password))
            return (user, password) == ("pi", "right-password")
        s = admin.Settings(judicom_dir=self.j, photos_dir=self.photos, trash_dir=self.trash, apply=[str(apply)], check_password=check,
                           clock=lambda: self.now[0])
        self.settings = s
        self.app = admin.create_app(s)
        self.client = self.app.test_client()
        self.sign_in()

    def sign_in(self, user="pi", password="right-password", address="192.168.1.20", **extra):
        form = self.client.get("/login", base_url="http://naspi.local:8080", environ_base={"REMOTE_ADDR": address})
        token = re.search(r'name="token" value="([^"]+)"', form.get_data(as_text=True)).group(1)
        return self.client.post("/login", data=dict(extra, user=user, password=password, token=token), base_url="http://naspi.local:8080",
                                environ_base={"REMOTE_ADDR": address})

    def get(self, url, **kw):
        kw.setdefault("environ_base", {"REMOTE_ADDR": "192.168.1.20"})
        return self.client.get(url, base_url="http://naspi.local:8080", **kw)

    def token(self):
        return re.search(r'name="token" value="([^"]+)"', self.get("/callers").get_data(as_text=True)).group(1)

    def post(self, url, data, token=True, **kw):
        if token:
            data = dict(data, token=self.token())
        kw.setdefault("environ_base", {"REMOTE_ADDR": "192.168.1.20"})
        return self.client.post(url, data=data, base_url="http://naspi.local:8080", **kw)

    def callers_form(self, rows):
        d = {}
        for i, r in enumerate(rows, 1):
            for k, v in zip(("number", "name", "relationship", "button"), r):
                d["%s-%d" % (k, i)] = v
        return d

    # ---- who may use it
    def test_only_home_and_tailscale(self):
        for addr, ok in (("192.168.1.20", True), ("100.64.0.2", True), ("127.0.0.1", True), ("8.8.8.8", False),
                         ("203.0.113.9", False)):
            with self.subTest(addr=addr):
                r = self.get("/", environ_base={"REMOTE_ADDR": addr})
                self.assertEqual(r.status_code, 200 if ok else 403)

    def test_other_host_names_are_refused(self):           # DNS rebinding: a page elsewhere pointing its own name at the NAS
        for url in ("/", "/login"):
            r = self.client.get(url, base_url="http://evil.example.com", environ_base={"REMOTE_ADDR": "192.168.1.20"})
            self.assertEqual(r.status_code, 403, url)
        for host in ("naspi.local:8080", "192.168.1.2:8080", "100.64.0.1:8080", "naspi-1.tail1234.ts.net:8080"):
            # allowed: not refused (whether it then shows the page or sends you to sign in is up to the sign-in check)
            for url in ("/", "/login"):
                r = self.client.get(url, base_url="http://" + host, environ_base={"REMOTE_ADDR": "192.168.1.20"})
                self.assertIn(r.status_code, (200, 302), (host, url))

    def test_a_post_without_the_token_changes_nothing(self):
        r = self.post("/callers", self.callers_form([("312-555-0999", "Scammer", "", "")]), token=False)
        self.assertEqual(r.status_code, 403)
        self.assertEqual((self.j / "contacts.txt").read_text(), CONTACTS)

    def test_pages_show(self):
        for url in ("/", "/callers", "/events", "/people", "/photos"):
            with self.subTest(url=url):
                self.assertEqual(self.get(url).status_code, 200)
        self.assertIn("Frank", self.get("/").get_data(as_text=True))

    # ---- callers
    def test_save_callers_and_apply(self):
        r = self.post("/callers", self.callers_form([("212 555 0142", "Frank", "husband", "left"), ("(312) 555-0187", "Ann",
                                                    "daughter", "right"), ("312.555.0177", "Bob", "brother", "")]))
        self.assertEqual(r.status_code, 302)
        text = (self.j / "contacts.txt").read_text()
        self.assertIn("312-555-0177 | Bob", text)
        self.assertNotIn("Hannah", text)
        self.assertTrue(self.applied.exists())                               # the PBX was updated at once
        self.assertEqual(len(list((self.j / "history").glob("contacts.txt.*"))), 1)
        from judicom.contacts import parse
        people, buttons = parse(text)
        self.assertEqual(len(people), 3)
        self.assertEqual(buttons["left"].name, "Frank")

    def test_remove_a_caller(self):
        form = self.callers_form([("212-555-0142", "Frank", "husband", "left"), ("312-555-0187", "Ann", "daughter", "right"),
                                  ("312-555-0123", "Hannah", "granddaughter", "")])
        form["remove-3"] = "1"
        self.post("/callers", form)
        self.assertNotIn("Hannah", (self.j / "contacts.txt").read_text())

    def test_bad_callers_are_shown_and_nothing_is_saved(self):
        for rows, words in (([("555-0142", "Frank", "", "")], "10 digits"),
                            ([("212-555-0142", "Frank", "", "left"), ("312-555-0187", "Ann", "", "left")], "both on the left"),
                            ([("212-555-0142", "Frank", "", ""), ("212-555-0142", "Frank2", "", "")], "already listed"),
                            ([("212-555-0142", "", "", "")], "name is needed"),
                            ([("212-555-0142", "Cl|ark", "", "")], "may not contain"),
                            ([("212-555-0142", "Ann", "", ""), ("312-555-0187", "ann", "", "")], "two people are called")):
            with self.subTest(words=words):
                r = self.post("/callers", self.callers_form(rows))
                self.assertEqual(r.status_code, 400)
                self.assertIn(words, r.get_data(as_text=True))
                self.assertEqual((self.j / "contacts.txt").read_text(), CONTACTS)
        form = self.callers_form([("212-555-0142", "Frank", "", "")])
        form["remove-1"] = "1"
        r = self.post("/callers", form)
        self.assertIn("would be empty", r.get_data(as_text=True))
        self.assertFalse(self.applied.exists())

    # ---- events
    def events_form(self, rows):
        d = {}
        for i, (kind, when, what) in enumerate(rows, 1):
            d["kind-%d" % i], d["when-%d" % i], d["what-%d" % i] = kind, when, what
        return d

    def test_events_round_trip_keeps_the_header_and_headings(self):
        page = self.get("/events").get_data(as_text=True)
        self.assertIn("days to go", page)
        r = self.post("/events", self.events_form([("heading", "", "holidays"), ("event", "12-25", "Christmas"),
                                                   ("heading", "", "family"), ("event", "04-22", "Ann's birthday"),
                                                   ("event", "2030-11-08 10:30", "Visit from Ann")]))
        self.assertEqual(r.status_code, 302)
        text = (self.j / "events.txt").read_text()
        self.assertTrue(text.startswith("# Judi's events.\n# One per line.\n"))
        self.assertIn("# ---- family", text)
        self.assertIn("2030-11-08 10:30 | Visit from Ann", text)
        self.assertNotIn("Thanksgiving", text)
        from judicom.events import parse
        problems = []
        self.assertEqual(len(parse(text, problems.append)), 3)
        self.assertEqual(problems, [])

    def test_a_new_holiday_can_go_with_the_holidays(self):
        (self.j / "events.txt").write_text("# Judi's events.\n\n# ---- holidays\n12-25 | Christmas\n\n# ---- family\n04-22 | Ann's birthday\n")
        page = self.get("/events").get_data(as_text=True)
        self.assertIn('placeholder="add to holidays"', page)
        self.assertLess(page.index('placeholder="add to holidays"'), page.index('value="family"'))   # a blank row before "family"
        form = {}
        for k, v in re.findall(r'name="((?:kind|when|what)-\d+)"(?: value="([^"]*)")?', page):
            form[k] = v
        blank = re.search(r'name="what-(\d+)" placeholder="add to holidays"', page).group(1)
        form["when-" + blank], form["what-" + blank] = "12-18", "Ugly Sweater Day"
        self.assertEqual(self.post("/events", form).status_code, 302)
        text = (self.j / "events.txt").read_text()
        self.assertLess(text.index("Ugly Sweater Day"), text.index("# ---- family"))
        self.assertGreater(text.index("Ugly Sweater Day"), text.index("Christmas"))

    def test_sort_puts_each_section_in_calendar_order(self):
        rows = [("heading", "", "holidays"), ("event", "12-25", "Christmas"), ("event", "Easter", "Easter"),
                ("event", "4th Thursday of November", "Thanksgiving"), ("event", "01-01", "New Year's Day"),
                ("event", "Friday after 4th Thursday of November", "Black Friday"),
                ("heading", "", "family"), ("event", "04-22", "Ann's birthday"), ("event", "2026-03-01 2 PM", "Visit"),
                ("event", "02-10", "Joe's birthday")]
        form = self.events_form(rows)
        form["sort"] = "1"
        self.assertEqual(self.post("/events", form).status_code, 302)
        titles = [l.split("|")[-1].strip() for l in (self.j / "events.txt").read_text().splitlines() if l and not l.startswith("#")]
        self.assertEqual(titles, ["New Year's Day", "Easter", "Thanksgiving", "Black Friday", "Christmas",
                                  "Joe's birthday", "Visit", "Ann's birthday"])
        text = (self.j / "events.txt").read_text()
        self.assertLess(text.index("Christmas"), text.index("# ---- family"))       # nothing moves to another section

    def test_a_bad_date_is_shown_and_nothing_is_saved(self):
        r = self.post("/events", self.events_form([("event", "12-25", "Christmas"), ("event", "Dec 25th", "Oops")]))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Oops", r.get_data(as_text=True))
        self.assertEqual((self.j / "events.txt").read_text(), EVENTS)

    # ---- caller pictures
    def test_a_caller_picture_is_cropped_square_and_named(self):
        r = self.post("/people/upload", {"name": "Ann", "picture": (io.BytesIO(picture(1200, 900)), "IMG_0001.JPG")},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        img = Image.open(self.j / "people" / "Ann.png")
        self.assertEqual((img.format, img.size), ("PNG", (800, 800)))
        self.post("/people/upload", {"name": "Ann", "picture": (io.BytesIO(picture(500, 700, (0, 0, 200))), "b.png")},
                  content_type="multipart/form-data")
        self.assertEqual(sorted(p.name for p in (self.j / "people").iterdir()), ["Ann.png"])
        self.assertEqual(len(list((self.trash / "caller pictures").iterdir())), 1)       # the old one kept aside
        self.assertEqual(self.get("/people/img/Ann.png").status_code, 200)

    def test_only_callers_get_pictures_and_junk_is_refused(self):
        r = self.post("/people/upload", {"name": "Stranger", "picture": (io.BytesIO(picture(10, 10)), "a.jpg")},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.post("/people/upload", {"name": "Ann", "picture": (io.BytesIO(b"not a picture"), "a.jpg")},
                  content_type="multipart/form-data")
        self.assertFalse((self.j / "people").exists() and any((self.j / "people").iterdir()))

    def test_remove_a_caller_picture(self):
        (self.j / "people").mkdir()
        (self.j / "people" / "Ann.png").write_bytes(picture(10, 10, fmt="PNG"))
        self.post("/people/remove", {"file": "Ann.png"})
        self.assertFalse((self.j / "people" / "Ann.png").exists())
        self.assertEqual(self.post("/people/remove", {"file": "../contacts.txt"}).status_code, 404)

    # ---- photos
    def test_upload_photos_with_a_caption(self):
        r = self.post("/photos/upload", {"pictures": [(io.BytesIO(picture(400, 300)), "Beach day.jpg"),
                                                      (io.BytesIO(picture(4000, 3000)), "huge.png")],
                                         "people": "Ann and Hannah", "relationship": "", "taken": "Summer 2026"},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        names = sorted(p.name for p in self.photos.iterdir())
        self.assertEqual(names, ["Beach_day.jpg", "Beach_day.meta", "huge.jpg", "huge.meta"])
        self.assertEqual(Image.open(self.photos / "huge.jpg").size, (3000, 2250))      # shrunk
        self.assertEqual((self.photos / "Beach_day.meta").read_text(), "people: Ann and Hannah\ntaken: Summer 2026\n")
        from judicom.photos import load_caption
        self.assertEqual(load_caption(self.photos / "huge.jpg").people, "Ann and Hannah")

    def test_same_name_does_not_overwrite(self):
        (self.photos / "a.jpg").write_bytes(picture(10, 10))
        self.post("/photos/upload", {"pictures": [(io.BytesIO(picture(20, 20)), "a.jpg")]}, content_type="multipart/form-data")
        self.assertEqual(sorted(p.name for p in self.photos.iterdir()), ["a.jpg", "a_2.jpg"])

    def test_edit_and_clear_a_caption(self):
        (self.photos / "a.jpg").write_bytes(picture(10, 10))
        self.post("/photos/caption", {"file": "a.jpg", "people": "Joe", "relationship": "Your son-in-law", "taken": ""})
        self.assertEqual((self.photos / "a.meta").read_text(), "people: Joe\nrelationship: Your son-in-law\n")
        self.assertIn('value="Joe"', self.get("/photos").get_data(as_text=True))
        self.post("/photos/caption", {"file": "a.jpg", "people": "", "relationship": "", "taken": ""})
        self.assertFalse((self.photos / "a.meta").exists())

    def test_remove_a_photo_keeps_it_aside(self):
        (self.photos / "a.jpg").write_bytes(picture(10, 10))
        (self.photos / "a.meta").write_text("people: Joe\n")
        self.post("/photos/remove", {"file": "a.jpg"})
        self.assertEqual(list(self.photos.iterdir()), [])
        self.assertEqual(len(list((self.trash / "photos").iterdir())), 2)
        self.assertEqual(self.get("/photos/img/a.jpg").status_code, 404)

    def test_thumbnails(self):
        (self.photos / "a.jpg").write_bytes(picture(2000, 1000))
        r = self.get("/photos/img/a.jpg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(r.data)).size, (360, 180))
        self.assertEqual(self.get("/photos/img/missing.jpg").status_code, 404)

    # ---- See Judicom Now
    def fake_judicom(self, code):
        """Stands in for the ssh command: `code` is Python; `looks` is the file it marks each time it is run."""
        script = self.j / "fake_judicom.py"
        self.looks = self.j / "looks"
        script.write_text("import sys\nopen(%r, 'a').write('x')\n%s\n" % (str(self.looks), code))
        self.settings.screen = [sys.executable, str(script)]

    def test_the_page_is_on_the_menu_and_shows_the_picture(self):
        self.assertIn('href="/screen"', self.get("/").get_data(as_text=True))
        page = self.get("/screen").get_data(as_text=True)
        self.assertIn("See Judicom Now", page)
        self.assertIn('fetch("/screen.png"', page)

    def test_the_picture_comes_from_the_judicom_and_is_never_kept_by_the_browser(self):
        self.fake_judicom("sys.stdout.buffer.write(b'\\x89PNG picture')")
        r = self.get("/screen.png")
        self.assertEqual((r.status_code, r.mimetype, r.data), (200, "image/png", b"\x89PNG picture"))
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_two_viewers_at_once_share_one_look(self):
        self.fake_judicom("sys.stdout.buffer.write(b'\\x89PNG')")
        self.get("/screen.png")
        self.get("/screen.png")
        self.assertEqual(self.looks.read_text(), "x")

    def test_a_look_that_has_gone_stale_is_taken_again(self):
        self.fake_judicom("sys.stdout.buffer.write(b'\\x89PNG')")
        self.get("/screen.png")
        with mock.patch.object(admin, "SCREEN_FRESH", 0):
            self.get("/screen.png")
        self.assertEqual(self.looks.read_text(), "xx")

    def test_a_judicom_that_does_not_answer_is_said_plainly_and_tried_again(self):
        self.fake_judicom("sys.exit(255)")
        self.assertEqual(self.get("/screen.png").status_code, 503)
        self.assertEqual(self.get("/screen.png").status_code, 503)
        self.assertEqual(self.looks.read_text(), "xx")              # a failure is not remembered

    def test_something_that_is_not_a_picture_is_not_passed_on(self):
        self.fake_judicom("print('Welcome to the Judicom')")
        self.assertEqual(self.get("/screen.png").status_code, 503)

    def test_a_missing_ssh_is_not_a_crash(self):
        self.settings.screen = [str(self.j / "no_such_program")]
        self.assertEqual(self.get("/screen.png").status_code, 503)

    def test_addresses_from_outside_cannot_see_the_screen(self):
        self.fake_judicom("sys.stdout.buffer.write(b'\\x89PNG')")
        self.assertEqual(self.get("/screen.png", environ_base={"REMOTE_ADDR": "8.8.8.8"}).status_code, 403)
        self.assertFalse(self.looks.exists())

    # ---- sending Judi a message
    def fake_nas_request(self, message=0, messages="{}"):
        """Stands in for ssh and nas_request.py: keeps what it was sent in `received`."""
        script = self.j / "fake_request.py"
        self.received = self.j / "received"
        script.write_text("import sys\nif sys.argv[1:] == ['message']:\n"
                          "    open(%r, 'wb').write(sys.stdin.buffer.read())\n"
                          "    if %r: sys.exit('nas_request: 20 messages are already waiting for Judi')\n"
                          "    print('ok')\n"
                          "else:\n    print(%r)\n" % (str(self.received), message, messages))
        self.settings.screen = [sys.executable, str(script)]

    def send(self, sender="Ann", text="Hi Mom"):
        return self.post("/screen/message", {"from": sender, "text": text})

    def sent_rows(self):
        return self.get("/screen/sent").get_json()

    def test_the_form_offers_only_the_people_in_the_caller_list(self):
        page = self.get("/screen").get_data(as_text=True)
        names = re.findall(r"<option(?: selected)?>([^<]+)</option>", page)
        self.assertEqual(names, [c["name"] for c in admin.read_callers(self.settings)])
        self.assertTrue(names)

    def first_caller(self):
        return admin.read_callers(self.settings)[0]["name"]

    def test_a_message_goes_to_the_judicom(self):
        self.fake_nas_request()
        r = self.send(self.first_caller())
        self.assertEqual(r.status_code, 302)
        got = json.loads(self.received.read_text())
        self.assertEqual((got["from"], got["text"]), (self.first_caller(), "Hi Mom"))
        self.assertRegex(got["id"], r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")

    def test_someone_not_in_the_caller_list_cannot_be_the_sender(self):
        self.fake_nas_request()
        r = self.send("The Bank")
        self.assertIn("Choose who the message is from", r.get_data(as_text=True))
        self.assertFalse(self.received.exists())

    def test_empty_and_too_long_are_refused_and_what_was_typed_is_kept(self):
        self.fake_nas_request()
        self.assertIn("Type a message first", self.send(self.first_caller(), "   ").get_data(as_text=True))
        r = self.send(self.first_caller(), "x" * 201)
        self.assertIn("too long", r.get_data(as_text=True))
        self.assertIn("x" * 201, r.get_data(as_text=True))
        self.assertFalse(self.received.exists())

    def test_emoji_are_taken_out_and_the_sender_is_told(self):
        self.fake_nas_request()
        r = self.post("/screen/message", {"from": self.first_caller(), "text": "Hi \U0001F60A Mom"}, follow_redirects=True)
        self.assertEqual(json.loads(self.received.read_text())["text"], "Hi Mom")
        self.assertIn("without the emoji", r.get_data(as_text=True))

    def test_a_judicom_that_does_not_answer_is_said_and_what_was_typed_is_kept(self):
        self.fake_judicom("sys.exit(255)")
        r = self.send(self.first_caller(), "Hello there")
        self.assertIn("did not take the message", r.get_data(as_text=True))
        self.assertIn("Hello there", r.get_data(as_text=True))
        self.assertEqual(self.sent_rows(), [])

    def test_the_old_key_that_only_sends_pictures_counts_as_not_sent(self):
        self.fake_judicom("sys.stdout.buffer.write(b'\\x89PNG')")
        self.assertIn("did not take the message", self.send(self.first_caller()).get_data(as_text=True))

    def test_a_refusal_gives_the_judicom_s_reason(self):
        self.fake_nas_request(message=1)
        self.assertIn("20 messages are already waiting", self.send(self.first_caller()).get_data(as_text=True))

    def test_without_the_token_nothing_is_sent(self):
        self.fake_nas_request()
        r = self.post("/screen/message", {"from": self.first_caller(), "text": "Hi"}, token=False)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(self.received.exists())

    def test_it_says_waiting_and_then_when_it_was_read(self):
        self.fake_nas_request()
        self.send(self.first_caller())
        self.assertEqual(self.sent_rows()[0]["status"], "Waiting for Judi")
        message_id = json.loads(self.received.read_text())["id"]
        today = admin.datetime.datetime.now().replace(hour=15, minute=12, second=0, microsecond=0)
        self.fake_nas_request(messages=json.dumps({message_id: today.isoformat()}))
        with mock.patch.object(admin, "SCREEN_EVERY", 0):
            self.assertEqual(self.sent_rows()[0]["status"], "Read at 03:12 PM".replace("03", "3"))

    def test_once_all_are_read_the_judicom_is_left_alone(self):
        self.fake_nas_request()
        self.send(self.first_caller())
        message_id = json.loads(self.received.read_text())["id"]
        self.fake_nas_request(messages=json.dumps({message_id: "2026-11-05T09:05:00"}))
        with mock.patch.object(admin, "SCREEN_EVERY", 0):
            self.assertEqual(self.sent_rows()[0]["status"], "Read at 9:05 AM on Nov 05")
            self.settings.screen = [str(self.j / "no_such_program")]
            self.assertEqual(self.sent_rows()[0]["status"], "Read at 9:05 AM on Nov 05")

    def test_a_judicom_that_cannot_say_leaves_it_waiting(self):
        self.fake_nas_request()
        self.send(self.first_caller())
        self.settings.screen = [str(self.j / "no_such_program")]
        with mock.patch.object(admin, "SCREEN_EVERY", 0):
            self.assertEqual(self.sent_rows()[0]["status"], "Waiting for Judi")

    def test_a_message_is_written_safely_into_the_page(self):
        self.fake_nas_request()
        r = self.send(self.first_caller(), "x" * 300 + "</textarea><script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)", r.get_data(as_text=True))

    # ---- signing in
    def signed_out(self):
        self.client = self.app.test_client()

    def test_every_page_needs_signing_in(self):
        self.signed_out()
        checked = 0
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint == "login":
                continue
            url = re.sub(r"<[^>]+>", "x", rule.rule)
            for method in rule.methods & {"GET", "POST"}:
                with self.subTest(url=url, method=method):
                    r = (self.get(url) if method == "GET" else
                         self.client.post(url, data={}, base_url="http://naspi.local:8080", environ_base={"REMOTE_ADDR": "192.168.1.20"}))
                    self.assertIn(r.status_code, (302, 401))
                    if r.status_code == 302:
                        self.assertIn("/login", r.headers["Location"])
                    checked += 1
        self.assertGreater(checked, 15)

    def test_a_signed_out_post_changes_nothing_even_with_the_token(self):
        token = self.token()
        before = (self.j / "contacts.txt").read_text()
        self.signed_out()
        r = self.client.post("/callers", data=dict(self.callers_form([("312-555-0999", "Stranger", "", "")]), token=token),
                             base_url="http://naspi.local:8080", environ_base={"REMOTE_ADDR": "192.168.1.20"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual((self.j / "contacts.txt").read_text(), before)

    def test_the_scripts_of_the_screen_page_hear_401(self):
        self.signed_out()
        self.assertEqual(self.get("/screen.png").status_code, 401)
        self.assertEqual(self.get("/screen/sent").status_code, 401)

    def test_the_sign_in_page_shows_no_menu(self):
        self.signed_out()
        page = self.get("/login").get_data(as_text=True)
        self.assertNotIn("Caller pictures", page)
        self.assertIn('type="password"', page)

    def test_the_right_password_goes_on_to_the_page_asked_for(self):
        self.signed_out()
        where = self.get("/events?x=1").headers["Location"]
        self.assertIn("next=", where)
        r = self.sign_in(next="/events?x=1")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/events?x=1"))
        self.assertEqual(self.get("/events").status_code, 200)

    def test_a_wrong_password_stays_out(self):
        self.signed_out()
        r = self.sign_in(password="wrong")
        self.assertEqual(r.status_code, 401)
        self.assertIn("not right", r.get_data(as_text=True))
        self.assertEqual(self.get("/callers").status_code, 302)

    def test_only_pi_may_sign_in_whatever_the_password(self):
        self.signed_out()
        self.passwords_tried.clear()
        for user in ("joe", "root", "PI", "pi ", ""):
            self.assertEqual(self.sign_in(user=user).status_code, 401)
        self.assertEqual(self.passwords_tried, [])
        self.assertEqual(self.get("/callers").status_code, 302)

    def test_an_empty_or_absurd_password_never_reaches_pam(self):
        self.signed_out()
        self.passwords_tried.clear()
        self.sign_in(password="")
        self.sign_in(password="x" * 5000)
        self.assertEqual(self.passwords_tried, [])

    def test_too_many_wrong_tries_lock_that_address_out_for_a_while(self):
        self.signed_out()
        for _ in range(admin.LOGIN_TRIES):
            self.sign_in(password="wrong")
        self.passwords_tried.clear()
        r = self.sign_in()
        self.assertEqual(r.status_code, 401)
        self.assertIn("Too many", r.get_data(as_text=True))
        self.assertEqual(self.passwords_tried, [])              # not even asked: guessing goes nowhere
        self.assertEqual(self.sign_in(address="192.168.1.21").status_code, 302)      # someone else is not locked out
        self.signed_out()
        self.now[0] += admin.LOGIN_LOCK_SECONDS
        self.assertEqual(self.sign_in().status_code, 302)

    def test_old_wrong_tries_are_forgotten(self):
        self.signed_out()
        for _ in range(admin.LOGIN_TRIES - 1):
            self.sign_in(password="wrong")
        self.now[0] += admin.LOGIN_LOCK_SECONDS
        self.sign_in(password="wrong")
        self.assertEqual(self.sign_in().status_code, 302)

    def test_a_right_password_clears_the_count(self):
        self.signed_out()
        for _ in range(admin.LOGIN_TRIES - 1):
            self.sign_in(password="wrong")
        self.sign_in()
        self.signed_out()
        self.sign_in(password="wrong")
        self.assertIn("not right", self.sign_in(password="wrong").get_data(as_text=True))

    def test_signing_in_needs_the_form_token(self):
        self.signed_out()
        r = self.client.post("/login", data={"user": "pi", "password": "right-password"}, base_url="http://naspi.local:8080",
                             environ_base={"REMOTE_ADDR": "192.168.1.20"})
        self.assertEqual(r.status_code, 403)

    def test_a_sign_in_runs_out(self):
        self.assertEqual(self.get("/callers").status_code, 200)
        self.now[0] += admin.LOGIN_HOURS * 3600 - 1
        self.assertEqual(self.get("/callers").status_code, 200)
        self.now[0] += 1
        self.assertEqual(self.get("/callers").status_code, 302)

    def test_signing_out(self):
        self.assertIn("Sign out", self.get("/").get_data(as_text=True))
        self.assertEqual(self.post("/logout", {}).status_code, 302)
        self.assertEqual(self.get("/callers").status_code, 302)

    def test_a_restart_signs_everyone_out(self):
        self.signed_out()
        cookie = self.sign_in().headers["Set-Cookie"].split(";")[0]
        same = dict(base_url="http://naspi.local:8080", environ_base={"REMOTE_ADDR": "192.168.1.20"}, headers={"Cookie": cookie})
        self.assertEqual(self.app.test_client(use_cookies=False).get("/callers", **same).status_code, 200)
        restarted = admin.create_app(self.settings).test_client(use_cookies=False)
        self.assertEqual(restarted.get("/callers", **same).status_code, 302)

    def test_it_only_goes_on_to_pages_of_this_site(self):
        self.signed_out()
        for bad in ("//evil.example/", "https://evil.example/", "/\\evil.example", "/\t/evil.example", "\\evil.example", "evil"):
            with self.subTest(bad=bad):
                self.signed_out()
                r = self.sign_in(next=bad)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(urlsplit(r.headers["Location"]).path, "/")
                self.assertNotIn("evil", r.headers["Location"])

    def test_the_cookie_is_kept_from_scripts_and_other_sites(self):
        self.signed_out()
        cookie = self.sign_in().headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_a_password_is_never_printed(self):
        self.signed_out()
        out = io.StringIO()
        with contextlib.redirect_stderr(out), contextlib.redirect_stdout(out):
            self.sign_in(password="my-secret-word")
        self.assertIn("wrong sign-in 1 from 192.168.1.20", out.getvalue())
        self.assertNotIn("my-secret-word", out.getvalue())

    def test_the_check_says_no_when_pam_is_missing_or_fails(self):
        out = io.StringIO()
        with mock.patch.dict(sys.modules, {"pam": None}), contextlib.redirect_stderr(out):
            self.assertFalse(admin.pam_check("pi", "my-secret-word"))
        broken = mock.Mock()
        broken.authenticate.side_effect = ValueError("my-secret-word")
        with mock.patch.dict(sys.modules, {"pam": broken}), contextlib.redirect_stderr(out):
            self.assertFalse(admin.pam_check("pi", "my-secret-word"))
        self.assertNotIn("my-secret-word", out.getvalue())

    def test_the_check_says_yes_only_for_true(self):
        answer = mock.Mock()
        answer.authenticate.return_value = True
        with mock.patch.dict(sys.modules, {"pam": answer}):
            self.assertTrue(admin.pam_check("pi", "pw"))
        answer.authenticate.assert_called_once_with("pi", "pw", service="login", resetcreds=False)
        answer.authenticate.return_value = 1
        with mock.patch.dict(sys.modules, {"pam": answer}):
            self.assertFalse(admin.pam_check("pi", "pw"))


@unittest.skipUnless(HAVE and shutil.which("openssl"), "needs Flask, Pillow and openssl")
class RealHttps(unittest.TestCase):
    """A real server on a real socket: the test client never goes near the handshake."""

    def serve(self, context):
        from werkzeug.serving import make_server
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.cert, self.key = Path(d.name) / "cert.pem", Path(d.name) / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-keyout", str(self.key), "-out",
                        str(self.cert), "-subj", "/CN=localhost"], check=True, capture_output=True)
        app = admin.create_app(admin.Settings(judicom_dir=Path(d.name), photos_dir=Path(d.name), trash_dir=Path(d.name)))
        server = make_server("127.0.0.1", 0, app, threaded=True, ssl_context=context(self.cert, self.key), request_handler=admin.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return server.server_port

    def fetch(self, port):
        context = ssl.create_default_context()
        context.check_hostname, context.verify_mode = False, ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", port), timeout=4) as raw, context.wrap_socket(raw) as tls:
            tls.sendall(b"GET /login HTTP/1.0\r\nHost: localhost\r\n\r\n")
            return tls.recv(100)

    def test_it_answers_over_https(self):
        self.assertIn(b"200", self.fetch(self.serve(admin.tls_context)))

    def test_a_connection_that_says_nothing_stops_nobody(self):
        port = self.serve(admin.tls_context)
        idle = [socket.create_connection(("127.0.0.1", port)) for _ in range(3)]
        self.addCleanup(lambda: [s.close() for s in idle])
        time.sleep(0.3)
        self.assertIn(b"200", self.fetch(port))

    def test_a_connection_that_is_not_https_stops_nobody(self):
        port = self.serve(admin.tls_context)
        with socket.create_connection(("127.0.0.1", port)) as plain:
            plain.sendall(b"GET / HTTP/1.0\r\n\r\n")
            self.assertIn(b"200", self.fetch(port))


if __name__ == "__main__":
    unittest.main()
