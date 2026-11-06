#!/usr/bin/env python3
"""screen_grab.py - save what the Judicom's screen is showing right now as a picture, upright as Judi sees it.

    python3 tools/screen_grab.py                 on the Judicom (over SSH is fine): writes ~/screen.png
    python3 tools/screen_grab.py some.png        writes that file
    python3 tools/screen_grab.py -               writes the PNG to standard output

To just look, use See Judicom Now on the housekeeping website (http://naspi.local:8080): it runs this with the - and shows the
picture, over a key that can do nothing else (docs/DEPLOYMENT.md).

It takes the picture the graphics hardware is sending to the panel, not one the phone program hands over, so nothing is stopped
or restarted, the phone program does not need to know, and the picture is the truth even if the program has hung.

/dev/fb0 does not help: it is only the text console, and SDL draws past it through KMS/DRM.  So this asks the kernel which
buffer is on the screen and reads that.  Being allowed to is for root alone, so it runs itself again through sudo -n for the
reading, and the file is written by you.

That buffer is not in plain rows: the Pi's GPU keeps it in "T-format" tiles (untile() below; its order was measured on the
Judicom on 2026-11-06).  The picture is also lying on its side, the quarter turn of judicom/display.py, which is turned back
here.  Started with --flip the phone program would turn the other way and these pictures would come out upside-down.
"""
import argparse
import ctypes
import mmap
import os
import struct
import subprocess
import sys
from io import BytesIO
from pathlib import Path

CARD = "/dev/dri/card0"
DEFAULT_FILE = "~/screen.png"

# The kernel's DRM calls (include/uapi/drm/drm.h, drm_mode.h): number, and the layout of the structure each one fills in.
PLANE_RES = "=QI4x"                # drm_mode_get_plane_res: where to put the ids, how many
PLANE = "=6IQ"                     # drm_mode_get_plane: plane, crtc, fb, possible_crtcs, gamma_size, format count, format list
FB2 = "=5I4I4I4I4x4Q"              # drm_mode_fb_cmd2: fb, width, height, format, flags, handles, pitches, offsets, modifiers
PRIME = "=IIi"                     # drm_prime_handle: handle, flags, the file descriptor that comes back
CAP = "=QQ"                        # drm_set_client_cap: which, value
CAP_UNIVERSAL_PLANES = 2           # without this the kernel leaves the main plane, the one with the picture, off its list
DRM_CLOEXEC = 0o2000000

FOURCC_ARGB, FOURCC_XRGB = 0x34325241, 0x34325258
MOD_BROADCOM_T_TILED = 0x0700000000000001

# Where the four 16 x 16 pieces of a 32 x 32 tile go, in the order they are stored: (down, across).  Tile rows run alternately
# left to right and right to left, and the order of the pieces alternates with them.
PIECES = (((0, 0), (1, 0), (1, 1), (0, 1)),        # even tile rows
          ((1, 1), (0, 1), (0, 0), (1, 0)))        # odd tile rows


def ioctl_number(nr, fmt, write_only=False):
    return ((1 if write_only else 3) << 30) | (struct.calcsize(fmt) << 16) | (ord("d") << 8) | nr


def call(fd, nr, fmt, *values, write_only=False):
    """One DRM call: the structure goes in with `values` and comes back filled in."""
    import fcntl                   # here, not at the top: the tests run on Windows PCs too, which do not have it

    buffer = bytearray(struct.pack(fmt, *values))
    fcntl.ioctl(fd, ioctl_number(nr, fmt, write_only), buffer, True)
    return struct.unpack(fmt, buffer)


def on_screen_buffer(card=CARD):
    """(bytes of the buffer on the screen, width, height, format, modifier).  Needs root."""
    fd = os.open(card, os.O_RDWR | os.O_CLOEXEC)
    try:
        call(fd, 0x0D, CAP, CAP_UNIVERSAL_PLANES, 1, write_only=True)
        count = call(fd, 0xB5, PLANE_RES, 0, 0)[1]
        ids = (ctypes.c_uint32 * count)()
        call(fd, 0xB5, PLANE_RES, ctypes.addressof(ids), count)

        frames = []
        for plane in ids:
            _, crtc, fb, *_rest = call(fd, 0xB6, PLANE, plane, 0, 0, 0, 0, 0, 0)
            if crtc and fb:
                frames.append(call(fd, 0xCE, FB2, fb, *[0] * 20))
        if not frames:
            sys.exit("Nothing is on the screen.")
        frame = max(frames, key=lambda f: f[1] * f[2])                  # the picture, not a cursor
        width, height, fourcc, handle, modifier = frame[1], frame[2], frame[3], frame[5], frame[17]

        buffer_fd = call(fd, 0x2D, PRIME, handle, DRM_CLOEXEC, -1)[2]
        try:
            with mmap.mmap(buffer_fd, os.lseek(buffer_fd, 0, os.SEEK_END), mmap.MAP_SHARED, mmap.PROT_READ) as memory:
                return memory[:], width, height, fourcc, modifier
        finally:
            os.close(buffer_fd)
    finally:
        os.close(fd)


def untile(data, width, height):
    """T-format bytes -> an array of `height` rows of `width` pixels of 4 bytes each.

    A 32 x 32 tile (4096 bytes) is four 16 x 16 pieces (see PIECES), each a 4 x 4 block of 4 x 4 pixel "micro-tiles"."""
    import numpy as np

    across, down = -(-width // 32), -(-height // 32)
    stored = np.frombuffer(data, np.uint8, across * down * 4096).reshape(down, across, 4, 4, 4, 4, 4, 4)
    # [tile row, tile, piece, micro-tile row, micro-tile, pixel row, pixel, byte]
    out = np.empty((down, 2, 4, 4, across, 2, 4, 4, 4), np.uint8)
    # [tile row, piece row, micro-tile row, pixel row, tile, piece, micro-tile, pixel, byte]
    for odd in (0, 1):
        tiles = stored[odd::2, ::-1] if odd else stored[0::2]
        for number, (piece_row, piece) in enumerate(PIECES[odd]):
            out[odd::2, piece_row, :, :, :, piece] = tiles[:, :, number].transpose(0, 2, 4, 1, 3, 5, 6)
    return out.reshape(down * 32, across * 32, 4)[:height, :width]


def as_png(data, width, height, fourcc, modifier):
    """The bytes of an upright PNG of the buffer."""
    from PIL import Image

    if fourcc not in (FOURCC_ARGB, FOURCC_XRGB) or modifier != MOD_BROADCOM_T_TILED:
        sys.exit("The screen is showing something other than the phone program's picture (format %08x, layout %016x), "
                 "and this only reads that one.  Is judicom-phone running?" % (fourcc, modifier))
    pixels = untile(data, width, height)
    picture = Image.fromarray(pixels[:, :, 2::-1].copy()).transpose(Image.Transpose.ROTATE_270)   # blue-green-red -> RGB, upright
    png = BytesIO()
    picture.save(png, "PNG")
    return png.getvalue()


def png_through_sudo():
    """Runs this file again as root, which gives back the PNG."""
    result = subprocess.run(["sudo", "-n", sys.executable, str(Path(__file__).resolve()), "-"], stdout=subprocess.PIPE)
    if result.returncode:
        sys.exit("Could not read the screen (it needs root, through sudo -n).")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Save what the Judicom's screen is showing as a picture.")
    parser.add_argument("file", nargs="?", default=DEFAULT_FILE, help="where to write the PNG, - for standard output "
                                                                      "(default %(default)s)")
    args = parser.parse_args()

    png = as_png(*on_screen_buffer()) if os.geteuid() == 0 else png_through_sudo()
    if args.file == "-":
        sys.stdout.buffer.write(png)
    else:
        path = Path(args.file).expanduser()
        path.write_bytes(png)
        print(path)


if __name__ == "__main__":
    main()
