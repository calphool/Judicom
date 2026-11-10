#!/usr/bin/env python3
"""The Judicom's housekeeping website, on the NAS:  https://naspi.local:8080   (also over Tailscale: https://naspi-1:8080)

    Callers         who may ring Judi, the names on her screen and her two buttons  (/home/pi/judicom/contacts.txt; applied to
                    Asterisk at once with apply_contacts.py)
    Events          birthdays, holidays and visits for the info screen  (/home/pi/judicom/events.txt)
    Caller pictures the faces on the call screens: cropped square from the middle and made 800 x 800 PNG  (/home/pi/judicom/people)
    Photos          the slideshow, with captions  (/mnt/8tbdrive/Photos/Judi, shared with Jellyfin; very big photos are shrunk)
    See Judicom Now what its screen is showing, looked at again every 10 seconds while the page is in view, and a message to
                    send her: a speech bubble with the face of someone in the caller list, and three beeps.  The page says
                    when she has read it.  (Both over SSH with a key that can do nothing else: docs/DEPLOYMENT.md;
                    what was sent: /home/pi/judicom/sent_messages.json)

The Judicom fetches the lists and caller pictures every 10 minutes and the photos every hour.

Safety:
  - every page needs signing in as pi, with pi's own password on the NAS (checked by PAM, so no copy of it is kept here).  A sign-in
    lasts LOGIN_HOURS, or until the website restarts.  LOGIN_TRIES wrong tries from one address lock it out for LOGIN_LOCK_SECONDS;
  - it speaks HTTPS, with a self-signed certificate from make_cert.sh, so the password does not cross the network in the clear
    (browsers warn once about the certificate);
  - only addresses on the home network, Tailscale and the NAS itself are answered; anything else gets 403;
  - only requests addressed to the NAS's own names and addresses are answered (stops "DNS rebinding" from a web page elsewhere);
  - every change needs the form's token, which other web sites cannot read (stops a page elsewhere from posting to this one);
  - each list is checked before it is saved (a bad entry is shown, nothing is written), the previous version is kept in
    /home/pi/judicom/history/, and removed pictures are moved to /mnt/8tbdrive/.judicom-deleted/, not erased.

Run by judicom-admin.service as pi.  By hand:  python3 /home/pi/Judicom/deploy/nas/admin/judicom_admin.py  [--port 8080]
Needs Flask, Pillow and PAM for Python (Debian: python3-flask python3-pil python3-pampy) and the rest of this repository (it uses software/judicom).
"""
import argparse
import datetime
import io
import ipaddress
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from jinja2 import DictLoader
from PIL import Image, ImageOps
from werkzeug.serving import WSGIRequestHandler
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "software"))
from judicom import callers as callers_mod  # noqa: E402
from judicom import events as events_mod  # noqa: E402
from judicom import messages as messages_mod  # noqa: E402
from judicom import photos as photos_mod  # noqa: E402

PICTURE_EXTS = (".jpg", ".jpeg", ".png")
FACE_PX = 800
PHOTO_MAX_PX = 3000                 # a photo bigger than this (longest side) is shrunk to it when uploaded
HISTORY_KEEP = 30
SCREEN_EVERY = 10                   # seconds between looks at the Judicom's screen, while someone has the page in view
SCREEN_FRESH = 5                    # a look this recent is shared, so two people watching do not double the work on the Judicom
SCREEN_TIMEOUT = 25                 # seconds; a look takes about 3
SENT_KEEP = 20                      # messages remembered, and shown on the page: the newest 5
NETS = [ipaddress.ip_network(n) for n in ("127.0.0.0/8", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                          "100.64.0.0/10", "fd7a:115c:a1e0::/48", "fe80::/10")]
HOSTS = {"naspi", "naspi.local", "naspi-1", "localhost"}
TLS_CERT, TLS_KEY = Path("/home/pi/judicom/tls/cert.pem"), Path("/home/pi/judicom/tls/key.pem")      # from make_cert.sh
IDLE_CONNECTION_SECONDS = 60        # a connection that sends nothing for this long is dropped
LOGIN_USER = "pi"                   # the only one who may sign in
LOGIN_HOURS = 12
LOGIN_TRIES = 5                     # wrong tries from one address before it has to wait
LOGIN_LOCK_SECONDS = 300
MAX_PASSWORD = 1024
SAFE_NEXT = re.compile(r"^/(?!/)[A-Za-z0-9_\-./?=&%+]*$")     # where to go after signing in: a page of this site, nothing else
NO_SIGN_IN_NEEDED = {"login"}
ASKED_BY_SCRIPT = {"screen_png", "screen_sent"}                # these answer 401; a page would get a sign-in form it cannot show


class HandshakeLater(ssl.SSLContext):
    """HTTPS, with each connection's handshake in that connection's own thread.  By default the server shakes hands in its one
    accepting loop, so a connection that says nothing (browsers keep spare ones open) stops the website for everybody."""

    def wrap_socket(self, sock, server_side=False, do_handshake_on_connect=True, **kw):
        return super().wrap_socket(sock, server_side=server_side, do_handshake_on_connect=False, **kw)


class Handler(WSGIRequestHandler):
    timeout = IDLE_CONNECTION_SECONDS


def tls_context(cert, key):
    context = HandshakeLater(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    return context


def pam_check(user, password):
    """True only if PAM says the password is right.  A program can check its own user's password without being root.
    Whatever goes wrong is a no, and nothing about the password is ever written down."""
    try:
        import pam
        return pam.authenticate(user, password, service="login", resetcreds=False) is True
    except Exception as exc:                                   # noqa: BLE001 - python3-pampy missing, or a password PAM cannot take
        print("(cannot check a password: %s)" % type(exc).__name__, file=sys.stderr, flush=True)
        return False


@dataclass
class Settings:
    judicom_dir: Path = Path("/home/pi/judicom")
    photos_dir: Path = Path("/mnt/8tbdrive/Photos/Judi")
    trash_dir: Path = Path("/mnt/8tbdrive/.judicom-deleted")
    apply: list = field(default_factory=lambda: ["/usr/bin/python3", "/home/pi/judicom/apply_contacts.py"])
    hosts: set = field(default_factory=lambda: set(HOSTS))
    screen: list = field(default_factory=lambda: ["/usr/bin/ssh", "-i", "/home/pi/.ssh/judicom_screen", "-o", "BatchMode=yes",
                                                  "-o", "ConnectTimeout=5", "joe@judicom"])
    check_password: object = pam_check
    clock: object = time.monotonic

    @property
    def sent(self):
        return self.judicom_dir / "sent_messages.json"

    @property
    def contacts(self):
        return self.judicom_dir / "contacts.txt"

    @property
    def events(self):
        return self.judicom_dir / "events.txt"

    @property
    def people(self):
        return self.judicom_dir / "people"

    @property
    def history(self):
        return self.judicom_dir / "history"

    @property
    def cache(self):
        return self.judicom_dir / "web-cache"


# ------------------------------------------------------------------ files ----------------------------------------------------
def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def write_atomically(path, data, mode=0o644):
    """Write path in one step (a reader never sees half of it).  data: str or bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data.encode("utf-8") if isinstance(data, str) else data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def keep_old_version(s, path):
    """Copy the current file into the history folder (newest HISTORY_KEEP per list kept)."""
    path = Path(path)
    if not path.exists():
        return
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    write_atomically(s.history / ("%s.%s" % (path.name, stamp)), path.read_bytes())
    old = sorted(p for p in s.history.glob(path.name + ".*"))
    for p in old[:-HISTORY_KEEP]:
        p.unlink()


def move_to_trash(s, path, kind):
    """Move a removed picture aside (never erased): trash_dir/kind/YYYY-MM-DD-HHMMSS name."""
    path = Path(path)
    folder = s.trash_dir / kind
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("%s %s" % (datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S"), path.name))
    n = 2
    while target.exists():
        target = folder / ("%s %d %s" % (datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S"), n, path.name))
        n += 1
    try:
        os.replace(path, target)
    except OSError:                                   # another drive: copy, then remove
        target.write_bytes(path.read_bytes())
        path.unlink()
    return target


# ------------------------------------------------------------------ callers -------------------------------------------------
CONTACTS_HEADER = """# Judi's caller list: who may ring the Judicom, the names on its screen, and its two buttons.
# Kept by the housekeeping website (https://naspi.local:8080); it can be edited by hand too.
# One person per line:   number | name | relationship | button (left / right / empty)
"""


digits_of, pretty = callers_mod.normalize, callers_mod.pretty      # the one way numbers are read (judicom/callers.py)


def read_callers(s):
    """Every person line of the list as a row of the form, as written (also lines the phone would skip, so they can be fixed)."""
    rows = []
    for line in read(s.contacts).splitlines():
        f = callers_mod.fields(line)
        if f is None:
            continue
        rows.append({"number": pretty(f[0]) or f[0], "name": f[1], "relationship": f[2], "button": f[3]})
    return rows


def check_callers(rows):
    """(clean rows, errors) for the rows of the form (blank rows already left out)."""
    errors, seen, buttons, clean = [], {}, {}, []
    for i, r in enumerate(rows, 1):
        number, name = r["number"].strip(), " ".join(r["name"].split())
        relationship, button = " ".join(r["relationship"].split()), r["button"].strip().lower()
        who = name or "row %d" % i
        d = digits_of(number)
        if len(d) != 10:
            errors.append("%s: the number must have 10 digits (area code first), not %r" % (who, number))
        if not name:
            errors.append("row %d: a name is needed" % i)
        for label, text in (("name", name), ("relationship", relationship)):
            if "|" in text or "#" in text[:1] or "/" in text or len(text) > 40:
                errors.append("%s: the %s may not contain | or /, start with #, or be longer than 40 letters" % (who, label))
        if button not in ("", "left", "right"):
            errors.append("%s: the button must be left, right or none" % who)
        if d in seen and len(d) == 10:
            errors.append("%s: %s is already listed for %s" % (who, pretty(d), seen[d]))
        seen.setdefault(d, who)
        if button:
            if button in buttons:
                errors.append("%s and %s are both on the %s button; only one person can be" % (buttons[button], who, button))
            buttons.setdefault(button, who)
        clean.append({"number": pretty(d), "name": name, "relationship": relationship, "button": button})
    if not clean:
        errors.append("the list would be empty: nobody could ring Judi, so it is not saved")
    names = {}
    for r in clean:
        k = r["name"].casefold()
        if k in names:
            errors.append("two people are called %s: give them different names (the caller pictures go by name)" % r["name"])
        names[k] = True
    return clean, errors


def render_callers(rows):
    w = [max([len(r[k]) for r in rows] + [len(h)]) for k, h in (("number", "number"), ("name", "name"),
                                                                  ("relationship", "relationship"))]
    lines = [CONTACTS_HEADER.rstrip("\n"), ""]
    for r in rows:
        line = "%s | %s | %s" % (r["number"].ljust(w[0]), r["name"].ljust(w[1]), r["relationship"].ljust(w[2]))
        lines.append((line + " | " + r["button"]) if r["button"] else line.rstrip())
    return "\n".join(lines) + "\n"


def form_rows(form, fields):
    """The rows posted by a table form: field names like number-3, name-3 ...; rows marked remove-3 are left out, blank rows too."""
    ids = sorted({k.split("-", 1)[1] for k in form if "-" in k and k.split("-", 1)[0] in fields},
                 key=lambda x: int(x) if x.isdigit() else 0)
    rows = []
    for i in ids:
        if form.get("remove-" + i):
            continue
        row = {f: form.get("%s-%s" % (f, i), "") for f in fields}
        if any(v.strip() for k, v in row.items() if k not in ("kind",)):
            rows.append(row)
    return rows


# ------------------------------------------------------------------ events --------------------------------------------------
def split_events_file(text):
    """(header lines, rows): the comment block at the top is kept as it is; after it, each '# ...' line becomes a heading row
    and each 'when | what' line an event row (in file order)."""
    lines = text.splitlines()
    header, i = [], 0
    while i < len(lines) and lines[i].strip().startswith("#"):
        header.append(lines[i].rstrip())
        i += 1
    rows = []
    for line in lines[i:]:
        t = line.strip()
        if not t:
            continue
        if t.startswith("#"):
            rows.append({"kind": "heading", "when": "", "what": t.lstrip("#").strip(" -")})
        else:
            when, _, what = (p.strip() for p in t.partition("|"))
            rows.append({"kind": "event", "when": when, "what": what})
    return header, rows


def check_event(when, what):
    """(Event, None) or (None, the reason it cannot be used)."""
    problems = []
    found = events_mod.parse("%s | %s" % (when, what), problems.append)
    if found:
        return found[0], None
    why = problems[0] if problems else "cannot be read"
    why = why.split("(", 1)[1].rsplit(")", 1)[0] if "(" in why else why
    return None, why


def check_events(rows):
    errors, clean = [], []
    for r in rows:
        kind = r.get("kind") or "event"
        when, what = " ".join(r.get("when", "").split()), " ".join(r.get("what", "").split())
        if kind == "heading":
            if what:
                clean.append({"kind": "heading", "when": "", "what": what})
            continue
        if "|" in what or "|" in when:
            errors.append("%s: no | please" % (what or when))
            continue
        _, why = check_event(when, what)
        if why:
            errors.append("%s: %s" % (what or when or "an event", why))
        clean.append({"kind": "event", "when": when, "what": what})
    return clean, errors


def render_events(header, rows):
    width = max([len(r["when"]) for r in rows if r["kind"] == "event"] + [8])
    out = list(header) + [""] if header else []
    for r in rows:
        if r["kind"] == "heading":
            if out and out[-1] != "":
                out.append("")
            out.append("# ---- " + r["what"])
        else:
            out.append("%s | %s" % (r["when"].ljust(width), r["what"]))
    return "\n".join(out).rstrip("\n") + "\n"


def sorted_by_date(rows, year):
    """The rows with each section's events in calendar order, as they fall in the given year (Thanksgiving, Easter and the
    like are worked out for that year).  A one-time event goes by its own date; one that cannot be read goes to the end of
    its section.  The headings stay where they are."""
    def key(r):
        ev, _ = check_event(r["when"], r["what"])
        d = None
        if ev is not None:
            d = datetime.date(ev.year, ev.month, ev.day) if ev.year is not None else ev.date_in(year)
            if d is None:                                   # a 5th weekday that is not there this year: about its month's end
                d = datetime.date(year, ev.month, 28)
        t = ev.time if ev is not None and ev.time else datetime.time(0)
        return (d is None, d or datetime.date.max, t)
    out, section = [], []
    for r in rows + [{"kind": "heading"}]:
        if r["kind"] == "heading":
            out += sorted(section, key=key)                  # (a stable sort: same-day events keep their order)
            section = []
            out.append(r)
        else:
            section.append(r)
    return out[:-1]


def with_blank_rows(rows, at_end=2):
    """The rows to show: a blank row for a new event at the end of each section (so a holiday can go with the holidays) and a
    couple more at the very end.  Each blank row knows its section's heading, for its hint."""
    out, section = [], ""                                       # (the hint leaves out any "(...)" in the heading)
    for r in rows:
        if r["kind"] == "heading":
            if out and out[-1]["kind"] != "heading":
                out.append({"kind": "new", "when": "", "what": "", "section": section})
            section = r["what"].split("(")[0].strip()
        out.append(r)
    out += [{"kind": "new", "when": "", "what": "", "section": section} for _ in range(at_end)]
    return out


def next_dates(rows, now):
    """For each event row: 'December 25 (51 days to go)' or '' (a one-off that is over, or not readable)."""
    out = []
    for r in rows:
        if r["kind"] != "event":
            out.append("")
            continue
        ev, why = check_event(r["when"], r["what"])
        if ev is None:
            out.append("")
            continue
        up = events_mod.upcoming([ev], now, 1)
        out.append("%s (%s)" % (up[0].when, up[0].countdown) if up else "over")
    return out


# ------------------------------------------------------------------ pictures ------------------------------------------------
def picture_files(folder):
    try:
        return sorted(p for p in Path(folder).iterdir()
                      if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in PICTURE_EXTS)
    except OSError:
        return []


def safe_name(name):
    """A caller's name as a file name: as written, without anything a file name cannot hold (check_callers allows no / or |)."""
    name = " ".join("".join(c for c in name if c.isprintable() and c not in '/\\:*?"<>|').split()).lstrip(".")
    return name or "person"


def name_key(name):
    return " ".join(name.replace("_", " ").split()).casefold()


def open_upright(data):
    """A Pillow image from uploaded bytes, turned the right way up (phones store the turn separately).  ValueError if unusable."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:                                                    # noqa: BLE001 - anything Pillow cannot read
        raise ValueError("this is not a picture that can be used (.jpg or .png from a phone or computer work): %s" % exc)
    return ImageOps.exif_transpose(img)


def face_png(data, size=FACE_PX):
    """resize.py's crop: the largest centred square, made size x size (LANCZOS), as PNG bytes."""
    img = open_upright(data)
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def photo_bytes(data, filename):
    """(bytes, extension) to store for a slideshow photo: as it came if it is a .jpg/.png no bigger than PHOTO_MAX_PX, otherwise
    turned upright, shrunk to PHOTO_MAX_PX and saved as JPEG."""
    img = open_upright(data)
    ext = Path(filename).suffix.lower()
    if ext in PICTURE_EXTS and max(img.size) <= PHOTO_MAX_PX:
        return data, ".jpg" if ext == ".jpeg" else ext
    img.thumbnail((PHOTO_MAX_PX, PHOTO_MAX_PX), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=90)
    return out.getvalue(), ".jpg"


def thumbnail(s, path, size):
    """A cached small JPEG of a picture (made again when the picture changes)."""
    st = path.stat()
    cache = s.cache / ("%s-%d-%d-%d.jpg" % (path.name, size, int(st.st_mtime), st.st_size))
    if not cache.exists():
        with Image.open(path) as img:
            img.draft("RGB", (size * 2, size * 2))                           # JPEG: decode at a fraction of the size (fast)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=82)
        for old in s.cache.glob("%s-%d-*.jpg" % (glob_escape(path.name), size)):
            old.unlink()
        write_atomically(cache, out.getvalue())
    return cache


def glob_escape(name):
    return "".join("[%s]" % c if c in "*?[" else c for c in name)


def read_caption(photo):
    meta = photos_mod.caption_file(photo)
    if meta is None:
        return {"people": "", "relationship": "", "taken": ""}
    c = photos_mod.parse_caption(read(meta))
    return {"people": c.people, "relationship": c.relationship, "taken": c.taken}


def write_caption(photo, people, relationship, taken):
    """The .meta file next to the photo (people / relationship / taken), the way the mail importer writes it; removed if empty."""
    meta = Path(photo).with_suffix(".meta")
    fields = [("people", people), ("relationship", relationship), ("taken", taken)]
    lines = ["%s: %s" % (k, " ".join(v.split())) for k, v in fields if v.strip()]
    if lines:
        write_atomically(meta, "\n".join(lines) + "\n")
    elif meta.exists():
        meta.unlink()


# ------------------------------------------------------------------ the web site --------------------------------------------
def judicom_screen(command):
    """The PNG the Judicom sends back, or None if it does not (it is off, its Tailscale is down, it is not showing a picture)."""
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=SCREEN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 and result.stdout.startswith(b"\x89PNG") else None


def send_message(command, sender, text):
    """Hands a message to the Judicom.  (its id, None), or (None, why not)."""
    message_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
    body = json.dumps({"id": message_id, "from": sender, "text": text}).encode()
    try:
        result = subprocess.run(command + ["message"], input=body, capture_output=True, timeout=SCREEN_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None, "The Judicom is not answering, so the message was not sent."
    if result.returncode == 0 and result.stdout.strip() == b"ok":
        return message_id, None
    said = result.stderr.decode(errors="replace").strip().splitlines()
    if result.returncode == 1 and said and said[-1].startswith("nas_request: "):
        return None, "The Judicom refused the message: %s." % said[-1][len("nas_request: "):]
    return None, "The Judicom did not take the message, so it was not sent."


def judicom_statuses(command):
    """{message id: when it was read, or None}, or None if the Judicom does not say."""
    try:
        result = subprocess.run(command + ["messages"], stdin=subprocess.DEVNULL, capture_output=True, timeout=SCREEN_TIMEOUT)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def read_sent(s):
    try:
        return json.loads(read(s.sent) or "[]")
    except ValueError:
        return []


def read_at_words(when):
    """'2026-11-06T15:12:00' -> 'Read at 3:12 PM', with the day if that was not today."""
    moment = datetime.datetime.fromisoformat(when)
    words = "Read at " + moment.strftime("%I:%M %p").lstrip("0")
    return words if moment.date() == datetime.date.today() else words + " on " + moment.strftime("%b %d")


def allowed_address(addr):
    try:
        ip = ipaddress.ip_address((addr or "").split("%")[0])
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return any(ip in n for n in NETS if n.version == ip.version)


def allowed_host(host, names):
    host = (host or "").strip().lower()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host in names or allowed_address(host) or host.endswith(".ts.net")


def create_app(s=None):
    s = s or Settings()
    app = Flask(__name__)
    app.secret_key = secrets.token_bytes(32)                  # signs the sign-in cookie; new at every start, which signs everyone out
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 400 * 1024 * 1024       # a batch of phone photos
    app.jinja_loader = DictLoader(TEMPLATES)
    token = secrets.token_urlsafe(24)
    screen_lock = threading.Lock()
    last_look = {"png": None, "at": 0.0}
    sent_lock = threading.Lock()
    last_asked = {"at": 0.0}
    login_lock = threading.Lock()
    wrong = {}                                                # address -> [wrong tries, when they are forgotten]

    def signed_in():
        return session.get("user") == LOGIN_USER and s.clock() < session.get("until", 0)

    @app.before_request
    def guard():
        if not allowed_address(request.remote_addr):
            abort(403, "only the home network and Tailscale may use this site")
        if not allowed_host(request.host, s.hosts):
            abort(403, "unknown host name %r" % request.host)
        if request.endpoint not in NO_SIGN_IN_NEEDED and not signed_in():
            if request.endpoint in ASKED_BY_SCRIPT:
                return "Please sign in.", 401, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}
            return redirect(url_for("login", next=request.full_path.rstrip("?")) if request.method == "GET" else url_for("login"))
        if request.method == "POST" and request.form.get("token") != token:
            abort(403, "the form has expired: go back, reload the page and try again")

    @app.context_processor
    def common():
        return {"token": token, "signed_in": signed_in(),
                "nav": [("home", "Home"), ("callers", "Callers"), ("events", "Events"), ("people", "Caller pictures"),
                        ("photos", "Photos"), ("screen", "See Judicom Now")] if signed_in() else []}

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("message.html", title="Not allowed", text=e.description), 403

    @app.errorhandler(413)
    def too_big(e):
        return render_template("message.html", title="Too big", text="That was more than 400 MB at once: send fewer photos at "
                               "a time."), 413

    # ---- signing in
    def try_password(user, password):
        """(signed in?, what to tell them).  One at a time, so that many tries at once cannot get past the count."""
        address = request.remote_addr
        with login_lock:
            now = s.clock()
            for gone in [a for a, (_, forget) in wrong.items() if forget <= now]:
                del wrong[gone]
            if wrong.get(address, [0])[0] >= LOGIN_TRIES:
                return False, "Too many wrong tries.  Wait a few minutes and try again."
            good = (secrets.compare_digest(user.encode(), LOGIN_USER.encode()) and 0 < len(password) <= MAX_PASSWORD and
                    s.check_password(LOGIN_USER, password))
            if good:
                wrong.pop(address, None)
                return True, ""
            entry = wrong.setdefault(address, [0, 0])
            entry[0], entry[1] = entry[0] + 1, s.clock() + LOGIN_LOCK_SECONDS
            print("wrong sign-in %d from %s" % (entry[0], address), file=sys.stderr, flush=True)
            if entry[0] >= LOGIN_TRIES:
                return False, "Too many wrong tries.  Wait a few minutes and try again."
            return False, "That user name or password is not right."

    @app.route("/login", methods=["GET", "POST"])
    def login():
        target = request.values.get("next", "")
        target = target if SAFE_NEXT.match(target) else url_for("home")
        if request.method == "GET":
            return redirect(target) if signed_in() else render_template("login.html", title="Sign in", next=target, error="")
        good, words = try_password(request.form.get("user", ""), request.form.get("password", ""))
        if not good:
            return render_template("login.html", title="Sign in", next=target, error=words), 401
        session.clear()
        session["user"], session["until"] = LOGIN_USER, s.clock() + LOGIN_HOURS * 3600
        return redirect(target)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ---- home
    @app.route("/")
    def home():
        callers = read_callers(s)
        _, rows = split_events_file(read(s.events))
        evs = [e for e in (check_event(r["when"], r["what"])[0] for r in rows if r["kind"] == "event") if e]
        coming = events_mod.upcoming(evs, datetime.datetime.now(), 3)
        log = read(s.judicom_dir / "apply.log").splitlines()[-3:]
        return render_template("home.html", callers=callers, coming=coming, photos=len(picture_files(s.photos_dir)),
                               faces=len(picture_files(s.people)), log=log)

    # ---- callers
    @app.route("/callers", methods=["GET", "POST"])
    def callers():
        if request.method == "GET":
            return render_template("callers.html", rows=read_callers(s), errors=[])
        rows = form_rows(request.form, ("number", "name", "relationship", "button"))
        clean, errors = check_callers(rows)
        if errors:
            return render_template("callers.html", rows=rows, errors=errors), 400
        text = render_callers(clean)
        if text == read(s.contacts):
            flash("No changes.")
            return redirect(url_for("callers"))
        keep_old_version(s, s.contacts)
        write_atomically(s.contacts, text)
        try:
            r = subprocess.run(s.apply, capture_output=True, text=True, timeout=60)
            out = (r.stdout + r.stderr).strip()
            if r.returncode == 0:
                flash("Saved.  Who may ring Judi is updated on the phone system now; Judi's screen and buttons follow within "
                      "10 minutes.")
            else:
                flash("Saved, but updating the phone system failed (it tries again within 10 minutes): %s" % out[-300:], "error")
        except (OSError, subprocess.TimeoutExpired) as exc:
            flash("Saved, but updating the phone system failed (it tries again within 10 minutes): %s" % exc, "error")
        return redirect(url_for("callers"))

    # ---- events
    @app.route("/events", methods=["GET", "POST"])
    def events():
        header, rows = split_events_file(read(s.events))
        if request.method == "POST":
            rows = form_rows(request.form, ("kind", "when", "what"))
            clean, errors = check_events(rows)
            if errors:
                rows = with_blank_rows(rows)
                return render_template("events.html", rows=rows, errors=errors, next=next_dates(rows, datetime.datetime.now()),
                                       coming=[]), 400
            if request.form.get("sort"):
                clean = sorted_by_date(clean, datetime.date.today().year)
            text = render_events(header, clean)
            if text == read(s.events):
                flash("No changes.")
            else:
                keep_old_version(s, s.events)
                write_atomically(s.events, text)
                flash("Saved.  Judi's info screen shows it within 10 minutes.")
            return redirect(url_for("events"))
        now = datetime.datetime.now()
        evs = [e for e in (check_event(r["when"], r["what"])[0] for r in rows if r["kind"] == "event") if e]
        rows = with_blank_rows(rows)
        return render_template("events.html", rows=rows, errors=[], next=next_dates(rows, now),
                               coming=events_mod.upcoming(evs, now, 3))

    # ---- caller pictures
    def face_for(name):
        for p in picture_files(s.people):
            if name_key(p.stem) == name_key(name):
                return p
        return None

    @app.route("/people")
    def people():
        names = [r["name"] for r in read_callers(s)]
        files = picture_files(s.people)
        listed = {name_key(n) for n in names}
        return render_template("people.html", people=[(n, face_for(n)) for n in names],
                               extra=[p for p in files if name_key(p.stem) not in listed])

    @app.route("/people/upload", methods=["POST"])
    def people_upload():
        name = request.form.get("name", "")
        if name_key(name) not in {name_key(r["name"]) for r in read_callers(s)}:
            abort(400, "%r is not in the caller list" % name)
        up = request.files.get("picture")
        if not up or not up.filename:
            flash("Choose a picture first.", "error")
            return redirect(url_for("people"))
        try:
            png = face_png(up.read())
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("people"))
        target = s.people / (safe_name(name) + ".png")       # named as in the caller list: the Judicom matches it by name
        old = face_for(name)
        if old is not None:
            move_to_trash(s, old, "caller pictures")
        write_atomically(target, png)
        flash("%s's picture is saved (800 x 800).  The Judicom shows it within 10 minutes." % name)
        return redirect(url_for("people"))

    @app.route("/people/remove", methods=["POST"])
    def people_remove():
        p = file_in(s.people, request.form.get("file", ""))
        move_to_trash(s, p, "caller pictures")
        flash("Removed %s (kept in %s)." % (p.name, s.trash_dir / "caller pictures"))
        return redirect(url_for("people"))

    @app.route("/people/img/<path:name>")
    def people_img(name):
        return send_file(thumbnail(s, file_in(s.people, name), 200), mimetype="image/jpeg", max_age=0)

    # ---- photos
    @app.route("/photos")
    def photos():
        files = sorted(picture_files(s.photos_dir), key=lambda p: p.stat().st_mtime, reverse=True)
        return render_template("photos.html", photos=[(p, read_caption(p)) for p in files])

    @app.route("/photos/upload", methods=["POST"])
    def photos_upload():
        ups = [u for u in request.files.getlist("pictures") if u and u.filename]
        if not ups:
            flash("Choose one or more photos first.", "error")
            return redirect(url_for("photos"))
        saved, failed = [], []
        caption = [request.form.get(k, "") for k in ("people", "relationship", "taken")]
        for up in ups:
            try:
                data, ext = photo_bytes(up.read(), up.filename)
            except ValueError as exc:
                failed.append("%s: %s" % (up.filename, exc))
                continue
            stem = Path(secure_filename(up.filename)).stem or "photo"
            target, n = s.photos_dir / (stem + ext), 2
            while target.exists() or target.with_suffix(".meta").exists():
                target, n = s.photos_dir / ("%s_%d%s" % (stem, n, ext)), n + 1
            write_atomically(target, data)
            if any(c.strip() for c in caption):
                write_caption(target, *caption)
            saved.append(target.name)
        if saved:
            flash("Saved %d photo(s): %s.  The Judicom gets them within the hour." % (len(saved), ", ".join(saved)))
        for f in failed:
            flash(f, "error")
        return redirect(url_for("photos"))

    @app.route("/photos/caption", methods=["POST"])
    def photos_caption():
        p = file_in(s.photos_dir, request.form.get("file", ""))
        write_caption(p, request.form.get("people", ""), request.form.get("relationship", ""), request.form.get("taken", ""))
        flash("Caption saved for %s." % p.name)
        return redirect(url_for("photos") + "#" + p.name)

    @app.route("/photos/remove", methods=["POST"])
    def photos_remove():
        p = file_in(s.photos_dir, request.form.get("file", ""))
        move_to_trash(s, p, "photos")
        meta = photos_mod.caption_file(p)
        if meta is not None:
            move_to_trash(s, meta, "photos")
        flash("Removed %s (kept in %s)." % (p.name, s.trash_dir / "photos"))
        return redirect(url_for("photos"))

    @app.route("/photos/img/<path:name>")
    def photos_img(name):
        return send_file(thumbnail(s, file_in(s.photos_dir, name), 360), mimetype="image/jpeg", max_age=0)

    # ---- what the Judicom is showing
    @app.route("/screen")
    def screen():
        return screen_page(sender=request.args.get("from", ""))

    def screen_page(sender="", text="", errors=None):
        return render_template("screen.html", title="See Judicom Now", every=SCREEN_EVERY, callers=caller_names(), sender=sender,
                               text=text, errors=errors, max_text=messages_mod.MAX_TEXT)

    def caller_names():
        return list(dict.fromkeys(c["name"] for c in read_callers(s) if c["name"]))

    @app.route("/screen/message", methods=["POST"])
    def screen_message():
        sender, typed = request.form.get("from", ""), request.form.get("text", "")
        text = messages_mod.clean_text(typed)
        if sender not in caller_names():
            problem = "Choose who the message is from."
        elif not text:
            problem = "Type a message first."
        elif len(text) > messages_mod.MAX_TEXT:
            problem = "That is too long for the screen: %d characters at most." % messages_mod.MAX_TEXT
        else:
            message_id, problem = send_message(s.screen, sender, text)
        if problem:
            return screen_page(sender, typed, [problem])
        with sent_lock:
            rows = read_sent(s) + [{"id": message_id, "from": sender, "text": text, "read_at": None}]
            write_atomically(s.sent, json.dumps(rows[-SENT_KEEP:]).encode())
        last_asked["at"] = 0.0
        flash("Sent." if text == " ".join(typed.split()) else "Sent, without the emoji (the Judicom cannot show them).")
        return redirect(url_for("screen", **{"from": sender}))

    @app.route("/screen/sent")
    def screen_sent():
        """What was sent lately and whether Judi has read it.  The Judicom is only asked while something is unread."""
        with sent_lock:
            rows = read_sent(s)
            if any(r["read_at"] is None for r in rows) and time.monotonic() - last_asked["at"] >= SCREEN_EVERY:
                last_asked["at"] = time.monotonic()
                known = judicom_statuses(s.screen)
                if known is not None:
                    for r in rows:
                        r["read_at"] = r["read_at"] or known.get(r["id"])
                    write_atomically(s.sent, json.dumps(rows).encode())
        return jsonify([{"from": r["from"], "text": r["text"],
                         "status": read_at_words(r["read_at"]) if r["read_at"] else "Waiting for Judi"} for r in rows[-5:][::-1]])

    @app.route("/screen.png")
    def screen_png():
        with screen_lock:                                  # one look at a time; whoever waited shares the answer
            if time.monotonic() - last_look["at"] >= SCREEN_FRESH or last_look["png"] is None:
                last_look["png"] = judicom_screen(s.screen)
                last_look["at"] = time.monotonic()
            png = last_look["png"]
        if png is None:
            return "The Judicom is not answering.", 503, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}
        return png, {"Content-Type": "image/png", "Cache-Control": "no-store"}

    def file_in(folder, name):
        """The picture called name in folder, or 404 (no paths, no hidden files, nothing else)."""
        for p in picture_files(folder):
            if p.name == name:
                return p
        abort(404)

    return app


# ------------------------------------------------------------------ the pages -----------------------------------------------
TEMPLATES = {
    "base.html": """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ title or "Judicom" }} - Judicom housekeeping</title>
<style>
:root{--bg:#f4f6f6;--card:#fff;--ink:#1f2a2c;--soft:#5f7378;--teal:#24424a;--accent:#2f7d6d;--line:#d7dfe0;--err:#b3261e;--errbg:#fdecea}
*{box-sizing:border-box}body{margin:0;font:16px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--teal);color:#fff;padding:12px 16px;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center}
header b{font-size:18px;margin-right:8px}header a{color:#dfeeee;text-decoration:none;padding:4px 0}header a.on{color:#fff;border-bottom:2px solid #fff}
main{max-width:1000px;margin:0 auto;padding:16px}h1{font-size:24px;margin:8px 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 16px}
.msg{padding:10px 14px;border-radius:8px;background:#e6f4ef;margin:0 0 12px}.msg.error,.errors{background:var(--errbg);color:var(--err)}
.errors{padding:10px 14px 10px 30px;border-radius:8px;margin:0 0 12px}
.help{color:var(--soft);font-size:14px}table{border-collapse:collapse;width:100%}th{text-align:left;font-size:13px;color:var(--soft);font-weight:600}
td,th{padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:middle}input[type=text],select{width:100%;padding:7px 8px;font:inherit;border:1px solid var(--line);border-radius:6px;background:#fff}
tr.heading td{background:#eef3f3;font-weight:600}tr.new input{background:#fbfdfd}
button,.button{font:inherit;padding:8px 16px;border-radius:8px;border:0;background:var(--accent);color:#fff;cursor:pointer}
button.quiet{background:#e7ecec;color:var(--ink)}button.danger{background:#fff;color:var(--err);border:1px solid #e3b5b1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.tile img{width:100%;border-radius:6px;display:block;background:#dde4e4}.tile .name{font-weight:600;margin:6px 0}
.tile input[type=text]{margin:3px 0}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px}.nopic{aspect-ratio:1;display:flex;align-items:center;justify-content:center;color:var(--soft);background:#e9eeee;border-radius:6px}
.when{white-space:nowrap;color:var(--soft);font-size:14px}@media(max-width:640px){td,th{padding:4px 3px}.hide-small{display:none}}
</style></head><body>
<header><b>Judicom</b>{% for ep, label in nav %}<a href="{{ url_for(ep) }}" class="{{ 'on' if request.endpoint == ep else '' }}">{{ label }}</a>{% endfor %}{% if signed_in %}<form method="post" action="{{ url_for('logout') }}" style="margin-left:auto"><input type="hidden" name="token" value="{{ token }}"><button type="submit">Sign out</button></form>{% endif %}</header>
<main>{% for cat, m in get_flashed_messages(with_categories=true) %}<div class="msg {{ cat }}">{{ m }}</div>{% endfor %}
{% if errors %}<ul class="errors">{% for e in errors %}<li>{{ e }}</li>{% endfor %}</ul>{% endif %}
{% block body %}{% endblock %}</main></body></html>""",

    "screen.html": """{% extends "base.html" %}{% block body %}<h1>See Judicom Now</h1>
<form class="card" method="post" action="{{ url_for('screen_message') }}"><input type="hidden" name="token" value="{{ token }}">
<b>Send Judi a message</b>
<p class="help">It appears on her screen in a speech bubble with three beeps, and stays until she touches the screen, presses a button or lifts the handset. During a call it waits until the call is over, and between 9 PM and 6 AM until the morning.</p>
<textarea name="text" rows="3" maxlength="{{ max_text }}" required style="width:100%;padding:7px 8px;font:inherit;border:1px solid var(--line);border-radius:6px" placeholder="Your message, up to {{ max_text }} characters">{{ text }}</textarea>
<div class="row"><label for="from">From</label><select id="from" name="from" required style="width:auto;flex:1 1 160px"><option value="">Choose a face</option>
{% for name in callers %}<option{{ " selected" if name == sender else "" }}>{{ name }}</option>{% endfor %}</select><button>Send</button></div>
</form>
<div class="card" id="sent" hidden><b>Sent lately</b><table id="sent-rows"></table></div>
<p class="help" id="status">Asking the Judicom...</p>
<img id="shot" alt="What the Judicom's screen is showing" style="display:block;width:100%;max-width:450px;aspect-ratio:600/1024;margin:0 auto;border-radius:8px;background:#dde4e4">
<script>
(function () {
  var shot = document.getElementById("shot"), status = document.getElementById("status"), timer, url;
  function look() {
    clearTimeout(timer);
    if (document.hidden) return;                       // nobody is watching: leave the Judicom alone until they come back
    fetch("{{ url_for('screen_png') }}", {cache: "no-store"}).then(function (r) {
      if (r.status === 401) location.reload();         // the sign-in has run out
      if (!r.ok) throw new Error("no answer");
      return r.blob();
    }).then(function (picture) {
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(picture);
      shot.src = url;
      shot.style.opacity = 1;
      status.textContent = "Updated at " + new Date().toLocaleTimeString() + ". Looks again every {{ every }} seconds.";
    }).catch(function () {
      shot.style.opacity = 0.4;
      status.textContent = "The Judicom is not answering. Trying again every {{ every }} seconds.";
    }).then(sent).then(function () {
      timer = setTimeout(look, {{ every }} * 1000);
    });
  }
  function sent() {
    return fetch("{{ url_for('screen_sent') }}", {cache: "no-store"}).then(function (r) { return r.json(); }).then(function (rows) {
      var table = document.getElementById("sent-rows");
      table.textContent = "";
      rows.forEach(function (row) {
        var tr = table.insertRow();
        [row.from, row.text, row.status].forEach(function (words) { tr.insertCell().textContent = words; });
      });
      document.getElementById("sent").hidden = !rows.length;
    }).catch(function () {});
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) look(); });
  look();
})();
</script>{% endblock %}""",

    "login.html": """{% extends "base.html" %}{% block body %}<h1>Sign in</h1>
<form method="post" action="{{ url_for('login') }}" class="card" style="max-width:360px"><input type="hidden" name="token" value="{{ token }}">
<input type="hidden" name="next" value="{{ next }}">
{% if error %}<p style="color:var(--err)">{{ error }}</p>{% endif %}
<p><label>User name<br><input name="user" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" autofocus required style="width:100%"></label></p>
<p><label>Password<br><input name="password" type="password" autocomplete="current-password" required style="width:100%"></label></p>
<p><button type="submit">Sign in</button></p></form>{% endblock %}""",

    "message.html": """{% extends "base.html" %}{% block body %}<h1>{{ title }}</h1><div class="card">{{ text }}</div>{% endblock %}""",

    "home.html": """{% extends "base.html" %}{% block body %}<h1>Judi's Judicom</h1>
<div class="card"><b>Callers</b>: {{ callers|length }} people may ring Judi
({% for c in callers %}{{ c.name }}{% if c.button %} - {{ c.button }} button{% endif %}{{ ", " if not loop.last }}{% endfor %}).
<a href="{{ url_for('callers') }}">Edit</a></div>
<div class="card"><b>Coming up</b> on her info screen:<ul>{% for u in coming %}<li>{{ u.title }}: {{ u.when }} ({{ u.countdown }})</li>{% else %}<li>nothing</li>{% endfor %}</ul>
<a href="{{ url_for('events') }}">Edit events</a></div>
<div class="card"><b>Pictures</b>: {{ photos }} photos in the slideshow (<a href="{{ url_for('photos') }}">add or change</a>),
{{ faces }} caller pictures (<a href="{{ url_for('people') }}">add or change</a>).</div>
<div class="card help">The Judicom picks up callers, events and caller pictures within 10 minutes, and photos within the hour.
{% if log %}<br>Phone system: {{ log[-1] }}{% endif %}</div>{% endblock %}""",

    "callers.html": """{% extends "base.html" %}{% set title = "Callers" %}{% block body %}<h1>Callers</h1>
<p class="help">Everyone here may ring Judi (everyone else hears a message); their name shows on her screen when they call.
The two people on the <b>left</b> and <b>right</b> buttons are the ones she can call.</p>
<form method="post" class="card"><input type="hidden" name="token" value="{{ token }}">
<table><tr><th>Phone number</th><th>Name</th><th>Relationship to Judi</th><th>Button</th><th>Remove</th></tr>
{% for r in rows %}{% set i = loop.index %}<tr>
<td><input type="text" name="number-{{ i }}" value="{{ r.number }}" inputmode="tel" placeholder="212-555-0142"></td>
<td><input type="text" name="name-{{ i }}" value="{{ r.name }}"></td>
<td><input type="text" name="relationship-{{ i }}" value="{{ r.relationship }}" placeholder="daughter"></td>
<td><select name="button-{{ i }}">{% for b in ["", "left", "right"] %}<option value="{{ b }}" {{ "selected" if r.button == b }}>{{ b or "none" }}</option>{% endfor %}</select></td>
<td><input type="checkbox" name="remove-{{ i }}" value="1" title="remove"></td></tr>{% endfor %}
{% for j in range(3) %}{% set i = rows|length + loop.index %}<tr class="new">
<td><input type="text" name="number-{{ i }}" inputmode="tel" placeholder="new: number"></td><td><input type="text" name="name-{{ i }}" placeholder="name"></td>
<td><input type="text" name="relationship-{{ i }}" placeholder="relationship"></td>
<td><select name="button-{{ i }}"><option value="">none</option><option>left</option><option>right</option></select></td><td></td></tr>{% endfor %}
</table><div class="row"><button>Save callers</button><a href="{{ url_for('callers') }}">Undo my edits</a></div></form>
<p class="help">The relationship reads on her screen as "Ann (daughter)".  The previous list is kept in /home/pi/judicom/history on the NAS.</p>{% endblock %}""",

    "events.html": """{% extends "base.html" %}{% set title = "Events" %}{% block body %}<h1>Events</h1>
{% if coming %}<div class="card"><b>On Judi's screen now:</b><ul>{% for u in coming %}<li>{{ u.title }}: {{ u.when }} ({{ u.countdown }})</li>{% endfor %}</ul></div>{% endif %}
<div class="card help">How to write <b>When</b>: <b>12-25</b> every year &middot; <b>2026-11-08 10:30</b> once (the time is optional: 10:30, 2 PM) &middot;
<b>4th Thursday of November</b> or <b>last Monday of May</b> &middot; <b>Easter</b> &middot; <b>Sunday after 1st Monday of September</b> &middot; <b>4th Sunday before 12-25</b> &middot; <b>46 days before Easter</b> &middot;
the church year by name: <b>Shrove Tuesday</b>, <b>Ash Wednesday</b>, <b>Palm Sunday</b>, <b>Maundy Thursday</b>, <b>Good Friday</b>, <b>Holy Saturday</b>, <b>Ascension Day</b>, <b>Pentecost</b>, <b>Trinity Sunday</b>, <b>Christ the King</b>, <b>Advent</b>, and <b>4th Sunday after Pentecost</b>.
A one-time event drops off by itself when its day is over.  Grey rows are headings, just for you; each section ends with a blank row for adding one there.</div>
<form method="post" class="card"><input type="hidden" name="token" value="{{ token }}">
<table><tr><th>When</th><th>What</th><th class="hide-small">Next</th><th>Remove</th></tr>
{% for r in rows %}{% set i = loop.index %}{% if r.kind == 'new' %}<tr class="new">
<td><input type="hidden" name="kind-{{ i }}" value="event"><input type="text" name="when-{{ i }}" placeholder="new: when"></td><td><input type="text" name="what-{{ i }}" placeholder="{{ ('add to ' ~ r.section) if r.section else 'what' }}"></td><td class="hide-small"></td><td></td></tr>
{% else %}<tr class="{{ 'heading' if r.kind == 'heading' }}">
{% if r.kind == 'heading' %}<td colspan="2"><input type="hidden" name="kind-{{ i }}" value="heading"><input type="text" name="what-{{ i }}" value="{{ r.what }}"></td><td class="hide-small"></td>
{% else %}<td><input type="hidden" name="kind-{{ i }}" value="event"><input type="text" name="when-{{ i }}" value="{{ r.when }}"></td><td><input type="text" name="what-{{ i }}" value="{{ r.what }}"></td>
<td class="when hide-small">{{ next[loop.index0] }}</td>{% endif %}
<td><input type="checkbox" name="remove-{{ i }}" value="1" title="remove"></td></tr>{% endif %}{% endfor %}
</table><div class="row"><button>Save events</button><button name="sort" value="1">Sort by date and save</button>
<a href="{{ url_for('events') }}">Undo my edits</a></div></form>
<p class="help">Sort puts each section in calendar order (January first); days like Thanksgiving or Easter go by this year's date.</p>{% endblock %}""",

    "people.html": """{% extends "base.html" %}{% set title = "Caller pictures" %}{% block body %}<h1>Caller pictures</h1>
<p class="help">The face shown while Judi calls someone, talks with them, or when they ring.  Any picture works: it is cropped to a
square from the middle and made 800 x 800.  A head-and-shoulders picture with the face filling most of it is best.</p>
<div class="grid">{% for name, pic in people %}<div class="tile">
{% if pic %}<img src="{{ url_for('people_img', name=pic.name) }}" alt="{{ name }}">{% else %}<div class="nopic">no picture yet</div>{% endif %}
<div class="name">{{ name }}</div>
<form method="post" action="{{ url_for('people_upload') }}" enctype="multipart/form-data"><input type="hidden" name="token" value="{{ token }}">
<input type="hidden" name="name" value="{{ name }}"><input type="file" name="picture" accept="image/*" required>
<div class="row"><button>{{ "Replace" if pic else "Upload" }}</button></div></form>
{% if pic %}<form method="post" action="{{ url_for('people_remove') }}" onsubmit="return confirm('Remove {{ name }}\\'s picture?')">
<input type="hidden" name="token" value="{{ token }}"><input type="hidden" name="file" value="{{ pic.name }}"><div class="row"><button class="danger">Remove</button></div></form>{% endif %}
</div>{% endfor %}</div>
{% if extra %}<h1>Pictures of people not in the caller list</h1><p class="help">Not shown on the Judicom (a picture goes by the caller's name).</p>
<div class="grid">{% for p in extra %}<div class="tile"><img src="{{ url_for('people_img', name=p.name) }}" alt=""><div class="name">{{ p.name }}</div>
<form method="post" action="{{ url_for('people_remove') }}"><input type="hidden" name="token" value="{{ token }}"><input type="hidden" name="file" value="{{ p.name }}">
<button class="danger">Remove</button></form></div>{% endfor %}</div>{% endif %}{% endblock %}""",

    "photos.html": """{% extends "base.html" %}{% set title = "Photos" %}{% block body %}<h1>Photos</h1>
<form method="post" action="{{ url_for('photos_upload') }}" enctype="multipart/form-data" class="card"><input type="hidden" name="token" value="{{ token }}">
<b>Add photos to Judi's slideshow</b> <span class="help">(.jpg or .png; several at once is fine; very big ones are made smaller)</span>
<div class="row"><input type="file" name="pictures" accept="image/jpeg,image/png" multiple required></div>
<p class="help">Caption (optional, for all the photos chosen): who is in it, how they are related to Judi, and when it was taken.</p>
<div class="row"><input type="text" name="people" placeholder="People: Ann and Hannah" style="flex:1 1 200px">
<input type="text" name="relationship" placeholder="Relationship: daughter, granddaughter" style="flex:1 1 200px">
<input type="text" name="taken" placeholder="Taken: Christmas 2025" style="flex:1 1 140px"></div>
<div class="row"><button>Upload</button></div></form>
<div class="grid">{% for p, c in photos %}<div class="tile" id="{{ p.name }}"><img src="{{ url_for('photos_img', name=p.name) }}" alt="" loading="lazy">
<form method="post" action="{{ url_for('photos_caption') }}"><input type="hidden" name="token" value="{{ token }}"><input type="hidden" name="file" value="{{ p.name }}">
<input type="text" name="people" value="{{ c.people }}" placeholder="People"><input type="text" name="relationship" value="{{ c.relationship }}" placeholder="Relationship">
<input type="text" name="taken" value="{{ c.taken }}" placeholder="Taken"><div class="row"><button class="quiet">Save caption</button></div></form>
<form method="post" action="{{ url_for('photos_remove') }}" onsubmit="return confirm('Remove this photo from the slideshow?')"><input type="hidden" name="token" value="{{ token }}">
<input type="hidden" name="file" value="{{ p.name }}"><div class="row"><button class="danger">Remove</button> <span class="help">{{ p.name }}</span></div></form>
</div>{% else %}<p>No photos yet.</p>{% endfor %}</div>{% endblock %}""",
}


def main(argv=None):
    ap = argparse.ArgumentParser(description="The Judicom's housekeeping website.")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all; only home and Tailscale are answered)")
    args = ap.parse_args(argv)
    s = Settings()
    s.hosts |= {h.strip().lower() for h in os.environ.get("ADMIN_HOSTS", "").split(",") if h.strip()}
    app = create_app(s)
    tls = tls_context(TLS_CERT, TLS_KEY) if TLS_CERT.is_file() and TLS_KEY.is_file() else None
    if tls:
        app.config["SESSION_COOKIE_SECURE"] = True
    else:
        print("WARNING: no certificate, so passwords cross the network in the clear: run make_cert.sh", file=sys.stderr, flush=True)
    app.run(host=args.host, port=args.port, threaded=True, ssl_context=tls, request_handler=Handler)


if __name__ == "__main__":
    main()
