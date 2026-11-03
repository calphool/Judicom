#!/usr/bin/env python3
"""
play_ringtone.py - play ~/phone_ring.wav on the Raspberry Pi's headphone jack (the card that feeds the ringtone amplifier).
 
  * The headphone card is looked up BY NAME ("Headphones"), not by number, because ALSA card numbers can change between boots.
    If that card is not present, HeadphonesNotFound is raised (the command line prints it and exits with status 1).
  * If ~/phone_ring.wav does not exist, a ringtone-like sound is generated and saved there first, then played.
    An existing file is never overwritten.
 
Run:   python3 play_ringtone.py            (as your normal user, not with sudo: "~" must be /home/joe)
Needs: aplay (package alsa-utils, already on Raspberry Pi OS).  Nothing to pip install.
 
From other code:   from play_ringtone import play_ringtone;  play_ringtone()
"""
import math
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path
 
CARD_ID = "Headphones"                           # ALSA card id of the 3.5 mm jack (see `aplay -l`: "card 0: Headphones [...]")
RING_FILE = Path.home() / "phone_ring.wav"
 
# --- the generated ringtone (only used when RING_FILE is missing) ---
SAMPLE_RATE = 44100
RING_SECONDS = 2.0                               # length of the ring itself
TAIL_SECONDS = 0.5                               # silence at the end, so a looping player breathes between rings
TONE_A, TONE_B = 880.0, 1100.0                   # the two warble tones, Hz
WARBLE_HZ = 20.0                                 # how often it switches between them (the "brrring" of an electronic ringer)
VOLUME = 0.6                                     # 0..1; kept well below full scale so the amplifier is not driven hard
 
 
class HeadphonesNotFound(RuntimeError):
    """The headphone sound card is not present."""
 
 
def find_headphones(card_id=CARD_ID):
    """Return the ALSA device string for the headphone jack, or raise HeadphonesNotFound."""
    try:
        listing = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        raise RuntimeError("aplay is not installed (sudo apt install alsa-utils)") from None
    cards = re.findall(r"^card \d+: (\S+) \[", listing.stdout, flags=re.MULTILINE)
    if card_id not in cards:
        raise HeadphonesNotFound(
            "No playback card named %r. Playback cards found: %s. (Run `aplay -l` to check.)"
            % (card_id, ", ".join(cards) or "none"))
    return "plughw:CARD=%s,DEV=0" % card_id      # plughw converts rate / format / channels if the file needs it
 
 
def make_ringtone(path):
    """Write a two-tone warbling ring (stereo, 16 bit, 44.1 kHz) to `path`."""
    total = int((RING_SECONDS + TAIL_SECONDS) * SAMPLE_RATE)
    ring_n = int(RING_SECONDS * SAMPLE_RATE)
    fade_n = int(0.03 * SAMPLE_RATE)             # 30 ms fade in / out, avoids clicks
    half_period = SAMPLE_RATE / (2.0 * WARBLE_HZ)
    phase = 0.0
    frames = bytearray()
    for i in range(total):
        if i < ring_n:
            freq = TONE_A if int(i / half_period) % 2 == 0 else TONE_B
            phase += 2.0 * math.pi * freq / SAMPLE_RATE     # the phase keeps running across the switch: no clicks
            gain = min(1.0, i / fade_n, (ring_n - i) / fade_n)
            sample = int(32767 * VOLUME * gain * math.sin(phase))
        else:
            sample = 0
        frames += struct.pack("<hh", sample, sample)        # same signal on both channels
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))
 
 
def play_ringtone(path=RING_FILE):
    device = find_headphones()                   # raises HeadphonesNotFound before anything else happens
    path = Path(path)
    if not path.exists():
        print("%s not found - generating a ringtone there." % path)
        make_ringtone(path)
    result = subprocess.run(["aplay", "-q", "-D", device, str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("aplay failed on %s: %s" % (device, result.stderr.strip() or "unknown error"))
 
 
if __name__ == "__main__":
    try:
        play_ringtone()
    except (HeadphonesNotFound, RuntimeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(1)
 
