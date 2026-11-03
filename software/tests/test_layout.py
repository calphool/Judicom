"""Tests for judicom/layout.py (where the photo goes relative to the caption).  No pygame needed."""
import unittest

from judicom.config import CAPTION_GAP, MIN_SHRINK
from judicom.config import SCREEN_H as H
from judicom.config import SCREEN_W as W
from judicom.layout import place_photo


def full_fit(iw, ih):
    return min(W / float(iw), H / float(ih))


def old_overlap(iw, ih, band_y):
    """How much of the photo the caption covered before: the photo was always centred on the whole screen."""
    _, y, _, fh = place_photo(iw, ih, None)
    return max(0, y + fh - band_y)


class NoCaption(unittest.TestCase):
    def test_whole_photo_in_the_middle_of_the_screen(self):
        for size in ((1600, 1200), (1200, 1600), (900, 900), (1800, 1000), (200, 100), (600, 1024)):
            x, y, fw, fh = place_photo(*size)
            f = full_fit(*size)
            self.assertEqual((fw, fh), (int(size[0] * f), int(size[1] * f)))
            self.assertEqual((x, y), ((W - fw) // 2, (H - fh) // 2))
            self.assertTrue(fw == W or fh == H or max(fw, fh) < max(W, H))      # as large as fits


class WithCaption(unittest.TestCase):
    BAND_Y = 758                                                                # a three-line caption: names, relationship, date

    def test_landscape_photo_moves_up_and_is_not_shrunk(self):
        x, y, fw, fh = place_photo(1600, 1200, self.BAND_Y)
        self.assertEqual((fw, fh), (600, 450))                                  # still full width
        self.assertEqual(y, (self.BAND_Y - CAPTION_GAP - 450) // 2)             # in the middle of the space above the caption
        self.assertLess(y, (H - 450) // 2)                                      # higher than before
        self.assertLessEqual(y + fh, self.BAND_Y - CAPTION_GAP)                 # clear of the caption

    def test_portrait_photo_is_made_a_little_smaller_to_clear_the_caption(self):
        x, y, fw, fh = place_photo(1200, 1600, self.BAND_Y)                     # 3:4: 800 high at full size, only 744 available
        self.assertLess(fh, 800)
        self.assertGreaterEqual(fh, int(800 * MIN_SHRINK))
        self.assertEqual(y + fh, self.BAND_Y - CAPTION_GAP)                     # ends just above the caption
        self.assertEqual(y, 0)

    def test_very_tall_photo_covers_as_little_as_possible(self):
        x, y, fw, fh = place_photo(900, 1600, self.BAND_Y)                      # 9:16
        self.assertEqual(y, 0)                                                  # as high as the screen allows
        covered = y + fh - self.BAND_Y
        self.assertGreater(covered, 0)                                          # it cannot avoid the caption ...
        self.assertLess(covered, old_overlap(900, 1600, self.BAND_Y) / 2.0)     # ... but covers far less than before

    def test_a_tall_caption_leaves_less_room(self):
        _, y1, _, fh1 = place_photo(1600, 1200, 758)
        _, y2, _, fh2 = place_photo(1600, 1200, 560)                            # a long caption: band starts higher
        self.assertLess(y2, y1)
        self.assertLessEqual(y2 + fh2, 560)

    def test_rules_hold_for_every_shape_and_caption_height(self):
        for ratio_100 in range(30, 351, 5):                                     # width / height from 0.30 to 3.50
            ih = 1000
            iw = int(ih * ratio_100 / 100.0)
            full = full_fit(iw, ih)
            for band_y in range(360, 980, 20):
                x, y, fw, fh = place_photo(iw, ih, band_y)
                where = "shape %.2f, band at %d" % (ratio_100 / 100.0, band_y)
                # on the screen, centred sideways
                self.assertTrue(0 <= x and x + fw <= W, where)
                self.assertTrue(0 <= y and y + fh <= H, where)
                self.assertLessEqual(abs(x - (W - fw) // 2), 1, where)
                # never larger than the usual size, never smaller than MIN_SHRINK of it, shape unchanged
                self.assertLessEqual(fw, int(iw * full) + 1, where)
                self.assertGreaterEqual(fw, int(iw * full * MIN_SHRINK) - 1, where)
                self.assertAlmostEqual(fw / float(fh), iw / float(ih), delta=0.02 + 2.0 / min(fw, fh), msg=where)
                covered = max(0, y + fh - band_y)
                # never covers more than before
                self.assertLessEqual(covered, old_overlap(iw, ih, band_y), where)
                if covered:
                    # it only covers if it could not be avoided: already at the smallest allowed size and as high as it can go
                    self.assertEqual(y, 0, where)
                    self.assertLessEqual(fw, int(iw * full * MIN_SHRINK) + 1, where)
                # a photo that fits above the caption at the usual size is not shrunk at all
                if full * ih <= band_y - CAPTION_GAP:
                    self.assertEqual(fw, int(iw * full), where)
                    self.assertLessEqual(y + fh, band_y - CAPTION_GAP, where)


if __name__ == "__main__":
    unittest.main()
