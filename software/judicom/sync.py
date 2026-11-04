"""Fetch Judi's caller list and events list from the NAS (the master copies) to the Judicom.   python3 -m judicom.sync

The master list is /home/pi/judicom/contacts.txt on the NAS; the PBX screens callers with it, and this puts the same people on the
Judicom: the names shown for incoming calls and the two buttons.  Run by the judicom-contacts-sync timer (at boot, then every
10 minutes); run it by hand for an instant update.

It connects over Tailscale with its own key (~/.ssh/judicom_sync), which the NAS only lets read those two lists: on the NAS's side
the key's line in ~pi/.ssh/authorized_keys is   restrict,command="/home/pi/judicom/serve_list.sh" ssh-ed25519 ...
(serve_list.sh answers "contacts", the default, or "events", and refuses anything else).
The events list (/home/pi/judicom/events.txt on the NAS -> ~/events.txt) is for the info screen; see judicom/events.py.
The fetched list replaces ~/contacts.txt only if it reads correctly and has somebody in it; otherwise the old one stays (and the
reason is printed: journalctl -u judicom-contacts-sync).  The file is replaced in one step, so the phone never sees half of it.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from . import config
from .contacts import parse

EVENTS_HEADER = ("# COPY of Judi's events list.  The master is /home/pi/judicom/events.txt on the NAS: edit it there.\n"
                 "# This file is replaced every 10 minutes (python3 -m judicom.sync), so changes made here are lost.\n")

HEADER = ("# COPY of Judi's caller list.  The master is /home/pi/judicom/contacts.txt on the NAS: edit it there.\n"
          "# This file is replaced every 10 minutes (python3 -m judicom.sync), so changes made here are lost.\n")


def fetch(host=None, key=None, timeout=30, run=subprocess.run, what=None):
    """The master list's text ('events': the events list), or raises RuntimeError with the reason."""
    host = host or config.SYNC_HOST
    key = key or config.SYNC_KEY
    cmd = ["ssh", "-i", key, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=15",
           "-o", "StrictHostKeyChecking=accept-new", host] + ([what] if what else [])
    try:
        result = run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("cannot reach %s: %s" % (host, exc)) from None
    if result.returncode != 0:
        why = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("%s refused (%s)" % (host, why[-1] if why else "exit status %d" % result.returncode))
    return result.stdout.decode("utf-8", "replace")


def check(text):
    """(people, buttons, problems) of a fetched list; raises RuntimeError if it must not be used."""
    problems = []
    people, buttons = parse(text, problems.append)
    if not people:
        raise RuntimeError("the list from the NAS has nobody in it")
    return people, buttons, problems


def store(text, path=None, header=HEADER):
    """Write the list (with the 'this is a copy' header) in one step.  True if the file changed."""
    path = str(config.CONTACTS_FILE if path is None else path)
    body = header + "\n" + text.lstrip("\n")
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.read() == body:
                return False
    except OSError:
        pass
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".contacts.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return True


def check_events(text):
    """(events, problems) of a fetched events list; raises RuntimeError if it must not be used.  An empty list is fine (nothing
    coming up); a list in which no line at all is an event is not (that is not an events list: the NAS answered something else)."""
    from .events import parse as parse_events
    problems = []
    events = parse_events(text, problems.append)
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if lines and not events:
        raise RuntimeError("the NAS's answer has no events in it (is serve_list.sh in place on the NAS?)")
    return events, problems


def sync_events(fetcher=None, path=None, log=print):
    """Fetch the events list; 0 done, 1 not changed (the reason is logged).  The caller list does not depend on it."""
    fetcher = fetcher or (lambda: fetch(what="events"))
    try:
        text = fetcher()
        events, problems = check_events(text)
    except RuntimeError as exc:
        log("events not updated: %s (keeping the current list)" % exc)
        return 1
    for p in problems:
        log("in the NAS's events list: " + p)
    changed = store(text, str(config.EVENTS_FILE if path is None else path), EVENTS_HEADER)
    log("events %s: %d" % ("updated" if changed else "unchanged", len(events)))
    return 0


def sync(fetcher=fetch, path=None, log=print):
    """0: done (changed or not), 1: nothing changed because the list could not be fetched or is not usable."""
    try:
        text = fetcher()
        people, buttons, problems = check(text)
    except RuntimeError as exc:
        log("contacts not updated: %s (keeping the current list)" % exc)
        return 1
    for p in problems:
        log("in the NAS's list: " + p)
    missing = [k for k in ("left", "right") if k not in buttons]
    if missing:
        log("note: nobody is on the %s button in the NAS's list" % " and ".join(missing))
    changed = store(text, path)
    log("contacts %s: %d people" % ("updated" if changed else "unchanged", len(people)))
    return 0


def main(argv=None):
    argparse.ArgumentParser(prog="python3 -m judicom.sync", description=__doc__.splitlines()[0]).parse_args(argv)
    result = sync()
    sync_events()                                        # the caller list matters more: its result is the exit status
    sys.exit(result)


if __name__ == "__main__":
    main()
