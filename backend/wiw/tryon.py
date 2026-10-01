"""Dress the shopper's mannequin in a look (style board), with Gemini image generation.

The mannequin is one of 16 faceless display mannequins (body type x finish, data/mannequins/). Pieces are sent with
their product photos in layer order (inside -> outside, from the board's z order) plus how each is worn. Results are
cached in media storage by mannequin + pieces + order, so the same look is never rendered twice. Only clothing is
described; the mannequin is faceless and product photos are already cropped below the chin.
"""
from __future__ import annotations

import hashlib
import io
import logging

from PIL import Image
from sqlalchemy.orm import Session

from . import models as m
from .settings import ROOT, get_settings
from .storage import storage
from .vocab import BODY_TYPES, SKIN_TONES, label

log = logging.getLogger(__name__)
VERSION = "tryon-v1"
MANNEQUIN_DIR = ROOT / "data/mannequins"
MANNEQUIN = object()   # placeholder in the prompt parts for the mannequin image
BODY_LABEL = {"slim": "slim", "curvy": "curvy", "plus": "plus-size", "athletic": "athletic"}


class TryOnError(RuntimeError):
    pass


def mannequin_of(db: Session, user_id: str) -> dict:
    mq = db.get(m.Mannequin, user_id)
    return {"body_type": mq.body_type, "skin_tone": mq.skin_tone, "chosen": True} if mq else \
        {"body_type": "slim", "skin_tone": "tan", "chosen": False}


def mannequin_path(body: str, tone: str):  # noqa: ANN201
    if body not in BODY_TYPES or tone not in SKIN_TONES:
        raise ValueError("unknown mannequin")
    return MANNEQUIN_DIR / f"{body}-{tone}.png"


def how_worn(p: m.Product, inner_on_torso: bool) -> str:
    cat = p.category
    if cat == "outerwear":
        return "outermost layer, worn open over everything else"
    if cat == "tops":
        return "worn on the torso" + (", under the outer layer" if inner_on_torso else "")
    if cat == "bottoms":
        return "worn on the legs"
    if cat == "one_piece":
        return "worn on the body as the main garment"
    if cat == "footwear":
        return "on the feet"
    return {"tote": "carried on the shoulder", "sling_bag": "worn across the body", "clutch": "held in one hand",
            "belt": "worn at the waist", "sunglasses": "on the head, pushed up", "watch": "on the wrist",
            "jewellery": "worn as jewellery", "scarf": "around the neck", "dupatta": "draped over the shoulders"}.get(
        p.subcategory, "worn naturally")


def _jpeg(data: bytes) -> bytes:
    im = Image.open(io.BytesIO(data))
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", im.size, "white")
        im = im.convert("RGBA")
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    im = im.convert("RGB")
    im.thumbnail((1024, 1024))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _product_photo(p: m.Product) -> bytes:
    path = p.image_url.removeprefix("/media/")
    data = storage().get(path)
    if not data or path.endswith(".svg"):
        raise TryOnError(f"{p.name} has no product photo to dress the mannequin with")
    return _jpeg(data)


def build_prompt(body: str, tone: str, products: list[m.Product]) -> list:
    """Parts for the image model: the mannequin, each piece (inside -> outside) with how it is worn, then the rules."""
    has_outer = any(p.category == "outerwear" for p in products)
    parts: list = [f"Image 1 is a faceless display mannequin ({BODY_LABEL[body]} body, {tone} finish) on a stand, "
                   "full body, plain light grey studio background.", MANNEQUIN]
    for k, p in enumerate(products, 2):
        parts.append(f"Image {k}: {p.name} ({label(p.subcategory).lower()}, {how_worn(p, has_outer)}). "
                     "Use only the garment in this photo; ignore any person, mannequin or background in it.")
        parts.append(p)
    parts.append(
        "Dress the mannequin from image 1 in exactly these pieces, like a high-street store window display.\n"
        "- Keep the same mannequin: same body shape and proportions, same finish, faceless head, same stand and pose, "
        "full body visible from head to stand.\n"
        "- Layer from inside to outside in the order listed. Inner layers show only where they really would "
        "(collar, hem, cuffs).\n"
        f"- Fit every piece to this {BODY_LABEL[body]} body the way the right size would: realistic drape, folds and "
        "fabric weight; fitted where the garment is fitted, relaxed where it is relaxed; correct length on this body.\n"
        "- Reproduce every piece faithfully: same colour, wash, texture, print, length, cut and details. Do not add, "
        "remove or redesign anything, and add no extra items.\n"
        "- Plain light grey studio background, soft even lighting, photorealistic product photography. "
        "No text, no people, no faces.")
    return parts


def cache_path(user_id: str, body: str, tone: str, product_ids: list[str]) -> str:
    s = get_settings()
    key = hashlib.sha256("|".join([VERSION, s.gemini_image_model, body, tone, *product_ids]).encode()).hexdigest()[:24]
    return f"tryon/{user_id}/{key}.png"


def dress(db: Session, user: m.User, product_ids: list[str], *, cached_only: bool = False) -> dict:
    """product_ids in layer order, inside first. Returns {image_url, cached} or raises TryOnError."""
    s = get_settings()
    if not product_ids:
        raise TryOnError("Put a few pieces on the board first")
    if len(product_ids) > 8:
        raise TryOnError("A mannequin can wear up to 8 pieces at once")
    mq = mannequin_of(db, user.id)
    body, tone = mq["body_type"], mq["skin_tone"]
    path = cache_path(user.id, body, tone, product_ids)
    if storage().exists(path):
        return {"image_url": f"/media/{path}", "cached": True}
    if cached_only:
        return {"image_url": None, "cached": False}
    if s.gemini_mode != "live":
        raise TryOnError("Dressing the mannequin needs live Gemini (GEMINI_MODE=live)")
    products = []
    for pid in product_ids:
        p = db.get(m.Product, pid)
        if not p:
            raise TryOnError(f"Unknown product {pid}")
        products.append(p)
    from google.genai import types

    from .gemini import client

    def image(data: bytes):  # noqa: ANN202
        return types.Part.from_bytes(data=data, mime_type="image/jpeg")

    contents = []
    for part in build_prompt(body, tone, products):
        if part is MANNEQUIN:
            contents.append(image(_jpeg(mannequin_path(body, tone).read_bytes())))
        elif isinstance(part, m.Product):
            contents.append(image(_product_photo(part)))
        else:
            contents.append(part)
    try:
        resp = client().models.generate_content(
            model=s.gemini_image_model, contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                               image_config=types.ImageConfig(aspect_ratio="3:4")))
        data = next((p.inline_data.data for p in resp.candidates[0].content.parts if p.inline_data), None)
    except Exception as e:  # noqa: BLE001
        log.warning("mannequin try-on failed: %s", e)
        raise TryOnError("We couldn't dress the mannequin right now. Try again in a moment.") from e
    if not data:
        raise TryOnError("We couldn't dress the mannequin with these pieces. Try removing one.")
    im = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    storage().put(path, buf.getvalue(), "image/png")
    return {"image_url": f"/media/{path}", "cached": False}
