"""The family-photo screen: one picture at a time, cross-faded, with its caption in a band near the bottom.

The picture is shown whole (never cropped) on a blurred, darkened copy of itself, so tall and wide pictures both fill the 600 x 1024
screen.  With a caption, the photo is placed in the space above the caption band (layout.py) so the words cover as little as possible.  The order comes from photos.PhotoDeck (shuffled rounds); the caption from the picture's .meta file (see photos.py).

A program calls `view.tick()` often and draws `view.draw(surface)` whenever `view.needs_redraw()` says so: while a cross-fade runs, when
the picture changes, and once more after a fade so that the finished picture replaces the last half-faded frame.  (Without that last frame
the old picture stays faintly visible under the new one.)  `view.version` changes whenever the picture changes.  Time comes from
`clock` (time.monotonic), which tests replace with a fake.
"""
import time

import pygame

from . import draw
from .config import BG, FADE_SECONDS, INK, MAX_PHOTO_PX, PHOTO_SECONDS, SOFT
from .config import SCREEN_H as H
from .config import SCREEN_W as W
from .layout import place_photo
from .photos import Caption, load_caption


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


def compose_picture(img, band_y=None):
    """The 600 x 1024 picture without its caption: a blurred, darkened copy as the backdrop and the photo fitted whole on top of it.
    `band_y` (where the caption band starts, if there is one) makes the photo move up out of the caption's way: see layout.place_photo."""
    iw, ih = img.get_size()
    img32 = pygame.Surface((iw, ih), 0, 32)                      # smoothscale only works on 24 / 32 bit surfaces
    img32.blit(img, (0, 0))
    img = img32
    back = pygame.transform.smoothscale(pygame.transform.smoothscale(img, (W // 24, H // 24)), (W, H))
    shade = pygame.Surface((W, H))
    shade.set_alpha(120)
    back.blit(shade, (0, 0))
    x, y, fw, fh = place_photo(iw, ih, band_y)
    back.blit(pygame.transform.smoothscale(img, (fw, fh)), (x, y))
    return back.convert()


def compose_caption(caption):
    """The caption band (a see-through dark strip with the words on it) and the y where it goes; None if there is no caption."""
    lines = []                                                   # (kind, size, color, string)
    if caption.people:
        lines += [("bold", 54, INK, s) for s in draw.wrap(caption.people_text, "bold", 54, W - 70)]
    if caption.relationship:
        lines += [("reg", 38, INK, s) for s in draw.wrap(caption.relationship_text, "reg", 38, W - 70)]
    if caption.taken:
        taken, ago = caption.taken_text, caption.years_ago()   # just the date: "Taken" could sound like someone was taken away
        both = "%s (%s)" % (taken, ago) if ago else taken
        if draw.get_font("reg", 34).size(both)[0] <= W - 70:
            lines += [("reg", 34, SOFT, both)]
        else:                                                    # too long for one line: "(7 years ago)" on its own beneath
            lines += [("reg", 34, SOFT, s) for s in draw.wrap(taken, "reg", 34, W - 70)]
            if ago:
                lines += [("reg", 34, SOFT, "(%s)" % ago)]
    if not lines:
        return None
    height = sum(int(size * 1.18) for _, size, _, _ in lines) + 36
    band = pygame.Surface((W, height), pygame.SRCALPHA)
    band.fill((0, 0, 0, 170))
    y = 18
    for kind, size, color, string in lines:
        draw.centered(band, draw.text(string, kind, size, color), y)
        y += int(size * 1.18)
    return band.convert_alpha(), H - 36 - height


class Photo:
    def __init__(self, path, surface, caption, band=None, band_y=0):
        self.path, self.surface, self.caption = path, surface, caption
        self.band, self.band_y = band, band_y                    # the caption strip and where it goes (None: no caption)

    def draw(self, surf, picture_alpha=255, caption_alpha=255):
        """Draw the picture, then its caption, each with its own see-through-ness (0-255)."""
        self.surface.set_alpha(picture_alpha)
        surf.blit(self.surface, (0, 0))
        self.surface.set_alpha(255)
        if self.band is not None and caption_alpha > 0:
            self.band.set_alpha(caption_alpha)
            surf.blit(self.band, (0, self.band_y))
            self.band.set_alpha(255)


def load_photo(path):
    """Read one picture and its caption file and compose the finished screen.  Raises if the picture cannot be read."""
    caption = load_caption(path)
    made = compose_caption(caption)                              # first: how much room the caption needs decides where the photo goes
    band, band_y = made if made else (None, None)
    return Photo(path, compose_picture(load_image(path), band_y), caption, band, band_y or 0)


class PhotoView:
    def __init__(self, deck, seconds=PHOTO_SECONDS, fade=FADE_SECONDS, loader=load_photo, log=None, clock=time.monotonic,
                 retry_seconds=10.0):
        self.deck = deck
        self.seconds, self.fade, self.loader, self.clock = seconds, fade, loader, clock
        self.log = log or (lambda msg: None)
        self.retry_seconds = retry_seconds
        self.current = None              # the Photo on the screen (None: there is nothing to show)
        self.previous = None             # the Photo being faded out
        self.since = 0.0                 # when the current one appeared
        self.shown = 0                   # how many pictures have been shown (a state machine can count "5, then the weather")
        self.version = 0                 # changes whenever the picture changes
        self._dirty = True               # the screen does not show the current state yet
        self._retry_at = 0.0

    # ---- control
    def start(self):
        """The screen is becoming visible: begin with a fresh picture (no fade from an old one)."""
        self.previous = None
        self._advance(fade=False)

    def next(self):
        """Go to the next picture now."""
        self._advance(fade=True)

    def tick(self):
        """Call often.  Moves to the next picture when the time is up, and retries when the folder had nothing."""
        now = self.clock()
        if self.current is None:
            if now >= self._retry_at:
                self._advance(fade=False)
            return
        if now - self.since >= self.seconds:
            self._advance(fade=True)
        elif self.previous is not None and now - self.since >= self.fade:
            self.previous = None                                       # the fade is over: let the old picture's memory go

    # ---- drawing
    def animated(self):
        return self.previous is not None and self.clock() - self.since < self.fade

    def needs_redraw(self):
        """True when the screen should be drawn again.  Stays true after a half-faded frame until a finished one has been drawn."""
        return self._dirty or self.animated()

    def draw(self, surf):
        cur = self.current
        self._dirty = False
        if cur is None:
            surf.fill(BG)
            y = draw.block(surf, "No photos yet", "bold", 64, INK, H // 2 - 80)
            draw.block(surf, "Looking in " + str(self.deck.folder), "reg", 30, SOFT, y + 10, W - 80)
            return
        elapsed = self.clock() - self.since
        if self.previous is not None and elapsed < self.fade:
            self._dirty = True                                           # a half-faded frame is never the last word
            f = max(0.0, elapsed) / self.fade                            # 0 .. 1 through the fade
            self.previous.draw(surf, 255, int(255 * max(0.0, 1.0 - 2.0 * f)))   # old caption fades out in the first half ...
            cur.draw(surf, int(255 * f), int(255 * max(0.0, 2.0 * f - 1.0)))   # ... the picture cross-fades all the way, the new caption fades in after
        else:
            cur.draw(surf)

    # ---- inside
    def _load_next(self):
        tried = set()
        while True:
            path = self.deck.next()
            if path is None or path in tried:            # nothing in the folder, or we have come round to a picture that already failed
                return None
            tried.add(path)
            try:
                return self.loader(path)
            except Exception as exc:                     # noqa: BLE001 - one bad file must not stop the show
                self.log("skipping %s: %s" % (path.name, exc))

    def _advance(self, fade):
        photo = self._load_next()
        now = self.clock()                               # after loading: the 15 seconds start when the picture is really on the screen
        self._dirty = True
        if photo is None:
            if self.current is not None:                 # only a change counts: a retry that finds nothing again redraws nothing
                self.log("no picture to show in %s" % self.deck.folder)
                self.version += 1
            self.current = self.previous = None
            self._retry_at = now + self.retry_seconds
            return
        self.version += 1
        self.previous = self.current if fade else None
        self.current = photo
        self.since = now
        self.shown += 1
        cap = photo.caption
        self.log("%s%s" % (photo.path.name, "  [%s]" % " | ".join(p for p in (cap.people_text, cap.relationship_text, cap.taken_text) if p)
                           if cap else "  [no caption]"))
