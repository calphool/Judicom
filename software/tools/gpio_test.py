#!/usr/bin/env python3
"""
gpio_test.py - Judicom GPIO Test Utility.
 
Shows five coloured rectangles, one per switch, each with its GPIO number above it.  A rectangle is filled with its colour while
the switch is pressed and black while it is not.  The program closes itself after 30 seconds (Esc or Q closes it sooner).
All five inputs use the Raspberry Pi's internal PULL-UP resistors, so each switch must connect its GPIO pin to GROUND.
 
Run it from an SSH session on the Judicom (no desktop needed):      python3 gpio_test.py
Needs:   sudo apt install python3-pygame python3-gpiozero python3-lgpio     (the Pi OS images usually have gpiozero already)
Tried on a PC with no GPIO:   python3 gpio_test.py --demo --window       (keys 1..5 act as the five switches)
 
Normal switches (NO) light up when the pin is pulled to ground.  Normally-closed switches (NC) are INVERTED on purpose:
they sit closed (pin low) when nobody touches them, so "pressed" means the contacts have just OPENED (pin high).  That way all
the hang-up switches light up together when the handset is in the cradle, and one that disagrees stands out.
If your wiring differs from the pin plan, edit the SWITCHES table below.
 
The screen is mounted sideways (portrait), so the picture is drawn upright in 600 x 1024 and turned 90 degrees onto the panel's
native 1024 x 600.  If it comes out upside-down, run it with --flip.
"""
import argparse
import os
import sys
import time
 
# ---------------------------------------------------------------- edit here -------------------------------------------------
SWITCHES = [
    # (GPIO number [BCM], name shown on screen, "NO" = normally open / "NC" = normally closed)
    (17, "Hang-up switch (NC 1)", "NC"),
    (27, "Hang-up switch (NC 2)", "NC"),
    (22, "Hang-up switch (NO)", "NO"),
    (23, "Frank button", "NO"),
    (24, "Ann button", "NO"),
]
COLORS = [(235, 70, 70), (70, 205, 100), (75, 140, 245), (250, 205, 50), (205, 100, 225)]     # fill colour while pressed
RUN_SECONDS = 30
TITLE = "GPIO Test Utility"
BACKGROUND = (26, 28, 34)
# ------------------------------------------------------------------------------------------------------------------------------
 
 
# ------------------------------------------------------------------ inputs ---------------------------------------------------
class GpiozeroInputs:
    """Reads the pins with gpiozero (internal pull-ups on)."""
 
    def __init__(self, pins):
        from gpiozero import Button
        self._buttons = {p: Button(p, pull_up=True, bounce_time=None) for p in pins}
 
    def is_low(self, pin):
        return self._buttons[pin].is_pressed          # with pull_up=True "pressed" means the pin is pulled LOW
 
    def close(self):
        for b in self._buttons.values():
            b.close()
 
 
class RpiGpioInputs:
    """Same thing with the older RPi.GPIO library."""
 
    def __init__(self, pins):
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for p in pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
 
    def is_low(self, pin):
        return self._gpio.input(pin) == self._gpio.LOW
 
    def close(self):
        self._gpio.cleanup()
 
 
class DemoInputs:
    """No GPIO at all: the keys 1..5 pretend to operate the five switches (held key = switch actuated)."""
 
    def __init__(self, switches):
        self._types = {pin: kind for pin, _, kind in switches}
        self._order = [pin for pin, _, _ in switches]
        self.held = set()
 
    def key(self, index, down):
        if 0 <= index < len(self._order):
            (self.held.add if down else self.held.discard)(self._order[index])
 
    def is_low(self, pin):
        actuated = pin in self.held
        return actuated if self._types[pin] == "NO" else not actuated      # an NC switch is closed (low) until it is actuated
 
    def close(self):
        pass
 
 
def make_inputs(switches, demo):
    if demo:
        return DemoInputs(switches), "demo mode (keys 1-5), no GPIO"
    pins = [p for p, _, _ in switches]
    errors = []
    for name, cls in (("gpiozero", GpiozeroInputs), ("RPi.GPIO", RpiGpioInputs)):
        try:
            return cls(pins), name
        except Exception as exc:                        # noqa: BLE001 - try the next library
            errors.append("%s: %s" % (name, exc))
    sys.exit("Cannot read the GPIO pins.\n  " + "\n  ".join(errors) +
             "\nInstall a library:  sudo apt install python3-gpiozero python3-lgpio")
 
 
def actuated(is_low, kind):
    """True when the switch is being operated.  NO: contacts closed = pin low.  NC: contacts opened = pin high."""
    return is_low if kind == "NO" else not is_low
 
 
# ------------------------------------------------------------------ drawing ---------------------------------------------------
def load_fonts(pygame, scale):
    path = pygame.font.match_font("dejavusans,liberationsans,freesans,arial", bold=True)      # None -> pygame's built-in font
    path_reg = pygame.font.match_font("dejavusans,liberationsans,freesans,arial")
    return {
        "title": pygame.font.Font(path, int(64 * scale)),
        "label": pygame.font.Font(path, int(44 * scale)),
        "name": pygame.font.Font(path_reg, int(28 * scale)),
        "foot": pygame.font.Font(path_reg, int(30 * scale)),
    }
 
 
def draw(pygame, surface, fonts, switches, pressed, remaining, source):
    w, h = surface.get_size()
    surface.fill(BACKGROUND)
    title = fonts["title"].render(TITLE, True, (245, 245, 245))
    surface.blit(title, ((w - title.get_width()) // 2, int(h * 0.02)))
 
    top = int(h * 0.02) + title.get_height() + int(h * 0.02)
    bottom = h - int(h * 0.085)
    n = len(switches)
    row = (bottom - top) / n
    margin = int(w * 0.06)
    for i, ((pin, name, kind), color, on) in enumerate(zip(switches, COLORS, pressed)):
        y = int(top + i * row)
        label = fonts["label"].render("GPIO %d" % pin, True, color)
        surface.blit(label, (margin, y))
        nm = fonts["name"].render(name, True, (170, 175, 185))
        surface.blit(nm, (w - margin - nm.get_width(), y + label.get_height() - nm.get_height() - 2))
        rect = pygame.Rect(margin, y + label.get_height() + 4, w - 2 * margin, int(row - label.get_height() - 4 - row * 0.09))
        pygame.draw.rect(surface, color if on else (0, 0, 0), rect)
        pygame.draw.rect(surface, color, rect, 4)                                 # outline so a black (released) box is still visible
 
    foot = fonts["foot"].render("Closing in %d s     Esc = quit" % max(0, int(remaining + 0.999)), True, (200, 200, 205))
    surface.blit(foot, ((w - foot.get_width()) // 2, h - int(h * 0.075)))
 
 
def to_screen(pygame, screen, logical, rotate, flip):
    """Put the upright (portrait) picture on the native landscape panel.  Pygame rotates counter-clockwise for positive angles."""
    if rotate:
        logical = pygame.transform.rotate(logical, -90 if flip else 90)
    screen.blit(logical, (0, 0))
    pygame.display.flip()
 
 
# ------------------------------------------------------------------- main -----------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Judicom GPIO test utility (closes itself after %d seconds)" % RUN_SECONDS)
    ap.add_argument("--seconds", type=float, default=RUN_SECONDS, help="how long to run (default %d)" % RUN_SECONDS)
    ap.add_argument("--demo", action="store_true", help="no GPIO: keys 1-5 act as the five switches")
    ap.add_argument("--window", action="store_true", help="small window instead of full screen (for a PC), no rotation")
    ap.add_argument("--no-rotate", action="store_true", help="do not turn the picture 90 degrees (normal portrait monitor)")
    ap.add_argument("--flip", action="store_true", help="turn it the other way (use if the picture is upside-down)")
    args = ap.parse_args()
 
    # On the Judicom (no desktop running) SDL has to draw straight to the screen through KMS/DRM.
    if "SDL_VIDEODRIVER" not in os.environ and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
    import pygame
 
    inputs, source = make_inputs(SWITCHES, args.demo)
    print("Inputs: %s.  Pull-ups on for GPIO %s." % (source, ", ".join(str(p) for p, _, _ in SWITCHES)))
    try:
        pygame.display.init()                          # only video and fonts: no audio device is opened
        pygame.font.init()
        if args.window:
            screen = pygame.display.set_mode((450, 768))
        else:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
    except pygame.error as exc:
        inputs.close()
        sys.exit("Cannot open the display: %s\n(Over SSH on the Judicom the user needs to be in the 'video' and 'render' groups, "
                 "and python3-pygame must be the apt package, not the pip one.)" % exc)
 
    nw, nh = screen.get_size()
    rotate = (nw > nh) and not args.no_rotate and not args.window
    logical = pygame.Surface((nh, nw) if rotate else (nw, nh))
    fonts = load_fonts(pygame, logical.get_width() / 600.0)
    print("Screen %dx%d, drawing %dx%d%s." % (nw, nh, logical.get_width(), logical.get_height(), ", turned 90 degrees" if rotate else ""))
 
    clock = pygame.time.Clock()
    start = time.monotonic()
    last = [None] * len(SWITCHES)
    running = True
    while running:
        remaining = args.seconds - (time.monotonic() - start)
        if remaining <= 0:
            break
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_q)):
                running = False
            elif ev.type in (pygame.KEYDOWN, pygame.KEYUP) and args.demo and pygame.K_1 <= ev.key <= pygame.K_9:
                inputs.key(ev.key - pygame.K_1, ev.type == pygame.KEYDOWN)
 
        pressed = [actuated(inputs.is_low(pin), kind) for pin, _, kind in SWITCHES]
        for i, (pin, name, _) in enumerate(SWITCHES):                  # log every change to the terminal as well
            if pressed[i] != last[i]:
                print("[%5.1f s] GPIO %-2d %-24s %s" % (time.monotonic() - start, pin, name, "PRESSED" if pressed[i] else "released"))
                last[i] = pressed[i]
 
        draw(pygame, logical, fonts, SWITCHES, pressed, remaining, source)
        to_screen(pygame, screen, logical, rotate, args.flip)
        clock.tick(30)
 
    print("Finished after %.0f s." % (time.monotonic() - start))
    pygame.quit()
    inputs.close()
 
 
if __name__ == "__main__":
    main()
 
