"""Outfit split: Gemini vision -> validated pieces with normalized boxes -> server-side crops."""
from __future__ import annotations

import hashlib
import io
import json
from functools import lru_cache
from typing import Literal

from PIL import Image as PILImage
from PIL import ImageFilter, ImageStat
from pydantic import BaseModel, Field, field_validator

from . import gemini
from .settings import ROOT
from .vocab import (ALL_SUBCATEGORIES, COLORS, FABRICS, LENGTHS, NECKLINES, OCCASIONS, PATTERNS, SILHOUETTES,
                    SLEEVES, STYLE_TAGS, SUB_TO_CAT)

PROMPT_VERSION = "detect-v4"
LOW_CONFIDENCE = 0.45

SYSTEM = (
    "You are a fashion cataloguer. You describe clothing, footwear and accessories only. "
    "Never identify, name, or describe people, faces, bodies, ethnicity, age or any personal attribute. "
    "Ignore app interface elements (usernames, captions, icons)."
)
PROMPT = """List every apparel, footwear and accessory piece visibly worn in this outfit image.

Rules:
- One entry per piece. A pair of shoes, earrings or similar counts as ONE piece.
- If several people are in the image, describe only the most prominent outfit (largest, most central).
- Include partly visible pieces, with lower confidence.
- Use only the allowed enum values. Pick the closest subcategory. Trousers: wide_leg_trousers only when the legs are
  clearly wider at the hem than at the thigh and hang loose; straight, slim or tapered smart trousers -> chinos;
  denim -> jeans. A flared skirt with a blouse worn for a wedding -> lehenga. 'none' is allowed for length/neckline/sleeve/silhouette
  when they do not apply (shoes, bags, jewellery).
- fabric is your best guess from texture and drape.
- name: a short plain shopping name, e.g. "Ivory linen shirt". No brand names.
- box_2d: [ymin, xmin, ymax, xmax] normalized to 0-1000, tight around the piece.
- confidence: 0-1, how sure you are about the piece and its attributes.
- image_quality: "ok", "blurry" (too blurry or small to judge), or "no_outfit" (no clothing visible).
Return JSON only."""


class DetectedPieceModel(BaseModel):
    subcategory: Literal[tuple(ALL_SUBCATEGORIES)]  # type: ignore[valid-type]
    name: str = Field(max_length=80)
    gender_fit: Literal["women", "men", "unisex"] = "unisex"
    color: Literal[tuple(COLORS)]  # type: ignore[valid-type]
    secondary_color: Literal[tuple(COLORS)] | None = None  # type: ignore[valid-type]
    pattern: Literal[tuple(PATTERNS)] = "solid"  # type: ignore[valid-type]
    fabric: Literal[tuple(FABRICS)] = "cotton"  # type: ignore[valid-type]
    silhouette: Literal[tuple(SILHOUETTES)] = "regular"  # type: ignore[valid-type]
    length: Literal[tuple(LENGTHS)] = "none"  # type: ignore[valid-type]
    neckline: Literal[tuple(NECKLINES)] = "none"  # type: ignore[valid-type]
    sleeve: Literal[tuple(SLEEVES)] = "none"  # type: ignore[valid-type]
    style_tags: list[Literal[tuple(STYLE_TAGS)]] = Field(default_factory=list, max_length=5)  # type: ignore[valid-type]
    occasion_tags: list[Literal[tuple(OCCASIONS)]] = Field(default_factory=list, max_length=5)  # type: ignore[valid-type]
    box_2d: list[int] = Field(min_length=4, max_length=4)
    confidence: float = Field(ge=0, le=1)

    @field_validator("box_2d")
    @classmethod
    def _box(cls, v: list[int]) -> list[int]:
        y0, x0, y1, x1 = (max(0, min(1000, int(n))) for n in v)
        if y1 <= y0 or x1 <= x0:
            raise ValueError("empty box")
        return [y0, x0, y1, x1]


class Detection(BaseModel):
    image_quality: Literal["ok", "blurry", "no_outfit"] = "ok"
    people_count: int = Field(default=1, ge=0, le=50)
    pieces: list[DetectedPieceModel] = Field(default_factory=list, max_length=12)


def _dedupe(d: Detection) -> Detection:
    """Drop duplicate pieces (same subcategory, heavily overlapping boxes), e.g. left/right shoe."""
    kept: list[DetectedPieceModel] = []
    for p in sorted(d.pieces, key=lambda p: -p.confidence):
        dup = next((k for k in kept if k.subcategory == p.subcategory), None)
        if dup and (SUB_TO_CAT[p.subcategory] in ("footwear", "accessories") or _iou(dup.box_2d, p.box_2d) > 0.3):
            dup.box_2d = [min(dup.box_2d[0], p.box_2d[0]), min(dup.box_2d[1], p.box_2d[1]),
                          max(dup.box_2d[2], p.box_2d[2]), max(dup.box_2d[3], p.box_2d[3])]
            continue
        kept.append(p)
    d.pieces = sorted(kept, key=lambda p: (p.box_2d[0], p.box_2d[1]))
    return d


def _iou(a: list[int], b: list[int]) -> float:
    y0, x0 = max(a[0], b[0]), max(a[1], b[1])
    y1, x1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, y1 - y0) * max(0, x1 - x0)
    area = lambda r: (r[2] - r[0]) * (r[3] - r[1])  # noqa: E731
    return inter / (area(a) + area(b) - inter) if inter else 0.0


@lru_cache(maxsize=1)
def _truth_by_sha() -> dict[str, dict]:
    p = ROOT / "demo/inspo/generated/truth.json"
    if not p.exists():
        return {}
    return {v["sha256"]: v for v in json.loads(p.read_text()).values()}


def image_quality(data: bytes) -> str:
    """Cheap local check used by the fallback: tiny, flat or very blurry images."""
    img = PILImage.open(io.BytesIO(data)).convert("L")
    if min(img.size) < 120:
        return "blurry"
    small = img.resize((256, int(256 * img.height / img.width) or 1))
    if ImageStat.Stat(small).stddev[0] < 6:
        return "no_outfit"  # a flat, empty image
    edges = small.filter(ImageFilter.FIND_EDGES).crop((2, 2, small.width - 2, small.height - 2))
    return "blurry" if ImageStat.Stat(edges).var[0] < 25 else "ok"


def fallback_detection(data: bytes) -> Detection:
    """Deterministic fallback: exact ground truth for the generated demo inspo; otherwise an honest empty result
    (the UI then offers tap-to-add)."""
    truth = _truth_by_sha().get(hashlib.sha256(data).hexdigest())
    if truth:
        return Detection(image_quality="ok", people_count=1, pieces=[
            DetectedPieceModel.model_validate({k: v for k, v in p.items() if k in DetectedPieceModel.model_fields})
            for p in truth["pieces"]])
    return Detection(image_quality=image_quality(data), people_count=0, pieces=[])


def detect(data: bytes, mime_type: str = "image/png") -> gemini.Result[Detection]:
    return gemini.generate_json(
        "detect", version=PROMPT_VERSION, system=SYSTEM, parts=[gemini.Image(data, mime_type), PROMPT],
        schema=Detection, fallback=lambda: fallback_detection(data), validate=_dedupe, temperature=0.1)


def crop(data: bytes, box_2d: list[int], pad: float = 0.04) -> bytes:
    """Crop a piece (box on 0..1000) with a little padding; returns PNG bytes."""
    img = PILImage.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    y0, x0, y1, x1 = box_2d
    px, py = pad * (x1 - x0) + 4, pad * (y1 - y0) + 4
    left = max(0, int((x0 - px) / 1000 * w))
    top = max(0, int((y0 - py) / 1000 * h))
    right = min(w, int((x1 + px) / 1000 * w))
    bottom = min(h, int((y1 + py) / 1000 * h))
    piece = img.crop((left, top, max(right, left + 1), max(bottom, top + 1)))
    piece.thumbnail((480, 480))
    buf = io.BytesIO()
    piece.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def normalize_upload(data: bytes, max_side: int = 1600) -> tuple[bytes, int, int, str]:
    """Validate and normalise an uploaded screenshot. Returns (png_or_jpeg_bytes, width, height, mime)."""
    img = PILImage.open(io.BytesIO(data))
    img.load()
    fmt = (img.format or "PNG").upper()
    if max(img.size) > max_side or fmt not in ("PNG", "JPEG", "WEBP"):
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue(), img.width, img.height, "image/jpeg"
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt]
    return data, img.width, img.height, mime
