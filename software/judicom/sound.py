"""The dial tone and the dialing digits (in the handset), and the ringer and a message's beeps (the speaker in the base).  The dial tone and the ringer loop
until they are switched off; the digits play once.

    sounds = Sounds(log)                       # finds the two sound cards; a missing card is reported once and stays quiet
    sounds.update(dial_tone=True, ringing=False, digits="")   # every frame, with what the machine wants; only changes do anything
    sounds.close()

The ringer speaker's amplifier is switched by GPIO 25 (config.AMP_PIN, through a MOSFET): Sounds switches it on before the ringer, a
message's beeps or a bong starts, and off AMP_OFF_SECONDS after the last of them has ended (update() checks, every frame).
This is the fix for the noise the amplifier makes when it is on with nothing to play: see docs/HARDWARE.md, "Ringer amplifier switch".

Playing is done by aplay (alsa-utils), fed from a thread with the same piece of sound over and over.  The dial tone must be stopped -
which lets aplay release the USB card - before the phone software opens that card for a call; Sounds does that as soon as the machine
leaves the "handset lifted" screen.
"""
import array
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

from . import config

RATE = 16000                     # Hz, mono, 16 bit; "plughw" converts if a card wants something else
DIAL_TONE_HZ = (350.0, 440.0)    # the North American dial tone: two steady notes together
RING_HZ = (880.0, 1100.0)        # the ringer warbles between these two notes ...
RING_WARBLE_HZ = 20.0            # ... this many times a second ("brrring")
RING_ON, RING_OFF = 2.0, 4.0     # seconds of ringing, then of silence (the North American cadence)
CHUNK = 3200                     # bytes written at a time (0.1 s; under the 4096-byte pipe limit, so never a short write)
LEAD_SECONDS = 0.3               # silence written before any sound: USB adapters swallow the very start
BEEP_HZ, BEEPS, BEEP_ON, BEEP_OFF = 1000.0, 3, 0.15, 0.15     # a new message: three short beeps
KEY_TONE_SECONDS = 0.15                                     # a keypad key's touch-tone (a little longer than a dialer's)
BONG_HZ, BONG_SECONDS = (392.0, 523.3, 659.3, 784.0, 1046.5), 0.5     # the maintenance sequence: armed, then the four corners
DIALING_TAIL = 0.4               # after the last digit: aplay's buffer drains and the card is let go before the call opens it

# Touch-tone (DTMF): each key is one low note (its row) and one high note (its column) together.
DTMF_ROWS, DTMF_COLS = (697.0, 770.0, 852.0, 941.0), (1209.0, 1336.0, 1477.0, 1633.0)
DTMF_KEYS = ("123A", "456B", "789C", "*0#D")
DTMF = {key: (DTMF_ROWS[r], DTMF_COLS[c]) for r, row in enumerate(DTMF_KEYS) for c, key in enumerate(row)}
PHONE_KEYS = "0123456789*#"      # the keys of an ordinary phone (A-D exist in the standard but not on a phone: never played)


def _to_bytes(samples):
    pcm = array.array("h", samples)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()


def dial_tone_pcm(level=config.DIAL_TONE_LEVEL, rate=RATE):
    """One second of 350 + 440 Hz: a whole number of cycles of both, so it loops without a click."""
    return _to_bytes(int(32767 * level * sum(math.sin(2 * math.pi * f * i / rate) for f in DIAL_TONE_HZ)) for i in range(rate))


def ring_pcm(level=config.RING_LEVEL, rate=RATE):
    """One ring and the pause after it (RING_ON + RING_OFF seconds), to be looped."""
    on, total, fade = int(RING_ON * rate), int((RING_ON + RING_OFF) * rate), int(0.03 * rate)   # 30 ms fades: no clicks
    half = rate / (2.0 * RING_WARBLE_HZ)
    phase, out = 0.0, []
    for i in range(total):
        if i < on:
            phase += 2 * math.pi * RING_HZ[int(i / half) % 2] / rate      # the phase runs on across each switch: no clicks
            out.append(int(32767 * level * min(1.0, i / fade, (on - i) / fade) * math.sin(phase)))
        else:
            out.append(0)
    return _to_bytes(out)


def beeps_pcm(level=config.BEEP_LEVEL, rate=RATE):
    """The three beeps of a new message, played once."""
    on, off, fade = int(BEEP_ON * rate), int(BEEP_OFF * rate), int(0.01 * rate)           # 10 ms fades: no clicks
    one = [int(32767 * level * min(1.0, i / fade, (on - i) / fade) * math.sin(2 * math.pi * BEEP_HZ * i / rate)) for i in range(on)]
    return _to_bytes((one + [0] * off) * BEEPS)


def bong_pcm(step, level=config.BONG_LEVEL, rate=RATE):
    """One bong of the maintenance sequence: a bell that dies away, higher for each step."""
    hz, n, fade = BONG_HZ[step], int(BONG_SECONDS * rate), int(0.005 * rate)
    return _to_bytes([int(32767 * level * min(1.0, i / fade, (n - i) / fade) * math.exp(-5.0 * i / rate) *
                          (0.75 * math.sin(2 * math.pi * hz * i / rate) + 0.25 * math.sin(4 * math.pi * hz * i / rate)))
                      for i in range(n)])


def dialable(digits):
    """Only the keys of an ordinary phone: '+1 (555) 010-0142' -> '15550100142', 'frank' -> ''."""
    return "".join(ch for ch in (digits or "") if ch in PHONE_KEYS)


def digits_pcm(digits, level=config.DIGIT_LEVEL, on=config.DIGIT_ON, off=config.DIGIT_OFF, rate=RATE):
    """The touch-tones of `digits`, each `on` seconds long (faded in and out: no clicks) with `off` seconds of quiet after it."""
    n_on, n_off, fade = int(on * rate), int(off * rate), int(0.005 * rate)
    out = []
    for key in dialable(digits):
        lo, hi = DTMF[key]
        for i in range(n_on):
            gain = min(1.0, i / fade, (n_on - i) / fade)
            out.append(int(32767 * level * gain * (math.sin(2 * math.pi * lo * i / rate) + math.sin(2 * math.pi * hi * i / rate))))
        out.extend([0] * n_off)
    return _to_bytes(out)


def dialing_seconds(digits, on=config.DIGIT_ON, off=config.DIGIT_OFF):
    """How long the dialing sound takes from start to the card being free again; 0 when there is nothing to dial."""
    n = len(dialable(digits))
    return LEAD_SECONDS + n * (on + off) + DIALING_TAIL if n else 0.0


def find_usb_card(proc_dir="/proc/asound"):
    """The ALSA card id of the first USB sound card that can play (the handset), or None."""
    try:
        with open(os.path.join(proc_dir, "cards")) as fh:
            listing = fh.read()
    except OSError:
        return None
    for m in re.finditer(r"^\s*(\d+) \[([^\]]*?)\s*\]:\s*(\S+)\s+-\s+(.*)$", listing, flags=re.MULTILINE):
        if m.group(3).lower().replace("_", "-") == "usb-audio" and os.path.exists(os.path.join(proc_dir, "card" + m.group(1), "pcm0p")):
            return m.group(2).strip()
    return None


def card_exists(card_id, proc_dir="/proc/asound"):
    return os.path.isdir(os.path.join(proc_dir, card_id))           # /proc/asound/<id> is a link to the card's folder


class Loop:
    """A piece of sound played over and over on one card until stop().  repeat=False: played once, then aplay ends by itself."""

    def __init__(self, card_id, pcm, name, log, repeat=True):
        self.device = "plughw:CARD=%s,DEV=0" % card_id
        self.pcm, self.name, self.log, self.repeat = pcm, name, log, repeat
        self._proc = self._thread = self._stop = self._err = None

    @property
    def playing(self):
        return self._proc is not None and self._proc.poll() is None

    def start(self):
        if self._proc is not None and self._proc.poll() is not None:
            self.stop()                                                   # the last aplay died by itself: clean up, try again
        if self._proc is not None:
            return
        cmd = ["aplay", "-q", "-D", self.device, "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
               "--buffer-time=200000", "--period-time=50000", "-"]
        err = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err, bufsize=0)
        except FileNotFoundError:
            err.close()
            self.log("(no %s: aplay is not installed - sudo apt install alsa-utils)" % self.name)
            return
        stop = threading.Event()

        def feed():
            try:
                proc.stdin.write(bytes(int(LEAD_SECONDS * RATE) * 2))     # a moment of silence first: USB adapters swallow the very start
                while not stop.is_set():
                    for off in range(0, len(self.pcm), CHUNK):
                        if stop.is_set():
                            return
                        proc.stdin.write(self.pcm[off:off + CHUNK])
                    if not self.repeat:
                        proc.stdin.close()                                # aplay plays what it has, then ends and lets the card go
                        return
            except (BrokenPipeError, OSError, ValueError):
                if not stop.is_set():
                    try:
                        err.seek(0)
                        why = err.read().decode(errors="replace").strip().splitlines()
                    except (OSError, ValueError):
                        why = []
                    self.log("(%s stopped: %s)" % (self.name, why[-1] if why else "aplay ended"))
        thread = threading.Thread(target=feed, name=self.name, daemon=True)
        thread.start()
        self._proc, self._thread, self._stop, self._err = proc, thread, stop, err

    def stop(self):
        if self._proc is None:
            return
        self._stop.set()
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
        self._thread.join(timeout=2)
        self._err.close()
        self._proc = self._thread = self._stop = self._err = None


class Silent:
    """Stands in for a sound whose card is missing (or with --no-sound)."""
    playing = False

    def start(self):
        pass

    def play(self, names):
        pass

    def stop(self):
        pass


class Amp:
    """The ringer's amplifier.  Held low (off) from the start, so the pin does not float while the phone program runs."""

    def __init__(self, pin=config.AMP_PIN):
        from gpiozero import DigitalOutputDevice
        self.pin = pin
        self._device = DigitalOutputDevice(pin, initial_value=False)
        self.is_on = False

    def on(self):
        if not self.is_on:
            self._device.on()
            self.is_on = True

    def off(self):
        if self.is_on:
            self._device.off()
            self.is_on = False

    def close(self):
        self._device.off()
        self._device.close()


def make_amp(log=None):
    """The amplifier switch, or None (said in the log: then the ringer speaker may stay silent)."""
    try:
        return Amp()
    except Exception as exc:                             # noqa: BLE001 - no GPIO (a PC), or the pin is taken: the phone goes on
        (log or print)("(cannot switch the ringer's amplifier on GPIO %d: %s.  The ringer may be silent.)" % (config.AMP_PIN, exc))
        return None


class Sounds:
    def __init__(self, log=None, enabled=True, handset_card=None, ringer_card=None, make_loop=Loop, amp=None, clock=time.monotonic,
                 make_mixer=None):
        self.log = log or (lambda msg: None)
        self.make_loop = make_loop
        self.amp, self.clock = amp, clock
        self._quiet_since = None
        self.dial = self.ring = self.digits = self.beeps = Silent()
        self.bongs, self._bong = [], Silent()
        self.game, self.make_mixer = Silent(), make_mixer             # the hidden game's sound (judicom/game_sound.py), made when needed
        self.handset_card = self.ringer_card = None
        if enabled:
            self.handset_card = handset_card or find_usb_card()
            self.ringer_card = ringer_card or (config.RINGER_CARD if card_exists(config.RINGER_CARD) else None)
            if self.handset_card:
                self.dial = make_loop(self.handset_card, dial_tone_pcm(), "dial tone", self.log)
            if self.ringer_card:
                self.ring = make_loop(self.ringer_card, ring_pcm(), "ringer", self.log)
                self.beeps = make_loop(self.ringer_card, beeps_pcm(), "message beeps", self.log, repeat=False)
                self.bongs = [make_loop(self.ringer_card, bong_pcm(step), "bong", self.log, repeat=False) for step in range(len(BONG_HZ))]
        self._want = (False, False, "")

    def describe(self):
        return "dial tone: %s.  ringer: %s." % (
            "sound card '%s'" % self.handset_card if self.handset_card else "no USB sound device (silent)",
            "sound card '%s'" % self.ringer_card if self.ringer_card else "no '%s' card (silent)" % config.RINGER_CARD)

    def _speaker_on(self):
        """Before anything starts on the ringer speaker."""
        self._quiet_since = None
        if self.amp is not None:
            self.amp.on()

    def _check_amp(self):
        """Off once the speaker has been quiet for AMP_OFF_SECONDS (so the end of a sound is not cut, and a ring's gaps keep it on)."""
        if self.amp is None or not self.amp.is_on:
            return
        if self.ring.playing or self.beeps.playing or self._bong.playing or self.game.playing:
            self._quiet_since = None
        elif self._quiet_since is None:
            self._quiet_since = self.clock()
        elif self.clock() - self._quiet_since >= config.AMP_OFF_SECONDS:
            self.amp.off()
            self._quiet_since = None

    def update(self, dial_tone, ringing, digits=""):
        """digits: the touch-tones to play once (while the machine is dialing), or "" for none."""
        self._check_amp()
        want = (bool(dial_tone), bool(ringing), dialable(digits))
        if want == self._want:
            return
        digits_changed = want[2] != self._want[2]
        self._want = want
        if not want[0]:                                 # first everything that stops: the dial tone must let the card go
            self.dial.stop()                            # before the dialing sound opens it
        if not want[1]:
            self.ring.stop()
        if digits_changed:
            self.digits.stop()
            self.digits = Silent()
            if want[2] and self.handset_card:
                self.digits = self.make_loop(self.handset_card, digits_pcm(want[2]), "dialing", self.log, repeat=False)
        if want[0]:
            self.dial.start()
        if want[1]:
            self.beeps.stop()                           # the ringer needs the card
            self._bong.stop()
            self.game.stop()
            self._speaker_on()
            self.ring.start()
        if digits_changed and want[2]:
            self.digits.start()
        self.log("      dial tone %s, ringer %s%s" % ("ON" if want[0] else "off", "ON" if want[1] else "off",
                                                    ", dialing %s" % want[2] if want[2] else ""))

    def key_tone(self, key):
        """One key's touch-tone in the handset, now (the hidden keypad).  Cuts off the one before.  Call it after update(),
        which has already stopped the dial tone at the first digit, so the card is free."""
        if not (self.handset_card and dialable(key)):
            return
        self.digits.stop()
        self.digits = self.make_loop(self.handset_card, digits_pcm(key, on=KEY_TONE_SECONDS), "key tone", self.log, repeat=False)
        self.digits.start()

    def beep(self):
        """The three beeps of a new message (not over the ringer: a call matters more)."""
        if not self._want[1]:
            self._speaker_on()
            self.beeps.start()

    def bong(self, step):
        """One bong of the maintenance sequence, cutting off the one before (not over the ringer: a call matters more)."""
        if self._want[1] or step >= len(self.bongs):
            return
        self.beeps.stop()                               # one sound at a time on this card
        self._bong.stop()
        self._bong = self.bongs[step]
        self._speaker_on()
        self._bong.start()

    def game_on(self, sounds=None):
        """A hidden game's sound on the ringer speaker, from now until game_off() (not over the ringer: a call matters more).
        sounds: the game's own ({name: samples}; None: Invaders')."""
        if self._want[1] or not self.ringer_card:
            return
        if self.make_mixer is None:
            from .game_sound import Mixer
            self.make_mixer = Mixer
        self.game.stop()
        self.game = self.make_mixer(self.ringer_card, self.log, sounds)
        self.beeps.stop()                               # one aplay at a time on this card
        self._bong.stop()
        self._speaker_on()
        self.game.start()

    def game_play(self, names):
        """The game's sounds, by name (game.py's events)."""
        if names and self.game.playing:
            self.game.play(names)

    def game_off(self):
        self.game.stop()

    def close(self):
        self.game.stop()
        self.dial.stop()
        self.ring.stop()
        self.beeps.stop()
        self._bong.stop()
        self.digits.stop()
        if self.amp is not None:
            self.amp.close()
