"""Fetch Judi's caller list and events list from the NAS (the master copies) to the Judicom.   python3 -m judicom.sync

The master list is /home/pi/judicom/contacts.txt on the NAS; the PBX screens callers with it, and this puts the same people on the
Judicom: the names shown for incoming calls and the two buttons.  Run by the judicom-contacts-sync timer (at boot, then every
10 minutes); run it by hand for an instant update.

It connects over Tailscale with its own key (~/.ssh/judicom_sync), which the NAS only lets read those two lists: on the NAS's side
the key's line in ~pi/.ssh/authorized_keys is   restrict,command="/home/pi/judicom/serve_list.sh" ssh-ed25519 ...
(serve_list.sh answers "contacts", the default, or "events", and refuses anything else).
The events list (/home/pi/judicom/events.txt on the NAS -> ~/events.txt) is for the info screen; see judicom/events.py.
The verse list likewise (verses.txt).  The people pictures (/home/pi/judicom/people/Ann.png ... -> ~/people/) are for the call
screens (judicom/faces.py); they are compared by sha256 and only fetched when something there changed.
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


def fetch(host=None, key=None, timeout=30, run=subprocess.run, what=None, raw=False):
    """The master list's text ('events': the events list; raw: the bytes), or raises RuntimeError with the reason."""
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
    return result.stdout if raw else result.stdout.decode("utf-8", "replace")


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


VERSES_HEADER = ("# COPY of Judi's verse list.  The master is /home/pi/judicom/verses.txt on the NAS: edit it there.\n"
                 "# This file is replaced every 10 minutes (python3 -m judicom.sync), so changes made here are lost.\n")


def sync_verses(fetcher=None, path=None, log=print):
    """Fetch the verse list; 0 done, 1 not changed (the reason is logged).  Like sync_events."""
    from .verses import parse as parse_verses
    fetcher = fetcher or (lambda: fetch(what="verses"))
    try:
        text = fetcher()
        problems = []
        verses = parse_verses(text, problems.append)
        lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        if lines and not verses:
            raise RuntimeError("the NAS's answer has no verses in it (is serve_list.sh up to date on the NAS?)")
    except RuntimeError as exc:
        log("verses not updated: %s (keeping the current list)" % exc)
        return 1
    for p in problems:
        log("in the NAS's verse list: " + p)
    changed = store(text, str(config.VERSES_FILE if path is None else path), VERSES_HEADER)
    log("verses %s: %d" % ("updated" if changed else "unchanged", len(verses)))
    return 0


def parse_people_list(text):
    """{file name: sha256} from serve_list.sh's "people-list" answer ("<sha256>  ./Ann.png" lines).  Names that are not plain
    picture names (a path, hidden, odd characters, another kind of file) are left out."""
    wanted = {}
    for line in text.splitlines():
        digest, sep, name = line.partition("  ")
        name = name[2:] if name.startswith("./") else name
        if not sep or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            continue
        if (not name or "/" in name or "\\" in name or name.startswith(".") or any(ord(c) < 32 for c in name)
                or os.path.splitext(name)[1].lower() not in config.PEOPLE_EXTS):
            continue
        wanted[name] = digest
    return wanted


def sha256_of(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unpack_people(data, wanted):
    """{name: bytes} of the pictures in the tar file `data`; only names in `wanted`, each checked against its sha256 and the size
    limits.  Raises RuntimeError if the file is not usable."""
    import hashlib
    import io
    import tarfile
    got, total = {}, 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            for m in tar:
                name = os.path.basename(m.name)
                if not m.isfile() or name not in wanted:
                    continue
                if m.size > config.PEOPLE_MAX_FILE:
                    raise RuntimeError("%s is too big (%.1f MB)" % (name, m.size / 1e6))
                total += m.size
                if total > config.PEOPLE_MAX_TOTAL:
                    raise RuntimeError("the pictures add up to more than %d MB" % (config.PEOPLE_MAX_TOTAL // 2 ** 20))
                body = tar.extractfile(m).read()
                if hashlib.sha256(body).hexdigest() != wanted[name]:
                    raise RuntimeError("%s did not arrive whole" % name)
                got[name] = body
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise RuntimeError("the pictures did not arrive whole (%s)" % exc) from None
    missing = sorted(set(wanted) - set(got))
    if missing:
        raise RuntimeError("missing from what the NAS sent: %s" % ", ".join(missing))
    return got


def sync_people(lister=None, fetcher=None, folder=None, log=print):
    """Make the people-pictures folder the same as the NAS's (/home/pi/judicom/people).  The pictures themselves are fetched only
    when the NAS's list differs from what is here.  0 done (changed or not), 1 nothing changed (the reason is logged)."""
    lister = lister or (lambda: fetch(what="people-list"))
    fetcher = fetcher or (lambda: fetch(what="people", raw=True, timeout=300))
    folder = str(config.PEOPLE_DIR if folder is None else folder)
    try:
        wanted = parse_people_list(lister())
        here = {}
        try:
            for n in os.listdir(folder):
                p = os.path.join(folder, n)
                if not n.startswith(".") and os.path.isfile(p):
                    here[n] = sha256_of(p)
        except OSError:
            pass
        new = {n: d for n, d in wanted.items() if here.get(n) != d}
        gone = sorted(set(here) - set(wanted))
        if not new and not gone:
            log("people pictures unchanged: %d" % len(wanted))
            return 0
        got = unpack_people(fetcher(), new) if new else {}
    except RuntimeError as exc:
        log("people pictures not updated: %s (keeping the ones here)" % exc)
        return 1
    os.makedirs(folder, exist_ok=True)
    for name, body in got.items():                       # each written under a hidden name, then renamed: never half a picture
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".people.")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(body)
            os.chmod(tmp, 0o644)
            os.replace(tmp, os.path.join(folder, name))
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    for name in gone:
        try:
            os.unlink(os.path.join(folder, name))
        except OSError:
            pass
    parts = (["new or changed: " + ", ".join(sorted(got))] if got else []) + (["removed: " + ", ".join(gone)] if gone else [])
    log("people pictures updated (%s): %d" % ("; ".join(parts), len(wanted)))
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
    sync_verses()
    sync_people()
    sys.exit(result)


if __name__ == "__main__":
    main()
