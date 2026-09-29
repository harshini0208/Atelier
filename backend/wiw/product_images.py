"""Store-owner product photos (backend only; customers can never upload these).

Drop files named after the product ID into data/product_images/, e.g. data/product_images/ut-001.jpg
(jpg, jpeg, png or webp). `make product-images` publishes them to media storage and points each product at its
photo. Products without a photo keep their generated flat-lay. `make product-manifest` writes a CSV listing every
product ID with its name, so you know which file name belongs to which product.

Tip: photos on a plain white or transparent background look best on the style board.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .settings import ROOT
from .storage import storage

PHOTO_DIR = ROOT / "data/product_images"
EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_SIDE = 1400


def find_photo(product_id: str) -> Path | None:
    for ext in EXTS:
        for cand in (PHOTO_DIR / f"{product_id}{ext}", PHOTO_DIR / f"{product_id}{ext.upper()}"):
            if cand.is_file():
                return cand
    return None


def prepare(path: Path) -> tuple[bytes, str, str]:
    """Normalise a photo: fix EXIF rotation, strip metadata, cap the size. Keeps transparency for PNG/WebP."""
    img = ImageOps.exif_transpose(Image.open(path))
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA", "P") and path.suffix.lower() in (".png", ".webp"):
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        return buf.getvalue(), ".png", "image/png"
    img.convert("RGB").save(buf, "JPEG", quality=88, optimize=True)
    return buf.getvalue(), ".jpg", "image/jpeg"


def apply_photos(db: Session) -> int:
    """Publish every photo in PHOTO_DIR and point its product at it. Returns how many products got a photo."""
    if not PHOTO_DIR.exists():
        return 0
    n = 0
    for p in db.scalars(select(m.Product)):
        src = find_photo(p.id)
        if not src:
            continue
        data, ext, mime = prepare(src)
        p.image_url = storage().put(f"products/photos/{p.id}{ext}", data, mime)
        n += 1
    return n


def write_manifest(db: Session, out: Path | None = None) -> Path:
    out = out or PHOTO_DIR / "manifest.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file_name", "product_id", "name", "section", "category", "colour", "has_photo"])
        for p in db.scalars(select(m.Product).order_by(m.Product.id)):
            w.writerow([f"{p.id}.jpg", p.id, p.name, p.gender_fit, p.subcategory, p.primary_color,
                        "yes" if find_photo(p.id) else "no"])
    return out
