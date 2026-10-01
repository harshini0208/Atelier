"""Deterministic generator for the synthetic Urban Thread storefront and demo personas.

    python data/generate.py        # writes data/catalog.json and data/personas.json

Everything here is fictional. Items are hand-specified (so the catalog has deliberate gaps and edge
cases for the demo); stock, MRP, and arrival dates come from a seeded RNG, so output is identical on
every run.

Deliberate gaps (drive partial look coverage): no wide-leg trousers, no lehengas, no stilettos,
no kolhapuris, no shrugs, no leggings, and only one pair of juttis.
Deliberate edge cases: over-budget items, polyester look-alikes, size-level stock-outs, one item that
is fully sold out (for the restock alert), one item with a scheduled price drop.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from wiw.colors import color_family  # noqa: E402
from wiw.vocab import SUB_TO_CAT, label, size_system  # noqa: E402

SEED = 20260929
NOW = datetime(2026, 9, 29, 10, 0, 0)
STORE = {"id": "urban-thread", "name": "Urban Thread", "brand": "Urban Thread", "warehouse_city": "Mumbai",
         "description": "A fictional mid-size high-street label: easy basics, smart workwear, a small festive edit."}

N = "none"
# sub, gender, name, color, color2, pattern, fabric, fit, length, neckline, sleeve, occasions, styles, season, price, extra
ITEMS: list[tuple] = [
    # ---------------- tops
    ("linen_shirt", "women", "Ivory linen relaxed shirt", "ivory", None, "solid", "linen", "relaxed", "regular", "collar", "long", "work brunch vacation", "old_money minimal classic", "summer", 1799, {}),
    ("linen_shirt", "women", "Cream linen oversized shirt", "cream", None, "solid", "linen", "oversized", "long", "collar", "long", "vacation brunch", "old_money resort", "summer", 3299, {}),
    ("linen_shirt", "women", "White linen-look shirt", "white", None, "solid", "polyester", "relaxed", "regular", "collar", "long", "work casual", "minimal classic", "summer", 1199, {}),
    ("linen_shirt", "women", "Ecru linen boyfriend shirt", "cream", None, "solid", "linen", "relaxed", "regular", "collar", "three_quarter", "brunch vacation work", "old_money minimal", "summer", 1999, {"stock": {"M": 0}}),
    ("linen_shirt", "men", "Sky linen shirt", "sky_blue", None, "solid", "linen", "regular", "regular", "collar", "long", "vacation beach wedding", "resort classic old_money", "summer", 1999, {}),
    ("linen_shirt", "men", "Sage linen band-collar shirt", "sage", None, "solid", "linen", "relaxed", "regular", "mandarin", "long", "vacation beach casual", "resort minimal", "summer", 2199, {}),
    ("linen_shirt", "unisex", "Olive linen camp shirt", "olive", None, "solid", "linen", "relaxed", "regular", "collar", "short", "vacation beach casual", "resort", "summer", 1699, {"price_drop_to": 1299}),
    ("shirt", "women", "Blue candy-stripe shirt", "sky_blue", "white", "stripes", "cotton", "relaxed", "regular", "collar", "long", "work brunch vacation", "old_money preppy classic", "all", 1899, {}),
    ("shirt", "men", "White oxford shirt", "white", None, "solid", "cotton", "slim", "regular", "collar", "long", "work formal wedding", "classic formal old_money", "all", 1999, {}),
    ("shirt", "men", "Navy pinstripe shirt", "navy", "white", "stripes", "cotton", "slim", "regular", "collar", "long", "work formal", "formal classic", "all", 2299, {}),
    ("shirt", "women", "Black satin shirt", "black", None, "solid", "polyester", "regular", "regular", "collar", "long", "party date", "edgy minimal", "all", 1599, {}),
    ("shirt", "men", "Red check flannel shirt", "red", "black", "checks", "cotton", "relaxed", "regular", "collar", "long", "casual travel", "streetwear", "winter", 1799, {}),
    ("tshirt", "unisex", "White crew tee", "white", None, "solid", "cotton", "regular", "regular", "crew", "short", "casual", "minimal athleisure", "all", 599, {}),
    ("tshirt", "unisex", "Black oversized graphic tee", "black", "white", "print", "cotton", "oversized", "regular", "crew", "short", "casual", "streetwear y2k", "all", 899, {}),
    ("tshirt", "men", "Navy striped breton tee", "navy", "white", "stripes", "cotton", "regular", "regular", "crew", "long", "casual brunch", "classic preppy", "all", 999, {}),
    ("crop_top", "women", "Black ribbed crop top", "black", None, "solid", "knit", "slim", "cropped", "square", "sleeveless", "party casual", "streetwear y2k", "summer", 699, {}),
    ("crop_top", "women", "Lavender halter crop top", "lavender", None, "solid", "viscose", "slim", "cropped", "halter", "sleeveless", "date vacation", "romantic", "summer", 799, {}),
    ("blouse", "women", "Blush puff-sleeve blouse", "blush", None, "solid", "viscose", "regular", "regular", "square", "short", "brunch date", "romantic", "summer", 1499, {}),
    ("blouse", "women", "Ivory silk-feel blouse", "ivory", None, "solid", "polyester", "regular", "regular", "v_neck", "long", "work", "old_money classic formal", "all", 1699, {}),
    ("kurta", "women", "Mustard block-print kurta", "mustard", "rust", "print", "cotton", "straight", "long", "mandarin", "three_quarter", "festive casual work", "ethnic boho", "all", 1499, {}),
    ("kurta", "men", "White chikankari kurta", "white", "ivory", "embroidered", "cotton", "regular", "long", "mandarin", "long", "festive wedding", "ethnic classic", "all", 2199, {}),
    ("hoodie", "unisex", "Black oversized hoodie", "black", None, "solid", "cotton", "oversized", "regular", "hood", "long", "casual travel", "streetwear athleisure", "winter", 1999, {}),
    ("hoodie", "unisex", "Grey zip hoodie", "grey", None, "solid", "cotton", "regular", "regular", "hood", "long", "gym casual", "athleisure", "winter", 1799, {}),
    ("sweater", "women", "Camel cable-knit sweater", "camel", None, "solid", "wool", "relaxed", "regular", "crew", "long", "work casual", "old_money classic", "winter", 2799, {}),
    ("sweater", "men", "Navy crew sweater", "navy", None, "solid", "wool", "regular", "regular", "crew", "long", "work", "classic preppy old_money", "winter", 2499, {}),
    # ---------------- bottoms (no wide-leg trousers, no leggings)
    ("jeans", "women", "Mid-blue straight jeans", "denim_blue", None, "solid", "denim", "straight", "ankle", N, N, "casual brunch", "classic minimal", "all", 2299, {}),
    ("jeans", "women", "Black skinny jeans", "black", None, "solid", "denim", "slim", "ankle", N, N, "casual party", "edgy", "all", 1999, {}),
    ("jeans", "men", "Indigo slim jeans", "navy", None, "solid", "denim", "slim", "long", N, N, "casual work", "classic", "all", 2499, {}),
    ("jeans", "men", "Light-wash baggy jeans", "sky_blue", None, "solid", "denim", "relaxed", "long", N, N, "casual", "streetwear y2k", "all", 2799, {}),
    ("chinos", "women", "Beige straight chinos", "beige", None, "solid", "cotton", "straight", "ankle", N, N, "work brunch", "old_money minimal classic", "all", 1999, {}),
    ("chinos", "women", "Sand tapered chinos", "sand", None, "solid", "cotton", "tapered", "ankle", N, N, "work casual", "minimal classic", "all", 1799, {"stock": {"28": 0}}),
    ("chinos", "men", "Khaki slim chinos", "khaki", None, "solid", "cotton", "slim", "long", N, N, "work casual", "classic preppy", "all", 1799, {}),
    ("chinos", "men", "Navy chinos", "navy", None, "solid", "cotton", "regular", "long", N, N, "work", "classic preppy old_money", "all", 1999, {}),
    ("chinos", "men", "Cream linen trousers", "cream", None, "solid", "linen", "relaxed", "long", N, N, "beach wedding vacation", "resort old_money", "summer", 2499, {}),
    ("cargo_pants", "unisex", "Olive cargo pants", "olive", None, "solid", "cotton", "relaxed", "long", N, N, "casual travel", "streetwear", "all", 2299, {}),
    ("cargo_pants", "unisex", "Black parachute cargos", "black", None, "solid", "polyester", "wide", "long", N, N, "casual", "streetwear y2k", "all", 2499, {}),
    ("palazzo", "women", "Rust printed palazzo", "rust", "mustard", "print", "viscose", "wide", "long", N, N, "festive casual vacation", "ethnic boho", "all", 1299, {}),
    ("palazzo", "women", "Black flowy palazzo", "black", None, "solid", "polyester", "wide", "long", N, N, "work casual", "minimal", "all", 999, {}),
    ("skirt", "women", "Ivory pleated midi skirt", "ivory", None, "solid", "polyester", "a_line", "midi", N, N, "brunch work", "old_money romantic", "all", 1799, {}),
    ("skirt", "women", "Floral tiered maxi skirt", "mustard", "rust", "floral", "viscose", "flared", "maxi", N, N, "vacation beach", "boho resort", "summer", 1999, {}),
    ("skirt", "women", "Denim mini skirt", "denim_blue", None, "solid", "denim", "a_line", "mini", N, N, "casual", "y2k streetwear", "all", 1499, {}),
    ("shorts", "men", "Beige linen shorts", "beige", None, "solid", "linen", "regular", "regular", N, N, "beach vacation", "resort", "summer", 1299, {}),
    ("shorts", "women", "White denim shorts", "white", None, "solid", "denim", "regular", "mini", N, N, "beach vacation", "boho", "summer", 999, {}),
    # ---------------- one-pieces (no lehengas)
    ("dress", "women", "Sage linen midi dress", "sage", None, "solid", "linen", "a_line", "midi", "square", "short", "brunch vacation wedding beach", "resort old_money romantic", "summer", 3499, {}),
    ("dress", "women", "Black slip dress", "black", None, "solid", "polyester", "bodycon", "midi", "v_neck", "sleeveless", "party date", "minimal edgy", "all", 2499, {}),
    ("dress", "women", "Floral wrap dress", "blush", "rust", "floral", "viscose", "a_line", "midi", "v_neck", "short", "brunch date beach wedding", "romantic boho", "summer", 2799, {}),
    ("dress", "women", "White broderie sundress", "white", "ivory", "embroidered", "cotton", "a_line", "mini", "square", "sleeveless", "vacation beach", "boho resort", "summer", 2999, {}),
    ("dress", "women", "Emerald satin maxi dress", "emerald", None, "solid", "polyester", "flared", "maxi", "halter", "sleeveless", "wedding party", "formal romantic", "all", 4499, {}),
    ("jumpsuit", "women", "Olive utility jumpsuit", "olive", None, "solid", "cotton", "relaxed", "long", "collar", "short", "casual travel", "streetwear minimal", "all", 2999, {}),
    ("coord_set", "women", "Sand linen co-ord set", "sand", None, "solid", "linen", "relaxed", "long", "collar", "short", "vacation brunch beach", "resort old_money minimal", "summer", 3999, {}),
    ("coord_set", "women", "Lilac printed co-ord", "lavender", "purple", "print", "viscose", "relaxed", "long", "collar", "short", "brunch vacation", "boho", "summer", 3299, {}),
    ("kurta_set", "women", "Maroon embroidered kurta set", "maroon", "gold", "embroidered", "viscose", "straight", "long", "mandarin", "three_quarter", "festive wedding", "ethnic", "all", 3999, {}),
    ("kurta_set", "women", "Pastel pink anarkali set", "pink", "gold", "embroidered", "viscose", "flared", "long", "mandarin", "three_quarter", "festive wedding", "ethnic romantic", "all", 4499, {"stock": "all_zero"}),
    ("kurta_set", "men", "Ivory kurta pyjama set", "ivory", None, "solid", "cotton", "regular", "long", "mandarin", "long", "festive wedding", "ethnic classic", "all", 3299, {}),
    ("saree", "women", "Teal silk-blend saree", "teal", "gold", "embroidered", "silk", "regular", "long", "square", "short", "wedding festive", "ethnic formal", "all", 5999, {}),
    # ---------------- outerwear (no shrugs)
    ("blazer", "women", "Camel single-breasted blazer", "camel", None, "solid", "wool", "regular", "regular", "collar", "long", "work formal", "old_money classic formal", "winter", 4999, {}),
    ("blazer", "men", "Navy tailored blazer", "navy", None, "solid", "wool", "slim", "regular", "collar", "long", "work formal wedding", "formal classic old_money", "all", 5999, {}),
    ("blazer", "women", "Ivory linen blazer", "ivory", None, "solid", "linen", "relaxed", "regular", "collar", "long", "work brunch wedding", "old_money minimal resort", "summer", 4299, {}),
    ("denim_jacket", "unisex", "Classic blue denim jacket", "denim_blue", None, "solid", "denim", "regular", "regular", "collar", "long", "casual travel", "classic streetwear", "all", 2999, {}),
    ("bomber", "men", "Olive bomber jacket", "olive", "black", "solid", "polyester", "regular", "regular", "crew", "long", "casual", "streetwear", "winter", 3499, {}),
    ("bomber", "women", "Black satin bomber", "black", "maroon", "solid", "polyester", "oversized", "regular", "crew", "long", "party casual", "streetwear edgy y2k", "all", 3299, {}),
    ("nehru_jacket", "men", "Charcoal Nehru jacket", "charcoal", None, "solid", "wool", "slim", "regular", "mandarin", "sleeveless", "festive wedding", "ethnic formal", "all", 2999, {}),
    ("cardigan", "women", "Cream knit cardigan", "cream", None, "solid", "knit", "relaxed", "regular", "v_neck", "long", "work casual", "old_money minimal", "winter", 2299, {}),
    ("cardigan", "women", "Sage cropped cardigan", "sage", None, "solid", "knit", "slim", "cropped", "v_neck", "long", "brunch casual", "romantic", "all", 1999, {}),
    # ---------------- footwear (no stilettos, no kolhapuris, one pair of juttis)
    ("sneakers", "unisex", "White leather sneakers", "white", "grey", "solid", "leather", N, N, N, N, "casual travel", "minimal classic athleisure", "all", 3499, {}),
    ("sneakers", "unisex", "Chunky white trainers", "white", "grey", "solid", "leather", N, N, N, N, "casual", "streetwear athleisure y2k", "all", 4499, {}),
    ("sneakers", "men", "Black runner sneakers", "black", "white", "solid", "knit", N, N, N, N, "gym casual", "athleisure", "all", 2999, {}),
    ("loafers", "women", "Tan leather penny loafers", "tan", None, "solid", "leather", N, N, N, N, "work brunch", "old_money classic", "all", 3999, {}),
    ("loafers", "women", "Chocolate suede loafers", "brown", None, "solid", "suede", N, N, N, N, "work brunch", "old_money classic", "all", 4999, {}),
    ("loafers", "men", "Black horsebit loafers", "black", None, "solid", "leather", N, N, N, N, "work formal wedding", "old_money formal classic", "all", 4499, {}),
    ("loafers", "men", "Tan suede loafers", "tan", None, "solid", "suede", N, N, N, N, "brunch vacation wedding", "old_money resort", "all", 3999, {}),
    ("block_heels", "women", "Nude block heels", "beige", None, "solid", "leather", N, N, N, N, "work party wedding", "classic minimal", "all", 2799, {}),
    ("block_heels", "women", "Gold strappy block heels", "gold", None, "solid", "synthetic", N, N, N, N, "party wedding festive", "formal", "all", 2999, {}),
    ("flats", "women", "Black ballet flats", "black", None, "solid", "leather", N, N, N, N, "work casual", "classic minimal old_money", "all", 1799, {}),
    ("sandals", "women", "Tan strappy flat sandals", "tan", None, "solid", "leather", N, N, N, N, "vacation beach brunch", "boho resort minimal", "summer", 1499, {}),
    ("sandals", "men", "Brown leather slides", "brown", None, "solid", "leather", N, N, N, N, "beach vacation casual", "resort", "summer", 1799, {}),
    ("boots", "women", "Black chelsea boots", "black", None, "solid", "leather", N, N, N, N, "casual work", "edgy classic", "winter", 4999, {}),
    ("juttis", "women", "Gold embroidered juttis", "gold", "maroon", "embroidered", "synthetic", N, N, N, N, "festive wedding", "ethnic", "all", 1899, {"stock": {"6": 0}}),
    # ---------------- accessories
    ("tote", "women", "Tan canvas tote", "tan", None, "solid", "canvas", N, N, N, N, "work vacation brunch", "old_money minimal resort", "all", 1999, {}),
    ("tote", "women", "Black leather-look tote", "black", None, "solid", "synthetic", N, N, N, N, "work", "minimal classic", "all", 2499, {}),
    ("sling_bag", "unisex", "Black nylon sling bag", "black", None, "solid", "polyester", N, N, N, N, "casual travel", "streetwear athleisure", "all", 1299, {}),
    ("sling_bag", "women", "Tan crossbody bag", "tan", None, "solid", "leather", N, N, N, N, "brunch casual", "classic", "all", 2299, {}),
    ("clutch", "women", "Gold embellished clutch", "gold", "ivory", "embroidered", "synthetic", N, N, N, N, "wedding party festive", "ethnic formal", "all", 1799, {}),
    ("clutch", "women", "Black box clutch", "black", None, "solid", "synthetic", N, N, N, N, "party", "minimal formal", "all", 1499, {}),
    ("belt", "unisex", "Brown leather belt", "brown", None, "solid", "leather", N, N, N, N, "work casual", "classic old_money", "all", 999, {}),
    ("sunglasses", "unisex", "Tortoise cat-eye sunglasses", "brown", "tan", "print", "synthetic", N, N, N, N, "vacation beach", "old_money resort", "summer", 1499, {}),
    ("sunglasses", "unisex", "Black aviator sunglasses", "black", None, "solid", "metal", N, N, N, N, "casual travel", "classic streetwear", "all", 1799, {}),
    ("watch", "unisex", "Gold-tone slim watch", "gold", None, "solid", "metal", N, N, N, N, "work wedding", "old_money classic formal", "all", 3499, {}),
    ("watch", "men", "Black sports watch", "black", None, "solid", "synthetic", N, N, N, N, "gym casual", "athleisure", "all", 2499, {}),
    ("jewellery", "women", "Gold-tone jhumkas", "gold", None, "embroidered", "metal", N, N, N, N, "festive wedding", "ethnic", "all", 799, {}),
    ("jewellery", "women", "Pearl drop earrings", "ivory", None, "solid", "metal", N, N, N, N, "wedding work brunch", "old_money classic romantic", "all", 999, {}),
    ("scarf", "women", "Silk-feel printed scarf", "navy", "cream", "print", "polyester", N, N, N, N, "work brunch", "old_money classic", "all", 899, {}),
    ("dupatta", "women", "Gold zari dupatta", "gold", "maroon", "embroidered", "silk", N, N, N, N, "festive wedding", "ethnic", "all", 1299, {}),
    ("dupatta", "women", "Pink chiffon dupatta", "pink", None, "solid", "chiffon", N, N, N, N, "festive", "ethnic romantic", "all", 899, {}),
]


def round99(x: float) -> int:
    return int(round(x / 100.0)) * 100 - 1


def describe(p: dict) -> str:
    bits = [f"{p['name']} in {p['fabric']}."]
    if p["silhouette"] != "none":
        bits.append(f"{label(p['silhouette'])} fit" + (f", {p['length'].replace('_', ' ')} length." if p["length"] != "none" else "."))
    bits.append("Made for " + ", ".join(p["occasion_tags"][:3]) + ".")
    return " ".join(bits)


def build_catalog() -> dict:
    rng = random.Random(SEED)
    products, sizes, price_history, stock_events = [], [], [], []
    for i, row in enumerate(ITEMS, start=1):
        (sub, gender, name, color, color2, pattern, fabric, fit, length, neck, sleeve,
         occ, styles, season, price, extra) = row
        pid = f"ut-{i:03d}"
        cat = SUB_TO_CAT[sub]
        discount = rng.choice([0, 0, 0, 0.1, 0.2, 0.3])
        mrp = round99(price / (1 - discount)) if discount else price
        added = NOW - timedelta(days=rng.randint(5, 150), hours=rng.randint(0, 23))
        p = {
            "id": pid, "store_id": STORE["id"], "brand": STORE["brand"], "name": name, "category": cat,
            "subcategory": sub, "gender_fit": gender, "primary_color": color, "secondary_color": color2,
            "color_family": color_family(color), "pattern": pattern, "fabric": fabric, "silhouette": fit,
            "length": length, "neckline": neck, "sleeve": sleeve, "occasion_tags": occ.split(),
            "style_tags": styles.split(), "season": season, "price_inr": price, "mrp_inr": max(mrp, price),
            "image_url": f"/media/products/{pid}.svg", "added_at": added.isoformat(timespec="seconds"),
        }
        p["description"] = describe(p)
        if "price_drop_to" in extra:
            p["scheduled_price_drop_inr"] = extra["price_drop_to"]
        products.append(p)
        stock_override = extra.get("stock", {})
        for sz in size_system(cat, gender):
            roll = rng.random()
            qty = 0 if roll < 0.10 else (rng.randint(1, 3) if roll < 0.40 else rng.randint(4, 12))
            if len(size_system(cat, gender)) == 1:
                qty = max(qty, 3)  # one-size items are never accidentally sold out
            if stock_override == "all_zero":
                qty = 0
            elif isinstance(stock_override, dict) and sz in stock_override:
                qty = stock_override[sz]
            sizes.append({"product_id": pid, "size": sz, "stock": qty})
            stock_events.append({"product_id": pid, "size": sz, "delta": qty, "new_stock": qty,
                                 "kind": "initial", "at": added.isoformat(timespec="seconds")})
        price_history.append({"product_id": pid, "price_inr": price, "mrp_inr": p["mrp_inr"],
                              "changed_at": added.isoformat(timespec="seconds")})
    return {"store": STORE, "products": products, "product_sizes": sizes,
            "price_history": price_history, "stock_events": stock_events}


# Items the admin/demo panel can "launch" as new arrivals (not in the catalog at seed time).
NEW_ARRIVALS = [
    ("linen_shirt", "women", "Sky stripe linen shirt", "sky_blue", "white", "stripes", "linen", "relaxed", "regular", "collar", "long", "vacation brunch work", "old_money resort classic", "summer", 2299, {}),
    ("block_heels", "women", "Ivory kitten heels", "ivory", None, "solid", "leather", N, N, N, N, "work wedding brunch", "old_money classic", "all", 2599, {}),
    ("cargo_pants", "men", "Charcoal tech cargos", "charcoal", None, "solid", "polyester", "relaxed", "long", N, N, "casual travel", "streetwear athleisure", "all", 2699, {}),
]


def by_name(catalog: dict) -> dict[str, str]:
    return {p["name"]: p["id"] for p in catalog["products"]}


def build_personas(catalog: dict) -> dict:
    ids = by_name(catalog)
    women_budget = {"tops": [500, 2500], "bottoms": [800, 2500], "one_piece": [1500, 4000],
                    "outerwear": [2000, 4500], "footwear": [1000, 4000], "accessories": [300, 2500]}
    men_budget = {"tops": [600, 2500], "bottoms": [1000, 3000], "one_piece": [2000, 4000],
                  "outerwear": [2500, 5000], "footwear": [1500, 4500], "accessories": [500, 3000]}
    return {"personas": [
        {"id": "aanya", "name": "Aanya", "city": "Mumbai", "tagline": "Quiet luxury on a high-street budget",
         "preferences": {"budgets": women_budget, "sizes": {"tops": "M", "bottoms": "28", "footwear": "5"},
                         "fit": "relaxed", "preferred_materials": ["linen", "cotton", "silk"],
                         "avoid_materials": ["polyester"], "avoid_colors": ["orange"],
                         "occasions": ["work", "brunch", "vacation"], "gender_fit": "women"},
         "avatar": {"presentation": "women", "body_type": "hourglass", "height_band": "average", "skin_tone": 4,
                    "hair_style": "long", "hair_color": "black"},
         "folders": [{"name": "Festive edit", "description": "Diwali parties and a cousin's sangeet", "inspo": ["festive_ethnic"]}],
         "orders": [["White crew tee", "M"], ["Mid-blue straight jeans", "28"], ["Tan crossbody bag", "Free"], ["Black ballet flats", "5"]]},
        {"id": "kabir", "name": "Kabir", "city": "Delhi", "tagline": "Oversized everything",
         "preferences": {"budgets": men_budget, "sizes": {"tops": "L", "bottoms": "32", "footwear": "9"},
                         "fit": "oversized", "preferred_materials": ["cotton", "denim"], "avoid_materials": [],
                         "avoid_colors": ["pink", "lavender"], "occasions": ["casual", "travel"], "gender_fit": "men"},
         "avatar": {"presentation": "men", "body_type": "athletic", "height_band": "tall", "skin_tone": 5,
                    "hair_style": "short", "hair_color": "black"},
         "folders": [{"name": "Streetwear", "description": "Weekend fits", "inspo": ["street_men"]}],
         "orders": [["Black oversized graphic tee", "L"], ["White leather sneakers", "9"]]},
        {"id": "meera", "name": "Meera", "city": "Bengaluru", "tagline": "Wedding-season regular",
         "preferences": {"budgets": {**women_budget, "one_piece": [2500, 6000]}, "sizes": {"tops": "M", "bottoms": "30", "footwear": "6"},
                         "fit": "regular", "preferred_materials": ["silk", "cotton"], "avoid_materials": ["polyester"],
                         "avoid_colors": [], "occasions": ["festive", "wedding"], "gender_fit": "women"},
         "avatar": {"presentation": "women", "body_type": "pear", "height_band": "petite", "skin_tone": 6,
                    "hair_style": "bun", "hair_color": "black"},
         "folders": [{"name": "Sister's wedding", "description": "Mehendi, sangeet and the reception", "inspo": ["festive_ethnic"]}],
         "orders": [["Gold-tone jhumkas", "Free"]]},
        {"id": "rohan", "name": "Rohan", "city": "Pune", "tagline": "Boardroom to brunch",
         "preferences": {"budgets": men_budget, "sizes": {"tops": "M", "bottoms": "32", "footwear": "8"},
                         "fit": "slim", "preferred_materials": ["cotton", "wool", "linen"], "avoid_materials": ["polyester"],
                         "avoid_colors": [], "occasions": ["work", "formal"], "gender_fit": "men"},
         "avatar": {"presentation": "men", "body_type": "slim", "height_band": "average", "skin_tone": 3,
                    "hair_style": "short", "hair_color": "dark_brown"},
         "folders": [{"name": "Office", "description": "Monday to Friday", "inspo": []}],
         "orders": [["White oxford shirt", "M"], ["Navy chinos", "32"], ["Black horsebit loafers", "8"]]},
        {"id": "zoya", "name": "Zoya", "city": "Hyderabad", "tagline": "Boho, always packing for Goa",
         "preferences": {"budgets": women_budget, "sizes": {"tops": "S", "bottoms": "26", "footwear": "4"},
                         "fit": "relaxed", "preferred_materials": ["linen", "cotton", "viscose"], "avoid_materials": [],
                         "avoid_colors": ["black"], "occasions": ["vacation", "beach", "brunch"], "gender_fit": "women"},
         "avatar": {"presentation": "women", "body_type": "slim", "height_band": "average", "skin_tone": 7,
                    "hair_style": "curly", "hair_color": "brown"},
         "folders": [{"name": "Goa trip", "description": "Beach days and sundowners", "inspo": ["resort_linen"]}],
         "orders": [["Floral tiered maxi skirt", "26"]]},
    ], "product_ids": {k: v for k, v in ids.items()}}


def main() -> None:
    catalog = build_catalog()
    catalog["new_arrivals"] = [dict(zip(
        ["subcategory", "gender_fit", "name", "primary_color", "secondary_color", "pattern", "fabric", "silhouette",
         "length", "neckline", "sleeve", "occasion_tags", "style_tags", "season", "price_inr", "extra"], r))
        for r in NEW_ARRIVALS]
    for a in catalog["new_arrivals"]:
        a["occasion_tags"], a["style_tags"] = a["occasion_tags"].split(), a["style_tags"].split()
        a.pop("extra")
    (ROOT / "data/catalog.json").write_text(json.dumps(catalog, indent=1) + "\n")
    personas = build_personas(catalog)
    (ROOT / "data/personas.json").write_text(json.dumps(personas, indent=1) + "\n")
    print(f"catalog: {len(catalog['products'])} products, {len(catalog['product_sizes'])} size rows; "
          f"personas: {len(personas['personas'])}")


if __name__ == "__main__":
    main()
