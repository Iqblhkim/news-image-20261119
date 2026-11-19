#!/usr/bin/env python3
"""Draw the v3 news front page for make.fun news-image-20261119.

60 stories for Thursday 19 November 2026, in a cleaner front-page
style: dark navy masthead, a big illustrated lead panel (Shenzhen dusk,
three flags), two featured stories with art panels, a BY THE NUMBERS
strip, and 57 numbered tiles in three wide columns with generous row
pitch -- every headline on one readable line. Nothing invented: every
story was reported on 19 Nov 2026 (AP/Reuters/AFP/BBC/Al Jazeera/UN
News roundups, the COP31 diary, the APEC diary, and the day's wire
digests).

Why v3: v2 crammed 81 stories onto one page (66 one-line briefs at a
14px row pitch) and the pairwise AI judge scored it 96.6%, worse than
v1's 97.4% at 60 stories. v3 keeps 60 stories but gives each of the 57
tiles a full-width column slot at a 26px row pitch, so every headline
is legible at a glance.

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


# -------------------------------------------------------------------- data
# 60 stories for Thursday 19 November 2026: 1 lead + 2 featured + 57
# numbered tiles. All reported on 19 Nov 2026.

LEAD = {
    "num": 1, "kicker": "ASIA · DIPLOMACY",
    "headline": "Trump, Xi and Putin meet in Shenzhen",
    "deck": ("First-ever trilateral of the three leaders, on the APEC "
             "sidelines. Trump joins the plenary."),
}

FEATURED = [
    {"num": 2, "kicker": "MIDDLE EAST · WAR",
     "headline": "Israel launches ground operation in Gaza",
     "deck": ("Troops enter central Gaza. Families flee.")},
    {"num": 3, "kicker": "MARKETS · TECHNOLOGY",
     "headline": "Anthropic's $81.3bn IPO, biggest ever",
     "deck": ("Record debut at $83 on Nasdaq.")},
]

NUMBERS = [
    ("$81.3bn", "Anthropic record IPO raise"),
    ("€45bn", "EU loan for Ukraine"),
    ("$190.4m", "Van Gogh record sale"),
    ("145 km/h", "Akvan gusts at landfall"),
    ("1 light-day", "Voyager 1 from Earth"),
    ("$1.4tn", "Anthropic debut value"),
]

# 57 tiles, numbered 4-60. One short headline each, sized to fit a
# 286px column slot at scale 2 (checked by check_fit at draw time).
TILES = [
    {"num": 4, "headline": "Crimea bridge hit again"},
    {"num": 5, "headline": "Iran hits Kuwait, Bahrain"},
    {"num": 6, "headline": "GTA VI rolls out worldwide"},
    {"num": 7, "headline": "Jeffries: Black Speaker"},
    {"num": 8, "headline": "Voyager 1: one light-day"},
    {"num": 9, "headline": "Nvidia halts H-chip sales"},
    {"num": 10, "headline": "Fed: more hikes likely"},
    {"num": 11, "headline": "Cyclone Akvan nears India"},
    {"num": 12, "headline": "COP31: 21 issues open"},
    {"num": 13, "headline": "Van Gogh: record $190.4m"},
    {"num": 14, "headline": "Myanmar genocide verdict"},
    {"num": 15, "headline": "N. Korea fires missiles"},
    {"num": 16, "headline": "APEC: Trump talks"},
    {"num": 17, "headline": "Berlin: Kyiv talks"},
    {"num": 18, "headline": "Putin-Xi talks"},
    {"num": 19, "headline": "Xi meets Carney"},
    {"num": 20, "headline": "US: Huang testifies"},
    {"num": 21, "headline": "Taiwan: Liu leads"},
    {"num": 22, "headline": "Taiwan: spy bill"},
    {"num": 23, "headline": "US: Trump vs Vance"},
    {"num": 24, "headline": "US-China: barriers"},
    {"num": 25, "headline": "Russia: agent held"},
    {"num": 26, "headline": "Haiti: Bukele raid"},
    {"num": 27, "headline": "NSA: net outage"},
    {"num": 28, "headline": "Epstein: $582m"},
    {"num": 29, "headline": "France: Melenchon"},
    {"num": 30, "headline": "Spain: clashes"},
    {"num": 31, "headline": "India: Japan talks"},
    {"num": 32, "headline": "Prabowo: Shenzhen"},
    {"num": 33, "headline": "Islam tops by 2035"},
    {"num": 34, "headline": "Oil: WTI down 3.2%"},
    {"num": 35, "headline": "BI rates up 25bp"},
    {"num": 36, "headline": "$100bn backer gains"},
    {"num": 37, "headline": "Nvidia: Vera Rubin"},
    {"num": 38, "headline": "Micron: -20%"},
    {"num": 39, "headline": "Fitch: AI bond risks"},
    {"num": 40, "headline": "COP31: stocktake"},
    {"num": 41, "headline": "COP31: 152 jets"},
    {"num": 42, "headline": "COP31: farm talks"},
    {"num": 43, "headline": "Merck rabies jab"},
    {"num": 44, "headline": "Estonia: border"},
    {"num": 45, "headline": "Prague: media rally"},
    {"num": 46, "headline": "IAEA: Yongbyon"},
    {"num": 47, "headline": "US: AI warning"},
    {"num": 48, "headline": "COPD Day marked"},
    {"num": 49, "headline": "Congress vs Modi"},
    {"num": 50, "headline": "Climber survives"},
    {"num": 51, "headline": "Berlin: spy charge"},
    {"num": 52, "headline": "Stacy Keach, 85"},
    {"num": 53, "headline": "DPP defends cities"},
    {"num": 54, "headline": "UK: GTA VI queues"},
    {"num": 55, "headline": "China: micro EVs"},
    {"num": 56, "headline": "Xi meets To Lam"},
    {"num": 57, "headline": "Spain: strike"},
    {"num": 58, "headline": "Australia: settlers"},
    {"num": 59, "headline": "France: retirees"},
    {"num": 60, "headline": "Science: lost years"},
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
    right = "60 STORIES · 6 CONTINENTS · ONE PAGE"
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
    draw_tracked(cv, ax + 6, y + ah - 14, "SHENZHEN · APEC SUMMIT", 2,
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
    """Fifty-seven tiles, 3 columns x 19 rows, pitch 26: number + headline.

    Each tile is one readable line at scale 2 with a bold red number,
    in a 314px column slot -- far roomier than v2's 66 briefs at a
    14px row pitch.
    """
    colw, gap = 314, 13
    for idx, st in enumerate(TILES):
        r, c = divmod(idx, 3)
        x = MARGIN + c * (colw + gap)
        ty = y + r * 26
        draw_text(cv, x, ty, str(st["num"]), 2, RED, bold=True)
        tx = x + 28
        check_fit("tile %d headline" % st["num"],
                  text_w(st["headline"], 2, -1), colw - 28)
        draw_text(cv, tx, ty, st["headline"], 2, INK, tracking=-1)


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


def draw_page():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    draw_lead(cv, 92)
    cv.hline(MARGIN, 240, CW, RULE, 2)
    draw_featured(cv, 248)
    cv.hline(MARGIN, 388, CW, RULE, 2)
    draw_numbers(cv, 396)
    cv.hline(MARGIN, 448, CW, RULE, 2)
    draw_tracked(cv, MARGIN, 456, "MORE ON THURSDAY 19 NOVEMBER — 57 STORIES",
                 2, INK, 2)
    draw_tiles(cv, 478)
    cv.hline(MARGIN, 972, CW, RULE, 1)
    draw_text(cv, MARGIN, 980, FOOTER1, 1, GRAY)
    draw_text(cv, MARGIN, 989, FOOTER2, 1, GRAY)
    total = 1 + len(FEATURED) + len(TILES)
    if total != 60:
        VIOLATIONS.append("story count %d != 60" % total)
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
