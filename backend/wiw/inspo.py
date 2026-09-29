"""Inspo pipeline: upload -> detect -> crop -> pieces; selection -> hangers + taste signals + events."""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from . import models as m
from .detection import LOW_CONFIDENCE, crop, detect, normalize_upload
from .events import emit, piece_fields
from .services import look_coverage, matches_for_piece, user_prefs
from .settings import get_settings
from .storage import storage
from .vocab import SUB_TO_CAT, label

MESSAGES = {
    "no_outfit": "We couldn't spot any clothing in this image. Try a screenshot where the outfit is clearly visible, "
                 "or tap on the image to add a piece yourself.",
    "blurry": "This image is a little too blurry or small for us to read the outfit. Try a sharper screenshot, "
              "or tap on the image to add a piece yourself.",
    "low_confidence": "Some pieces were hard to make out, so they're marked as a best guess. You can uncheck them "
                      "or tap on the image to add a piece we missed.",
    "several_people": "There are a few people in this image, so we focused on the most prominent outfit.",
    "empty": "We couldn't read this outfit automatically. Tap on the image where a piece is and tell us what it is.",
}


def ingest(db: Session, user_id: str, folder_id: int | None, data: bytes) -> m.InspoImage:
    data, w, h, mime = normalize_upload(data)
    sha = hashlib.sha256(data).hexdigest()
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
    st = storage()
    url = st.put(f"inspo/{user_id}/{sha[:16]}.{ext}", data, mime)
    result = detect(data, mime)
    det = result.value
    inspo = m.InspoImage(user_id=user_id, folder_id=folder_id, image_url=url, sha256=sha, width=w, height=h,
                         source=result.source)
    notes = []
    if det.image_quality != "ok" and not det.pieces:
        inspo.status, notes = det.image_quality, [MESSAGES[det.image_quality]]
    elif not det.pieces:
        inspo.status, notes = "no_apparel", [MESSAGES["empty"] if result.source == "fallback" else MESSAGES["no_outfit"]]
    else:
        inspo.status = "analyzed"
        if det.people_count > 1:
            notes.append(MESSAGES["several_people"])
        if any(p.confidence < LOW_CONFIDENCE for p in det.pieces):
            notes.append(MESSAGES["low_confidence"])
    inspo.message = " ".join(notes)
    db.add(inspo)
    db.flush()
    for i, p in enumerate(det.pieces):
        crop_url = st.put(f"crops/{user_id}/{sha[:16]}-{i}.png", crop(data, p.box_2d), "image/png")
        piece = m.DetectedPiece(
            inspo_id=inspo.id, idx=i, category=SUB_TO_CAT[p.subcategory], subcategory=p.subcategory, name=p.name,
            gender_fit=p.gender_fit, color=p.color, secondary_color=p.secondary_color, pattern=p.pattern,
            fabric=p.fabric, silhouette=p.silhouette, length=p.length, neckline=p.neckline, sleeve=p.sleeve,
            style_tags=list(p.style_tags), occasion_tags=list(p.occasion_tags), box=p.box_2d,
            confidence=p.confidence, crop_url=crop_url)
        db.add(piece)
        emit(db, "piece_detected", user_id, **piece_fields(piece))
    db.flush()
    db.refresh(inspo)
    return inspo


def add_manual_piece(db: Session, inspo: m.InspoImage, *, subcategory: str, color: str, name: str | None = None,
                     box: list[int] | None = None, fabric: str = "cotton", pattern: str = "solid") -> m.DetectedPiece:
    """Tap-to-add: the shopper tells us what a piece is (and optionally where)."""
    data = storage().get(inspo.image_url.removeprefix("/media/"))
    if box is None:
        box = [0, 0, 1000, 1000]
    crop_url = None
    if data:
        crop_url = storage().put(f"crops/{inspo.user_id}/{inspo.sha256[:16]}-m{len(inspo.pieces)}.png", crop(data, box))
    piece = m.DetectedPiece(
        inspo_id=inspo.id, idx=len(inspo.pieces), category=SUB_TO_CAT[subcategory], subcategory=subcategory,
        name=name or f"{label(color)} {label(subcategory).lower()}", color=color, pattern=pattern, fabric=fabric,
        silhouette="regular", style_tags=[], occasion_tags=[], box=box, confidence=1.0, crop_url=crop_url, manual=True)
    db.add(piece)
    if inspo.status != "analyzed":
        inspo.status, inspo.message = "analyzed", ""
    db.flush()
    emit(db, "piece_detected", inspo.user_id, **piece_fields(piece))
    return piece


def select_pieces(db: Session, user_id: str, inspo: m.InspoImage, selected_ids: list[int],
                  folder_by_piece: dict[int, int] | None = None, default_folder_id: int | None = None) -> dict:
    """Selected pieces become hangers (positive taste); unselected ones are mild negative signals."""
    cfg = get_settings().matching["taste"]
    prefs = user_prefs(db, user_id)
    folder_by_piece = folder_by_piece or {}
    created: list[m.Hanger] = []
    existing = {h.piece_id for h in db.query(m.Hanger).filter(m.Hanger.user_id == user_id)}
    for p in inspo.pieces:
        chosen = p.id in selected_ids
        if p.selected is not None and p.selected == chosen and (not chosen or p.id in existing):
            continue  # already recorded
        p.selected = chosen
        attrs = {"subcategory": p.subcategory, "color": p.color, "fabric": p.fabric, "pattern": p.pattern,
                 "silhouette": p.silhouette, "style_tags": p.style_tags, "occasion_tags": p.occasion_tags}
        db.add(m.TasteSignal(user_id=user_id, piece_id=p.id, weight=1.0 if chosen else cfg["skip_weight"],
                             attributes=attrs))
        if not chosen:
            emit(db, "piece_skipped", user_id, **piece_fields(p))
            continue
        folder_id = folder_by_piece.get(p.id) or default_folder_id or inspo.folder_id
        if p.id not in existing:
            h = m.Hanger(user_id=user_id, folder_id=folder_id, piece_id=p.id)
            db.add(h)
            created.append(h)
        res = matches_for_piece(db, user_id, p, prefs)
        emit(db, "piece_selected", user_id, matched=int(res.covered), **piece_fields(p))
        if not res.covered:
            emit(db, "hanger_no_match", user_id, **piece_fields(p))
    db.flush()
    hangers = [h for h in db.query(m.Hanger).join(m.DetectedPiece).filter(
        m.Hanger.user_id == user_id, m.DetectedPiece.inspo_id == inspo.id)]
    cov = look_coverage(db, user_id, hangers, prefs)
    if created:
        emit(db, "coverage_computed", user_id, covered=cov["covered"], covered_in_prefs=cov["covered_in_prefs"],
             total=cov["total"])
    return {"created": [h.id for h in created], "coverage": cov}
