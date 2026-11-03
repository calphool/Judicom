"""Where a photo goes on the 600 x 1024 screen.  Plain arithmetic - no pygame - so it is tested everywhere."""
from .config import CAPTION_GAP, MIN_SHRINK
from .config import SCREEN_H as H
from .config import SCREEN_W as W


def place_photo(iw, ih, band_y=None):
    """Where the photo goes: (x, y, width, height).  `band_y` is the top of the caption band, or None if the picture has no caption.

    No caption:   as large as it fits, in the middle of the screen.
    With caption: the photo goes in the space above the band, in the middle of it, so the caption covers nothing of it.
                  If it does not fit there, it is made smaller - but by no more than MIN_SHRINK allows - and if it is still too tall it is
                  moved up as far as needed (to the top of the screen at the most), so the caption covers as little of it as possible.
    """
    full = min(W / float(iw), H / float(ih))                     # the usual size: the whole photo, as large as the screen allows
    fit = full
    if band_y is not None:
        room = band_y - CAPTION_GAP                              # height of the free space above the band
        fit = max(min(full, room / float(ih)), full * MIN_SHRINK)
    fw, fh = max(1, int(iw * fit)), max(1, int(ih * fit))
    x = (W - fw) // 2
    if band_y is None:
        y = (H - fh) // 2
    elif fh <= band_y - CAPTION_GAP:
        y = (band_y - CAPTION_GAP - fh) // 2                     # fits above the band: in the middle of the space above it
    else:
        y = max(0, band_y - fh)                                  # bottom of the photo meets the band, or the top of the screen at most
    return x, y, fw, fh
