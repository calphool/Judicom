# Judicom software

Run these from this folder (`software/`).  Needs `sudo apt install python3-pygame python3-pil` for anything that draws.

## Step 3: the hook switch, the buttons, and what the phone does

    python3 -m judicom.inputs                 # wiring check: prints "lifted", "hung_up", "button left" ... from the real switches
    python3 -m judicom.machine                # the phone's state machine driven by the real switches, printed (no screen, no calls yet)
    python3 -m judicom.machine --demo --speed 10    # on a PC: l = lift / hang up, 1 / 2 = buttons; y / f / e / i = pretend call events

Pins, which way round the hook switch works, settle times, who each button calls, and the timeouts are in `judicom/config.py`.
The modes and how they change are described at the top of `judicom/machine.py`.  Needs `sudo apt install python3-gpiozero python3-lgpio` on the Judicom.

## Step 2: the photo screen

    python3 -m judicom.photo_show             # full screen on the Judicom: pictures from /home/joe/photos, 15 s each, random order
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

## Files

    judicom/config.py       settings: photo folder, seconds per picture, colours
    judicom/photos.py       which picture comes next (shuffled rounds), caption files          (no pygame; runs anywhere)
    judicom/layout.py       where the photo goes so the caption covers as little of it as possible  (no pygame)
    judicom/photo_view.py   the photo screen: fitting, caption band, cross-fade               (pygame)
    judicom/display.py      opens the screen; turns the upright picture 90 degrees onto the panel
    judicom/inputs.py       hook switch (3 contacts, majority vote) and buttons -> debounced events   (no pygame)
    judicom/machine.py      the phone's modes: events in, screen / dial tone / ringer / call actions out (no pygame)
    judicom/draw.py         text helpers        judicom/keys.py   key presses        judicom/photo_show.py   the program above

Suggested place in the repo: `software/`.
