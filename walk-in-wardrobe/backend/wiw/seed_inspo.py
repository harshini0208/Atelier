"""Attach pre-analysed demo inspo to persona folders by running the real pipeline (never live Gemini)."""
from __future__ import annotations

from datetime import datetime, timedelta

from .db import session_scope
from .inspo import ingest, select_pieces
from .services import matches_for_piece, pick_size, user_prefs
from .settings import ROOT, get_settings
from . import models as m


def attach_persona_inspo(personas: dict, folders: dict[str, list[int]]) -> None:
    s = get_settings()
    mode = s.gemini_mode
    if mode == "live":
        s.gemini_mode = "replay"  # seeding must be deterministic and offline
    try:
        for pr in personas["personas"]:
            for folder_id, f in zip(folders[pr["id"]], pr["folders"]):
                for name in f["inspo"]:
                    data = (ROOT / "demo/inspo/generated" / f"{name}.png").read_bytes()
                    with session_scope() as db:
                        inspo = ingest(db, pr["id"], folder_id, data)
                        select_pieces(db, pr["id"], inspo, [p.id for p in inspo.pieces], default_folder_id=folder_id)
                        prefs = user_prefs(db, pr["id"])
                        for h in db.query(m.Hanger).filter(m.Hanger.folder_id == folder_id):
                            res = matches_for_piece(db, pr["id"], h.piece, prefs)
                            top = (res.for_you or res.also_view or [None])[0]
                            if top:
                                h.chosen_product_id = top.product["id"]
                                h.chosen_size = pick_size(prefs, top.product)
                        # persona history happened weeks ago, so today's saves read as "exploring"
                        old = datetime.utcnow() - timedelta(days=30)
                        for sig in db.query(m.TasteSignal).filter(m.TasteSignal.user_id == pr["id"]):
                            sig.created_at = old
    finally:
        s.gemini_mode = mode
