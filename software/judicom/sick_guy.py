"""A cartoon of a fellow with a cold, for the out-of-order screen: a hot water bottle on his head, a thermometer in his mouth, a red
nose, heavy eyelids, flushed cheeks.  Drawn with pygame shapes (no picture file), at four times the size and then shrunk, so the
edges come out smooth.

    img = sick_guy(380)        # a transparent 380 x 380 surface (made once per size)
"""
import math

import pygame

SKIN, SKIN_SHADE = (250, 218, 186), (232, 190, 156)
LINE = (58, 44, 40)
NOSE, NOSE_SHINE = (222, 58, 52), (250, 150, 140)
CHEEK = (246, 150, 150)
BOTTLE, BOTTLE_DARK, BOTTLE_SHINE = (214, 62, 70), (160, 38, 48), (240, 130, 136)
CAP = (90, 90, 100)
GLASS, MERCURY = (236, 244, 248), (220, 40, 40)
DROP = (120, 190, 240)

_cache = {}


def sick_guy(size):
    if size not in _cache:
        k = 4 * size / 400.0                                    # the drawing below is laid out on a 400 x 400 grid
        big = pygame.Surface((int(400 * k), int(400 * k)), pygame.SRCALPHA)
        _draw(big, k)
        _cache[size] = pygame.transform.smoothscale(big, (size, size))
    return _cache[size]


def _draw(s, k):
    def P(x, y):
        return int(x * k), int(y * k)

    def R(v):
        return max(1, int(v * k))

    # the head
    pygame.draw.circle(s, LINE, P(200, 236), R(138))
    pygame.draw.circle(s, SKIN, P(200, 236), R(132))
    pygame.draw.circle(s, SKIN_SHADE, P(200, 236), R(132), R(10), draw_bottom_left=True, draw_bottom_right=True)
    # ears
    for x in (66, 334):
        pygame.draw.circle(s, LINE, P(x, 246), R(24))
        pygame.draw.circle(s, SKIN, P(x, 246), R(19))

    # cheeks, flushed
    for x in (128, 272):
        pygame.draw.ellipse(s, CHEEK, pygame.Rect(*P(x - 30, 262), R(60), R(32)))

    # eyes: heavy lids, looking a little down, worried brows
    for x, inner in ((148, 1), (252, -1)):                     # inner: which way is towards the nose
        eye = pygame.Rect(*P(x - 30, 196), R(60), R(44))
        pygame.draw.ellipse(s, (255, 255, 255), eye)
        pygame.draw.circle(s, LINE, P(x, 230), R(10))                              # looking down, tired
        pygame.draw.ellipse(s, LINE, eye, R(4))
        pygame.draw.rect(s, SKIN, pygame.Rect(*P(x - 34, 190), R(68), R(29)))     # the heavy lid, half over the eye
        pygame.draw.arc(s, LINE, pygame.Rect(*P(x - 30, 205), R(60), R(28)), 0, math.pi, R(5))
        pygame.draw.line(s, LINE, P(x - 24 * inner, 184), P(x + 22 * inner, 170), R(6))     # brows up in the middle: worried

    # the mouth: a small wobbly frown
    pts = [P(166 + i * 4, 326 - 6 * math.sin(i / 17.0 * math.pi)) for i in range(18)]
    pygame.draw.lines(s, LINE, False, pts, R(6))

    # the thermometer, from the corner of the mouth, pointing up and out
    a = math.radians(-24)
    start, length, half = (222, 322), 150, 9
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    end = (start[0] + dx * length, start[1] + dy * length)
    body = [P(start[0] + nx * half, start[1] + ny * half), P(end[0] + nx * half, end[1] + ny * half),
            P(end[0] - nx * half, end[1] - ny * half), P(start[0] - nx * half, start[1] - ny * half)]
    pygame.draw.polygon(s, GLASS, body)
    pygame.draw.polygon(s, LINE, body, R(4))
    pygame.draw.circle(s, GLASS, P(*end), R(half))
    pygame.draw.circle(s, LINE, P(*end), R(half), R(4))
    hot = (start[0] + dx * length * 0.78, start[1] + dy * length * 0.78)           # the red line, nearly to the top
    pygame.draw.line(s, MERCURY, P(start[0] + dx * 6, start[1] + dy * 6), P(*hot), R(6))
    for i in range(1, 7):                                                         # the marks
        m = (start[0] + dx * (40 + 16 * i), start[1] + dy * (40 + 16 * i))
        pygame.draw.line(s, LINE, P(m[0] + nx * 3, m[1] + ny * 3), P(m[0] + nx * 8, m[1] + ny * 8), R(2))
    pygame.draw.circle(s, MERCURY, P(*start), R(13))                              # the bulb, in his mouth
    pygame.draw.circle(s, LINE, P(*start), R(13), R(4))

    # the red nose, with a shine
    pygame.draw.circle(s, LINE, P(200, 270), R(30))
    pygame.draw.circle(s, NOSE, P(200, 270), R(26))
    pygame.draw.circle(s, NOSE_SHINE, P(190, 260), R(8))

    # a drop of sweat
    drop = [P(330, 150), P(318, 176), P(342, 176)]
    pygame.draw.polygon(s, DROP, drop)
    pygame.draw.circle(s, DROP, P(330, 180), R(12))

    # the hot water bottle, lying across the top of his head, tilted a little
    w, h = 250, 96
    bottle = pygame.Surface((R(w + 80), R(h + 20)), pygame.SRCALPHA)
    body = pygame.Rect(R(6), R(10), R(w), R(h))
    pygame.draw.rect(bottle, LINE, body.inflate(R(10), R(10)), border_radius=R(46))
    pygame.draw.rect(bottle, BOTTLE, body, border_radius=R(42))
    for i in range(1, 8):                                                         # the ribs of the rubber
        x = body.x + R(14 + 26 * i)
        pygame.draw.line(bottle, BOTTLE_DARK, (x, body.y + R(18)), (x, body.bottom - R(18)), R(5))
    pygame.draw.line(bottle, BOTTLE_SHINE, (body.x + R(30), body.y + R(14)), (body.x + R(120), body.y + R(14)), R(6))
    neck = pygame.Rect(body.right - R(4), body.centery - R(20), R(34), R(40))
    pygame.draw.rect(bottle, LINE, neck.inflate(R(8), R(8)), border_radius=R(8))
    pygame.draw.rect(bottle, BOTTLE, neck, border_radius=R(6))
    cap = pygame.Rect(neck.right, neck.centery - R(26), R(30), R(52))
    pygame.draw.rect(bottle, LINE, cap.inflate(R(8), R(8)), border_radius=R(10))
    pygame.draw.rect(bottle, CAP, cap, border_radius=R(8))
    bottle = pygame.transform.rotate(bottle, 10)
    s.blit(bottle, bottle.get_rect(center=P(214, 92)))
