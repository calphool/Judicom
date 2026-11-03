"""Settings that other parts of the program share.  Change a value here, nowhere else."""
import os
from pathlib import Path

# Where the family photos live (the twice-a-day NAS sync fills this folder).
# For a test on another computer:  JUDICOM_PHOTOS=/some/folder python3 -m judicom.photos
PHOTO_DIR = Path(os.environ.get("JUDICOM_PHOTOS", "/home/joe/photos"))

# Which files count as pictures (capital letters do not matter).
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".bmp")

# ---- the screen -------------------------------------------------------------------------------------------------------------
# Everything is drawn upright at this size.  The panel is mounted sideways, so judicom/display.py turns the picture 90 degrees.
SCREEN_W, SCREEN_H = 600, 1024

# ---- the photo screen -------------------------------------------------------------------------------------------------------
PHOTO_SECONDS = 15.0          # how long each picture stays
FADE_SECONDS = 0.8            # cross-fade from one picture to the next
MAX_PHOTO_PX = 1400           # pictures are shrunk to this (longest side) when loaded; the Pi has little memory
CAPTION_GAP = 14              # clear space kept between a photo and its caption band when there is room for it (pixels)
MIN_SHRINK = 0.82             # to keep clear of the caption a photo may be made up to this much smaller than usual (0.82 = 18 % smaller);
                              # a photo that would still not fit is left at that size and the caption covers the least possible of it

# ---- colours ----------------------------------------------------------------------------------------------------------------
BG = (36, 66, 74)             # the teal of the boot splash
INK, SOFT = (246, 246, 240), (182, 202, 206)
