#!/usr/bin/env python3
"""Judi's caller list on the NAS -> Asterisk's allowed list.

The master list is /home/pi/judicom/contacts.txt (the same format as the Judicom's file: number | name | relationship | button).
Everyone in it may ring the Judicom.  This script writes them into Asterisk's judicom-allowed.conf and reloads the dialplan, but
only when the list has really changed.  It is run by pi's cron every 10 minutes; run it by hand for an instant update:

    python3 /home/pi/judicom/apply_contacts.py            (--dry-run: show what it would write, change nothing)

A list that cannot be read, or that has nobody in it, changes nothing: the last good allowed list stays (and the reason is logged).
The Judicom fetches the same master file by itself (judicom.sync), for the names on its screen and the two buttons.
Only the standard library: it runs on the NAS without the rest of the Judicom software.
"""
import argparse
import datetime
import os
import subprocess
import sys
import tempfile

MASTER = "/home/pi/judicom/contacts.txt"
ALLOWED = "/home/pi/asterisk-test/config/judicom-allowed.conf"
LOG = "/home/pi/judicom/apply.log"
RELOAD = ["/usr/bin/docker", "exec", "asterisk-test", "asterisk", "-rx", "dialplan reload"]
LOG_MAX = 200_000                      # bytes; the log is cut back to half when it grows past this


def normalize(number):
    """Every way of writing a number -> its digits, 10 for North America ('+1 (641) 555-0142' -> '6415550142')."""
    digits = "".join(ch for ch in (number or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def parse(text):
    """(people, problems): people = [(10 digits, name)] in file order, one per number; problems = messages about skipped lines.
    The same rules as the Judicom's judicom/contacts.py."""
    people, seen, problems = [], {}, []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [f.strip() for f in line.split("|")] + ["", "", ""]
        digits, name = normalize(fields[0]), fields[1]
        if len(digits) < 3 or not name:
            problems.append("line %d skipped (needs at least a number and a name): %s" % (n, line))
            continue
        if digits in seen:
            problems.append("line %d: %s is listed twice; the later line wins" % (n, digits))
            people[seen[digits]] = (digits, name)
            continue
        seen[digits] = len(people)
        people.append((digits, name))
    return people, problems


def render(people):
    safe = lambda s: "".join(ch for ch in s if ch.isalnum() or ch in " -'.")[:40] or "caller"     # noqa: E731
    lines = ["; Who may ring the Judicom.  WRITTEN BY /home/pi/judicom/apply_contacts.py from /home/pi/judicom/contacts.txt:",
             "; edit that file, not this one (this one is replaced).",
             "[judicom-allowed]"]
    lines += ["exten => %s,1,NoOp(%s)" % (digits, safe(name)) for digits, name in people]
    return "\n".join(lines) + "\n"


def log(msg, path=LOG):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(msg)
    try:
        if os.path.exists(path) and os.path.getsize(path) > LOG_MAX:
            with open(path, "rb") as fh:
                fh.seek(-LOG_MAX // 2, os.SEEK_END)
                tail = fh.read()
            with open(path, "wb") as fh:
                fh.write(tail[tail.find(b"\n") + 1:])
        with open(path, "a") as fh:
            fh.write("%s %s\n" % (stamp, msg))
    except OSError:
        pass


def write_atomically(path, text):
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".judicom-allowed.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def apply(master=MASTER, allowed=ALLOWED, reload_cmd=RELOAD, dry_run=False, logger=log):
    """Returns 0 (nothing to do, or done), 1 (the list is unusable: nothing changed), 2 (written but the reload failed)."""
    try:
        with open(master, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        logger("cannot read %s (%s): the allowed list is left as it is" % (master, exc))
        return 1
    people, problems = parse(text)
    for p in problems:
        logger(p)
    if not people:
        logger("%s has nobody in it: the allowed list is left as it is" % master)
        return 1
    new = render(people)
    try:
        with open(allowed, encoding="utf-8") as fh:
            old = fh.read()
    except OSError:
        old = None
    if new == old:
        return 0
    if dry_run:
        print(new, end="")
        return 0
    if old is not None:
        write_atomically(allowed + ".prev", old)     # the list before this change, in case it has to be put back by hand
    write_atomically(allowed, new)
    try:
        result = subprocess.run(reload_cmd, capture_output=True, text=True, timeout=30)
        ok = result.returncode == 0 and "reloaded" in (result.stdout + result.stderr).lower()
        why = (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        ok, why = False, str(exc)
    if not ok:
        logger("wrote %s (%d people) but the dialplan reload failed: %s" % (allowed, len(people), why))
        return 2
    logger("allowed list updated: %d people (%s)" % (len(people), ", ".join(name for _, name in people)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write Asterisk's allowed list from Judi's caller list.")
    ap.add_argument("--dry-run", action="store_true", help="show what would be written; change nothing")
    args = ap.parse_args(argv)
    sys.exit(apply(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
