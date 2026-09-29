"""Parametric SVG flat-lay garment library.

Every garment is drawn on a 200x200 canvas with a transparent background. Each category follows a fixed
canvas convention so the frontend mannequin can map garments onto the body without per-item tuning:

  tops / outerwear : neck centre (100, 24), shoulders at y=30, body half-width ~36, hem y 105..190
  bottoms          : waistband y=12..20 spanning x 66..134, crotch y=78, hem y 70..196
  one_piece        : neck y=6, waist y=70, hem y 115..196 (a whole body from neck to ankle)
  footwear         : a pair of shoes inside x 30..170, y 20..185
  accessories      : the item centred inside the canvas

The mannequin slot geometry lives in frontend/src/mannequin.ts and uses the same conventions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .colors import color_hex, darken

CANVAS = 200


@dataclass
class Spec:
    subcategory: str
    color: str
    color2: str | None = None
    pattern: str = "solid"
    fit: str = "regular"
    length: str = "regular"
    neckline: str = "crew"
    sleeve: str = "short"
    fabric: str = "cotton"


@dataclass
class _Canvas:
    uid: str
    spec: Spec
    defs: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)

    @property
    def base(self) -> str:
        return color_hex(self.spec.color)

    @property
    def accent(self) -> str:
        if self.spec.color2:
            return color_hex(self.spec.color2)
        return darken(self.base, 0.35) if self.spec.color not in ("black", "charcoal", "navy") else "#d9d4c7"

    @property
    def stroke(self) -> str:
        return darken(self.base, 0.4) if self.spec.color not in ("black", "charcoal") else "#000000"

    def fill(self) -> str:
        """Fill reference for the main fabric (pattern or plain colour)."""
        p = self.spec.pattern
        if p == "solid" or self.spec.subcategory in ("sunglasses", "watch"):
            return self.base
        pid = f"{self.uid}-pat"
        if not any(pid in d for d in self.defs):
            self.defs.append(_pattern(pid, p, self.base, self.accent))
        return f"url(#{pid})"

    def shape(self, d: str, fill: str | None = None, extra: str = "") -> None:
        f = fill or self.fill()
        self.body.append(f'<path d="{d}" fill="{f}" stroke="{self.stroke}" stroke-width="1.6" '
                         f'stroke-linejoin="round" {extra}/>')
        # soft fabric shading so flat-lays read as fabric, not clip-art
        self.body.append(f'<path d="{d}" fill="url(#{self.uid}-shade)" stroke="none"/>')

    def line(self, d: str, width: float = 1.2, color: str | None = None, dash: str = "", opacity: float = 0.8) -> None:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<path d="{d}" fill="none" stroke="{color or self.stroke}" stroke-width="{width}" '
                         f'stroke-linecap="round" opacity="{opacity}"{dash_attr}/>')

    def dot(self, x: float, y: float, r: float = 2.2, color: str | None = None) -> None:
        self.body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color or self.stroke}"/>')

    def raw(self, s: str) -> None:
        self.body.append(s)


def _pattern(pid: str, kind: str, base: str, accent: str) -> str:
    inner = {
        "stripes": f'<rect width="12" height="12" fill="{base}"/><rect x="0" width="4" height="12" fill="{accent}"/>',
        "checks": (f'<rect width="16" height="16" fill="{base}"/><rect width="16" height="6" fill="{accent}" opacity=".55"/>'
                   f'<rect width="6" height="16" fill="{accent}" opacity=".55"/>'),
        "polka": f'<rect width="14" height="14" fill="{base}"/><circle cx="7" cy="7" r="2.6" fill="{accent}"/>',
        "floral": (f'<rect width="22" height="22" fill="{base}"/>'
                   + "".join(f'<circle cx="{11 + dx}" cy="{11 + dy}" r="2.6" fill="{accent}"/>'
                             for dx, dy in ((0, -3.5), (3.5, 0), (0, 3.5), (-3.5, 0)))
                   + '<circle cx="11" cy="11" r="1.8" fill="#f4e3b0"/>'
                   + f'<circle cx="2" cy="2" r="1.4" fill="{accent}" opacity=".6"/>'),
        "print": (f'<rect width="18" height="18" fill="{base}"/>'
                  f'<path d="M3 13 L8 4 L13 13 Z" fill="{accent}" opacity=".75"/>'
                  f'<circle cx="14" cy="5" r="1.8" fill="{accent}" opacity=".6"/>'),
        "embroidered": (f'<rect width="16" height="16" fill="{base}"/>'
                        f'<path d="M8 3 L10 8 L8 13 L6 8 Z" fill="{accent}" opacity=".85"/>'
                        f'<circle cx="2" cy="2" r="1" fill="{accent}"/><circle cx="14" cy="14" r="1" fill="{accent}"/>'),
    }.get(kind, f'<rect width="10" height="10" fill="{base}"/>')
    size = {"stripes": 12, "checks": 16, "polka": 14, "floral": 22, "print": 18, "embroidered": 16}.get(kind, 10)
    return (f'<pattern id="{pid}" width="{size}" height="{size}" patternUnits="userSpaceOnUse">{inner}</pattern>')


def _shade_def(uid: str) -> str:
    return (f'<linearGradient id="{uid}-shade" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#ffffff" stop-opacity=".16"/>'
            '<stop offset=".55" stop-color="#ffffff" stop-opacity="0"/>'
            '<stop offset="1" stop-color="#000000" stop-opacity=".14"/></linearGradient>')


# ------------------------------------------------------------------ tops & outerwear

HALF_W = {"slim": 31, "regular": 35, "relaxed": 39, "oversized": 44, "straight": 36, "tapered": 33,
          "a_line": 36, "flared": 36, "bodycon": 30, "wide": 40, "none": 35}
TOP_HEM = {"cropped": 104, "regular": 150, "long": 178, "midi": 186, "maxi": 190, "ankle": 186, "mini": 150, "none": 150}
NECK_DEPTH = {"crew": 9, "v_neck": 34, "collar": 7, "mandarin": 5, "square": 18, "halter": 0, "hood": 8, "none": 9}


def _top_path(fit: str, length: str, sleeve: str, neckline: str, flare: float = 0, ny: float = 24,
              hem: float | None = None, hem_w: float | None = None) -> str:
    w = HALF_W.get(fit, 35)
    sh = w + (6 if fit == "oversized" else 3)
    shoulder_y = ny + 6
    arm_y = shoulder_y + 32 + (6 if fit == "oversized" else 0)
    hem = hem if hem is not None else TOP_HEM.get(length, 150)
    hw = hem_w if hem_w is not None else w + flare
    nd = NECK_DEPTH.get(neckline, 9)
    nx = 14 if neckline != "halter" else 9
    # sleeve end points (outer, inner) for the left side; right side mirrors
    sleeves = {
        "short": ((100 - sh - 24, shoulder_y + 38), (100 - w - 12, arm_y + 10)),
        "three_quarter": ((100 - sh - 32, shoulder_y + 80), (100 - w - 17, arm_y + 50)),
        "long": ((100 - sh - 36, shoulder_y + 118), (100 - w - 20, arm_y + 86)),
    }

    def m(x: float) -> float:
        return 200 - x

    if neckline == "halter":
        # straps tie at the neck; shoulders are bare
        pts = (f"M {100 - nx} {ny} L {100 - w + 4} {arm_y} L {100 - hw} {hem} L {m(100 - hw)} {hem} "
               f"L {m(100 - w + 4)} {arm_y} L {100 + nx} {ny} Q 100 {ny + 26} {100 - nx} {ny} Z")
        return pts
    d = f"M {100 - nx} {ny} L {100 - sh} {shoulder_y} "
    if sleeve in sleeves:
        (ox, oy), (ix, iy) = sleeves[sleeve]
        d += f"L {ox} {oy} L {ix} {iy} L {100 - w} {arm_y} "
    else:
        d += f"Q {100 - w - 2} {shoulder_y + 12} {100 - w} {arm_y} "
    d += f"L {100 - hw} {hem} L {m(100 - hw)} {hem} L {m(100 - w)} {arm_y} "
    if sleeve in sleeves:
        (ox, oy), (ix, iy) = sleeves[sleeve]
        d += f"L {m(ix)} {iy} L {m(ox)} {oy} "
    else:
        d += f"Q {m(100 - w - 2)} {shoulder_y + 12} {m(100 - sh)} {shoulder_y} "
    d += f"L {m(100 - sh)} {shoulder_y} L {100 + nx} {ny} "
    if neckline == "v_neck":
        d += f"L 100 {ny + nd} Z"
    elif neckline == "square":
        d += f"L {100 + nx} {ny + nd} L {100 - nx} {ny + nd} Z"
    else:
        d += f"Q 100 {ny + nd * 2} {100 - nx} {ny} Z"
    return d


def _collar(c: _Canvas, ny: float = 24) -> None:
    c.shape(f"M 86 {ny} L 100 {ny + 16} L 92 {ny + 22} L 80 {ny + 6} Z")
    c.shape(f"M 114 {ny} L 100 {ny + 16} L 108 {ny + 22} L 120 {ny + 6} Z")


def _placket(c: _Canvas, top: float, bottom: float, buttons: int = 5) -> None:
    c.line(f"M 100 {top} L 100 {bottom}", 1.0)
    step = (bottom - top) / (buttons + 1)
    for i in range(1, buttons + 1):
        c.dot(100 + 3, top + i * step, 1.7, color="#f5f0e6" if c.spec.color in ("black", "navy", "charcoal") else None)


def draw_top(c: _Canvas) -> None:
    s = c.spec
    sub = s.subcategory
    fit, length, sleeve, neck = s.fit, s.length, s.sleeve, s.neckline
    if sub == "hoodie":
        c.shape("M 76 30 Q 100 -2 124 30 L 118 40 Q 100 22 82 40 Z")  # hood behind
        neck = "crew"
    flare = 6 if sub == "kurta" else 0
    c.shape(_top_path(fit, length, sleeve, neck, flare))
    hem = TOP_HEM.get(length, 150)
    w = HALF_W.get(fit, 35)
    if sub in ("shirt", "linen_shirt"):
        _collar(c)
        _placket(c, 40, hem - 4)
        if sub == "linen_shirt" and sleeve in ("long", "three_quarter"):
            # rolled cuffs
            ox = 100 - w - 3 - (32 if sleeve == "three_quarter" else 36)
            c.line(f"M {ox + 2} {84 if sleeve == 'three_quarter' else 118} l 16 6", 2.2)
            c.line(f"M {200 - ox - 2} {84 if sleeve == 'three_quarter' else 118} l -16 6", 2.2)
        c.line(f"M 118 58 l 12 0 l 0 12 l -12 0 Z", 1.0, opacity=0.5)  # chest pocket
    elif sub == "kurta":
        _placket(c, 34, 70, 3)
        c.line(f"M {100 - w - 5} {hem - 30} L {100 - w - 6} {hem}", 1.2)
        c.line(f"M {100 + w + 5} {hem - 30} L {100 + w + 6} {hem}", 1.2)
        if s.pattern == "solid":
            c.line(f"M {100 - w - 6} {hem - 6} L {100 + w + 6} {hem - 6}", 3, color=c.accent)
    elif sub == "hoodie":
        c.line(f"M 78 {hem - 44} L 122 {hem - 44} L 128 {hem - 16} L 72 {hem - 16} Z", 1.2)  # pouch
        c.line("M 94 36 L 92 60 M 106 36 L 108 60", 1.2)  # drawstrings
        c.line(f"M {100 - w} {hem - 8} L {100 + w} {hem - 8}", 1.0, opacity=0.5)
    elif sub == "sweater":
        for x in range(int(100 - w) + 4, int(100 + w), 5):
            c.line(f"M {x} {hem - 10} L {x} {hem - 1}", 0.8, opacity=0.5)
        if sub == "sweater" and s.pattern == "solid" and fit == "relaxed":
            for x in (88, 112):  # cable knit
                c.line(f"M {x} 40 q 5 8 0 16 q -5 8 0 16 q 5 8 0 16 q -5 8 0 16 q 5 8 0 16", 1.0, opacity=0.45)
    elif sub == "blouse" and sleeve == "short":
        c.shape("M 58 30 Q 36 36 42 66 Q 56 70 66 60 Z")
        c.shape("M 142 30 Q 164 36 158 66 Q 144 70 134 60 Z")
    elif sub == "tshirt" and s.pattern == "print":
        c.raw(f'<circle cx="100" cy="82" r="18" fill="{c.accent}" opacity=".85"/>'
              f'<path d="M 88 88 L 100 68 L 112 88 Z" fill="{c.base}" opacity=".9"/>')


def draw_outer(c: _Canvas) -> None:
    s = c.spec
    sub = s.subcategory
    fit = s.fit if s.fit != "none" else "regular"
    w = HALF_W.get(fit, 35) + 3
    length = s.length if s.length != "none" else "regular"
    sleeve = "sleeveless" if sub == "nehru_jacket" else ("three_quarter" if sub == "shrug" else "long")
    if sub == "shrug":
        length = "cropped"
    hem = TOP_HEM.get(length, 150) + (8 if sub == "blazer" else 0)
    neck = "mandarin" if sub == "nehru_jacket" else "v_neck"
    c.shape(_top_path(fit, length, sleeve, neck, hem=hem, hem_w=w))
    if sub == "blazer":
        # lapels + open V front
        c.shape("M 86 24 L 100 96 L 92 100 L 74 40 Z")
        c.shape("M 114 24 L 100 96 L 108 100 L 126 40 Z")
        c.dot(104, 112, 2.6)
        c.dot(104, 128, 2.6)
        c.line(f"M 70 {hem - 40} l 20 0", 1.2)
        c.line(f"M 110 {hem - 40} l 20 0", 1.2)
    elif sub == "denim_jacket":
        _collar(c)
        _placket(c, 40, hem - 6, 5)
        c.line("M 72 60 L 92 60 L 92 76 L 72 76 Z M 108 60 L 128 60 L 128 76 L 108 76 Z", 1.2, color="#c9a34e", dash="3 2")
        c.line(f"M {100 - w} {hem - 14} L {100 + w} {hem - 14}", 1.2, color="#c9a34e", dash="3 2")
    elif sub == "bomber":
        c.line("M 100 32 L 100 " + str(hem - 2), 1.6)
        c.shape(f"M {100 - w} {hem - 10} L {100 + w} {hem - 10} L {100 + w} {hem} L {100 - w} {hem} Z", fill=c.accent)
        c.shape("M 86 24 Q 100 36 114 24 L 116 30 Q 100 44 84 30 Z", fill=c.accent)
    elif sub == "nehru_jacket":
        _placket(c, 34, hem - 6, 6)
        c.line("M 76 64 l 14 0", 1.2)
    elif sub in ("cardigan", "shrug"):
        _placket(c, 60, hem - 4, 4)
        for x in range(int(100 - w) + 4, int(100 + w), 5):
            c.line(f"M {x} {hem - 8} L {x} {hem - 1}", 0.8, opacity=0.45)


# ------------------------------------------------------------------ bottoms

LEG = {  # outer hem x, inner hem x (left leg)
    "slim": (72, 96), "tapered": (74, 96), "straight": (66, 98), "regular": (66, 98), "relaxed": (62, 99),
    "wide": (50, 100), "oversized": (56, 100), "flared": (48, 100), "bodycon": (74, 96), "a_line": (66, 98), "none": (66, 98),
}
BOTTOM_HEM = {"ankle": 182, "long": 194, "regular": 194, "maxi": 194, "midi": 150, "mini": 72, "cropped": 150, "none": 194}


def _trouser_path(fit: str, hem: float, waist_y: float = 12, waist_x: float = 66, hip_y: float = 50,
                  hip_x: float = 62, crotch_y: float = 80) -> str:
    ox, ix = LEG.get(fit, (66, 98))
    return (f"M {waist_x} {waist_y} L {200 - waist_x} {waist_y} L {200 - hip_x} {hip_y} L {200 - ox} {hem} "
            f"L {200 - ix} {hem} L 101 {crotch_y} L 99 {crotch_y} L {ix} {hem} L {ox} {hem} L {hip_x} {hip_y} Z")


def draw_bottom(c: _Canvas) -> None:
    s = c.spec
    sub = s.subcategory
    if sub == "skirt":
        hem = {"mini": 80, "midi": 150, "maxi": 194}.get(s.length, 150)
        hw = {"a_line": 52, "flared": 66, "bodycon": 40, "straight": 42}.get(s.fit, 52) + (hem - 80) * 0.12
        c.shape(f"M 66 12 L 134 12 L {100 + hw} {hem} Q 100 {hem + 6} {100 - hw} {hem} Z")
        if s.fit == "flared" or s.pattern == "floral":
            for frac in (0.45, 0.72):  # tiers
                y = 12 + (hem - 12) * frac
                x = 34 + (hw - 34) * frac
                c.line(f"M {100 - x - 1} {y} Q 100 {y + 4} {100 + x + 1} {y}", 1.2)
        else:
            for x in (84, 100, 116):
                c.line(f"M {x} 22 L {100 + (x - 100) * hw / 34} {hem - 2}", 0.9, opacity=0.45)
        c.line("M 66 20 L 134 20", 1.2)
        return
    if sub == "shorts":
        hem = 70 if s.length == "mini" else 86
        fit = "relaxed"
    elif sub == "palazzo":
        hem, fit = 194, "flared"
    elif sub == "wide_leg_trousers":
        hem, fit = 194, "wide"
    elif sub == "leggings":
        hem, fit = 186, "slim"
    else:
        hem, fit = BOTTOM_HEM.get(s.length, 194), s.fit
    c.shape(_trouser_path(fit, hem))
    c.line("M 66 20 L 134 20", 1.2)
    c.line("M 100 20 L 100 50", 1.0)
    if sub == "jeans":
        stitch = "#c9a34e"
        c.line("M 72 22 Q 80 36 90 22 M 128 22 Q 120 36 110 22", 1.1, color=stitch, dash="3 2")
        c.line("M 100 20 Q 106 40 100 58", 1.1, color=stitch, dash="3 2")
        c.dot(72, 24, 1.4, "#b8bcc2")
        c.dot(128, 24, 1.4, "#b8bcc2")
    elif sub == "cargo_pants":
        c.line("M 58 100 L 76 100 L 76 124 L 58 124 Z M 142 100 L 124 100 L 124 124 L 142 124 Z", 1.2)
        c.line("M 58 100 l 18 -6 M 142 100 l -18 -6", 1.0)
    elif sub in ("chinos", "wide_leg_trousers"):
        c.line("M 74 22 Q 78 34 86 22 M 126 22 Q 122 34 114 22", 1.0)
        c.line(f"M 82 60 L {(LEG.get(fit, (66, 98))[0] + LEG.get(fit, (66, 98))[1]) / 2} {hem - 2}", 0.8, opacity=0.4)
        c.line(f"M 118 60 L {200 - (LEG.get(fit, (66, 98))[0] + LEG.get(fit, (66, 98))[1]) / 2} {hem - 2}", 0.8, opacity=0.4)
    elif sub == "palazzo":
        for x in (70, 84, 116, 130):
            c.line(f"M {x} 30 L {x + (x - 100) * 0.9} {hem - 2}", 0.9, opacity=0.4)


# ------------------------------------------------------------------ one-pieces


def _bodice(c: _Canvas, sleeve: str, neckline: str, waist: float = 70, fit: str = "slim") -> None:
    # A top scaled into the one-piece canvas (neck at y=6, waist at y=70).
    c.shape(_top_path(fit, "regular", sleeve, neckline, ny=6, hem=waist))


def draw_one_piece(c: _Canvas) -> None:
    s = c.spec
    sub = s.subcategory
    hem = {"mini": 118, "midi": 162, "maxi": 196, "long": 196, "regular": 196}.get(s.length, 196)
    if sub == "dress":
        hw = {"a_line": 50, "flared": 62, "bodycon": 32, "relaxed": 44}.get(s.fit, 48)
        c.shape(f"M 70 68 L 130 68 L {100 + hw} {hem} Q 100 {hem + 5} {100 - hw} {hem} Z")
        _bodice(c, s.sleeve, s.neckline, 72, "bodycon" if s.fit == "bodycon" else "slim")
        c.line("M 70 70 L 130 70", 1.4)
    elif sub == "jumpsuit":
        c.shape(_trouser_path(s.fit if s.fit != "none" else "relaxed", hem, 68, 68, 104, 64, 124))
        _bodice(c, s.sleeve, "collar", 72, "regular")
        _collar(c, 6)
        c.line("M 68 72 L 132 72", 2.0)
        _placket(c, 20, 70, 3)
    elif sub == "coord_set":
        c.shape(_trouser_path("wide", hem, 86, 68, 116, 62, 134))
        _bodice(c, s.sleeve, "collar", 92, "relaxed")
        _collar(c, 6)
        _placket(c, 22, 88, 4)
    elif sub in ("kurta_set", "lehenga"):
        if sub == "kurta_set":
            c.shape(_trouser_path("straight", hem, 110, 72, 140, 68, 150))
            flare = 22 if s.fit == "flared" else 8
            c.shape(_top_path("slim", "regular", s.sleeve, "mandarin", ny=6, hem=150, hem_w=HALF_W["slim"] + flare))
            c.line(f"M {100 - HALF_W['slim'] - flare} 144 L {100 + HALF_W['slim'] + flare} 144", 3, color=c.accent)
            _placket(c, 16, 50, 3)
        else:
            c.shape(f"M 68 70 L 132 70 L 176 196 Q 100 202 24 196 Z")
            c.line("M 26 186 Q 100 194 174 186", 5, color=c.accent, opacity=0.9)
            _bodice(c, "short", "square", 58, "slim")
    elif sub == "saree":
        c.shape("M 70 64 L 130 64 L 150 196 Q 100 200 50 196 Z")
        for x in (86, 94, 102, 110):
            c.line(f"M {x} 110 L {x - 4} 194", 1.0, opacity=0.5)
        _bodice(c, "short", "square", 58, "slim")
        c.shape("M 60 30 L 140 120 L 150 196 L 128 196 L 124 128 L 52 42 Z", fill=c.fill(), extra='opacity="0.95"')  # pallu
        c.line("M 60 30 L 140 120 L 150 196", 4, color=c.accent)


# ------------------------------------------------------------------ footwear


def draw_shoes(c: _Canvas) -> None:
    sub = c.spec.subcategory
    for flip in (False, True):
        def X(x: float) -> float:
            return 200 - x if flip else x

        pointed = sub in ("stilettos", "juttis", "block_heels")
        toe = f"Q {X(62)} 190 {X(66)} 184" if not pointed else f"L {X(62)} 190 L {X(70)} 170"
        top_y = 20 if sub == "boots" else 60
        outline = (f"M {X(46)} {top_y} L {X(84)} {top_y} Q {X(92)} {top_y + 10} {X(90)} 120 L {X(86)} 170 "
                   f"{toe} Q {X(52)} 184 {X(42)} 172 L {X(38)} 120 Q {X(36)} {top_y + 10} {X(46)} {top_y} Z")
        if sub in ("sandals", "kolhapuris"):
            c.shape(outline, fill=color_hex("tan") if c.spec.color != "tan" else color_hex("brown"))
            for y in (96, 132) if sub == "sandals" else (110,):
                c.shape(f"M {X(38)} {y} L {X(90)} {y - 6} L {X(90)} {y + 6} L {X(38)} {y + 12} Z")
            if sub == "kolhapuris":
                c.shape(f"M {X(62)} {110} L {X(66)} 150 L {X(60)} 150 Z")
            continue
        c.shape(outline)
        if sub == "sneakers":
            c.shape(f"M {X(40)} 158 Q {X(64)} 196 {X(88)} 158 L {X(88)} 170 Q {X(64)} 204 {X(40)} 170 Z", fill="#f4f2ee")
            for y in (80, 92, 104):
                c.line(f"M {X(54)} {y} L {X(76)} {y}", 1.6, color="#ffffff" if c.spec.color == "black" else None)
            c.line(f"M {X(44)} 130 Q {X(64)} 118 {X(86)} 130", 2.4, color=c.accent)
        elif sub == "loafers":
            c.line(f"M {X(46)} 118 Q {X(64)} 96 {X(84)} 118", 1.4)
            c.shape(f"M {X(48)} 112 L {X(82)} 112 L {X(82)} 120 L {X(48)} 120 Z", fill=c.base)
            if c.spec.color == "black":
                c.raw(f'<rect x="{min(X(56), X(72))}" y="112" width="16" height="5" rx="2" fill="#c9a34e"/>')
        elif sub in ("block_heels", "stilettos"):
            heel = f"M {X(52)} 50 L {X(76)} 50 L {X(74)} 66 L {X(54)} 66 Z" if sub == "block_heels" else f"M {X(62)} 34 L {X(66)} 34 L {X(65)} 62 L {X(63)} 62 Z"
            c.shape(heel, fill=darken(c.base, 0.2))
            c.line(f"M {X(42)} 76 L {X(88)} 76", 3, color=c.stroke)
        elif sub == "flats":
            c.line(f"M {X(44)} 104 Q {X(64)} 120 {X(84)} 104", 1.4)
            c.shape(f"M {X(58)} 104 L {X(70)} 104 L {X(64)} 112 Z", fill=c.accent)
        elif sub == "boots":
            c.shape(f"M {X(46)} 40 L {X(52)} 40 L {X(52)} 100 L {X(46)} 100 Z", fill=darken(c.base, 0.3))
            c.shape(f"M {X(40)} 176 Q {X(64)} 196 {X(88)} 176 L {X(88)} 182 Q {X(64)} 202 {X(40)} 182 Z", fill="#2a2a2a")
        elif sub == "juttis":
            for y in (120, 140, 160):
                c.dot(X(64), y, 2.2, color=c.accent if c.spec.color != "gold" else "#8a1c2b")


# ------------------------------------------------------------------ accessories


def draw_accessory(c: _Canvas) -> None:
    sub = c.spec.subcategory
    if sub == "tote":
        c.line("M 70 70 Q 72 22 100 22 Q 128 22 130 70", 5, color=c.stroke, opacity=1)
        c.shape("M 44 70 L 156 70 L 166 178 L 34 178 Z")
        c.line("M 44 84 L 156 84", 1.0, opacity=0.5)
    elif sub == "sling_bag":
        c.line("M 58 88 Q 60 14 150 20 Q 176 24 150 88", 3, color=c.stroke, opacity=1)
        c.shape("M 48 88 Q 48 78 58 78 L 142 78 Q 152 78 152 88 L 152 160 Q 152 170 142 170 L 58 170 Q 48 170 48 160 Z")
        c.shape("M 48 88 Q 48 78 58 78 L 142 78 Q 152 78 152 88 L 152 118 Q 100 132 48 118 Z")
        c.dot(100, 124, 3, "#c9a34e")
    elif sub == "clutch":
        c.shape("M 30 70 L 170 70 L 170 140 Q 170 148 162 148 L 38 148 Q 30 148 30 140 Z")
        c.shape("M 30 70 L 170 70 L 100 116 Z")
        c.dot(100, 112, 4, "#c9a34e")
    elif sub == "belt":
        c.shape("M 10 88 L 150 88 L 150 112 L 10 112 Z")
        c.raw(f'<rect x="150" y="80" width="30" height="40" rx="3" fill="none" stroke="#b8a060" stroke-width="5"/>')
        c.line("M 150 100 L 176 100", 2, color="#b8a060", opacity=1)
        for x in (40, 60, 80):
            c.dot(x, 100, 2.2, darken(c.base, 0.5))
    elif sub == "sunglasses":
        lens = c.base
        c.raw(f'<ellipse cx="62" cy="100" rx="34" ry="26" fill="{lens}" stroke="{c.stroke}" stroke-width="5"/>'
              f'<ellipse cx="138" cy="100" rx="34" ry="26" fill="{lens}" stroke="{c.stroke}" stroke-width="5"/>'
              f'<path d="M 94 94 Q 100 86 106 94" fill="none" stroke="{c.stroke}" stroke-width="5"/>'
              '<path d="M 50 92 q 10 -8 22 -6 M 126 92 q 10 -8 22 -6" stroke="#ffffff" stroke-width="3" opacity=".45" fill="none"/>')
        if c.spec.pattern == "print":  # tortoiseshell flecks on the frame
            for x, y in ((34, 92), (86, 112), (114, 88), (166, 108)):
                c.dot(x, y, 2.4, "#3b2414")
    elif sub == "watch":
        c.shape("M 84 20 L 116 20 L 116 180 L 84 180 Z", fill=darken(c.base, 0.15) if c.spec.fabric != "metal" else c.base)
        c.raw(f'<circle cx="100" cy="100" r="36" fill="{c.base}" stroke="{c.stroke}" stroke-width="4"/>'
              '<circle cx="100" cy="100" r="28" fill="#fbfaf7"/>'
              '<path d="M 100 100 L 100 80 M 100 100 L 114 106" stroke="#222" stroke-width="3" stroke-linecap="round"/>')
    elif sub == "jewellery":
        for cx in (64, 136):
            c.raw(f'<circle cx="{cx}" cy="44" r="10" fill="{c.base}" stroke="{c.stroke}" stroke-width="2"/>'
                  f'<path d="M {cx} 54 L {cx} 70" stroke="{c.stroke}" stroke-width="2"/>')
            if c.spec.pattern == "embroidered" or c.spec.color == "gold":
                c.raw(f'<path d="M {cx - 26} 118 Q {cx} 58 {cx + 26} 118 Z" fill="{c.base}" stroke="{c.stroke}" stroke-width="2"/>')
                for dx in range(-22, 26, 8):
                    c.dot(cx + dx, 126, 3, c.base)
            else:
                c.raw(f'<circle cx="{cx}" cy="92" r="20" fill="{c.base}" stroke="{c.stroke}" stroke-width="2"/>'
                      f'<circle cx="{cx - 6}" cy="86" r="5" fill="#ffffff" opacity=".7"/>')
    elif sub == "scarf":
        c.shape("M 30 40 L 170 40 L 100 170 Z")
        for x in range(92, 110, 4):
            c.line(f"M {x} 168 L {x} 186", 1.2)
    elif sub == "dupatta":
        c.shape("M 40 20 Q 100 60 160 20 L 170 40 Q 120 90 120 186 L 80 186 Q 80 90 30 40 Z")
        c.line("M 80 176 L 120 176", 4, color=c.accent if c.spec.color != "gold" else "#8a1c2b")
        for x in range(82, 122, 6):
            c.line(f"M {x} 186 L {x} 196", 1.2)


DRAWERS = {"tops": draw_top, "outerwear": draw_outer, "bottoms": draw_bottom, "one_piece": draw_one_piece,
           "footwear": draw_shoes, "accessories": draw_accessory}


def garment_parts(spec: Spec, uid: str = "g") -> tuple[str, str]:
    """Return (defs, body) SVG fragments in the 200x200 canvas for embedding."""
    from .vocab import SUB_TO_CAT

    c = _Canvas(uid=uid, spec=spec)
    c.defs.append(_shade_def(uid))
    DRAWERS[SUB_TO_CAT[spec.subcategory]](c)
    return "".join(c.defs), "".join(c.body)


def garment_svg(spec: Spec, uid: str = "g") -> str:
    defs, body = garment_parts(spec, uid)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS} {CANVAS}" width="{CANVAS * 2}" '
            f'height="{CANVAS * 2}"><defs>{defs}</defs>{body}</svg>')
