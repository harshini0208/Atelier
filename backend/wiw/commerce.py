"""Cart and mock checkout. Every number here comes from the database; nothing from the model."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .events import emit
from .services import delivery_days, pick_size, prefs_dict, product_dict


class CartError(ValueError):
    def __init__(self, message: str, items: list[dict] | None = None) -> None:
        super().__init__(message)
        self.items = items or []


def _stock(p: m.Product, size: str) -> int | None:
    return next((s.stock for s in p.sizes if s.size == size), None)


def add_item(db: Session, user_id: str, product_id: str, size: str | None, qty: int = 1,
             folder_id: int | None = None) -> m.CartItem:
    p = db.get(m.Product, product_id)
    if not p or not p.active:
        raise CartError("That product isn't available.")
    if not size:
        raise CartError(f"Pick a size for the {p.name}.")
    stock = _stock(p, size)
    if stock is None:
        raise CartError(f"The {p.name} doesn't come in size {size}.")
    item = db.scalar(select(m.CartItem).where(m.CartItem.user_id == user_id, m.CartItem.product_id == product_id,
                                              m.CartItem.size == size))
    want = (item.qty if item else 0) + max(1, qty)
    if stock < want:
        raise CartError(f"Only {stock} left of the {p.name} in {size}." if stock else f"Size {size} of the {p.name} is sold out.")
    if item:
        item.qty = want
    else:
        item = m.CartItem(user_id=user_id, product_id=product_id, size=size, qty=want, folder_id=folder_id)
        db.add(item)
    emit(db, "add_to_cart", user_id, product_id=p.id, subcategory=p.subcategory, value_inr=p.price_inr * max(1, qty))
    db.flush()
    return item


def add_look(db: Session, user_id: str, folder_id: int, items: list[dict]) -> dict:
    """Add a whole look. items: [{product_id, size?}]. Auto-picks the shopper's size when it's in stock;
    otherwise returns the item under `needs_size` so the UI can ask."""
    prefs = prefs_dict(db.get(m.Preferences, user_id))
    added, needs_size, failed = [], [], []
    for it in items:
        p = db.get(m.Product, it["product_id"])
        if not p:
            continue
        size = it.get("size") or pick_size(prefs, p)
        if not size:
            needs_size.append({"product": product_dict(p), "reason": "Your size isn't set or is sold out. Pick one."})
            continue
        try:
            add_item(db, user_id, p.id, size, 1, folder_id)
            added.append({"product_id": p.id, "size": size})
        except CartError as e:
            failed.append({"product": product_dict(p), "reason": str(e)})
    return {"added": added, "needs_size": needs_size, "failed": failed}


def cart_view(db: Session, user: m.User) -> dict:
    items = list(db.scalars(select(m.CartItem).where(m.CartItem.user_id == user.id).order_by(m.CartItem.added_at)))
    groups: dict[str, dict] = {}
    for it in items:
        p = it.product
        stock = _stock(p, it.size) or 0
        g = groups.setdefault(p.brand, {"brand": p.brand, "store_id": p.store_id, "items": [], "subtotal_inr": 0,
                                        "delivery_days": delivery_days(user.city)})
        line = p.price_inr * it.qty
        g["items"].append({"id": it.id, "product": product_dict(p), "size": it.size, "qty": it.qty, "line_total_inr": line,
                           "in_stock": stock >= it.qty, "stock": stock})
        g["subtotal_inr"] += line
    subtotal = sum(g["subtotal_inr"] for g in groups.values())
    mrp = sum(it.product.mrp_inr * it.qty for it in items)
    shipping = 0 if subtotal >= 1999 or subtotal == 0 else 99
    return {"groups": list(groups.values()), "count": sum(i.qty for i in items), "subtotal_inr": subtotal,
            "savings_inr": max(0, mrp - subtotal), "shipping_inr": shipping, "total_inr": subtotal + shipping,
            "city": user.city, "delivery_days": delivery_days(user.city)}


def checkout(db: Session, user: m.User) -> m.Order:
    """Mock checkout: re-checks stock, decrements it, writes stock events and a purchase event. No payment."""
    items = list(db.scalars(select(m.CartItem).where(m.CartItem.user_id == user.id)))
    if not items:
        raise CartError("Your cart is empty.")
    short = []
    for it in items:
        ps = db.get(m.ProductSize, (it.product_id, it.size))
        if ps is None or ps.stock < it.qty:
            short.append({"product_id": it.product_id, "name": it.product.name, "size": it.size,
                          "available": ps.stock if ps else 0})
    if short:
        raise CartError("Some items sold out while they were in your cart.", short)
    view = cart_view(db, user)
    order = m.Order(user_id=user.id, total_inr=view["total_inr"], status="placed", city=user.city,
                    delivery_days=delivery_days(user.city))
    for it in items:
        ps = db.get(m.ProductSize, (it.product_id, it.size))
        ps.stock -= it.qty
        db.add(m.StockEvent(product_id=it.product_id, size=it.size, delta=-it.qty, new_stock=ps.stock, kind="sale"))
        order.items.append(m.OrderItem(product_id=it.product_id, size=it.size, qty=it.qty, price_inr=it.product.price_inr))
        emit(db, "purchase", user.id, product_id=it.product_id, subcategory=it.product.subcategory,
             value_inr=it.product.price_inr * it.qty)
        db.delete(it)
    db.add(order)
    db.flush()
    db.add(m.Notification(user_id=user.id, kind="order", title=f"Order #{order.id} placed",
                          body=f"{len(order.items)} item(s), ₹{order.total_inr:,}. Arriving in about {order.delivery_days} days "
                               f"(demo order, no payment taken)."))
    return order
