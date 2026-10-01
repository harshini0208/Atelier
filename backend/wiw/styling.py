"""Deterministic outfit building from a folder's hangers (used by the stylist and "Style it for me").

Scores and prices come from the matcher and the database. Gemini only phrases the one-line reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .services import matcher, matches_for_piece, user_prefs
from .settings import get_settings
from .vocab import SUB_TO_CAT, label, slot_for

SLOT_ORDER = ["full", "torso", "legs", "outer", "feet", "hand", "neck", "head", "waist", "wrist"]


@dataclass
class Choice:
    hanger_index: int
    hanger_id: int | None
    piece_name: str
    slot: str
    options: list[dict]            # [{product, score, reasons, tier}] best first
    pick: int = 0

    @property
    def current(self) -> dict:
        return self.options[self.pick]


@dataclass
class Outfit:
    items: list[dict] = field(default_factory=list)
    total_inr: int = 0
    max_total_inr: int | None = None
    occasion: str | None = None
    gaps: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)  # optional accessories left out to meet the budget
    owned_count: int = 0                               # pieces the shopper already owns (not in total_inr)

    @property
    def within_budget(self) -> bool:
        return self.max_total_inr is None or self.total_inr <= self.max_total_inr

    def as_dict(self) -> dict:
        return {"items": self.items, "total_inr": self.total_inr, "max_total_inr": self.max_total_inr,
                "within_budget": self.within_budget,
                "over_by_inr": 0 if self.within_budget else self.total_inr - (self.max_total_inr or 0),
                "occasion": self.occasion, "gaps": self.gaps, "dropped": self.dropped, "owned_count": self.owned_count}


def folder_hangers(db: Session, user_id: str, folder_id: int) -> list[m.Hanger]:
    return list(db.scalars(select(m.Hanger).where(m.Hanger.user_id == user_id, m.Hanger.folder_id == folder_id)
                           .order_by(m.Hanger.id)))


def _occasion_set(occasion: str | None) -> set[str]:
    if not occasion:
        return set()
    rel = get_settings().matching["stylist"]["related_occasions"]
    out: set[str] = set()
    for word in occasion.replace(",", " ").split():
        out |= set(rel.get(word, [word] if word in rel else []))
    return out


def _why(product: dict, occasion: str | None, reasons: list[dict]) -> str:
    fabric = product["fabric"]
    what = label(product["subcategory"]).lower()
    base = {"linen": "Breathable linen", "cotton": "Easy cotton", "silk": "Silk that dresses it up",
            "leather": "Leather that lasts", "denim": "Classic denim", "wool": "Tailored wool"}.get(fabric, fabric.capitalize())
    s = f"{base} {what}" + (f", right for {occasion}" if occasion else "")
    if reasons:
        s += f" (note: {reasons[0]['label'].lower()})"
    return s


@dataclass
class Brief:
    """What a request implies beyond the occasion: the weather and a style direction."""
    season: str | None = None          # winter | summer
    styles: set[str] = field(default_factory=set)

    def bonus(self, p: dict) -> float:
        sc = 0.0
        if self.season == "winter":
            if p["season"] == "summer" or p.get("sleeve") == "sleeveless" or p["subcategory"] in COLD_WRONG:
                sc -= 25
            if p["season"] == "winter" or p["fabric"] == "wool" or p["category"] == "outerwear":
                sc += 10
        elif self.season == "summer":
            if p["season"] == "winter" or p["fabric"] == "wool" or p["subcategory"] in ("coat", "boots"):
                sc -= 20
            if p["fabric"] in ("linen", "cotton"):
                sc += 5
        if self.styles & set(p["style_tags"]):
            sc += 14
        return sc


COLD_WRONG = {"crop_top", "shorts", "sandals", "kolhapuris", "flats"}


def parse_brief(*texts: str | None) -> Brief:
    words = " ".join(t for t in texts if t).lower().replace("_", " ")
    cfg = get_settings().matching["stylist"].get("brief", {})
    hit = lambda key: any(w in words for w in cfg.get(key, []))  # noqa: E731
    season = "winter" if hit("winter") or "winter" in words.split() else "summer" if hit("summer") else None
    styles = {"ethnic"} if hit("ethnic") else set()
    styles |= {w for w in ("formal", "streetwear", "minimal", "boho", "old_money", "classic", "edgy", "romantic", "resort")
               if w.replace("_", " ") in words}
    return Brief(season, styles)


OPTIONAL_SLOTS = {"hand", "head", "neck", "waist", "wrist", "outer"}
UNBUYABLE = {"size", "stock"}  # an outfit never includes something the shopper can't buy in their size


def build_choices(db: Session, user_id: str, folder_id: int | None, occasion: str | None = None,
                  formality: str | None = None, prefs_override: dict | None = None,
                  hangers: list[m.Hanger] | None = None,
                  owned: frozenset[str] = frozenset(), brief: str | None = None,
                  complete: bool = False) -> tuple[list[Choice], list[str]]:
    """One Choice per body slot. Candidates for a slot are pooled from every hanger in that slot, so a folder with
    loafers AND sandals lets the occasion and budget decide between them."""
    prefs = user_prefs(db, user_id)
    if prefs_override:
        prefs = {**(prefs or {}), **prefs_override}
    occ = _occasion_set(occasion)
    br = parse_brief(occasion, brief, formality and formality.replace("more_", ""))
    shift = set(get_settings().matching["stylist"]["formality_shift"].get(formality or "", []))
    if hangers is None:   # a folder's hangers; the rail passes its own in-memory hangers
        hangers = folder_hangers(db, user_id, folder_id)
    has_top_bottom = any(slot_for(h.piece.subcategory) in ("torso", "legs") for h in hangers)
    by_slot: dict[str, list[tuple[int, m.Hanger]]] = {}
    for idx, h in enumerate(hangers, start=1):
        slot = slot_for(h.piece.subcategory)
        if slot == "full" and has_top_bottom and formality != "more_festive":
            continue
        by_slot.setdefault(slot, []).append((idx, h))
    choices: list[Choice] = []
    gaps: list[str] = []
    for slot, members in by_slot.items():
        pooled: dict[str, dict] = {}
        for idx, h in members:
            res = matches_for_piece(db, user_id, h.piece, prefs)
            if not res.covered:
                gaps.append(h.piece.name)
            for tier, items in (("for_you", res.for_you), ("also_view", res.also_view)):
                for it in items:
                    if {r.code for r in it.reasons} & UNBUYABLE:
                        continue
                    p = it.product
                    sc = it.display_score + (10 if tier == "for_you" else 0)
                    if occ:
                        sc += 12 if occ & set(p["occasion_tags"]) else -8
                    if shift:
                        sc += 8 if shift & set(p["style_tags"]) else 0
                    if h.chosen_product_id == p["id"]:
                        sc += 5
                    if p["id"] in owned:      # styling the rail: lean on what they already own
                        sc += 15
                    sc += br.bonus(p)
                    opt = {"product": p, "score": round(sc, 1), "style_score": round(it.score, 1), "hanger_index": idx,
                           "hanger_id": h.id, "piece_name": h.piece.name, "reasons": [r.as_dict() for r in it.reasons],
                           "tier": tier}
                    if p["id"] not in pooled or pooled[p["id"]]["score"] < opt["score"]:
                        pooled[p["id"]] = opt
        ranked = sorted(pooled.values(), key=lambda r: (-r["score"], r["product"]["price_inr"]))
        if not ranked:
            continue
        if slot in OPTIONAL_SLOTS:  # accessories can be dropped to hit a budget, at a cost
            ranked.append({"product": None, "score": ranked[0]["score"] - 30, "style_score": 0, "hanger_index": members[0][0],
                           "hanger_id": members[0][1].id, "piece_name": members[0][1].piece.name, "reasons": [], "tier": "skip"})
        first = ranked[0]
        choices.append(Choice(first["hanger_index"], first["hanger_id"], first["piece_name"], slot, ranked))
    if complete and choices and get_settings().matching["stylist"].get("complete_slots", True):
        choices += _complete(db, prefs, {c.slot for c in choices}, occ, br, shift,
                             [c.current["product"] for c in choices if c.current["product"]])
    choices.sort(key=lambda c: SLOT_ORDER.index(c.slot) if c.slot in SLOT_ORDER else 99)
    return choices, gaps


def _complete(db: Session, prefs: dict | None, have: set[str], occ: set[str], br: Brief, shift: set[str],
              anchors: list[dict]) -> list[Choice]:
    """Fill the slots a look can't do without (top + bottom or a one-piece, shoes, and a coat in winter) from the
    catalog: in the shopper's size, section and materials, suited to the occasion and the brief."""
    from sqlalchemy.orm import selectinload

    from .catalog_search import allowed_genders
    from .services import pick_size, product_dict

    need = [] if "full" in have else [s for s in ("torso", "legs") if s not in have]
    need += [s for s in ("feet",) if s not in have]
    if br.season == "winter" and "outer" not in have:
        need.append("outer")
    if not need:
        return []
    prefs = prefs or {}
    avoid_f, avoid_c = set(prefs.get("avoid_materials") or []), set(prefs.get("avoid_colors") or [])
    budgets = prefs.get("budgets") or {}
    anchor_styles = {t for a in anchors for t in a["style_tags"]}
    rows = db.scalars(select(m.Product).options(selectinload(m.Product.sizes))
                      .where(m.Product.active.is_(True), m.Product.gender_fit.in_(allowed_genders(prefs.get("gender_fit", "any")))))
    pools: dict[str, list[dict]] = {s: [] for s in need}
    for p in rows:
        slot = slot_for(p.subcategory)
        if slot not in pools or p.fabric in avoid_f or p.primary_color in avoid_c or not pick_size(prefs, p):
            continue
        d = product_dict(p)
        sc = 50 + br.bonus(d) + 3 * len(anchor_styles & set(d["style_tags"]))
        if occ:
            sc += 12 if occ & set(d["occasion_tags"]) else -8
        if shift:
            sc += 8 if shift & set(d["style_tags"]) else 0
        lo, hi = (budgets.get(SUB_TO_CAT[p.subcategory]) or [0, 10**6])[:2]
        sc -= 0 if lo <= d["price_inr"] <= hi else 10
        pools[slot].append({"product": d, "score": round(sc, 1), "style_score": round(sc, 1), "hanger_index": 0,
                            "hanger_id": None, "piece_name": "To complete the look", "reasons": [], "tier": "suggested"})
    out = []
    for slot, opts in pools.items():
        ranked = sorted(opts, key=lambda o: (-o["score"], o["product"]["price_inr"]))[:6]
        if ranked:
            out.append(Choice(0, None, "To complete the look", slot, ranked))
    return out


def _fit_budget(choices: list[Choice], max_total: int | None, owned: frozenset[str] = frozenset()) -> None:
    """Swap to cheaper options with the smallest score loss per rupee saved until within budget (owned pieces are free)."""
    if max_total is None:
        return
    price = lambda o: o["product"]["price_inr"] if o["product"] and o["product"]["id"] not in owned else 0  # noqa: E731
    total = lambda: sum(price(c.current) for c in choices)  # noqa: E731
    while total() > max_total:
        best = None
        for c in choices:
            cur = c.current
            for j, opt in enumerate(c.options):
                saving = price(cur) - price(opt)
                if saving <= 0:
                    continue
                cost = (cur["score"] - opt["score"]) / saving
                if best is None or cost < best[0]:
                    best = (cost, c, j)
        if best is None:
            break
        best[1].pick = best[2]


def outfit_from(choices: list[Choice], gaps: list[str], occasion: str | None, max_total: int | None,
                owned: frozenset[str] = frozenset()) -> Outfit:
    items, dropped = [], []
    for c in choices:
        cur = c.current
        if cur["product"] is None:
            dropped.append(c.options[0]["product"]["name"])
            continue
        items.append({"hanger_index": cur["hanger_index"], "hanger_id": cur["hanger_id"], "piece_name": cur["piece_name"],
                      "slot": c.slot, "product": cur["product"], "score": cur["style_score"], "tier": cur["tier"],
                      "reasons": cur["reasons"], "why": _why(cur["product"], occasion, cur["reasons"]),
                      "owned": cur["product"]["id"] in owned})
    o = Outfit(items=items, total_inr=sum(i["product"]["price_inr"] for i in items if not i["owned"]), max_total_inr=max_total,
               occasion=occasion, gaps=gaps, owned_count=sum(i["owned"] for i in items))
    o.dropped = dropped
    return o


def suggest_outfit(db: Session, user_id: str, folder_id: int | None, occasion: str | None = None,
                   max_total_inr: int | None = None, formality: str | None = None,
                   hangers: list[m.Hanger] | None = None, owned: frozenset[str] = frozenset(),
                   brief: str | None = None, complete: bool = True) -> Outfit:
    choices, gaps = build_choices(db, user_id, folder_id, occasion, formality, hangers=hangers, owned=owned,
                                  brief=brief, complete=complete)
    _fit_budget(choices, max_total_inr, owned)
    return outfit_from(choices, gaps, occasion, max_total_inr, owned)


def style_options(db: Session, user_id: str, folder_id: int | None, n: int = 3, occasion: str | None = None,
                  formality: str | None = None, hangers: list[m.Hanger] | None = None,
                  owned: frozenset[str] = frozenset(), brief: str | None = None,
                  complete: bool = True) -> list[Outfit]:
    """Up to n distinct combinations: the best look, then variants that swap the closest runner-up."""
    choices, gaps = build_choices(db, user_id, folder_id, occasion, formality, hangers=hangers, owned=owned,
                                  brief=brief, complete=complete)
    if not choices:
        return []
    outfits = [outfit_from(choices, gaps, occasion, None, owned)]
    seen = {tuple(i["product"]["id"] for i in outfits[0].items)}
    swaps = sorted(((c.options[0]["score"] - c.options[1]["score"], k) for k, c in enumerate(choices)
                    if len(c.options) > 1 and c.options[1]["product"] is not None))
    for _, k in swaps:
        if len(outfits) >= n:
            break
        choices[k].pick = 1
        o = outfit_from(choices, gaps, occasion, None, owned)
        key = tuple(i["product"]["id"] for i in o.items)
        if key not in seen:
            seen.add(key)
            outfits.append(o)
        choices[k].pick = 0
    return outfits


def complete_the_look(db: Session, user_id: str, look_products: list[dict], limit: int | None = None) -> list[dict]:
    """Suggest pieces for empty slots that go with the look AND with the shopper's past purchases."""
    from .services import product_dict

    cfg = get_settings().matching["complete_the_look"]
    mt = matcher()
    prefs = user_prefs(db, user_id)
    past = [product_dict(p) for p in db.scalars(
        select(m.Product).join(m.OrderItem, m.OrderItem.product_id == m.Product.id)
        .join(m.Order, m.Order.id == m.OrderItem.order_id).where(m.Order.user_id == user_id))]
    past += [product_dict(p) for p in db.scalars(       # in-store purchases count too
        select(m.Product).join(m.StorePurchase, m.StorePurchase.product_id == m.Product.id)
        .where(m.StorePurchase.user_id == user_id))]
    genders = {"women": {"women", "unisex"}, "men": {"men", "unisex"}}.get((prefs or {}).get("gender_fit", "any"),
                                                                          {"women", "men", "unisex"})
    owned = {p["id"] for p in past} | {p["id"] for p in look_products}
    out = []
    for p in db.scalars(select(m.Product).where(m.Product.active.is_(True))):
        d = product_dict(p)
        if d["id"] in owned or d["gender_fit"] not in genders or not d["in_stock"]:
            continue
        if not mt.fills_gap(d, look_products):
            continue
        look_score, _ = mt.compatibility(d, look_products)
        past_score = mt.compatibility(d, past)[0] if past else look_score
        score = 0.7 * look_score + 0.3 * past_score
        if score < cfg["min_score"]:
            continue
        reasons = [r.as_dict() for r in mt.preference_reasons(d, prefs)]
        pairs_with = max(past, key=lambda q: mt.compatibility(d, [q])[0])["name"] if past else None
        out.append({"product": d, "score": round(score, 1), "reasons": reasons, "pairs_with_past": pairs_with})
    out.sort(key=lambda r: (bool(r["reasons"]), -r["score"], r["product"]["price_inr"]))
    # one suggestion per slot keeps it a look, not a list
    seen_slots: set[str] = set()
    uniq = []
    for r in out:
        if r["product"]["slot"] in seen_slots:
            continue
        seen_slots.add(r["product"]["slot"])
        uniq.append(r)
    return uniq[: limit or cfg["max_suggestions"]]


# Flat-lay starting positions on the style board, in % of board width/height. z: higher = worn outside / on top.
LAYOUT = {
    "torso": (30, 4, 40, 20), "full": (29, 3, 42, 20), "outer": (12, 2, 44, 30), "legs": (31, 40, 38, 10),
    "feet": (36, 80, 28, 15), "hand": (70, 46, 26, 40), "head": (70, 4, 24, 45), "neck": (4, 6, 24, 42),
    "ears": (4, 30, 18, 43), "waist": (32, 36, 34, 25), "wrist": (4, 50, 18, 44),
}


def auto_layout(products: list[dict]) -> list[dict]:
    """Deterministic board layout for a set of products. Pieces sharing a slot are fanned out so both stay visible;
    outerwear overlaps the top and sits above it (layered outside)."""
    out, used = [], {}
    for p in products:
        slot = slot_for(p["subcategory"])
        x, y, w, z = LAYOUT.get(slot, (40, 40, 24, 50))
        n = used.get(slot, 0)
        used[slot] = n + 1
        out.append({"product_id": p["id"], "x": x + 8 * n, "y": y + 5 * n, "w": w, "z": z + n})
    return out
