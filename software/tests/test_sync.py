"""Tests for judicom/sync.py (fetching the caller list from the NAS) and deploy/nas/judicom/apply_contacts.py (the NAS side).
Run from the software folder:   python3 -m unittest -v"""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

from judicom import sync
from judicom.contacts import Contacts

LIST = """# number | name | relationship | button
212-555-0142 | Frank  | husband       | left
312-555-0187 | Ann    | daughter      | right
+1 312 555 0123 | Hannah | granddaughter
"""

NAS_SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "judicom" / "apply_contacts.py"
spec = importlib.util.spec_from_file_location("apply_contacts", NAS_SCRIPT)
apply_contacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_contacts)


class Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.logged = []


class Fetch(unittest.TestCase):
    def run_with(self, returncode=0, stdout=b"", stderr=b"", exc=None):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            if exc:
                raise exc
            return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)
        return run, calls

    def test_uses_its_own_key_and_never_asks(self):
        run, calls = self.run_with(stdout=LIST.encode())
        self.assertEqual(sync.fetch("pi@100.64.0.1", "/k", run=run), LIST)
        cmd = calls[0]
        self.assertEqual(cmd[:3], ["ssh", "-i", "/k"])
        self.assertIn("BatchMode=yes", cmd)
        self.assertIn("IdentitiesOnly=yes", cmd)
        self.assertEqual(cmd[-1], "pi@100.64.0.1")                # no command: the NAS decides what runs (cat the list)

    def test_refused(self):
        run, _ = self.run_with(returncode=255, stderr=b"pi@100.64.0.1: Permission denied (publickey).\n")
        with self.assertRaisesRegex(RuntimeError, "Permission denied"):
            sync.fetch("h", "/k", run=run)

    def test_unreachable(self):
        run, _ = self.run_with(exc=subprocess.TimeoutExpired("ssh", 30))
        with self.assertRaisesRegex(RuntimeError, "cannot reach"):
            sync.fetch("h", "/k", run=run)


class Sync(Folder):
    def test_writes_the_list_with_a_copy_header(self):
        path = self.dir / "contacts.txt"
        self.assertEqual(sync.sync(lambda: LIST, path, self.logged.append), 0)
        text = path.read_text()
        self.assertTrue(text.startswith("# COPY"))
        self.assertIn("212-555-0142 | Frank", text)
        self.assertEqual(Contacts(path).buttons()["left"].name, "Frank")   # the phone reads it like before
        self.assertIn("updated: 3 people", self.logged[-1])

    def test_unchanged_is_not_rewritten(self):
        path = self.dir / "contacts.txt"
        sync.sync(lambda: LIST, path, self.logged.append)
        before = path.stat().st_mtime_ns
        sync.sync(lambda: LIST, path, self.logged.append)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertIn("unchanged", self.logged[-1])

    def test_nas_unreachable_keeps_the_old_list(self):
        path = self.dir / "contacts.txt"
        path.write_text("old list\n")

        def down():
            raise RuntimeError("cannot reach pi@100.64.0.1: timed out")
        self.assertEqual(sync.sync(down, path, self.logged.append), 1)
        self.assertEqual(path.read_text(), "old list\n")
        self.assertIn("keeping the current list", self.logged[-1])

    def test_empty_or_broken_list_keeps_the_old_one(self):
        path = self.dir / "contacts.txt"
        path.write_text("old list\n")
        for bad in ("", "# only comments\n", "not | a | list\n"):
            with self.subTest(bad=bad):
                self.assertEqual(sync.sync(lambda: bad, path, self.logged.append), 1)
                self.assertEqual(path.read_text(), "old list\n")

    def test_bad_lines_are_reported_but_the_rest_is_used(self):
        path = self.dir / "contacts.txt"
        self.assertEqual(sync.sync(lambda: LIST + "nonsense\n", path, self.logged.append), 0)
        self.assertTrue(any(m.startswith("in the NAS's list:") and "line 5 skipped" in m for m in self.logged))

    def test_missing_button_is_noted(self):
        path = self.dir / "contacts.txt"
        sync.sync(lambda: "212-555-0142 | Frank | husband | left\n", path, self.logged.append)
        self.assertTrue(any("nobody is on the right button" in m for m in self.logged))

    def test_no_temporary_files_left_behind(self):
        path = self.dir / "contacts.txt"
        sync.sync(lambda: LIST, path, self.logged.append)
        self.assertEqual([p.name for p in self.dir.iterdir()], ["contacts.txt"])


class Events(Folder):
    def test_writes_the_events_with_a_copy_header(self):
        path = self.dir / "events.txt"
        self.assertEqual(sync.sync_events(lambda: "12-25 | Christmas\n", path, self.logged.append), 0)
        self.assertTrue(path.read_text().startswith("# COPY of Judi's events list"))
        from judicom.events import EventList
        self.assertEqual(EventList(path).events[0].title, "Christmas")
        self.assertIn("events updated: 1", self.logged[-1])

    def test_an_empty_list_is_fine(self):
        path = self.dir / "events.txt"
        self.assertEqual(sync.sync_events(lambda: "# nothing planned\n", path, self.logged.append), 0)
        self.assertIn("events updated: 0", self.logged[-1])

    def test_the_caller_list_given_instead_is_refused(self):
        path = self.dir / "events.txt"
        path.write_text("old\n")
        self.assertEqual(sync.sync_events(lambda: LIST, path, self.logged.append), 1)  # an old NAS key line answers contacts
        self.assertEqual(path.read_text(), "old\n")
        self.assertIn("serve_list.sh", self.logged[-1])

    def test_unreachable_keeps_the_old_list(self):
        path = self.dir / "events.txt"
        path.write_text("old\n")

        def down():
            raise RuntimeError("cannot reach pi@100.64.0.1: timed out")
        self.assertEqual(sync.sync_events(down, path, self.logged.append), 1)
        self.assertEqual(path.read_text(), "old\n")

    def test_asks_the_nas_for_events(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, b"12-25 | Christmas\n", b"")
        self.assertEqual(sync.fetch("pi@h", "/k", run=run, what="events"), "12-25 | Christmas\n")
        self.assertEqual(calls[0][-2:], ["pi@h", "events"])


class Verses(Folder):
    def test_writes_the_verses_with_a_copy_header(self):
        path = self.dir / "verses.txt"
        self.assertEqual(sync.sync_verses(lambda: "Psalm 56:3 | What time I am afraid, I will trust in thee.\n", path,
                                          self.logged.append), 0)
        self.assertTrue(path.read_text().startswith("# COPY of Judi's verse list"))
        self.assertIn("verses updated: 1", self.logged[-1])

    def test_the_caller_list_given_instead_is_refused(self):
        path = self.dir / "verses.txt"
        path.write_text("old\n")
        self.assertEqual(sync.sync_verses(lambda: "contacts only, no bars here\n", path, self.logged.append), 1)
        self.assertEqual(path.read_text(), "old\n")


class NasSide(Folder):
    def setUp(self):
        super().setUp()
        self.master = self.dir / "contacts.txt"
        self.allowed = self.dir / "judicom-allowed.conf"
        self.reloads = []

    def reload_cmd(self, ok=True):
        script = self.dir / "fake_asterisk.sh"
        script.write_text("#!/bin/sh\necho %s\n" % ("Dialplan reloaded." if ok else "Unable to connect to remote asterisk"))
        script.chmod(0o755)
        return [str(script)]

    def apply(self, ok=True):
        return apply_contacts.apply(str(self.master), str(self.allowed), self.reload_cmd(ok), logger=self.logged.append)

    def test_writes_the_allowed_list(self):
        self.master.write_text(LIST)
        self.assertEqual(self.apply(), 0)
        text = self.allowed.read_text()
        self.assertIn("[judicom-allowed]", text)
        for line in ("exten => 2125550142,1,NoOp(Frank)", "exten => 3125550187,1,NoOp(Ann)", "exten => 3125550123,1,NoOp(Hannah)"):
            self.assertIn(line, text)
        self.assertIn("3 people", self.logged[-1])

    def test_unchanged_does_nothing(self):
        self.master.write_text(LIST)
        self.apply()
        n = len(self.logged)
        self.assertEqual(self.apply(), 0)
        self.assertEqual(len(self.logged), n)                           # no reload, nothing logged

    def test_keeps_the_previous_list(self):
        self.master.write_text(LIST)
        self.apply()
        first = self.allowed.read_text()
        self.master.write_text(LIST + "312-555-0199 | Bob | friend\n")
        self.apply()
        self.assertEqual((self.dir / "judicom-allowed.conf.prev").read_text(), first)
        self.assertIn("3125550199", self.allowed.read_text())

    def test_empty_or_missing_list_changes_nothing(self):
        self.master.write_text(LIST)
        self.apply()
        good = self.allowed.read_text()
        for bad in ("", "# nobody\n"):
            self.master.write_text(bad)
            self.assertEqual(self.apply(), 1)
            self.assertEqual(self.allowed.read_text(), good)
        self.master.unlink()
        self.assertEqual(self.apply(), 1)
        self.assertEqual(self.allowed.read_text(), good)

    def test_failed_reload_is_reported(self):
        self.master.write_text(LIST)
        self.assertEqual(self.apply(ok=False), 2)
        self.assertIn("reload failed", self.logged[-1])

    def test_names_cannot_break_the_dialplan(self):
        self.master.write_text("212-555-0142 | Frank) ; [x] ${EVIL} | husband\n")
        self.apply()
        line = [l for l in self.allowed.read_text().splitlines() if l.startswith("exten")][0]
        self.assertEqual(line.count("("), 1)
        self.assertNotIn("$", line)
        self.assertNotIn(";", line)

    def test_same_rules_as_the_judicom(self):
        from judicom.contacts import parse as judicom_parse
        text = LIST + "nonsense line\n212-555-0142 | Grandpa | husband\n"
        nas = dict(apply_contacts.parse(text)[0])
        judicom = {k: p.name for k, p in judicom_parse(text)[0].items()}
        self.assertEqual(nas, judicom)                                  # both sides agree on who is in the list


if __name__ == "__main__":
    unittest.main()


class ServeList(unittest.TestCase):
    """deploy/nas/judicom/serve_list.sh: what the Judicom's sync key may read on the NAS."""

    def ask(self, request):
        script = NAS_SCRIPT.parent / "serve_list.sh"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "contacts.txt").write_text("C\n")
            (Path(d) / "events.txt").write_text("E\n")
            (Path(d) / "verses.txt").write_text("V\n")
            local = Path(d) / "serve_list.sh"
            local.write_text(script.read_text().replace("/home/pi/judicom/", d + "/"))
            env = {"PATH": "/usr/bin:/bin", "SSH_ORIGINAL_COMMAND": request}
            r = subprocess.run(["sh", str(local)], capture_output=True, text=True, env=env)
            return r.returncode, r.stdout, r.stderr

    def test_answers(self):
        self.assertEqual(self.ask("verses")[:2], (0, "V\n"))
        self.assertEqual(self.ask("")[:2], (0, "C\n"))
        self.assertEqual(self.ask("contacts")[:2], (0, "C\n"))
        self.assertEqual(self.ask("events")[:2], (0, "E\n"))

    def test_refuses_everything_else(self):
        for request in ("cat /etc/passwd", "contacts; id", "events && ls", "../contacts", "bash"):
            with self.subTest(request=request):
                code, out, err = self.ask(request)
                self.assertNotEqual(code, 0)
                self.assertEqual(out, "")
