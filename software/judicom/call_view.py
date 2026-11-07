"""The phone screens: everything except the photos.  Drawn from the state of a machine.Machine.

    view = CallView(buttons)                 # buttons: {"left": Party, "right": Party}, the people shown above the two buttons
    view.draw(surface, machine.mode, machine.party, t)
    view.animated(machine.mode)              # True while something moves: draw every frame; otherwise only when machine.version changes

  LIFTED          "Who would you like to call?" and an arrow down to each button, with the name above it and their picture above
                  that if there is one (the arrows bob gently)
  DIALING         the same as CALLING (the touch-tones play meanwhile; the screen does not change when the call goes out)
  CALLING         the handset on a white panel with rings spreading out, "Calling Ann (daughter)..."
  ONGOING         sound waves from the handset, "Speaking with Ann (daughter)"
  INCOMING        the handset shaking, rings spreading, "Incoming call from / Hannah / granddaughter", "Pick up the handset to answer"
                  (someone not in the contacts file: "Incoming call from / unknown caller: / 312-555-0123")
  NO_ANSWER       "No answer." and who it was
  ENDED           "Call just ended with Ann (daughter)"
  PLEASE_HANG_UP  yellow all over: "Please put the handset back on the phone."
  OUT_OF_ORDER    a cartoon fellow with a cold (judicom/sick_guy.py), and "The phone is not working.  It is being fixed."  (a button pressed while the phone
                  cannot reach the PBX)

With a picture of the person (faces.Faces: "Ann.png" in config.PEOPLE_DIR), DIALING, CALLING, ONGOING and INCOMING show their face
in place of the handset: in a frame, with the same rings spreading out while it rings, a green border while talking, and gently
growing and shrinking with the ring of an incoming call.  No picture, or an unknown caller: the handset, as above.
"""
import math

import pygame

from . import draw
from .config import AMBER, BG, BUTTON_X, DARK, FACE_PX, GREEN, INK, LIFTED_FACE_PX, ROSE, SOFT, YELLOW
from .config import SCREEN_H as H
from .config import SCREEN_W as W
from .machine import Mode

PANEL = (232, 235, 238)
ACCENT = {Mode.DIALING: AMBER, Mode.CALLING: AMBER, Mode.ONGOING: GREEN, Mode.ENDED: ROSE, Mode.INCOMING: AMBER, Mode.NO_ANSWER: ROSE}
ANIMATED = (Mode.LIFTED, Mode.DIALING, Mode.CALLING, Mode.ONGOING, Mode.INCOMING)
WITH_FACE = (Mode.DIALING, Mode.CALLING, Mode.ONGOING, Mode.INCOMING)
FRAME = 12                     # the light frame round a face
PULSE_STEPS = (0, 6, 12, 18)   # how much bigger (pixels) an incoming caller's face gets as it pulses: a few sizes, made once each


def mix(a, b, f):
    return tuple(int(x + (y - x) * f) for x, y in zip(a, b))


# ------------------------------------------------------------------ the handset picture --------------------------------------
_handset = None


def handset_body():
    """The black handset on a transparent 520 x 230 surface (drawn once)."""
    global _handset
    if _handset is None:
        s = pygame.Surface((520, 230), pygame.SRCALPHA)
        black, shine = (22, 22, 26), (84, 86, 96)
        cx, cy = 260, 94
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
        _handset = s
    return _handset


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
                for x, colour in ((cx - 175, (40, 150, 80)), (cx + 175, (40, 100, 200))):
                    pygame.draw.arc(surf, colour, pygame.Rect(x - r, cy - 26 - r, 2 * r, 2 * r), math.radians(60), math.radians(120), 7)


def arrow(surf, cx, tip, color):
    """A fat arrow pointing down, its point at (cx, tip)."""
    pygame.draw.polygon(surf, color, [(cx - 22, tip - 150), (cx + 22, tip - 150), (cx + 22, tip - 70), (cx + 62, tip - 70), (cx, tip),
                                      (cx - 62, tip - 70), (cx - 22, tip - 70)])


# ------------------------------------------------------------------ the screens ----------------------------------------------
class CallView:
    def __init__(self, buttons, faces=None):
        self.buttons = buttons
        self.faces = faces
        self._words_key = self._words = None

    @staticmethod
    def animated(mode):
        return mode in ANIMATED

    def draw(self, surf, mode, party, t):
        if mode == Mode.LIFTED:
            self.draw_lifted(surf, t)
        elif mode == Mode.PLEASE_HANG_UP:
            self.draw_please_hang_up(surf)
        elif mode == Mode.OUT_OF_ORDER:
            self.draw_out_of_order(surf)
        elif mode in ACCENT:
            self.draw_call(surf, mode, party, t)
        else:
            raise ValueError("CallView does not draw %s" % mode)

    def button_face(self, party):
        """The small picture over a button's arrow, or None."""
        return self.faces.get(party.name, LIFTED_FACE_PX) if self.faces is not None else None

    def preload(self):
        """Reads the button pictures now, so that the first lift of the handset does not wait for them."""
        for party in self.buttons.values():
            self.button_face(party)

    def draw_lifted(self, surf, t):
        surf.fill(BG)
        size = 72
        lines = draw.wrap("Who would you like to call?", "bold", size, W - 40)
        pictures = {key: self.button_face(party) for key, party in self.buttons.items()}
        y = (H - int(size * 1.15) * len(lines)) // 2 - 120                    # above the middle: the names and arrows are below
        if any(pictures.values()):
            y -= 70                                                           # and the pictures above them
        for line in lines:
            draw.centered(surf, draw.text(line, "bold", size, INK), y)
            y += int(size * 1.15)
        nudge = int(12 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.1)))     # the arrows bob toward the buttons; all else holds still
        tip = H - 40
        for key, party in self.buttons.items():
            cx = BUTTON_X.get(key)
            if cx is None:
                continue
            arrow(surf, cx, tip + nudge, AMBER)
            ny = tip - 150 - 16 - 62 - 44
            if pictures[key] is not None:
                surf.blit(pictures[key], (cx - LIFTED_FACE_PX // 2, ny - 14 - LIFTED_FACE_PX))
            draw.centered(surf, draw.text(party.name or party.dial, "bold", 62, INK, 255), ny, cx)
            if party.relationship:
                draw.centered(surf, draw.text("(%s)" % party.relationship, "reg", 40, SOFT, 255), ny + 66, cx)

    def draw_please_hang_up(self, surf):
        surf.fill(YELLOW)
        size = 76
        lines = draw.wrap("Please put the handset back on the phone.", "bold", size, W - 60)
        text_h = int(size * 1.15) * len(lines)
        group = 230 + 40 + 150 + 50 + text_h                                  # handset, gap, arrow, gap, words
        y = (H - group) // 2
        draw_handset(surf, W // 2, y + 115)
        arrow(surf, W // 2, y + 230 + 40 + 150, DARK)
        y += 230 + 40 + 150 + 50
        for line in lines:
            draw.centered(surf, draw.text(line, "bold", size, DARK), y)
            y += int(size * 1.15)

    def face(self, mode, party, size=FACE_PX):
        """The person's picture for this screen, or None (then the handset is drawn)."""
        if self.faces is None or mode not in WITH_FACE or not (party and party.name):
            return None
        return self.faces.get(party.name, size)

    def draw_out_of_order(self, surf):
        """Calm, not alarming: the same teal, a cartoon fellow with a cold (the phone is poorly), and plain words."""
        from .sick_guy import sick_guy
        surf.fill(BG)
        tmp = pygame.Surface((W, 700), pygame.SRCALPHA)
        y = draw.block(tmp, "The phone is not working.", "bold", 72, INK, 0)
        y = draw.block(tmp, "It is being fixed.", "reg", 52, SOFT, y + 24)
        words = tmp.subsurface((0, 0, W, max(1, min(y, tmp.get_height())))).copy()
        size = 460
        group = size + 20 + words.get_height()
        y0 = max(24, (H - group) // 2 - 20)
        surf.blit(sick_guy(size), ((W - size) // 2, y0))
        surf.blit(words, (0, y0 + size + 20))

    def draw_call(self, surf, mode, party, t):
        surf.fill(BG)
        accent = ACCENT[mode]
        words = self.words(mode, party)
        face = self.face(mode, party)
        if face is not None:
            self.draw_face_call(surf, mode, party, t, accent, words)
            return
        group = 290 + 56 + words.get_height()                                 # handset panel + gap + words, centred as one block
        y0 = max(24, (H - group) // 2 - 30)
        panel = pygame.Rect(40, y0, W - 80, 290)
        if mode in (Mode.DIALING, Mode.CALLING, Mode.INCOMING):               # rings spreading out from the panel
            for k in range(3):
                phase = (t * 0.7 + k / 3.0) % 1.0
                grow = int(phase * 46)
                pygame.draw.rect(surf, mix(accent, BG, phase), panel.inflate(2 * grow, 2 * grow), 5, border_radius=34 + grow)
        pygame.draw.rect(surf, PANEL, panel, border_radius=34)
        if mode == Mode.ONGOING:
            pygame.draw.rect(surf, accent, panel, 8, border_radius=34)
            draw_handset(surf, panel.centerx, panel.centery, waves=0.5 + 0.5 * math.sin(t * 3.2))
        elif mode == Mode.INCOMING:
            shaking = (t % 2.0) < 1.2                                         # shakes with the ring, rests in between
            draw_handset(surf, panel.centerx, panel.centery, angle=9 * math.sin(t * 2 * math.pi * 6) if shaking else 0.0)
        else:
            draw_handset(surf, panel.centerx, panel.centery)
        surf.blit(words, (0, panel.bottom + 56))
        if mode == Mode.INCOMING:
            draw.centered(surf, draw.text("Pick up the handset to answer", "reg", 36, SOFT, W - 60), H - 90)

    def draw_face_call(self, surf, mode, party, t, accent, words):
        """draw_call with the person's picture in place of the handset."""
        side = FACE_PX + 2 * FRAME
        group = side + 48 + words.get_height()
        y0 = max(24, (H - group) // 2 - (40 if mode == Mode.INCOMING else 10))     # incoming: room for the hint at the bottom
        panel = pygame.Rect((W - side) // 2, y0, side, side)
        if mode in (Mode.DIALING, Mode.CALLING, Mode.INCOMING):
            for k in range(3):
                phase = (t * 0.7 + k / 3.0) % 1.0
                grow = int(phase * 46)
                pygame.draw.rect(surf, mix(accent, BG, phase), panel.inflate(2 * grow, 2 * grow), 5, border_radius=34 + grow)
        grow = 0
        if mode == Mode.INCOMING and (t % 2.0) < 1.2:                          # with the ring, like the handset's shaking
            wave = abs(math.sin(t * 2 * math.pi * 1.5))
            grow = PULSE_STEPS[min(len(PULSE_STEPS) - 1, int(wave * len(PULSE_STEPS)))]
        frame = panel.inflate(grow, grow)
        pygame.draw.rect(surf, PANEL, frame, border_radius=34)
        if mode == Mode.ONGOING:
            pygame.draw.rect(surf, accent, frame, 8, border_radius=34)
        img = self.face(mode, party, FACE_PX + grow) or self.face(mode, party)
        surf.blit(img, img.get_rect(center=frame.center))
        surf.blit(words, (0, panel.bottom + 48))
        if mode == Mode.INCOMING:
            draw.centered(surf, draw.text("Pick up the handset to answer", "reg", 36, SOFT, W - 60), H - 90)

    def words(self, mode, party):
        """The words under the handset picture, as a transparent surface (kept until the mode or the party changes)."""
        if mode == Mode.DIALING:
            mode = Mode.CALLING                                               # same words: nothing jumps when the call goes out
        key = (mode, party)
        if key != self._words_key:
            tmp = pygame.Surface((W, 560), pygame.SRCALPHA)
            label = party.label if party else "someone"
            if mode == Mode.CALLING:
                y = draw.block(tmp, "Calling %s..." % label, "bold", 66, INK, 0)
            elif mode == Mode.ONGOING:
                y = draw.block(tmp, "Speaking with %s" % label, "bold", 66, INK, 0)
            elif mode == Mode.ENDED:
                y = draw.block(tmp, "Call just ended with %s" % label, "bold", 66, SOFT, 0)
            elif mode == Mode.NO_ANSWER:
                y = draw.block(tmp, "No answer.", "bold", 84, INK, 0)
                y = draw.block(tmp, label, "reg", 46, SOFT, y + 4)
            else:                                                             # INCOMING
                y = draw.centered(tmp, draw.text("Incoming call from", "reg", 44, SOFT), 0)
                if party and party.name:
                    y = draw.centered(tmp, draw.text(party.name, "bold", 92, INK, W - 60), y + 2)
                    if party.relationship:
                        y = draw.centered(tmp, draw.text(party.relationship, "reg", 52, AMBER, W - 60), y)
                else:                                                         # not in the contacts file: it rings all the same
                    y = draw.centered(tmp, draw.text("unknown caller" + (":" if party and party.dial else ""), "bold", 60, INK,
                                                     W - 60), y + 6)
                    if party and party.dial:
                        y = draw.centered(tmp, draw.text(party.dial, "bold", 76, AMBER, W - 60), y + 6)
            self._words = tmp.subsurface((0, 0, W, max(1, min(y, tmp.get_height())))).copy()
            self._words_key = key
        return self._words
