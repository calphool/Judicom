"""Where the touch buttons go on the "Who would you like to call?" screen, when calling by touch is on (judicom/features.py
"touch_calls"): one for each person in the caller list, below the heading.  (The real buttons call nobody then: main.py.)
No pygame: judicom/main.py finds the one touched with it, judicom/call_view.py draws them in the same places.

    rects = tiles(len(people))          # [(x, y, w, h)], in the caller list's order
    hit(rects, x, y)                    # the index of the one at (x, y), or None

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
