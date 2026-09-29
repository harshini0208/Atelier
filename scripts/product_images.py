"""Product photos for the store catalog (backend only).

    make product-manifest   # data/product_images/manifest.csv: which file name belongs to which product
    make product-images     # publish data/product_images/<product_id>.jpg|png|webp and use them in the app

Runs against whichever backend the environment selects (local by default; `make product-images-cloud` for Cloud).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    from wiw.db import session_scope
    from wiw.product_images import PHOTO_DIR, apply_photos, write_manifest
    from wiw.seed import ensure_schema

    ensure_schema()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "apply"
    with session_scope() as db:
        if cmd == "manifest":
            print(f"wrote {write_manifest(db)}")
        else:
            n = apply_photos(db)
            print(f"{n} product photo(s) published from {PHOTO_DIR}")
            if cmd == "apply" and n:
                _reindex()


def _reindex() -> None:
    import os

    if os.getenv("SEARCH_BACKEND") != "vertex":
        return
    from sqlalchemy import select

    from wiw import models as m
    from wiw.catalog_search import VertexIndex, to_document
    from wiw.db import session_scope

    with session_scope() as db:
        VertexIndex().import_documents([to_document(p) for p in db.scalars(select(m.Product))])


if __name__ == "__main__":
    main()
