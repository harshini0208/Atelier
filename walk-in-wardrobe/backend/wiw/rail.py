"""The rail: one generic hanger with everything a shopper already has a relationship with in this store.

Bought online (orders), bought in store (membership-linked receipts), in the bag, and wishlisted. From the rail a piece
can be hung in any number of folders, styled on a canvas, and the stylist styles it when no folder is open.

Rail pieces reuse the folder machinery: hanging a product in a folder creates a hanger whose "piece" is described from
the product itself (filed under a hidden per-shopper "wardrobe" inspo, never listed as an upload).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .catalog_search import allowed_genders
from .services import pick_size, prefs_dict, product_dict

WARDROBE = "wardrobe"   # InspoImage.status of the hidden per-shopper source of rail pieces
KIND_LABEL = {"online": "Bought online", "in_store": "Bought in store", "cart": "In your bag", "wishlist": "Wishlist"}
STORES = {"Bengaluru": "Phoenix Marketcity, Bengaluru", "Mumbai": "Palladium, Lower Parel", "Delhi": "Select Citywalk, Saket",
          "Hyderabad": "Inorbit Mall, Hyderabad", "Chennai": "Express Avenue, Chennai", "Pune": "Phoenix Palladium, Pune",
          "Kolkata": "Quest Mall, Kolkata", "Ahmedabad": "Alpha One, Ahmedabad"}


def _date(d: datetime) -> str:
    return f"{d.day} {d:%b %Y}"


def rail(db: Session, user: m.User) -> dict:
    entries: dict[str, dict] = {}

    def add(p: m.Product, kind: str, at: datetime, detail: str = "", size: str | None = None) -> None:
        e = entries.setdefault(p.id, {"product": product_dict(p, user.city), "sources": [], "latest": at})
        e["sources"].append({"kind": kind, "label": KIND_LABEL[kind], "detail": detail, "size": size, "at": at.isoformat()})
        e["latest"] = max(e["latest"], at)

    for o in db.scalars(select(m.Order).where(m.Order.user_id == user.id)):
        for it in o.items:
            add(db.get(m.Product, it.product_id), "online", o.created_at, _date(o.created_at), it.size)
    for sp in db.scalars(select(m.StorePurchase).where(m.StorePurchase.user_id == user.id)):
        add(db.get(m.Product, sp.product_id), "in_store", sp.purchased_at,
            f"{sp.store_label.split(',')[0]} · {_date(sp.purchased_at)}", sp.size)
    for c in db.scalars(select(m.CartItem).where(m.CartItem.user_id == user.id)):
        add(c.product, "cart", c.added_at, "", c.size)
    for w in db.scalars(select(m.WishlistItem).where(m.WishlistItem.user_id == user.id)):
        add(db.get(m.Product, w.product_id), "wishlist", w.added_at)

    folders: dict[str, set[int]] = {}
    if entries:
        for h in db.scalars(select(m.Hanger).where(m.Hanger.user_id == user.id, m.Hanger.chosen_product_id.in_(list(entries)))):
            folders.setdefault(h.chosen_product_id, set()).add(h.folder_id)
    items = sorted(entries.values(), key=lambda e: e["latest"], reverse=True)
    for e in items:
        e["owned"] = any(s["kind"] in ("online", "in_store") for s in e["sources"])
        e["folder_ids"] = sorted(folders.get(e["product"]["id"], set()))
        e.pop("latest")
    counts = {k: sum(any(s["kind"] == k for s in e["sources"]) for e in items) for k in KIND_LABEL}
    counts["bought"] = counts["online"] + counts["in_store"]
    linked = db.scalar(select(m.StorePurchase.id).where(m.StorePurchase.user_id == user.id).limit(1)) is not None
    return {"items": items, "counts": counts, "member_linked": linked}


# ------------------------------------------------------------------ rail pieces in folders

def wardrobe_inspo(db: Session, user_id: str) -> m.InspoImage:
    i = db.scalar(select(m.InspoImage).where(m.InspoImage.user_id == user_id, m.InspoImage.status == WARDROBE))
    if not i:
        i = m.InspoImage(user_id=user_id, folder_id=None, image_url="", sha256=WARDROBE, width=0, height=0,
                         status=WARDROBE, message="Pieces hung from the shopper's rail", source="rail")
        db.add(i)
        db.flush()
    return i


def product_piece(p: m.Product, inspo_id: int | None = None, idx: int = 0) -> m.DetectedPiece:
    """A piece described from a store product, so matching, styling and the stylist treat it like any hanger."""
    return m.DetectedPiece(inspo_id=inspo_id, idx=idx, category=p.category, subcategory=p.subcategory, name=p.name,
                           gender_fit=p.gender_fit, color=p.primary_color, secondary_color=p.secondary_color,
                           pattern=p.pattern, fabric=p.fabric, silhouette=p.silhouette, length=p.length,
                           neckline=p.neckline, sleeve=p.sleeve, style_tags=list(p.style_tags), occasion_tags=list(p.occasion_tags),
                           box=None, confidence=1.0, crop_url=p.image_url, selected=True, manual=True)


def is_rail_piece(piece: m.DetectedPiece) -> bool:
    return bool(piece.manual and piece.inspo and piece.inspo.status == WARDROBE)


def set_folders(db: Session, user: m.User, product: m.Product, folder_ids: list[int], size: str | None = None) -> list[int]:
    """Hang this product in exactly these folders (adds hangers where missing, removes it from the others)."""
    mine = {f.id for f in db.scalars(select(m.Folder).where(m.Folder.user_id == user.id))}
    wanted = set(folder_ids) & mine
    current: dict[int, list[m.Hanger]] = {}
    for h in db.scalars(select(m.Hanger).where(m.Hanger.user_id == user.id, m.Hanger.chosen_product_id == product.id)):
        current.setdefault(h.folder_id, []).append(h)
    for fid, hs in current.items():
        if fid not in wanted:
            for h in hs:
                db.delete(h)
    inspo = None
    for fid in sorted(wanted - set(current)):
        inspo = inspo or wardrobe_inspo(db, user.id)
        n = len(inspo.pieces)
        piece = product_piece(product, inspo.id, n)
        db.add(piece)
        db.flush()
        db.add(m.Hanger(user_id=user.id, folder_id=fid, piece_id=piece.id, chosen_product_id=product.id, chosen_size=size))
    db.flush()
    return sorted(wanted)


def owned_ids(db: Session, user: m.User) -> frozenset[str]:
    """Products this shopper has bought, online or in store."""
    online = db.scalars(select(m.OrderItem.product_id).join(m.Order).where(m.Order.user_id == user.id))
    offline = db.scalars(select(m.StorePurchase.product_id).where(m.StorePurchase.user_id == user.id))
    return frozenset(online) | frozenset(offline)


def rail_hangers(db: Session, user: m.User) -> list[m.Hanger]:
    """Unsaved, in-memory hangers for every rail product (for styling and the stylist when no folder is open)."""
    out = []
    for e in rail(db, user)["items"]:
        p = db.get(m.Product, e["product"]["id"])
        size = next((s["size"] for s in e["sources"] if s.get("size")), None)
        out.append(m.Hanger(id=None, user_id=user.id, folder_id=None, chosen_product_id=p.id, chosen_size=size,
                            piece=product_piece(p)))
    return out


# ------------------------------------------------------------------ membership (demo)

PLAN = [("online", 96, ["tops", "bottoms"]), ("in_store", 71, ["one_piece", "accessories"]),
        ("online", 42, ["footwear"]), ("in_store", 19, ["outerwear", "tops"])]


def link_membership(db: Session, user: m.User) -> dict:
    """Demo: bring in this shopper's Urban Thread purchase history (online orders and in-store receipts).

    A real store would look these up by membership number; here a small, plausible history is picked from the
    catalog in the shopper's section, sizes and budgets. It never changes stock (these are past purchases)."""
    if db.scalar(select(m.StorePurchase.id).where(m.StorePurchase.user_id == user.id).limit(1)) is not None:
        return {"linked": True, "added": 0}
    prefs = prefs_dict(db.get(m.Preferences, user.id)) or {}
    genders = allowed_genders(prefs.get("gender_fit", "any"))
    budgets = prefs.get("budgets") or {}
    rng = random.Random(f"membership-{user.id}")
    pool: dict[str, list[m.Product]] = {}
    for p in db.scalars(select(m.Product).where(m.Product.active.is_(True), m.Product.gender_fit.in_(genders))
                        .order_by(m.Product.id)):
        pool.setdefault(p.category, []).append(p)
    now = m.now()
    store = STORES.get(user.city, f"Urban Thread, {user.city}")
    used: set[str] = set()
    added = 0
    for k, (channel, days_ago, cats) in enumerate(PLAN):
        when = now - timedelta(days=days_ago, hours=rng.randint(0, 8))
        picks = []
        for cat in cats:
            lo, hi = (budgets.get(cat) or [0, 10**6])[:2]
            cands = [p for p in pool.get(cat, []) if p.id not in used]
            fits = [p for p in cands if lo <= p.price_inr <= hi and pick_size(prefs, p)] or cands
            if fits:
                p = rng.choice(fits)
                used.add(p.id)
                picks.append((p, pick_size(prefs, p) or next((s.size for s in p.sizes if s.stock > 0), p.sizes[0].size)))
        if not picks:
            continue
        if channel == "online":
            order = m.Order(user_id=user.id, total_inr=sum(p.price_inr for p, _ in picks), status="delivered",
                            city=user.city, delivery_days=3, created_at=when)
            for p, size in picks:
                order.items.append(m.OrderItem(product_id=p.id, size=size, qty=1, price_inr=p.price_inr))
            db.add(order)
        else:
            receipt = f"UT{rng.randint(100000, 999999)}"
            for p, size in picks:
                db.add(m.StorePurchase(user_id=user.id, product_id=p.id, size=size, price_inr=p.price_inr,
                                       store_label=store, receipt=receipt, purchased_at=when))
        added += len(picks)
    db.flush()
    return {"linked": True, "added": added}
