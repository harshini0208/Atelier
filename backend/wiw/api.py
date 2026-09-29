"""HTTP API. A shopper creates a profile once; the app keeps its id and sends it as X-User-Id (no passwords).
Brand-side endpoints (insights, store events, resets) require X-Admin-Token when ADMIN_TOKEN is set."""
from __future__ import annotations

import os
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .colors import color_hex
from .db import get_db
from .events import emit
from .inspo import add_manual_piece, hang_piece, ingest, select_pieces
from .services import (delivery_label, hanger_dict, inspo_dict, look_coverage, look_hangers, matches_for_piece,
                       pick_size, prefs_dict, product_dict)
from .settings import get_settings
from .vocab import (CATEGORIES, CITIES, COLORS, FABRICS, OCCASIONS, PALETTE, STYLE_TAGS, SUBCATEGORIES, label,
                    size_system)

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]
MAX_UPLOAD = 12 * 1024 * 1024


def current_user(db: Db, x_user_id: Annotated[str | None, Header()] = None) -> m.User:
    user = db.get(m.User, x_user_id) if x_user_id else None
    if not user:
        raise HTTPException(401, "Let's set up your profile first.")
    return user


User = Annotated[m.User, Depends(current_user)]


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    """Brand-side endpoints. Open locally when ADMIN_TOKEN is unset; required on Cloud Run."""
    token = os.getenv("ADMIN_TOKEN")
    if token and not (x_admin_token and secrets.compare_digest(x_admin_token, token)):
        raise HTTPException(403, "Admin token required")


Admin = Depends(require_admin)


def own_folder(db: Session, user: m.User, folder_id: int) -> m.Folder:
    f = db.get(m.Folder, folder_id)
    if not f or f.user_id != user.id:
        raise HTTPException(404, "Folder not found")
    return f


def own_hanger(db: Session, user: m.User, hanger_id: int) -> m.Hanger:
    h = db.get(m.Hanger, hanger_id)
    if not h or h.user_id != user.id:
        raise HTTPException(404, "Hanger not found")
    return h


def own_inspo(db: Session, user: m.User, inspo_id: int) -> m.InspoImage:
    i = db.get(m.InspoImage, inspo_id)
    if not i or i.user_id != user.id:
        raise HTTPException(404, "Inspo not found")
    return i


# ------------------------------------------------------------------ meta

@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {"ok": True, "gemini_mode": s.gemini_mode, "model": s.gemini_model, "db": s.db_backend,
            "storage": s.storage_backend, "events": s.events_backend, "search": s.search_backend}


@router.get("/vocab")
def vocab() -> dict:
    return {
        "categories": [{"key": c, "label": label(c), "subcategories": [{"key": s, "label": label(s)} for s in subs]}
                       for c, subs in SUBCATEGORIES.items()],
        "colors": [{"key": c, "label": label(c), "hex": color_hex(c), "family": PALETTE[c][1]} for c in COLORS],
        "fabrics": FABRICS, "occasions": OCCASIONS, "style_tags": STYLE_TAGS, "cities": CITIES,
        "sizes": {"tops": {g: size_system("tops", g) for g in ("women", "men")},
                  "bottoms": {g: size_system("bottoms", g) for g in ("women", "men")},
                  "footwear": {g: size_system("footwear", g) for g in ("women", "men")}},
    }


@router.get("/me")
def me(db: Db, user: User) -> dict:
    unread = db.scalar(select(func.count()).select_from(m.Notification).where(
        m.Notification.user_id == user.id, m.Notification.read.is_(False)))
    cart = db.scalar(select(func.coalesce(func.sum(m.CartItem.qty), 0)).where(m.CartItem.user_id == user.id))
    return {"id": user.id, "name": user.name, "city": user.city, "tagline": user.tagline, "is_guest": user.is_guest,
            "preferences": prefs_dict(db.get(m.Preferences, user.id)), "unread_notifications": unread,
            "cart_count": cart}


# ------------------------------------------------------------------ preferences

class PrefsIn(BaseModel):
    budgets: dict[str, list[int]] = Field(default_factory=dict)
    sizes: dict[str, str] = Field(default_factory=dict)
    fit: str = "regular"
    preferred_materials: list[str] = Field(default_factory=list)
    avoid_materials: list[str] = Field(default_factory=list)
    avoid_colors: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)
    gender_fit: str = "women"
    city: str | None = None


def validate_prefs(p: PrefsIn) -> None:
    for c, rng in p.budgets.items():
        if c not in CATEGORIES or len(rng) != 2 or rng[0] < 0 or rng[1] < rng[0]:
            raise HTTPException(422, f"Invalid budget for {c}")
    for f in p.preferred_materials + p.avoid_materials:
        if f not in FABRICS:
            raise HTTPException(422, f"Unknown material {f}")
    if set(p.preferred_materials) & set(p.avoid_materials):
        raise HTTPException(422, "A material can't be both preferred and avoided")
    for c in p.avoid_colors:
        if c not in COLORS:
            raise HTTPException(422, f"Unknown colour {c}")
    if p.gender_fit not in ("women", "men", "any"):
        raise HTTPException(422, "gender_fit must be women, men or any")


class ProfileIn(PrefsIn):
    name: str = Field(min_length=1, max_length=60)
    city: str = Field(default="Mumbai", max_length=40)


@router.post("/profile")
def create_profile(body: ProfileIn, db: Db) -> dict:
    """Onboarding: a new shopper tells us their name and preferences; we return their id."""
    validate_prefs(body)
    uid = f"u-{uuid.uuid4().hex[:12]}"
    db.add(m.User(id=uid, name=body.name.strip(), city=body.city, tagline=""))
    db.flush()
    db.add(m.Preferences(user_id=uid, **body.model_dump(exclude={"name", "city"})))
    db.commit()
    return {"id": uid, "name": body.name.strip()}


class MeIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    city: str = Field(max_length=40)


@router.patch("/me")
def update_me(body: MeIn, db: Db, user: User) -> dict:
    user.name, user.city = body.name.strip(), body.city
    db.commit()
    return {"id": user.id, "name": user.name, "city": user.city}


@router.delete("/me")
def delete_me(db: Db, user: User) -> dict:
    """Delete this shopper's profile and everything they created (folders, uploads' records, cart, orders, events)."""
    uid = user.id
    for model in (m.ChatMessage, m.Notification, m.CartItem, m.TasteSignal, m.Look, m.Hanger):
        db.query(model).filter(model.user_id == uid).delete(synchronize_session=False)
    for o in db.scalars(select(m.Order).where(m.Order.user_id == uid)):
        db.delete(o)
    for i in db.scalars(select(m.InspoImage).where(m.InspoImage.user_id == uid)):
        db.delete(i)
    db.query(m.Folder).filter(m.Folder.user_id == uid).delete(synchronize_session=False)
    db.query(m.Preferences).filter(m.Preferences.user_id == uid).delete(synchronize_session=False)
    db.query(m.Event).filter(m.Event.user_id == uid).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    from .storage import storage

    for prefix in (f"inspo/{uid}/", f"crops/{uid}/"):  # their uploaded screenshots and crops
        storage().delete_prefix(prefix)
    return {"ok": True}


@router.get("/preferences")
def get_prefs(db: Db, user: User) -> dict:
    return {**(prefs_dict(db.get(m.Preferences, user.id)) or {}), "city": user.city}


@router.put("/preferences")
def put_prefs(body: PrefsIn, db: Db, user: User) -> dict:
    validate_prefs(body)
    p = db.get(m.Preferences, user.id) or m.Preferences(user_id=user.id)
    for k, v in body.model_dump(exclude={"city"}).items():
        setattr(p, k, v)
    db.add(p)
    if body.city:
        user.city = body.city
    db.commit()
    return {**prefs_dict(p), "city": user.city}


# ------------------------------------------------------------------ folders

class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=300)


def folder_summary(db: Session, f: m.Folder) -> dict:
    hangers = list(db.scalars(select(m.Hanger).where(m.Hanger.folder_id == f.id).order_by(m.Hanger.id)))
    inspo = list(db.scalars(select(m.InspoImage).where(m.InspoImage.folder_id == f.id).order_by(m.InspoImage.id)))
    return {"id": f.id, "name": f.name, "description": f.description, "created_at": f.created_at.isoformat(),
            "hanger_count": len(hangers), "inspo_count": len(inspo),
            "cover_images": [h.piece.crop_url for h in hangers[:4] if h.piece.crop_url],
            "inspo_images": [i.image_url for i in inspo[:3]]}


@router.get("/folders")
def list_folders(db: Db, user: User) -> list[dict]:
    return [folder_summary(db, f) for f in db.scalars(
        select(m.Folder).where(m.Folder.user_id == user.id).order_by(m.Folder.id))]


@router.post("/folders")
def create_folder(body: FolderIn, db: Db, user: User) -> dict:
    f = m.Folder(user_id=user.id, name=body.name.strip(), description=body.description.strip())
    db.add(f)
    db.commit()
    return folder_summary(db, f)


@router.patch("/folders/{folder_id}")
def update_folder(folder_id: int, body: FolderIn, db: Db, user: User) -> dict:
    f = own_folder(db, user, folder_id)
    f.name, f.description = body.name.strip(), body.description.strip()
    db.commit()
    return folder_summary(db, f)


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Db, user: User) -> dict:
    f = own_folder(db, user, folder_id)
    # a folder's stylist conversation goes with it (otherwise it would surface in the general chat)
    db.query(m.ChatMessage).filter(m.ChatMessage.folder_id == folder_id).delete()
    db.delete(f)
    db.commit()
    return {"ok": True}


@router.get("/folders/{folder_id}")
def get_folder(folder_id: int, db: Db, user: User) -> dict:
    f = own_folder(db, user, folder_id)
    inspos = list(db.scalars(select(m.InspoImage).where(m.InspoImage.folder_id == f.id).order_by(m.InspoImage.id.desc())))
    hangers = list(db.scalars(select(m.Hanger).where(m.Hanger.folder_id == f.id).order_by(m.Hanger.id)))
    looks = []
    by_inspo: dict[int, list[m.Hanger]] = {}
    for h in hangers:
        by_inspo.setdefault(h.piece.inspo_id, []).append(h)
    for inspo_id, hs in by_inspo.items():
        inspo = db.get(m.InspoImage, inspo_id)
        looks.append({"inspo_id": inspo_id, "image_url": inspo.image_url if inspo else None,
                      "coverage": look_coverage(db, user.id, hs)})
    return {**folder_summary(db, f), "inspo": [inspo_dict(i) for i in inspos],
            "hangers": [hanger_dict(db, h) for h in hangers], "looks": looks}


# ------------------------------------------------------------------ inspo

@router.post("/inspo")
async def upload_unfiled_inspo(db: Db, user: User, file: UploadFile = File(...)) -> dict:
    """Upload from the landing page: the screenshot isn't in a folder yet. Each hung piece picks its own folder."""
    return await _upload(db, user, None, file)


@router.get("/inspo")
def list_unfiled_inspo(db: Db, user: User) -> list[dict]:
    """Uploads not filed into any folder yet (nothing hung from them)."""
    rows = db.scalars(select(m.InspoImage).where(m.InspoImage.user_id == user.id, m.InspoImage.folder_id.is_(None))
                      .order_by(m.InspoImage.id.desc()))
    return [inspo_dict(i) for i in rows]


@router.post("/folders/{folder_id}/inspo")
async def upload_inspo(folder_id: int, db: Db, user: User, file: UploadFile = File(...)) -> dict:
    own_folder(db, user, folder_id)
    return await _upload(db, user, folder_id, file)


async def _upload(db: Session, user: m.User, folder_id: int | None, file: UploadFile) -> dict:
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "That image is over 12 MB. Try a smaller screenshot.")
    try:
        inspo = ingest(db, user.id, folder_id, data)
    except Exception as e:  # noqa: BLE001  (unreadable / not an image)
        if "cannot identify image" in str(e).lower():
            raise HTTPException(415, "We couldn't open that file. Upload a PNG, JPG or WebP screenshot.") from e
        raise
    db.commit()
    return inspo_dict(inspo)


@router.get("/inspo/{inspo_id}")
def get_inspo(inspo_id: int, db: Db, user: User) -> dict:
    return inspo_dict(own_inspo(db, user, inspo_id))


@router.delete("/inspo/{inspo_id}")
def delete_inspo(inspo_id: int, db: Db, user: User) -> dict:
    inspo = own_inspo(db, user, inspo_id)
    for h in db.scalars(select(m.Hanger).join(m.DetectedPiece).where(m.DetectedPiece.inspo_id == inspo.id)):
        db.delete(h)
    db.delete(inspo)
    db.commit()
    return {"ok": True}


class ManualPieceIn(BaseModel):
    subcategory: str
    color: str
    name: str | None = None
    fabric: str = "cotton"
    pattern: str = "solid"
    point: list[int] | None = None  # [y, x] on 0..1000 where the shopper tapped


@router.post("/inspo/{inspo_id}/pieces")
def manual_piece(inspo_id: int, body: ManualPieceIn, db: Db, user: User) -> dict:
    inspo = own_inspo(db, user, inspo_id)
    if body.subcategory not in {s for subs in SUBCATEGORIES.values() for s in subs} or body.color not in COLORS:
        raise HTTPException(422, "Pick a piece type and colour from the list")
    box = None
    if body.point:
        y, x = body.point
        box = [max(0, y - 120), max(0, x - 120), min(1000, y + 120), min(1000, x + 120)]
    add_manual_piece(db, inspo, subcategory=body.subcategory, color=body.color, name=body.name, box=box,
                     fabric=body.fabric if body.fabric in FABRICS else "cotton", pattern=body.pattern)
    db.commit()
    db.refresh(inspo)
    return inspo_dict(inspo)


class SelectIn(BaseModel):
    piece_ids: list[int]
    folder_id: int | None = None
    folder_by_piece: dict[int, int] = Field(default_factory=dict)


@router.post("/inspo/{inspo_id}/select")
def select_inspo_pieces(inspo_id: int, body: SelectIn, db: Db, user: User) -> dict:
    inspo = own_inspo(db, user, inspo_id)
    for fid in {body.folder_id, *body.folder_by_piece.values()} - {None}:
        own_folder(db, user, fid)
    if inspo.folder_id is None and body.folder_id is None and body.piece_ids:
        raise HTTPException(422, "Choose a folder first.")
    out = select_pieces(db, user.id, inspo, body.piece_ids, body.folder_by_piece, body.folder_id)
    db.commit()
    return out


def own_piece(inspo: m.InspoImage, piece_id: int) -> m.DetectedPiece:
    piece = next((p for p in inspo.pieces if p.id == piece_id), None)
    if not piece:
        raise HTTPException(404, "Piece not found")
    return piece


@router.get("/inspo/{inspo_id}/pieces/{piece_id}/matches")
def piece_matches(inspo_id: int, piece_id: int, db: Db, user: User) -> dict:
    """Shown the moment a shopper taps a piece they like: what this store actually has for it."""
    inspo = own_inspo(db, user, inspo_id)
    piece = own_piece(inspo, piece_id)
    res = matches_for_piece(db, user.id, piece)
    for item in (res.for_you or res.also_view)[:1]:
        emit(db, "match_viewed", user.id, product_id=item.product["id"], subcategory=piece.subcategory)
    db.commit()
    hanger = db.scalar(select(m.Hanger).where(m.Hanger.user_id == user.id, m.Hanger.piece_id == piece.id))
    out = res.as_dict()
    out["piece"] = {"id": piece.id, "name": piece.name, "crop_url": piece.crop_url, "subcategory": piece.subcategory,
                    "subcategory_label": label(piece.subcategory), "color": piece.color, "fabric": piece.fabric}
    out["hanger"] = {"id": hanger.id, "chosen_product_id": hanger.chosen_product_id} if hanger else None
    if not res.covered:
        out["gap_message"] = (f"Urban Thread doesn't stock a close match for the {piece.name.lower()} right now. "
                              "Here's the closest from this store, or save it as a wish.")
    return out


class HangIn(BaseModel):
    product_id: str | None = None   # None = save as a wish (nothing close in store)
    size: str | None = None
    folder_id: int | None = None


@router.post("/inspo/{inspo_id}/pieces/{piece_id}/hang")
def hang(inspo_id: int, piece_id: int, body: HangIn, db: Db, user: User) -> dict:
    inspo = own_inspo(db, user, inspo_id)
    piece = own_piece(inspo, piece_id)
    if body.folder_id:
        own_folder(db, user, body.folder_id)
    elif inspo.folder_id is None and not db.scalar(select(m.Hanger).where(m.Hanger.piece_id == piece.id)):
        raise HTTPException(422, "Choose a folder for this piece first.")
    try:
        h = hang_piece(db, user.id, inspo, piece, product_id=body.product_id, size=body.size, folder_id=body.folder_id)
    except ValueError as e:
        raise HTTPException(404, "Product not found") from e
    db.commit()
    return hanger_dict(db, h, with_top=False)


@router.delete("/inspo/{inspo_id}/pieces/{piece_id}/hang")
def unhang(inspo_id: int, piece_id: int, db: Db, user: User) -> dict:
    """Un-like a piece: take it off its hanger."""
    inspo = own_inspo(db, user, inspo_id)
    piece = own_piece(inspo, piece_id)
    for h in db.scalars(select(m.Hanger).where(m.Hanger.user_id == user.id, m.Hanger.piece_id == piece.id)):
        db.delete(h)
    piece.selected = None
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ hangers + matches

@router.get("/hangers/{hanger_id}/matches")
def hanger_matches(hanger_id: int, db: Db, user: User) -> dict:
    h = own_hanger(db, user, hanger_id)
    res = matches_for_piece(db, user.id, h.piece)
    for item in (res.for_you or res.also_view)[:1]:
        emit(db, "match_viewed", user.id, product_id=item.product["id"], subcategory=h.piece.subcategory)
    cov = look_coverage(db, user.id, look_hangers(db, h))
    db.commit()
    out = res.as_dict()
    out["hanger"] = hanger_dict(db, h, with_top=False)
    out["coverage"] = cov
    if not res.covered:
        out["gap_message"] = (f"Urban Thread doesn't stock a close match for the {h.piece.name.lower()} right now. "
                              "Here's the closest from this store.")
    return out


class MoveIn(BaseModel):
    folder_id: int


@router.patch("/hangers/{hanger_id}")
def move_hanger(hanger_id: int, body: MoveIn, db: Db, user: User) -> dict:
    h = own_hanger(db, user, hanger_id)
    own_folder(db, user, body.folder_id)
    h.folder_id = body.folder_id
    db.commit()
    return hanger_dict(db, h)


@router.delete("/hangers/{hanger_id}")
def delete_hanger(hanger_id: int, db: Db, user: User) -> dict:
    db.delete(own_hanger(db, user, hanger_id))
    db.commit()
    return {"ok": True}


class ChooseIn(BaseModel):
    product_id: str
    size: str | None = None


@router.post("/hangers/{hanger_id}/choose")
def choose_product(hanger_id: int, body: ChooseIn, db: Db, user: User) -> dict:
    """'Add to look': pin a catalog product to this hanger (it is what the mannequin and cart use)."""
    h = own_hanger(db, user, hanger_id)
    p = db.get(m.Product, body.product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    h.chosen_product_id = p.id
    h.chosen_size = body.size or pick_size(prefs_dict(db.get(m.Preferences, user.id)), p)
    emit(db, "add_to_look", user.id, product_id=p.id, subcategory=p.subcategory, value_inr=p.price_inr)
    db.commit()
    return hanger_dict(db, h)


# ------------------------------------------------------------------ products

@router.get("/products/{product_id}")
def get_product(product_id: str, db: Db, user: User) -> dict:
    p = db.get(m.Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    prefs = prefs_dict(db.get(m.Preferences, user.id))
    history = [{"price_inr": h.price_inr, "at": h.changed_at.isoformat()} for h in db.scalars(
        select(m.PriceHistory).where(m.PriceHistory.product_id == p.id).order_by(m.PriceHistory.changed_at))]
    return {**product_dict(p, user.city), "delivery": delivery_label(user.city), "price_history": history,
            "suggested_size": pick_size(prefs, p)}


@router.get("/products")
def list_products(db: Db, user: User, category: str | None = None, subcategory: str | None = None,
                  limit: int = 60) -> list[dict]:
    q = select(m.Product).where(m.Product.active.is_(True))
    if category:
        q = q.where(m.Product.category == category)
    if subcategory:
        q = q.where(m.Product.subcategory == subcategory)
    return [product_dict(p) for p in db.scalars(q.order_by(m.Product.id).limit(min(limit, 200)))]
