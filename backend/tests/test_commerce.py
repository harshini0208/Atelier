"""Cart, full-look add, and mock checkout: all numbers come from the database."""
import pytest
from sqlalchemy import select

from wiw import models as m
from wiw.commerce import CartError, add_item, add_look, cart_view, checkout
from wiw.db import session_scope


@pytest.fixture(scope="module", autouse=True)
def seeded():
    from wiw.seed import seed_all
    seed_all(images=False, with_history=False)


def pid(db, name):
    return db.scalar(select(m.Product.id).where(m.Product.name == name))


def stock(db, product_id, size):
    return db.get(m.ProductSize, (product_id, size)).stock


def test_add_item_validates_size_and_stock():
    with session_scope() as db:
        shirt = pid(db, "Ecru linen boyfriend shirt")
        with pytest.raises(CartError, match="sold out"):
            add_item(db, "aanya", shirt, "M")
        with pytest.raises(CartError, match="doesn't come in size"):
            add_item(db, "aanya", shirt, "XXL")
        with pytest.raises(CartError, match="Pick a size"):
            add_item(db, "aanya", shirt, None)
        db.rollback()


def test_quantity_cannot_exceed_stock():
    with session_scope() as db:
        watch = pid(db, "Gold-tone slim watch")
        available = stock(db, watch, "Free")
        for _ in range(available):
            add_item(db, "rohan", watch, "Free")
        with pytest.raises(CartError, match="Only"):
            add_item(db, "rohan", watch, "Free")
        db.rollback()


def test_add_look_autoselects_size_or_asks():
    with session_scope() as db:
        items = [{"product_id": pid(db, "Ivory linen relaxed shirt")},        # M in stock -> auto
                 {"product_id": pid(db, "Ecru linen boyfriend shirt")},       # M sold out -> ask
                 {"product_id": pid(db, "Tan canvas tote")}]                  # one size -> Free
        out = add_look(db, "aanya", None, items)
        assert {a["size"] for a in out["added"]} == {"M", "Free"}
        assert [n["product"]["name"] for n in out["needs_size"]] == ["Ecru linen boyfriend shirt"]
        db.rollback()


def test_cart_groups_by_brand_with_db_totals():
    with session_scope() as db:
        user = db.get(m.User, "zoya")
        a, b = pid(db, "Tan strappy flat sandals"), pid(db, "Tortoise cat-eye sunglasses")
        add_item(db, "zoya", a, "4")
        add_item(db, "zoya", b, "Free")
        v = cart_view(db, user)
        prices = {p.id: p.price_inr for p in db.scalars(select(m.Product).where(m.Product.id.in_([a, b])))}
        assert [g["brand"] for g in v["groups"]] == ["Urban Thread"]
        assert v["subtotal_inr"] == sum(prices.values())
        assert v["total_inr"] == v["subtotal_inr"] + v["shipping_inr"]
        db.rollback()


def test_checkout_decrements_stock_and_writes_events():
    with session_scope() as db:
        user = db.get(m.User, "kabir")
        hoodie = pid(db, "Black oversized hoodie")
        before = stock(db, hoodie, "L")
        add_item(db, "kabir", hoodie, "L", qty=2)
        order = checkout(db, user)
        assert stock(db, hoodie, "L") == before - 2
        assert order.total_inr == sum(i.price_inr * i.qty for i in order.items) + (0 if order.total_inr >= 1999 else 99)
        assert db.scalar(select(m.CartItem).where(m.CartItem.user_id == "kabir")) is None
        ev = db.scalars(select(m.StockEvent).where(m.StockEvent.product_id == hoodie, m.StockEvent.kind == "sale")).all()
        assert ev and ev[-1].delta == -2
        assert db.scalar(select(m.Event).where(m.Event.event_type == "purchase", m.Event.user_id == "kabir"))


def test_checkout_rechecks_stock():
    with session_scope() as db:
        user = db.get(m.User, "meera")
        tote = pid(db, "Tan canvas tote")
        add_item(db, "meera", tote, "Free")
        db.get(m.ProductSize, (tote, "Free")).stock = 0  # sold out while in the cart
        with pytest.raises(CartError) as e:
            checkout(db, user)
        assert e.value.items[0]["available"] == 0
        db.rollback()


def test_empty_cart_cannot_checkout():
    with session_scope() as db:
        with pytest.raises(CartError, match="empty"):
            checkout(db, db.get(m.User, "rohan"))
