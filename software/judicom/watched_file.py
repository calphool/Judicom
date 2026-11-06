"""A text file that is read again only when it changes: the contacts, events and verses files, which judicom.sync replaces
from the NAS now and then.

    f = WatchedFile(path, log)
    changed, text = f.read()       # (False, None): the same as last time, nothing to do
                                   # (True, text):  new text (the first read, or the file was changed)
                                   # (True, None):  there is no file (at the first read, or it has gone)
    f.missing                      # True while there is no file

"Changed" means its modification time or size is different.  A file that is there but cannot be read is logged and counts as
unchanged (what was read before is kept), and it is tried again when it next changes.  Bytes that are not UTF-8 are replaced by a
mark (U+FFFD) rather than stopping the read.  No pygame needed.
"""
import os

_UNREAD = object()


class WatchedFile:
    def __init__(self, path, log=None):
        self.path = str(path)
        self.log = log or (lambda msg: None)
        self._stamp = _UNREAD

    @property
    def missing(self):
        return self._stamp is None

    def read(self):
        try:
            st = os.stat(self.path)
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            stamp = None
        if stamp == self._stamp:
            return False, None
        self._stamp = stamp
        if stamp is None:
            return True, None
        try:
            with open(self.path, encoding="utf-8", errors="replace") as fh:
                return True, fh.read()
        except OSError as exc:
            self.log("Cannot read %s: %s (keeping what was read before)" % (self.path, exc))
            return False, None
