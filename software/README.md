# Judicom software

Step 1: the photo folder (`judicom/photos.py`) - which picture comes next, and its caption file.

    python3 -m judicom.photos            # list /home/joe/photos and show the next 10 pictures in random order
    python3 -m judicom.photos DIR -n 20  # another folder / more pictures
    python3 -m unittest -v               # run the tests (needs only Python 3.9 or newer, nothing to install)

The folder is set in `judicom/config.py` (or the JUDICOM_PHOTOS environment variable).
Suggested place in the repo: `software/`.
