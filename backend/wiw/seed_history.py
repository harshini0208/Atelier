"""Synthetic shopper history for the retailer view (clearly flagged synthetic=True).

Anonymous shoppers save popular "trend looks". Whether each saved piece had a good match is computed by the real
matcher against the real catalog, so the gap report reflects genuine catalog gaps rather than invented numbers.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from . import models as m
from .db import session_scope
from .events import emit
from .services import matcher, product_dict

SEED = 7
N_SHOPPERS = 240
NOW = datetime(2026, 9, 28, 18, 0)


def P(sub, color, fabric="cotton", pattern="solid", sil="regular", styles=(), occ=()):  # noqa: N802
    return {"subcategory": sub, "color": color, "fabric": fabric, "pattern": pattern, "silhouette": sil,
            "style_tags": list(styles), "occasion_tags": list(occ), "secondary_color": None}


TREND_LOOKS = [  # (weight, gender, pieces)
    (34, "women", [P("linen_shirt", "ivory", "linen", sil="relaxed", styles=("old_money", "minimal"), occ=("brunch",)),
                   P("chinos", "beige", sil="straight", styles=("old_money", "classic"), occ=("work",)),
                   P("loafers", "tan", "leather", sil="none", styles=("old_money",), occ=("work",)),
                   P("tote", "tan", "canvas", sil="none", styles=("minimal",), occ=("vacation",))]),
    (46, "women", [P("shirt", "sky_blue", pattern="stripes", sil="relaxed", styles=("resort", "preppy"), occ=("vacation",)),
                   P("wide_leg_trousers", "sand", "linen", sil="wide", styles=("resort", "old_money"), occ=("vacation", "beach")),
                   P("sandals", "tan", "leather", sil="none", styles=("resort",), occ=("beach",)),
                   P("sunglasses", "brown", "synthetic", "print", sil="none", styles=("resort",), occ=("beach",))]),
    (22, "women", [P("crop_top", "white", "linen", sil="relaxed", styles=("resort", "minimal"), occ=("vacation",)),
                   P("wide_leg_trousers", "white", "linen", sil="wide", styles=("resort", "minimal"), occ=("vacation",)),
                   P("kolhapuris", "tan", "leather", sil="none", styles=("ethnic", "boho"), occ=("casual",))]),
    (24, "women", [P("lehenga", "maroon", "silk", "embroidered", sil="flared", styles=("ethnic",), occ=("wedding",)),
                   P("dupatta", "gold", "silk", "embroidered", sil="none", styles=("ethnic",), occ=("wedding",)),
                   P("juttis", "gold", "synthetic", "embroidered", sil="none", styles=("ethnic",), occ=("wedding",)),
                   P("jewellery", "gold", "metal", "embroidered", sil="none", styles=("ethnic",), occ=("wedding",))]),
    (26, "unisex", [P("hoodie", "black", sil="oversized", styles=("streetwear",), occ=("casual",)),
                    P("cargo_pants", "olive", sil="relaxed", styles=("streetwear",), occ=("casual",)),
                    P("sneakers", "white", "leather", sil="none", styles=("streetwear", "athleisure"), occ=("casual",)),
                    P("sling_bag", "black", "polyester", sil="none", styles=("streetwear",), occ=("travel",))]),
    (14, "women", [P("dress", "black", "polyester", sil="bodycon", styles=("minimal", "edgy"), occ=("party",)),
                   P("stilettos", "black", "leather", sil="none", styles=("formal",), occ=("party",)),
                   P("clutch", "black", "synthetic", sil="none", styles=("minimal",), occ=("party",))]),
    (12, "women", [P("shrug", "cream", "knit", sil="relaxed", styles=("romantic",), occ=("brunch",)),
                   P("dress", "blush", "viscose", "floral", sil="a_line", styles=("romantic", "boho"), occ=("brunch",)),
                   P("flats", "beige", "leather", sil="none", styles=("classic",), occ=("brunch",))]),
    (10, "women", [P("blazer", "camel", "wool", sil="regular", styles=("old_money", "formal"), occ=("work",)),
                   P("wide_leg_trousers", "cream", "wool", sil="wide", styles=("old_money", "formal"), occ=("work",)),
                   P("block_heels", "beige", "leather", sil="none", styles=("classic",), occ=("work",))]),
]


def seed_synthetic_history() -> dict:
    rng = random.Random(SEED)
    mt = matcher()
    with session_scope() as db:
        catalog = [product_dict(p) for p in db.scalars(select(m.Product))]
        by_cat: dict[str, list[dict]] = {}
        for p in catalog:
            by_cat.setdefault(p["category"], []).append(p)

        def best(piece: dict, gender: str):  # noqa: ANN202
            from .vocab import SUB_TO_CAT

            cands = [p for p in by_cat[SUB_TO_CAT[piece["subcategory"]]]
                     if gender == "unisex" or p["gender_fit"] in (gender, "unisex")]
            res = mt.rank(piece, cands, None)
            return res, (res.for_you or res.also_view or [None])[0]

        memo = {}
        weights = [w for w, _, _ in TREND_LOOKS]
        n = 0
        for i in range(N_SHOPPERS):
            uid = f"anon-{i:03d}"
            for _ in range(rng.choice([1, 1, 2, 2, 3])):
                li = rng.choices(range(len(TREND_LOOKS)), weights=weights)[0]
                _, gender, pieces = TREND_LOOKS[li]
                ts = NOW - timedelta(days=rng.uniform(0, 60))
                covered = total = 0
                for j, piece in enumerate(pieces):
                    key = (li, j)
                    if key not in memo:
                        memo[key] = best(piece, gender)
                    res, top = memo[key]
                    f = {k: piece[k] for k in ("subcategory", "color", "fabric", "pattern")} | {"style_tags": piece["style_tags"]}
                    emit(db, "piece_detected", uid, ts=ts, synthetic=True, **f)
                    if rng.random() > 0.85:
                        emit(db, "piece_skipped", uid, ts=ts, synthetic=True, **f)
                        continue
                    total += 1
                    covered += res.covered
                    emit(db, "piece_selected", uid, ts=ts, synthetic=True, matched=int(res.covered), **f)
                    n += 1
                    if not res.covered:
                        emit(db, "hanger_no_match", uid, ts=ts, synthetic=True, **f)
                        continue
                    if rng.random() < 0.7:
                        emit(db, "match_viewed", uid, ts=ts, synthetic=True, product_id=top.product["id"],
                             subcategory=piece["subcategory"])
                        if rng.random() < 0.45:
                            emit(db, "add_to_look", uid, ts=ts, synthetic=True, product_id=top.product["id"],
                                 subcategory=piece["subcategory"], value_inr=top.product["price_inr"])
                            if rng.random() < 0.5:
                                emit(db, "add_to_cart", uid, ts=ts, synthetic=True, product_id=top.product["id"],
                                     subcategory=piece["subcategory"], value_inr=top.product["price_inr"])
                                if rng.random() < 0.55:
                                    emit(db, "purchase", uid, ts=ts + timedelta(hours=2), synthetic=True,
                                         product_id=top.product["id"], subcategory=piece["subcategory"],
                                         value_inr=top.product["price_inr"])
                if total:
                    emit(db, "coverage_computed", uid, ts=ts, synthetic=True, covered=covered,
                         covered_in_prefs=covered, total=total)
    return {"synthetic_saves": n}
