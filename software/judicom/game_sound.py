"""The hidden game's sounds, made here, and the mixer that plays them on the ringer speaker.

The phone's other sounds each start their own aplay (judicom/sound.py), which takes a few tenths of a second: far too slow for a
game, and they cannot overlap.  So the game has one aplay for as long as it runs, fed by a thread that mixes whatever is
sounding, a little ahead of time (AHEAD_SECONDS).  Sounds (sound.py) starts and stops it: never over the ringer.
"""
import array
import math
import random
import subprocess
import tempfile
import threading
import time

from . import config

RATE = 16000
CHUNK = 160                      # samples mixed at a time (10 ms)
AHEAD_SECONDS = 0.06             # mixed this far ahead of what is being heard: the delay of a sound
LEAD_SECONDS = 0.3               # silence first: USB adapters (and the Pi's jack) swallow the very start
MAX_VOICES = 8
MARCH_HZ = (82.0, 110.0, 73.0, 98.0)      # the formation's steps, round and round


def _env(i, n, attack=0.004):
    """A quick start, then a straight fade to nothing."""
    a = int(attack * RATE)
    return min(1.0, i / a if a else 1.0) * (1.0 - i / n)


def _square(phase):
    return 1.0 if (phase % 1.0) < 0.5 else -1.0


def _pcm(values, level):
    return array.array("h", (int(max(-1.0, min(1.0, v)) * level * 32767) for v in values))


def shoot_pcm(level):
    n, phase, out = int(0.11 * RATE), 0.0, []
    for i in range(n):
        f = 1500.0 - 1000.0 * i / n                     # a falling zap
        phase += f / RATE
        out.append(_square(phase) * _env(i, n) * 0.6)
    return _pcm(out, level)


def hit_pcm(level):
    rng, n, phase, out = random.Random(1), int(0.18 * RATE), 0.0, []
    for i in range(n):
        phase += (320.0 - 240.0 * i / n) / RATE
        out.append((0.55 * rng.uniform(-1, 1) + 0.45 * _square(phase)) * _env(i, n))
    return _pcm(out, level)


def die_pcm(level):
    """A long, crunching break-up: noise held for longer and longer stretches, so it sinks lower as it fades."""
    rng, n, out, held, hold = random.Random(2), int(1.1 * RATE), [], 0.0, 0
    for i in range(n):
        if hold <= 0:
            held, hold = rng.uniform(-1, 1), 1 + int(14 * i / n)
        hold -= 1
        out.append(held * (1.0 - i / n) ** 1.5)
    return _pcm(out, level)


def march_pcm(hz, level):
    n, out = int(0.09 * RATE), []
    for i in range(n):
        out.append(_square(i * hz / RATE) * _env(i, n) ** 0.7)
    return _pcm(out, level * 0.9)


def bonus_pcm(level):
    """The bonus ship's warble: one loop of it (it repeats while the ship is on the screen); whole cycles, so no click."""
    n, phase, out = int(0.3 * RATE), 0.0, []
    for i in range(n):
        f = 750.0 + 170.0 * math.sin(2 * math.pi * 2 * i / n)
        phase += f / RATE
        tri = 4 * abs((phase % 1.0) - 0.5) - 1
        out.append(tri * 0.5)
    return _pcm(out, level)


def notes_pcm(notes, on, off, level):
    out = []
    for hz in notes:
        n = int(on * RATE)
        out += [_square(i * hz / RATE) * _env(i, n) * 0.5 for i in range(n)]
        out += [0.0] * int(off * RATE)
    return _pcm(out, level)


_cache = {}


def invaders_sounds():
    """Invaders' sounds, made once (it takes a moment on the Pi)."""
    if "invaders" not in _cache:
        _cache["invaders"] = make_sounds()
    return _cache["invaders"]


def make_sounds(level=None):
    level = config.GAME_LEVEL if level is None else level
    sounds = {"shoot": shoot_pcm(level), "hit": hit_pcm(level), "die": die_pcm(level), "bonus": bonus_pcm(level),
              "bonus_hit": notes_pcm((523.3, 659.3, 784.0, 1046.5), 0.07, 0.01, level),
              "extra": notes_pcm((1318.5, 1318.5, 1318.5), 0.06, 0.04, level)}
    for i, hz in enumerate(MARCH_HZ):
        sounds["march%d" % i] = march_pcm(hz, level)
    return sounds


def tone_pcm(hz, seconds, level, to_hz=None):
    """A square tone, quickly faded; with to_hz it slides there."""
    n, phase, out = int(seconds * RATE), 0.0, []
    for i in range(n):
        phase += (hz + ((to_hz or hz) - hz) * i / n) / RATE
        out.append(_square(phase) * _env(i, n) * 0.5)
    return _pcm(out, level)


def bricks_sounds(level=None):
    """Brick Breaker's sounds, made once."""
    if "bricks" not in _cache:
        level = config.GAME_LEVEL if level is None else level
        sounds = {"paddle": tone_pcm(196.0, 0.06, level), "wall": tone_pcm(1200.0, 0.015, level * 0.7),
                  "lost": tone_pcm(600.0, 0.5, level, to_hz=140.0),
                  "level": notes_pcm((523.3, 659.3, 784.0, 1046.5), 0.09, 0.02, level),
                  "over": notes_pcm((784.0, 659.3, 523.3, 392.0, 261.6), 0.2, 0.05, level)}
        for i, hz in enumerate((987.8, 784.0, 659.3, 523.3)):          # the top bricks ring highest
            sounds["brick%d" % i] = tone_pcm(hz, 0.05, level)
        _cache["bricks"] = sounds
    return _cache["bricks"]


def noise_pcm(seconds, level, hold_from=1, hold_to=12, seed=3):
    """A burst of rough noise that sinks lower as it fades (held for longer and longer stretches)."""
    rng, n, out, held, hold = random.Random(seed), int(seconds * RATE), [], 0.0, 0
    for i in range(n):
        if hold <= 0:
            held, hold = rng.uniform(-1, 1), hold_from + int((hold_to - hold_from) * i / n)
        hold -= 1
        out.append(held * (1.0 - i / n) ** 1.3)
    return _pcm(out, level)


# Mars Patrol's tune, written for the Judicom: a bouncing, syncopated bass line in E major over sixteenth-note hi-hats, four
# bars round and round (A A B C).  Sixteenths at 140 beats a minute; each bar is 16 steps: a note name to play, "." to rest.
# The bass sounds an octave up (E3 = 164.8 Hz): the little speaker cannot make the real bass notes.
TUNE_STEP = 60 / 140 / 4
NOTE = {"E3": 164.8, "F#3": 185.0, "G#3": 207.7, "A3": 220.0, "B3": 246.9, "C#4": 277.2, "D4": 293.7, "D#4": 311.1,
        "E4": 329.6, "F#4": 370.0, "A4": 440.0, "B4": 493.9}
TUNE_BARS = (
    "E3 . E4 . G#3 . A3 B3 . E3 . E4 D4 . B3 .",
    "E3 . E4 . G#3 . A3 B3 . E3 . E4 D4 . B3 .",
    "A3 . A4 . C#4 . E4 . B3 . B4 . F#4 D#4 B3 .",
    "E3 . E4 . G#3 A3 B3 . C#4 . B3 . G#3 . F#3 .",
)


def tune_pcm(level):
    step = int(TUNE_STEP * RATE)
    notes = [n for bar in TUNE_BARS for n in bar.split()]
    out = [0.0] * (step * len(notes))
    rng = random.Random(8)
    for k, name in enumerate(notes):
        base = k * step
        if name != ".":                                 # a plucked bass note: bright at first, then rounder
            hz, length = NOTE[name], int(step * 1.8)
            for i in range(min(length, len(out) - base)):
                bright = _square(i * hz / RATE)
                round_ = math.sin(2 * math.pi * i * hz / RATE)
                fade = (1 - i / length) ** 1.5
                out[base + i] += 0.55 * fade * (0.4 * bright + 0.6 * round_)
        tick = int(0.012 * RATE)                        # the hi-hat, on every sixteenth, a little louder off the beat
        loud = 0.16 if k % 2 else 0.09
        for i in range(tick):
            out[base + i] += loud * rng.uniform(-1, 1) * (1 - i / tick)
    return _pcm(out, level)


def mars_sounds(level=None):
    """Mars Patrol's sounds, made once."""
    if "mars" not in _cache:
        level = config.GAME_LEVEL if level is None else level
        sounds = {"fire": tone_pcm(1800.0, 0.08, level * 0.8, to_hz=600.0),
                  "jump": tone_pcm(300.0, 0.15, level * 0.7, to_hz=700.0),
                  "land": tone_pcm(120.0, 0.06, level * 0.8),
                  "rock": noise_pcm(0.25, level),
                  "boom": noise_pcm(0.35, level, hold_from=2, hold_to=16, seed=5),
                  "bomb": noise_pcm(0.2, level * 0.8, hold_from=3, hold_to=10, seed=6),
                  "die": die_pcm(level),
                  "checkpoint": notes_pcm((784.0, 987.8, 1174.7), 0.08, 0.02, level),
                  "course": notes_pcm((523.3, 659.3, 784.0, 1046.5, 784.0, 1046.5), 0.09, 0.02, level),
                  "over": notes_pcm((659.3, 587.3, 523.3, 440.0, 392.0, 329.6), 0.2, 0.04, level),
                  "extra": notes_pcm((1318.5, 1318.5, 1318.5), 0.06, 0.04, level),
                  "music": tune_pcm(level * 0.22)}        # background: well under the game's own sounds
        _cache["mars"] = sounds
    return _cache["mars"]


def mix(voices, n):
    """n samples of everything in voices ([samples, position, loops?]), moving each on; finished ones are dropped."""
    out = [0] * n
    keep = []
    for v in voices:
        samples, pos, loops = v
        got = 0
        while got < n:
            part = samples[pos:pos + n - got]
            for i, x in enumerate(part, got):
                out[i] += x
            got += len(part)
            pos += len(part)
            if pos >= len(samples):
                if not loops:
                    break
                pos = 0
        v[1] = pos
        if loops or pos < len(samples):
            keep.append(v)
    voices[:] = keep
    return array.array("h", (32767 if x > 32767 else -32768 if x < -32768 else x for x in out)).tobytes()


class Mixer:
    """The game's sound on one card.  start() / stop(); play(names) with the game's events.  sounds: {name: samples}
    (a looping sound is played by "<name>_on" and stopped by "<name>_off")."""

    def __init__(self, card_id, log=None, sounds=None, popen=subprocess.Popen, clock=time.monotonic):
        self.device = "plughw:CARD=%s,DEV=0" % card_id
        self.log = log or (lambda msg: None)
        self.sounds = sounds if sounds is not None else invaders_sounds()
        self.popen, self.clock = popen, clock
        self._voices, self._loops = [], {}
        self._lock = threading.Lock()
        self._proc = self._thread = self._stop = None

    @property
    def playing(self):
        return self._proc is not None and self._proc.poll() is None

    def play(self, names):
        with self._lock:
            for name in names:
                if name.endswith("_on") and name[:-3] in self.sounds:
                    loop = name[:-3]
                    if loop not in self._loops:
                        self._loops[loop] = [self.sounds[loop], 0, True]
                        self._voices.append(self._loops[loop])
                elif name.endswith("_off"):
                    v = self._loops.pop(name[:-4], None)
                    if v in self._voices:
                        self._voices.remove(v)
                elif name in self.sounds:
                    pcm = self.sounds[name]
                    self._voices[:] = [v for v in self._voices if v[0] is not pcm]     # the same sound again: start it over
                    if len(self._voices) >= MAX_VOICES:
                        self._voices.pop(0)
                    self._voices.append([pcm, 0, False])

    def start(self):
        if self.playing:
            return
        self.stop()
        cmd = ["aplay", "-q", "-D", self.device, "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1",
               "--buffer-time=100000", "--period-time=20000", "-"]
        err = tempfile.TemporaryFile()
        try:
            proc = self.popen(cmd, stdin=subprocess.PIPE, stderr=err, bufsize=0)
        except FileNotFoundError:
            err.close()
            self.log("(no game sound: aplay is not installed)")
            return
        stop = threading.Event()

        def feed():
            try:
                proc.stdin.write(bytes(int(LEAD_SECONDS * RATE) * 2))
                start, written = self.clock(), 0
                while not stop.is_set():
                    ahead = written / RATE - (self.clock() - start)
                    if ahead < -0.2:                    # far behind (the Pi was busy): start the reckoning again
                        start, written = self.clock(), 0
                    elif ahead < AHEAD_SECONDS:
                        with self._lock:
                            data = mix(self._voices, CHUNK)
                        proc.stdin.write(data)
                        written += CHUNK
                    else:
                        stop.wait(0.004)
            except (BrokenPipeError, OSError, ValueError):
                if not stop.is_set():
                    self.log("(game sound stopped: aplay ended)")
            finally:
                err.close()
        self._thread = threading.Thread(target=feed, name="game sound", daemon=True)
        self._proc, self._stop = proc, stop
        self._thread.start()

    def stop(self):
        with self._lock:
            self._voices, self._loops = [], {}
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
        self._proc = self._thread = self._stop = None
