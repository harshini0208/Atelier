"""2D mannequin geometry (single source of truth for the app mannequin and the illustrated demo inspo).

The figure is faceless by design (no face images). Garment SVGs use the canvas conventions documented in
garments.py; `slot_transforms` maps each category's 200x200 canvas onto this body with a translate+scale.
"""
from __future__ import annotations

from dataclasses import dataclass

from .vocab import SUB_TO_CAT, slot_for

W, H = 540, 960
SKIN_TONES = ["#F6E0D0", "#EECBB0", "#E3B48F", "#D9A27A", "#C98C62",
              "#B5774E", "#9C6440", "#7F4F33", "#633C27", "#4A2C1D"]
HAIR_COLORS = {"black": "#1b1714", "dark_brown": "#3b2618", "brown": "#6a4328", "auburn": "#8a3b1f",
               "blonde": "#d8b56d", "grey": "#9d9a96"}
HAIR_STYLES = ["long", "bob", "bun", "curly", "short", "buzz"]
BODY_TYPES = {
    # shoulder, waist, hip half-widths (px)
    "women": {"slim": (58, 40, 54), "hourglass": (62, 40, 64), "pear": (56, 44, 70), "apple": (62, 56, 62),
              "plus": (70, 60, 76)},
    "men": {"slim": (64, 48, 52), "athletic": (74, 50, 56), "broad": (80, 60, 62), "plus": (78, 68, 70)},
}
HEIGHT_BANDS = {"petite": 0.94, "average": 1.0, "tall": 1.05}

# z-order: lower draws first
Z = {"legs": 10, "feet": 15, "torso": 20, "full": 20, "waist": 28, "outer": 30, "neck": 40, "wrist": 42,
     "head": 44, "hand": 46}


@dataclass
class Body:
    presentation: str = "women"
    body_type: str = "slim"
    height_band: str = "average"

    def __post_init__(self) -> None:
        types = BODY_TYPES.get(self.presentation, BODY_TYPES["women"])
        if self.body_type not in types:
            self.body_type = next(iter(types))
        self.sh, self.wa, self.hip = types[self.body_type]
        k = HEIGHT_BANDS.get(self.height_band, 1.0)
        top = 110  # crown of the head
        self.cx = W / 2
        self.head_cy = top + 58 * k
        self.head_r = 34
        self.neck_y = top + 116 * k        # base of neck / top of garments
        self.shoulder_y = self.neck_y + 10 * k
        self.bust_y = self.neck_y + 80 * k
        self.waist_y = self.neck_y + 158 * k
        self.hip_y = self.neck_y + 214 * k
        self.crotch_y = self.neck_y + 250 * k
        self.knee_y = self.neck_y + 420 * k
        self.ankle_y = self.neck_y + 596 * k
        self.hand_y = self.neck_y + 248 * k


def slot_transforms(b: Body) -> dict[str, dict]:
    """translate(x,y) scale(sx,sy) for each slot, mapping the 200x200 garment canvas onto the body."""
    cx = b.cx
    torso_sx = b.sh / 38
    torso_sy = (b.hip_y + 8 - b.neck_y) / (150 - 24)
    legs_sx = b.hip / 38
    legs_sy = (b.ankle_y - b.waist_y) / (182 - 12)
    full_sx = b.sh / 34
    full_sy = (b.ankle_y + 8 - b.neck_y) / (196 - 6)

    def t(anchor_x: float, anchor_y: float, x: float, y: float, sx: float, sy: float) -> dict:
        return {"x": round(x - anchor_x * sx, 2), "y": round(y - anchor_y * sy, 2), "sx": round(sx, 4), "sy": round(sy, 4)}

    feet_w = max(b.hip * 2.1, 118)
    return {
        "torso": t(100, 24, cx, b.neck_y, torso_sx, torso_sy),
        "outer": t(100, 24, cx, b.neck_y - 2, torso_sx * 1.04, torso_sy * 1.02),
        "legs": t(100, 12, cx, b.waist_y, legs_sx, legs_sy),
        "full": t(100, 6, cx, b.neck_y - 4, full_sx, full_sy),
        "feet": t(100, 40, cx, b.ankle_y - 6, feet_w / 140, 0.5),
        "hand": t(100, 100, cx + b.hip + 52, b.hand_y + 24, 0.52, 0.52),
        "head": t(100, 100, cx, b.head_cy - 2, 0.44, 0.34),
        "neck": t(100, 44, cx, b.head_cy + 6, 0.62, 0.5),
        "waist": t(100, 100, cx, b.waist_y + 6, (b.wa + 10) / 90, 0.42),
        "wrist": t(100, 100, cx - b.hip - 38, b.hand_y - 18, 0.2, 0.2),
    }


def slot_transforms_for(b: Body, subcategory: str) -> dict:
    tr = slot_transforms(b)
    slot = slot_for(subcategory)
    t = dict(tr[slot])
    if subcategory == "dupatta":  # a dupatta drapes over the shoulders to the knee
        t = {"x": round(b.cx - 100 * 0.95 * b.sh / 60, 2), "y": round(b.neck_y - 24, 2),
             "sx": round(0.95 * b.sh / 60, 4), "sy": round((b.knee_y - b.neck_y) / 200, 4)}
    if subcategory == "scarf":
        t = {"x": round(b.cx - 100 * 0.45, 2), "y": round(b.neck_y - 20, 2), "sx": 0.45, "sy": 0.45}
    return {"slot": slot, "z": Z[slot], **t}


DROP_ZONES = ["head", "neck", "torso", "outer", "full", "waist", "legs", "feet", "hand", "wrist"]


def drop_zones(b: Body) -> dict[str, dict]:
    """Rectangles (x, y, w, h) used as drag-and-drop targets in the frontend."""
    cx = b.cx
    return {
        "head": {"x": cx - 50, "y": b.head_cy - 40, "w": 100, "h": 70, "label": "Head"},
        "neck": {"x": cx - 50, "y": b.head_cy + 30, "w": 100, "h": b.neck_y - b.head_cy - 18, "label": "Neck"},
        "torso": {"x": cx - b.sh - 10, "y": b.neck_y, "w": 2 * b.sh + 20, "h": b.waist_y - b.neck_y, "label": "Top"},
        "waist": {"x": cx - b.wa - 10, "y": b.waist_y - 6, "w": 2 * b.wa + 20, "h": 26, "label": "Waist"},
        "legs": {"x": cx - b.hip - 6, "y": b.waist_y + 20, "w": 2 * b.hip + 12, "h": b.ankle_y - b.waist_y - 30, "label": "Bottom"},
        "feet": {"x": cx - 70, "y": b.ankle_y - 10, "w": 140, "h": 70, "label": "Feet"},
        "hand": {"x": cx + b.hip + 10, "y": b.hand_y - 20, "w": 90, "h": 110, "label": "Bag"},
        "wrist": {"x": cx - b.hip - 70, "y": b.hand_y - 40, "w": 60, "h": 60, "label": "Wrist"},
    }


def _hair(b: Body, style: str, color: str) -> tuple[str, str]:
    """(behind-head, front-of-head) SVG for the hair style."""
    c = HAIR_COLORS.get(color, color if color.startswith("#") else "#1b1714")
    cx, cy, r = b.cx, b.head_cy, b.head_r
    back, front = "", ""
    if style == "long":
        back = f'<path d="M {cx - r - 6} {cy - 6} Q {cx - r - 14} {cy + 110} {cx - r + 4} {cy + 150} L {cx + r - 4} {cy + 150} Q {cx + r + 14} {cy + 110} {cx + r + 6} {cy - 6} Z" fill="{c}"/>'
        front = f'<path d="M {cx - r - 2} {cy - 2} Q {cx - r} {cy - r - 12} {cx} {cy - r - 8} Q {cx + r} {cy - r - 12} {cx + r + 2} {cy - 2} Q {cx + 10} {cy - r + 6} {cx - r - 2} {cy - 2} Z" fill="{c}"/>'
    elif style == "bob":
        back = f'<path d="M {cx - r - 8} {cy - 4} Q {cx - r - 10} {cy + 40} {cx - r} {cy + 44} L {cx + r} {cy + 44} Q {cx + r + 10} {cy + 40} {cx + r + 8} {cy - 4} Z" fill="{c}"/>'
        front = f'<path d="M {cx - r - 4} {cy} Q {cx - r} {cy - r - 12} {cx} {cy - r - 8} Q {cx + r} {cy - r - 12} {cx + r + 4} {cy} Q {cx} {cy - r + 10} {cx - r - 4} {cy} Z" fill="{c}"/>'
    elif style == "bun":
        back = f'<circle cx="{cx}" cy="{cy - r - 10}" r="18" fill="{c}"/>'
        front = f'<path d="M {cx - r - 1} {cy - 4} Q {cx - r} {cy - r - 8} {cx} {cy - r - 6} Q {cx + r} {cy - r - 8} {cx + r + 1} {cy - 4} Q {cx} {cy - r + 8} {cx - r - 1} {cy - 4} Z" fill="{c}"/>'
    elif style == "curly":
        back = "".join(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="16" fill="{c}"/>'
                       for dx, dy in ((-38, -10), (38, -10), (-42, 18), (42, 18), (-34, 44), (34, 44), (-24, -36), (24, -36), (0, -44)))
        front = "".join(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="12" fill="{c}"/>' for dx, dy in ((-20, -30), (0, -36), (20, -30)))
    elif style == "short":
        front = f'<path d="M {cx - r - 2} {cy - 2} Q {cx - r - 2} {cy - r - 14} {cx} {cy - r - 10} Q {cx + r + 2} {cy - r - 14} {cx + r + 2} {cy - 2} Q {cx + 6} {cy - r + 4} {cx - r - 2} {cy - 2} Z" fill="{c}"/>'
    else:  # buzz
        front = f'<path d="M {cx - r} {cy - 6} Q {cx} {cy - r - 8} {cx + r} {cy - 6} Q {cx} {cy - r + 2} {cx - r} {cy - 6} Z" fill="{c}" opacity=".85"/>'
    return back, front


def body_svg_parts(b: Body, skin_tone: int = 4, hair_style: str = "long", hair_color: str = "black") -> tuple[str, str]:
    """(body, hair_front) inner SVG in the W x H viewBox. Garments are drawn between the two."""
    skin = SKIN_TONES[max(0, min(9, skin_tone))]
    shade = "#000000"
    cx = b.cx
    back, front = _hair(b, hair_style, hair_color)
    sh, wa, hip = b.sh, b.wa, b.hip
    arm = 15
    torso = (f"M {cx - 11} {b.neck_y - 14} L {cx - 11} {b.neck_y} Q {cx - sh + 6} {b.neck_y + 2} {cx - sh} {b.shoulder_y + 8} "
             f"Q {cx - sh + 2} {b.bust_y} {cx - wa} {b.waist_y} Q {cx - hip - 4} {b.hip_y - 20} {cx - hip} {b.hip_y} "
             f"L {cx - hip + 8} {b.crotch_y + 30} L {cx + hip - 8} {b.crotch_y + 30} L {cx + hip} {b.hip_y} "
             f"Q {cx + hip + 4} {b.hip_y - 20} {cx + wa} {b.waist_y} Q {cx + sh - 2} {b.bust_y} {cx + sh} {b.shoulder_y + 8} "
             f"Q {cx + sh - 6} {b.neck_y + 2} {cx + 11} {b.neck_y} L {cx + 11} {b.neck_y - 14} Z")
    legs = ""
    for side in (-1, 1):
        x_top_out = cx + side * (hip - 2)
        x_top_in = cx + side * 3
        legs += (f'<path d="M {x_top_out} {b.hip_y} Q {cx + side * (hip - 6)} {b.knee_y - 60} {cx + side * (hip * 0.62)} {b.knee_y} '
                 f'L {cx + side * (hip * 0.5)} {b.ankle_y} L {cx + side * 10} {b.ankle_y} L {cx + side * 12} {b.knee_y} '
                 f'L {x_top_in} {b.crotch_y} Z" fill="{skin}"/>')
        legs += (f'<ellipse cx="{cx + side * (hip * 0.3 + 5)}" cy="{b.ankle_y + 16}" rx="{hip * 0.3 + 6}" ry="12" fill="{skin}"/>')
    arms = ""
    for side in (-1, 1):
        sx = cx + side * (sh - 6)
        hx = cx + side * (hip + 40)
        arms += (f'<path d="M {sx} {b.shoulder_y + 2} Q {cx + side * (sh + 30)} {b.bust_y + 10} {hx} {b.hand_y} '
                 f'L {hx - side * arm} {b.hand_y + 4} Q {cx + side * (sh + 12)} {b.bust_y + 20} {sx - side * 14} {b.shoulder_y + 26} Z" fill="{skin}"/>'
                 f'<ellipse cx="{hx - side * 6}" cy="{b.hand_y + 14}" rx="11" ry="15" fill="{skin}"/>')
    head = (f'<ellipse cx="{cx}" cy="{b.head_cy}" rx="{b.head_r - 4}" ry="{b.head_r + 2}" fill="{skin}"/>'
            f'<ellipse cx="{cx}" cy="{b.head_cy + 4}" rx="{b.head_r - 6}" ry="{b.head_r - 2}" fill="{shade}" opacity=".05"/>')
    body = (back + legs + arms + f'<path d="{torso}" fill="{skin}"/>'
            + f'<path d="{torso}" fill="{shade}" opacity=".04"/>' + head)
    return body, front


def garment_placement_svg(b: Body, subcategory: str, defs: str, inner: str) -> str:
    t = slot_transforms_for(b, subcategory)
    return (f'<g transform="translate({t["x"]} {t["y"]}) scale({t["sx"]} {t["sy"]})"><defs>{defs}</defs>{inner}</g>')


def garment_bbox(b: Body, subcategory: str, canvas_box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Map a canvas-space (x0, y0, x1, y1) box to figure pixels."""
    t = slot_transforms_for(b, subcategory)
    x0, y0, x1, y1 = canvas_box
    return (t["x"] + x0 * t["sx"], t["y"] + y0 * t["sy"], t["x"] + x1 * t["sx"], t["y"] + y1 * t["sy"])


def category_z(subcategory: str) -> int:
    return Z[slot_for(subcategory)] if SUB_TO_CAT.get(subcategory) else 0
