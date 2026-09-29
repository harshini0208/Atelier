"""Domain services shared by the API, the stylist tools and the agents."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .catalog_search import catalog_search, query_text
from .matching import Matcher, MatchResult, coverage_line, piece_attrs
from .settings import get_settings
from .vocab import DEFAULT_DELIVERY_DAYS, DELIVERY_DAYS, label, size_group, slot_for


@lru_cache(maxsize=1)
def matcher() -> Matcher:
    return Matcher(get_settings().matching)


# ------------------------------------------------------------------ serializers

def product_dict(p: m.Product, city: str | None = None) -> dict:
    d = {
        "id": p.id, "store_id": p.store_id, "brand": p.brand, "name": p.name, "description": p.description,
        "category": p.category, "subcategory": p.subcategory, "subcategory_label": label(p.subcategory),
        "gender_fit": p.gender_fit, "primary_color": p.primary_color, "secondary_color": p.secondary_color,
        "color_family": p.color_family, "pattern": p.pattern, "fabric": p.fabric, "silhouette": p.silhouette,
        "length": p.length, "neckline": p.neckline, "sleeve": p.sleeve, "occasion_tags": p.occasion_tags,
        "style_tags": p.style_tags, "season": p.season, "price_inr": p.price_inr, "mrp_inr": p.mrp_inr,
        "image_url": p.image_url, "slot": slot_for(p.subcategory), "added_at": p.added_at.isoformat(),
        "sizes": [{"size": s.size, "stock": s.stock} for s in p.sizes],
        "in_stock": any(s.stock > 0 for s in p.sizes),
    }
    if city is not None:
        d["delivery_days"] = delivery_days(city)
    return d


def delivery_days(city: str) -> int:
    return DELIVERY_DAYS.get(city, DEFAULT_DELIVERY_DAYS)


def delivery_label(city: str, today: datetime | None = None) -> str:
    days = delivery_days(city)
    eta = (today or datetime.utcnow()) + timedelta(days=days)
    return f"Delivery to {city} by {eta.strftime('%a %d %b')} ({days} days)"


def prefs_dict(p: m.Preferences | None) -> dict | None:
    if p is None:
        return None
    return {"budgets": p.budgets, "sizes": p.sizes, "fit": p.fit, "preferred_materials": p.preferred_materials,
            "avoid_materials": p.avoid_materials, "avoid_colors": p.avoid_colors, "occasions": p.occasions,
            "gender_fit": p.gender_fit}


def piece_dict(p: m.DetectedPiece) -> dict:
    return {"id": p.id, "inspo_id": p.inspo_id, "idx": p.idx, "category": p.category, "subcategory": p.subcategory,
            "subcategory_label": label(p.subcategory), "name": p.name, "gender_fit": p.gender_fit, "color": p.color,
            "secondary_color": p.secondary_color, "pattern": p.pattern, "fabric": p.fabric, "silhouette": p.silhouette,
            "length": p.length, "neckline": p.neckline, "sleeve": p.sleeve, "style_tags": p.style_tags,
            "occasion_tags": p.occasion_tags, "box": p.box, "confidence": p.confidence, "crop_url": p.crop_url,
            "selected": p.selected, "manual": p.manual, "slot": slot_for(p.subcategory)}


def inspo_dict(i: m.InspoImage) -> dict:
    return {"id": i.id, "folder_id": i.folder_id, "image_url": i.image_url, "width": i.width, "height": i.height,
            "status": i.status, "message": i.message, "source": i.source, "created_at": i.created_at.isoformat(),
            "pieces": [piece_dict(p) for p in i.pieces]}


def hanger_dict(db: Session, h: m.Hanger, *, with_top: bool = True) -> dict:
    d = {"id": h.id, "folder_id": h.folder_id, "piece": piece_dict(h.piece), "chosen_product_id": h.chosen_product_id,
         "chosen_size": h.chosen_size, "created_at": h.created_at.isoformat()}
    if h.chosen_product_id:
        d["chosen_product"] = product_dict(db.get(m.Product, h.chosen_product_id))
    if with_top:
        res = matches_for_piece(db, h.user_id, h.piece)
        top = (res.for_you or res.also_view or [None])[0]
        d["top_match"] = top.as_dict() if top else None
        d["covered"], d["covered_in_prefs"] = res.covered, res.covered_in_prefs
    return d


# ------------------------------------------------------------------ matching

def load_products(db: Session, ids: list[str]) -> list[m.Product]:
    if not ids:
        return []
    rows = {p.id: p for p in db.scalars(select(m.Product).where(m.Product.id.in_(ids), m.Product.active.is_(True)))}
    return [rows[i] for i in ids if i in rows]


def user_prefs(db: Session, user_id: str) -> dict | None:
    return prefs_dict(db.get(m.Preferences, user_id))


def matches_for_piece(db: Session, user_id: str, piece, prefs: dict | None = None,  # noqa: ANN001
                      prefs_override: dict | None = None) -> MatchResult:
    attrs = piece_attrs(piece)
    prefs = prefs or user_prefs(db, user_id)
    if prefs_override:
        prefs = {**(prefs or {}), **prefs_override}
    gender = (prefs or {}).get("gender_fit", "any")
    cfg = get_settings().matching["retrieval"]
    ids = catalog_search().candidates(db, category=attrs["category"], subcategory=attrs["subcategory"],
                                      gender=gender, query=query_text(attrs), limit=cfg["max_candidates"])
    products = [product_dict(p) for p in load_products(db, ids)]
    return matcher().rank(attrs, products, prefs)


def look_coverage(db: Session, user_id: str, hangers: list[m.Hanger], prefs: dict | None = None) -> dict:
    prefs = prefs or user_prefs(db, user_id)
    results = [(h, matches_for_piece(db, user_id, h.piece, prefs)) for h in hangers]
    cov = Matcher.coverage([r for _, r in results])
    cov["pieces"] = [{"hanger_id": h.id, "name": h.piece.name, "subcategory": h.piece.subcategory,
                      "covered": r.covered, "covered_in_prefs": r.covered_in_prefs} for h, r in results]
    cov["line"] = coverage_line(cov["covered"], cov["covered_in_prefs"], cov["total"])
    return cov


def look_hangers(db: Session, hanger: m.Hanger) -> list[m.Hanger]:
    """The 'look' a hanger belongs to: hangers from the same inspo image in the same folder."""
    return list(db.scalars(select(m.Hanger).join(m.DetectedPiece).where(
        m.Hanger.user_id == hanger.user_id, m.Hanger.folder_id == hanger.folder_id,
        m.DetectedPiece.inspo_id == hanger.piece.inspo_id).order_by(m.Hanger.id)))


def pick_size(prefs: dict | None, product: m.Product | dict) -> str | None:
    """User's size if in stock; Free for one-size; None means 'ask the shopper'."""
    cat = product["category"] if isinstance(product, dict) else product.category
    sizes = product["sizes"] if isinstance(product, dict) else [{"size": s.size, "stock": s.stock} for s in product.sizes]
    stock = {s["size"]: s["stock"] for s in sizes}
    group = size_group(cat)
    if group == "free":
        return "Free" if stock.get("Free", 0) > 0 else None
    mine = ((prefs or {}).get("sizes") or {}).get(group)
    return mine if mine and stock.get(mine, 0) > 0 else None
