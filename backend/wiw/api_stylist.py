"""Stylist chat endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import models as m
from .api import Db, User, own_folder
from .stylist import chat, greeting, message_dict
from .styling import folder_hangers

router = APIRouter(prefix="/api")


@router.get("/chat")
def history(db: Db, user: User, folder_id: int | None = None) -> list[dict]:
    folder = own_folder(db, user, folder_id) if folder_id else None
    rows = list(db.scalars(select(m.ChatMessage).where(m.ChatMessage.user_id == user.id, m.ChatMessage.folder_id == folder_id)
                           .order_by(m.ChatMessage.id)))
    if folder:
        n = len(folder_hangers(db, user.id, folder.id))
    else:
        from .rail import rail

        n = len(rail(db, user)["items"])
    return [greeting(user, folder, n)] + [message_dict(c) for c in rows]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=800)
    folder_id: int | None = None


@router.post("/chat")
def send(body: ChatIn, db: Db, user: User) -> dict:
    folder = own_folder(db, user, body.folder_id) if body.folder_id else None
    reply = chat(db, user, folder, body.message.strip())
    db.commit()
    return reply


class ConfirmIn(BaseModel):
    accept: bool


@router.post("/chat/{message_id}/confirm")
def confirm(message_id: int, body: ConfirmIn, db: Db, user: User) -> dict:
    msg = db.get(m.ChatMessage, message_id)
    if not msg or msg.user_id != user.id or not (msg.payload or {}).get("pending_preferences"):
        raise HTTPException(404, "Nothing to confirm")
    payload = dict(msg.payload)
    pending = payload["pending_preferences"]
    if body.accept:
        prefs = db.get(m.Preferences, user.id)
        for k, v in pending["preferences"].items():
            if hasattr(prefs, k):
                setattr(prefs, k, v)
        payload["actions"] = [*payload.get("actions", []), f"Saved: {pending['summary']}"]
    else:
        payload["actions"] = [*payload.get("actions", []), "Kept your preferences as they were"]
    payload["pending_preferences"] = None
    msg.payload = payload
    db.commit()
    return message_dict(msg)
