#!/usr/bin/env python3
"""
judicom_mockup.py - Judicom screen MOCK-UP / prototype.

Draws every screen of the Judicom state machine and lets you force the mode from the keyboard.  Nothing is hooked up yet (no GPIO,
no SIP, no network check); this is for looking at the screens and the timing.  The program keeps running until you quit.

THE NINE MODES (keys 1-8 are the numbers of your list; 9 is new)
  1  Family photos     5 photos, then ...      (photo, with the people / relationship / date from its .meta file as a caption)
  2  Weather / date / upcoming events          for 30 s, then back to the photos
  3  Night: black screen with only the date and time   (scheduled 9:00 pm - 6:00 am, see --night-schedule)
  4  Handset lifted: "Who would you like to call?" with arrows down to the Clark and Amy buttons, and a DIAL TONE in the handset
  5  Calling Amy (daughter)...
  6  Ongoing call with Amy (daughter)...
  7  Call ended with Amy (daughter)...     for 5 s, then back to the photos
  8  Incoming call from ...                (press 8 again for the next sample caller)
  9  No answer.                            for 10 s, then back to the arrows (the mock-up has no hook switch: it assumes the handset is
                                           still lifted, and that for screen 7 it was hung up)
OTHER KEYS
  a / c            Amy / Clark is the other party.  On screen 4 this is the same as pressing that button (-> calling).
  space or ->      next photo               n   network problem on / off (the yellow warning at the top, in every mode)
  h or ?           key help on the screen    q or Esc   quit
Type the keys in the terminal (SSH session) that started the program, in its window (--window on a PC), or on a USB keyboard
attached to the Judicom.  Every mode change is also printed in the terminal.

Run on the Judicom (no desktop needed):     python3 judicom_mockup.py
Try on a PC, in a window:                   python3 judicom_mockup.py --window
Needs:   sudo apt install python3-pygame python3-pil      (python3-pil turns phone photos the right way up and keeps them small)

PHOTOS
  The folder is ~/photos (or --photos DIR).  If it does not exist, built-in demo pictures are used.   --write-samples DIR writes a
  small sample set (pictures + .meta files) into DIR, so you can see the file format by example.
  Each picture IMG_0001.jpg may have a caption file IMG_0001.meta (IMG_0001.jpg.meta works too), plain text:

      people: Clark and Amy
      relationship: Your husband and your daughter
      taken: 2019-06-14

  'taken' may be 2019-06-14, 2019-06 or 2019 (shown as "June 14, 2019" ...) or any other text, which is shown as it is.  Write the
  relationship the way it should read on the screen.  Lines without a "word:" in front are used in that same order
  (people, relationship, taken).  No .meta file = no caption.  The folder is looked at again whenever the photos start, so the twice-a-day
  sync is picked up.  Photos are shown in random order, none repeated until all have been shown.

THINGS I CHOSE (all are constants at the top): 15 s per photo, 0.8 s cross-fade, call-ended screen 5 s, no-answer screen 10 s,
the dial tone stops by itself after 60 s (the arrows stay), the night window 21:00-06:00.
At night, calls are not blocked: a call mode replaces the black screen, and when the call is over the screen goes back to black.

OPTIONS
  --speed N          run all timers N times faster (try 10)         --time HH:MM[:SS]   pretend the clock starts at that time
  --night-schedule   switch to / from mode 3 at 21:00 / 06:00 by the clock (off by default, so the screens can be looked at at any hour)
  --photos DIR       --write-samples DIR      --snapshots DIR (save a PNG of every screen, then exit)
  --no-sound         no dial tone.  Otherwise screen 4 plays it on the handset speaker (the USB sound device, found by itself; set the
                     loudness with `alsamixer -c Device`).  Without a USB sound device it is only mentioned in the terminal.
  --window / --no-rotate / --flip   same as the other Judicom utilities (the panel is mounted sideways: --flip if it is upside-down)
"""
import argparse
import array
import datetime
import enum
import math
import os
import random
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    import termios
    import tty
except ImportError:                                  # Windows: keys only through the window
    termios = tty = None

try:
    import pygame
except ImportError:
    sys.exit("pygame is missing:   sudo apt install python3-pygame")

# ---------------------------------------------------------------- edit here -------------------------------------------------
W, H = 600, 1024                                     # the picture is always drawn upright at this size (the panel is mounted sideways)
PHOTO_DIR = Path.home() / "photos"
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
PHOTOS_PER_ROUND = 5
PHOTO_SECONDS = 15.0
FADE_SECONDS = 0.8
WEATHER_SECONDS = 30.0
CALL_ENDED_SECONDS = 5.0
NO_ANSWER_SECONDS = 10.0
DIAL_TONE_SECONDS = 60.0                             # the dial tone plays at most this long; the arrows stay on the screen
NIGHT_FROM, NIGHT_TO = datetime.time(21, 0), datetime.time(6, 0)
MAX_PHOTO_PX = 1400                                  # photos are shrunk to this when loaded (the Pi 3A+ has little memory)

CONTACTS = {"clark": ("Clark", "husband"), "amy": ("Amy", "daughter")}      # the two buttons: (name, relationship)
BUTTON_CX = {"clark": W // 2 - 129, "amy": W // 2 + 129}      # screen x above each button: buttons 37 mm apart, 600 px = 86 mm of screen

# demo data - to be replaced by the real feeds later
DEMO_WEATHER = {"icon": "partly", "temp": 62, "text": "Partly cloudy", "high": 68, "low": 51}
DEMO_EVENTS = [("Today, 3:00 PM", "Visit from Amy"),
               ("Thursday, 10:30 AM", "Hair appointment"),
               ("Saturday, 12:00 PM", "Lunch with Clark")]
DEMO_CALLERS = [("(999) 999-9999", "Sydney", "Granddaughter"), ("(555) 010-2345", None, None)]    # (number, name, relationship)

DIAL_TONE_HZ = (350.0, 440.0)                        # the North American dial tone: two steady tones together
DIAL_TONE_LEVEL = 0.12                               # each tone, as a fraction of full scale (together about -12 dBFS: moderate)
AUDIO_RATE = 16000

BANNER_TEXT = "Network problem, phone cannot receive or send calls..."

BG, CARD = (36, 66, 74), (52, 90, 100)               # the teal of the boot splash, and a lighter teal for panels
INK, SOFT = (246, 246, 240), (182, 202, 206)
AMBER, GREEN, ROSE = (255, 196, 64), (112, 214, 144), (240, 150, 150)
YELLOW, DARK = (255, 214, 10), (30, 30, 30)
NIGHT_INK, NIGHT_SOFT = (104, 104, 104), (78, 78, 78)
# ------------------------------------------------------------------------------------------------------------------------------


class Mode(enum.Enum):
    PHOTOS = 1
    WEATHER = 2
    NIGHT = 3
    LIFTED = 4
    CALLING = 5
    ONGOING = 6
    ENDED = 7
    INCOMING = 8
    NO_ANSWER = 9


MODE_NAMES = {Mode.PHOTOS: "Family photos", Mode.WEATHER: "Weather / date / events", Mode.NIGHT: "Night clock",
              Mode.LIFTED: "Handset lifted", Mode.CALLING: "Calling", Mode.ONGOING: "Ongoing call",
              Mode.ENDED: "Call ended", Mode.INCOMING: "Incoming call", Mode.NO_ANSWER: "No answer"}


# =================================================================== text helpers ===========================================
_font_paths = {}
_fonts = {}
_texts = {}


def init_fonts():
    _font_paths["bold"] = pygame.font.match_font("dejavusans,liberationsans,freesans,arial", bold=True)     # None -> built-in font
    _font_paths["reg"] = pygame.font.match_font("dejavusans,liberationsans,freesans,arial")


def get_font(kind, size):
    key = (kind, int(size))
    if key not in _fonts:
        _fonts[key] = pygame.font.Font(_font_paths[kind], int(size))
    return _fonts[key]


def text(string, kind, size, color, max_w=None):
    """A rendered line of text (cached).  With max_w the size shrinks until it fits."""
    size = max(10, int(size))
    key = (string, kind, size, color, max_w)
    img = _texts.get(key)
    if img is None:
        img = get_font(kind, size).render(string, True, color)
        while max_w and img.get_width() > max_w and size > 12:
            size -= 2
            img = get_font(kind, size).render(string, True, color)
        if len(_texts) > 400:
            _texts.clear()
        _texts[key] = img
    return img


def wrap(string, kind, size, max_w):
    font, lines, cur = get_font(kind, size), [], ""
    for word in string.split():
        trial = (cur + " " + word).strip()
        if cur and font.size(trial)[0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def block(surf, string, kind, size, color, y, max_w=W - 60, cx=W // 2, spacing=1.15):
    """Centred, word-wrapped text.  Returns the y below it."""
    for line in wrap(string, kind, size, max_w):
        img = text(line, kind, size, color)
        surf.blit(img, (cx - img.get_width() // 2, y))
        y += int(size * spacing)
    return y


def centered(surf, img, y, cx=W // 2):
    surf.blit(img, (cx - img.get_width() // 2, y))
    return y + img.get_height()


def mix(a, b, f):
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def clock_text(dt):
    h = dt.hour % 12 or 12
    return "%d:%02d %s" % (h, dt.minute, "AM" if dt.hour < 12 else "PM")


def long_date(dt):
    return "%s %d, %d" % (dt.strftime("%B"), dt.day, dt.year)


def nice_date(raw):
    """2019-06-14 -> June 14, 2019;  2019-06 -> June 2019;  2019 -> 2019;  anything else as it is."""
    raw = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    try:
        if m:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", raw)
        if m:
            return "%s %d" % (datetime.date(int(m.group(1)), int(m.group(2)), 1).strftime("%B"), int(m.group(1)))
    except ValueError:
        pass
    return raw


def party_label(party):
    name, rel = party
    return "%s (%s)" % (name, rel.lower()) if rel else name


# =================================================================== photos =================================================
META_KEYS = {"people": "people", "names": "people", "name": "people", "who": "people",
             "relationship": "relationship", "relationships": "relationship", "relation": "relationship",
             "taken": "taken", "date": "taken", "when": "taken", "photographed": "taken"}
META_ORDER = ("people", "relationship", "taken")


def find_meta(photo_path):
    for cand in (photo_path.with_suffix(".meta"), photo_path.with_name(photo_path.name + ".meta")):
        if cand.is_file():
            return cand
    return None


def parse_meta(path):
    """-> {'people':..., 'relationship':..., 'taken':...} (only the parts that exist).  See the docstring for the format."""
    fields, loose = {}, []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z ]+?)\s*[:=]\s*(.+)$", line)
        if m and m.group(1).strip().lower() in META_KEYS:
            fields[META_KEYS[m.group(1).strip().lower()]] = m.group(2).strip()
        else:
            loose.append(line)
    for key in META_ORDER:                              # lines without a label fill the gaps in order
        if key not in fields and loose:
            fields[key] = loose.pop(0)
    return fields


def load_image(path):
    """Load a picture, turned the right way up (EXIF) and no bigger than MAX_PHOTO_PX."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
    if Image is not None:
        with Image.open(path) as im:
            im.draft("RGB", (MAX_PHOTO_PX, MAX_PHOTO_PX))              # JPEG: decode at reduced size (fast); other formats ignore this
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
            make = getattr(pygame.image, "frombytes", None) or pygame.image.fromstring
            return make(im.tobytes(), im.size, "RGB")
    img = pygame.image.load(str(path))
    if max(img.get_size()) > MAX_PHOTO_PX:
        f = MAX_PHOTO_PX / float(max(img.get_size()))
        img = pygame.transform.smoothscale(img, (int(img.get_width() * f), int(img.get_height() * f)))
    return img


def compose_photo(img, meta):
    """The finished 600 x 1024 picture: blurred backdrop, the photo fitted whole in the middle, the caption band near the bottom."""
    iw, ih = img.get_size()
    img32 = pygame.Surface((iw, ih), 0, 32)                      # smoothscale only works on 24 / 32 bit surfaces
    img32.blit(img, (0, 0))
    img = img32
    back = pygame.transform.smoothscale(pygame.transform.smoothscale(img, (W // 24, H // 24)), (W, H))
    shade = pygame.Surface((W, H))
    shade.set_alpha(120)
    back.blit(shade, (0, 0))
    fit = min(W / float(iw), H / float(ih))
    fw, fh = max(1, int(iw * fit)), max(1, int(ih * fit))
    back.blit(pygame.transform.smoothscale(img, (fw, fh)), ((W - fw) // 2, (H - fh) // 2))
    lines = []                                           # caption: (kind, size, color, string)
    if meta.get("people"):
        lines += [("bold", 54, INK, s) for s in wrap(meta["people"], "bold", 54, W - 70)]
    if meta.get("relationship"):
        lines += [("reg", 38, INK, s) for s in wrap(meta["relationship"], "reg", 38, W - 70)]
    if meta.get("taken"):
        lines += [("reg", 34, SOFT, "Taken " + nice_date(meta["taken"]))]
    if lines:
        height = sum(int(size * 1.18) for _, size, _, _ in lines) + 36
        band = pygame.Surface((W, height), pygame.SRCALPHA)
        band.fill((0, 0, 0, 170))
        y = H - 36 - height
        back.blit(band, (0, y))
        y += 18
        for kind, size, color, string in lines:
            centered(back, text(string, kind, size, color), y)
            y += int(size * 1.18)
    return back.convert()


class Photo:
    def __init__(self, path, surface, meta):
        self.path, self.surface, self.meta = path, surface, meta


class PhotoLibrary:
    """The photo folder: shuffled deck, loaded one picture at a time."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.deck = []
        self.cache = {}
        self.last = None

    def scan(self):
        try:
            return sorted(p for p in self.folder.iterdir() if p.suffix.lower() in PHOTO_EXTS and p.is_file())
        except OSError:
            return []

    def next(self):
        """The next Photo, or None if the folder has no usable picture."""
        for _ in range(12):                              # skip pictures that cannot be read
            if not self.deck:
                self.deck = self.scan()
                random.shuffle(self.deck)
                if not self.deck:
                    return None
                if len(self.deck) > 1 and self.deck[-1] == self.last:       # a new round must not start with the picture just shown
                    self.deck[0], self.deck[-1] = self.deck[-1], self.deck[0]
            path = self.deck.pop()
            if not path.is_file():
                continue
            try:
                if path not in self.cache:
                    meta_path = find_meta(path)
                    meta = parse_meta(meta_path) if meta_path else {}
                    if len(self.cache) >= 3:
                        self.cache.pop(next(iter(self.cache)))
                    self.cache[path] = Photo(path, compose_photo(load_image(path), meta), meta)
                self.last = path
                return self.cache[path]
            except Exception as exc:                     # noqa: BLE001 - one bad file must not stop the show
                print("  (skipping %s: %s)" % (path.name, exc), file=sys.stderr)
        return None


# ------------------------------------------------------------------ demo pictures ---------------------------------------------
PALETTES = [((120, 180, 235), (250, 235, 190), (92, 150, 82)), ((250, 170, 120), (255, 225, 140), (70, 120, 90)),
            ((150, 140, 215), (250, 200, 170), (60, 100, 110)), ((110, 200, 220), (255, 245, 200), (110, 160, 80))]
SAMPLES = [  # (file name, size, people in the picture, palette, meta text or None)
    ("clark_and_amy_lake", (1600, 1200), 2, 0, "people: Clark and Amy\nrelationship: Your husband and your daughter\ntaken: 2019-06-14"),
    ("sydney_birthday", (1200, 1600), 1, 1, "people: Sydney\nrelationship: Your granddaughter\ntaken: 2023-03-18"),
    ("family_dinner", (1600, 1200), 3, 2, "people: Clark, Amy and Sydney\nrelationship: Your husband, your daughter and your granddaughter\n"
                                          "taken: 2021-12-25"),
    ("amy_on_the_porch", (1200, 1200), 1, 3, "people: Amy\nrelationship: Your daughter\ntaken: 2012-08"),
    ("clark_in_the_garden", (1600, 1200), 1, 1, "people: Clark\nrelationship: Your husband\ntaken: 2016"),
    ("no_caption_file", (1600, 1200), 2, 0, None),
]


def sample_scene(size, people, palette):
    w, h = size
    sky, sun, hill = PALETTES[palette % len(PALETTES)]
    s = pygame.Surface(size)
    for y in range(h):
        pygame.draw.line(s, mix(sky, (255, 255, 255), 0.5 * y / h), (0, y), (w, y))
    pygame.draw.circle(s, sun, (int(w * 0.78), int(h * 0.2)), int(min(w, h) * 0.09))
    pygame.draw.ellipse(s, mix(hill, (0, 0, 0), 0.15), (-w * 0.3, h * 0.6, w * 1.0, h * 0.8))
    pygame.draw.ellipse(s, hill, (w * 0.25, h * 0.68, w * 1.0, h * 0.8))
    for i in range(people):
        x = int(w * (0.5 + (i - (people - 1) / 2.0) * 0.22))
        top = int(h * 0.52)
        c = [(200, 90, 90), (80, 120, 200), (230, 190, 70)][i % 3]
        pygame.draw.rect(s, c, (x - int(w * 0.05), top + int(h * 0.1), int(w * 0.1), int(h * 0.3)), border_radius=int(w * 0.03))
        pygame.draw.circle(s, (240, 205, 170), (x, top + int(h * 0.06)), int(min(w, h) * 0.06))
    s.blit(text("DEMO PHOTO", "bold", int(h * 0.04), (255, 255, 255)), (int(w * 0.03), int(h * 0.02)))
    return s


def write_samples(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, size, people, palette, meta in SAMPLES:
        pygame.image.save(sample_scene(size, people, palette), str(folder / (name + ".jpg")))
        if meta:
            (folder / (name + ".meta")).write_text(meta + "\n", encoding="utf-8")
    return folder


# =================================================================== sound ==================================================
def find_usb_card(proc_dir="/proc/asound"):
    """The ALSA card id of the first USB sound card that has a playback device (the handset speaker), or None."""
    try:
        with open(os.path.join(proc_dir, "cards")) as fh:
            listing = fh.read()
    except OSError:
        return None
    for m in re.finditer(r"^\s*(\d+) \[([^\]]*?)\s*\]:\s*(\S+)\s+-\s+(.*)$", listing, flags=re.MULTILINE):
        if m.group(3).lower().replace("_", "-") == "usb-audio" and os.path.exists(os.path.join(proc_dir, "card" + m.group(1), "pcm0p")):
            return m.group(2).strip()
    return None


class NoAudio:
    """Stands in when there is no handset sound device (or --no-sound)."""

    def dial_tone(self, on):
        pass

    def close(self):
        pass


class DialTone:
    """The dial tone on the handset speaker: aplay, fed with one second of 350 + 440 Hz over and over (a whole number of cycles of both
    tones, so the loop is seamless).  The real app must stop this - and let aplay release the card - before the phone software opens
    the same card for a call."""

    def __init__(self, card_id, log):
        self.device = "plughw:CARD=%s,DEV=0" % card_id
        self.log = log
        n = AUDIO_RATE
        pcm = array.array("h", [int(32767 * DIAL_TONE_LEVEL * sum(math.sin(2 * math.pi * f * i / n) for f in DIAL_TONE_HZ)) for i in range(n)])
        if sys.byteorder != "little":
            pcm.byteswap()
        self.pcm = pcm.tobytes()
        self._proc = self._thread = self._stop = self._err = None

    def dial_tone(self, on):
        if on:
            if self._proc is not None and self._proc.poll() is not None:
                self._stop_now()                                   # the last aplay died by itself: clean up, try again
            if self._proc is None:
                self._start()
        elif self._proc is not None:
            self._stop_now()

    def _start(self):
        cmd = ["aplay", "-q", "-D", self.device, "-t", "raw", "-f", "S16_LE", "-r", str(AUDIO_RATE), "-c", "1",
               "--buffer-time=200000", "--period-time=50000", "-"]
        err = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err, bufsize=0)
        except FileNotFoundError:
            err.close()
            self.log("      (no dial tone: aplay is not installed - sudo apt install alsa-utils)")
            return
        stop = threading.Event()

        def feed():
            try:
                proc.stdin.write(bytes(int(0.3 * AUDIO_RATE) * 2))        # a moment of silence first: USB adapters swallow the very start
                while not stop.is_set():
                    for off in range(0, len(self.pcm), 3200):             # 0.1 s pieces (under the 4096-byte pipe limit: never a short write)
                        if stop.is_set():
                            return
                        proc.stdin.write(self.pcm[off:off + 3200])
            except (BrokenPipeError, OSError):
                if not stop.is_set():
                    try:
                        err.seek(0)
                        why = err.read().decode(errors="replace").strip().splitlines()
                    except (OSError, ValueError):
                        why = []
                    self.log("      (dial tone stopped: %s)" % (why[-1] if why else "aplay ended"))
        thread = threading.Thread(target=feed, daemon=True)
        thread.start()
        self._proc, self._thread, self._stop, self._err = proc, thread, stop, err

    def _stop_now(self):
        self._stop.set()
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._thread.join(timeout=2)
        self._err.close()
        self._proc = self._thread = self._stop = self._err = None

    def close(self):
        self.dial_tone(False)


# =================================================================== the machine ============================================
class Machine:
    """Which screen is showing, and the timed changes (photos -> weather -> photos, call ended -> photos, night clock).
    Forced mode changes come in through set_mode() / handle(); the real triggers (switches, SIP, network check) will call the same."""

    def __init__(self, library, speed, night_schedule, clock_offset, log, audio=None):
        self.library, self.speed, self.night_schedule, self.offset, self.log = library, speed, night_schedule, clock_offset, log
        self.audio = audio or NoAudio()
        self._tone_on = False
        self.network_ok = True
        self.help = False
        self.party = CONTACTS["amy"]
        self.caller_i = 0
        self.mode = None
        self.mode_since = 0.0
        self.current = self.prev = None
        self.photo_since = 0.0
        self.shown = 0
        self._was_night = self.in_night() if night_schedule else None
        self.set_mode(self.home_mode(), time.monotonic())               # at start-up: the night clock if it is night and the schedule is on

    def now(self):
        return datetime.datetime.now() + self.offset

    def in_night(self):
        t = self.now().time()
        return t >= NIGHT_FROM or t < NIGHT_TO

    def home_mode(self):
        return Mode.NIGHT if (self.night_schedule and self.in_night()) else Mode.PHOTOS

    def set_mode(self, mode, t):
        self.mode, self.mode_since = mode, t
        detail = ""
        if mode in (Mode.CALLING, Mode.ONGOING, Mode.ENDED, Mode.INCOMING, Mode.NO_ANSWER):
            detail = " - " + party_label(self.party)
        self.log("%d  %s%s" % (mode.value, MODE_NAMES[mode], detail))
        if mode == Mode.PHOTOS:
            self.shown = 0
            self._next_photo(t)
            self.prev = None                                       # no cross-fade from a picture that is not on the screen
        self._sync_audio(t)

    def _sync_audio(self, t):
        """The dial tone plays while the 'handset lifted' screen is up (and for at most DIAL_TONE_SECONDS)."""
        want = self.mode == Mode.LIFTED and (t - self.mode_since) < DIAL_TONE_SECONDS / self.speed
        if want != self._tone_on:
            self._tone_on = want
            self.audio.dial_tone(want)
            self.log("      dial tone " + ("on" if want else "off"))

    def _next_photo(self, t):
        self.prev = self.current
        self.current = self.library.next()
        self.photo_since = t
        self.shown += 1
        self.log("      photo %d of %d: %s" % (self.shown, PHOTOS_PER_ROUND, self.current.path.name if self.current else "(no photos found)"))

    def handle(self, key, t):
        """Returns False to quit."""
        if key == "quit":
            return False
        if key in "123456789" and len(key) == 1:
            mode = Mode(int(key))
            if mode in (Mode.CALLING, Mode.NO_ANSWER) and self.party not in CONTACTS.values():
                self.party = CONTACTS["amy"]                       # Judi can only call Clark or Amy
            if mode == Mode.INCOMING:
                if self.mode == Mode.INCOMING:
                    self.caller_i += 1
                _, name, rel = DEMO_CALLERS[self.caller_i % len(DEMO_CALLERS)]
                self.party = (name, rel) if name else (DEMO_CALLERS[self.caller_i % len(DEMO_CALLERS)][0], None)
            self.set_mode(mode, t)
        elif key in ("a", "c"):
            self.party = CONTACTS["amy" if key == "a" else "clark"]
            if self.mode == Mode.LIFTED:
                self.set_mode(Mode.CALLING, t)                      # same as pressing that button
            else:
                self.log("other party: " + party_label(self.party))
        elif key == "next":
            if self.mode == Mode.PHOTOS:
                self.photo_since = t - PHOTO_SECONDS / self.speed
        elif key == "net":
            self.network_ok = not self.network_ok
            self.log("network " + ("OK" if self.network_ok else "PROBLEM - warning shown"))
        elif key == "help":
            self.help = not self.help
        return True

    def tick(self, t):
        mode = self.mode
        if mode == Mode.PHOTOS and t - self.photo_since >= PHOTO_SECONDS / self.speed:
            if self.shown >= PHOTOS_PER_ROUND:
                self.set_mode(Mode.WEATHER, t)
            else:
                self._next_photo(t)
        elif mode == Mode.WEATHER and t - self.mode_since >= WEATHER_SECONDS / self.speed:
            self.set_mode(Mode.PHOTOS, t)
        elif mode == Mode.ENDED and t - self.mode_since >= CALL_ENDED_SECONDS / self.speed:
            self.set_mode(self.home_mode(), t)
        elif mode == Mode.NO_ANSWER and t - self.mode_since >= NO_ANSWER_SECONDS / self.speed:
            self.set_mode(Mode.LIFTED, t)                          # the handset is still lifted: back to the arrows (and the dial tone)
        self._sync_audio(t)
        if self.night_schedule:                                  # only the moments 21:00 and 06:00 count, so forced modes stay put
            night = self.in_night()
            if night != self._was_night:
                self._was_night = night
                if night and self.mode in (Mode.PHOTOS, Mode.WEATHER):
                    self.set_mode(Mode.NIGHT, t)
                elif not night and self.mode == Mode.NIGHT:
                    self.set_mode(Mode.PHOTOS, t)

    def animated(self, t):
        if self.mode in (Mode.LIFTED, Mode.CALLING, Mode.ONGOING, Mode.INCOMING):
            return True
        return self.mode == Mode.PHOTOS and self.prev is not None and self.current is not None and t - self.photo_since < FADE_SECONDS

    def signature(self):
        now = self.now()
        return (self.mode, self.party, self.caller_i, id(self.current), self.network_ok, self.help, now.hour, now.minute,
                now.day if self.mode in (Mode.WEATHER, Mode.NIGHT) else 0)


# =================================================================== drawing ================================================
_handset_body = None


def handset_body():
    """The black handset on a transparent surface (drawn once)."""
    global _handset_body
    if _handset_body is None:
        s = pygame.Surface((520, 230), pygame.SRCALPHA)
        black, shine = (22, 22, 26), (84, 86, 96)
        cx, cy = 260, 94                                  # the handset spans cy-45 .. cy+87, so its middle is the surface middle (115)
        left, right, ctrl = (cx - 175, cy - 5), (cx + 175, cy - 5), (cx, cy + 135)

        def bez(t):
            return ((1 - t) ** 2 * left[0] + 2 * (1 - t) * t * ctrl[0] + t * t * right[0],
                    (1 - t) ** 2 * left[1] + 2 * (1 - t) * t * ctrl[1] + t * t * right[1])
        for i in range(161):
            x, y = bez(i / 160.0)
            pygame.draw.circle(s, black, (int(x), int(y)), 22)
        for i in range(16, 145):
            x, y = bez(i / 160.0)
            pygame.draw.circle(s, shine, (int(x), int(y) - 10), 3)
        for (x, y) in (left, right):
            cup = pygame.Rect(x - 62, y - 40, 124, 80)
            pygame.draw.rect(s, black, cup, border_radius=28)
            pygame.draw.rect(s, shine, cup, 3, border_radius=28)
            for dx in (-30, -10, 10, 30):
                for dy in (-14, 6):
                    pygame.draw.circle(s, shine, (x + dx, y + dy), 4)
        _handset_body = s
    return _handset_body


def draw_handset(surf, cx, cy, waves=0.0, angle=0.0):
    """The handset centred at (cx, cy).  waves 0..1 draws sound arcs round the two cups; angle (degrees) tilts it."""
    body = handset_body()
    if abs(angle) > 0.01:
        body = pygame.transform.rotate(body, angle)
    surf.blit(body, (cx - body.get_width() // 2, cy - body.get_height() // 2))
    if waves > 0 and abs(angle) <= 0.01:
        for k, threshold in enumerate((0.15, 0.4, 0.65)):
            if waves >= threshold:
                r = 66 + k * 20
                for (x, colour) in ((cx - 175, (40, 150, 80)), (cx + 175, (40, 100, 200))):
                    pygame.draw.arc(surf, colour, pygame.Rect(x - r, cy - 26 - r, 2 * r, 2 * r), math.radians(60), math.radians(120), 7)


def draw_weather_icon(surf, kind, cx, cy, r):
    sun, cloud = (255, 205, 60), (236, 240, 244)

    def sun_at(x, y, rad):
        for i in range(8):
            a = i * math.pi / 4
            pygame.draw.line(surf, sun, (x + math.cos(a) * rad * 1.35, y + math.sin(a) * rad * 1.35),
                             (x + math.cos(a) * rad * 1.8, y + math.sin(a) * rad * 1.8), max(3, int(rad * 0.16)))
        pygame.draw.circle(surf, sun, (int(x), int(y)), int(rad))

    def cloud_at(x, y, s):
        for dx, dy, rad in ((-0.55, 0.1, 0.45), (-0.05, -0.2, 0.6), (0.5, 0.1, 0.45)):
            pygame.draw.circle(surf, cloud, (int(x + dx * s), int(y + dy * s)), int(rad * s))
        pygame.draw.rect(surf, cloud, (int(x - 0.55 * s), int(y + 0.1 * s), int(1.05 * s), int(0.45 * s)))
    if kind == "sun":
        sun_at(cx, cy, r * 0.6)
    elif kind == "cloud":
        cloud_at(cx, cy, r)
    elif kind == "rain":
        cloud_at(cx, cy - r * 0.2, r)
        for dx in (-0.5, 0.0, 0.5):
            pygame.draw.line(surf, (110, 170, 240), (cx + dx * r, cy + r * 0.65), (cx + dx * r - r * 0.12, cy + r * 0.95), max(3, int(r * 0.07)))
    else:                                                            # partly cloudy
        sun_at(cx - r * 0.3, cy - r * 0.3, r * 0.4)
        cloud_at(cx + r * 0.1, cy + r * 0.2, r * 0.9)


def draw_banner(surf):
    """The yellow network warning across the top.  Returns its height."""
    icon, pad = 64, 16
    lines = wrap(BANNER_TEXT, "bold", 33, W - icon - 3 * pad)
    height = max(icon, int(33 * 1.18) * len(lines)) + 2 * pad
    pygame.draw.rect(surf, YELLOW, (0, 0, W, height))
    pygame.draw.line(surf, DARK, (0, height - 1), (W, height - 1), 3)
    x0, y0 = pad, (height - icon) // 2
    pygame.draw.polygon(surf, DARK, [(x0 + icon // 2, y0), (x0 + icon, y0 + icon - 4), (x0, y0 + icon - 4)])
    img = text("!", "bold", 44, YELLOW)
    surf.blit(img, (x0 + icon // 2 - img.get_width() // 2, y0 + icon // 2 - 12))
    y = (height - int(33 * 1.18) * len(lines)) // 2
    for line in lines:
        surf.blit(text(line, "bold", 33, DARK), (x0 + icon + pad, y))
        y += int(33 * 1.18)
    return height


_banner_h = None


def banner_height():
    global _banner_h
    if _banner_h is None:
        _banner_h = draw_banner(pygame.Surface((W, 300)))
    return _banner_h


def draw_photos(surf, m, t, top):
    cur = m.current
    if cur is None:
        surf.fill(BG)
        y = block(surf, "No photos yet", "bold", 64, INK, H // 2 - 80)
        block(surf, "Looking in " + str(m.library.folder), "reg", 30, SOFT, y + 10, W - 80)
        return
    if m.prev is not None and t - m.photo_since < FADE_SECONDS:
        surf.blit(m.prev.surface, (0, 0))
        cur.surface.set_alpha(int(255 * (t - m.photo_since) / FADE_SECONDS))
        surf.blit(cur.surface, (0, 0))
        cur.surface.set_alpha(255)
    else:
        surf.blit(cur.surface, (0, 0))


def draw_weather(surf, m, t, top):
    surf.fill(BG)
    s = min(1.0, (H - top) / float(H))                               # everything shrinks a little when the banner takes the top
    now = m.now()
    y = top + int(34 * s)
    y = centered(surf, text(now.strftime("%A"), "bold", 96 * s, INK, W - 40), y)
    y = centered(surf, text(long_date(now), "reg", 48 * s, SOFT, W - 40), y + int(2 * s))
    y = centered(surf, text(clock_text(now), "bold", 62 * s, AMBER, W - 40), y + int(10 * s))
    # weather card
    card = pygame.Rect(24, y + int(22 * s), W - 48, int(240 * s))
    pygame.draw.rect(surf, CARD, card, border_radius=int(30 * s))
    wx = DEMO_WEATHER
    draw_weather_icon(surf, wx["icon"], card.x + int(135 * s), card.centery, 82 * s)
    tx = card.x + int(268 * s)
    surf.blit(text("%d°" % wx["temp"], "bold", 118 * s, INK), (tx, card.y + int(10 * s)))
    surf.blit(text(wx["text"], "reg", 38 * s, INK, card.right - tx - 14), (tx, card.y + int(142 * s)))
    surf.blit(text("High %d°   Low %d°" % (wx["high"], wx["low"]), "reg", 33 * s, SOFT, card.right - tx - 14),
              (tx, card.y + int(188 * s)))
    # upcoming events card
    ev = pygame.Rect(24, card.bottom + int(22 * s), W - 48, H - int(22 * s) - (card.bottom + int(22 * s)))
    pygame.draw.rect(surf, CARD, ev, border_radius=int(30 * s))
    yy = ev.y + int(18 * s)
    yy = centered(surf, text("Coming up", "bold", 40 * s, AMBER), yy) + int(6 * s)
    row_h = (ev.bottom - yy - int(14 * s)) / float(len(DEMO_EVENTS))
    for i, (when, title) in enumerate(DEMO_EVENTS):
        y1 = yy + int(i * row_h + (row_h - 90 * s) / 2)                  # each event centred in its share of the card
        surf.blit(text(when, "reg", 32 * s, SOFT, ev.width - 60), (ev.x + 30, y1))
        surf.blit(text(title, "bold", 44 * s, INK, ev.width - 60), (ev.x + 30, y1 + int(38 * s)))


def draw_night(surf, m, t, top):
    surf.fill((0, 0, 0))
    now = m.now()
    big = text(clock_text(now), "bold", 150, NIGHT_INK, W - 60)
    small = text("%s, %s %d" % (now.strftime("%A"), now.strftime("%B"), now.day), "reg", 46, NIGHT_SOFT, W - 60)
    total = big.get_height() + 10 + small.get_height()
    y = top + (H - top - total) // 2
    y = centered(surf, big, y) + 10
    centered(surf, small, y)


def draw_lifted(surf, m, t, top):
    surf.fill(BG)
    lines = wrap("Who would you like to call?", "bold", 72, W - 40)
    total = int(72 * 1.15) * len(lines)
    y = top + (H - top - total) // 2 - 40                            # the middle of the screen (a little high, the arrows are below)
    for line in lines:
        centered(surf, text(line, "bold", 72, INK), y)
        y += int(72 * 1.15)
    nudge = int(12 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.1)))     # the arrows bob toward the buttons
    tip = H - 28 - 12 + nudge
    for key, (name, rel) in CONTACTS.items():
        cx = BUTTON_CX[key]
        pygame.draw.polygon(surf, AMBER, [(cx - 22, tip - 150), (cx + 22, tip - 150), (cx + 22, tip - 70), (cx + 62, tip - 70), (cx, tip),
                                          (cx - 62, tip - 70), (cx - 22, tip - 70)])
        ny = tip - 150 - 16 - 62 - 44
        centered(surf, text(name, "bold", 62, INK, 255), ny, cx)
        centered(surf, text("(%s)" % rel, "reg", 40, SOFT, 255), ny + 66, cx)


_call_text = {}


def call_text(m):
    """The words under the handset picture, as a transparent surface (cached)."""
    mode = m.mode
    key = (mode, party_label(m.party), m.caller_i)
    img = _call_text.get(key)
    if img is None:
        tmp = pygame.Surface((W, 520), pygame.SRCALPHA)
        label = party_label(m.party)
        if mode == Mode.CALLING:
            y = block(tmp, "Calling %s..." % label, "bold", 66, INK, 0)
        elif mode == Mode.ONGOING:
            y = block(tmp, "Ongoing call with %s..." % label, "bold", 66, INK, 0)
        elif mode == Mode.ENDED:
            y = block(tmp, "Call ended with %s..." % label, "bold", 66, SOFT, 0)
        elif mode == Mode.NO_ANSWER:
            y = block(tmp, "No answer.", "bold", 84, INK, 0)
            y = block(tmp, label, "reg", 46, SOFT, y + 4)
        else:
            number, name, rel = DEMO_CALLERS[m.caller_i % len(DEMO_CALLERS)]
            y = centered(tmp, text("Incoming call from", "reg", 44, SOFT), 0)
            if name:
                y = centered(tmp, text(name, "bold", 92, INK, W - 60), y + 2)
                y = centered(tmp, text(rel, "reg", 52, AMBER), y)
                y = centered(tmp, text(number, "reg", 44, SOFT), y + 14)
            else:
                y = centered(tmp, text(number, "bold", 70, INK, W - 60), y + 6)
        img = tmp.subsurface((0, 0, W, y)).copy()
        _call_text.clear()
        _call_text[key] = img
    return img


def draw_call(surf, m, t, top):
    surf.fill(BG)
    mode = m.mode
    accent = {Mode.CALLING: AMBER, Mode.ONGOING: GREEN, Mode.ENDED: ROSE, Mode.INCOMING: AMBER, Mode.NO_ANSWER: ROSE}[mode]
    words = call_text(m)
    group = 290 + 56 + words.get_height()                            # handset panel + gap + words, centred as one block
    y0 = top + max(24, (H - top - group) // 2 - 30)
    panel = pygame.Rect(40, y0, W - 80, 290)
    if mode in (Mode.CALLING, Mode.INCOMING):                        # rings spreading out from the panel
        for k in range(3):
            phase = (t * 0.7 + k / 3.0) % 1.0
            grow = int(phase * 46)
            pygame.draw.rect(surf, mix(accent, BG, phase), panel.inflate(2 * grow, 2 * grow), 5, border_radius=34 + grow)
    pygame.draw.rect(surf, (232, 235, 238), panel, border_radius=34)
    if mode == Mode.ONGOING:
        pygame.draw.rect(surf, accent, panel, 8, border_radius=34)
        draw_handset(surf, panel.centerx, panel.centery, waves=0.5 + 0.5 * math.sin(t * 3.2))
    elif mode == Mode.INCOMING:
        shaking = (t % 2.0) < 1.2
        draw_handset(surf, panel.centerx, panel.centery, angle=9 * math.sin(t * 2 * math.pi * 6) if shaking else 0.0)
    else:
        draw_handset(surf, panel.centerx, panel.centery)
    surf.blit(words, (0, panel.bottom + 56))
    if mode == Mode.INCOMING:
        centered(surf, text("Pick up the handset to answer", "reg", 36, SOFT, W - 60), H - 90)


def draw_help(surf):
    veil = pygame.Surface((W, H), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 238))
    surf.blit(veil, (0, 0))
    rows = [("1", "Family photos"), ("2", "Weather / date / events"), ("3", "Night clock"), ("4", "Handset lifted"),
            ("5", "Calling"), ("6", "Ongoing call"), ("7", "Call ended"), ("8", "Incoming call (again: next caller)"),
            ("9", "No answer"), ("a / c", "Amy / Clark (on 4: the button)"), ("space", "next photo"), ("n", "network problem on / off"),
            ("h", "this help"), ("q / Esc", "quit")]
    y = 110
    y = centered(surf, text("Keys", "bold", 56, AMBER), y) + 20
    for key, what in rows:
        surf.blit(text(key, "bold", 32, AMBER), (40, y))
        surf.blit(text(what, "reg", 30, INK, W - 190), (170, y + 2))
        y += 48


DRAWERS = {Mode.PHOTOS: draw_photos, Mode.WEATHER: draw_weather, Mode.NIGHT: draw_night, Mode.LIFTED: draw_lifted,
           Mode.CALLING: draw_call, Mode.ONGOING: draw_call, Mode.ENDED: draw_call, Mode.INCOMING: draw_call,
           Mode.NO_ANSWER: draw_call}


def render(surf, m, t):
    """Draw the whole upright 600 x 1024 picture for the machine's current state."""
    top = banner_height() if not m.network_ok else 0
    DRAWERS[m.mode](surf, m, t, top)
    if not m.network_ok:
        draw_banner(surf)
    if m.help:
        draw_help(surf)


# =================================================================== keyboard ===============================================
def parse_keys(data):
    """Raw bytes from the terminal -> command names: '1'..'9', 'a', 'c', 'next', 'net', 'help', 'quit'."""
    keys, i = [], 0
    while i < len(data):
        rest = data[i:]
        if rest.startswith(b"\x1b[C") or rest.startswith(b"\x1bOC"):
            keys.append("next")
            i += 3
            continue
        if rest.startswith(b"\x1b[") or rest.startswith(b"\x1bO"):      # some other cursor / function key: ignore the whole sequence
            j = 2
            while j < len(rest) and not (0x40 <= rest[j] <= 0x7e):
                j += 1
            i += j + 1
            continue
        ch = chr(rest[0]).lower()
        if rest[0] == 0x1b and len(rest) == 1:
            keys.append("quit")
        elif ch in "123456789":
            keys.append(ch)
        elif ch in "ac":
            keys.append(ch)
        elif ch == " ":
            keys.append("next")
        elif ch == "n":
            keys.append("net")
        elif ch in "h?":
            keys.append("help")
        elif ch == "q":
            keys.append("quit")
        i += 1
    return keys


class TerminalKeys:
    """Single key presses from the terminal the program was started in (works over SSH)."""

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        self.dead = False

    def poll(self):
        keys = []
        while not self.dead and select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 64)
            if not data:
                self.dead = True
                break
            keys += parse_keys(data)
        return keys

    def close(self):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


def window_keys(events):
    keys = []
    for ev in events:
        if ev.type == pygame.QUIT:
            keys.append("quit")
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                keys.append("quit")
            elif ev.key in (pygame.K_RIGHT, pygame.K_SPACE):
                keys.append("next")
            else:
                keys += parse_keys((ev.unicode or "").encode("ascii", "ignore"))
    return keys


# =================================================================== main ===================================================
def present(screen, logical, rotate, flip):
    out = pygame.transform.rotate(logical, -90 if flip else 90) if rotate else logical     # pygame turns counter-clockwise for positive angles
    if out.get_size() != screen.get_size():
        out = pygame.transform.smoothscale(out, screen.get_size())
    screen.blit(out, (0, 0))
    pygame.display.flip()


def parse_clock(text_in):
    try:
        parts = [int(p) for p in text_in.split(":")]
        target = datetime.datetime.combine(datetime.date.today(), datetime.time(*parts))
    except (ValueError, TypeError):
        sys.exit("--time must look like 20:59 or 20:59:30")
    return target - datetime.datetime.now()


def snapshots(folder, library, offset):
    """One PNG per screen (upright), with and without the network warning."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    m = Machine(library, 1.0, False, offset, lambda msg: None)
    surf = pygame.Surface((W, H))
    t0 = time.monotonic()

    def save(name, tt):
        render(surf, m, tt)
        pygame.image.save(surf, str(folder / name))
    for net_ok in (True, False):
        m.network_ok = net_ok
        for mode in Mode:
            m.caller_i, m.party = 0, CONTACTS["amy"]
            m.handle(str(mode.value), t0)
            save("%d_%s%s.png" % (mode.value, mode.name.lower(), "" if net_ok else "_network"), t0 + (100.0 if mode == Mode.PHOTOS else 0.35))
        if net_ok:
            m.handle("8", t0)                                          # already on screen 8: the next sample caller (no name)
            save("8_incoming_unknown_number.png", t0 + 0.35)
            m.handle("help", t0)
            save("help.png", t0)
            m.handle("help", t0)
    return folder


def main():
    ap = argparse.ArgumentParser(description="Judicom screen mock-up (keys 1-9 force the modes; h = help)")
    ap.add_argument("--photos", help="photo folder (default ~/photos, or built-in demo pictures if that is missing)")
    ap.add_argument("--write-samples", metavar="DIR", help="write a sample photo set with .meta files into DIR and exit")
    ap.add_argument("--snapshots", metavar="DIR", help="save a PNG of every screen into DIR and exit")
    ap.add_argument("--speed", type=float, default=1.0, help="run the timers this many times faster (default 1)")
    ap.add_argument("--time", help="pretend the clock starts at HH:MM[:SS]")
    ap.add_argument("--night-schedule", action="store_true", help="go to the night clock at 21:00 and back to the photos at 06:00")
    ap.add_argument("--no-sound", action="store_true", help="no dial tone on the handset speaker")
    ap.add_argument("--window", action="store_true", help="small window instead of full screen (for a PC), no rotation")
    ap.add_argument("--no-rotate", action="store_true", help="do not turn the picture 90 degrees (normal portrait monitor)")
    ap.add_argument("--flip", action="store_true", help="turn it the other way (use if the picture is upside-down)")
    args = ap.parse_args()
    if args.speed <= 0:
        sys.exit("--speed must be above zero")
    offset = parse_clock(args.time) if args.time else (parse_clock("14:07") if args.snapshots else datetime.timedelta(0))

    headless = bool(args.write_samples or args.snapshots)
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    elif "SDL_VIDEODRIVER" not in os.environ and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"                       # on the Judicom: straight to the screen, no desktop
    try:
        pygame.display.init()                                          # video and fonts only: no audio device is opened
        pygame.font.init()
        if headless:
            screen = pygame.display.set_mode((W, H))
        elif args.window:
            screen = pygame.display.set_mode((450, 768))
        else:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        if not headless:
            pygame.mouse.set_visible(False)
    except pygame.error as exc:
        sys.exit("Cannot open the display: %s\n(Over SSH on the Judicom the user needs to be in the 'video' and 'render' groups, "
                 "and python3-pygame must be the apt package, not the pip one.)" % exc)
    init_fonts()

    if args.write_samples:
        print("Wrote %d sample pictures (%d with .meta files) to %s" % (len(SAMPLES), sum(1 for s in SAMPLES if s[4]),
                                                                        write_samples(args.write_samples)))
        return

    temp_dir = None
    folder = Path(args.photos).expanduser() if args.photos else PHOTO_DIR
    if args.photos and not folder.is_dir():
        sys.exit("Photo folder %s does not exist." % folder)
    if not folder.is_dir() or not any(p.suffix.lower() in PHOTO_EXTS for p in folder.iterdir()):
        if args.photos:
            print("Note: %s has no pictures." % folder)
        else:
            temp_dir = tempfile.mkdtemp(prefix="judicom_demo_photos_")
            folder = write_samples(temp_dir)
            print("No pictures in %s - showing the built-in demo pictures." % PHOTO_DIR)
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Note: python3-pil is not installed, so phone photos may come out sideways (sudo apt install python3-pil).")

    library = PhotoLibrary(folder)
    if args.snapshots:
        snapshots(args.snapshots, library, offset)
        print("Saved the screens to", args.snapshots)
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return

    nw, nh = screen.get_size()
    rotate = (nw > nh) and not args.no_rotate and not args.window
    logical = pygame.Surface((W, H))
    start = time.monotonic()
    log = lambda msg: print("[%6.1f s] %s" % (time.monotonic() - start, msg))      # noqa: E731
    card = None if args.no_sound else find_usb_card()
    audio = DialTone(card, log) if card else NoAudio()
    m = Machine(library, args.speed, args.night_schedule, offset, log, audio)
    print(__doc__.split("THE NINE MODES")[0].strip().splitlines()[0])
    print("Screen %dx%d, drawing %dx%d%s.  Folder: %s.  Night schedule %s.  Press h for the key list, q to quit.\n"
          % (nw, nh, W, H, ", turned 90 degrees" if rotate else "", folder, "ON" if args.night_schedule else "off"))
    print("Dial tone: " + ("on the handset speaker (sound card '%s')." % card if card else
                           "no USB sound device found (or --no-sound), so it is only mentioned in the terminal."))
    terminal = TerminalKeys() if (termios and sys.stdin.isatty()) else None

    clock = pygame.time.Clock()
    last_sig = None
    running = True
    try:
        while running:
            t = time.monotonic()
            for key in (terminal.poll() if terminal else []) + window_keys(pygame.event.get()):
                if not m.handle(key, t):
                    running = False
            m.tick(t)
            sig = m.signature()
            if m.animated(t) or sig != last_sig:
                render(logical, m, t)
                present(screen, logical, rotate, args.flip)
                last_sig = sig
            clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        audio.close()
        if terminal:
            terminal.close()
        pygame.quit()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
    print("Bye.")


if __name__ == "__main__":
    main()
