"""The rail (everything bought online or in store, in the bag, or wishlisted), wishlist and membership linking."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import models as m
from .api import Db, User
from .rail import link_membership, rail, set_folders

router = APIRouter(prefix="/api")


@router.get("/rail")
def get_rail(db: Db, user: User) -> dict:
    return rail(db, user)


class FoldersIn(BaseModel):
    folder_ids: list[int] = Field(default_factory=list, max_length=50)
    size: str | None = Field(default=None, max_length=10)


@router.put("/rail/{product_id}/folders")
def put_folders(product_id: str, body: FoldersIn, db: Db, user: User) -> dict:
    """Hang a piece in any number of folders at once (and take it out of the ones not listed)."""
    p = db.get(m.Product, product_id)
    if not p:
        raise HTTPException(404, "Unknown product")
    folder_ids = set_folders(db, user, p, body.folder_ids, body.size)
    db.commit()
    return {"product_id": p.id, "folder_ids": folder_ids}


@router.post("/membership/link")
def link(db: Db, user: User) -> dict:
    out = link_membership(db, user)
    db.commit()
    return {**out, "rail": rail(db, user)}


@router.get("/wishlist")
def wishlist(db: Db, user: User) -> list[str]:
    return list(db.scalars(select(m.WishlistItem.product_id).where(m.WishlistItem.user_id == user.id)
                           .order_by(m.WishlistItem.added_at.desc())))


class WishIn(BaseModel):
    product_id: str


@router.post("/wishlist")
def add_wish(body: WishIn, db: Db, user: User) -> dict:
    if not db.get(m.Product, body.product_id):
        raise HTTPException(404, "Unknown product")
    if not db.get(m.WishlistItem, (user.id, body.product_id)):
        db.add(m.WishlistItem(user_id=user.id, product_id=body.product_id))
        db.commit()
    return {"ok": True}


@router.delete("/wishlist/{product_id}")
def remove_wish(product_id: str, db: Db, user: User) -> dict:
    w = db.get(m.WishlistItem, (user.id, product_id))
    if w:
        db.delete(w)
        db.commit()
    return {"ok": True}


class RailCartIn(BaseModel):
    items: list[dict] = Field(min_length=1, max_length=20)   # [{product_id, size?}]


@router.post("/rail/cart")
def rail_look_to_cart(body: RailCartIn, db: Db, user: User) -> dict:
    """'Add the look to cart' from the rail's board (pieces the shopper already owns are skipped by the UI)."""
    from .commerce import add_look, cart_view

    out = add_look(db, user.id, None, body.items)
    db.commit()
    return {**out, "cart": cart_view(db, user)}
