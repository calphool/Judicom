#!/usr/bin/env python3
"""
speaker_tone_test.py - Judicom handset SPEAKER level test.
 
Plays a gentle looping melody (a scale and an arpeggio, C4 up to C6) through the handset speaker on the USB sound device, at a fixed,
moderate signal level.  While it plays you change the speaker's loudness with the keyboard, so you can find the level that sounds
right.  The microphone is not used at all, so whatever you hear has nothing to do with the mic or with feedback.
 
  Up or +        louder             Down or -      quieter
  PgUp / PgDn    five steps         q or Esc       quit
 
The keys move the card's "Speaker" mixer control (the same one as `alsamixer -c Device`).  When you quit, the final setting is printed.
To keep it across reboots and power cuts:     sudo alsactl store
 
It stops by itself after 5 minutes (--seconds N changes that).  If the USB sound device is missing it stops with an error.
 
Run it from an SSH session on the Judicom:       python3 speaker_tone_test.py
Needs only alsa-utils (aplay and amixer), already on Raspberry Pi OS - nothing to install.
Start with the handset a little away from your ear, then bring it closer.
Other options:  --card NAME (use this ALSA card instead of finding the USB one)   --control NAME (mixer control, default Speaker)
"""
import argparse
import array
import math
import os
import re
import select
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty
 
RUN_SECONDS = 300
RATE = 16000                    # Hz, mono, 16 bit (ALSA's "plughw" converts if the device wants something else)
PEAK = 0.35                     # loudest sample as a fraction of full scale (about -9 dBFS): a moderate, undistorted level
NOTE_SECONDS = 0.25
SPEAKER_CONTROL = "Speaker"
BIG_STEP = 5
SCALE = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60]         # MIDI note numbers: C major scale up and down (C4..C5)
ARPEGGIO = [60, 64, 67, 72, 76, 79, 84, 79, 76, 72, 67, 64, 60]              # C major chord spread over C4..C6 and back
 
 
class AudioError(RuntimeError):
    pass
 
 
# ------------------------------------------------------------------ finding the USB sound device ------------------------------
def find_usb_card(proc_dir="/proc/asound"):
    """Return (card id, description) of the first USB sound card that has a playback device (the handset speaker)."""
    try:
        with open(os.path.join(proc_dir, "cards")) as fh:
            text = fh.read()
    except OSError as exc:
        raise AudioError("Cannot read the list of sound cards (%s)." % exc)
    cards, usb_without_playback = [], []
    for m in re.finditer(r"^\s*(\d+) \[([^\]]*?)\s*\]:\s*(\S+)\s+-\s+(.*)$", text, flags=re.MULTILINE):
        num, card_id, driver, desc = m.group(1), m.group(2).strip(), m.group(3), m.group(4).strip()
        cards.append("%s (%s)" % (card_id, driver))
        if driver.lower().replace("_", "-") != "usb-audio":
            continue
        card_dir = os.path.join(proc_dir, "card" + num)
        names = os.listdir(card_dir) if os.path.isdir(card_dir) else []
        if "pcm0p" in names:
            return card_id, desc
        usb_without_playback.append(card_id)
    if usb_without_playback:
        raise AudioError("USB sound card %s was found, but it has no speaker (playback) output." % ", ".join(usb_without_playback))
    raise AudioError("No USB sound device found.  Sound cards present: %s.  Is the handset's USB audio adapter plugged in?"
                     % (", ".join(cards) or "none"))
 
 
# ------------------------------------------------------------------ the melody ----------------------------------------------------
def midi_hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)
 
 
def note_samples(midi):
    """One soft, bell-like note: fundamental plus two quiet harmonics, quick attack, exponential decay, faded to zero at the end."""
    n = int(NOTE_SECONDS * RATE)
    attack, release = int(0.008 * RATE), int(0.03 * RATE)
    w = 2.0 * math.pi * midi_hz(midi)
    out = []
    for i in range(n):
        t = i / RATE
        tone = math.sin(w * t) + 0.30 * math.sin(2 * w * t) + 0.10 * math.sin(3 * w * t)
        out.append(tone * math.exp(-t / 0.10) * min(1.0, i / attack, (n - i) / release))
    return out
 
 
def make_melody():
    """The whole loop as 16 bit little-endian mono PCM bytes; it begins and ends in silence, so repeating it never clicks."""
    rest = lambda seconds: [0.0] * int(seconds * RATE)          # noqa: E731
    samples = []
    for midi in SCALE:
        samples += note_samples(midi)
    samples += rest(0.4)
    for midi in ARPEGGIO:
        samples += note_samples(midi)
    samples += rest(0.8)
    scale = PEAK * 32767.0 / max(abs(s) for s in samples)
    pcm = array.array("h", [int(round(s * scale)) for s in samples])
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()
 
 
# ------------------------------------------------------------------ playing it ----------------------------------------------------
class Tones:
    """aplay fed with the melody over and over by a background thread."""
 
    def __init__(self, card_id, pcm):
        self.device = "plughw:CARD=%s,DEV=0" % card_id
        self.pcm = pcm
        self.error = None
        self._stop = threading.Event()
        self._proc = self._thread = self._err = None
 
    def start(self):
        cmd = ["aplay", "-q", "-D", self.device, "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
               "--buffer-time=200000", "--period-time=50000", "-"]
        self._err = tempfile.TemporaryFile()
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self._err, bufsize=0)
        except FileNotFoundError as exc:
            raise AudioError("%s is not installed (sudo apt install alsa-utils)." % exc.filename)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
 
    def _run(self):
        try:
            self._proc.stdin.write(bytes(int(0.4 * RATE) * 2))          # a moment of silence first: USB adapters swallow the very start
            while not self._stop.is_set():
                for off in range(0, len(self.pcm), 3200):               # 0.1 s pieces (under the 4096-byte pipe limit: never a short write)
                    if self._stop.is_set():
                        return
                    self._proc.stdin.write(self.pcm[off:off + 3200])
        except (BrokenPipeError, OSError):
            pass
        if not self._stop.is_set():
            self._err.seek(0)
            why = self._err.read().decode(errors="replace").strip()
            self.error = why.splitlines()[-1] if why else "the audio stream stopped unexpectedly"
 
    def stop(self):
        self._stop.set()
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._thread is not None:
            self._thread.join(timeout=2)
 
 
# ------------------------------------------------------------------ the mixer -----------------------------------------------------
class Mixer:
    """Reads and sets one playback volume control with amixer."""
 
    def __init__(self, card_id, control):
        self.card, self.control = card_id, control
 
    def read(self):
        """-> dict(min, max, value, db, on), or None if the control cannot be read."""
        try:
            r = subprocess.run(["amixer", "-c", self.card, "sget", self.control], capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if r.returncode != 0:
            return None
        limits = re.search(r"Limits:\s*Playback\s+(-?\d+)\s*-\s*(-?\d+)", r.stdout)
        cur = re.search(r"Playback\s+(-?\d+)\s*\[(\d+)%\](?:\s*\[(-?[\d.]+)dB\])?(?:\s*\[(on|off)\])?", r.stdout)
        if not (limits and cur):
            return None
        return {"min": int(limits.group(1)), "max": int(limits.group(2)), "value": int(cur.group(1)),
                "db": float(cur.group(3)) if cur.group(3) else None, "on": cur.group(4) != "off"}
 
    def set(self, value):
        subprocess.run(["amixer", "-c", self.card, "-q", "sset", self.control, str(value)], capture_output=True, timeout=5)
 
 
# ------------------------------------------------------------------ keyboard ------------------------------------------------------
def parse_keys(data):
    """Raw bytes from the terminal -> a list of 'up', 'down', 'pgup', 'pgdn', 'quit'."""
    sequences = ((b"\x1b[A", "up"), (b"\x1bOA", "up"), (b"\x1b[B", "down"), (b"\x1bOB", "down"),
                 (b"\x1b[5~", "pgup"), (b"\x1b[6~", "pgdn"))
    keys, i = [], 0
    while i < len(data):
        rest = data[i:]
        for seq, name in sequences:
            if rest.startswith(seq):
                keys.append(name)
                i += len(seq)
                break
        else:
            ch = rest[:1]
            if ch in (b"+", b"="):
                keys.append("up")
            elif ch in (b"-", b"_"):
                keys.append("down")
            elif ch in (b"q", b"Q") or rest == b"\x1b":                 # q, or a lone Esc key
                keys.append("quit")
            i += 1
    return keys
 
 
def status_line(state, remaining, control):
    if state is None:
        return "No '%s' control to show - set the level with:  alsamixer -c <card>      stops in %3d s" % (control, remaining)
    span = max(1, state["max"] - state["min"])
    filled = int(round(20.0 * (state["value"] - state["min"]) / span))
    db = "  %+.1f dB" % state["db"] if state["db"] is not None else ""
    muted = "   ** MUTED - press m in alsamixer to unmute **" if not state["on"] else ""
    return "%s %2d of %d%s  [%s%s]  stops in %3d s%s" % (control, state["value"], state["max"], db,
                                                         "#" * filled, "-" * (20 - filled), remaining, muted)
 
 
# ------------------------------------------------------------------ main ----------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Judicom handset speaker level test (closes itself after %d seconds)" % RUN_SECONDS)
    ap.add_argument("--seconds", type=float, default=RUN_SECONDS, help="how long to run at most (default %d)" % RUN_SECONDS)
    ap.add_argument("--card", help="ALSA card name to use instead of finding the USB sound device")
    ap.add_argument("--control", default=SPEAKER_CONTROL, help="mixer control to adjust (default %s)" % SPEAKER_CONTROL)
    args = ap.parse_args()
 
    try:
        if args.card:
            card_id, desc = args.card, args.card
        else:
            card_id, desc = find_usb_card()
    except AudioError as exc:
        sys.exit("ERROR: %s" % exc)
 
    mixer = Mixer(card_id, args.control)
    state = mixer.read()
    interactive = sys.stdin.isatty()
    print("Speaker tone test - sound card '%s' (%s)" % (card_id, desc))
    print("A looping melody plays at a fixed level; the '%s' mixer control decides how loud it is." % args.control)
    if state is None:
        print("WARNING: cannot read the '%s' control on card '%s'.  (amixer -c %s scontrols  lists the controls.)" % (args.control, card_id, card_id))
    if interactive:
        print("Up / +  louder     Down / -  quieter     PgUp / PgDn  five steps     q or Esc  quit")
    else:
        print("Not running in a terminal, so the keys are off; change the level from another window with:  amixer -c %s sset %s N" % (card_id, args.control))
    print("Start with the handset a little away from your ear.\n")
 
    tones = Tones(card_id, make_melody())
    try:
        tones.start()
    except AudioError as exc:
        sys.exit("ERROR: %s" % exc)
 
    fd = sys.stdin.fileno() if interactive else None
    old_attrs = termios.tcgetattr(fd) if interactive else None
    deadline = time.monotonic() + args.seconds
    shown = None
    failure = None
    try:
        if interactive:
            tty.setcbreak(fd)                                       # keys arrive one at a time, without waiting for Enter
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if tones.error:
                failure = tones.error
                break
            quit_now = False
            if interactive and select.select([fd], [], [], 0.2)[0]:
                for key in parse_keys(os.read(fd, 64)):
                    if key == "quit":
                        quit_now = True
                    elif state is not None:
                        step = BIG_STEP if key in ("pgup", "pgdn") else 1
                        target = state["value"] + (step if key in ("up", "pgup") else -step)
                        mixer.set(max(state["min"], min(state["max"], target)))
                        state = mixer.read() or state
            elif not interactive:
                time.sleep(0.2)
            if quit_now:
                break
            line = status_line(state, int(remaining + 0.999), args.control)
            if line != shown:
                sys.stdout.write("\r\033[K" + line)
                sys.stdout.flush()
                shown = line
    except KeyboardInterrupt:
        pass
    finally:
        tones.stop()
        if interactive:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    print()
 
    if failure:
        sys.exit("ERROR: audio stopped: %s" % failure)
    state = mixer.read() or state
    if state is not None:
        print("Final setting: %s %d of %d%s." % (args.control, state["value"], state["max"],
                                                 " (%+.1f dB)" % state["db"] if state["db"] is not None else ""))
        print("To make it permanent (survives reboot and power cuts):   sudo alsactl store")
 
 
if __name__ == "__main__":
    main()
 
