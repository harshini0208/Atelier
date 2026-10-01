"""The shopper's mannequin (body type x finish) and dressing it in a look from the style board."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import models as m
from .api import Db, User
from .tryon import TryOnError, dress, mannequin_of, mannequin_path
from .vocab import BODY_TYPES, SKIN_TONES

router = APIRouter(prefix="/api")


@router.get("/mannequins/{body}-{tone}.png")
def mannequin_image(body: str, tone: str) -> Response:
    try:
        path = mannequin_path(body, tone)
    except ValueError as e:
        raise HTTPException(404, "Unknown mannequin") from e
    return Response(path.read_bytes(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/mannequin")
def get_mannequin(db: Db, user: User) -> dict:
    return {**mannequin_of(db, user.id), "body_types": BODY_TYPES, "skin_tones": SKIN_TONES}


class MannequinIn(BaseModel):
    body_type: str
    skin_tone: str


@router.put("/mannequin")
def put_mannequin(body: MannequinIn, db: Db, user: User) -> dict:
    if body.body_type not in BODY_TYPES or body.skin_tone not in SKIN_TONES:
        raise HTTPException(422, "Pick a body type and a finish from the list")
    mq = db.get(m.Mannequin, user.id) or m.Mannequin(user_id=user.id)
    mq.body_type, mq.skin_tone = body.body_type, body.skin_tone
    db.add(mq)
    db.commit()
    return mannequin_of(db, user.id)


class DressIn(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=8)   # layer order: inside first
    cached_only: bool = False


@router.post("/tryon")
def tryon(body: DressIn, db: Db, user: User) -> dict:
    try:
        return dress(db, user, body.product_ids, cached_only=body.cached_only)
    except TryOnError as e:
        raise HTTPException(422, str(e)) from e
