"""My taste, the retailer view, and the demo/admin trigger panel."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import gemini
from . import models as m
from .agents import change_price, launch_new_arrival, new_arrivals_available, restock, watched_products
from .api import Admin, Db, User
from .events import query_view
from .settings import get_settings
from .taste import profile, taste_sentence
from .vocab import label

router = APIRouter(prefix="/api")


@router.get("/taste")
def my_taste(db: Db, user: User) -> dict:
    prof = profile(db, user.id)
    sentence, source = taste_sentence(prof)
    return {**prof, "sentence": sentence, "source": source}


# ------------------------------------------------------------------ retailer

class Memo(BaseModel):
    headline: str = Field(max_length=140)
    bullets: list[str] = Field(min_length=2, max_length=4)
    action: str = Field(max_length=220)


def retailer_numbers(db) -> dict:  # noqa: ANN001
    funnel = query_view(db, "inspo_to_cart_funnel")
    gaps_raw = query_view(db, "gap_report")
    top = query_view(db, "top_saved_attributes")
    cov = (query_view(db, "coverage_summary") or [{}])[0]
    by_sub: dict[str, dict] = defaultdict(lambda: {"saves": 0, "with_match": 0, "variants": []})
    for g in gaps_raw:
        d = by_sub[g["subcategory"]]
        d["saves"] += int(g["saves"])
        d["with_match"] += int(g["saves_with_match"])
        d["variants"].append({"color": g["color"], "fabric": g["fabric"], "saves": int(g["saves_without_match"])})
    gaps = [{"subcategory": k, "label": label(k), "saves": v["saves"], "saves_with_match": v["with_match"],
             "unmatched": v["saves"] - v["with_match"],
             "variants": sorted(v["variants"], key=lambda x: -x["saves"])[:3]} for k, v in by_sub.items()]
    gaps.sort(key=lambda g: -g["unmatched"])
    attrs: dict[str, list] = defaultdict(list)
    for r in top:
        if r["value"]:
            attrs[r["attribute"]].append({"value": r["value"], "label": label(r["value"]), "saves": int(r["saves"])})
    for k in attrs:
        attrs[k] = sorted(attrs[k], key=lambda x: -x["saves"])[:6]
    coverage = {k: (float(v) if isinstance(v, float) else int(v or 0)) for k, v in cov.items()}
    return {"funnel": [{"step": f["step"], "shoppers": int(f["shoppers"]), "events": int(f["events"])} for f in funnel],
            "gaps": gaps[:8], "top_attributes": dict(attrs), "coverage": coverage,
            "source": "BigQuery (wiw dataset)" if get_settings().events_backend == "bigquery" else "Local event log",
            "synthetic_note": ("Includes synthetic shopper history (flagged synthetic=true)."
                               if db.query(m.Event).filter(m.Event.synthetic.is_(True)).first() else "Real shopper activity only.")}


def memo_fallback(n: dict) -> Memo:
    g = n["gaps"][:2]
    f = {s["step"]: s["shoppers"] for s in n["funnel"]}
    c = n["coverage"]
    bullets = [f"{x['label']}: saved {x['saves']} times, {x['saves_with_match']} matched in stock." for x in g]
    bullets.append(f"{c.get('pieces_covered', 0)} of {c.get('pieces', 0)} saved pieces had a good in-stock match.")
    bullets.append(f"{f.get('Purchased', 0)} of {f.get('Inspo uploaded', 0)} shoppers who uploaded inspo went on to buy.")
    top = g[0] if g else None
    return Memo(headline=f"Shoppers keep asking for {top['label'].lower()} we don't stock" if top else "Coverage is healthy",
                bullets=bullets[:4],
                action=(f"Trial a small {top['variants'][0]['color'].replace('_', ' ')} {top['variants'][0]['fabric']} "
                        f"{top['label'].lower()} drop next season." if top else "Keep monitoring saves weekly."))


@router.get("/retailer", dependencies=[Admin])
def retailer(db: Db) -> dict:
    n = retailer_numbers(db)
    if not n["coverage"].get("pieces"):
        return {**n, "memo": {"headline": "No shopper activity yet",
                              "bullets": ["Nobody has saved inspo pieces yet, so there is nothing to report.",
                                          "Numbers appear here as shoppers upload inspo and hang pieces."],
                              "action": "Share the Walk-In Wardrobe link with shoppers."}, "memo_source": "fallback"}
    facts = {"funnel": n["funnel"], "top_gaps": n["gaps"][:4], "coverage": n["coverage"],
             "top_saved": {k: v[:4] for k, v in n["top_attributes"].items()}}
    prompt = ("You are writing a short memo for a fashion merchandiser at Urban Thread (a fictional store). Use ONLY the "
              "numbers below; quote counts exactly, do not invent percentages or data. Headline (max 14 words), 3 bullets, "
              f"one concrete buying action.\n{facts}")
    res = gemini.generate_json("retailer_memo", version="memo-v1", parts=[prompt], schema=Memo, fallback=lambda: memo_fallback(n))
    return {**n, "memo": res.value.model_dump(), "memo_source": res.source}


# ------------------------------------------------------------------ demo / admin panel

@router.get("/demo/state", dependencies=[Admin])
def demo_state(db: Db) -> dict:
    return {"watched": watched_products(db), "new_arrivals": new_arrivals_available(db)}


class PriceIn(BaseModel):
    product_id: str
    new_price_inr: int = Field(ge=99, le=100000)


@router.post("/demo/price", dependencies=[Admin])
def demo_price(body: PriceIn, db: Db) -> dict:
    try:
        out = change_price(db, body.product_id, body.new_price_inr)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    return out


class RestockIn(BaseModel):
    product_id: str
    size: str
    qty: int = Field(default=5, ge=1, le=100)


@router.post("/demo/restock", dependencies=[Admin])
def demo_restock(body: RestockIn, db: Db) -> dict:
    try:
        out = restock(db, body.product_id, body.size, body.qty)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    db.commit()
    return out


@router.post("/demo/new-arrival/{index}", dependencies=[Admin])
def demo_new_arrival(index: int, db: Db) -> dict:
    try:
        out = launch_new_arrival(db, index)
    except (ValueError, IndexError) as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return out


@router.post("/demo/reset", dependencies=[Admin])
def demo_reset() -> dict:
    """Re-seed the synthetic data (demo rehearsals). Never touches anything outside the wiw database."""
    from .seed import seed_all

    return seed_all(images=get_settings().storage_backend == "local", personas=False, with_history=False)
