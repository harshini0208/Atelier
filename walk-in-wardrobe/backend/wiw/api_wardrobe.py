"""Style board: a plain canvas per folder where shoppers arrange real store pieces, saved looks, "Style it for me"."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import gemini
from . import models as m
from .api import Db, User, own_folder
from .services import matches_for_piece, product_dict
from .settings import get_settings
from .styling import auto_layout, complete_the_look, folder_hangers, style_options
from .vocab import label

router = APIRouter(prefix="/api")
_REASONS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="look-reasons")


@router.get("/folders/{folder_id}/tray")
def tray(folder_id: int, db: Db, user: User) -> dict:
    """Pieces available for the board: each hanger's store product (chosen, else its best in-store match)."""
    own_folder(db, user, folder_id)
    items = []
    for i, h in enumerate(folder_hangers(db, user.id, folder_id), 1):
        entry = {"hanger_id": h.id, "hanger_index": i, "piece": {"name": h.piece.name, "crop_url": h.piece.crop_url,
                                                                "subcategory": h.piece.subcategory}}
        if h.chosen_product_id:
            entry["product"], entry["source"] = product_dict(db.get(m.Product, h.chosen_product_id)), "chosen"
        else:
            res = matches_for_piece(db, user.id, h.piece)
            top = (res.for_you or res.also_view or [None])[0]
            entry["product"] = top.product if top else None
            entry["source"] = "top_match" if top else "not_in_store"
        items.append(entry)
    return {"items": items}


class Placement(BaseModel):
    product_id: str
    x: float | None = Field(default=None, ge=-50, le=150)   # % of board width (left edge)
    y: float | None = Field(default=None, ge=-50, le=150)   # % of board height (top edge)
    w: float | None = Field(default=None, ge=5, le=100)     # % of board width
    z: int | None = Field(default=None, ge=0, le=999)       # layer order: higher is on top (worn outside)


class LookIn(BaseModel):
    name: str = Field(default="My look", max_length=80)
    placements: list[Placement]
    reason: str = Field(default="", max_length=300)


def look_dict(db, lk: m.Look) -> dict:  # noqa: ANN001
    items = []
    for pl in lk.placements:
        p = db.get(m.Product, pl["product_id"])
        if p:
            items.append({"product": product_dict(p), **{k: pl.get(k) for k in ("x", "y", "w", "z")}})
    return {"id": lk.id, "name": lk.name, "reason": lk.reason, "items": items, "created_at": lk.created_at.isoformat(),
            "total_inr": sum(i["product"]["price_inr"] for i in items)}


def normalise_placements(db, placements: list[Placement]) -> list[dict]:  # noqa: ANN001
    products, seen = [], set()
    for pl in placements:
        p = db.get(m.Product, pl.product_id)
        if not p:
            raise HTTPException(404, f"Unknown product {pl.product_id}")
        if p.id in seen:
            raise HTTPException(422, f"{p.name} is on the board twice")
        seen.add(p.id)
        products.append(product_dict(p))
    layout = {d["product_id"]: d for d in auto_layout(products)}  # defaults for anything not positioned yet
    out = []
    for pl in placements:
        d = dict(layout[pl.product_id])
        d.update({k: v for k, v in pl.model_dump().items() if v is not None})
        out.append(d)
    return out


@router.get("/folders/{folder_id}/looks")
def list_looks(folder_id: int, db: Db, user: User) -> list[dict]:
    own_folder(db, user, folder_id)
    rows = db.scalars(select(m.Look).where(m.Look.folder_id == folder_id).order_by(m.Look.created_at.desc(), m.Look.id.desc()))
    return [look_dict(db, lk) for lk in rows]


@router.post("/folders/{folder_id}/looks")
def save_look(folder_id: int, body: LookIn, db: Db, user: User) -> dict:
    own_folder(db, user, folder_id)
    if not body.placements:
        raise HTTPException(422, "Put at least one piece on the board first")
    look = m.Look(user_id=user.id, folder_id=folder_id, name=body.name.strip() or "My look",
                  placements=normalise_placements(db, body.placements), reason=body.reason)
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
    return _style(db, user, folder_id, None, body, "Hang a few pieces in this folder first and I'll style them for you.")


def _style(db, user: m.User, folder_id: int | None, hangers: list | None, body: StyleIn, empty: str,  # noqa: ANN001
           owned: frozenset[str] = frozenset()) -> dict:
    options = [o.as_dict() for o in style_options(db, user.id, folder_id, 3, body.occasion, body.formality,
                                                  hangers=hangers, owned=owned)]
    if not options:
        return {"options": [], "message": empty}
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

    def fallback() -> ReasonLines:
        return ReasonLines(lines=[_fallback_line(o, body.occasion, body.formality) for o in options])

    # The one-line "why" is nice to have, never worth a long wait: past the timeout the rule-based lines are used and
    # the Gemini answer still lands in the cache for next time.
    fut = _REASONS.submit(gemini.generate_json, "look_reasons", version="reasons-v1", parts=[prompt], schema=ReasonLines,
                          validate=validate, fallback=fallback)
    try:
        res = fut.result(timeout=get_settings().matching["stylist"].get("reasons_timeout_s", 8))
    except FutureTimeout:
        res = gemini.Result(fallback(), "fallback")
    for o, line in zip(options, res.value.lines):
        o["reason"] = line
        o["layout"] = auto_layout([i["product"] for i in o["items"]])
    extras = complete_the_look(db, user.id, [i["product"] for i in options[0]["items"]], limit=3)
    return {"options": options, "source": res.source, "complete_the_look": extras}



# ------------------------------------------------------------------ the rail's style board (no folder)

@router.get("/rail/tray")
def rail_tray(db: Db, user: User) -> dict:
    from .rail import rail

    return {"items": [{"key": e["product"]["id"], "product": e["product"], "owned": e["owned"],
                       "sources": [s["label"] for s in e["sources"]]} for e in rail(db, user)["items"]]}


@router.get("/rail/looks")
def rail_looks(db: Db, user: User) -> list[dict]:
    rows = db.scalars(select(m.RailLook).where(m.RailLook.user_id == user.id)
                      .order_by(m.RailLook.created_at.desc(), m.RailLook.id.desc()))
    return [look_dict(db, lk) for lk in rows]


@router.post("/rail/looks")
def save_rail_look(body: LookIn, db: Db, user: User) -> dict:
    if not body.placements:
        raise HTTPException(422, "Put at least one piece on the board first")
    look = m.RailLook(user_id=user.id, name=body.name.strip() or "My look",
                      placements=normalise_placements(db, body.placements), reason=body.reason)
    db.add(look)
    db.commit()
    return look_dict(db, look)


@router.delete("/rail/looks/{look_id}")
def delete_rail_look(look_id: int, db: Db, user: User) -> dict:
    lk = db.get(m.RailLook, look_id)
    if not lk or lk.user_id != user.id:
        raise HTTPException(404, "Look not found")
    db.delete(lk)
    db.commit()
    return {"ok": True}


@router.post("/rail/style")
def style_rail(body: StyleIn, db: Db, user: User) -> dict:
    from .rail import owned_ids, rail_hangers

    return _style(db, user, None, rail_hangers(db, user), body,
                  "Your rail is empty. Wishlist a few pieces in the Shop and I'll style them for you.", owned_ids(db, user))
