#!/usr/bin/env python3
"""
handset_echo_test.py - Judicom handset echo test.

For 30 seconds it listens to the microphone of the USB sound device (the electret mic in the handset) and plays what it hears straight
back into the handset's speaker, which hangs on the same USB sound device.  The screen shows "Handset Echo Test", a picture of a
handset with sound waves, a microphone level meter and a countdown.  Esc or Q stops it early.

If no USB sound device with both a microphone and a speaker is found, it stops with an error (before any window opens).

Run it from an SSH session on the Judicom:       python3 handset_echo_test.py
Needs:   sudo apt install python3-pygame        (arecord and aplay, from alsa-utils, are already on Raspberry Pi OS)

Hold the handset against your ear while you talk.  If the earpiece sits near the mouthpiece (handset lying on the desk) it will
squeal - that is feedback, not a fault.  --gain 0.5 turns the echo down; the speaker volume itself is set with `alsamixer -c Device`.

The screen is mounted sideways, so the picture is drawn upright in 600 x 1024 and turned 90 degrees onto the panel (same as
gpio_test.py).  If it comes out upside-down, add --flip.
Other options:  --seconds N   --card NAME (use this ALSA card instead of finding the USB one)   --window / --no-rotate (for a PC)
"""
import argparse
import array
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

RUN_SECONDS = 30
TITLE = "Handset Echo Test"
RATE = 16000                    # Hz, mono, 16 bit: plenty for a voice (ALSA's "plughw" converts if the device wants something else)
CHUNK_BYTES = 640               # 20 ms of audio per pass through Python
BUFFER_US, PERIOD_US = 80000, 20000     # ALSA buffer / period for both directions: small, so the echo comes back within about 0.15 s


class AudioError(RuntimeError):
    pass


# ------------------------------------------------------------------ finding the USB sound device ------------------------------
def find_usb_card(proc_dir="/proc/asound"):
    """Return (card id, description) of the first USB sound card that has both a capture (mic) and a playback (speaker) device."""
    try:
        with open(os.path.join(proc_dir, "cards")) as fh:
            text = fh.read()
    except OSError as exc:
        raise AudioError("Cannot read the list of sound cards (%s)." % exc)
    cards, usb_without_both = [], []
    for m in re.finditer(r"^\s*(\d+) \[([^\]]*?)\s*\]:\s*(\S+)\s+-\s+(.*)$", text, flags=re.MULTILINE):
        num, card_id, driver, desc = m.group(1), m.group(2).strip(), m.group(3), m.group(4).strip()
        cards.append("%s (%s)" % (card_id, driver))
        if driver.lower().replace("_", "-") != "usb-audio":
            continue
        names = os.listdir(os.path.join(proc_dir, "card" + num)) if os.path.isdir(os.path.join(proc_dir, "card" + num)) else []
        if "pcm0c" in names and "pcm0p" in names:
            return card_id, desc
        usb_without_both.append(card_id)
    if usb_without_both:
        raise AudioError("USB sound card %s was found, but it does not have both a microphone input and a speaker output."
                         % ", ".join(usb_without_both))
    raise AudioError("No USB sound device found.  Sound cards present: %s.  Is the handset's USB audio adapter plugged in?"
                     % (", ".join(cards) or "none"))


# ------------------------------------------------------------------ the echo itself --------------------------------------------
class Echo:
    """arecord -> (Python: level meter + gain) -> aplay, in a background thread."""

    def __init__(self, card_id, gain):
        self.device = "plughw:CARD=%s,DEV=0" % card_id
        self.gain = gain
        self.level = 0.0                    # 0..1, what the microphone hears right now (a dB scale from -60 dB to 0 dB)
        self.error = None
        self._stop = threading.Event()
        self._rec = self._play = self._thread = None
        self._err_files = {}

    def start(self):
        common = ["-q", "-D", self.device, "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
                  "--buffer-time=%d" % BUFFER_US, "--period-time=%d" % PERIOD_US]
        for tool in ("arecord", "aplay"):
            self._err_files[tool] = tempfile.TemporaryFile()
        try:
            self._rec = subprocess.Popen(["arecord"] + common + ["-"], stdout=subprocess.PIPE, stderr=self._err_files["arecord"], bufsize=0)
            self._play = subprocess.Popen(["aplay"] + common + ["-"], stdin=subprocess.PIPE, stderr=self._err_files["aplay"], bufsize=0)
        except FileNotFoundError as exc:
            self.stop()
            raise AudioError("%s is not installed (sudo apt install alsa-utils)." % exc.filename)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _message(self, tool):
        f = self._err_files.get(tool)
        if f is None:
            return ""
        f.seek(0)
        return f.read().decode(errors="replace").strip()

    def _run(self):
        leftover = b""
        try:
            fd = self._rec.stdout.fileno()
            while not self._stop.is_set():
                data = os.read(fd, CHUNK_BYTES)
                if not data:
                    break                                   # arecord has ended: it could not open the device
                data = leftover + data
                n = len(data) // 2 * 2
                data, leftover = data[:n], data[n:]
                if not data:
                    continue
                samples = array.array("h")
                samples.frombytes(data)
                if sys.byteorder != "little":
                    samples.byteswap()
                rms = math.sqrt(sum(s * s for s in samples) / len(samples))
                self.level = max(0.0, min(1.0, (20.0 * math.log10(max(rms, 1.0) / 32768.0) + 60.0) / 60.0))
                if self.gain != 1.0:
                    samples = array.array("h", [max(-32768, min(32767, int(s * self.gain))) for s in samples])
                if sys.byteorder != "little":
                    samples.byteswap()
                self._play.stdin.write(samples.tobytes())
        except (BrokenPipeError, OSError):
            pass
        if not self._stop.is_set():
            why = self._message("arecord") or self._message("aplay") or "the audio stream stopped unexpectedly"
            self.error = why.splitlines()[-1] if why else "the audio stream stopped"

    def stop(self):
        self._stop.set()
        for p in (self._rec, self._play):
            if p is not None and p.poll() is None:
                p.terminate()
        for p in (self._rec, self._play):
            if p is not None:
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
        for f in self._err_files.values():
            f.close()


# ------------------------------------------------------------------ drawing -----------------------------------------------------
def load_fonts(pygame):
    bold = pygame.font.match_font("dejavusans,liberationsans,freesans,arial", bold=True)      # None -> pygame's built-in font
    reg = pygame.font.match_font("dejavusans,liberationsans,freesans,arial")
    return {"bold": bold, "reg": reg}


def text(pygame, fonts, kind, size, string, color, max_width=None):
    size = max(8, int(size))
    surf = pygame.font.Font(fonts[kind], size).render(string, True, color)
    while max_width and surf.get_width() > max_width and size > 10:       # shrink to fit
        size -= 2
        surf = pygame.font.Font(fonts[kind], size).render(string, True, color)
    return surf


def centered(surface, img, y):
    surface.blit(img, ((surface.get_width() - img.get_width()) // 2, y))


def draw_handset(pygame, surf, cx, cy, level):
    """A black telephone handset (cups up, handle curved down) with sound waves around the two cups."""
    black, shine = (22, 22, 26), (84, 86, 96)
    left, right = (cx - 175, cy - 5), (cx + 175, cy - 5)                      # centres of the earpiece and mouthpiece cups
    ctrl = (cx, cy + 135)

    def bez(t):
        return ((1 - t) ** 2 * left[0] + 2 * (1 - t) * t * ctrl[0] + t * t * right[0],
                (1 - t) ** 2 * left[1] + 2 * (1 - t) * t * ctrl[1] + t * t * right[1])
    for i in range(0, 161):                                                   # the handle: a thick curve, stamped with circles
        x, y = bez(i / 160.0)
        pygame.draw.circle(surf, black, (int(x), int(y)), 22)
    for i in range(16, 145):                                                  # a highlight along the handle
        x, y = bez(i / 160.0)
        pygame.draw.circle(surf, shine, (int(x), int(y) - 10), 3)
    for (x, y) in (left, right):                                              # the two cups
        cup = pygame.Rect(x - 62, y - 40, 124, 80)
        pygame.draw.rect(surf, black, cup, border_radius=28)
        pygame.draw.rect(surf, shine, cup, 3, border_radius=28)
        for dx in (-30, -10, 10, 30):                                         # grille holes
            for dy in (-14, 6):
                pygame.draw.circle(surf, shine, (x + dx, y + dy), 4)
    # sound waves around the cups: more arcs the louder the microphone hears
    for k, threshold in enumerate((0.20, 0.45, 0.70)):
        if level >= threshold:
            r = 66 + k * 20
            for (x, y), colour in ((left, (40, 170, 90)), (right, (50, 110, 220))):
                pygame.draw.arc(surf, colour, pygame.Rect(x - r, y - r, 2 * r, 2 * r), math.radians(60), math.radians(120), 7)


def draw(pygame, surface, fonts, remaining, level, card_text, error):
    w, h = surface.get_size()
    s = w / 600.0
    surface.fill((26, 28, 34))
    centered(surface, text(pygame, fonts, "bold", 62 * s, TITLE, (245, 245, 245), w * 0.92), int(h * 0.025))

    panel = pygame.Rect(int(w * 0.06), int(h * 0.14), int(w * 0.88), int(h * 0.27))
    pygame.draw.rect(surface, (232, 235, 238), panel, border_radius=int(24 * s))
    draw_handset(pygame, surface, w // 2, panel.centery + int(15 * s), level)

    # microphone level meter
    my = int(h * 0.455)
    centered(surface, text(pygame, fonts, "reg", 30 * s, "Microphone level", (190, 195, 205)), my)
    bar = pygame.Rect(int(w * 0.06), my + int(46 * s), int(w * 0.88), int(46 * s))
    pygame.draw.rect(surface, (0, 0, 0), bar)
    segments = 24
    for i in range(segments):
        if (i + 0.5) / segments <= level:
            colour = (70, 205, 100) if i < 15 else ((250, 205, 50) if i < 20 else (235, 70, 70))
            seg = pygame.Rect(bar.x + 4 + i * (bar.width - 8) // segments, bar.y + 5, (bar.width - 8) // segments - 3, bar.height - 10)
            pygame.draw.rect(surface, colour, seg)
    pygame.draw.rect(surface, (120, 125, 135), bar, 2)

    # countdown
    secs = max(0, int(remaining + 0.999))
    num = text(pygame, fonts, "bold", 190 * s, str(secs), (250, 205, 50))
    ny = int(h * 0.575)
    centered(surface, num, ny)
    centered(surface, text(pygame, fonts, "reg", 34 * s, "seconds left", (190, 195, 205)), ny + num.get_height() - int(14 * s))

    if error:
        centered(surface, text(pygame, fonts, "bold", 34 * s, "Audio stopped:", (235, 90, 90), w * 0.9), int(h * 0.865))
        centered(surface, text(pygame, fonts, "reg", 28 * s, error[:60], (235, 90, 90), w * 0.9), int(h * 0.865) + int(44 * s))
    else:
        centered(surface, text(pygame, fonts, "bold", 36 * s, "Talk into the handset", (245, 245, 245), w * 0.9), int(h * 0.865))
        centered(surface, text(pygame, fonts, "reg", 28 * s, "You should hear yourself a moment later", (200, 205, 215), w * 0.92), int(h * 0.865) + int(46 * s))
    centered(surface, text(pygame, fonts, "reg", 24 * s, "%s     Esc = quit" % card_text, (140, 146, 158), w * 0.95), h - int(h * 0.04))


def to_screen(pygame, screen, logical, rotate, flip):
    if rotate:
        logical = pygame.transform.rotate(logical, -90 if flip else 90)      # pygame turns counter-clockwise for positive angles
    screen.blit(logical, (0, 0))
    pygame.display.flip()


# ------------------------------------------------------------------ main --------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Judicom handset echo test (stops itself after %d seconds)" % RUN_SECONDS)
    ap.add_argument("--seconds", type=float, default=RUN_SECONDS)
    ap.add_argument("--gain", type=float, default=1.0, help="echo volume factor (default 1.0; try 0.5 if it squeals)")
    ap.add_argument("--card", help="ALSA card id to use instead of looking for the USB one (see `aplay -l`)")
    ap.add_argument("--window", action="store_true", help="small window instead of full screen (for a PC), no rotation")
    ap.add_argument("--no-rotate", action="store_true", help="do not turn the picture 90 degrees")
    ap.add_argument("--flip", action="store_true", help="turn it the other way (if the picture is upside-down)")
    args = ap.parse_args()

    # 1. find the USB sound device - stop with an error if it is not there
    try:
        card_id, desc = (args.card, args.card) if args.card else find_usb_card()
    except AudioError as exc:
        sys.exit("ERROR: %s" % exc)
    print("Using sound card %r (%s) for both the microphone and the speaker." % (card_id, desc))

    # 2. the screen (on the Judicom there is no desktop, so SDL draws straight to the display through KMS/DRM)
    if "SDL_VIDEODRIVER" not in os.environ and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
    import pygame
    try:
        pygame.display.init()
        pygame.font.init()
        screen = pygame.display.set_mode((450, 768)) if args.window else pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
    except pygame.error as exc:
        sys.exit("ERROR: cannot open the display: %s\n(over SSH on the Judicom: python3-pygame from apt, and the user in the 'video' and "
                 "'render' groups)" % exc)
    nw, nh = screen.get_size()
    rotate = (nw > nh) and not args.no_rotate and not args.window
    logical = pygame.Surface((nh, nw) if rotate else (nw, nh))
    fonts = load_fonts(pygame)

    # 3. start the echo only now, so that the sound and the countdown begin together
    echo = Echo(card_id, args.gain)
    try:
        echo.start()
    except AudioError as exc:
        pygame.quit()
        sys.exit("ERROR: %s" % exc)

    clock = pygame.time.Clock()
    start = time.monotonic()
    shown, failed_at = 0.0, None
    print("Echo running for %d s.  Talk into the handset." % args.seconds)
    try:
        while True:
            remaining = args.seconds - (time.monotonic() - start)
            if remaining <= 0:
                break
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q)):
                    remaining = 0
            if remaining <= 0:
                break
            if echo.error and failed_at is None:
                failed_at = time.monotonic()
            if failed_at is not None and time.monotonic() - failed_at > 4:
                break
            level = echo.level
            shown = level if level > shown else shown * 0.85 + level * 0.15           # quick rise, smooth fall
            draw(pygame, logical, fonts, remaining, shown, "USB sound card: %s" % card_id, echo.error)
            to_screen(pygame, screen, logical, rotate, args.flip)
            clock.tick(30)
    finally:
        echo.stop()
        pygame.quit()
    if echo.error:
        sys.exit("ERROR: the audio stopped: %s" % echo.error)
    print("Finished after %.0f s." % (time.monotonic() - start))


if __name__ == "__main__":
    main()
