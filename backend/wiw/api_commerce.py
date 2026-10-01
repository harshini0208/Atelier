"""Cart, mock checkout, orders and notifications."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from . import models as m
from .api import Db, User, own_folder
from .commerce import CartError, add_item, add_look, cart_view, checkout
from .services import product_dict

router = APIRouter(prefix="/api")


class CartIn(BaseModel):
    product_id: str
    size: str | None = None
    qty: int = Field(default=1, ge=1, le=10)
    folder_id: int | None = None


def _err(e: CartError, status: int = 409) -> HTTPException:
    return HTTPException(status, {"message": str(e), "items": e.items} if e.items else str(e))


@router.get("/cart")
def get_cart(db: Db, user: User) -> dict:
    return cart_view(db, user)


@router.post("/cart")
def post_cart(body: CartIn, db: Db, user: User) -> dict:
    try:
        add_item(db, user.id, body.product_id, body.size, body.qty, body.folder_id)
    except CartError as e:
        raise _err(e) from e
    db.commit()
    return cart_view(db, user)


class CartPatch(BaseModel):
    qty: int = Field(ge=0, le=10)


@router.patch("/cart/{item_id}")
def patch_cart(item_id: int, body: CartPatch, db: Db, user: User) -> dict:
    it = db.get(m.CartItem, item_id)
    if not it or it.user_id != user.id:
        raise HTTPException(404, "Cart item not found")
    if body.qty == 0:
        db.delete(it)
    else:
        stock = next((s.stock for s in it.product.sizes if s.size == it.size), 0)
        if body.qty > stock:
            raise HTTPException(409, f"Only {stock} left in {it.size}.")
        it.qty = body.qty
    db.commit()
    return cart_view(db, user)


class LookIn(BaseModel):
    items: list[dict] = Field(default_factory=list)  # [{product_id, size?}]; empty = use the folder's look


@router.post("/cart/look/{folder_id}")
def add_full_look(folder_id: int, body: LookIn, db: Db, user: User) -> dict:
    own_folder(db, user, folder_id)
    items = body.items
    if not items:
        hangers = db.scalars(select(m.Hanger).where(m.Hanger.folder_id == folder_id, m.Hanger.chosen_product_id.is_not(None)))
        items = [{"product_id": h.chosen_product_id, "size": h.chosen_size} for h in hangers]
    if not items:
        raise HTTPException(400, "This look has no pieces yet. Add matches to your look first.")
    out = add_look(db, user.id, folder_id, items)
    db.commit()
    return {**out, "cart": cart_view(db, user)}


@router.post("/checkout")
def post_checkout(db: Db, user: User) -> dict:
    try:
        order = checkout(db, user)
    except CartError as e:
        db.rollback()
        raise _err(e) from e
    db.commit()
    return order_dict(order)


def order_dict(o: m.Order) -> dict:
    return {"id": o.id, "total_inr": o.total_inr, "status": o.status, "city": o.city, "delivery_days": o.delivery_days,
            "created_at": o.created_at.isoformat(),
            "items": [{"product_id": i.product_id, "size": i.size, "qty": i.qty, "price_inr": i.price_inr} for i in o.items]}


@router.get("/orders")
def orders(db: Db, user: User) -> list[dict]:
    out = []
    for o in db.scalars(select(m.Order).where(m.Order.user_id == user.id).order_by(m.Order.created_at.desc())):
        d = order_dict(o)
        for it in d["items"]:
            it["product"] = product_dict(db.get(m.Product, it["product_id"]))
        out.append(d)
    return out


@router.get("/notifications")
def notifications(db: Db, user: User) -> list[dict]:
    rows = db.scalars(select(m.Notification).where(m.Notification.user_id == user.id)
                      .order_by(m.Notification.created_at.desc(), m.Notification.id.desc()).limit(50))
    out = []
    for n in rows:
        d = {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "read": n.read,
             "created_at": n.created_at.isoformat(), "hanger_id": n.hanger_id, "product": None}
        if n.product_id:
            d["product"] = product_dict(db.get(m.Product, n.product_id))
        out.append(d)
    return out


@router.post("/notifications/read")
def mark_read(db: Db, user: User) -> dict:
    db.execute(update(m.Notification).where(m.Notification.user_id == user.id).values(read=True))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ shop (the customer storefront)

SORTS = {"recommended", "new", "price_asc", "price_desc", "discount"}


@router.get("/shop")
def shop(db: Db, gender: str = "women", category: str | None = None, subcategory: str | None = None,
         sort: str = "recommended", q: str | None = None) -> dict:
    """Browse the whole catalog like a store website: a women's/men's section, categories, sort and search.
    Unisex pieces appear in both sections."""
    from .vocab import CATEGORIES, SUBCATEGORIES, label

    genders = {"women": ("women", "unisex"), "men": ("men", "unisex")}.get(gender, ("women", "men", "unisex"))
    rows = [product_dict(p) for p in db.scalars(select(m.Product).where(m.Product.active.is_(True),
                                                                        m.Product.gender_fit.in_(genders)))]
    if q:
        terms = q.lower().split()
        rows = [p for p in rows if all(t in f"{p['name']} {p['subcategory_label']} {p['fabric']} {p['primary_color']}".lower()
                                       for t in terms)]
    cat_counts = {c: sum(p["category"] == c for p in rows) for c in CATEGORIES}
    if category in CATEGORIES:
        rows = [p for p in rows if p["category"] == category]
    sub_counts = {s: sum(p["subcategory"] == s for p in rows) for s in SUBCATEGORIES.get(category or "", [])}
    if subcategory:
        rows = [p for p in rows if p["subcategory"] == subcategory]
    key = {"new": lambda p: (p["added_at"],), "price_asc": lambda p: (p["price_inr"],),
           "price_desc": lambda p: (-p["price_inr"],),
           "discount": lambda p: (-(p["mrp_inr"] - p["price_inr"]) / p["mrp_inr"],)}.get(sort if sort in SORTS else "")
    if sort == "new":
        rows.sort(key=lambda p: p["added_at"], reverse=True)
    elif key:
        rows.sort(key=key)
    else:  # recommended: in stock first, then category order, then name
        rows.sort(key=lambda p: (not p["in_stock"], CATEGORIES.index(p["category"]), p["name"]))
    newest = sorted((p["added_at"] for p in rows), reverse=True)[:8]
    for p in rows:
        p["is_new"] = p["added_at"] in newest
    return {"gender": gender, "category": category, "subcategory": subcategory, "count": len(rows), "products": rows,
            "categories": [{"key": c, "label": label(c), "count": n} for c, n in cat_counts.items() if n],
            "subcategories": [{"key": s, "label": label(s), "count": n} for s, n in sub_counts.items() if n]}
