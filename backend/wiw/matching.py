"""Deterministic matching engine. All weights and thresholds come from config/matching.yaml.

Pure functions over plain dicts, so they are easy to unit-test with fixtures:
  piece   : attributes Gemini produced for a detected piece (validated against the vocabulary)
  product : catalog attributes + price + sizes [{size, stock}]
  prefs   : user preferences (budgets, sizes, avoid lists ...)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .colors import color_similarity, harmony
from .vocab import SUB_TO_CAT, label, size_group, slot_for

NONE = ("none", None, "")


def _pairs_to_map(pairs: list[list]) -> dict[frozenset, float]:
    return {frozenset((a, b)): float(s) for a, b, s in pairs}


@dataclass
class Reason:
    code: str   # budget | size | material | color | stock
    label: str

    def as_dict(self) -> dict:
        return {"code": self.code, "label": self.label}


@dataclass
class ScoredItem:
    product: dict
    score: float                     # 0..100 style score
    breakdown: dict[str, float]
    good: bool
    reasons: list[Reason] = field(default_factory=list)   # failed preferences
    positives: list[str] = field(default_factory=list)    # "why" chips
    display_score: float = 0.0

    @property
    def passes_prefs(self) -> bool:
        return not self.reasons

    def as_dict(self) -> dict:
        return {"product": self.product, "score": round(self.score, 1), "display_score": round(self.display_score, 1),
                "good_match": self.good, "reasons": [r.as_dict() for r in self.reasons], "why": self.positives}


@dataclass
class MatchResult:
    for_you: list[ScoredItem]
    also_view: list[ScoredItem]
    closest: list[ScoredItem]     # best items when there is no good match at all

    @property
    def covered(self) -> bool:
        return bool(self.for_you or self.also_view)

    @property
    def covered_in_prefs(self) -> bool:
        return bool(self.for_you)

    def as_dict(self) -> dict:
        return {"for_you": [i.as_dict() for i in self.for_you], "also_view": [i.as_dict() for i in self.also_view],
                "closest": [i.as_dict() for i in self.closest], "covered": self.covered,
                "covered_in_prefs": self.covered_in_prefs}


class Matcher:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        ss = cfg["style_score"]
        self.weights: dict[str, float] = ss["weights"]
        self.max_de = ss["max_delta_e"]
        self.secondary_bonus = ss.get("secondary_color_bonus", 0)
        self.threshold = cfg["good_match"]["threshold"]
        self.min_sub = cfg["good_match"]["min_subcategory_similarity"]
        self.require_stock = cfg["good_match"]["require_in_stock"]
        self.sub_pairs = _pairs_to_map(cfg["subcategory_similarity"])
        self.fabric_groups = [set(g) for g in cfg["fabric_groups"]["groups"]]
        self.fabric_group_score = cfg["fabric_groups"]["score"]
        self.sil_groups = [set(g) for g in cfg["silhouette_groups"]["groups"]]
        self.sil_group_score = cfg["silhouette_groups"]["score"]
        self.busy = set(cfg["pattern_similarity"]["busy"])
        self.busy_score = cfg["pattern_similarity"]["score"]
        self.pref_bonus = cfg["preferences"]["preferred_material_bonus"]
        self.tiers = cfg["tiers"]

    # ---------------------------------------------------------------- attribute similarities

    def sub_sim(self, a: str, b: str) -> float:
        return 1.0 if a == b else self.sub_pairs.get(frozenset((a, b)), 0.0)

    def fabric_sim(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        return self.fabric_group_score if any(a in g and b in g for g in self.fabric_groups) else 0.0

    def silhouette_sim(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        return self.sil_group_score if any(a in g and b in g for g in self.sil_groups) else 0.0

    def pattern_sim(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        return self.busy_score if a in self.busy and b in self.busy else 0.0

    @staticmethod
    def jaccard(a: list[str], b: list[str]) -> float:
        sa, sb = set(a or []), set(b or [])
        return len(sa & sb) / len(sa | sb) if sa | sb else 0.0

    # ---------------------------------------------------------------- style score

    def style_score(self, piece: dict, product: dict) -> tuple[float, dict[str, float]]:
        sims: dict[str, float | None] = {
            "subcategory": self.sub_sim(piece["subcategory"], product["subcategory"]),
            "color": color_similarity(piece["color"], product["primary_color"], self.max_de),
            "pattern": self.pattern_sim(piece.get("pattern", "solid"), product["pattern"]),
            "silhouette": (None if piece.get("silhouette") in NONE or product["silhouette"] in NONE
                           else self.silhouette_sim(piece["silhouette"], product["silhouette"])),
            "fabric": self.fabric_sim(piece.get("fabric", "cotton"), product["fabric"]),
            "style_tags": None if not piece.get("style_tags") else self.jaccard(piece["style_tags"], product["style_tags"]),
            "occasion_tags": (None if not piece.get("occasion_tags")
                              else self.jaccard(piece["occasion_tags"], product["occasion_tags"])),
        }
        active = {k: v for k, v in sims.items() if v is not None}
        total_w = sum(self.weights[k] for k in active)
        raw = {k: self.weights[k] * v * 100 / total_w for k, v in active.items()}
        score = sum(raw.values())
        breakdown = {k: round(v, 2) for k, v in raw.items()}
        sec_a, sec_b = piece.get("secondary_color"), product.get("secondary_color")
        if sec_a and sec_b and sec_a == sec_b:
            score = min(100.0, score + self.secondary_bonus)
        return score, breakdown

    def is_good(self, piece: dict, product: dict, score: float) -> bool:
        if score < self.threshold or self.sub_sim(piece["subcategory"], product["subcategory"]) < self.min_sub:
            return False
        return not self.require_stock or any(s["stock"] > 0 for s in product["sizes"])

    # ---------------------------------------------------------------- preferences

    def preference_reasons(self, product: dict, prefs: dict | None) -> list[Reason]:
        if not prefs:
            return []
        reasons: list[Reason] = []
        lo_hi = (prefs.get("budgets") or {}).get(product["category"])
        if lo_hi and product["price_inr"] > lo_hi[1]:
            reasons.append(Reason("budget", f"₹{product['price_inr'] - lo_hi[1]:,} over budget"))
        group = size_group(product["category"])
        stock = {s["size"]: s["stock"] for s in product["sizes"]}
        if group == "free":
            if not any(stock.values()):
                reasons.append(Reason("stock", "Sold out"))
        else:
            mine = (prefs.get("sizes") or {}).get(group)
            if mine and mine not in stock:
                reasons.append(Reason("size", f"Not made in your size {mine}"))
            elif mine and stock[mine] <= 0:
                reasons.append(Reason("size", f"Your size {mine} is sold out"))
            elif not mine and not any(stock.values()):
                reasons.append(Reason("stock", "Sold out"))
        if product["fabric"] in (prefs.get("avoid_materials") or []):
            reasons.append(Reason("material", product["fabric"].capitalize()))
        if product["primary_color"] in (prefs.get("avoid_colors") or []):
            reasons.append(Reason("color", f"{label(product['primary_color'])}, a colour you avoid"))
        return reasons

    def positives(self, piece: dict, product: dict, breakdown: dict[str, float], prefs: dict | None) -> list[str]:
        chips = []
        if piece["subcategory"] == product["subcategory"]:
            chips.append(label(product["subcategory"]))
        if breakdown.get("color", 0) >= self.weights["color"] * 0.7:
            chips.append("Close colour")
        if piece.get("fabric") == product["fabric"]:
            chips.append(f"Same fabric ({product['fabric']})")
        shared = set(piece.get("style_tags") or []) & set(product["style_tags"])
        if shared:
            chips.append(", ".join(label(s) for s in sorted(shared)[:2]))
        if prefs and product["fabric"] in (prefs.get("preferred_materials") or []) and piece.get("fabric") != product["fabric"]:
            chips.append(f"{product['fabric'].capitalize()}, a fabric you like")
        return chips

    # ---------------------------------------------------------------- ranking + tiers

    def score_item(self, piece: dict, product: dict, prefs: dict | None) -> ScoredItem:
        score, breakdown = self.style_score(piece, product)
        good = self.is_good(piece, product, score)
        reasons = self.preference_reasons(product, prefs)
        bonus = self.pref_bonus if prefs and product["fabric"] in (prefs.get("preferred_materials") or []) else 0
        return ScoredItem(product=product, score=score, breakdown=breakdown, good=good, reasons=reasons,
                          positives=self.positives(piece, product, breakdown, prefs), display_score=min(100, score + bonus))

    def rank(self, piece: dict, products: list[dict], prefs: dict | None) -> MatchResult:
        items = [self.score_item(piece, p, prefs) for p in products]
        items.sort(key=lambda i: (-i.display_score, i.product["price_inr"], i.product["id"]))
        good = [i for i in items if i.good]
        for_you = [i for i in good if i.passes_prefs][: self.tiers["max_for_you"]]
        also = [i for i in good if not i.passes_prefs][: self.tiers["max_also_view"]]
        closest = [] if good else [i for i in items if any(s["stock"] > 0 for s in i.product["sizes"])][: self.tiers["max_closest"]]
        return MatchResult(for_you, also, closest)

    # ---------------------------------------------------------------- look coverage

    @staticmethod
    def coverage(results: list[MatchResult]) -> dict[str, Any]:
        total = len(results)
        covered = sum(r.covered for r in results)
        in_prefs = sum(r.covered_in_prefs for r in results)
        return {"covered": covered, "covered_in_prefs": in_prefs, "total": total,
                "line": coverage_line(covered, in_prefs, total)}

    # ---------------------------------------------------------------- complete the look

    def compatibility(self, product: dict, look: list[dict]) -> tuple[float, dict[str, float]]:
        """How well `product` goes with the pieces already in a look (0..100)."""
        w = self.cfg["complete_the_look"]["weights"]
        if not look:
            return 0.0, {}
        colors = [harmony(product["primary_color"], o.get("primary_color") or o.get("color")) for o in look]
        styles = set().union(*(set(o.get("style_tags") or []) for o in look))
        occs = set().union(*(set(o.get("occasion_tags") or []) for o in look))
        s_overlap = len(set(product["style_tags"]) & styles) / max(1, min(len(product["style_tags"]), 3))
        o_overlap = len(set(product["occasion_tags"]) & occs) / max(1, min(len(product["occasion_tags"]), 3))
        parts = {"color_harmony": w["color_harmony"] * sum(colors) / len(colors),
                 "style_overlap": w["style_overlap"] * min(1.0, s_overlap),
                 "occasion_overlap": w["occasion_overlap"] * min(1.0, o_overlap)}
        return sum(parts.values()), parts

    def fills_gap(self, product: dict, look: list[dict]) -> bool:
        """No duplicated slot: a look has one top/bottom/one-piece/outerwear/footwear and one of each accessory."""
        slots = {slot_for(o["subcategory"]) for o in look}
        subs = {o["subcategory"] for o in look}
        slot = slot_for(product["subcategory"])
        if product["subcategory"] in subs or slot in slots:
            return False
        if slot == "full" and slots & {"torso", "legs"}:
            return False
        if slot in ("torso", "legs") and "full" in slots:
            return False
        return True


def coverage_line(covered: int, in_prefs: int, total: int) -> str:
    if total == 0:
        return "Save a few pieces to see how much of the look this store covers."
    base = f"This store covers {covered} of {total} piece{'s' if total != 1 else ''}"
    return f"{base} ({in_prefs} within your preferences)." if covered else f"{base}."


def piece_attrs(p: Any) -> dict:
    """DetectedPiece model or dict -> matcher piece dict."""
    g = (lambda k, d=None: p.get(k, d)) if isinstance(p, dict) else (lambda k, d=None: getattr(p, k, d))
    sub = g("subcategory")
    return {"subcategory": sub, "category": SUB_TO_CAT[sub], "color": g("color"), "secondary_color": g("secondary_color"),
            "pattern": g("pattern", "solid"), "fabric": g("fabric", "cotton"), "silhouette": g("silhouette", "none"),
            "length": g("length", "none"), "style_tags": list(g("style_tags", []) or []),
            "occasion_tags": list(g("occasion_tags", []) or []), "gender_fit": g("gender_fit", "unisex")}
