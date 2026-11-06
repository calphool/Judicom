"""Tests for deploy/nas/admin/judicom_admin.py (the housekeeping website), with Flask's test client and temporary folders.
Skipped where Flask or Pillow is not installed.   Run from the software folder:   python3 -m unittest -v"""
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
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
641-555-0142 | Clark | husband  | left
515-555-0187 | Amy   | daughter | right
515-555-0123 | Sydney | granddaughter
"""
EVENTS = """# Judi's events.
# One per line.

# ---- holidays
12-25 | Christmas
4th Thursday of November | Thanksgiving

# ---- family
04-22 | Amy's birthday
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
        s = admin.Settings(judicom_dir=self.j, photos_dir=self.photos, trash_dir=self.trash, apply=[str(apply)])
        self.settings = s
        self.app = admin.create_app(s)
        self.client = self.app.test_client()

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
        r = self.client.get("/", base_url="http://evil.example.com", environ_base={"REMOTE_ADDR": "192.168.1.20"})
        self.assertEqual(r.status_code, 403)
        for host in ("naspi.local:8080", "192.168.1.2:8080", "100.64.0.1:8080", "naspi-1.tail1234.ts.net:8080"):
            r = self.client.get("/", base_url="http://" + host, environ_base={"REMOTE_ADDR": "192.168.1.20"})
            self.assertEqual(r.status_code, 200, host)

    def test_a_post_without_the_token_changes_nothing(self):
        r = self.post("/callers", self.callers_form([("515-555-0999", "Scammer", "", "")]), token=False)
        self.assertEqual(r.status_code, 403)
        self.assertEqual((self.j / "contacts.txt").read_text(), CONTACTS)

    def test_pages_show(self):
        for url in ("/", "/callers", "/events", "/people", "/photos"):
            with self.subTest(url=url):
                self.assertEqual(self.get(url).status_code, 200)
        self.assertIn("Clark", self.get("/").get_data(as_text=True))

    # ---- callers
    def test_save_callers_and_apply(self):
        r = self.post("/callers", self.callers_form([("641 555 0142", "Clark", "husband", "left"), ("(515) 555-0187", "Amy",
                                                    "daughter", "right"), ("515.555.0177", "Bob", "brother", "")]))
        self.assertEqual(r.status_code, 302)
        text = (self.j / "contacts.txt").read_text()
        self.assertIn("515-555-0177 | Bob", text)
        self.assertNotIn("Sydney", text)
        self.assertTrue(self.applied.exists())                               # the PBX was updated at once
        self.assertEqual(len(list((self.j / "history").glob("contacts.txt.*"))), 1)
        from judicom.contacts import parse
        people, buttons = parse(text)
        self.assertEqual(len(people), 3)
        self.assertEqual(buttons["left"].name, "Clark")

    def test_remove_a_caller(self):
        form = self.callers_form([("641-555-0142", "Clark", "husband", "left"), ("515-555-0187", "Amy", "daughter", "right"),
                                  ("515-555-0123", "Sydney", "granddaughter", "")])
        form["remove-3"] = "1"
        self.post("/callers", form)
        self.assertNotIn("Sydney", (self.j / "contacts.txt").read_text())

    def test_bad_callers_are_shown_and_nothing_is_saved(self):
        for rows, words in (([("555-0142", "Clark", "", "")], "10 digits"),
                            ([("641-555-0142", "Clark", "", "left"), ("515-555-0187", "Amy", "", "left")], "both on the left"),
                            ([("641-555-0142", "Clark", "", ""), ("641-555-0142", "Clark2", "", "")], "already listed"),
                            ([("641-555-0142", "", "", "")], "name is needed"),
                            ([("641-555-0142", "Cl|ark", "", "")], "may not contain"),
                            ([("641-555-0142", "Amy", "", ""), ("515-555-0187", "amy", "", "")], "two people are called")):
            with self.subTest(words=words):
                r = self.post("/callers", self.callers_form(rows))
                self.assertEqual(r.status_code, 400)
                self.assertIn(words, r.get_data(as_text=True))
                self.assertEqual((self.j / "contacts.txt").read_text(), CONTACTS)
        form = self.callers_form([("641-555-0142", "Clark", "", "")])
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
                                                   ("heading", "", "family"), ("event", "04-22", "Amy's birthday"),
                                                   ("event", "2030-11-08 10:30", "Visit from Amy")]))
        self.assertEqual(r.status_code, 302)
        text = (self.j / "events.txt").read_text()
        self.assertTrue(text.startswith("# Judi's events.\n# One per line.\n"))
        self.assertIn("# ---- family", text)
        self.assertIn("2030-11-08 10:30 | Visit from Amy", text)
        self.assertNotIn("Thanksgiving", text)
        from judicom.events import parse
        problems = []
        self.assertEqual(len(parse(text, problems.append)), 3)
        self.assertEqual(problems, [])

    def test_a_new_holiday_can_go_with_the_holidays(self):
        (self.j / "events.txt").write_text("# Judi's events.\n\n# ---- holidays\n12-25 | Christmas\n\n# ---- family\n04-22 | Amy's birthday\n")
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
                ("heading", "", "family"), ("event", "04-22", "Amy's birthday"), ("event", "2026-03-01 2 PM", "Visit"),
                ("event", "02-10", "Joe's birthday")]
        form = self.events_form(rows)
        form["sort"] = "1"
        self.assertEqual(self.post("/events", form).status_code, 302)
        titles = [l.split("|")[-1].strip() for l in (self.j / "events.txt").read_text().splitlines() if l and not l.startswith("#")]
        self.assertEqual(titles, ["New Year's Day", "Easter", "Thanksgiving", "Black Friday", "Christmas",
                                  "Joe's birthday", "Visit", "Amy's birthday"])
        text = (self.j / "events.txt").read_text()
        self.assertLess(text.index("Christmas"), text.index("# ---- family"))       # nothing moves to another section

    def test_a_bad_date_is_shown_and_nothing_is_saved(self):
        r = self.post("/events", self.events_form([("event", "12-25", "Christmas"), ("event", "Dec 25th", "Oops")]))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Oops", r.get_data(as_text=True))
        self.assertEqual((self.j / "events.txt").read_text(), EVENTS)

    # ---- caller pictures
    def test_a_caller_picture_is_cropped_square_and_named(self):
        r = self.post("/people/upload", {"name": "Amy", "picture": (io.BytesIO(picture(1200, 900)), "IMG_0001.JPG")},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        img = Image.open(self.j / "people" / "Amy.png")
        self.assertEqual((img.format, img.size), ("PNG", (800, 800)))
        self.post("/people/upload", {"name": "Amy", "picture": (io.BytesIO(picture(500, 700, (0, 0, 200))), "b.png")},
                  content_type="multipart/form-data")
        self.assertEqual(sorted(p.name for p in (self.j / "people").iterdir()), ["Amy.png"])
        self.assertEqual(len(list((self.trash / "caller pictures").iterdir())), 1)       # the old one kept aside
        self.assertEqual(self.get("/people/img/Amy.png").status_code, 200)

    def test_only_callers_get_pictures_and_junk_is_refused(self):
        r = self.post("/people/upload", {"name": "Stranger", "picture": (io.BytesIO(picture(10, 10)), "a.jpg")},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.post("/people/upload", {"name": "Amy", "picture": (io.BytesIO(b"not a picture"), "a.jpg")},
                  content_type="multipart/form-data")
        self.assertFalse((self.j / "people").exists() and any((self.j / "people").iterdir()))

    def test_remove_a_caller_picture(self):
        (self.j / "people").mkdir()
        (self.j / "people" / "Amy.png").write_bytes(picture(10, 10, fmt="PNG"))
        self.post("/people/remove", {"file": "Amy.png"})
        self.assertFalse((self.j / "people" / "Amy.png").exists())
        self.assertEqual(self.post("/people/remove", {"file": "../contacts.txt"}).status_code, 404)

    # ---- photos
    def test_upload_photos_with_a_caption(self):
        r = self.post("/photos/upload", {"pictures": [(io.BytesIO(picture(400, 300)), "Beach day.jpg"),
                                                      (io.BytesIO(picture(4000, 3000)), "huge.png")],
                                         "people": "Amy and Sydney", "relationship": "", "taken": "Summer 2026"},
                      content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)
        names = sorted(p.name for p in self.photos.iterdir())
        self.assertEqual(names, ["Beach_day.jpg", "Beach_day.meta", "huge.jpg", "huge.meta"])
        self.assertEqual(Image.open(self.photos / "huge.jpg").size, (3000, 2250))      # shrunk
        self.assertEqual((self.photos / "Beach_day.meta").read_text(), "people: Amy and Sydney\ntaken: Summer 2026\n")
        from judicom.photos import load_caption
        self.assertEqual(load_caption(self.photos / "huge.jpg").people, "Amy and Sydney")

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

    def send(self, sender="Amy", text="Hi Mom"):
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


if __name__ == "__main__":
    unittest.main()
