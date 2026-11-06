#!/usr/bin/env python3
"""Emails when the Judicom is offline (not registered with the PBX), and when it is back.   Run by pi's cron every 5 minutes.

    watch_judicom.py              check (and email if needed)
    watch_judicom.py --status     only say what it sees, send nothing
    watch_judicom.py --test       send a test email now

What counts as offline: the Judicom has no registration with Asterisk (its Wi-Fi or Tailscale is down, it is unplugged or hung,
baresip stopped), or Asterisk itself does not answer (then Judi's calls fail too).
Emails: one when it has been offline for DELAY_MINUTES; then, if REMINDER_HOUR is set, one reminder a day at about that hour while
it is still offline; and one when it is back, with how long it was gone.  Short blips (a restart, a Wi-Fi hiccup) send nothing.
Settings: /home/pi/judicom/watch.env (not in git: it has the email address):
    ALERT_TO=someone@example.com
    DELAY_MINUTES=30          (optional)
    REMINDER_HOUR=9           (optional; 0 or empty: no daily reminders)
The email goes out through the mail importer's Gmail account (GMAIL_USER / GMAIL_APP_PASSWORD in its config.env; read, never copied).
State: /home/pi/judicom/watch.state; log: /home/pi/judicom/watch.log.  Only the standard library.
"""
import argparse
import datetime
import json
import os
import smtplib
import subprocess
import sys
from email.message import EmailMessage

SETTINGS = "/home/pi/judicom/watch.env"
GMAIL = "/home/pi/jellyfin-mail-importer/config.env"
STATE = "/home/pi/judicom/watch.state"
LOG = "/home/pi/judicom/watch.log"
CONTACTS = ["/usr/bin/docker", "exec", "asterisk-test", "asterisk", "-rx", "pjsip show contacts"]
LOG_MAX = 200_000


def load_env(path):
    values = {}
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def look(run=subprocess.run):
    """('up', '') or ('down', why)."""
    try:
        r = run(CONTACTS, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "down", "the phone system (Asterisk on the NAS) did not answer: %s" % exc
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "Unable to connect" in out:
        return "down", "the phone system (Asterisk on the NAS) did not answer"
    for line in out.splitlines():
        if line.strip().startswith("Contact:") and "judicom/" in line and "Unavail" not in line:
            return "up", ""
    return "down", "the Judicom is not connected to the phone system"


def how_long(seconds):
    minutes = int(seconds // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if days:
        parts.append("%d day%s" % (days, "" if days == 1 else "s"))
    if hours:
        parts.append("%d hour%s" % (hours, "" if hours == 1 else "s"))
    if not days and (minutes or not parts):
        parts.append("%d minute%s" % (minutes, "" if minutes == 1 else "s"))
    return " ".join(parts)


def stamp(ts):
    d = datetime.datetime.fromtimestamp(ts)
    return "%s, %s %d at %d:%02d %s" % (d.strftime("%A"), d.strftime("%B"), d.day, d.hour % 12 or 12, d.minute,
                                         "AM" if d.hour < 12 else "PM")


ADVICE = """What usually causes it, most likely first:
  - the Wi-Fi at the nursing home is down, or the Judicom was moved out of its reach
  - the Judicom was unplugged or switched off (or the power went off)
  - the Judicom's Tailscale connection is down
If you can, check from a computer on Tailscale:  ssh joe@judicom   (or through the NAS: ssh -J pi@naspi.local joe@judicom)
Until it is back, callers hear "Judi can't come to the phone right now".
"""


def message(kind, since, now, why):
    if kind == "offline":
        return ("Judicom offline since %s" % stamp(since),
                "The Judicom has been offline since %s (%s).\n\nReason seen: %s.\n\n%s\nYou will get one email when it is back."
                % (stamp(since), how_long(now - since), why, ADVICE))
    if kind == "reminder":
        return ("Judicom still offline (%s)" % how_long(now - since),
                "The Judicom is still offline: since %s, %s now.\n\nReason seen: %s.\n\n%s" % (stamp(since), how_long(now - since), why, ADVICE))
    if kind == "back":
        return ("Judicom back online", "The Judicom is back online (%s).  It was offline for %s, since %s."
                % (stamp(now), how_long(now - since), stamp(since)))
    return ("Judicom alert test", "This is a test of the Judicom's offline alerts.  If you can read it, they reach you.\n"
            "Sent %s." % stamp(now))


def send(subject, body, settings, gmail, smtp=smtplib.SMTP):
    msg = EmailMessage()
    msg["From"] = "Judicom <%s>" % gmail["GMAIL_USER"]
    msg["To"] = settings["ALERT_TO"]
    msg["Subject"] = subject
    msg.set_content(body)
    with smtp("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login(gmail["GMAIL_USER"], gmail["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


def log(text, path=LOG, now=None):
    line = "%s %s" % (datetime.datetime.fromtimestamp(now or datetime.datetime.now().timestamp()).strftime("%Y-%m-%d %H:%M"), text)
    print(text)
    try:
        if os.path.exists(path) and os.path.getsize(path) > LOG_MAX:
            with open(path) as fh:
                keep = fh.readlines()[-500:]
            with open(path, "w") as fh:
                fh.writelines(keep)
        with open(path, "a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_state(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh)
    os.replace(tmp, path)


def step(now, seen, state, settings, mailer, logger):
    """One check.  seen = ('up', '') or ('down', why).  Returns the new state (and sends what is due through mailer)."""
    status, why = seen
    delay = float(settings.get("DELAY_MINUTES") or 30) * 60
    hour = settings.get("REMINDER_HOUR", "9").strip()
    hour = int(hour) if hour.isdigit() and 0 < int(hour) < 24 else None
    state = dict(state)

    def mail(kind, since):
        subject, body = message(kind, since, now, why)
        try:
            mailer(subject, body)
        except Exception as exc:                        # noqa: BLE001 - no internet, Gmail refused: try again next time
            logger("could not send '%s': %s (will try again)" % (subject, exc))
            return False
        logger("sent: %s" % subject)
        return True

    if status == "up":
        if state.get("down_since") and state.get("alerted"):
            if not mail("back", state["down_since"]):
                return state                             # keep the outage until the "back" email is out
        elif state.get("down_since"):
            logger("back after %s (no email: shorter than %d minutes)" % (how_long(now - state["down_since"]), delay // 60))
        return {"last_up": now}

    if not state.get("down_since"):
        logger("offline: %s" % why)
        state["down_since"] = state.get("last_up", now) if now - state.get("last_up", now) < 600 else now
    since = state["down_since"]
    if not state.get("alerted"):
        if now - since >= delay and mail("offline", since):
            state["alerted"], state["reminded"] = True, now
    elif hour is not None:
        today_at = datetime.datetime.fromtimestamp(now).replace(hour=hour, minute=0, second=0, microsecond=0).timestamp()
        due = now >= today_at > state.get("reminded", 0) and now - state.get("reminded", 0) >= 12 * 3600
        if due and mail("reminder", since):
            state["reminded"] = now
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description="Email when the Judicom is offline, and when it is back.")
    ap.add_argument("--status", action="store_true", help="only say what it sees; send nothing")
    ap.add_argument("--test", action="store_true", help="send a test email now")
    args = ap.parse_args(argv)
    settings, gmail = load_env(SETTINGS), load_env(GMAIL)
    if not settings.get("ALERT_TO"):
        sys.exit("No ALERT_TO in %s: nobody to tell." % SETTINGS)
    if not (gmail.get("GMAIL_USER") and gmail.get("GMAIL_APP_PASSWORD")):
        sys.exit("No Gmail account in %s: cannot send." % GMAIL)
    mailer = lambda subject, body: send(subject, body, settings, gmail)        # noqa: E731
    now = datetime.datetime.now().timestamp()
    if args.test:
        subject, body = message("test", now, now, "")
        mailer(subject, body)
        log("sent: %s" % subject, now=now)
        return
    seen = look()
    state = load_state(STATE)
    if args.status:
        print("now: %s%s" % (seen[0], " (%s)" % seen[1] if seen[1] else ""))
        if state.get("down_since"):
            print("offline since %s; email sent: %s" % (stamp(state["down_since"]), "yes" if state.get("alerted") else "not yet"))
        return
    save_state(STATE, step(now, seen, state, settings, mailer, lambda t: log(t, now=now)))


if __name__ == "__main__":
    main()
