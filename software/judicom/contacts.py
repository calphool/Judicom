"""Who Judi's two buttons call, and the names shown for incoming calls: one plain text file, kept on the Judicom (not in git).

    contacts = Contacts(config.CONTACTS_FILE, log)
    contacts.buttons()                  # {"left": Party, "right": Party}: the people on the two buttons
    contacts.lookup("+13125550187")     # the Party for an incoming number (only the number, if it is not in the file)
    contacts.refresh()                  # True if the file changed and was read again (call now and then)

THE FILE (see contacts.example.txt), one person per line, fields separated by |

    # number       | name  | relationship | button
    212-555-0142   | Frank | husband      | left
    312-555-0187   | Ann   | daughter     | right
    312-555-0123   | Hannah | granddaughter

  number        any way of writing it: 212-555-0142, (212) 555-0142, +1 212 555 0142 are all the same number
  relationship  the way it should read on the screen ("husband", "granddaughter")
  button        left or right for the two people on the buttons; empty for everyone else
Lines starting with # and empty lines are skipped.  A line that cannot be read is reported (with its line number) and skipped.
Whether a caller gets through at all is decided by the PBX, not here: this file only puts a name on the screen.  A call from a
number that is not in the file still rings ("Incoming call from unknown caller: 312-555-0123"), so a file that has fallen behind
the PBX's list never keeps anyone from getting through.

If the file is missing, the buttons from config.BUTTONS are used (a PC demo), and incoming calls show only the number.
"""

from . import config
from .watched_file import WatchedFile
from .machine import Party, buttons_from_config
from .sound import dialable

BUTTON_KEYS = ("left", "right")


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


def parse(text, log=None):
    """(people, buttons): people = {10-digit number: Party}, buttons = {"left"/"right": Party}."""
    log = log or (lambda msg: None)
    people, buttons = {}, {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [f.strip() for f in line.split("|")]
        fields += [""] * (4 - len(fields))
        number, name, relationship, button = fields[:4]
        digits = normalize(number)
        if len(digits) < 3 or not name:
            log("contacts line %d skipped (needs at least a number and a name): %s" % (n, line))
            continue
        button = button.lower()
        if button and button not in BUTTON_KEYS:
            log("contacts line %d: button must be left or right, not %r (the person is kept, without a button)" % (n, button))
            button = ""
        party = Party(name, relationship, digits, dialable(digits))
        if digits in people:
            log("contacts line %d: %s is listed twice; the later line wins" % (n, pretty(digits)))
        people[digits] = party
        if button:
            if button in buttons:
                log("contacts line %d: two people on the %s button; the later line wins" % (n, button))
            buttons[button] = party
    return people, buttons


class Contacts:
    def __init__(self, path=None, log=None):
        self.path = str(config.CONTACTS_FILE if path is None else path)
        self.log = log or (lambda msg: None)
        self._people, self._buttons = {}, {}
        self._file = WatchedFile(self.path, self.log)
        self.refresh()

    def refresh(self):
        """Read the file again if it changed (or appeared, or disappeared).  True if something changed."""
        changed, text = self._file.read()
        if not changed:
            return False
        if text is None:
            self.log("No contacts file at %s: the buttons use the demo people in config.py, and incoming calls show only the "
                     "number.  (See contacts.example.txt.)" % self.path)
            changed = bool(self._people or self._buttons)
            self._people, self._buttons = {}, {}
            return changed
        self._people, self._buttons = parse(text, self.log)
        missing = [k for k in BUTTON_KEYS if k not in self._buttons]
        self.log("Contacts: %d people from %s%s" % (len(self._people), self.path,
                 "; nobody on the %s button" % " and ".join(missing) if missing else ""))
        return True

    def buttons(self):
        """The people on the two buttons: from the file; without a file, the demo people in config.BUTTONS."""
        if self._file.missing:
            return buttons_from_config()
        return dict(self._buttons)

    def lookup(self, number):
        """The person with this number, or a Party with only the number (name ""), which the screen shows as
        "Incoming call from unknown caller: 312-555-0123".  The call is let through either way: screening is the PBX's job."""
        party = self._people.get(normalize(number))
        return party if party else Party(dial=pretty(number))
