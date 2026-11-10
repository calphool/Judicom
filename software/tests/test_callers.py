"""Tests for judicom/callers.py: the one reading of Judi's caller list, used by the Judicom (contacts.py), the NAS's
apply_contacts.py and the housekeeping website.  Every number here is made up.   Run from the software folder:
python3 -m unittest -v"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from judicom.callers import Entry, fields, normalize, pretty, read

REPO = Path(__file__).resolve().parents[2]
APPLY = REPO / "deploy" / "nas" / "judicom" / "apply_contacts.py"

LIST = """# number | name | relationship | button
212-555-0142   | Frank  | husband       | left
(312) 555-0187 | Ann    | daughter      | right
+1 312 555 0123 | Hannah | granddaughter
555           |        | nobody
312-555-0177   | Bob    | brother       | middle
212-555-0142   | Frank  | husband (new) |
312.555.0199   | Kaylee | granddaughter | LEFT
"""


class Reading(unittest.TestCase):
    def test_the_list(self):
        entries, buttons, problems = read(LIST)
        self.assertEqual([e.digits for e in entries], ["2125550142", "3125550187", "3125550123", "3125550177", "3125550199"])
        self.assertEqual(entries[0], Entry("2125550142", "Frank", "husband (new)", "", 7))     # later line, earlier place
        self.assertEqual((buttons["left"].name, buttons["right"].name), ("Kaylee", "Ann"))   # LEFT counts; the later one wins
        self.assertEqual(len(problems), 4)
        for line, words in ((5, "skipped"), (6, "button must be left or right"), (7, "listed twice"), (8, "two people on the left")):
            self.assertTrue(any(p.startswith("line %d" % line) and words in p for p in problems), (line, problems))

    def test_empty_and_nothing(self):
        self.assertEqual(read(""), ([], {}, []))
        self.assertEqual(read(None), ([], {}, []))
        self.assertEqual(read("# only a comment\n\n"), ([], {}, []))

    def test_fields(self):
        self.assertIsNone(fields("  # a comment"))
        self.assertIsNone(fields("   "))
        self.assertEqual(fields(" 212-555-0142 |Frank| husband | Left "), ("212-555-0142", "Frank", "husband", "left"))
        self.assertEqual(fields("212-555-0142 | Frank"), ("212-555-0142", "Frank", "", ""))

    def test_numbers(self):
        for written in ("212-555-0142", "(212) 555-0142", "+1 212 555 0142", "12125550142", "sip:+12125550142@pbx"):
            self.assertEqual(normalize(written), "2125550142", written)
        self.assertEqual((pretty("+12125550142"), pretty("sip:101@pbx"), pretty("sip:anonymous@x")), ("212-555-0142", "101", ""))


class EveryoneReadsItTheSameWay(unittest.TestCase):
    def test_phone_nas_and_website(self):
        import importlib.util
        from judicom.contacts import parse as phone_parse
        spec = importlib.util.spec_from_file_location("apply_contacts", APPLY)
        nas = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nas)
        people, buttons = phone_parse(LIST)
        allowed, _ = nas.parse(LIST)
        self.assertEqual([d for d, _ in allowed], list(people))                               # same people, same order
        self.assertEqual({d: n for d, n in allowed}, {d: p.name for d, p in people.items()})
        self.assertEqual({k: p.name for k, p in buttons.items()}, {"left": "Kaylee", "right": "Ann"})

    def test_apply_contacts_through_a_link(self):
        """On the NAS /home/pi/judicom/apply_contacts.py is a link into the repository: it must still find judicom/callers.py."""
        with tempfile.TemporaryDirectory() as d:
            link = Path(d) / "apply_contacts.py"
            os.symlink(APPLY, link)
            code = ("import importlib.util, sys; spec = importlib.util.spec_from_file_location('a', sys.argv[1]); "
                    "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
                    "print(m.parse('212-555-0142 | Frank')[0])")
            out = subprocess.run([sys.executable, "-I", "-c", code, str(link)], cwd=d, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), "[('2125550142', 'Frank')]")


if __name__ == "__main__":
    unittest.main()
