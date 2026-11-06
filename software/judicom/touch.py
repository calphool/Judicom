"""The touch screen.  Nothing here needs extra packages: it reads /dev/input itself.

    taps = Taps(log)            # finds the panel; without one it just never reports a tap
    taps.poll()                 # True once each time a finger comes down (call it often)

The panel is found by what it does (it reports finger positions), not by its name.  Its corners were measured on 2026-11-05: its x
runs down Judi's upright picture and its y runs right to left, the same quarter turn as the picture (judicom/display.py).
"""
import os
import re
import struct
from pathlib import Path

from .config import SCREEN_H as H
from .config import SCREEN_W as W

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, ABS_MT_SLOT, ABS_MT_X, ABS_MT_Y, ABS_MT_ID = 0x00, 0x01, 0x2f, 0x35, 0x36, 0x39
BTN_TOUCH = 0x14a
EVENT = "llHHi"                    # struct input_event: time (two longs), type, code, value
EVENT_SIZE = struct.calcsize(EVENT)


def find_touch_screen(devices="/proc/bus/input/devices"):
    """(/dev/input/eventN, its name) of the first device that reports finger positions, or (None, None)."""
    for block in Path(devices).read_text().split("\n\n"):
        abs_bits = re.search(r"^B: ABS=([0-9a-f ]+)$", block, re.M)
        event = re.search(r"\bevent\d+\b", block)
        if not (abs_bits and event):
            continue
        bits, word = 0, struct.calcsize("l") * 8                     # words of the kernel's long, leading zeros left out
        for w in abs_bits.group(1).split():                          # most significant word first
            bits = (bits << word) | int(w, 16)
        if bits >> ABS_MT_X & 1 and bits >> ABS_MT_Y & 1:
            name = re.search(r'^N: Name="(.*)"$', block, re.M)
            return "/dev/input/" + event.group(0), name.group(1) if name else "?"
    return None, None


def axis_max(fd, code, default=2048):
    import fcntl                # here, not at the top: the program also runs on Windows PCs, which do not have it

    buf = bytearray(24)
    try:
        fcntl.ioctl(fd, 0x80184540 + code, buf)                      # EVIOCGABS(code): value, min, max, fuzz, flat, resolution
        return struct.unpack("6i", buf)[2] or default
    except OSError:
        return default


class Touches:
    """Reads the panel without blocking.  poll() -> {finger: (x, y) on the upright picture}, the fingers down now."""

    def __init__(self, path, flip=False):
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.max_x, self.max_y = axis_max(self.fd, ABS_MT_X), axis_max(self.fd, ABS_MT_Y)
        self.flip = flip
        self.slot = 0
        self.raw = {}                     # slot -> [raw x, raw y]
        self.down = {}                    # slot -> True while that finger is on the glass
        self._buf = b""

    def to_screen(self, rx, ry):
        x, y = (self.max_y - ry) * W / self.max_y, rx * H / self.max_x
        return (W - x, H - y) if self.flip else (x, y)

    def poll(self):
        try:
            self._buf += os.read(self.fd, EVENT_SIZE * 256)
        except BlockingIOError:
            pass
        while len(self._buf) >= EVENT_SIZE:
            _, _, typ, code, val = struct.unpack(EVENT, self._buf[:EVENT_SIZE])
            self._buf = self._buf[EVENT_SIZE:]
            if typ == EV_ABS and code == ABS_MT_SLOT:
                self.slot = val
            elif typ == EV_ABS and code == ABS_MT_ID:
                self.down[self.slot] = val >= 0
            elif typ == EV_ABS and code in (ABS_MT_X, ABS_MT_Y):
                self.raw.setdefault(self.slot, [None, None])[code == ABS_MT_Y] = val
            elif typ == EV_KEY and code == BTN_TOUCH and val == 0:
                self.down = {}                                       # every finger off (for panels that do not send the ids)
        return {s: self.to_screen(*self.raw[s]) for s, d in self.down.items() if d and None not in self.raw.get(s, (None,))}

    def close(self):
        os.close(self.fd)


class Taps:
    def __init__(self, log=None, flip=False, devices="/proc/bus/input/devices", open_panel=Touches):
        self.log = log or (lambda msg: None)
        self.panel, self.down = None, False
        try:
            path, name = find_touch_screen(devices)
            if path is None:
                self.log("(no touch screen found: a message goes away with a button or the handset only)")
                return
            self.panel = open_panel(path, flip=flip)
            self.log("touch screen: %s (%s)" % (name, path))
        except OSError as exc:
            self.log("(cannot read the touch screen: %s)" % exc)

    def poll(self):
        if self.panel is None:
            return False
        try:
            down = bool(self.panel.poll())
        except OSError as exc:                          # the panel came loose: the phone carries on without it
            self.log("(the touch screen stopped: %s)" % exc)
            self.close()
            return False
        tapped = down and not self.down
        self.down = down
        return tapped

    def close(self):
        if self.panel is not None:
            self.panel.close()
            self.panel = None
