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

# ---- the phone: switches ----------------------------------------------------------------------------------------------------
# GPIO numbers (BCM).  Every switch connects its pin to ground; the Pi's internal pull-ups are used.  Same pins as tests/gpio_test.py.
HOOK_NC_PINS = (17, 27)       # the hook switch's two normally-closed contacts
HOOK_NO_PINS = (22,)          # ... and its normally-open contact.  The three vote, so one bad contact cannot fake a lift or a hang-up.
HOOK_PRESSED_ON_HOOK = True   # True: the handset resting in the cradle presses the switch.  False if it is the other way round.
BUTTON_PINS = {"left": 23, "right": 24}
LIFT_SETTLE = 0.10            # the handset counts as lifted after it has been up this long (seconds)
HANG_UP_SETTLE = 0.50         # ... and as hung up after it has been down this long, so a jostle in the cradle does not end a call
BUTTON_SETTLE = 0.05          # a button press counts after this long (contact bounce)

# ---- the phone: who the buttons call ----------------------------------------------------------------------------------------
# "dial" is what is sent to the PBX (an extension or a number).
BUTTONS = {
    "left": {"name": "Clark", "relationship": "husband", "dial": "clark"},
    "right": {"name": "Amy", "relationship": "daughter", "dial": "amy"},
}

# ---- the phone: timing ------------------------------------------------------------------------------------------------------
LIFTED_SECONDS = 60.0         # handset up, no button pressed: after this long the yellow "please hang up" screen (dial tone stops)
RING_OUT_SECONDS = 30.0       # calling someone who does not pick up: give up after this long -> "No answer."
NO_ANSWER_SECONDS = 10.0      # the "No answer." screen
CALL_ENDED_SECONDS = 10.0     # the "Call just ended with ..." screen

# ---- the call screens -------------------------------------------------------------------------------------------------------
BUTTON_X = {"left": SCREEN_W // 2 - 129, "right": SCREEN_W // 2 + 129}   # screen x right above each button (37 mm apart; 600 px = 86 mm)
AMBER, GREEN, ROSE = (255, 196, 64), (112, 214, 144), (240, 150, 150)
YELLOW, DARK = (255, 214, 10), (30, 30, 30)    # the "please hang up" screen

# ---- sounds -----------------------------------------------------------------------------------------------------------------
# The dial tone goes to the handset (the USB sound device, found by itself); the ringer to the Pi's headphone jack -> LM386 -> speaker.
RINGER_CARD = "Headphones"    # ALSA card id of the 3.5 mm jack (see `aplay -l`)
DIAL_TONE_LEVEL = 0.12        # each of the two dial tone notes, as a fraction of full scale
RING_LEVEL = 0.6              # the ringer (kept below full scale so the amplifier is not driven hard)
