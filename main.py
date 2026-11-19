#!/usr/bin/env python3
"""Draw the v2 news front page for make.fun news-image-20261119.

81 stories for Thursday 19 November 2026, in a dense front-page style:
dark navy masthead, a big illustrated lead panel (Shenzhen dusk, three
flags), two featured stories with art panels, twelve illustrated tiles,
a BY THE NUMBERS strip, a flat world map with 12 numbered pins, and an
ALSO list of 66 one-line briefs. Nothing invented: every story was
reported on 19 Nov 2026 (AP/Reuters/AFP/BBC/Al Jazeera/UN News roundups,
the COP31 diary, the APEC diary, and the day's wire digests).

Top of the day: the first-ever Trump-Xi-Putin trilateral in Shenzhen on
the APEC sidelines; Israel's ground operation in central Gaza; Anthropic's
record $81.3bn IPO, priced at $83, trading on Nasdaq; the Crimea bridge
attacked again; Iran widening its strikes to a US base in Kuwait and
Bahrain again; GTA VI's global rollout; Jeffries nominated as the first
Black House Speaker; Voyager 1 reaching one light-day from Earth; a
record $190.4m Van Gogh sale; the UN court's historic Myanmar genocide
verdict; North Korea firing missiles after a US-South Korea drill.

This program draws the whole page itself with the Python standard
library only: a small RGB canvas, a hand-made 5x7 bitmap font, flat
vector panel art, and a PNG encoder built on zlib. No network, no
randomness, no third-party packages -- running it twice writes the
same bytes. It writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR).

Usage: python3 main.py  ->  writes /output/entry.png (1024x1024, <=1 MiB)
"""

import binascii
import os
import struct
import sys
import zlib

W, H = 1024, 1024
MARGIN = 28
CW = W - 2 * MARGIN  # 968

PAPER = (247, 242, 231)
INK = (26, 26, 26)
RED = (178, 32, 44)
NAVY = (22, 35, 63)
NAVY_DARK = (16, 26, 48)
GOLD = (198, 158, 74)
GOLD_LT = (226, 196, 120)
GRAY = (96, 96, 96)
DARKGRAY = (60, 60, 60)
RULE = (26, 26, 26)
MAP_BG = (214, 228, 236)
LAND = (196, 176, 128)
WHITE = (255, 255, 255)
CREAM = (240, 235, 220)


# ------------------------------------------------------------------ canvas
class Canvas:
    """An RGB canvas backed by one bytearray; all drawing is slice work."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def _row(self, y):
        return y * self.w * 3

    def rect(self, x, y, w, h, col):
        """Filled rectangle, clipped to the canvas."""
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        span = bytes(col) * (x1 - x0)
        for yy in range(y0, y1):
            o = self._row(yy) + x0 * 3
            self.px[o:o + len(span)] = span

    def hline(self, x, y, w, col, thick=1):
        self.rect(x, y, w, thick, col)

    def vline(self, x, y, h, col, thick=1):
        self.rect(x, y, thick, h, col)

    def line(self, x0, y0, x1, y1, col, thick=1):
        """Bresenham line with square brush."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        half = thick // 2
        while True:
            self.rect(x0 - half, y0 - half, thick, thick, col)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, col):
        """Filled circle via horizontal spans."""
        r = int(r)
        for dy in range(-r, r + 1):
            half = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - half, cy + dy, half * 2 + 1, 1, col)

    def ring(self, cx, cy, r, col, thick=1):
        for rr in range(r, r - thick, -1):
            if rr < 0:
                continue
            for dy in range(-rr, rr + 1):
                half = int((rr * rr - dy * dy) ** 0.5)
                self.rect(cx - half, cy + dy, 1, 1, col)
                self.rect(cx + half, cy + dy, 1, 1, col)

    def ellipse(self, cx, cy, rx, ry, col):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            half = int(rx * (t ** 0.5)) if t > 0 else 0
            self.rect(cx - half, cy + dy, half * 2 + 1, 1, col)

    def polygon(self, pts, col):
        """Scanline fill (even-odd) of a polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, yy0 = pts[i]
                x1, yy1 = pts[(i + 1) % n]
                if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                    t = (y - yy0) / float(yy1 - yy0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa, xb = int(xs[i] + 0.5), int(xs[i + 1] + 0.5)
                if xb > xa:
                    self.rect(xa, y, xb - xa, 1, col)

    def vgrad(self, x, y, w, h, top, bottom):
        """Vertical gradient, one row slice per line."""
        for i in range(h):
            t = i / max(1, h - 1)
            col = tuple(int(top[c] + (bottom[c] - top[c]) * t)
                        for c in range(3))
            self.rect(x, y + i, w, 1, col)

    def outline(self, x, y, w, h, col, thick=1):
        self.rect(x, y, w, thick, col)
        self.rect(x, y + h - thick, w, thick, col)
        self.rect(x, y, thick, h, col)
        self.rect(x + w - thick, y, thick, h, col)


def star_points(cx, cy, r_out, r_in, rot=-90.0):
    """Five-point star vertices, alternating outer/inner radius."""
    import math
    pts = []
    for i in range(10):
        ang = math.radians(rot + i * 36.0)
        r = r_out if i % 2 == 0 else r_in
        pts.append((int(cx + r * math.cos(ang)),
                    int(cy + r * math.sin(ang))))
    return pts


def png_bytes(cv):
    """Encode the canvas as a PNG (color type 2, filter 0 per row)."""
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# -------------------------------------------------------------------- font
# Hand-made 5x7 bitmap font. Each glyph is 7 rows of 5 cells ('1' = on).
# Proportional advances: default 6, narrow 4, wide 7, space 4.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01110", "10001", "10001", "01111", "00010", "01100"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "00010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    "q": ("00000", "00000", "01111", "10001", "10001", "01111", "00010"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01000", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "10001", "01111", "00110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "–": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "—": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "*": ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "•": ("00000", "00000", "01110", "11111", "11111", "01110", "00000"),
    "·": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    "°": ("01100", "10010", "01100", "00000", "00000", "00000", "00000"),
    "€": ("01110", "10001", "10000", "11110", "10000", "10001", "01110"),
    "×": ("00000", "00000", "10001", "01110", "01110", "10001", "00000"),
}

# Every glyph is exactly 7 rows; descenders live in rows 5-6.
_NARROW = set("il1Ijt.,:;'\"()![]")
_WIDE = set("mwMW")


def adv(ch):
    """Advance width of one character, in font units."""
    if ch == " ":
        return 4
    if ch in _NARROW:
        return 4
    if ch in _WIDE:
        return 7
    return 6


def text_w(text, scale, tracking=0):
    """Pixel width of text at the given scale."""
    w = 0
    for ch in text:
        w += adv(ch) * scale + tracking
    return w - tracking if text else 0


def draw_glyph(cv, x, y, ch, scale, col):
    """Draw one glyph; runs of on-pixels become filled rectangles."""
    rows = FONT.get(ch)
    if rows is None:
        rows = FONT["?"]
    for r, row in enumerate(rows):
        c = 0
        while c < 5:
            if row[c] == "1":
                c0 = c
                while c + 1 < 5 and row[c + 1] == "#":
                    c += 1
                cv.rect(x + c0 * scale, y + r * scale,
                        (c - c0 + 1) * scale, scale, col)
            c += 1


def draw_text(cv, x, y, text, scale, col, bold=False, tracking=0,
              align="left", box_w=None):
    """Draw text; align left/center/right within box_w when given."""
    w = text_w(text, scale, tracking)
    if align == "center" and box_w is not None:
        x += (box_w - w) // 2
    elif align == "right" and box_w is not None:
        x += box_w - w
    cx = x
    for ch in text:
        draw_glyph(cv, cx, y, ch, scale, col)
        if bold:
            draw_glyph(cv, cx + 1, y, ch, scale, col)
        cx += adv(ch) * scale + tracking
    return w


def draw_tracked(cv, x, y, text, scale, col, tracking=2):
    return draw_text(cv, x, y, text, scale, col, tracking=tracking)


def wrap_text(text, scale, max_w, tracking=0):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            trial = wd if not cur else cur + " " + wd
            if text_w(trial, scale, tracking) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
    return lines


# ------------------------------------------------------------------- icons
def draw_icon(cv, x, y, s, kind):
    """A pictogram in a coloured s*s square (flat vector style)."""
    bg = {"bridge": (38, 84, 160), "blast": (178, 32, 44),
          "game": (110, 70, 150), "ballot": (36, 110, 70),
          "probe": (20, 90, 110), "chip": (30, 30, 40),
          "chart": (24, 90, 60), "storm": (70, 80, 100),
          "leaf": (46, 125, 60), "art": (190, 110, 30),
          "scales": (120, 85, 40), "rocket": (40, 50, 110)}.get(kind, GRAY)
    cv.rect(x, y, s, s, bg)
    w = WHITE
    u = s // 40  # unit; icons are drawn for s = 40
    if kind == "bridge":
        cv.rect(x + 6, y + 24, 10, 3, w)
        cv.rect(x + 24, y + 24, 10, 3, w)
        cv.polygon([(x + 6, y + 26), (x + 11, y + 14), (x + 16, y + 26)], w)
        cv.polygon([(x + 24, y + 26), (x + 29, y + 14), (x + 34, y + 26)], w)
        cv.polygon([(x + 17, y + 25), (x + 21, y + 33), (x + 24, y + 31),
                    (x + 20, y + 24)], w)
        cv.circle(x + 31, y + 10, 4, (255, 210, 110))
    elif kind == "blast":
        cx, cy = x + 20, y + 20
        cv.polygon([(cx, cy - 14), (cx + 4, cy - 4), (cx + 14, cy - 6),
                    (cx + 7, cy + 2), (cx + 12, cy + 10), (cx + 2, cy + 8),
                    (cx, cy + 15), (cx - 3, cy + 7), (cx - 13, cy + 9),
                    (cx - 7, cy + 1), (cx - 14, cy - 5), (cx - 4, cy - 5)],
                   (255, 210, 110))
        cv.circle(cx, cy, 4, w)
    elif kind == "game":
        cv.rect(x + 6, y + 14, 28, 16, w)
        cv.circle(x + 12, y + 20, 3, (110, 70, 150))
        cv.circle(x + 28, y + 20, 3, (110, 70, 150))
        cv.hline(x + 11, y + 27, 5, (110, 70, 150), 2)
        cv.hline(x + 24, y + 26, 5, (110, 70, 150), 2)
    elif kind == "ballot":
        cv.rect(x + 10, y + 16, 20, 16, w)
        cv.rect(x + 16, y + 12, 8, 4, w)
        cv.line(x + 13, y + 24, x + 18, y + 29, (36, 110, 70), 3)
        cv.line(x + 18, y + 29, x + 27, y + 19, (36, 110, 70), 3)
    elif kind == "probe":
        cv.polygon([(x + 8, y + 8), (x + 26, y + 8), (x + 17, y + 24)], w)
        cv.line(x + 17, y + 24, x + 30, y + 32, w, 3)
        cv.rect(x + 28, y + 30, 6, 6, w)
        for dx, dy in ((30, 8), (34, 14), (26, 12)):
            cv.circle(x + dx, y + dy, 1, (255, 210, 110))
    elif kind == "chip":
        cv.rect(x + 12, y + 12, 16, 16, w, )
        cv.rect(x + 17, y + 17, 6, 6, (30, 30, 40))
        for i in range(3):
            cv.vline(x + 14 + i * 6, y + 6, 6, w, 2)
            cv.vline(x + 14 + i * 6, y + 28, 6, w, 2)
            cv.hline(x + 6, y + 14 + i * 6, 6, w, 2)
            cv.hline(x + 28, y + 14 + i * 6, 6, w, 2)
    elif kind == "chart":
        for bx, bh in ((8, 10), (16, 16), (24, 22), (32, 30)):
            cv.rect(x + bx, y + 34 - bh, 5, bh, (120, 220, 150))
        cv.line(x + 8, y + 22, x + 34, y + 6, (255, 210, 110), 2)
    elif kind == "storm":
        cv.circle(x + 14, y + 16, 7, w)
        cv.circle(x + 22, y + 13, 8, w)
        cv.circle(x + 28, y + 17, 6, w)
        cv.rect(x + 8, y + 18, 26, 5, w)
        cv.polygon([(x + 20, y + 24), (x + 15, y + 32), (x + 20, y + 32),
                    (x + 17, y + 38), (x + 25, y + 28), (x + 20, y + 28)],
                   (255, 210, 110))
    elif kind == "leaf":
        cv.polygon([(x + 8, y + 32), (x + 8, y + 16), (x + 22, y + 8),
                    (x + 32, y + 18), (x + 28, y + 32)], (150, 220, 130))
        cv.line(x + 10, y + 32, x + 30, y + 12, (20, 80, 35), 2)
    elif kind == "art":
        cv.rect(x + 7, y + 7, 26, 26, w)
        cv.rect(x + 10, y + 10, 20, 20, (190, 110, 30))
        cv.circle(x + 24, y + 16, 4, (255, 210, 110))
        cv.polygon([(x + 10, y + 30), (x + 18, y + 18), (x + 26, y + 30)],
                   (60, 90, 60))
        cv.polygon([(x + 20, y + 30), (x + 26, y + 22), (x + 30, y + 30)],
                   (90, 120, 70))
    elif kind == "scales":
        cv.vline(x + 20, y + 8, 24, w, 2)
        cv.hline(x + 8, y + 10, 24, w, 2)
        cv.line(x + 8, y + 10, x + 4, y + 22, w, 2)
        cv.line(x + 8, y + 10, x + 12, y + 22, w, 2)
        cv.polygon([(x + 3, y + 22), (x + 13, y + 22), (x + 8, y + 27)], w)
        cv.line(x + 32, y + 10, x + 28, y + 22, w, 2)
        cv.line(x + 32, y + 10, x + 36, y + 22, w, 2)
        cv.polygon([(x + 27, y + 22), (x + 37, y + 22), (x + 32, y + 27)], w)
        cv.hline(x + 14, y + 32, 12, w, 2)
    elif kind == "rocket":
        cv.polygon([(x + 20, y + 5), (x + 26, y + 14), (x + 26, y + 26),
                    (x + 20, y + 32), (x + 14, y + 26), (x + 14, y + 14)],
                   w)
        cv.circle(x + 20, y + 17, 3, (40, 50, 110))
        cv.polygon([(x + 14, y + 24), (x + 8, y + 32), (x + 14, y + 30)], w)
        cv.polygon([(x + 26, y + 24), (x + 32, y + 32), (x + 26, y + 30)], w)
        cv.polygon([(x + 17, y + 32), (x + 20, y + 38), (x + 23, y + 32)],
                   (255, 160, 60))
    del u


# ------------------------------------------------------------------- flags
def draw_flag(cv, x, y, w, h, kind):
    """Small flag, drawn with rectangles (and stars for China)."""
    if kind == "us":
        for i in range(7):
            cv.rect(x, y + i * h // 7, w, h // 7 + 1,
                    (178, 32, 44) if i % 2 == 0 else WHITE)
        cw, ch = w * 2 // 5, h * 4 // 7
        cv.rect(x, y, cw, ch, (30, 50, 110))
        for r in range(3):
            for c in range(4):
                cv.rect(x + 3 + c * (cw // 4), y + 3 + r * (ch // 3), 2, 2,
                        WHITE)
    elif kind == "china":
        cv.rect(x, y, w, h, (200, 30, 30))
        cv.polygon(star_points(x + w // 4, y + h // 3, 7, 3),
                   (255, 215, 0))
        for sx, sy in ((x + w * 3 // 5, y + h // 5),
                       (x + w * 3 // 4, y + h * 2 // 5),
                       (x + w * 3 // 4, y + h * 3 // 5),
                       (x + w * 3 // 5, y + h * 4 // 5)):
            cv.polygon(star_points(sx, sy, 3, 1), (255, 215, 0))
    elif kind == "russia":
        cv.rect(x, y, w, h // 3 + 1, WHITE)
        cv.rect(x, y + h // 3, w, h // 3 + 1, (30, 80, 170))
        cv.rect(x, y + 2 * h // 3, w, h - 2 * h // 3, (200, 30, 30))


# -------------------------------------------------------------- panel art
def panel_shenzhen(cv, x, y, w, h):
    """Dusk over Shenzhen: orange-purple sky, sun, skyline, three flags."""
    ground = y + int(h * 0.72)
    cv.vgrad(x, y, w, ground - y, (232, 128, 52), (146, 68, 116))
    sx, sy, sr = x + w - 52, y + 26, 13
    cv.circle(sx, sy, sr, (255, 226, 140))
    cv.rect(x, ground, w, y + h - ground, (26, 28, 58))
    heights = [26, 40, 32, 48, 36, 56, 30, 44, 38, 52, 28, 42]
    bw = w // len(heights)
    for i, bh in enumerate(heights):
        bh = bh * h // 150
        bx = x + i * bw
        cv.rect(bx + 1, ground - bh, bw - 2, bh, (26, 28, 58))
        if i % 3 == 0:
            cv.rect(bx + bw // 2 - 1, ground - bh - 8, 2, 8, (26, 28, 58))
        for wy in range(ground - bh + 6, ground - 4, 9):
            for wx in (bx + 5, bx + bw - 9):
                if (wx + wy) % 3 == 0:
                    cv.rect(wx, wy, 2, 2, (255, 210, 110))
    kinds = ["us", "china", "russia"]
    fw, fh = 56, 36
    gap = (w - len(kinds) * fw) // (len(kinds) + 1)
    for i, kind in enumerate(kinds):
        fx = x + gap + i * (fw + gap)
        fy = ground - fh - 16
        cv.rect(fx + fw // 2 - 1, fy, 2, ground - fy, CREAM)
        draw_flag(cv, fx, fy, fw, fh, kind)


def panel_gaza_night(cv, x, y, w, h):
    """Night over central Gaza: tents, searchlights, flare, smoke.

    All positions are fractions of the panel size, so the art works at
    any width/height.
    """
    horizon = y + int(h * 0.62)
    cv.vgrad(x, y, w, horizon - y, (8, 18, 42), (30, 50, 92))
    for fx, fy, r in ((0.05, 0.10, 1), (0.13, 0.22, 1), (0.22, 0.08, 1),
                      (0.32, 0.16, 2), (0.40, 0.06, 1), (0.50, 0.18, 1),
                      (0.60, 0.08, 2), (0.70, 0.20, 1), (0.79, 0.10, 1),
                      (0.89, 0.22, 1), (0.96, 0.12, 1), (0.17, 0.34, 1),
                      (0.53, 0.32, 1), (0.76, 0.34, 1)):
        cv.circle(x + int(fx * w), y + int(fy * h), r, (235, 238, 245))
    cv.rect(x, horizon, w, y + h - horizon, (24, 22, 20))
    for fx, fw, fh in ((0.05, 0.15, 0.20), (0.23, 0.19, 0.26),
                       (0.47, 0.17, 0.22), (0.68, 0.20, 0.28),
                       (0.86, 0.15, 0.18)):
        tx, tw = x + int(fx * w), int(fw * w)
        th = int(fh * h)
        cv.polygon([(tx, horizon), (tx + tw // 2, horizon - th),
                    (tx + tw, horizon)], (120, 110, 92))
        cv.polygon([(tx + tw // 2 - 3, horizon),
                    (tx + tw // 2, horizon - th // 2),
                    (tx + tw // 2 + 3, horizon)], (40, 36, 30))
    for ex, ey in ((0.50, 0.12), (0.70, 0.26)):
        cv.polygon([(x + int(0.07 * w), horizon - 6),
                    (x + int(ex * w), y + int(ey * h) - 3),
                    (x + int(ex * w), y + int(ey * h) + 3)],
                   (220, 220, 190))
    gx, gy = x + int(0.84 * w), horizon - 6
    for frac, col in ((1.00, (198, 88, 28)), (0.72, (228, 128, 38)),
                      (0.48, (248, 188, 78)), (0.26, (255, 230, 150))):
        cv.circle(gx, gy, max(2, int(22 * frac * h / 100)), col)
    for px, py, pr in ((-0.05, -0.20, 10), (0.0, -0.30, 12),
                       (0.05, -0.22, 9), (0.01, -0.40, 8)):
        cv.circle(gx + int(px * w), gy + int(py * h), max(2, pr * h // 100),
                  (88, 88, 96))
    cv.line(gx - 30, gy - 30, gx + 6, gy - 8, (255, 240, 180), 2)


def panel_ipo(cv, x, y, w, h):
    """Nasdaq debut: dark board, rising green bars, gold $81.3bn tag."""
    cv.vgrad(x, y, w, h, (10, 22, 48), (24, 52, 92))
    for gy in (0.22, 0.44, 0.66):
        cv.hline(x + 8, y + int(gy * h), w - 16, (60, 80, 120), 1)
    bars = [18, 26, 22, 34, 30, 44, 40, 56]
    bw = max(4, w // 12)
    gap = max(2, w // 48)
    bx0 = x + 10
    base = y + h - 14
    for i, bh in enumerate(bars):
        bx = bx0 + i * (bw + gap)
        bh_px = bh * h // 100
        cv.rect(bx, base - bh_px, bw, bh_px, (46, 160, 90))
    pts = [(bx0 + 4, base - 18), (bx0 + int(0.30 * w), base - 34),
           (bx0 + int(0.55 * w), base - 30), (bx0 + int(0.80 * w), base - 56),
           (bx0 + w - 24, base - 62)]
    for a, b in zip(pts, pts[1:]):
        cv.line(a[0], a[1], b[0], b[1], (120, 220, 150), 3)
    ex, ey = pts[-1]
    cv.polygon([(ex, ey), (ex - 14, ey - 4), (ex - 12, ey + 8)],
               (120, 220, 150))
    tag = "$81.3bn"
    tscale = 3 if text_w(tag, 3) <= w - 20 else 2
    draw_text(cv, x + w - text_w(tag, tscale) - 8, y + 8, tag, tscale,
              GOLD_LT)
    draw_text(cv, x + w - text_w("BIGGEST IPO EVER", 1) - 8,
              y + 8 + tscale * 7 + 4, "BIGGEST IPO EVER", 1, WHITE)


# -------------------------------------------------------------------- map
# Simplified continent outlines (lon, lat). Stylised, not survey-grade.
CONTINENTS = [
    # North America
    [(-168, 66), (-145, 70), (-130, 71), (-115, 69), (-100, 69), (-90, 68),
     (-85, 66), (-80, 70), (-75, 72), (-65, 62), (-60, 55), (-55, 47),
     (-60, 45), (-65, 44), (-70, 42), (-74, 39), (-76, 35), (-80, 32),
     (-81, 26), (-84, 30), (-89, 29), (-97, 26), (-100, 20), (-105, 20),
     (-110, 23), (-114, 28), (-117, 32), (-122, 37), (-124, 42),
     (-124, 48), (-128, 52), (-135, 58), (-145, 60), (-155, 58),
     (-162, 55), (-168, 66)],
    # South America
    [(-78, 8), (-72, 11), (-64, 10), (-58, 6), (-52, 4), (-44, -3),
     (-35, -8), (-38, -15), (-40, -22), (-48, -27), (-52, -33),
     (-58, -38), (-65, -45), (-68, -52), (-70, -54), (-73, -50),
     (-73, -40), (-72, -30), (-70, -18), (-76, -13), (-80, -6),
     (-81, -1), (-78, 4), (-78, 8)],
    # Africa
    [(-17, 15), (-16, 21), (-11, 27), (-6, 33), (0, 36), (9, 37),
     (11, 34), (19, 32), (25, 32), (32, 31), (34, 28), (37, 22),
     (39, 18), (43, 12), (48, 11), (51, 10), (48, 2), (41, -4),
     (40, -12), (36, -18), (33, -26), (28, -33), (20, -35), (17, -32),
     (14, -27), (12, -18), (13, -12), (9, -4), (9, 4), (4, 6), (-4, 5),
     (-8, 5), (-13, 8), (-17, 12), (-17, 15)],
    # Europe
    [(-10, 36), (-9, 38), (-9, 43), (-4, 44), (-2, 47), (-1, 50), (2, 51),
     (5, 53), (8, 55), (8, 57), (10, 58), (12, 56), (18, 56), (21, 55),
     (21, 59), (24, 60), (28, 61), (30, 62), (30, 66), (32, 70), (40, 68),
     (44, 66), (40, 60), (36, 58), (34, 55), (30, 50), (28, 46), (26, 44),
     (23, 40), (22, 40), (19, 42), (16, 44), (12, 44), (8, 44), (6, 43),
     (3, 42), (0, 40), (-2, 37), (-6, 36), (-9, 37), (-10, 36)],
    # Asia
    [(30, 70), (38, 69), (44, 68), (50, 69), (58, 69), (66, 69), (72, 71),
     (80, 72), (88, 73), (96, 74), (104, 75), (112, 74), (120, 73),
     (128, 72), (136, 72), (142, 71), (150, 70), (156, 69), (160, 66),
     (162, 60), (158, 56), (156, 52), (150, 59), (144, 59), (141, 52),
     (140, 46), (138, 42), (134, 38), (130, 35), (127, 35), (124, 32),
     (122, 30), (120, 27), (116, 23), (112, 20), (108, 18), (105, 14),
     (103, 10), (100, 8), (98, 12), (96, 16), (94, 18), (91, 22),
     (89, 22), (86, 20), (83, 17), (80, 13), (77, 8), (75, 10),
     (73, 16), (70, 20), (67, 24), (64, 25), (61, 25), (58, 26),
     (55, 26), (52, 27), (50, 29), (48, 30), (45, 32), (42, 34),
     (40, 36), (36, 36), (33, 36), (30, 36), (28, 40), (28, 44),
     (30, 46), (33, 48), (36, 52), (40, 56), (40, 60), (38, 64),
     (34, 68), (30, 70)],
    # Australia
    [(113, -22), (114, -30), (115, -34), (118, -35), (124, -33),
     (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
     (143, -39), (146, -39), (149, -37), (150, -37), (153, -32),
     (153, -27), (150, -23), (147, -19), (144, -15), (142, -11),
     (137, -12), (135, -12), (132, -11), (130, -13), (126, -14),
     (123, -17), (120, -20), (116, -21), (113, -22)],
    # United Kingdom
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51),
     (-2, 50), (-5, 50)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (137, 36), (139, 38), (141, 40),
     (142, 42), (140, 44), (138, 40), (136, 37), (133, 35), (131, 33),
     (130, 31)],
    # Indonesia
    [(95, 5), (98, 3), (101, 0), (104, -2), (106, -6), (110, -7),
     (114, -8), (118, -9), (120, -10), (122, -9), (125, -9), (128, -7),
     (131, -4), (132, -2), (130, 0), (128, 1), (126, 1), (124, 1),
     (121, 0), (119, 0), (116, 1), (114, 2), (111, 1), (108, -1),
     (105, -3), (103, -1), (100, 0), (97, 2), (95, 5)],
    # New Zealand
    [(167, -45), (170, -42), (173, -40), (175, -38), (177, -38),
     (175, -41), (172, -43), (169, -46), (167, -45)],
    # Madagascar
    [(44, -16), (47, -15), (50, -16), (49, -20), (47, -24), (45, -25),
     (44, -21), (44, -16)],
]


def draw_map(cv, x, y, w, h, pins):
    """Flat world map with numbered red pins."""
    cv.rect(x, y, w, h, MAP_BG)
    cv.outline(x, y, w, h, (150, 150, 140), 1)
    lon0, lon1, lat0, lat1 = -180.0, 180.0, 83.0, -58.0

    def proj(lon, lat):
        px = x + (lon - lon0) / (lon1 - lon0) * w
        py = y + (lat0 - lat) / (lat0 - lat1) * h
        return (int(px), int(py))

    for poly in CONTINENTS:
        cv.polygon([proj(lon, lat) for lon, lat in poly], LAND)
    for num, (plon, plat) in pins:
        px, py = proj(plon, plat)
        cv.circle(px, py, 7, RED)
        cv.ring(px, py, 7, WHITE, 1)
        s = str(num)
        sw = text_w(s, 1)
        draw_text(cv, px - sw // 2, py - 4, s, 1, WHITE)


# -------------------------------------------------------------------- data
# 81 stories for Thursday 19 November 2026: 1 lead + 2 featured + 12
# illustrated tiles + 66 one-line briefs. All reported on 19 Nov 2026.

LEAD = {
    "num": 1, "kicker": "ASIA · DIPLOMACY",
    "headline": "Trump, Xi and Putin meet in Shenzhen",
    "deck": ("First-ever trilateral of the three leaders, on the APEC "
             "sidelines. Trump joins the plenary."),
    "pin": (114.1, 22.5),
}

FEATURED = [
    {"num": 2, "kicker": "MIDDLE EAST · WAR",
     "headline": "Israel launches ground operation in Gaza",
     "deck": ("Troops enter central Gaza. Families flee."),
     "pin": (30.0, 34.0)},
    {"num": 3, "kicker": "MARKETS · TECHNOLOGY",
     "headline": "Anthropic's $81.3bn IPO, biggest ever",
     "deck": ("Record debut at $83 on Nasdaq."),
     "pin": (-74.0, 40.7)},
]

MEDIUM = [
    {"num": 4, "kicker": "EUROPE · WAR", "icon": "bridge",
     "headline": "Crimea bridge hit again",
     "deck": "Traffic halted",
     "pin": (35.0, 46.0)},
    {"num": 5, "kicker": "MIDDLE EAST · WAR", "icon": "blast",
     "headline": "Iran hits Kuwait, Bahrain",
     "deck": "Kuwait base hit",
     "pin": (51.0, 27.0)},
    {"num": 6, "kicker": "CULTURE · GAMING", "icon": "game",
     "headline": "GTA VI rolls out worldwide",
     "deck": "Vice City opens",
     "pin": (-80.2, 25.8)},
    {"num": 7, "kicker": "AMERICAS · POLITICS", "icon": "ballot",
     "headline": "First Black Speaker: Jeffries",
     "deck": "Democrats pick",
     "pin": None},
    {"num": 8, "kicker": "SCIENCE · SPACE", "icon": "probe",
     "headline": "Voyager 1 reaches one light-day",
     "deck": "48 years on",
     "pin": (-104.0, 32.0)},
    {"num": 9, "kicker": "TRADE · CHIPS", "icon": "chip",
     "headline": "Nvidia halts H-chip China sales",
     "deck": "Hopper ends",
     "pin": (-121.9, 37.3)},
    {"num": 10, "kicker": "ECONOMY · RATES", "icon": "chart",
     "headline": "Fed: more hikes likely",
     "deck": "Minutes hint hikes",
     "pin": None},
    {"num": 11, "kicker": "ASIA · WEATHER", "icon": "storm",
     "headline": "Cyclone Akvan nears Indian coast",
     "deck": "Landfall Friday",
     "pin": (79.0, 14.0)},
    {"num": 12, "kicker": "CLIMATE · COP31", "icon": "leaf",
     "headline": "COP31 crunch: 21 issues open",
     "deck": "21 issues open",
     "pin": None},
    {"num": 13, "kicker": "CULTURE · ART", "icon": "art",
     "headline": "Van Gogh sells for record $190.4m",
     "deck": "Nazi-row sale tops",
     "pin": None},
    {"num": 14, "kicker": "WORLD · JUSTICE", "icon": "scales",
     "headline": "Myanmar faces genocide verdict",
     "deck": "UN court rules",
     "pin": (94.0, 25.0)},
    {"num": 15, "kicker": "ASIA · SECURITY", "icon": "rocket",
     "headline": "N. Korea fires missiles",
     "deck": "After US drill",
     "pin": (127.5, 39.5)},
]

NUMBERS = [
    ("$81.3bn", "Anthropic record IPO raise"),
    ("€45bn", "EU loan for Ukraine"),
    ("$190.4m", "Van Gogh record sale"),
    ("145 km/h", "Akvan gusts at landfall"),
    ("1 light-day", "Voyager 1 from Earth"),
    ("$1.4tn", "Anthropic debut value"),
]

ALSO = [
    "APEC: Trump talks",
    "Berlin: Kyiv talks",
    "Putin-Xi talks",
    "Xi meets Carney",
    "Canada: right deal",
    "Panama: ships row",
    "US: Huang testifies",
    "Taiwan: Liu leads",
    "Taiwan: spy bill",
    "Taiwan: vote probe",
    "US: Trump vs Vance",
    "US-China: barriers",
    "Russia: agent held",
    "Haiti: Bukele raid",
    "Microsoft: brief",
    "NSA: net outage",
    "US: stockpiling up",
    "Epstein: $582m",
    "Somalia: UAE bases",
    "Libya: drug haul",
    "Saudi: all clear",
    "France: Melenchon",
    "France: retirees",
    "Spain: clashes",
    "Australia: settlers",
    "Australia: Putin pic",
    "India: cyclone rail",
    "India: Japan talks",
    "Prabowo: Shenzhen",
    "Korea: Lee ends",
    "Islam tops by 2035",
    "Science: lost years",
    "Oil: WTI down 3.2%",
    "BI rates up 25bp",
    "Markets: slowdown",
    "$100bn backer gains",
    "Nvidia: Vera Rubin",
    "Micron: -20%",
    "Fitch: AI bond risks",
    "Gulf: tanker stuck",
    "COP31: stocktake",
    "COP31: 152 jets",
    "COP31: farm talks",
    "COP31: kelp seat",
    "Merck rabies jab",
    "Deep sea: leases",
    "Estonia: border",
    "Prague: media rally",
    "N. Korea: missiles",
    "IAEA: Yongbyon",
    "US: AI warning",
    "COPD Day marked",
    "Congress vs Modi",
    "Climber survives",
    "Berlin: spy charge",
    "McDonald's inquiry",
    "ESA: space laws",
    "Spain: strike",
    "Stacy Keach, 85",
    "DPP defends cities",
    "UK: GTA VI queues",
    "Australia: migrants",
    "China: micro EVs",
    "Germany: hybrids",
    "BJP: temple row",
    "Xi meets To Lam",
]

FOOTER1 = ("Every story here happened or was first reported on Thursday "
           "19 November 2026. Disputed claims are attributed.")
FOOTER2 = "Sources: AP, Reuters, AFP, BBC, Al Jazeera, UN News. Original drawings."


# ------------------------------------------------------------------ layout
VIOLATIONS = []


def check_fit(label, width, max_w):
    if width > max_w:
        VIOLATIONS.append("%s: %dpx > %dpx" % (label, width, max_w))


def draw_masthead(cv):
    cv.rect(0, 0, W, 84, NAVY)
    draw_tracked(cv, MARGIN, 10, "THE DAY IN WORLD NEWS", 2, GOLD_LT, 2)
    right = "81 STORIES · 6 CONTINENTS · ONE PAGE"
    draw_tracked(cv, W - MARGIN - text_w(right, 2, 2), 10, right, 2,
                 GOLD_LT, 2)
    check_fit("masthead title", text_w("Thursday 19 November 2026", 5), CW)
    draw_text(cv, MARGIN, 26, "Thursday 19 November 2026", 5, WHITE)
    sub = ("Every story on this page happened, or was first reported, "
           "on this day.")
    check_fit("masthead subtitle", text_w(sub, 2), CW)
    draw_text(cv, MARGIN, 66, sub, 2, (205, 205, 195))
    cv.rect(0, 84, W, 3, GOLD)


def draw_lead(cv, y):
    """Big Shenzhen panel left (620x140), lead story text right."""
    ax, aw, ah = MARGIN, 620, 140
    panel_shenzhen(cv, ax, y, aw, ah)
    cv.rect(ax, y + ah - 15, aw, 15, NAVY_DARK)
    draw_tracked(cv, ax + 6, y + ah - 11, "SHENZHEN · APEC SUMMIT", 2,
                 WHITE, 1)
    cv.outline(ax, y, aw, ah, INK, 2)
    tx, tw = 664, 332
    cv.circle(tx + 10, y + 11, 9, RED)
    draw_text(cv, tx + 7, y + 4, "1", 1, WHITE)
    draw_tracked(cv, tx + 24, y + 4, LEAD["kicker"], 2, RED, 1)
    yy = y + 22
    for ln in wrap_text(LEAD["headline"], 3, tw):
        draw_text(cv, tx, yy, ln, 3, INK)
        yy += 21
    yy += 4
    for ln in wrap_text(LEAD["deck"], 2, tw):
        draw_text(cv, tx, yy, ln, 2, DARKGRAY)
        yy += 14
    yy += 6
    cv.rect(tx, yy, 60, 2, GOLD)
    draw_text(cv, tx, yy + 6, "APEC 2026 · SHENZHEN, CHINA", 1, GRAY)


def draw_featured(cv, y):
    """Two stories side by side: art panel 200x132 left, text right."""
    fx = [MARGIN, MARGIN + 472 + 24]
    captions = ["CENTRAL GAZA · NIGHT", "NASDAQ · $81.3BN IPO"]
    panels = [panel_gaza_night, panel_ipo]
    for i, st in enumerate(FEATURED):
        x = fx[i]
        panels[i](cv, x, y, 200, 132)
        cv.rect(x, y + 132 - 15, 200, 15, NAVY_DARK)
        draw_tracked(cv, x + 6, y + 132 - 11, captions[i], 1, WHITE, 1)
        cv.outline(x, y, 200, 132, INK, 2)
        tx, tw = x + 212, 260
        cv.circle(tx + 10, y + 11, 9, RED)
        draw_text(cv, tx + 7, y + 4, str(st["num"]), 1, WHITE)
        draw_tracked(cv, tx + 24, y + 4, st["kicker"], 2, RED, 1)
        yy = y + 22
        lines = wrap_text(st["headline"], 2, tw)
        check_fit("featured %d headline lines" % st["num"], len(lines), 3)
        for ln in lines:
            draw_text(cv, tx, yy, ln, 2, INK)
            yy += 14
        yy += 4
        deck_lines = wrap_text(st["deck"], 2, tw)
        check_fit("featured %d deck lines" % st["num"], len(deck_lines), 3)
        for ln in deck_lines:
            draw_text(cv, tx, yy, ln, 2, DARKGRAY)
            yy += 14


def draw_tiles(cv, y):
    """Twelve tiles, 4 columns x 3 rows, each 233x60."""
    colw, gap = 233, 12
    for idx, st in enumerate(MEDIUM):
        r, c = divmod(idx, 4)
        x = MARGIN + c * (colw + gap)
        ty = y + r * 64
        draw_icon(cv, x, ty + 10, 40, st["icon"])
        tx, tw = x + 48, colw - 48
        kick = "%d %s" % (st["num"], st["kicker"])
        check_fit("tile %d kicker" % st["num"], text_w(kick, 1), tw)
        draw_text(cv, tx, ty + 2, kick, 1, RED)
        yy = ty + 11
        lines = wrap_text(st["headline"], 2, tw, tracking=-1)
        check_fit("tile %d headline lines" % st["num"], len(lines), 2)
        for ln in lines:
            draw_text(cv, tx, yy, ln, 2, INK, tracking=-1)
            yy += 14
        deck_lines = wrap_text(st["deck"], 2, tw, tracking=-1)
        check_fit("tile %d deck lines" % st["num"], len(deck_lines), 1)
        draw_text(cv, tx, ty + 41, deck_lines[0] if deck_lines else "", 2,
                  DARKGRAY, tracking=-1)


def draw_numbers(cv, y):
    draw_text(cv, MARGIN, y, "BY THE", 2, RED)
    draw_text(cv, MARGIN, y + 16, "NUMBERS", 2, RED)
    nx0, colw = 130, 144
    for i, (num, label) in enumerate(NUMBERS):
        nx = nx0 + i * colw
        scale = 3 if text_w(num, 3) <= 140 else 2
        draw_text(cv, nx, y, num, scale, NAVY)
        yy = y + 24
        for ln in wrap_text(label, 1, 140):
            draw_text(cv, nx, yy, ln, 1, DARKGRAY)
            yy += 9


def draw_bottom(cv, y):
    """Map left (260x240), ALSO list right (3 cols x 22 rows)."""
    draw_tracked(cv, MARGIN, y, "WHERE IT HAPPENED", 2, INK, 2)
    draw_tracked(cv, 308, y, "ALSO ON THURSDAY 19 NOVEMBER — 66 MORE",
                 2, INK, 2)
    my = y + 18
    pins = [(s["num"], s["pin"]) for s in [LEAD] + FEATURED + MEDIUM
            if s["pin"] is not None]
    draw_map(cv, MARGIN, my, 260, 240, pins)
    draw_text(cv, MARGIN, my + 244, "Numbered dots mark the big stories",
              1, GRAY)
    start_num = 16
    cols_x = [308, 537, 766]
    per_col = 22
    for col_i in range(3):
        chunk = ALSO[col_i * per_col:(col_i + 1) * per_col]
        cx = cols_x[col_i]
        yy = my
        for j, item in enumerate(chunk):
            num = start_num + col_i * per_col + j
            draw_text(cv, cx, yy, str(num), 2, RED, bold=True)
            place, sep, rest = item.partition(": ")
            tx = cx + 28
            if sep:
                head = place + ": "
                check_fit("also #%d" % num,
                          text_w(head, 2, -1) + 1
                          + text_w(rest, 2, -1), 197)
                draw_text(cv, tx, yy, head, 2, INK, bold=True, tracking=-1)
                draw_text(cv, tx + text_w(head, 2, -1) + 1, yy, rest, 2,
                          INK, tracking=-1)
            else:
                check_fit("also #%d" % num, text_w(item, 2, -1), 197)
                draw_text(cv, tx, yy, item, 2, INK, tracking=-1)
            yy += 14


def draw_page():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    draw_lead(cv, 92)
    cv.hline(MARGIN, 240, CW, RULE, 2)
    draw_featured(cv, 248)
    cv.hline(MARGIN, 388, CW, RULE, 2)
    draw_tiles(cv, 396)
    cv.hline(MARGIN, 592, CW, RULE, 2)
    draw_numbers(cv, 600)
    cv.hline(MARGIN, 650, CW, RULE, 2)
    draw_bottom(cv, 658)
    cv.hline(MARGIN, 992, CW, RULE, 1)
    draw_text(cv, MARGIN, 998, FOOTER1, 1, GRAY)
    draw_text(cv, MARGIN, 1007, FOOTER2, 1, GRAY)
    total = 1 + len(FEATURED) + len(MEDIUM) + len(ALSO)
    if total != 81:
        VIOLATIONS.append("story count %d != 81" % total)
    if VIOLATIONS:
        print("LAYOUT VIOLATIONS:")
        for v in VIOLATIONS:
            print("  " + v)
        sys.exit(1)
    return cv


def main():
    cv = draw_page()
    data = png_bytes(cv)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, "entry.png")
    with open(dest, "wb") as f:
        f.write(data)
    import hashlib
    print("wrote %s (%d bytes, sha256 %s)"
          % (dest, len(data), hashlib.sha256(data).hexdigest()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
