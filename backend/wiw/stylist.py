"""Stylist chat: Gemini function calling over deterministic tools, with an offline rule-based planner.

The model never sees raw database IDs for folders or hangers (hangers are "hanger 1..n" in the current folder),
which keeps replay cache keys stable. Products are referenced by catalog ID and always resolved from the database.
Preference changes are proposed by the tool and only applied after the shopper confirms in the UI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gemini
from . import models as m
from .catalog_search import allowed_genders
from .colors import color_similarity
from .commerce import CartError, add_item
from .services import matches_for_piece, pick_size, prefs_dict, product_dict
from .settings import get_settings
from .styling import folder_hangers, suggest_outfit
from .vocab import CATEGORIES, COLORS, FABRICS, OCCASIONS, SUB_TO_CAT, label, slot_for

VERSION = "stylist-v2"
FORMALITY = ["more_casual", "more_formal", "more_festive"]

TOOLS = [
    {"name": "search_catalog", "description": "Search the Urban Thread catalog. Returns real in-stock products with IDs and prices.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "What to look for, e.g. 'white linen shirt'"},
         "category": {"type": "string", "enum": CATEGORIES},
         "max_price_inr": {"type": "integer"},
         "occasion": {"type": "string", "enum": OCCASIONS},
         "color": {"type": "string", "enum": COLORS}}, "required": ["query"]}},
    {"name": "get_hanger_matches", "description": "Matches for one saved hanger in the current folder: 'for_you' (fits style and preferences) and 'also_view' (fits style, fails a preference, with reasons).",
     "parameters": {"type": "object", "properties": {"hanger": {"type": "integer", "description": "Hanger number from the folder list (1-based)"}},
                    "required": ["hanger"]}},
    {"name": "get_preferences", "description": "The shopper's saved preferences (budgets, sizes, materials, colours, occasions).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "update_preferences", "description": "Propose a change to saved preferences. It is NOT applied until the shopper confirms in the app.",
     "parameters": {"type": "object", "properties": {
         "sizes": {"type": "object", "properties": {"tops": {"type": "string"}, "bottoms": {"type": "string"}, "footwear": {"type": "string"}}},
         "budget_category": {"type": "string", "enum": CATEGORIES}, "budget_max_inr": {"type": "integer"},
         "add_avoid_materials": {"type": "array", "items": {"type": "string", "enum": FABRICS}},
         "add_preferred_materials": {"type": "array", "items": {"type": "string", "enum": FABRICS}},
         "add_avoid_colors": {"type": "array", "items": {"type": "string", "enum": COLORS}},
         "add_occasions": {"type": "array", "items": {"type": "string", "enum": OCCASIONS}},
         "fit": {"type": "string", "enum": ["slim", "regular", "relaxed", "oversized"]}}}},
    {"name": "suggest_outfit", "description": "Build a full outfit from the current folder's hangers using real catalog items, optionally for an occasion, a total budget, or a formality nudge.",
     "parameters": {"type": "object", "properties": {
         "occasion": {"type": "string", "description": "e.g. 'beach wedding', 'work', 'sangeet'"},
         "max_total_inr": {"type": "integer", "description": "Budget for the whole outfit"},
         "formality": {"type": "string", "enum": FORMALITY}}}},
    {"name": "place_on_mannequin", "description": "Dress the folder's mannequin. Omit product_ids to use the most recently suggested outfit.",
     "parameters": {"type": "object", "properties": {"product_ids": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "add_to_cart", "description": "Add products to the cart in the shopper's size when it is in stock. Omit product_ids to add the most recently suggested outfit.",
     "parameters": {"type": "object", "properties": {"product_ids": {"type": "array", "items": {"type": "string"}}}}},
]

SYSTEM = """You are the in-store stylist for Urban Thread, a fictional Indian high-street fashion store, inside the
Walk-In Wardrobe app. The shopper saves outfit inspiration and you help turn it into pieces they can buy here.

How you work:
- Be warm, brief and specific: 1-3 short sentences, then let the product cards do the talking.
- If you don't know the occasion or how they want to wear it, ask ONE short question (you may still offer a first pick).
- Use tools for every product fact. Only mention products, prices, sizes and totals that a tool returned in this
  conversation. Never invent products, prices, discounts, sizes or stock. Refer to products by name, not ID.
- For "make it work for <occasion> under <budget>", call suggest_outfit with occasion and max_total_inr.
- For "more casual/formal/festive", call suggest_outfit with formality.
- Only call update_preferences when the shopper states a lasting preference ("I'm a size L", "I hate polyester").
  Then say you've proposed the change and they can confirm it. Never claim it is saved.
- If the store can't cover a piece, say so honestly and offer the closest option.
- Describe clothing only. Never comment on the shopper's body, face or appearance.
- Prices are in Indian rupees, written like ₹1,999. Never add up prices yourself: outfit totals come from
  suggest_outfit. If the shopper wants a swap, call suggest_outfit again (or search) instead of doing arithmetic.
"""


@dataclass
class Ctx:
    db: Session
    user: m.User
    folder: m.Folder | None
    hangers: list[m.Hanger]
    products: dict[str, dict] = field(default_factory=dict)   # full product dicts for the UI
    outfit: dict | None = None
    shown: list[str] = field(default_factory=list)            # product ids to show as cards
    pending: dict | None = None
    actions: list[str] = field(default_factory=list)

    @property
    def prefs(self) -> dict | None:
        return prefs_dict(self.db.get(m.Preferences, self.user.id))


def compact(p: dict, prefs: dict | None) -> dict:
    size = pick_size(prefs, p)
    return {"id": p["id"], "name": p["name"], "price_inr": p["price_inr"], "fabric": p["fabric"],
            "color": p["primary_color"], "type": label(p["subcategory"]),
            "your_size_in_stock": bool(size), "occasions": p["occasion_tags"][:3]}


def context_text(ctx: Ctx) -> str:
    prefs = ctx.prefs or {}
    lines = [f"Shopper: {ctx.user.name}, shops {prefs.get('gender_fit', 'women')}'s, city {ctx.user.city}."]
    if prefs:
        lines.append(f"Sizes: {prefs.get('sizes')}. Avoids materials: {prefs.get('avoid_materials')}. "
                     f"Avoids colours: {prefs.get('avoid_colors')}. Budgets per piece (INR min,max): {prefs.get('budgets')}.")
    if ctx.folder:
        lines.append(f"Current folder: \"{ctx.folder.name}\" ({ctx.folder.description or 'no description'}).")
        if ctx.hangers:
            lines.append("Hangers in this folder:")
            for i, h in enumerate(ctx.hangers, 1):
                lines.append(f"  {i}. {h.piece.name} ({label(h.piece.subcategory)}, {h.piece.color} {h.piece.fabric})")
        else:
            lines.append("The folder has no hangers yet.")
    else:
        lines.append("No folder is open.")
    if ctx.outfit and ctx.outfit.get("items"):
        lines.append("Most recent outfit you suggested (total ₹{:,}): ".format(ctx.outfit["total_inr"])
                     + "; ".join(f"{i['product']['name']} [{i['product']['id']}]" for i in ctx.outfit["items"]))
    return SYSTEM + "\nContext:\n" + "\n".join(lines)


# ------------------------------------------------------------------ tools

def _remember(ctx: Ctx, p: dict, show: bool = True) -> dict:
    ctx.products[p["id"]] = p
    if show and p["id"] not in ctx.shown:
        ctx.shown.append(p["id"])
    return compact(p, ctx.prefs)


def t_search_catalog(ctx: Ctx, query: str = "", category: str | None = None, max_price_inr: int | None = None,
                     occasion: str | None = None, color: str | None = None) -> dict:
    prefs = ctx.prefs
    q = select(m.Product).where(m.Product.active.is_(True),
                                m.Product.gender_fit.in_(allowed_genders((prefs or {}).get("gender_fit", "any"))))
    words = set(re.findall(r"[a-z]+", query.lower()))
    subs = subcategories_in(query)
    if subs:
        q = q.where(m.Product.subcategory.in_(subs))
    elif category in CATEGORIES:
        q = q.where(m.Product.category == category)
    if max_price_inr:
        q = q.where(m.Product.price_inr <= max_price_inr)
    rows = [product_dict(p) for p in ctx.db.scalars(q)]
    rows = [p for p in rows if p["in_stock"]]
    qcolors = [c for c in COLORS if c.replace("_", " ") in query.lower()] + ([color] if color else [])
    qfabrics = [f for f in FABRICS if f in words]

    def score(p: dict) -> float:
        s = 0.0
        if qcolors:
            s += 3 * max(color_similarity(c, p["primary_color"], 45) for c in qcolors)
        s += 2 * (p["fabric"] in qfabrics)
        s += 1.5 * bool(occasion and occasion in p["occasion_tags"])
        s += sum(w in p["name"].lower() for w in words) * 0.5
        s += 1.0 * bool(pick_size(prefs, p))
        return s

    rows.sort(key=lambda p: (-score(p), p["price_inr"]))
    return {"results": [_remember(ctx, p) for p in rows[:6]], "count": len(rows)}


def t_get_hanger_matches(ctx: Ctx, hanger: int) -> dict:
    if not ctx.hangers or not 1 <= int(hanger) <= len(ctx.hangers):
        return {"error": f"There is no hanger {hanger} in this folder."}
    h = ctx.hangers[int(hanger) - 1]
    res = matches_for_piece(ctx.db, ctx.user.id, h.piece)
    out = {"piece": h.piece.name,
           "for_you": [_remember(ctx, i.product) for i in res.for_you[:3]],
           "also_view": [{**_remember(ctx, i.product), "fails": [r.label for r in i.reasons]} for i in res.also_view[:3]]}
    if not res.covered:
        out["closest"] = [_remember(ctx, i.product) for i in res.closest[:2]]
        out["note"] = "The store has no close match for this piece."
    return out


def t_get_preferences(ctx: Ctx) -> dict:
    return ctx.prefs or {}


def t_update_preferences(ctx: Ctx, **changes) -> dict:  # noqa: ANN003
    prefs = ctx.prefs or {}
    new = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in prefs.items()}
    summary = []
    if changes.get("sizes"):
        new["sizes"] = {**new.get("sizes", {}), **{k: str(v) for k, v in changes["sizes"].items() if v}}
        summary.append("sizes " + ", ".join(f"{k} {v}" for k, v in changes["sizes"].items() if v))
    if changes.get("budget_category") in CATEGORIES and changes.get("budget_max_inr"):
        c = changes["budget_category"]
        lo = (new.get("budgets", {}).get(c) or [0, 0])[0]
        new.setdefault("budgets", {})[c] = [lo, int(changes["budget_max_inr"])]
        summary.append(f"{label(c).lower()} budget up to ₹{int(changes['budget_max_inr']):,}")
    for key, field_, verb in (("add_avoid_materials", "avoid_materials", "avoid"), ("add_preferred_materials", "preferred_materials", "prefer"),
                              ("add_avoid_colors", "avoid_colors", "avoid colour"), ("add_occasions", "occasions", "shop for")):
        vals = [v for v in changes.get(key) or [] if v in (FABRICS if "materials" in key else COLORS if "colors" in key else OCCASIONS)]
        if vals:
            new[field_] = sorted(set(new.get(field_, [])) | set(vals))
            if field_ == "avoid_materials":
                new["preferred_materials"] = [x for x in new.get("preferred_materials", []) if x not in vals]
            summary.append(f"{verb} {', '.join(vals)}")
    if changes.get("fit") in ("slim", "regular", "relaxed", "oversized"):
        new["fit"] = changes["fit"]
        summary.append(f"{changes['fit']} fit")
    if not summary:
        return {"status": "no_change"}
    ctx.pending = {"preferences": new, "summary": "; ".join(summary)}
    return {"status": "needs_confirmation", "summary": ctx.pending["summary"]}


def t_suggest_outfit(ctx: Ctx, occasion: str | None = None, max_total_inr: int | None = None,
                     formality: str | None = None) -> dict:
    if not ctx.folder:
        return {"error": "Open a folder first so I know which look to style."}
    if not ctx.hangers:
        return {"error": "This folder has no hangers yet. Upload an inspo and pick some pieces first."}
    o = suggest_outfit(ctx.db, ctx.user.id, ctx.folder.id, occasion, max_total_inr,
                       formality if formality in FORMALITY else None).as_dict()
    for it in o["items"]:
        _remember(ctx, it["product"], show=False)
    ctx.outfit = o
    return {"items": [{"for": it["piece_name"], **compact(it["product"], ctx.prefs),
                       "outside_preferences": [r["label"] for r in it["reasons"]]} for it in o["items"]],
            "total_inr": o["total_inr"], "within_budget": o["within_budget"], "over_by_inr": o["over_by_inr"],
            "left_out_for_budget": o.get("dropped", []), "not_in_store": o["gaps"]}


def _default_ids(ctx: Ctx, product_ids: list[str] | None) -> list[str]:
    return list(product_ids or []) or [i["product"]["id"] for i in (ctx.outfit or {}).get("items", [])]


def t_place_on_mannequin(ctx: Ctx, product_ids: list[str] | None = None) -> dict:
    if not ctx.folder:
        return {"error": "Open a folder first."}
    product_ids = _default_ids(ctx, product_ids)
    placements, seen_slots = [], set()
    for pid in product_ids:
        p = ctx.db.get(m.Product, pid)
        if not p:
            continue
        slot = slot_for(p.subcategory)
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        placements.append({"product_id": p.id, "slot": slot})
    if not placements:
        return {"error": "None of those products exist in the catalog."}
    occasion = (ctx.outfit or {}).get("occasion")
    look = m.Look(user_id=ctx.user.id, folder_id=ctx.folder.id, name=f"Stylist pick for {occasion}" if occasion else "Stylist pick",
                  placements=placements, reason=occasion or "")
    ctx.db.add(look)
    ctx.db.flush()
    ctx.actions.append(f"Dressed the mannequin in {len(placements)} piece{'s' if len(placements) != 1 else ''}")
    return {"status": "ok", "placed": [p["product_id"] for p in placements]}


def t_add_to_cart(ctx: Ctx, product_ids: list[str] | None = None) -> dict:
    product_ids = _default_ids(ctx, product_ids)
    added, needs = [], []
    for pid in product_ids:
        p = ctx.db.get(m.Product, pid)
        if not p:
            continue
        size = pick_size(ctx.prefs, p)
        try:
            if not size:
                raise CartError("size needed")
            add_item(ctx.db, ctx.user.id, p.id, size, 1, ctx.folder.id if ctx.folder else None)
            added.append({"id": p.id, "name": p.name, "size": size})
        except CartError:
            needs.append({"id": p.id, "name": p.name})
            _remember(ctx, product_dict(p))
    if added:
        ctx.actions.append(f"Added {len(added)} item{'s' if len(added) != 1 else ''} to your cart")
    return {"added": added, "needs_size_choice": needs}


IMPL = {"search_catalog": t_search_catalog, "get_hanger_matches": t_get_hanger_matches,
        "get_preferences": t_get_preferences, "update_preferences": t_update_preferences,
        "suggest_outfit": t_suggest_outfit, "place_on_mannequin": t_place_on_mannequin, "add_to_cart": t_add_to_cart}


def execute(ctx: Ctx, name: str, args: dict) -> dict:
    fn = IMPL.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(ctx, **(args or {}))
    except TypeError as e:
        return {"error": f"bad arguments: {e}"}


# ------------------------------------------------------------------ offline planner

SYNONYMS = {"tee": "tshirt", "t-shirt": "tshirt", "t shirt": "tshirt", "tshirt": "tshirt", "heels": "block_heels",
            "earrings": "jewellery", "jhumkas": "jewellery", "necklace": "jewellery", "sunnies": "sunglasses",
            "shades": "sunglasses", "trainers": "sneakers", "mojaris": "juttis", "pants": "chinos", "trousers": "chinos",
            "handbag": "tote", "bag": "tote", "jacket": "denim_jacket", "kurti": "kurta", "co-ord": "coord_set"}


def subcategories_in(text: str) -> list[str]:
    t = text.lower()
    found = [s for s in SUB_TO_CAT if re.search(rf"\b{re.escape(s.replace('_', ' '))}s?\b", t)
             or re.search(rf"\b{re.escape(label(s).lower())}s?\b", t)]
    found += [v for k, v in SYNONYMS.items() if re.search(rf"\b{re.escape(k)}s?\b", t) and v not in found]
    return found

OCCASION_WORDS = [
    (r"beach wedding", "beach wedding"), (r"sangeet|mehendi|mehndi|haldi|diwali|puja|festive|festival", "festive"),
    (r"wedding|reception|shaadi", "wedding"), (r"beach|pool", "beach"), (r"office|work|meeting|interview", "work"),
    (r"party|club|night out|cocktail", "party"), (r"date", "date"), (r"brunch|lunch|cafe", "brunch"),
    (r"goa|vacation|holiday|trip|travel", "vacation"), (r"formal|black tie", "formal"), (r"casual|everyday|weekend", "casual"),
]


def parse_budget(text: str) -> int | None:
    t = text.lower().replace(",", "")
    mt = re.search(r"(?:under|below|within|max|less than|upto|up to|budget(?: of)?|₹|rs\.?|inr)\s*₹?\s*(\d+(?:\.\d+)?)\s*(k)?", t)
    if not mt:
        mt = re.search(r"(\d+(?:\.\d+)?)\s*(k)\b", t)
    if not mt:
        return None
    n = float(mt.group(1)) * (1000 if mt.group(2) else 1)
    return int(n) if n >= 100 else None


def parse_occasion(text: str) -> str | None:
    t = text.lower()
    for pat, occ in OCCASION_WORDS:
        if re.search(rf"\b(?:{pat})\b", t):
            return occ
    return None


def parse_formality(text: str) -> str | None:
    t = text.lower()
    if re.search(r"more (casual|relaxed|chill)|less formal|dress(?:ed)?(?: it| this| them)? down", t):
        return "more_casual"
    if re.search(r"more (formal|polished|dressy)|dress(?:ed)?(?: it| this| them)? up|dressier", t):
        return "more_formal"
    if re.search(r"more (festive|ethnic|traditional)", t):
        return "more_festive"
    return None


def parse_pref_change(text: str) -> dict:
    t = text.lower()
    ch: dict = {}
    mt = re.search(r"\b(?:i(?:'m| am)(?: a)?|my size is)\s*(?:size\s*)?(xxs|xs|s|m|l|xl|xxl)\b", t)
    if mt:
        ch["sizes"] = {"tops": mt.group(1).upper()}
    avoid = re.search(r"(?:hate|avoid|no more|don't like|dont like|can't stand)\s+([a-z ,and]+)", t)
    if avoid:
        vals = [f for f in FABRICS if f in avoid.group(1)]
        cols = [c for c in COLORS if c.replace("_", " ") in avoid.group(1)]
        if vals:
            ch["add_avoid_materials"] = vals
        if cols:
            ch["add_avoid_colors"] = cols
    love = re.search(r"(?:love|prefer|only wear)\s+([a-z ,and]+)", t)
    if love:
        vals = [f for f in FABRICS if f in love.group(1)]
        if vals:
            ch["add_preferred_materials"] = vals
    return ch


def plan(ctx: Ctx, message: str, trace: list[dict]) -> gemini.AgentResult:
    """Deterministic stand-in for the model: pick tools from simple intent rules, then write a templated reply."""
    ran = {t["name"] for t in trace if t["role"] == "tool"}

    def call(name: str, **args) -> dict:  # noqa: ANN003
        out = execute(ctx, name, args)
        trace.append({"role": "model", "calls": [{"name": name, "args": args}]})
        trace.append({"role": "tool", "name": name, "response": out})
        return out

    t = message.lower()
    budget, occasion, formality = parse_budget(message), parse_occasion(message), parse_formality(message)
    pref = parse_pref_change(message)
    if pref and "update_preferences" not in ran:
        out = call("update_preferences", **pref)
        if out.get("status") == "needs_confirmation":
            return gemini.AgentResult(f"Got it. I've proposed saving: {out['summary']}. Tap confirm and I'll use it for "
                                      "every match from now on.", trace, "fallback")
    if re.search(r"\b(cart|buy|checkout|order)\b", t):
        ids = [i["product"]["id"] for i in (ctx.outfit or {}).get("items", [])]
        if not ids:
            call("suggest_outfit", occasion=occasion, max_total_inr=budget)
            ids = [i["product"]["id"] for i in (ctx.outfit or {}).get("items", [])]
        out = call("add_to_cart", product_ids=ids)
        msg = f"Added {len(out['added'])} piece{'s' if len(out['added']) != 1 else ''} to your cart in your size."
        if out["needs_size_choice"]:
            msg += " Pick a size for: " + ", ".join(n["name"] for n in out["needs_size_choice"]) + "."
        return gemini.AgentResult(msg, trace, "fallback")
    hm = re.search(r"(?:matches|options|alternatives|else) for (?:the |my )?([a-z ]+)", t)
    if hm and ctx.hangers:
        idx = next((i for i, h in enumerate(ctx.hangers, 1) if any(w in h.piece.name.lower() for w in hm.group(1).split())), None)
        if idx:
            out = call("get_hanger_matches", hanger=idx)
            n = len(out.get("for_you", []))
            return gemini.AgentResult(f"Here are the closest pieces to your {out['piece'].lower()}: {n} fit your preferences"
                                      + (", plus a few that are worth a look." if out.get("also_view") else "."), trace, "fallback")
    if re.search(r"mannequin|try (it|this|them) on|put (it|them|this) on|dress (me|it|her|him)", t):
        if not (ctx.outfit or {}).get("items") and "suggest_outfit" not in ran:
            call("suggest_outfit", occasion=occasion, max_total_inr=budget, formality=formality)
        items = (ctx.outfit or {}).get("items", [])
        if not items:
            return gemini.AgentResult("Add a few hangers to this folder first, then I can dress the mannequin.", trace, "fallback")
        call("place_on_mannequin", product_ids=[i["product"]["id"] for i in items])
        return gemini.AgentResult(f"Done. Your mannequin is wearing the {', '.join(i['product']['name'] for i in items)}. "
                                  "Open the walk-in wardrobe to see it.", trace, "fallback")
    wants_search = re.search(r"\b(find|show|search|looking for|need|want)\b", t)
    sub_hit = subcategories_in(t)
    if wants_search and sub_hit and not occasion:
        out = call("search_catalog", query=message, max_price_inr=budget)
        if not out["results"]:
            return gemini.AgentResult("I couldn't find that in Urban Thread right now. Want me to try a close alternative?",
                                      trace, "fallback")
        n = len(out["results"])
        return gemini.AgentResult(f"Here {'is' if n == 1 else 'are'} {n} option{'s' if n != 1 else ''} from Urban Thread"
                                  + (f" under ₹{budget:,}" if budget else "") + ".", trace, "fallback")
    if not ctx.folder or not ctx.hangers:
        return gemini.AgentResult("Open a folder with a few hangers and I'll style them into a look. What's the occasion "
                                  "you're shopping for?", trace, "fallback")
    if not (budget or occasion or formality) and not re.search(r"\b(style|outfit|look|wear|suggest|pick)\b", t):
        return gemini.AgentResult("Happy to help! What's the occasion, and do you want it dressed up or easy? "
                                  "You can also give me a budget, like “under ₹5,000”.", trace, "fallback")
    if "suggest_outfit" not in ran:
        call("suggest_outfit", occasion=occasion, max_total_inr=budget, formality=formality)
    o = ctx.outfit or {}
    if not o.get("items"):
        return gemini.AgentResult("I couldn't build a look from this folder's hangers yet.", trace, "fallback")
    names = ", ".join(i["product"]["name"] for i in o["items"])
    msg = (f"For {occasion}" if occasion else "Here's a look") + f": {names}. Total ₹{o['total_inr']:,}"
    if budget:
        msg += " (within your budget)." if o["within_budget"] else f", ₹{o['over_by_inr']:,} over your budget; that's the closest I can get."
    else:
        msg += "."
    if o.get("dropped"):
        msg += f" I left out the {', '.join(d.lower() for d in o['dropped'])} to stay on budget."
    if o.get("gaps"):
        msg += f" Urban Thread doesn't stock a match for the {', '.join(g.lower() for g in o['gaps'])} yet."
    notes = [f"{i['product']['name']}: {i['reasons'][0]['label'].lower()}" for i in o["items"] if i["reasons"]]
    if notes:
        msg += " Heads-up: " + "; ".join(notes) + "."
    if re.search(r"mannequin|try (it )?on|put (it|them) on", t):
        call("place_on_mannequin", product_ids=[i["product"]["id"] for i in o["items"]])
        msg += " I've dressed your mannequin in it."
    return gemini.AgentResult(msg, trace, "fallback")


# ------------------------------------------------------------------ entry point

def chat(db: Session, user: m.User, folder: m.Folder | None, message: str) -> dict:
    cfg = get_settings().matching["stylist"]
    hangers = folder_hangers(db, user.id, folder.id) if folder else []
    ctx = Ctx(db=db, user=user, folder=folder, hangers=hangers)
    prev = list(db.scalars(select(m.ChatMessage).where(m.ChatMessage.user_id == user.id,
                                                        m.ChatMessage.folder_id == (folder.id if folder else None))
                           .order_by(m.ChatMessage.id.desc()).limit(cfg["history_messages"])))[::-1]
    history = [{"role": "user" if c.role == "user" else "model", "text": c.content} for c in prev if c.content]
    history.append({"role": "user", "text": message})
    # the offline planner can see the last outfit it proposed (so "add it to cart" works)
    last_outfit = next((c.payload.get("outfit") for c in reversed(prev) if c.role == "assistant" and c.payload.get("outfit")), None)
    if last_outfit:
        ctx.outfit = last_outfit
    res = gemini.run_agent("stylist", version=VERSION, system=context_text(ctx), history=history, tools=TOOLS,
                           execute=lambda n, a: execute(ctx, n, a), fallback=lambda tr: plan(ctx, message, tr),
                           max_steps=cfg["max_steps"])
    text = res.text.strip() or "Here's what I found."
    # never surface IDs or products the tools didn't return
    text = re.sub(r"\s*\(?\b(?:ID:?\s*)?ut-\d{3}\b\)?", "", text).strip()
    outfit = ctx.outfit if any(t["name"] == "suggest_outfit" for t in res.trace if t["role"] == "tool") else None
    shown = [] if outfit else [ctx.products[i] for i in ctx.shown if i in ctx.products][:6]
    payload = {"source": res.source, "products": shown,
               "outfit": outfit, "pending_preferences": ctx.pending, "actions": ctx.actions}
    db.add(m.ChatMessage(user_id=user.id, folder_id=folder.id if folder else None, role="user", content=message, payload={}))
    reply = m.ChatMessage(user_id=user.id, folder_id=folder.id if folder else None, role="assistant", content=text,
                          payload=payload)
    db.add(reply)
    db.flush()
    return message_dict(reply)


def message_dict(c: m.ChatMessage) -> dict:
    return {"id": c.id, "role": c.role, "content": c.content, "payload": c.payload or {}, "created_at": c.created_at.isoformat()}


def greeting(user: m.User, folder: m.Folder | None, n_hangers: int) -> dict:
    if folder and n_hangers:
        text = (f"Hi {user.name}! I'm your Urban Thread stylist. You've got {n_hangers} piece{'s' if n_hangers != 1 else ''} "
                f"hanging in “{folder.name}”. What's the occasion, and how do you want to wear it?")
    elif folder:
        text = f"Hi {user.name}! Upload an inspo to “{folder.name}” and I'll help you shop the look."
    else:
        text = f"Hi {user.name}! Open a wardrobe folder and I'll help you style it, or ask me to find something."
    return {"id": 0, "role": "assistant", "content": text, "payload": {}, "created_at": ""}
