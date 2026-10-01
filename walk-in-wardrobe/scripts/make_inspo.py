"""Generate illustrated outfit "screenshots" for the demo (never downloaded from Instagram or Pinterest).

    python scripts/make_inspo.py

Writes demo/inspo/generated/<name>.png and demo/inspo/generated/truth.json. The truth file holds the exact
pieces and boxes (Gemini box_2d convention: [ymin, xmin, ymax, xmax] on 0..1000) and is used as the
deterministic detection fallback for these images. Put your own screenshots directly in demo/inspo/.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from wiw.garments import Spec, garment_parts  # noqa: E402
from wiw.mannequin import H, W, Body, body_svg_parts, category_z, garment_placement_svg  # noqa: E402
from wiw.vocab import SUB_TO_CAT, label  # noqa: E402

OUT = ROOT / "demo/inspo/generated"
FIG_SCALE, FIG_DX, FIG_DY = 0.8, 54, 40  # figure placed inside the post area


def piece(sub, color, name, *, color2=None, pattern="solid", fabric="cotton", fit="regular", length="regular",
          neckline="none", sleeve="none", styles=(), occasions=(), gender="women"):
    return dict(subcategory=sub, category=SUB_TO_CAT[sub], name=name, color=color, secondary_color=color2,
                pattern=pattern, fabric=fabric, silhouette=fit, length=length, neckline=neckline, sleeve=sleeve,
                style_tags=list(styles), occasion_tags=list(occasions), gender_fit=gender)


LOOKS = {
    "old_money_summer": {
        "caption": "old money summer, linen + loafers", "handle": "@slowsundays.edit", "bg": ("#efe6d6", "#d9c8ad"),
        "body": ("women", "hourglass", "average", 3, "long", "brown"),
        "pieces": [
            piece("linen_shirt", "ivory", "Ivory linen shirt", fabric="linen", fit="relaxed", neckline="collar", sleeve="long",
                  styles=("old_money", "minimal"), occasions=("brunch", "vacation")),
            piece("chinos", "beige", "Beige slim chinos", fit="slim", length="ankle",
                  styles=("old_money", "classic"), occasions=("work", "brunch")),
            piece("loafers", "tan", "Tan leather loafers", fabric="leather", styles=("old_money", "classic"), occasions=("work", "brunch")),
            piece("tote", "tan", "Tan canvas tote", fabric="canvas", styles=("old_money", "minimal"), occasions=("vacation", "brunch")),
            piece("watch", "gold", "Gold watch", fabric="metal", styles=("old_money", "classic"), occasions=("work",), gender="unisex"),
        ]},
    "resort_linen": {
        "caption": "goa, but make it linen", "handle": "@saltwater.wardrobe", "bg": ("#e4eef0", "#c9dbe0"),
        "body": ("women", "slim", "average", 6, "bun", "black"),
        "pieces": [
            piece("shirt", "sky_blue", "Blue striped shirt", color2="white", pattern="stripes", fit="relaxed", neckline="collar", sleeve="long",
                  styles=("old_money", "resort", "preppy"), occasions=("vacation", "brunch")),
            piece("wide_leg_trousers", "sand", "Sand wide-leg linen trousers", fabric="linen", fit="wide", length="long",
                  styles=("resort", "old_money", "minimal"), occasions=("vacation", "beach")),
            piece("sandals", "tan", "Tan flat sandals", fabric="leather", styles=("resort", "boho"), occasions=("beach", "vacation")),
            piece("sunglasses", "brown", "Tortoiseshell sunglasses", color2="tan", pattern="print", fabric="synthetic",
                  styles=("resort", "old_money"), occasions=("beach", "vacation"), gender="unisex"),
        ]},
    "festive_ethnic": {
        "caption": "sangeet night, maroon + gold", "handle": "@shaadi.season.notes", "bg": ("#f3e3d3", "#e2c3a4"),
        "body": ("women", "pear", "average", 5, "long", "black"),
        "pieces": [
            piece("lehenga", "maroon", "Maroon embroidered lehenga", color2="gold", pattern="embroidered", fabric="silk", fit="flared",
                  length="maxi", neckline="square", sleeve="short", styles=("ethnic", "formal"), occasions=("wedding", "festive")),
            piece("dupatta", "gold", "Gold dupatta", color2="maroon", pattern="embroidered", fabric="silk", styles=("ethnic",), occasions=("wedding", "festive")),
            piece("juttis", "gold", "Gold embroidered juttis", color2="maroon", pattern="embroidered", fabric="synthetic",
                  styles=("ethnic",), occasions=("wedding", "festive")),
            piece("jewellery", "gold", "Gold jhumkas", pattern="embroidered", fabric="metal", styles=("ethnic",), occasions=("wedding", "festive")),
            piece("clutch", "gold", "Gold embellished clutch", color2="ivory", pattern="embroidered", fabric="synthetic",
                  styles=("ethnic", "formal"), occasions=("wedding", "festive")),
        ]},
    "street_men": {
        "caption": "sunday uniform", "handle": "@concrete.fits", "bg": ("#e6e6e3", "#c9c9c4"),
        "body": ("men", "athletic", "average", 7, "short", "black"),
        "pieces": [
            piece("hoodie", "black", "Black oversized hoodie", fit="oversized", neckline="hood", sleeve="long",
                  styles=("streetwear", "athleisure"), occasions=("casual",), gender="unisex"),
            piece("cargo_pants", "olive", "Olive cargo pants", fit="relaxed", length="long", styles=("streetwear",), occasions=("casual", "travel"), gender="unisex"),
            piece("sneakers", "white", "Chunky white sneakers", color2="grey", fabric="leather", styles=("streetwear", "athleisure"),
                  occasions=("casual",), gender="unisex"),
            piece("sling_bag", "black", "Black sling bag", fabric="polyester", styles=("streetwear",), occasions=("casual", "travel"), gender="unisex"),
        ]},
}

FIG = f'transform="translate({FIG_DX} {FIG_DY}) scale({FIG_SCALE})"'


def spec(p: dict) -> Spec:
    return Spec(subcategory=p["subcategory"], color=p["color"], color2=p["secondary_color"], pattern=p["pattern"],
                fit=p["silhouette"], length=p["length"], neckline=p["neckline"], sleeve=p["sleeve"], fabric=p["fabric"])


def chrome(look: dict) -> tuple[str, str]:
    bg1, bg2 = look["bg"]
    under = (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{bg1}"/>'
             f'<stop offset="1" stop-color="{bg2}"/></linearGradient></defs>'
             f'<rect width="{W}" height="{H}" fill="#ffffff"/><rect y="84" width="{W}" height="760" fill="url(#bg)"/>'
             f'<path d="M 90 844 L 90 300 Q 90 150 270 150 Q 450 150 450 300 L 450 844 Z" fill="#ffffff" opacity=".28"/>'
             f'<rect y="760" width="{W}" height="84" fill="#000" opacity=".05"/>')
    font = 'font-family="Helvetica, Arial, sans-serif"'
    over = (f'<text x="24" y="28" font-size="17" font-weight="700" {font} fill="#111">9:41</text>'
            f'<rect x="478" y="14" width="34" height="16" rx="4" fill="none" stroke="#111" stroke-width="2"/>'
            f'<rect x="481" y="17" width="24" height="10" rx="2" fill="#111"/>'
            f'<circle cx="40" cy="60" r="16" fill="{bg2}"/><circle cx="40" cy="60" r="16" fill="none" stroke="#d6336c" stroke-width="2.5"/>'
            f'<text x="66" y="66" font-size="16" font-weight="700" {font} fill="#111">{look["handle"]}</text>'
            f'<text x="470" y="66" font-size="16" {font} fill="#111">•••</text>'
            f'<path d="M 30 872 q 8 -12 16 0 q 8 -12 16 0 q 0 12 -16 22 q -16 -10 -16 -22 Z" fill="none" stroke="#111" stroke-width="2.4"/>'
            f'<circle cx="92" cy="880" r="11" fill="none" stroke="#111" stroke-width="2.4"/>'
            f'<path d="M 124 872 L 150 880 L 124 890 Z" fill="none" stroke="#111" stroke-width="2.4"/>'
            f'<path d="M 494 868 L 494 894 L 504 886 L 514 894 L 514 868 Z" fill="none" stroke="#111" stroke-width="2.4"/>'
            f'<text x="24" y="928" font-size="15" {font} fill="#111"><tspan font-weight="700">{look["handle"][1:]}</tspan> {look["caption"]}</text>')
    return under, over


def render(svg_inner: str, transparent: bool = False) -> Image.Image:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{svg_inner}</svg>'
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg))
    return Image.open(io.BytesIO(png)).convert("RGBA")


def build(name: str, look: dict) -> tuple[bytes, list[dict]]:
    pres, bt, hb, skin, hair, hair_c = look["body"]
    b = Body(pres, bt, hb)
    body, hair_front = body_svg_parts(b, skin, hair, hair_c)
    ordered = sorted(enumerate(look["pieces"]), key=lambda ip: category_z(ip[1]["subcategory"]))
    garments = {}
    for i, p in ordered:
        defs, inner = garment_parts(spec(p), uid=f"{name}-{i}")
        garments[i] = garment_placement_svg(b, p["subcategory"], defs, inner)
    under, over = chrome(look)
    full = under + f'<g {FIG}>{body}{"".join(garments[i] for i, _ in ordered)}{hair_front}</g>' + over
    img = render(full).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    truth = []
    for i, p in enumerate(look["pieces"]):
        bbox = render(f'<g {FIG}>{garments[i]}</g>').getchannel("A").getbbox()
        x0, y0, x1, y1 = bbox
        box = [round(y0 / H * 1000), round(x0 / W * 1000), round(y1 / H * 1000), round(x1 / W * 1000)]
        truth.append({**p, "box_2d": box, "confidence": 0.95})
    return buf.getvalue(), truth


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    for name, look in LOOKS.items():
        png, truth = build(name, look)
        (OUT / f"{name}.png").write_bytes(png)
        index[name] = {"sha256": hashlib.sha256(png).hexdigest(), "file": f"{name}.png", "pieces": truth}
        print(f"{name}: {len(truth)} pieces -> {', '.join(label(t['subcategory']) for t in truth)}")
    (OUT / "truth.json").write_text(json.dumps(index, indent=1) + "\n")


if __name__ == "__main__":
    main()
