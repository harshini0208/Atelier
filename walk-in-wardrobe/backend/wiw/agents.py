"""Agentic extras: catalog events (price change, restock, new arrival) trigger watchers that notify shoppers.

Each watcher is deterministic: it re-runs the matcher over hangers and compares with the event. Notifications
are written to the DB and an `alert_sent` event is emitted per notification.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .events import emit
from .services import matches_for_piece, prefs_dict, product_dict  # noqa: F401
from .settings import ROOT, get_settings
from .taste import profile, taste_score
from .colors import color_family as color_family_of
from .vocab import SUB_TO_CAT, size_group


def _watchers(db: Session, product: m.Product) -> list[tuple[m.Hanger, float]]:
    """(hanger, style score) for every hanger this product is a good *style* match for, ignoring stock
    (so a sold-out item can still trigger a restock alert), plus hangers that chose it."""
    from .matching import piece_attrs
    from .services import matcher

    mt = matcher()
    pd = product_dict(product)
    out = []
    hangers = db.scalars(select(m.Hanger).join(m.DetectedPiece).where(m.DetectedPiece.category == product.category)
                         .order_by(m.Hanger.id))
    for h in hangers:
        piece = piece_attrs(h.piece)
        score, _ = mt.style_score(piece, pd)
        if h.chosen_product_id == product.id or (score >= mt.threshold and mt.sub_sim(piece["subcategory"], pd["subcategory"]) >= mt.min_sub):
            prefs = prefs_dict(db.get(m.Preferences, h.user_id)) or {}
            if prefs.get("gender_fit") in ("women", "men") and pd["gender_fit"] not in (prefs["gender_fit"], "unisex"):
                continue
            out.append((h, score))
    return out


def _notify(db: Session, user_id: str, kind: str, title: str, body: str, product_id: str | None, hanger_id: int | None) -> None:
    db.add(m.Notification(user_id=user_id, kind=kind, title=title, body=body, product_id=product_id, hanger_id=hanger_id))
    p = db.get(m.Product, product_id) if product_id else None
    emit(db, "alert_sent", user_id, product_id=product_id, subcategory=p.subcategory if p else None)


def change_price(db: Session, product_id: str, new_price: int) -> dict:
    p = db.get(m.Product, product_id)
    if not p:
        raise ValueError("unknown product")
    old = p.price_inr
    p.price_inr = int(new_price)
    db.add(m.PriceHistory(product_id=p.id, price_inr=p.price_inr, mrp_inr=p.mrp_inr))
    db.flush()
    notified = []
    min_pct = get_settings().matching["alerts"]["price_drop_min_pct"]
    if new_price < old and (old - new_price) * 100 / old >= min_pct:
        seen = set()
        for h, _tier in _watchers(db, p):
            if h.user_id in seen:
                continue
            seen.add(h.user_id)
            prefs = prefs_dict(db.get(m.Preferences, h.user_id)) or {}
            budget = (prefs.get("budgets") or {}).get(p.category)
            fits = f" That's now within your {p.category.replace('_', ' ')} budget." if budget and old > budget[1] >= new_price else ""
            _notify(db, h.user_id, "price_drop", f"Price drop: {p.name}",
                    f"The {p.name.lower()} that matches your saved {h.piece.name.lower()} dropped from ₹{old:,} to ₹{new_price:,}.{fits}",
                    p.id, h.id)
            notified.append(h.user_id)
    return {"product": p.name, "old_price": old, "new_price": new_price, "notified": notified}


def restock(db: Session, product_id: str, size: str, qty: int) -> dict:
    ps = db.get(m.ProductSize, (product_id, size))
    if not ps:
        raise ValueError("unknown product/size")
    was = ps.stock
    ps.stock += qty
    db.add(m.StockEvent(product_id=product_id, size=size, delta=qty, new_stock=ps.stock, kind="restock"))
    db.flush()
    p = db.get(m.Product, product_id)
    notified = []
    if was <= 0 < ps.stock:
        seen = set()
        group = size_group(p.category)
        for h, _tier in _watchers(db, p):
            prefs = prefs_dict(db.get(m.Preferences, h.user_id)) or {}
            mine = (prefs.get("sizes") or {}).get(group) if group != "free" else "Free"
            if h.user_id in seen or mine != size:
                continue
            seen.add(h.user_id)
            _notify(db, h.user_id, "restock", f"Back in your size: {p.name}",
                    f"Size {size} of the {p.name.lower()} (a match for your {h.piece.name.lower()}) is back in stock.", p.id, h.id)
            notified.append(h.user_id)
    return {"product": p.name, "size": size, "was": was, "now": ps.stock, "notified": notified}


def new_arrivals_available(db: Session) -> list[dict]:
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    names = set(db.scalars(select(m.Product.name)))
    return [dict(a, index=i) for i, a in enumerate(catalog.get("new_arrivals", [])) if a["name"] not in names]


def launch_new_arrival(db: Session, index: int) -> dict:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from make_images import product_svg  # type: ignore

    from .storage import storage
    from .vocab import size_system

    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    a = catalog["new_arrivals"][index]
    if db.scalar(select(m.Product).where(m.Product.name == a["name"])):
        raise ValueError("already launched")
    pid = f"ut-{101 + index}"
    cat = SUB_TO_CAT[a["subcategory"]]
    d = {**a, "id": pid, "store_id": "urban-thread", "brand": "Urban Thread", "category": cat,
         "color_family": color_family_of(a["primary_color"]), "mrp_inr": a["price_inr"], "image_url": f"/media/products/{pid}.svg"}
    storage().put(f"products/{pid}.svg", product_svg(d).encode(), "image/svg+xml")
    p = m.Product(id=pid, store_id="urban-thread", brand="Urban Thread", name=a["name"],
                  description=f"New in: {a['name']} in {a['fabric']}.", category=cat, subcategory=a["subcategory"],
                  gender_fit=a["gender_fit"], primary_color=a["primary_color"], secondary_color=a.get("secondary_color"),
                  color_family=d["color_family"], pattern=a["pattern"], fabric=a["fabric"], silhouette=a["silhouette"],
                  length=a["length"], neckline=a["neckline"], sleeve=a["sleeve"], occasion_tags=a["occasion_tags"],
                  style_tags=a["style_tags"], season=a["season"], price_inr=a["price_inr"], mrp_inr=a["price_inr"],
                  image_url=d["image_url"], added_at=datetime.utcnow())
    db.add(p)
    db.flush()
    for i, sz in enumerate(size_system(cat, a["gender_fit"])):
        db.add(m.ProductSize(product_id=pid, size=sz, stock=6, position=i))
        db.add(m.StockEvent(product_id=pid, size=sz, delta=6, new_stock=6, kind="initial"))
    db.add(m.PriceHistory(product_id=pid, price_inr=p.price_inr, mrp_inr=p.mrp_inr))
    db.flush()
    db.refresh(p)
    _index_vertex(p)
    # taste agent: notify only shoppers whose taste profile clears the threshold
    threshold = get_settings().matching["alerts"]["new_arrival_threshold"]
    pd = product_dict(p)
    notified, scores = [], {}
    for u in db.scalars(select(m.User)):
        prefs = prefs_dict(db.get(m.Preferences, u.id)) or {}
        if prefs.get("gender_fit") not in (None, "any", p.gender_fit) and p.gender_fit != "unisex":
            continue
        prof = profile(db, u.id)
        if not prof["saves"]:
            continue
        s = taste_score(prof, pd)
        scores[u.id] = s
        if s >= threshold:
            liked = [i["label"].lower() for i in prof["core"] if i["value"] in (pd["fabric"], pd["primary_color"], pd["subcategory"],
                                                                                 *pd["style_tags"])][:2]
            why = f" It fits your love of {' and '.join(liked)}." if liked else ""
            _notify(db, u.id, "new_arrival", f"New in: {p.name}", f"Just landed at Urban Thread for ₹{p.price_inr:,}.{why}", p.id, None)
            notified.append(u.id)
    return {"product": pd, "scores": scores, "threshold": threshold, "notified": notified}


def _index_vertex(p: m.Product) -> None:
    if get_settings().search_backend != "vertex":
        return
    try:
        from .catalog_search import VertexIndex, to_document

        VertexIndex().upsert(to_document(p))
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger("wiw.agents").warning("vertex upsert failed: %s", e)


def watched_products(db: Session) -> list[dict]:
    """Store products that at least one shopper's hangers are watching (for the admin store-events panel)."""
    n = get_settings().matching["alerts"]["watch_top_n"]
    out: dict[str, dict] = {}
    for h in db.scalars(select(m.Hanger).order_by(m.Hanger.id)):
        res = matches_for_piece(db, h.user_id, h.piece)
        picks = ([product_dict(db.get(m.Product, h.chosen_product_id))] if h.chosen_product_id else []) + \
                [i.product for i in res.for_you[:n] + res.also_view[:n]]
        for p in picks:
            e = out.setdefault(p["id"], {"product": p, "watchers": set(), "hangers": set()})
            e["watchers"].add(h.user_id)
            e["hangers"].add(h.piece.name)
    return [{"product": e["product"], "watchers": len(e["watchers"]), "hanger": sorted(e["hangers"])[0],
             "reasons": []} for e in out.values()]
