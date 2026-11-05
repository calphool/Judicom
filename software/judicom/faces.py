"""The pictures of the people in the caller list, for the call screens.

    faces = Faces()                          # the folder is config.PEOPLE_DIR (filled from the NAS by judicom.sync)
    faces.get("Ann", 400)                    # a 400 x 400 surface with rounded corners, or None (no picture for Ann)

"Ann.png", "ann.JPG", "Aunt Sue.jpg" or "Aunt_Sue.jpg" all match (capitals and _ for spaces do not matter).  A picture that is not
square is cropped from the middle.  The folder is looked at again at most every RESCAN seconds, so new pictures show up without a
restart; a picture that cannot be read is skipped (and said once in the log), and the call screen then shows the handset as before.
"""
import os
import time

from . import config

RESCAN = 30.0
RADIUS = 34                                  # the corners, the same as the call screen's panel


def key(name):
    """'Aunt_Sue' / 'aunt sue' / ' Aunt  Sue ' -> 'aunt sue'."""
    return " ".join(name.replace("_", " ").split()).casefold()


def find(folder):
    """{key(name): path} of the pictures in folder."""
    found = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return found
    for n in names:
        stem, ext = os.path.splitext(n)
        if n.startswith(".") or ext.lower() not in config.PEOPLE_EXTS:
            continue
        path = os.path.join(folder, n)
        if os.path.isfile(path):
            found.setdefault(key(stem), path)
    return found


def rounded(img, size, radius=RADIUS):
    """img cropped to a square from its middle, scaled to size x size, with rounded corners (transparent outside them)."""
    import pygame
    w, h = img.get_size()
    side = min(w, h)
    square = img.subsurface(((w - side) // 2, (h - side) // 2, side, side))
    flat = pygame.Surface((side, side), pygame.SRCALPHA)           # 32-bit with alpha whatever the file was (smoothscale needs it)
    flat.blit(square, (0, 0))
    out = pygame.transform.smoothscale(flat, (size, size))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


class Faces:
    def __init__(self, folder=None, log=None, clock=time.monotonic):
        self.folder = str(config.PEOPLE_DIR if folder is None else folder)
        self.log = log or (lambda msg: None)
        self.clock = clock
        self._paths, self._seen_at = {}, None
        self._images = {}                    # (path, mtime, size) -> surface
        self._bad = set()                    # (path, mtime) that could not be read

    def path(self, name):
        """The picture file for name, or None."""
        if not name:
            return None
        now = self.clock()
        if self._seen_at is None or now - self._seen_at >= RESCAN:
            self._paths, self._seen_at = find(self.folder), now
        return self._paths.get(key(name))

    def get(self, name, size=config.FACE_PX):
        path = self.path(name)
        if path is None:
            return None
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            return None
        k = (path, mtime, size)
        if k not in self._images:
            if (path, mtime) in self._bad:
                return None
            import pygame
            try:
                img = pygame.image.load(path)
                self._images = {x: v for x, v in self._images.items() if x[0] != path or x[1] == mtime}   # an older copy: gone
                self._images[k] = rounded(img, size)
            except (pygame.error, OSError, ValueError) as exc:
                self._bad.add((path, mtime))
                self.log("(the picture %s cannot be shown: %s)" % (os.path.basename(path), exc))
                return None
        return self._images[k]
