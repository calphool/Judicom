#!/usr/bin/env python3
"""nas_request.py - everything the NAS's key may ask of the Judicom, and nothing else.  It is that key's forced command:

    restrict,command="/usr/bin/nice -n 10 /usr/bin/python3 /home/joe/Judicom/software/tools/nas_request.py" ssh-ed25519 ... judicom-screen

The NAS's housekeeping website asks for one of these (SSH_ORIGINAL_COMMAND):

    screen      (also when it asks for nothing) a PNG of what the screen is showing: tools/screen_grab.py
    message     a message for Judi comes in on standard input (judicom/messages.py); says "ok"
    messages    which messages are still waiting and when the others were read, as JSON

Anything else is refused.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))       # the software folder, for the judicom package

from judicom import messages                                       # noqa: E402

MAX_REQUEST = 8192                 # bytes: a message is far smaller


def main():
    request = os.environ.get("SSH_ORIGINAL_COMMAND", "").strip() or "screen"
    if request == "screen":
        grab = str(Path(__file__).resolve().with_name("screen_grab.py"))
        os.execv(sys.executable, [sys.executable, grab, "-"])
    elif request == "message":
        try:
            messages.deliver(sys.stdin.buffer.read(MAX_REQUEST))
        except (ValueError, OSError) as exc:
            sys.exit("nas_request: %s" % exc)
        print("ok")
    elif request == "messages":
        print(json.dumps(messages.statuses()))
    else:
        sys.exit("nas_request: only 'screen', 'message' or 'messages' may be asked for")


if __name__ == "__main__":
    main()
