# Judicom software

Run these from this folder (`software/`).  Needs `sudo apt install python3-pygame python3-pil` for anything that draws.

## Starting by itself at power-on

    bash systemd/install_services.sh          # once, on the Judicom: installs and starts judicom-baresip and judicom-phone
    journalctl -u judicom-phone -f            # what the phone is doing (judicom-baresip for the phone line)
    sudo systemctl restart judicom-phone      # after a git pull
    bash systemd/uninstall_services.sh        # back to starting things by hand

It also keeps the boot picture on the screen until the first photo replaces it, and turns off the login prompt on the screen
(SSH is unchanged; Ctrl-Alt-F2 still gives a login with a keyboard).  Run it again after a `git pull` that changes `systemd/`.

While the services run, the screen, the switches, the sound cards and baresip's control port are taken: stop them first to run
anything by hand (`sudo systemctl stop judicom-phone judicom-baresip`).  baresip under systemd has no keyboard, so its log shows
"module stdio.so: Operation not permitted" once at start; that is expected and harmless.

## The contacts file (on the Judicom, not in git)

Who the two buttons call and the names shown for incoming calls are in `/home/joe/contacts.txt` on the Judicom (setting:
`CONTACTS_FILE` in `judicom/config.py`, or the `JUDICOM_CONTACTS` environment variable).  Start from `contacts.example.txt`:

    641-555-0142 | Clark  | husband       | left
    515-555-0187 | Amy    | daughter      | right
    515-555-0123 | Sydney | granddaughter

The file is not kept in git (the repository is public, and these are family phone numbers; `.gitignore` keeps `contacts.txt` out).
The phone reads it again by itself within a few seconds of a change.  Whether a caller gets through at all is up to the PBX.

On the Judicom this file is a **copy**: the master is `/home/pi/judicom/contacts.txt` on the NAS (the PBX screens callers with the
same list), and `python3 -m judicom.sync`, run by the `judicom-contacts-sync` timer every 10 minutes, fetches it.  Edit the list on
the NAS; see docs/DEPLOYMENT.md.

## Step 4: the whole phone (photos + call screens + dial tone + ringer)

    python3 -m judicom.main                   # on the Judicom: photos, and the phone screens when the handset is lifted or a call comes in
    python3 -m judicom.main --demo --window   # on a PC: l = lift / hang up, 1 / 2 = buttons
    python3 -m judicom.main --snapshots DIR   # a PNG of every phone screen, to look at (no screen needed)

The phone software (baresip) is not connected yet: "Calling..." turns into "No answer." after 30 s.  Keys pretend to be it:
**y** = they answer, **f** = the call fails, **e** = they hang up, **i** = an incoming call (from the right button's
person), **u** = an incoming call from a number that is not in the contacts file.  **space** = next photo, **q** = quit.
The dial tone plays on the USB sound device (the handset), the ringer on the `Headphones` card (the jack -> PAM8403 amplifier -> speaker); a missing
card is reported at start and stays silent.  `--no-sound` turns both off, `--speed 10` runs the phone's timers faster.
Pressing a button plays touch-tone digits in the handset first (about 2 s, the screen already says "Calling ..."), then the call goes
out.  The digits are the person's number from the contacts file.

## Step 3: the hook switch, the buttons, and what the phone does

    python3 -m judicom.inputs                 # wiring check: prints "lifted", "hung_up", "button left" ... from the real switches
    python3 -m judicom.machine                # the phone's state machine driven by the real switches, printed (no screen, no calls yet)
    python3 -m judicom.machine --demo --speed 10    # on a PC: l = lift / hang up, 1 / 2 = buttons; y / f / e / i = pretend call events

Pins, which way round the hook switch works, settle times, who each button calls, and the timeouts are in `judicom/config.py`.
The modes and how they change are described at the top of `judicom/machine.py`.  Needs `sudo apt install python3-gpiozero python3-lgpio` on the Judicom.

## Step 2: the photo screen

    python3 -m judicom.photo_show             # full screen on the Judicom: pictures from /home/joe/photos, 15 s each, random order
                                              # (the folder is a copy of the NAS's, see judicom/photo_sync.py)
    python3 -m judicom.photo_show --window    # small window on a PC
    python3 -m judicom.photo_show --flip      # if the picture is upside-down on the panel
    python3 -m judicom.photo_show --seconds 3 # quick look

Keys, typed in the terminal you started it from: **space** = next picture, **q** (or Esc, or Ctrl-C) = quit.

## Step 1: the photo folder

    python3 -m judicom.photos                 # list /home/joe/photos, show the next 10 pictures in random order
    python3 -m judicom.photos DIR -n 20       # another folder / more pictures

The folder is set in `judicom/config.py` (or the JUDICOM_PHOTOS environment variable).  Caption files (`IMG.meta`) are described at the
top of `judicom/photos.py`.

## Tests

    python3 -m unittest -v                    # the picture-drawing tests are skipped if pygame is not installed

To try the whole program on a PC, without the phone's hardware:  `python3 -m judicom.main --demo --window`.

## Hardware checks (`tools/`)

Small programs run by hand on the Judicom while building or fixing it (not part of the tests):

    python3 tools/gpio_test.py              the five switches (hook contacts, buttons), live on the screen for 30 s
    python3 tools/list_audio_devices.py     every sound device, as ALSA and as Python see it (--probe: what each accepts)
    python3 tools/speaker_tone_test.py      a melody in the handset speaker; the keys change its loudness, to find the level
    python3 tools/play_ringtone.py          the ringtone (~/phone_ring.wav, made if missing) on the ringer speaker
    python3 tools/mic_meter.py              live microphone level meters, in an SSH terminal
    python3 tools/handset_echo_test.py      what the handset microphone hears, played back in its speaker for 30 s
    python3 tools/touch_draw.py             draw on the screen with your fingers; a button or the handset ends it (it
                                            stops the phone program while it runs and starts it again after)
    python3 tools/screen_grab.py            what the screen is showing now, upright, in ~/screen.png (nothing is stopped)

## Files

    judicom/config.py       settings: photo folder, seconds per picture, colours
    judicom/photos.py       which picture comes next (shuffled rounds), caption files          (no pygame; runs anywhere)
    judicom/layout.py       where the photo goes so the caption covers as little of it as possible  (no pygame)
    judicom/photo_view.py   the photo screen: fitting, caption band, cross-fade               (pygame)
    judicom/display.py      opens the screen; turns the upright picture 90 degrees onto the panel
    judicom/messages.py     messages from the housekeeping website: waiting, showing, read                (no pygame)
    judicom/message_view.py the speech bubble screen                                                  (pygame)
    judicom/touch.py        the touch screen: finds it, reads fingers and taps
    judicom/inputs.py       hook switch (3 contacts, majority vote) and buttons -> debounced events   (no pygame)
    judicom/machine.py      the phone's modes: events in, screen / dial tone / ringer / call actions out (no pygame)
    judicom/home.py         what shows when no call is on: photos; every 5 photos the info, verse or weather screen in turn;
                            9 pm - 6 am the night clock
    judicom/screens.py      the screens that take turns between photos (info, verse, weather): one way for each  (no pygame)
    judicom/info_view.py    the info screen (day, date, time, next events with countdowns) and the night clock (pygame)
    judicom/weather_view.py the weather screen: today and the next 5 days                              (pygame)
    judicom/event_icons.py  the little pictures beside the events (a cake, a tree, a turkey ...)    (pygame)
    judicom/verse_view.py   the verse screen: a verse on a page like an old Bible (EB Garamond, judicom/fonts)    (pygame)
    judicom/verses.py       Judi's verse list (KJV) and the shuffled deck                                 (no pygame)
    judicom/events.py       Judi's events list (birthdays, holidays, visits) and the countdowns           (no pygame)
    judicom/weather.py      Oskaloosa's weather and forecast from Open-Meteo, fetched every 30 min      (no pygame)
    judicom/call_view.py    the phone screens: arrows to the buttons, calling, speaking, no answer, incoming, please hang up (pygame)
    judicom/contacts.py     the contacts file: the two buttons' people, names for incoming numbers (no pygame)
    judicom/watched_file.py reads the contacts / events / verses file again only when it changes     (no pygame)
    judicom/sync.py         fetches the contacts file from the NAS (the master copy)                (no pygame)
    judicom/photo_sync.py   copies the photos from the NAS (/mnt/8tbdrive/Photos/Judi), every hour  (no pygame)
    judicom/sound.py        dial tone and ringer, looped through aplay                        (no pygame)
    judicom/main.py         the program: switches + keys -> machine -> screens, sounds, phone software
    judicom/draw.py         text helpers        judicom/keys.py   key presses        judicom/photo_show.py   photos only (step 2)

Suggested place in the repo: `software/`.
