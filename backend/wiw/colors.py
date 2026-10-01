"""Perceptual colour maths (sRGB -> CIELAB, CIEDE2000) and simple harmony rules."""
from __future__ import annotations

import math
from functools import lru_cache

from .vocab import PALETTE


def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


@lru_cache(maxsize=None)
def hex_to_lab(h: str) -> tuple[float, float, float]:
    r, g, b = (_lin(c) for c in hex_to_rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    cm = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(cm ** 7 / (cm ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, c2p - c1p
    dh = h2p - h1p
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    Lm, cmp_ = (L1 + L2) / 2, (c1p + c2p) / 2
    hsum = h1p + h2p
    if c1p * c2p == 0:
        hm = hsum
    elif abs(h1p - h2p) <= 180:
        hm = hsum / 2
    else:
        hm = (hsum + 360) / 2 if hsum < 360 else (hsum - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm))
         + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63)))
    d_theta = 30 * math.exp(-(((hm - 275) / 25) ** 2))
    rc = 2 * math.sqrt(cmp_ ** 7 / (cmp_ ** 7 + 25 ** 7))
    sl = 1 + (0.015 * (Lm - 50) ** 2) / math.sqrt(20 + (Lm - 50) ** 2)
    sc = 1 + 0.045 * cmp_
    sh = 1 + 0.015 * cmp_ * t
    rt = -math.sin(math.radians(2 * d_theta)) * rc
    return math.sqrt((dLp / sl) ** 2 + (dCp / sc) ** 2 + (dHp / sh) ** 2 + rt * (dCp / sc) * (dHp / sh))


def color_hex(name: str) -> str:
    return PALETTE[name][0]


def color_family(name: str) -> str:
    return PALETTE[name][1]


def color_distance(a: str, b: str) -> float:
    """CIEDE2000 distance between two named palette colours (0 = identical)."""
    return delta_e2000(hex_to_lab(color_hex(a)), hex_to_lab(color_hex(b)))


def color_similarity(a: str, b: str, max_delta_e: float) -> float:
    return max(0.0, 1.0 - color_distance(a, b) / max_delta_e)


def darken(hex_: str, amount: float = 0.25) -> str:
    r, g, b = hex_to_rgb(hex_)
    return "#%02x%02x%02x" % tuple(int(max(0, c * (1 - amount)) * 255) for c in (r, g, b))


def is_neutral(name: str) -> bool:
    return color_family(name) in ("neutral", "earth", "metallic") or name in ("navy", "denim_blue")


def harmony(a: str, b: str) -> float:
    """0..1 colour harmony between two garments.

    Neutrals pair with everything; same family reads tonal; very different saturated hues clash.
    """
    if a == b:
        return 0.8  # tonal but a little flat
    if is_neutral(a) or is_neutral(b):
        return 1.0
    if color_family(a) == color_family(b):
        return 0.85
    d = color_distance(a, b)
    return 0.6 if d < 40 else 0.35
