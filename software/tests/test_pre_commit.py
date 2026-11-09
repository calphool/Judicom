"""Tests for .githooks/pre-commit (keeps private things out of the public repository).  Every number and name here is made up.
Run from the software folder:   python3 -m unittest -v"""
import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"
loader = importlib.machinery.SourceFileLoader("pre_commit_hook", str(HOOK))
spec = importlib.util.spec_from_loader("pre_commit_hook", loader)
hook = importlib.util.module_from_spec(spec)
loader.exec_module(hook)


def private(*entries):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("# a comment\n" + "\n".join(entries) + "\n")
    try:
        return hook.load_private(Path(fh.name))
    finally:
        os.unlink(fh.name)


class Lines(unittest.TestCase):
    def test_private_number_in_any_form(self):
        words = private("+1 (999) 340-8817")  # not-private: made up
        for text in ("9993408817", "999-340-8817", "call 340.8817 now", "+1 999 340 8817", "3408817"):  # not-private: made up
            self.assertEqual(hook.check_line(text, words)[0], "private list line 2", text)   # (often also "a phone number")
        self.assertEqual(hook.check_line("34088170", words), [])           # longer digit runs are something else

    def test_private_words_any_capitals_and_never_echoed(self):
        words = private("SecretTailnet", "998877")
        found = hook.check_line("host = secrettailnet  # id 998877", words)
        self.assertEqual(found, ["private list line 2", "private list line 3"])
        self.assertNotIn("secret", " ".join(found).lower())

    def test_ip_addresses(self):
        for text in ("100.101.102.103", "192.168.7.20", "172.20.1.5", "8.8.4.4"):  # not-private: made up
            self.assertEqual(hook.check_line("addr " + text, []), ["an IP address"], text)
        for text in ("127.0.0.1", "192.168.1.20", "100.64.0.2", "10.0.0.0/8", "172.16.0.0/12", "203.0.113.20", "208.100.60.6",
                     "224.0.2.21", "version 1.2.3.4.5", "999.1.2.3"):
            self.assertEqual(hook.check_line("addr " + text, []), [], text)

    def test_phone_numbers(self):
        self.assertEqual(hook.check_line("999-340-8817", []), ["a phone number without a 555 in it"])  # not-private: made up
        self.assertEqual(hook.check_line("(999) 340-8817", []), ["a phone number without a 555 in it"])  # not-private: made up
        for text in ("312-555-0199", "+1 (555) 010-0142", "212-555-0142", "timestamp 1794201471"):
            self.assertEqual(hook.check_line(text, []), [], text)

    def test_tailnet_names_keys_mail_checkins(self):
        self.assertEqual(hook.check_line("naspi.tail9f3e2.ts.net", []), ["a tailnet name (*.ts.net)"])  # not-private: made up
        self.assertEqual(hook.check_line("naspi-1.tail1234.ts.net or host.endswith('.ts.net')", []), [])
        self.assertEqual(hook.check_line("-----BEGIN OPENSSH PRIVATE KEY-----", []), ["a private key"])  # not-private: made up
        self.assertEqual(hook.check_line("ALERT_TO=someone@gmail.com", []), ["a Gmail address"])  # not-private: made up
        self.assertEqual(hook.check_line("PING_URL=https://hc-ping.com/1f2e3d4c-aaaa-bbbb", []), ["a check-in URL (healthchecks)"])  # not-private: made up
        self.assertEqual(hook.check_line("ALERT_TO=someone@example.com", []), [])

    def test_the_words_not_private_let_a_line_through(self):
        self.assertEqual(hook.check_line("8.8.4.4  # Google's DNS: not-private", []), [])

    def test_files_that_never_belong(self):
        for name in ("contacts.txt", "software/contacts.txt", "deploy/nas/asterisk/voipms.conf", "x/watch.env", "id_ed25519", "a.pem"):
            self.assertTrue(hook.check("", [name], []), name)
        for name in ("software/contacts.example.txt", "deploy/nas/asterisk/voipms.conf.example", "deploy/judicom/baresip/accounts.example"):
            self.assertEqual(hook.check("", [name], []), [], name)

    def test_only_added_lines_with_their_numbers(self):
        diff = ("diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n@@ -3,0 +4,2 @@\n+fine\n+192.168.7.20\n"  # not-private: made up
                "@@ -10 +11 @@\n-100.101.102.103\n+gone\n")  # not-private: made up
        self.assertEqual(hook.check(diff, [], []), ["f.txt:5: an IP address"])


@unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
class Committing(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.dir.name) / "repo"
        self.words = Path(self.dir.name) / "private-words.txt"
        self.words.write_text("999-340-8817\n")  # not-private: made up
        self.git("init", "-q", str(self.repo), cwd=self.dir.name)
        for k, v in (("user.name", "Test"), ("user.email", "test@example.com"), ("core.hooksPath", str(HOOK.parent))):
            self.git("config", k, v)

    def tearDown(self):
        self.dir.cleanup()

    def git(self, *args, cwd=None):
        env = dict(os.environ, JUDICOM_PRIVATE_WORDS=str(self.words))
        return subprocess.run(["git", *args], cwd=cwd or self.repo, capture_output=True, text=True, env=env)

    def commit(self, name, text):
        (self.repo / name).write_text(text)
        self.git("add", "-f", name)
        return self.git("commit", "-q", "-m", "test")

    def test_refused_then_allowed(self):
        r = self.commit("a.txt", "Grandma: 999.340.8817\n")  # not-private: made up
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a.txt:1: private list line 1", r.stderr)
        self.assertNotIn("8817", r.stderr)
        self.assertEqual(self.commit("a.txt", "Grandma: see the caller list\n").returncode, 0)

    def test_no_private_list_no_commit(self):
        self.words.unlink()
        r = self.commit("a.txt", "hello\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no private list", r.stderr)


if __name__ == "__main__":
    unittest.main()
