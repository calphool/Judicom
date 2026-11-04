"""Tests for deploy/nas/firewall/voipms_address_check.py (the NAS's hourly VoIP.ms address check).  Nothing real is touched:
the firewall, the lookup and Asterisk are stand-ins.   Run from the software folder:   python3 -m unittest -v"""
import importlib.util
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "nas" / "firewall" / "voipms_address_check.py"
spec = importlib.util.spec_from_file_location("voipms_address_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

OLD_RULE = (SCRIPT.parent / "asterisk-firewall.nft").read_text()          # the fixed rule as it is on the NAS today
PJSIP = """[voipms-auth]
type=auth
password=CHANGE_ME
[voipms]
type=aor
contact=sip:chicago4.voip.ms:5060
[voipms-identify]
type=identify
endpoint=voipms
match=208.100.60.6
[other-identify]
type=identify
match=10.0.0.1
"""


class Files(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.nft, self.pjsip = d / "asterisk-firewall.nft", d / "voipms.conf"
        self.nft.write_text(OLD_RULE)
        self.pjsip.write_text(PJSIP)
        self.ran, self.logged = [], []

    def run_cmd(self, fail=()):
        def run(cmd, **kw):
            self.ran.append(cmd)
            bad = any(word in cmd for word in fail)
            return subprocess.CompletedProcess(cmd, 1 if bad else 0, "" if bad else "ok", "error!" if bad else "")
        return run

    def check(self, found, fail=(), dry_run=False):
        def resolver():
            if isinstance(found, Exception):
                raise found
            return found
        return check.check(resolver, str(self.nft), str(self.pjsip), self.run_cmd(fail), dry_run, self.logged.append)

    def test_first_run_turns_the_fixed_rule_into_a_set(self):
        self.assertEqual(self.check(["208.100.60.6"]), 0)
        text = self.nft.read_text()
        self.assertIn("set voipms", text)
        self.assertIn("ip saddr != @voipms drop", text)
        self.assertEqual(check.file_addresses(text), ["208.100.60.6"])
        self.assertEqual(self.ran, [[check.NFT, "-f", str(self.nft)]])            # the firewall reloaded, Asterisk not
        self.assertEqual(self.pjsip.read_text(), PJSIP)

    def test_up_to_date_does_nothing(self):
        self.check(["208.100.60.6"])
        self.ran.clear()
        before = self.nft.read_text()
        self.assertEqual(self.check(["208.100.60.6"]), 0)
        self.assertEqual(self.ran, [])
        self.assertEqual(self.nft.read_text(), before)
        self.assertIn("allowed in the firewall and known to Asterisk", self.logged[-1])

    def test_a_new_address_is_added_everywhere_and_the_old_kept(self):
        self.check(["208.100.60.6"])
        self.ran.clear()
        self.assertEqual(self.check(["208.100.60.9"]), 0)
        self.assertEqual(check.file_addresses(self.nft.read_text()), ["208.100.60.6", "208.100.60.9"])
        text = self.pjsip.read_text()
        self.assertIn("match=208.100.60.6,208.100.60.9", text)
        self.assertIn("match=10.0.0.1", text)                                     # other sections untouched
        self.assertEqual(self.ran, [[check.NFT, "-f", str(self.nft)], check.RELOAD])
        self.assertTrue(any("added 208.100.60.9" in m for m in self.logged))

    def test_a_failed_lookup_changes_nothing_and_warns(self):
        self.assertEqual(self.check(RuntimeError("cannot look up chicago4.voip.ms: timed out")), 0)
        self.assertEqual(self.nft.read_text(), OLD_RULE)
        self.assertEqual(self.ran, [])
        self.assertTrue(self.logged[-1].startswith("WARNING"))

    def test_a_firewall_that_refuses_is_an_error(self):
        self.assertEqual(self.check(["208.100.60.6"], fail=(check.NFT,)), 1)
        self.assertTrue(any(m.startswith("ERROR: the firewall") for m in self.logged))

    def test_asterisk_that_refuses_is_an_error(self):
        self.check(["208.100.60.6"])
        self.assertEqual(self.check(["208.100.60.9"], fail=("module reload res_pjsip.so",)), 1)
        self.assertTrue(any(m.startswith("ERROR: Asterisk") for m in self.logged))

    def test_dry_run_changes_nothing(self):
        self.assertEqual(self.check(["208.100.60.9"], dry_run=True), 0)
        self.assertEqual((self.nft.read_text(), self.pjsip.read_text(), self.ran), (OLD_RULE, PJSIP, []))
        self.assertIn("would allow 208.100.60.6, 208.100.60.9", self.logged[-1])

    def test_the_set_never_grows_without_end(self):
        self.check(["208.100.60.6"])
        for i in range(20):
            self.check(["203.0.113.%d" % (i + 1)])
        self.assertEqual(len(check.file_addresses(self.nft.read_text())), check.MAX_KEPT)
        self.assertIn("203.0.113.20", check.file_addresses(self.nft.read_text()))


class Lookup(unittest.TestCase):
    def answer(self, *addresses):
        return [(socket.AF_INET, socket.SOCK_DGRAM, 17, "", (a, 5060)) for a in addresses]

    def test_public_addresses_sorted(self):
        with mock.patch.object(check.socket, "getaddrinfo", return_value=self.answer("208.100.60.9", "208.100.60.6")):
            self.assertEqual(check.resolve(), ["208.100.60.6", "208.100.60.9"])

    def test_strange_answers_are_not_believed(self):
        for answer in (self.answer("192.168.1.1"), self.answer("127.0.0.1"), self.answer("100.64.0.1"),
                       self.answer(*["208.100.60.%d" % i for i in range(1, 10)]), []):
            with self.subTest(answer=answer):
                with mock.patch.object(check.socket, "getaddrinfo", return_value=answer):
                    with self.assertRaises(RuntimeError):
                        check.resolve()

    def test_no_answer(self):
        with mock.patch.object(check.socket, "getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            with self.assertRaisesRegex(RuntimeError, "cannot look up"):
                check.resolve()


class Text(unittest.TestCase):
    def test_round_trip(self):
        for addresses in (["208.100.60.6"], ["208.100.60.6", "208.100.60.9"]):
            self.assertEqual(check.file_addresses(check.nft_text(addresses)), addresses)

    def test_reads_the_old_fixed_rule(self):
        self.assertEqual(check.file_addresses(OLD_RULE), ["208.100.60.6"])

    def test_the_new_file_replaces_the_table_in_one_step(self):
        text = check.nft_text(["208.100.60.6"])
        body = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(body[:2], ["table inet asterisk_test", "delete table inet asterisk_test"])


if __name__ == "__main__":
    unittest.main()
