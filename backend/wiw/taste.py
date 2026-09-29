"""Taste profile from saves (positive) and skips (mild negative). Deterministic counts; Gemini only writes a sentence."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gemini
from . import models as m
from .colors import color_similarity
from .settings import get_settings
from .vocab import label

FIELDS = ["subcategory", "color", "fabric", "pattern", "style_tags", "occasion_tags"]
WEIGHTS = {"subcategory": 25, "color": 20, "fabric": 15, "style_tags": 25, "occasion_tags": 10, "pattern": 5}


def _values(attrs: dict, f: str) -> list[str]:
    v = attrs.get(f)
    return list(v) if isinstance(v, list) else [v] if v else []


def profile(db: Session, user_id: str, now: datetime | None = None) -> dict:
    cfg = get_settings().matching["taste"]
    now = now or datetime.utcnow()
    signals = list(db.scalars(select(m.TasteSignal).where(m.TasteSignal.user_id == user_id).order_by(m.TasteSignal.created_at)))
    pos: dict[str, Counter] = defaultdict(Counter)
    neg: dict[str, Counter] = defaultdict(Counter)
    first_seen: dict[tuple[str, str], datetime] = {}
    for s in signals:
        for f in FIELDS:
            for v in _values(s.attributes, f):
                if s.weight > 0:
                    pos[f][v] += 1
                    first_seen.setdefault((f, v), s.created_at)
                else:
                    neg[f][v] += 1
    cutoff = now - timedelta(days=cfg["exploring_days"])
    core, exploring = [], []
    for f, counter in pos.items():
        for v, n in counter.most_common():
            item = {"field": f, "value": v, "label": label(v), "count": n}
            if n >= cfg["core_min_count"]:
                core.append(item)
            elif first_seen[(f, v)] >= cutoff:
                exploring.append(item)
    core.sort(key=lambda i: -i["count"])
    exploring.sort(key=lambda i: -i["count"])
    return {"saves": sum(1 for s in signals if s.weight > 0), "skips": sum(1 for s in signals if s.weight <= 0),
            "core": core[:10], "exploring": exploring[:8],
            "counts": {f: dict(pos[f].most_common(6)) for f in FIELDS},
            "skipped": {f: dict(neg[f].most_common(3)) for f in FIELDS if neg[f]}}


def taste_score(prof: dict, product: dict) -> float:
    """0..100: how well a product fits the saved-taste counts (used for new-arrival alerts)."""
    counts = prof["counts"]
    total, got = 0.0, 0.0
    for f, w in WEIGHTS.items():
        c = counts.get(f) or {}
        if not c:
            continue
        top = max(c.values())
        total += w
        key = {"color": "primary_color"}.get(f, f)
        vals = product.get(key)
        vals = vals if isinstance(vals, list) else [vals]
        if f == "color":
            best = max((color_similarity(v, col, 45) * n / top for col, n in c.items() for v in vals), default=0)
        else:
            best = max((c.get(v, 0) / top for v in vals), default=0)
        got += w * min(1.0, best)
    return round(100 * got / total, 1) if total else 0.0


class TasteSentence(BaseModel):
    sentence: str = Field(max_length=240)


def taste_sentence(prof: dict) -> tuple[str, str]:
    core = [i["label"].lower() for i in prof["core"][:4]]
    expl = [i["label"].lower() for i in prof["exploring"][:3]]

    def fallback() -> TasteSentence:
        if not core and not expl:
            return TasteSentence(sentence="Save a few pieces from your inspo and we'll learn your taste.")
        s = f"You keep coming back to {', '.join(core)}" if core else "Your taste is still taking shape"
        if expl:
            s += f", and lately you're exploring {', '.join(expl)}"
        return TasteSentence(sentence=s + ".")

    if not core and not expl:
        return fallback().sentence, "fallback"
    prompt = ("Write ONE warm sentence (max 30 words) summarising a shopper's fashion taste for them, using only these "
              f"facts. Core taste (saved repeatedly): {core}. Recently exploring: {expl}. No prices, no body comments.")
    res = gemini.generate_json("taste", version="taste-v1", parts=[prompt], schema=TasteSentence, fallback=fallback)
    return res.value.sentence, res.source
