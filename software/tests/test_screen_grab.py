"""Tests for tools/screen_grab.py: turning the GPU's tiles back into rows, and the layouts of the kernel's structures.
The tile tests need numpy and PIL; without them they are skipped.  Run from the software folder:   python3 -m unittest -v"""
import importlib.util
import struct
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = None

spec = importlib.util.spec_from_file_location("screen_grab", Path(__file__).resolve().parents[1] / "tools" / "screen_grab.py")
screen_grab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen_grab)

# Where each 16 x 16 piece of a tile is stored, written out by hand: (down, across) -> number, for even and odd tile rows.
EVEN = {(0, 0): 0, (1, 0): 1, (1, 1): 2, (0, 1): 3}
ODD = {(1, 1): 0, (0, 1): 1, (0, 0): 2, (1, 0): 3}


def address(x, y, across):
    """The byte in a T-format buffer that holds pixel (x, y), worked out one pixel at a time."""
    row, tile = y // 32, x // 32
    stored_tile = across - 1 - tile if row % 2 else tile
    piece = (ODD if row % 2 else EVEN)[(y // 16 % 2, x // 16 % 2)]
    micro = (y // 4 % 4) * 4 + x // 4 % 4
    pixel = (y % 4) * 4 + x % 4
    return (row * across + stored_tile) * 4096 + piece * 1024 + micro * 64 + pixel * 4


def tiled(width, height):
    """A T-format buffer in which every pixel says where it is: bytes are x low, x high, y low, y high."""
    across, down = -(-width // 32), -(-height // 32)
    data = bytearray(across * down * 4096)
    for y in range(down * 32):
        for x in range(across * 32):
            data[address(x, y, across):address(x, y, across) + 4] = struct.pack("<HH", x, y)
    return bytes(data)


@unittest.skipIf(np is None, "numpy and PIL are not installed")
class Untile(unittest.TestCase):
    def check(self, width, height):
        pixels = screen_grab.untile(tiled(width, height), width, height)
        self.assertEqual(pixels.shape, (height, width, 4))
        got = pixels.copy().view("<u2").reshape(height, width, 2)
        self.assertTrue((got[:, :, 0] == np.arange(width)).all())
        self.assertTrue((got[:, :, 1] == np.arange(height)[:, None]).all())

    def test_the_judicom_panel(self):
        self.check(1024, 600)              # 600 is not a whole number of tiles: the last tile row is cut

    def test_an_odd_number_of_tile_rows_and_part_tiles(self):
        self.check(70, 100)

    def test_a_longer_buffer_is_fine(self):
        data = tiled(64, 64) + bytes(4096)
        self.assertEqual(screen_grab.untile(data, 64, 64).shape, (64, 64, 4))


@unittest.skipIf(np is None, "numpy and PIL are not installed")
class Png(unittest.TestCase):
    def test_comes_out_upright_with_the_colours_right(self):
        width, height = 64, 32                                       # the panel lies on its side, so wider than tall
        data = bytearray(width // 32 * height // 32 * 4096)
        data[address(0, 0, 2):address(0, 0, 2) + 4] = bytes((30, 20, 10, 255))       # blue, green, red, alpha
        png = screen_grab.as_png(bytes(data), width, height, screen_grab.FOURCC_XRGB, screen_grab.MOD_BROADCOM_T_TILED)
        picture = Image.open(BytesIO(png))
        self.assertEqual(picture.size, (height, width))
        self.assertEqual(picture.getpixel((height - 1, 0)), (10, 20, 30))  # the panel's first pixel: top right when upright

    def test_something_else_on_the_screen_is_said_plainly(self):
        with self.assertRaises(SystemExit) as caught:
            screen_grab.as_png(bytes(4096), 32, 32, 0x36314752, 0)
        self.assertIn("judicom-phone", str(caught.exception))


class KernelStructures(unittest.TestCase):
    def test_sizes_match_the_kernel_headers(self):
        self.assertEqual(struct.calcsize(screen_grab.PLANE_RES), 16)
        self.assertEqual(struct.calcsize(screen_grab.PLANE), 32)
        self.assertEqual(struct.calcsize(screen_grab.FB2), 104)
        self.assertEqual(struct.calcsize(screen_grab.PRIME), 12)
        self.assertEqual(struct.calcsize(screen_grab.CAP), 16)

    def test_the_call_number_for_reading_a_frame_buffer(self):
        self.assertEqual(screen_grab.ioctl_number(0xCE, screen_grab.FB2), 0xC06864CE)      # DRM_IOCTL_MODE_GETFB2



class Root(unittest.TestCase):
    def test_sudo_runs_the_copy_only_root_can_change_not_the_one_in_the_repo(self):
        done = mock.Mock(returncode=0, stdout=b"png")
        with mock.patch.object(screen_grab.subprocess, "run", return_value=done) as run:
            self.assertEqual(screen_grab.png_through_sudo(), b"png")
        self.assertEqual(run.call_args[0][0], ["sudo", "-n", "/usr/bin/python3", "-I", "/usr/local/lib/judicom/screen_grab.py", "-"])


if __name__ == "__main__":
    unittest.main()
