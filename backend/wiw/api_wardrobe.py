"""Walk-in wardrobe: avatar, mannequin geometry, saved looks, "Style it for me"."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import gemini
from . import models as m
from .api import Db, User, own_folder
from .mannequin import (BODY_TYPES, DROP_ZONES, H, HAIR_COLORS, HAIR_STYLES, HEIGHT_BANDS, W, Body, body_svg_parts,
                        drop_zones, slot_transforms_for)
from .services import product_dict
from .styling import complete_the_look, folder_hangers, style_options
from .vocab import ALL_SUBCATEGORIES, label, slot_for

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ avatar

class AvatarIn(BaseModel):
    presentation: Literal["women", "men"] = "women"
    body_type: str = "slim"
    height_band: Literal["petite", "average", "tall"] = "average"
    skin_tone: int = Field(default=4, ge=0, le=9)
    hair_style: Literal["long", "bob", "bun", "curly", "short", "buzz"] = "long"
    hair_color: Literal["black", "dark_brown", "brown", "auburn", "blonde", "grey"] = "black"


def fix_avatar(a: AvatarIn) -> AvatarIn:
    if a.body_type not in BODY_TYPES[a.presentation]:
        a.body_type = next(iter(BODY_TYPES[a.presentation]))
    return a


def avatar_dict(a: m.Avatar) -> dict:
    return {"presentation": a.presentation, "body_type": a.body_type, "height_band": a.height_band,
            "skin_tone": a.skin_tone, "hair_style": a.hair_style, "hair_color": a.hair_color}


@router.get("/avatar")
def get_avatar(db: Db, user: User) -> dict:
    a = db.get(m.Avatar, user.id) or m.Avatar(user_id=user.id)
    return avatar_dict(a)


@router.put("/avatar")
def put_avatar(body: AvatarIn, db: Db, user: User) -> dict:
    body = fix_avatar(body)
    a = db.get(m.Avatar, user.id) or m.Avatar(user_id=user.id)
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    db.add(a)
    db.commit()
    return avatar_dict(a)


class DescribeIn(BaseModel):
    text: str = Field(min_length=2, max_length=400)
    presentation: Literal["women", "men"] | None = None


AVATAR_PROMPT = """Convert the shopper's own description of themselves into parameters for drawing a simple, faceless
2D fashion mannequin. Use only what they say; keep defaults (average height, the first body type) when not stated.
body_type must be one of: women -> {women}; men -> {men}. skin_tone is an index 0 (lightest) to 9 (deepest).
hair_style: long, bob, bun, curly, short, buzz. hair_color: black, dark_brown, brown, auburn, blonde, grey.
Description: "{text}"
"""


def describe_fallback(text: str, presentation: str | None) -> AvatarIn:
    t = text.lower()
    pres = presentation or ("men" if re.search(r"\b(man|male|guy|he|him|men)\b", t) else "women")
    body = {"women": [("hourglass", r"hourglass|curvy"), ("pear", r"pear|wide hips|bottom.?heavy|hips"),
                      ("apple", r"apple|tummy|midsection"), ("plus", r"plus|full.?figured|xl|curvy plus")],
            "men": [("athletic", r"athletic|fit|muscular|gym"), ("broad", r"broad|stocky|big shoulders"),
                    ("plus", r"plus|heavy|big|xl")]}[pres]
    bt = next((b for b, pat in body if re.search(pat, t)), "slim")
    height = "tall" if re.search(r"\btall\b|5'?\s?(9|10|11)|6'", t) else "petite" if re.search(r"petite|short|5'?\s?[0-2]\b|4'", t) else "average"
    tones = [(r"very fair|porcelain", 0), (r"fair|light", 1), (r"wheatish|medium|olive", 4), (r"tan|dusky|brown", 6),
             (r"dark|deep", 8)]
    skin = next((v for pat, v in tones if re.search(pat, t)), 4)
    hair = next((h for h in ("curly", "bob", "bun", "buzz", "short", "long") if h in t), "short" if pres == "men" else "long")
    if re.search(r"bald|shaved", t):
        hair = "buzz"
    colors = [("blonde", r"blond"), ("auburn", r"auburn|red(dish)? hair|ginger"), ("grey", r"grey|gray|silver hair"),
              ("brown", r"\bbrown hair|light brown"), ("dark_brown", r"dark brown")]
    hc = next((c for c, pat in colors if re.search(pat, t)), "black")
    return AvatarIn(presentation=pres, body_type=bt, height_band=height, skin_tone=skin, hair_style=hair, hair_color=hc)


@router.post("/avatar/describe")
def describe(body: DescribeIn, user: User) -> dict:
    prompt = AVATAR_PROMPT.format(women=", ".join(BODY_TYPES["women"]), men=", ".join(BODY_TYPES["men"]), text=body.text)
    res = gemini.generate_json("avatar", version="avatar-v1", parts=[prompt], schema=AvatarIn,
                               fallback=lambda: describe_fallback(body.text, body.presentation), validate=fix_avatar,
                               system="You only output drawing parameters. You never judge or comment on appearance.")
    out = res.value
    if body.presentation and out.presentation != body.presentation:
        out.presentation = body.presentation
        out = fix_avatar(out)
    return {**out.model_dump(), "source": res.source}


@router.get("/mannequin")
def mannequin(presentation: str = "women", body_type: str = "slim", height_band: str = "average", skin_tone: int = 4,
              hair_style: str = "long", hair_color: str = "black") -> dict:
    presentation = presentation if presentation in BODY_TYPES else "women"
    b = Body(presentation, body_type, height_band if height_band in HEIGHT_BANDS else "average")
    body, hair_front = body_svg_parts(b, max(0, min(9, skin_tone)), hair_style if hair_style in HAIR_STYLES else "long",
                                      hair_color if hair_color in HAIR_COLORS else "black")
    return {"width": W, "height": H, "body": body, "hair_front": hair_front,
            "transforms": {s: slot_transforms_for(b, s) for s in ALL_SUBCATEGORIES},
            "drop_zones": drop_zones(b), "zone_order": DROP_ZONES}


# ------------------------------------------------------------------ tray + looks

@router.get("/folders/{folder_id}/tray")
def tray(folder_id: int, db: Db, user: User) -> dict:
    """What can go on the mannequin: each hanger's chosen product, else its best in-store match."""
    from .services import matches_for_piece

    own_folder(db, user, folder_id)
    items = []
    for i, h in enumerate(folder_hangers(db, user.id, folder_id), 1):
        entry = {"hanger_id": h.id, "hanger_index": i, "piece": {"name": h.piece.name, "crop_url": h.piece.crop_url,
                                                                "subcategory": h.piece.subcategory}}
        if h.chosen_product_id:
            entry["product"] = product_dict(db.get(m.Product, h.chosen_product_id))
            entry["source"] = "chosen"
        else:
            res = matches_for_piece(db, user.id, h.piece)
            top = (res.for_you or res.also_view or [None])[0]
            entry["product"] = top.product if top else None
            entry["source"] = "top_match" if top else "not_in_store"
        entry["slot"] = slot_for(entry["product"]["subcategory"] if entry["product"] else h.piece.subcategory)
        items.append(entry)
    return {"items": items}


class Placement(BaseModel):
    product_id: str
    slot: str | None = None


class LookIn(BaseModel):
    name: str = Field(default="My look", max_length=80)
    placements: list[Placement]
    reason: str = Field(default="", max_length=300)


def look_dict(db, l: m.Look) -> dict:  # noqa: ANN001, E741
    items = []
    for pl in l.placements:
        p = db.get(m.Product, pl["product_id"])
        if p:
            items.append({"product": product_dict(p), "slot": pl.get("slot") or slot_for(p.subcategory)})
    return {"id": l.id, "name": l.name, "reason": l.reason, "items": items, "created_at": l.created_at.isoformat(),
            "total_inr": sum(i["product"]["price_inr"] for i in items)}


@router.get("/folders/{folder_id}/looks")
def list_looks(folder_id: int, db: Db, user: User) -> list[dict]:
    own_folder(db, user, folder_id)
    rows = db.scalars(select(m.Look).where(m.Look.folder_id == folder_id).order_by(m.Look.created_at.desc(), m.Look.id.desc()))
    return [look_dict(db, lk) for lk in rows]


@router.post("/folders/{folder_id}/looks")
def save_look(folder_id: int, body: LookIn, db: Db, user: User) -> dict:
    own_folder(db, user, folder_id)
    placements, slots = [], set()
    for pl in body.placements:
        p = db.get(m.Product, pl.product_id)
        if not p:
            raise HTTPException(404, f"Unknown product {pl.product_id}")
        slot = slot_for(p.subcategory)
        if slot in slots:
            raise HTTPException(422, f"Two pieces can't share the {slot} slot")
        slots.add(slot)
        placements.append({"product_id": p.id, "slot": slot})
    look = m.Look(user_id=user.id, folder_id=folder_id, name=body.name.strip() or "My look", placements=placements,
                  reason=body.reason)
    db.add(look)
    db.commit()
    return look_dict(db, look)


@router.delete("/looks/{look_id}")
def delete_look(look_id: int, db: Db, user: User) -> dict:
    lk = db.get(m.Look, look_id)
    if not lk or lk.user_id != user.id:
        raise HTTPException(404, "Look not found")
    db.delete(lk)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ style it for me

class ReasonLines(BaseModel):
    lines: list[str] = Field(min_length=1, max_length=4)


class StyleIn(BaseModel):
    occasion: str | None = Field(default=None, max_length=60)
    formality: Literal["more_casual", "more_formal", "more_festive"] | None = None


def _fallback_line(o: dict, occasion: str | None, formality: str | None) -> str:
    items = o["items"]
    fabrics = sorted({i["product"]["fabric"] for i in items if i["product"]["fabric"] not in ("metal", "synthetic")})
    colors = list(dict.fromkeys(label(i["product"]["primary_color"]).lower() for i in items))[:3]
    mood = {"more_casual": "easy and relaxed", "more_formal": "polished", "more_festive": "festive"}.get(formality or "", "")
    head = f"{' and '.join(fabrics[:2]).capitalize() or 'Mixed textures'} in {', '.join(colors)}"
    return head + (f", {mood}" if mood else "") + (f" for {occasion}" if occasion else "") + "."


@router.post("/folders/{folder_id}/style")
def style_it(folder_id: int, body: StyleIn, db: Db, user: User) -> dict:
    own_folder(db, user, folder_id)
    options = [o.as_dict() for o in style_options(db, user.id, folder_id, 3, body.occasion, body.formality)]
    if not options:
        return {"options": [], "message": "Hang a few pieces in this folder first and I'll style them for you."}
    summary = "\n".join(f"Look {k + 1}: " + ", ".join(f"{i['product']['name']} ({i['product']['fabric']}, "
                                                        f"{i['product']['primary_color']})" for i in o["items"])
                        for k, o in enumerate(options))
    prompt = (f"Write one short line (max 16 words) for each look explaining why it works"
              f"{' for ' + body.occasion if body.occasion else ''}"
              f"{' with a ' + body.formality.replace('_', ' ') + ' feel' if body.formality else ''}. "
              f"Mention colour or fabric. Do not mention prices or invent items.\n{summary}")

    def validate(r: ReasonLines) -> ReasonLines:
        if len(r.lines) != len(options):
            raise ValueError("wrong number of lines")
        r.lines = [ln.strip()[:140] for ln in r.lines]
        return r

    res = gemini.generate_json("look_reasons", version="reasons-v1", parts=[prompt], schema=ReasonLines,
                               validate=validate, fallback=lambda: ReasonLines(lines=[
                                   _fallback_line(o, body.occasion, body.formality) for o in options]))
    for o, line in zip(options, res.value.lines):
        o["reason"] = line
    extras = complete_the_look(db, user.id, [i["product"] for i in options[0]["items"]], limit=3)
    return {"options": options, "source": res.source, "complete_the_look": extras}
