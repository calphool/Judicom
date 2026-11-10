"""Settings that other parts of the program share.  Change a value here, nowhere else."""
import configparser
import os
from pathlib import Path

# ---- this installation's own facts (NOT in git: the repository is public) ---------------------------------------------------
# Where Judi lives (for the weather) and the names she goes by are in a small file on the Judicom; see judicom-site.example.conf.
# Without it the phone works as always, only with no weather screen.
SITE_FILE = Path(os.environ.get("JUDICOM_SITE", "/home/joe/judicom-site.conf"))
_site = configparser.ConfigParser()
try:
    _site.read(SITE_FILE, encoding="utf-8")
except (OSError, configparser.Error, UnicodeDecodeError):
    pass                                             # a broken file counts as no file


def _site_float(section, key):
    try:
        return float(_site.get(section, key))
    except (configparser.Error, ValueError):
        return None

# Where the family photos live (judicom.photo_sync fills this folder from the NAS every hour).
# For a test on another computer:  JUDICOM_PHOTOS=/some/folder python3 -m judicom.photos
PHOTO_DIR = Path(os.environ.get("JUDICOM_PHOTOS", "/home/joe/photos"))

# Judi's own name as family members might write it in a caption: shown as "You" ("Judi and Ann" -> "You and Ann",
# "Judi's sister" -> "Your sister").  Add other names she goes by if family use them for her.
JUDI_NAMES = tuple(n.strip() for n in _site.get("judi", "names", fallback="Judi").split(",") if n.strip()) or ("Judi",)

# Which files count as pictures (capital letters do not matter).
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".bmp")

# A picture of each person in the caller list, shown while calling them, talking with them, or when they ring: "Ann.png",
# "Frank.jpg" (named as in the caller list; capitals do not matter).  Square, about 800 x 800, the face filling most of it; any
# other shape is cropped from the middle.  judicom.sync fills this folder from /home/pi/judicom/people on the NAS.
PEOPLE_DIR = Path(os.environ.get("JUDICOM_PEOPLE", "/home/joe/people"))
PEOPLE_EXTS = (".png", ".jpg", ".jpeg")
PEOPLE_MAX_FILE = 5 * 1024 * 1024     # a bigger picture is not copied from the NAS (800 x 800 is far smaller)
PEOPLE_MAX_TOTAL = 50 * 1024 * 1024   # nor more than this altogether
FACE_PX = 400                         # the picture's size on the call screens
LIFTED_FACE_PX = 190                  # the small picture over each arrow when the handset is lifted

# Messages from the housekeeping website (judicom/messages.py) wait here until Judi has read them.
MESSAGES_DIR = Path(os.environ.get("JUDICOM_MESSAGES", "/home/joe/messages"))

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
# GPIO numbers (BCM).  Every switch connects its pin to ground; the Pi's internal pull-ups are used.  Same pins as tools/gpio_test.py.
HOOK_NC_PINS = (17, 27)       # the hook switch's two normally-closed contacts
HOOK_NO_PINS = (22,)          # ... and its normally-open contact.  The three vote, so one bad contact cannot fake a lift or a hang-up.
HOOK_PRESSED_ON_HOOK = True   # True: the handset resting in the cradle presses the switch.  False if it is the other way round.
BUTTON_PINS = {"left": 23, "right": 24}
AMP_PIN = 25                  # an OUTPUT: high switches the ringer's amplifier on (through a MOSFET); low, or no program, off
AMP_OFF_SECONDS = 1.0         # it is switched off this long after the speaker's last sound has ended
#                               (switched so that the amplifier's noise is not heard between sounds: docs/HARDWARE.md)
LIFT_SETTLE = 0.10            # the handset counts as lifted after it has been up this long (seconds)
HANG_UP_SETTLE = 0.50         # ... and as hung up after it has been down this long, so a jostle in the cradle does not end a call
BUTTON_SETTLE = 0.05          # a button press counts after this long (contact bounce)

# ---- the phone: who the buttons call ----------------------------------------------------------------------------------------
# The real people are in the contacts file on the Judicom (not in git: the repository is public).  See contacts.example.txt.
CONTACTS_FILE = Path(os.environ.get("JUDICOM_CONTACTS", "/home/joe/contacts.txt"))

# The master list is on the NAS; judicom.sync copies it here every 10 minutes (over Tailscale, with a key that can only read it).
SYNC_HOST = "pi@naspi-1"
SYNC_KEY = "/home/joe/.ssh/judicom_sync"
# The photos come from /mnt/8tbdrive/Photos/Judi on the NAS (shared with Jellyfin); judicom.photo_sync copies them into PHOTO_DIR
# every hour, with a key the NAS only lets read that folder.
PHOTO_SYNC_KEY = "/home/joe/.ssh/judicom_photos"
PHOTO_KEEP_FREE = 4 * 1024 ** 3    # the photo sync never fills the card past this: it copies nothing and logs a warning instead

# Only used when there is no contacts file (a demo on a PC).  Made-up 555 numbers.
# "dial" is what is sent to the PBX (an extension or a number).
# "tones" are the touch-tone digits played in the handset when the button is pressed, so it sounds like a phone dialing.  Leave it out
# and the digits of "dial" are used (if it has any); "" = no dialing sound.  The same digits every time: the same little tune per person.
BUTTONS = {
    "left": {"name": "Frank", "relationship": "husband", "dial": "frank", "tones": "5550100142"},
    "right": {"name": "Ann", "relationship": "daughter", "dial": "ann", "tones": "5550100187"},
}

# ---- the phone software ------------------------------------------------------------------------------------------------------
BARESIP_CTRL = ("127.0.0.1", 4444)   # baresip's ctrl_tcp_listen (in ~/.baresip/config)

# ---- the phone: timing ------------------------------------------------------------------------------------------------------
LIFTED_SECONDS = 60.0         # handset up, no button pressed: after this long the yellow "please hang up" screen (dial tone stops)
KEYPAD_SECONDS = 60.0         # the hidden keypad (judicom/keypad.py) with no key pressed for this long: "please hang up" too
KEYPAD_KNOCK_SECONDS = 4.0    # its secret knock (top left twice, top right twice): each tap within this long of the last
RING_OUT_SECONDS = 30.0       # calling someone who does not pick up: give up after this long -> "No answer."
NO_ANSWER_SECONDS = 10.0      # the "No answer." screen
OUT_OF_ORDER_SECONDS = 15.0   # "The phone is not working.": a button pressed while the phone cannot reach the PBX
CALL_ENDED_SECONDS = 10.0     # the "Call just ended with ..." screen
DIGIT_ON, DIGIT_OFF = 0.08, 0.06   # each touch-tone digit sounds this long, with this much quiet after it (about a fast dialer's pace)

# ---- the call screens -------------------------------------------------------------------------------------------------------
BUTTON_X = {"left": SCREEN_W // 2 - 129, "right": SCREEN_W // 2 + 129}   # screen x right above each button (37 mm apart; 600 px = 86 mm)
AMBER, GREEN, ROSE = (255, 196, 64), (112, 214, 144), (240, 150, 150)
YELLOW, DARK = (255, 214, 10), (30, 30, 30)    # the "please hang up" screen

# ---- sounds -----------------------------------------------------------------------------------------------------------------
# The dial tone goes to the handset (the USB sound device, found by itself); the ringer to the Pi's headphone jack -> PAM8403 -> speaker.
RINGER_CARD = "Headphones"    # ALSA card id of the 3.5 mm jack (see `aplay -l`)
DIAL_TONE_LEVEL = 0.12        # each of the two dial tone notes, as a fraction of full scale
DIGIT_LEVEL = 0.15            # each of the two notes of a touch-tone digit
RING_LEVEL = 0.6              # the ringer (kept below full scale so the amplifier is not driven hard)
BEEP_LEVEL = 0.5              # the three beeps of a new message, on the ringer speaker

# ---- the maintenance shell (judicom/maintenance.py) -------------------------------------------------------------------------
ARM_SECONDS = 3.0             # both buttons held this long, handset on the hook: a bong
KNOCK_SECONDS = 10.0          # then each corner within this long of the last
CORNER_PX = 170               # how far from the edges a tap still counts as in the corner
SHELL_IDLE_SECONDS = 600.0    # back to the photos after this long without a key
SHELL_COLUMNS, SHELL_ROWS = 58, 32                 # 10 x 19 pixels each, above the keyboard
SHELL_TOP = 36                # the first row starts this far down: the bezel covers the top of the screen
SHELL_RIGHT = 20              # and the shell and the keyboard stop this far from the right edge, which the bezel covers too
BONG_LEVEL = 0.4              # on the ringer speaker

# ---- the info screen and the night clock ------------------------------------------------------------------------------------
INFO_EVERY_PHOTOS = 5         # after this many photos, the next of the info screen (date, time, upcoming events), a verse or
INFO_SECONDS = 30.0           # the weather ... the info screen for this long, then the photos again
INFO_EVENTS = 5               # how many upcoming events it shows (fewer when long names leave no room)
WEATHER_SECONDS = 30.0        # the weather screen (today and the next days), for this long
NIGHT_FROM = (21, 0)          # the night clock (a dark screen with only the time and date) from 9:00 pm ...
NIGHT_TO = (6, 0)             # ... to 6:00 am.  Calls work as always; afterwards the night clock comes back.
# To see the photos and the info screen at night (setting it up, showing it to someone): create this file
# (touch /home/joe/judicom-awake).  The night clock stays away while it exists, but only for NIGHT_PAUSE_HOURS after it was made
# or last touched, so a forgotten file does no harm.  Remove it to bring the night clock back at once.
NIGHT_PAUSE_FILE = Path(os.environ.get("JUDICOM_AWAKE", "/home/joe/judicom-awake"))
NIGHT_PAUSE_HOURS = 2.0
# Judi's events: a copy of /home/pi/judicom/events.txt on the NAS (judicom.sync fetches it with the caller list).
EVENTS_FILE = Path(os.environ.get("JUDICOM_EVENTS", "/home/joe/events.txt"))
# The weather screen (Open-Meteo: free, no account), fetched every 30 minutes; left out when it is more than 3 hours old.
# The place is in the site file ([weather] place, latitude, longitude, timezone); without a latitude and longitude: no weather.
WEATHER_PLACE = _site.get("weather", "place", fallback="")
WEATHER_LAT, WEATHER_LON = _site_float("weather", "latitude"), _site_float("weather", "longitude")
WEATHER_TIMEZONE = _site.get("weather", "timezone", fallback="auto")        # "auto": the place's own time zone
WEATHER_EVERY = 30 * 60
WEATHER_STALE = 3 * 60 * 60
NIGHT_INK, NIGHT_SOFT = (104, 104, 104), (78, 78, 78)    # the night clock's dim greys
CARD = (52, 90, 100)          # the info screen's lighter teal panels

# ---- the verse screen ------------------------------------------------------------------------------------------------------
# It takes its turn with the info and weather screens (after every INFO_EVERY_PHOTOS photos, the next of the three), for
# VERSE_SECONDS.  The verses: a copy of /home/pi/judicom/verses.txt on the NAS (judicom.sync fetches it with the caller
# list); see judicom/verses.py.
VERSE_SECONDS = 30.0
VERSES_FILE = Path(os.environ.get("JUDICOM_VERSES", "/home/joe/verses.txt"))

# ---- the joke screen -------------------------------------------------------------------------------------------------------
# A joke's setup, then its punchline PUNCHLINE_SECONDS later on the same screen, JOKE_SECONDS in all.  The jokes: a copy of
# /home/pi/judicom/jokes.txt on the NAS (judicom.sync fetches it with the caller list); see judicom/jokes.py.
JOKE_SECONDS = 30.0
PUNCHLINE_SECONDS = 8.0
LAUGH_DELAY_SECONDS = 2.0     # the jester laughs this long after the punchline appears ...
LAUGH_SECONDS = 4.0           # ... for this long, then smiles again
LAUGH_FPS = 12                # the laugh is drawn this many times a second (the rest of the time the screen is still)
JOKES_FILE = Path(os.environ.get("JUDICOM_JOKES", "/home/joe/jokes.txt"))
FONT_DIR = Path(__file__).resolve().parent / "fonts"
