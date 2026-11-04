"""Plays the ringer on the speaker, over and over, until Ctrl-C.  For checking the speaker and setting its volume.

    cd ~/Judicom/software && python3 -m judicom.ring_test          # at the usual level (config.RING_LEVEL)
    python3 -m judicom.ring_test 0.3                              # at another level, 0.0 - 1.0

Safe to run while the phone program is running: the phone only opens the speaker while it is ringing for a call.
"""
import signal
import sys
import time

from judicom import config, sound


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        level = float(args[0]) if args else config.RING_LEVEL
    except ValueError:
        sys.exit(__doc__)
    if not 0.0 <= level <= 1.0:
        sys.exit("The level must be between 0.0 and 1.0.")
    if not sound.card_exists(config.RINGER_CARD):
        sys.exit("No '%s' sound card (see `aplay -l`)." % config.RINGER_CARD)
    ring = sound.Loop(config.RINGER_CARD, sound.ring_pcm(level=level), "ringer", print)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print("Ringing at level %.2f on '%s'.  Ctrl-C to stop." % (level, config.RINGER_CARD))
    try:
        ring.start()
        while ring.playing:                                # until Ctrl-C (or aplay fails, which Loop reports)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()
    finally:
        ring.stop()
    print("Stopped.")


if __name__ == "__main__":
    main()
