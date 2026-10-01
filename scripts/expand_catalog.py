"""Grow the store catalog from product photos (women's high-street basics, knitwear, tailoring, denim...).

    python scripts/expand_catalog.py fetch      # download candidates in data/expand/candidates.json
    python scripts/expand_catalog.py tag        # Gemini vision: attributes in the catalog vocabulary (cached)
    python scripts/expand_catalog.py crop       # model shots: find the chin line so photos are cropped headless
    python scripts/expand_catalog.py sheet      # contact sheets of accepted products for review
    python scripts/expand_catalog.py build      # data/catalog_extra.json + data/product_images/<id>.jpg

Gemini only describes each photo (type, colour, fabric, fit, style, a plain name) and flags unusable ones.
IDs, prices, sizes and stock are assigned deterministically here. Images whose hash is listed in
data/expand/exclude.txt (after visual review) are skipped.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import requests
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from wiw.colors import color_family  # noqa: E402
from wiw.vocab import (ALL_SUBCATEGORIES, COLORS, FABRICS, LENGTHS, NECKLINES, OCCASIONS, PATTERNS,  # noqa: E402
                       SILHOUETTES, SLEEVES, STYLE_TAGS, SUB_TO_CAT, size_system)

WORK = ROOT / "data/expand"
DL = WORK / "dl"
FIRST_ID = 201
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*"}
BRANDS = re.compile(r"\b(uniqlo|zara|h\s*&\s*m|hm|mango|cos|asos|levi'?s?|nike|adidas|gucci|prada)\b", re.I)

# Indicative high-street price bands (INR) per subcategory.
PRICE = {"tshirt": (599, 1499), "shirt": (1299, 2999), "linen_shirt": (1499, 2999), "crop_top": (599, 1499),
         "blouse": (999, 2499), "kurta": (999, 2499), "hoodie": (1499, 2999), "sweater": (1499, 3999),
         "jeans": (1799, 3499), "wide_leg_trousers": (1499, 3499), "chinos": (1299, 2799), "cargo_pants": (1499, 2999),
         "palazzo": (999, 1999), "skirt": (999, 2799), "shorts": (799, 1799), "leggings": (599, 1299),
         "dress": (1499, 4499), "jumpsuit": (1999, 3999), "coord_set": (2499, 4999), "kurta_set": (2499, 4999),
         "saree": (2999, 6999), "lehenga": (4999, 9999), "blazer": (2999, 5999), "denim_jacket": (2499, 3999),
         "bomber": (2499, 4499), "shrug": (999, 1999), "nehru_jacket": (2499, 3999), "cardigan": (1499, 3499),
         "coat": (3999, 7999), "sneakers": (2499, 4999), "loafers": (2499, 4499), "block_heels": (1999, 3499),
         "stilettos": (2499, 3999), "flats": (1299, 2499), "sandals": (999, 2499), "boots": (3499, 5999),
         "juttis": (1299, 2499), "kolhapuris": (999, 1799), "tote": (1499, 3499), "sling_bag": (1299, 2999),
         "clutch": (999, 2499), "belt": (699, 1499), "sunglasses": (999, 2499), "watch": (1999, 4999),
         "jewellery": (499, 1499), "scarf": (599, 1499), "dupatta": (699, 1499)}


class CatalogTag(BaseModel):
    usable: bool = Field(description="One clearly visible clothing, footwear or accessory product suitable for a store listing")
    reject_reason: str = ""
    shows_person_face: bool = False
    visible_logo_or_text: bool = Field(description="Any brand logo, watermark or readable text on the item or image")
    womens_item: bool = True
    subcategory: Literal[tuple(ALL_SUBCATEGORIES)]  # type: ignore[valid-type]
    name: str = Field(max_length=60, description="Short plain shopping name, no brand, e.g. 'Cream ribbed knit cardigan'")
    primary_color: Literal[tuple(COLORS)]  # type: ignore[valid-type]
    secondary_color: Literal[tuple(COLORS)] | None = None  # type: ignore[valid-type]
    pattern: Literal[tuple(PATTERNS)] = "solid"  # type: ignore[valid-type]
    fabric: Literal[tuple(FABRICS)] = "cotton"  # type: ignore[valid-type]
    silhouette: Literal[tuple(SILHOUETTES)] = "regular"  # type: ignore[valid-type]
    length: Literal[tuple(LENGTHS)] = "none"  # type: ignore[valid-type]
    neckline: Literal[tuple(NECKLINES)] = "none"  # type: ignore[valid-type]
    sleeve: Literal[tuple(SLEEVES)] = "none"  # type: ignore[valid-type]
    style_tags: list[Literal[tuple(STYLE_TAGS)]] = Field(min_length=1, description="1 to 4 tags")  # type: ignore[valid-type]
    occasion_tags: list[Literal[tuple(OCCASIONS)]] = Field(min_length=1, description="1 to 4 tags")  # type: ignore[valid-type]
    season: Literal["summer", "winter", "monsoon", "all"] = "all"

    @field_validator("style_tags", "occasion_tags")
    @classmethod
    def _top4(cls, v: list) -> list:
        return list(dict.fromkeys(v))[:4]


PROMPT = """You are cataloguing product photos for a women's high-street fashion store.
Describe the single main product in this image using only the allowed values.
- usable=false if it is a collage, a lifestyle scene where the product is unclear, several different products,
  a drawing/mockup template, or the product is cut off.
- visible_logo_or_text=true if any brand logo, watermark, label text or slogan is readable.
- name: short plain shopping name (colour + material/detail + type), no brand names.
- For footwear, bags and jewellery use silhouette/length/neckline/sleeve = none.
- coat = trench, wool or long coat; cardigan = buttoned knit; sweater = pullover knit.
Describe only the product, never the person wearing it."""


def tag_one(path: Path):  # noqa: ANN201
    from wiw import gemini

    data = path.read_bytes()
    return gemini.generate_json("catalog_tag", version="tag-v1", parts=[gemini.Image(data, "image/png"), PROMPT],
                                schema=CatalogTag, temperature=0.1, fallback=lambda: None)


class FaceCrop(BaseModel):
    has_face: bool
    chin_y: float = Field(description="Vertical position of the bottom of the chin, as a fraction 0..1 of image height")


CROP_PROMPT = """This is a fashion product photo. If a person's face is visible, give chin_y: the vertical position
of the bottom of their chin as a fraction of the image height (0 = top, 1 = bottom). Otherwise has_face=false, chin_y=0.
Do not describe or identify the person."""


def crop() -> None:
    """Locate the chin in model shots so build() can crop the photo headless (face never shown)."""
    import os

    from wiw import gemini
    from wiw.settings import get_settings

    os.environ["GEMINI_MODE"] = "live"
    get_settings().gemini_mode = "live"
    tags = json.loads((WORK / "tags.json").read_text())
    path = WORK / "crops.json"
    crops = json.loads(path.read_text()) if path.exists() else {}
    todo = [k for k in accepted_keys() if tags[k]["shows_person_face"] and k not in crops]

    def run(k):  # noqa: ANN001, ANN202
        r = gemini.generate_json("face_crop", version="crop-v1", temperature=0.0, fallback=lambda: None, schema=FaceCrop,
                                 parts=[gemini.Image((DL / f"{k}.png").read_bytes(), "image/png"), CROP_PROMPT])
        return k, (r.value.model_dump() if r.value else None)

    with ThreadPoolExecutor(6) as ex:
        for k, c in ex.map(run, todo):
            if c:
                crops[k] = c
    path.write_text(json.dumps(crops, indent=1))
    print(f"crops {len(crops)} / faces {sum(tags[k]['shows_person_face'] for k in accepted_keys())}")


def photo(k: str) -> Image.Image:
    """The downloaded photo, cropped just below the chin when it shows a face."""
    img = Image.open(DL / f"{k}.png")
    c = json.loads((WORK / "crops.json").read_text()).get(k) if (WORK / "crops.json").exists() else None
    if c and c["has_face"] and 0 < c["chin_y"] < 0.6:
        img = img.crop((0, int(img.height * (c["chin_y"] + 0.015)), img.width, img.height))
    return img


def dhash(img: Image.Image) -> int:
    g = img.convert("L").resize((9, 8))
    px = list(g.getdata())
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def fetch() -> None:
    DL.mkdir(parents=True, exist_ok=True)
    cands = json.loads((WORK / "candidates.json").read_text())
    jobs = [(q, u) for q, v in cands.items() for u in v["urls"]]

    def get(job):  # noqa: ANN001, ANN202
        q, url = job
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        out = DL / f"{key}.png"
        if out.exists():
            return key, q, url, True
        try:
            r = requests.get(url, headers=UA, timeout=25)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content))
            im.load()
            if min(im.size) < 300:
                return key, q, url, False
            im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            im.thumbnail((1400, 1400))
            im.save(out)
            return key, q, url, True
        except Exception:  # noqa: BLE001
            return key, q, url, False

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(get, jobs))
    index, seen = {}, {}
    for key, q, url, ok in res:
        if not ok:
            continue
        h = dhash(Image.open(DL / f"{key}.png"))
        dup = next((k for k, hh in seen.items() if bin(h ^ hh).count("1") <= 6), None)
        if dup:
            continue
        seen[key] = h
        index[key] = {"query": q, "target": cands[q]["target"], "url": url}
    (WORK / "index.json").write_text(json.dumps(index, indent=1))
    print(f"downloaded {sum(r[3] for r in res)}/{len(jobs)}, unique {len(index)}")


def tag() -> None:
    import os

    os.environ["GEMINI_MODE"] = "live"
    from wiw.settings import get_settings

    get_settings().gemini_mode = "live"
    index = json.loads((WORK / "index.json").read_text())
    tags_path = WORK / "tags.json"
    tags = json.loads(tags_path.read_text()) if tags_path.exists() else {}
    todo = [k for k in index if tags.get(k) is None]

    def run(key):  # noqa: ANN001, ANN202
        r = tag_one(DL / f"{key}.png")
        return key, (r.value.model_dump() if r.value else None)

    with ThreadPoolExecutor(8) as ex:
        for key, t in ex.map(run, todo):
            tags[key] = t
    tags_path.write_text(json.dumps(tags, indent=1))
    ok = [k for k in index if accepted(index[k], tags.get(k))]
    print(f"tagged {len(tags)}, accepted {len(ok)}")


def accepted(meta: dict, t: dict | None) -> bool:
    if not t or not t["usable"] or t["visible_logo_or_text"] or not t["womens_item"]:
        return False
    if BRANDS.search(t["name"]):
        return False
    target = meta["target"]
    targets = target if isinstance(target, list) else [target]
    return SUB_TO_CAT[t["subcategory"]] in {SUB_TO_CAT[x] for x in targets}


def headless_ok(k: str, tags: dict, crops: dict) -> bool:
    """A photo showing a face is only used when it can be cropped below the chin."""
    c = crops.get(k)
    return not tags[k]["shows_person_face"] or bool(c and c["has_face"] and 0 < c["chin_y"] < 0.6)


def accepted_keys(final: bool = False) -> list[str]:
    index = json.loads((WORK / "index.json").read_text())
    tags = json.loads((WORK / "tags.json").read_text())
    crops = json.loads((WORK / "crops.json").read_text()) if (WORK / "crops.json").exists() else {}
    excl = set((WORK / "exclude.txt").read_text().split()) if (WORK / "exclude.txt").exists() else set()
    keys = [k for k in index if k not in excl and accepted(index[k], tags.get(k))
            and (not final or headless_ok(k, tags, crops))]
    order = list(SUB_TO_CAT)
    return sorted(keys, key=lambda k: (order.index(tags[k]["subcategory"]), tags[k]["name"], k))


def sheet() -> None:
    tags = json.loads((WORK / "tags.json").read_text())
    keys = accepted_keys(final=True)
    cell, cols, per = 180, 6, 36
    for n in range(0, len(keys), per):
        chunk = keys[n:n + per]
        rows = (len(chunk) + cols - 1) // cols
        s = Image.new("RGB", (cols * cell, rows * (cell + 30)), "white")
        d = ImageDraw.Draw(s)
        for i, k in enumerate(chunk):
            im = photo(k).convert("RGB")
            im.thumbnail((cell - 10, cell - 10))
            x, y = (i % cols) * cell, (i // cols) * (cell + 30)
            s.paste(im, (x + 5, y + 5))
            t = tags[k]
            d.text((x + 4, y + cell - 2), f"{k[:6]} {t['subcategory']}", fill="red")
            d.text((x + 4, y + cell + 12), t["name"][:30], fill="black")
        out = WORK / f"sheet_{n // per:02d}.png"
        s.save(out)
        print(out)
    print(f"{len(keys)} accepted")


def build() -> None:
    index = json.loads((WORK / "index.json").read_text())
    tags = json.loads((WORK / "tags.json").read_text())
    keys = accepted_keys(final=True)
    now = datetime(2026, 9, 30, 10, 0)
    products, sizes, history, events, names = [], [], [], [], set()
    photos = ROOT / "data/product_images"
    sources = []
    for i, k in enumerate(keys):
        t = tags[k]
        pid = f"ut-{FIRST_ID + i}"
        rng = random.Random(f"wiw-extra-{k}")
        lo, hi = PRICE[t["subcategory"]]
        price = int(round(rng.uniform(lo, hi) / 100.0)) * 100 - 1
        discount = rng.choice([0, 0, 0, 0.1, 0.2, 0.3])
        mrp = max(price, int(round(price / (1 - discount) / 100.0)) * 100 - 1) if discount else price
        name = t["name"].strip().rstrip(".")
        name = name[0].upper() + name[1:]
        base, n = name, 2
        alts = [f"{base} in {t['fabric']}"] if t["fabric"] not in base.lower() else []
        alts += [f"{tag.replace('_', ' ').capitalize()} {base[0].lower()}{base[1:]}" for tag in t["style_tags"]]
        for alt in alts:
            if name.lower() not in names:
                break
            name = alt
        while name.lower() in names:
            name, n = f"{base} {n}", n + 1
        names.add(name.lower())
        cat = SUB_TO_CAT[t["subcategory"]]
        added = now - timedelta(days=rng.randint(1, 120), hours=rng.randint(0, 23))
        gender = "women"
        p = {"id": pid, "store_id": "urban-thread", "brand": "Urban Thread", "name": name, "category": cat,
             "subcategory": t["subcategory"], "gender_fit": gender, "primary_color": t["primary_color"],
             "secondary_color": t["secondary_color"], "color_family": color_family(t["primary_color"]),
             "pattern": t["pattern"], "fabric": t["fabric"], "silhouette": t["silhouette"], "length": t["length"],
             "neckline": t["neckline"], "sleeve": t["sleeve"], "occasion_tags": t["occasion_tags"],
             "style_tags": t["style_tags"], "season": t["season"], "price_inr": price, "mrp_inr": mrp,
             "image_url": f"/media/products/{pid}.svg", "added_at": added.isoformat(timespec="seconds")}
        p["description"] = f"{name} in {t['fabric']}. Made for " + ", ".join(t["occasion_tags"][:3]) + "."
        products.append(p)
        for sz in size_system(cat, gender):
            roll = rng.random()
            qty = 0 if roll < 0.08 else (rng.randint(1, 3) if roll < 0.35 else rng.randint(4, 12))
            if len(size_system(cat, gender)) == 1:
                qty = max(qty, 3)
            sizes.append({"product_id": pid, "size": sz, "stock": qty})
            events.append({"product_id": pid, "size": sz, "delta": qty, "new_stock": qty, "kind": "initial",
                           "at": p["added_at"]})
        history.append({"product_id": pid, "price_inr": price, "mrp_inr": p["mrp_inr"], "changed_at": p["added_at"]})
        img = photo(k)
        for old in photos.glob(f"{pid}.*"):
            old.unlink()
        if img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 250:
            img.save(photos / f"{pid}.png", optimize=True)
        else:
            img.convert("RGB").save(photos / f"{pid}.jpg", quality=90)
        sources.append([pid, name, index[k]["url"], "web image search (expansion)"])
    (ROOT / "data/catalog_extra.json").write_text(json.dumps(
        {"products": products, "product_sizes": sizes, "price_history": history, "stock_events": events}, indent=1) + "\n")
    src = photos / "sources.csv"
    rows = [r for r in csv.reader(src.open())] if src.exists() else [["product_id", "name", "source_image_url", "added_by"]]
    rows = [r for r in rows if not (r[0].startswith("ut-") and int(r[0][3:]) >= FIRST_ID)] + sources
    with src.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    from collections import Counter
    print(f"built {len(products)} products: {dict(Counter(p['category'] for p in products))}")


if __name__ == "__main__":
    {"fetch": fetch, "tag": tag, "crop": crop, "sheet": sheet, "build": build}[sys.argv[1]]()
