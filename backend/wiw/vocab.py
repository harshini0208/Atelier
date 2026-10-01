"""Controlled attribute vocabulary shared by the catalog generator, Gemini schemas and the matcher."""
from __future__ import annotations

SUBCATEGORIES: dict[str, list[str]] = {
    "tops": ["tshirt", "shirt", "linen_shirt", "crop_top", "blouse", "kurta", "hoodie", "sweater"],
    "bottoms": ["jeans", "wide_leg_trousers", "chinos", "cargo_pants", "palazzo", "skirt", "shorts", "leggings"],
    "one_piece": ["dress", "jumpsuit", "coord_set", "kurta_set", "saree", "lehenga"],
    "outerwear": ["blazer", "denim_jacket", "bomber", "shrug", "nehru_jacket", "cardigan", "coat"],
    "footwear": ["sneakers", "loafers", "block_heels", "stilettos", "flats", "sandals", "boots", "juttis", "kolhapuris"],
    "accessories": ["tote", "sling_bag", "clutch", "belt", "sunglasses", "watch", "jewellery", "scarf", "dupatta"],
}
CATEGORIES = list(SUBCATEGORIES)
SUB_TO_CAT = {s: c for c, subs in SUBCATEGORIES.items() for s in subs}
ALL_SUBCATEGORIES = list(SUB_TO_CAT)

LABELS = {
    "tshirt": "T-shirt", "linen_shirt": "Linen shirt", "crop_top": "Crop top", "wide_leg_trousers": "Wide-leg trousers",
    "cargo_pants": "Cargo pants", "coord_set": "Co-ord set", "kurta_set": "Kurta set", "denim_jacket": "Denim jacket",
    "nehru_jacket": "Nehru jacket", "block_heels": "Block heels", "sling_bag": "Sling bag", "one_piece": "One-pieces",
    "juttis": "Juttis / mojaris",
}


def label(key: str) -> str:
    return LABELS.get(key, key.replace("_", " ").capitalize())


# Mannequin slot per subcategory (drives drag-and-drop targets and z-order).
SLOT_BY_CATEGORY = {"tops": "torso", "bottoms": "legs", "one_piece": "full", "outerwear": "outer", "footwear": "feet"}
ACCESSORY_SLOTS = {
    "tote": "hand", "sling_bag": "hand", "clutch": "hand", "belt": "waist", "sunglasses": "head",
    "watch": "wrist", "jewellery": "ears", "scarf": "neck", "dupatta": "neck",
}


def slot_for(subcategory: str) -> str:
    cat = SUB_TO_CAT[subcategory]
    return ACCESSORY_SLOTS[subcategory] if cat == "accessories" else SLOT_BY_CATEGORY[cat]


GENDER_FITS = ["women", "men", "unisex"]

# Named palette -> (hex, family). Colour distance is computed in CIELAB from these hex values.
PALETTE: dict[str, tuple[str, str]] = {
    "white": ("#F7F7F4", "neutral"), "ivory": ("#F3EBDD", "neutral"), "cream": ("#EADFC8", "neutral"),
    "beige": ("#D8C3A5", "earth"), "sand": ("#CDB894", "earth"), "khaki": ("#B5A27A", "earth"),
    "camel": ("#B8864B", "earth"), "tan": ("#C19A6B", "earth"), "brown": ("#6F4E37", "earth"),
    "black": ("#1E1E1E", "neutral"), "charcoal": ("#3A3D42", "neutral"), "grey": ("#9A9A9A", "neutral"),
    "navy": ("#1F2A44", "blue"), "blue": ("#2F5DA8", "blue"), "sky_blue": ("#A9C8E8", "blue"),
    "denim_blue": ("#4A6A8F", "blue"), "teal": ("#1F6F78", "blue"),
    "olive": ("#6B6B3A", "green"), "sage": ("#A8B89A", "green"), "green": ("#3E7D4F", "green"),
    "emerald": ("#0F6B4C", "green"), "mustard": ("#D4A017", "warm"), "yellow": ("#F2D35B", "warm"),
    "orange": ("#E07B39", "warm"), "rust": ("#B7472A", "warm"), "red": ("#B3262E", "warm"),
    "maroon": ("#6D1F2B", "warm"), "pink": ("#E58FA8", "pink"), "blush": ("#EFC3C3", "pink"),
    "lavender": ("#B9A7D6", "purple"), "purple": ("#6B4C9A", "purple"),
    "gold": ("#C9A34E", "metallic"), "silver": ("#B8BCC2", "metallic"),
}
COLORS = list(PALETTE)

PATTERNS = ["solid", "stripes", "checks", "floral", "polka", "print", "embroidered"]
FABRICS = ["cotton", "linen", "denim", "polyester", "viscose", "silk", "wool", "knit", "leather", "suede",
           "canvas", "chiffon", "synthetic", "metal"]
SILHOUETTES = ["slim", "regular", "relaxed", "oversized", "straight", "wide", "tapered", "a_line", "flared", "bodycon", "none"]
LENGTHS = ["cropped", "regular", "long", "ankle", "mini", "midi", "maxi", "none"]
NECKLINES = ["crew", "v_neck", "collar", "mandarin", "square", "halter", "hood", "none"]
SLEEVES = ["sleeveless", "short", "three_quarter", "long", "none"]
OCCASIONS = ["casual", "work", "formal", "party", "wedding", "festive", "vacation", "beach", "date", "brunch", "travel", "gym"]
STYLE_TAGS = ["formal", "ethnic", "streetwear", "minimal", "boho", "old_money", "athleisure", "classic", "preppy",
              "edgy", "romantic", "resort", "y2k"]
SEASONS = ["summer", "winter", "monsoon", "all"]

# Sizes per category and gender fit.
SIZE_SYSTEMS = {
    ("apparel", "women"): ["XS", "S", "M", "L", "XL"],
    ("apparel", "men"): ["S", "M", "L", "XL", "XXL"],
    ("apparel", "unisex"): ["XS", "S", "M", "L", "XL", "XXL"],
    ("bottoms", "women"): ["26", "28", "30", "32", "34"],
    ("bottoms", "men"): ["28", "30", "32", "34", "36"],
    ("bottoms", "unisex"): ["26", "28", "30", "32", "34", "36"],
    ("footwear", "women"): ["3", "4", "5", "6", "7", "8"],
    ("footwear", "men"): ["6", "7", "8", "9", "10", "11"],
    ("footwear", "unisex"): ["4", "5", "6", "7", "8", "9", "10"],
    ("accessories", "women"): ["Free"], ("accessories", "men"): ["Free"], ("accessories", "unisex"): ["Free"],
}


def size_group(category: str) -> str:
    """Which of the user's sizes applies: tops | bottoms | footwear | free."""
    return {"bottoms": "bottoms", "footwear": "footwear", "accessories": "free"}.get(category, "tops")


def size_system(category: str, gender_fit: str) -> list[str]:
    key = {"bottoms": "bottoms", "footwear": "footwear", "accessories": "accessories"}.get(category, "apparel")
    return SIZE_SYSTEMS[(key, gender_fit)]


# Delivery estimate from the store warehouse (Mumbai), in days.
DELIVERY_DAYS = {"Mumbai": 2, "Pune": 2, "Bengaluru": 3, "Delhi": 3, "Hyderabad": 3, "Chennai": 3,
                 "Ahmedabad": 3, "Kolkata": 4, "Jaipur": 4}
DEFAULT_DELIVERY_DAYS = 5
CITIES = list(DELIVERY_DAYS)
