"""Tests for judicom/contacts.py.   Run from the software folder:   python3 -m unittest -v"""
import os
import tempfile
import unittest
from pathlib import Path

from judicom.contacts import Contacts, normalize, parse, pretty
from judicom.machine import Party

EXAMPLE = Path(__file__).resolve().parent.parent / "contacts.example.txt"

FILE = """# number | name | relationship | button
212-555-0142   | Frank  | husband       | left
(312) 555-0187 | Ann    | daughter      | RIGHT

+1 312 555 0123 | Hannah | granddaughter
"""


class Numbers(unittest.TestCase):
    def test_every_way_of_writing_it_is_the_same(self):
        for written in ("212-555-0142", "(212) 555-0142", "+1 212 555 0142", "12125550142", "2125550142",
                        "sip:+12125550142@100.64.0.1", "sip:2125550142@pbx.local;transport=udp", "<sip:+1-212-555-0142@pbx>"):
            with self.subTest(written=written):
                self.assertEqual(normalize(written), "2125550142")

    def test_other_lengths_are_kept(self):
        self.assertEqual(normalize("100"), "100")
        self.assertEqual(normalize("+44 20 7946 0000"), "442079460000")
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize(None), "")

    def test_pretty(self):
        self.assertEqual(pretty("+12125550142"), "(212) 555-0142")
        self.assertEqual(pretty("sip:2125550142@pbx"), "(212) 555-0142")
        self.assertEqual(pretty("100"), "100")


class Parsing(unittest.TestCase):
    def test_people_and_buttons(self):
        people, buttons = parse(FILE)
        self.assertEqual(set(people), {"2125550142", "3125550187", "3125550123"})
        self.assertEqual(buttons["left"], Party("Frank", "husband", "2125550142", "2125550142"))
        self.assertEqual(buttons["right"].name, "Ann")                  # "RIGHT" is fine
        self.assertEqual(people["3125550123"], Party("Hannah", "granddaughter", "3125550123", "3125550123"))

    def test_the_button_dials_and_plays_the_real_digits(self):
        _, buttons = parse(FILE)
        self.assertEqual(buttons["left"].dial, "2125550142")
        self.assertEqual(buttons["left"].tones, "2125550142")

    def test_bad_lines_are_reported_and_skipped(self):
        logged = []
        people, buttons = parse("no number here | Bob\n555-0100 |\n212-555-0142 | Frank | husband | middle\n", logged.append)
        self.assertEqual(list(people), ["2125550142"])
        self.assertEqual(buttons, {})                                    # "middle" is not a button, but Frank is kept
        self.assertEqual(len(logged), 3)
        self.assertIn("line 1", logged[0])
        self.assertIn("line 2", logged[1])
        self.assertIn("left or right", logged[2])

    def test_twice_listed_later_wins(self):
        logged = []
        people, buttons = parse("212-555-0142 | Frank | husband | left\n2125550142 | Frank | Grandpa | left\n", logged.append)
        self.assertEqual(people["2125550142"].relationship, "Grandpa")
        self.assertEqual(buttons["left"].relationship, "Grandpa")
        self.assertEqual(len(logged), 2)

    def test_name_only_relationship_optional(self):
        people, _ = parse("212-555-0142 | Frank\n")
        self.assertEqual(people["2125550142"].label, "Frank")

    def test_example_file_in_the_repository(self):
        logged = []
        people, buttons = parse(EXAMPLE.read_text(), logged.append)
        self.assertEqual(logged, [])
        self.assertEqual(set(buttons), {"left", "right"})
        for number in people:
            self.assertEqual(number[3:6], "555", "the example file must only have made-up 555 numbers")


class File(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "contacts.txt"
        self.logged = []

    def write(self, text, bump=0):
        self.path.write_text(text)
        st = self.path.stat()
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + bump))      # a clearly new time, however fast the test runs

    def test_lookup(self):
        self.write(FILE)
        c = Contacts(self.path, self.logged.append)
        self.assertEqual(c.lookup("sip:+13125550187@pbx").label, "Ann (daughter)")
        unknown = c.lookup("+13125550199")
        self.assertEqual((unknown.name, unknown.label), ("", "(312) 555-0199"))
        self.assertIn("3 people", self.logged[-1])

    def test_missing_file_uses_the_demo_buttons(self):
        c = Contacts(self.path, self.logged.append)
        self.assertEqual(set(c.buttons()), {"left", "right"})
        self.assertEqual(len(self.logged), 1)
        self.assertIn("No contacts file", self.logged[0])
        self.assertFalse(c.refresh())
        self.assertEqual(len(self.logged), 1)                           # said once, not every few seconds

    def test_changes_are_picked_up(self):
        self.write(FILE)
        c = Contacts(self.path, self.logged.append)
        self.assertFalse(c.refresh())                                   # nothing changed
        self.write(FILE.replace("Frank ", "Grandpa Frank "), bump=10**9)
        self.assertTrue(c.refresh())
        self.assertEqual(c.buttons()["left"].name, "Grandpa Frank")

    def test_file_appears_and_disappears(self):
        c = Contacts(self.path, self.logged.append)
        self.write(FILE)
        self.assertTrue(c.refresh())
        self.assertEqual(c.buttons()["left"].dial, "2125550142")
        self.path.unlink()
        self.assertTrue(c.refresh())
        self.assertEqual(c.buttons()["left"].dial, "frank")             # back to the demo people
        self.assertEqual(c.lookup("2125550142").name, "")

    def test_a_missing_button_is_reported(self):
        self.write("212-555-0142 | Frank | husband | left\n")
        Contacts(self.path, self.logged.append)
        self.assertIn("nobody on the right button", self.logged[-1])


if __name__ == "__main__":
    unittest.main()
