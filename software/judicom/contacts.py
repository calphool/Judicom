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
from .callers import BUTTON_KEYS, normalize, pretty, read     # noqa: F401  (normalize, pretty: used from here elsewhere too)
from .watched_file import WatchedFile
from .machine import Party, buttons_from_config
from .sound import dialable


def parse(text, log=None):
    """(people, buttons): people = {10-digit number: Party}, buttons = {"left"/"right": Party}.  The reading itself is
    judicom/callers.py, shared with the NAS (Asterisk's allowed list) and the housekeeping website."""
    log = log or (lambda msg: None)
    entries, on_buttons, problems = read(text)
    for problem in problems:
        log("contacts " + problem)
    people = {e.digits: Party(e.name, e.relationship, e.digits, dialable(e.digits)) for e in entries}
    buttons = {key: Party(e.name, e.relationship, e.digits, dialable(e.digits)) for key, e in on_buttons.items()}
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
