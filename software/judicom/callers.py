"""Judi's caller list, read the one way everything reads it: the Judicom (contacts.py), the NAS's apply_contacts.py (Asterisk's
allowed list) and the housekeeping website.  Only the standard library and nothing else of the Judicom's, so the NAS can use it
straight from its copy of the repository.

THE FILE, one person per line, fields separated by |  (lines starting with # and empty lines are skipped):

    # number       | name  | relationship | button
    212-555-0142   | Frank | husband      | left
    312-555-0123   | Hannah | granddaughter

    entries, buttons, problems = read(text)
    entries   [Entry, ...] in file order, one per number (a number listed twice: the later line's details, the earlier place)
    buttons   {"left" / "right": Entry}  (two people on one button: the later line wins)
    problems  ["line 4 skipped (needs at least a number and a name): ...", ...]  (the line number and why; nothing is raised)

A line needs at least a number (3 digits or more) and a name; one without is skipped.  A button that is not left or right is
dropped (the person stays).  The website has stricter rules of its own for what it saves (check_callers in judicom_admin.py).
"""
from collections import namedtuple

BUTTON_KEYS = ("left", "right")

Entry = namedtuple("Entry", "digits name relationship button line")


def normalize(number):
    """The number as 10 digits (North America) so that every way of writing it matches: '+1 (212) 555-0142' -> '2125550142'.
    A SIP address works too: 'sip:+12125550142@pbx' -> '2125550142'.  Other lengths are kept as their digits."""
    text = number or ""
    if ":" in text:
        text = text.split(":", 1)[1]                 # sip:...  -> the part after the scheme
    text = text.split("@", 1)[0]                     # ...@host -> the user part
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def pretty(number):
    """For the screen: '+12125550142' -> '212-555-0142'; other numbers as their digits ('sip:101@pbx' -> '101');
    '' when there is no number at all (a caller who hides it: 'sip:anonymous@...')."""
    d = normalize(number)
    return "%s-%s-%s" % (d[:3], d[3:6], d[6:]) if len(d) == 10 else d


def fields(line):
    """(number, name, relationship, button) as written, spaces trimmed, button in small letters; None for a comment or an
    empty line.  Missing fields are ""."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [f.strip() for f in line.split("|")] + ["", "", "", ""]
    return parts[0], parts[1], parts[2], parts[3].lower()


def read(text):
    """(entries, buttons, problems): see the top of this file."""
    entries, where, buttons, problems = [], {}, {}, []
    for n, line in enumerate((text or "").splitlines(), 1):
        f = fields(line)
        if f is None:
            continue
        number, name, relationship, button = f
        digits = normalize(number)
        if len(digits) < 3 or not name:
            problems.append("line %d skipped (needs at least a number and a name): %s" % (n, line.strip()))
            continue
        if button and button not in BUTTON_KEYS:
            problems.append("line %d: button must be left or right, not %r (the person is kept, without a button)" % (n, button))
            button = ""
        entry = Entry(digits, name, relationship, button, n)
        if digits in where:
            problems.append("line %d: %s is listed twice; the later line wins" % (n, pretty(digits)))
            entries[where[digits]] = entry
        else:
            where[digits] = len(entries)
            entries.append(entry)
        if button:
            if button in buttons:
                problems.append("line %d: two people on the %s button; the later line wins" % (n, button))
            buttons[button] = entry
    return entries, buttons, problems
