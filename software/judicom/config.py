"""Settings that other parts of the program share.  Change a value here, nowhere else."""
import os
from pathlib import Path

# Where the family photos live (the twice-a-day NAS sync fills this folder).
# For a test on another computer:  JUDICOM_PHOTOS=/some/folder python3 -m judicom.photos
PHOTO_DIR = Path(os.environ.get("JUDICOM_PHOTOS", "/home/joe/photos"))

# Which files count as pictures (capital letters do not matter).
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".bmp")
