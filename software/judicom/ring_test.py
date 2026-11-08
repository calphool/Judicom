"""Plays the ringer on the speaker, over and over, until Ctrl-C.  For checking the speaker and setting its volume.

    cd ~/Judicom/software && python3 -m judicom.ring_test              # at the usual level (config.RING_LEVEL)
    python3 -m judicom.ring_test 0.3                                  # at another level, 0.0 - 1.0
    python3 -m judicom.ring_test --pin 25=0                           # the amplifier's pin low: the speaker should stay silent
    python3 -m judicom.ring_test --pin 25=0 --pin 26=1 0.3            # several pins, and a level

The amplifier's pin (config.AMP_PIN, GPIO 25) is set high first unless a --pin says otherwise.  Each --pin is set before the ringer
starts and held while it rings; on Ctrl-C the pins are set back to 0 and released.
The switch pins (hook and buttons) are refused: they are wired to ground, and driving one high would short it.
The phone program holds the amplifier's pin, so stop it first:  sudo systemctl stop judicom-phone   (and start it again after).
"""
import argparse
import signal
import sys
import time

from judicom import config, sound

SWITCH_PINS = set(config.HOOK_NC_PINS) | set(config.HOOK_NO_PINS) | set(config.BUTTON_PINS.values())


def pin_setting(text):
    """'25=1' -> (25, 1)."""
    pin, sep, value = text.partition("=")
    try:
        pin, value = int(pin), int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("%r: write it as PIN=1 or PIN=0, e.g. 25=1" % text)
    if not sep or value not in (0, 1):
        raise argparse.ArgumentTypeError("%r: write it as PIN=1 or PIN=0, e.g. 25=1" % text)
    if not 2 <= pin <= 27:
        raise argparse.ArgumentTypeError("GPIO %d: the Pi's pins are GPIO 2 - 27 (BCM numbers)" % pin)
    if pin in SWITCH_PINS:
        raise argparse.ArgumentTypeError("GPIO %d is one of the Judicom's switch pins (%s); not driving it"
                                         % (pin, ", ".join(str(p) for p in sorted(SWITCH_PINS))))
    return pin, value


def parse(argv):
    p = argparse.ArgumentParser(prog="python3 -m judicom.ring_test", description="Plays the ringer until Ctrl-C.")
    p.add_argument("level", nargs="?", type=float, default=config.RING_LEVEL,
                   help="loudness, 0.0 - 1.0 (default %s)" % config.RING_LEVEL)
    p.add_argument("--pin", action="append", type=pin_setting, default=[], metavar="PIN=0|1",
                   help="set this GPIO (BCM number) to 0 or 1 before ringing; may be given more than once")
    args = p.parse_args(argv)
    if not 0.0 <= args.level <= 1.0:
        p.error("the level must be between 0.0 and 1.0")
    return args


def set_pins(settings):
    """Sets the pins with gpiozero; returns the devices (they hold the pins until closed)."""
    from gpiozero import DigitalOutputDevice
    held = []
    try:
        for pin, value in settings:
            held.append(DigitalOutputDevice(pin, initial_value=bool(value)))
            print("GPIO %d set to %d." % (pin, value))
    except Exception:
        release(held)
        raise
    return held


def release(held):
    for d in held:
        try:
            d.off()
            d.close()
        except Exception:
            pass


def main(argv=None):
    args = parse(sys.argv[1:] if argv is None else argv)
    if not sound.card_exists(config.RINGER_CARD):
        sys.exit("No '%s' sound card (see `aplay -l`)." % config.RINGER_CARD)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    held = []
    ring = sound.Loop(config.RINGER_CARD, sound.ring_pcm(level=args.level), "ringer", print)
    try:
        pins = args.pin if any(pin == config.AMP_PIN for pin, _ in args.pin) else [(config.AMP_PIN, 1)] + args.pin
        try:
            held = set_pins(pins)
        except Exception as e:
            sys.exit("Could not set the pins: %s\n(Is the phone program running?  It holds GPIO %d:  sudo systemctl stop judicom-phone)"
                     % (e, config.AMP_PIN))
        print("Ringing at level %.2f on '%s'.  Ctrl-C to stop." % (args.level, config.RINGER_CARD))
        ring.start()
        while ring.playing:                                # until Ctrl-C (or aplay fails, which Loop reports)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
    finally:
        ring.stop()
        release(held)
        if held:
            print("Pins set back to 0 and released.")
    print("Stopped.")


if __name__ == "__main__":
    main()
