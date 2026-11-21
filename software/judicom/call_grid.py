"""Where the touch buttons go on the choose-who-to-call screen, when calling by touch is on (judicom/features.py
"touch_calls"): one for each person in the caller list, below the heading.  (The real buttons call nobody then: main.py.)
No pygame: judicom/main.py finds the one touched with it, judicom/call_view.py draws them in the same places.

    rects = tiles(len(people))          # [(x, y, w, h)], in the caller list's order
    hit(rects, x, y)                    # the index of the one at (x, y), or None
    areas = button_areas(buttons)       # calling by touch off: {"left": (x, y, w, h), ...}, over each real button's
                                        # picture, name and arrow; a touch there calls them like the button does

Up to 6 people: one wide button each, in a column; up to 12: two columns; more: three (the picture above the name).  The
buttons keep below CORNER_PX (the top corners are the hidden keypad's knock) and left of the bezel on the right.
"""
from . import config

W, H = config.SCREEN_W, config.SCREEN_H
TOP = 190                              # below the heading (and the knock's corners: config.CORNER_PX)
BOTTOM = H - 40
LEFT, RIGHT = 20, W - config.SHELL_RIGHT - 16
GAP = 16
MOST = 21                              # more than this: the first MOST (the caller list's order)
COLUMNS = ((1, 100, 150), (2, 100, 150), (3, 0, 190))      # (columns, lowest a button may be, highest)

# Calling by touch off: the arrow down to each real button, the name above it and the picture above that (call_view.py)
ARROW_TIP = H - 40                     # the arrow's point (it bobs 12 pixels lower)
NAME_Y = ARROW_TIP - 150 - 16 - 62 - 44                     # the top of the name
AREA_TOP = NAME_Y - 14 - config.LIFTED_FACE_PX - 20         # a little above the picture
AREA_GAP = 24                          # nobody between the two, in the middle: a touch there is not a call


def tiles(n):
    n = min(n, MOST)
    if n <= 0:
        return []
    area_w, area_h = RIGHT - LEFT, BOTTOM - TOP
    for cols, low, high in COLUMNS:
        rows = -(-n // cols)
        h = min(high, (area_h - (rows - 1) * GAP) // rows)
        if h >= low:
            break
    w = (area_w - (cols - 1) * GAP) // cols
    top = TOP + (area_h - (rows * h + (rows - 1) * GAP)) // 2           # the block in the middle of its room
    out = []
    for i in range(n):
        row, col = divmod(i, cols)
        if row == rows - 1 and n % cols:                               # a short last row: in the middle
            col += (cols - n % cols) / 2.0
        out.append((int(LEFT + col * (w + GAP)), top + row * (h + GAP), w, h))
    return out


def hit(rects, x, y):
    for i, (rx, ry, w, h) in enumerate(rects):
        if rx <= x < rx + w and ry <= y < ry + h:
            return i
    return None


def button_areas(buttons):
    """{key: (x, y, w, h)} for each real button that has a person: half the screen each, from above the picture to the
    bottom, with a gap between them."""
    out = {}
    for key in buttons:
        cx = config.BUTTON_X.get(key)
        if cx is None:
            continue
        if cx < W // 2:
            out[key] = (0, AREA_TOP, W // 2 - AREA_GAP // 2, H - AREA_TOP)
        else:
            out[key] = (W // 2 + AREA_GAP // 2, AREA_TOP, W - W // 2 - AREA_GAP // 2, H - AREA_TOP)
    return out
