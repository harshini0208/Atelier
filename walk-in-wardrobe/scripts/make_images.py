"""Render every catalog product as a transparent SVG flat-lay into media storage (products/<id>.svg).

    python scripts/make_images.py [--sheet out.png]   # optional contact sheet for eyeballing

`--photos` is reserved for a later upgrade to generated product photos; the app never depends on it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from wiw.garments import Spec, garment_parts, garment_svg  # noqa: E402


def spec_for(p: dict) -> Spec:
    return Spec(subcategory=p["subcategory"], color=p["primary_color"], color2=p.get("secondary_color"),
                pattern=p["pattern"], fit=p["silhouette"], length=p["length"], neckline=p["neckline"],
                sleeve=p["sleeve"], fabric=p["fabric"])


def product_svg(p: dict) -> str:
    return garment_svg(spec_for(p), uid=p["id"])


def contact_sheet(products: list[dict], out: Path) -> None:
    import resvg_py

    cols, cell = 10, 150
    rows = (len(products) + cols - 1) // cols
    parts = []
    for i, p in enumerate(products):
        x, y = (i % cols) * cell, (i // cols) * cell
        defs, body = garment_parts(spec_for(p), uid=p["id"])
        parts.append(f'<g transform="translate({x + 5} {y + 5}) scale({(cell - 30) / 200})"><defs>{defs}</defs>{body}</g>'
                     f'<text x="{x + 4}" y="{y + cell - 8}" font-size="9" font-family="Helvetica">{p["name"][:26]}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{cols * cell}" height="{rows * cell}">'
           f'<rect width="100%" height="100%" fill="#f4f1ec"/>{"".join(parts)}</svg>')
    out.write_bytes(bytes(resvg_py.svg_to_bytes(svg_string=svg)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--photos", action="store_true", help="reserved: upgrade to generated photos (not implemented)")
    args = ap.parse_args()
    catalog = json.loads((ROOT / "data/catalog.json").read_text())
    from wiw.storage import storage

    st = storage()
    for p in catalog["products"]:
        st.put(f"products/{p['id']}.svg", product_svg(p).encode(), "image/svg+xml")
    print(f"wrote {len(catalog['products'])} product images")
    if args.sheet:
        contact_sheet(catalog["products"], args.sheet)
        print(f"contact sheet: {args.sheet}")


if __name__ == "__main__":
    main()
