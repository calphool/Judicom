#!/usr/bin/env python3
"""touch_draw.py - draw on the Judicom's screen with your fingers (a check of the touch screen, and a toy).

    python3 tools/touch_draw.py              on the Judicom (over SSH is fine)
    python3 tools/touch_draw.py --window     on a PC: draw with the mouse; 1 / 2 = the buttons, l = the handset

Every finger draws its own line (the panel follows up to 6).  Along the top: colour dots to pick from, and Clear.
It ends when either button is pressed or the handset is lifted, after IDLE_MINUTES without a touch, or with Ctrl-C.

Only one program can have the screen and the switches, so on the Judicom it stops the phone program (judicom-phone) first
and ALWAYS starts it again when it ends, however it ends (sudo -n: allowed by /etc/sudoers.d/judicom).  While it runs,
Judi's phone does not work, which is why it gives up by itself when nobody is drawing.

The touch screen is found by what it does (it reports finger positions), not by its name.  Its corners were measured on
2026-11-05: the panel's x runs down Judi's upright picture and its y runs right to left, the same quarter turn as the picture
(judicom/display.py), so a point is turned the same way before it is drawn.  No extra packages: it reads /dev/input itself.
"""
import argparse
import fcntl
import os
import re
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))       # the software folder, for the judicom package

import pygame                                                      # noqa: E402

from judicom.config import SCREEN_H as H                           # noqa: E402
from judicom.config import SCREEN_W as W                           # noqa: E402

IDLE_MINUTES = 5.0
SERVICE = "judicom-phone"
BG = (250, 248, 240)
COLOURS = [(30, 30, 30), (220, 50, 50), (240, 200, 30), (60, 170, 80), (50, 110, 220), (150, 80, 200)]
BAR = 110                          # the strip along the top with the colour dots and Clear
PEN = 9                            # half the line's width, pixels

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, ABS_MT_SLOT, ABS_MT_X, ABS_MT_Y, ABS_MT_ID = 0x00, 0x01, 0x2f, 0x35, 0x36, 0x39
BTN_TOUCH = 0x14a
EVENT = "llHHi"                    # struct input_event: time (two longs), type, code, value
EVENT_SIZE = struct.calcsize(EVENT)


# ------------------------------------------------------------------ the touch screen -----------------------------------------
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


class MouseTouches:
    """--window on a PC: the mouse is one finger."""

    def __init__(self, display):
        self.display = display

    def poll(self):
        if not pygame.mouse.get_pressed()[0]:
            return {}
        mx, my = pygame.mouse.get_pos()
        sw, sh = self.display.screen.get_size()
        return {0: (mx * W / sw, my * H / sh)}

    def close(self):
        pass


# ------------------------------------------------------------------ the phone program --------------------------------------
def service_active():
    return subprocess.run(["systemctl", "is-active", "--quiet", SERVICE]).returncode == 0


def service(action):
    r = subprocess.run(["sudo", "-n", "systemctl", action, SERVICE], capture_output=True, text=True)
    if r.returncode:
        print("could not %s %s: %s" % (action, SERVICE, (r.stderr or r.stdout).strip()), flush=True)
    return r.returncode == 0


# ------------------------------------------------------------------ the drawing ---------------------------------------------
def swatches():
    """[(rect, colour or "clear")] along the top."""
    out, size, gap = [], 62, 10
    x = 20
    for c in COLOURS:
        out.append((pygame.Rect(x, (BAR - size) // 2, size, size), c))
        x += size + gap
    out.append((pygame.Rect(x, (BAR - size) // 2, W - 20 - x, size), "clear"))
    return out


def draw_bar(surf, colour, font):
    pygame.draw.rect(surf, (225, 222, 212), (0, 0, W, BAR))
    for rect, c in swatches():
        if c == "clear":
            pygame.draw.rect(surf, (255, 255, 255), rect, border_radius=14)
            pygame.draw.rect(surf, (120, 120, 120), rect, 3, border_radius=14)
            label = font.render("Clear", True, (60, 60, 60))
            surf.blit(label, label.get_rect(center=rect.center))
        else:
            pygame.draw.circle(surf, c, rect.center, rect.w // 2)
            if c == colour:
                pygame.draw.circle(surf, (255, 255, 255), rect.center, rect.w // 2 - 6, 4)


def run(display, touches, controls, idle_minutes, log):
    font = pygame.font.Font(None, 40)
    canvas = pygame.Surface((W, H - BAR))
    canvas.fill(BG)
    colour, last, idle_from = COLOURS[0], {}, time.monotonic()
    clock = pygame.time.Clock()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return "window closed"
            if ev.type == pygame.KEYDOWN:
                key = ev.unicode.lower()
                if key in ("q", "\x1b"):
                    return "q"
                controls.key(key) if hasattr(controls, "key") else None
        for event in controls.poll():
            if event[0] == "button":
                return "%s button" % event[1]
            if event[0] == "lifted":
                return "handset lifted"
        fingers = touches.poll()
        if fingers:
            idle_from = time.monotonic()
        for f, (x, y) in fingers.items():
            if y < BAR:
                if f not in last:                                    # a tap on the strip (not a line wandering into it)
                    for rect, c in swatches():
                        if rect.collidepoint(x, y):
                            if c == "clear":
                                canvas.fill(BG)
                            else:
                                colour = c
                last[f] = None
                continue
            p = (int(x), int(y - BAR))
            if last.get(f) is not None:
                pygame.draw.line(canvas, colour, last[f], p, PEN * 2)
            pygame.draw.circle(canvas, colour, p, PEN)
            last[f] = p
        last = {f: p for f, p in last.items() if f in fingers}
        if time.monotonic() - idle_from > idle_minutes * 60:
            return "nobody drew for %g minutes" % idle_minutes
        display.logical.blit(canvas, (0, BAR))
        draw_bar(display.logical, colour, font)
        display.present()
        clock.tick(60)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw on the Judicom's screen with your fingers.  A button or the handset ends it.")
    ap.add_argument("--window", action="store_true", help="on a PC: a window, the mouse draws, keys 1 / 2 / l are the switches")
    ap.add_argument("--flip", action="store_true", help="if the phone program runs with --flip (the picture turned the other way)")
    ap.add_argument("--idle-minutes", type=float, default=IDLE_MINUTES, help="end after this long without a touch (%(default)s)")
    args = ap.parse_args(argv)
    log = lambda msg: print(msg, flush=True)                          # noqa: E731

    def stop(signum, frame):
        raise SystemExit("stopped (signal %d)" % signum)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)                               # the SSH connection went away: still clean up

    from judicom.display import Display
    from judicom.inputs import make_controls
    restart = False
    controls = touches = display = None
    try:
        if not args.window:
            path, name = find_touch_screen()
            if path is None:
                sys.exit("No touch screen found (nothing in /proc/bus/input/devices reports finger positions).")
            log("touch screen: %s (%s)" % (name, path))
            if service_active():
                log("stopping %s (it will be started again at the end)" % SERVICE)
                restart = True
                if not service("stop"):
                    sys.exit(1)
                time.sleep(1.0)                                      # let it give back the screen and the pins
        display = Display(window=args.window, flip=args.flip)
        controls, source = make_controls(demo=args.window, log=log)
        touches = MouseTouches(display) if args.window else Touches(path, flip=args.flip)
        log("draw away.  A button or lifting the handset ends it (switches: %s)." % source)
        why = run(display, touches, controls, args.idle_minutes, log)
        log("ended: %s" % why)
    finally:
        for thing in (touches, controls):
            try:
                thing and thing.close()
            except Exception:                                        # noqa: BLE001 - cleaning up: carry on regardless
                pass
        if display:
            display.close()
        if restart:
            log("starting %s again" % SERVICE)
            service("start")


if __name__ == "__main__":
    main()
