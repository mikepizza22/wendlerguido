#!/usr/bin/env python3
"""Generate app icons for the 5/3/1 tracker. Stdlib only — no PIL/rsvg needed.

Draws a barbell mark on the app's accent-orange gradient and writes the PNG
sizes iOS and Android need. Run from anywhere:

    python3 tools/make-icons.py

Shapes are rounded rectangles in normalized 0..1 coordinates. Because every
shape is axis-aligned, each scanline reduces to a set of x-intervals that can
be clipped to pixel boundaries for exact horizontal coverage; only the vertical
axis is supersampled. That keeps it fast and still anti-aliases cleanly.
"""

import math
import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BG_TOP_LEFT = (0xFF, 0xA0, 0x5C)      # lighter accent
BG_BOTTOM_RIGHT = (0xE5, 0x66, 0x1F)  # deeper accent
MARK = (0x12, 0x15, 0x1B)             # --bg from the app's palette

SUBSAMPLES = 8  # vertical sub-scanlines per pixel row

# (center_x, center_y, half_width, half_height, corner_radius)
# The bar ends flush with the outer plates' outer edge so no nub sticks out.
# Every corner stays inside the central circle of radius 0.4, which is the
# maskable-icon safe zone Android may crop to.
BAR = (0.500, 0.500, 0.378, 0.028, 0.028)
PLATES_INNER = [(0.500 + dx, 0.500, 0.050, 0.185, 0.040) for dx in (-0.245, 0.245)]
PLATES_OUTER = [(0.500 + dx, 0.500, 0.033, 0.100, 0.028) for dx in (-0.345, 0.345)]
SHAPES = [BAR] + PLATES_INNER + PLATES_OUTER


def row_intervals(y):
    """X-intervals covered by the mark at normalized height y, merged."""
    spans = []
    for cx, cy, hw, hh, r in SHAPES:
        dy = abs(y - cy)
        if dy > hh:
            continue
        if dy <= hh - r:
            half = hw
        else:
            # inside a corner arc: shrink the half-width by the arc's inset
            over = dy - (hh - r)
            half = (hw - r) + math.sqrt(max(r * r - over * over, 0.0))
        spans.append((cx - half, cx + half))

    if not spans:
        return []
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def render(size):
    """Return raw RGB bytes for a size x size icon."""
    rows = []
    inv_sub = 1.0 / SUBSAMPLES
    for py in range(size):
        cov = [0.0] * size
        for s in range(SUBSAMPLES):
            y = (py + (s + 0.5) * inv_sub) / size
            for a, b in row_intervals(y):
                # normalized -> pixel space, then exact per-pixel clipping
                a_px, b_px = a * size, b * size
                first = max(int(math.floor(a_px)), 0)
                last = min(int(math.ceil(b_px)), size)
                for i in range(first, last):
                    overlap = min(b_px, i + 1) - max(a_px, i)
                    if overlap > 0:
                        cov[i] += overlap
        row = bytearray()
        y_norm = (py + 0.5) / size
        for px in range(size):
            t = (((px + 0.5) / size) + y_norm) * 0.5  # diagonal gradient
            alpha = min(cov[px] * inv_sub, 1.0)
            for ch in range(3):
                bg = BG_TOP_LEFT[ch] + (BG_BOTTOM_RIGHT[ch] - BG_TOP_LEFT[ch]) * t
                row.append(int(round(bg + (MARK[ch] - bg) * alpha)))
        rows.append(bytes(row))
    return rows


def write_png(path, rows, size):
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + r for r in rows)  # filter type 0 per scanline
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


TARGETS = [
    ("icon-512.png", 512),
    ("icon-192.png", 192),
    ("apple-touch-icon.png", 180),
    ("favicon-32.png", 32),
]

if __name__ == "__main__":
    for name, size in TARGETS:
        path = os.path.join(OUT_DIR, name)
        write_png(path, render(size), size)
        print(f"{name}  {size}x{size}  {os.path.getsize(path)} bytes")
