"""Load the synthetic data into the cloud backends (idempotent; only touches wiw-* resources).

    make load-cloud

1. Cloud SQL `wiw` database: schema reset (ALL shopper data is deleted) + the store catalog; product images and
   photos into the GCS bucket; shopper uploads (inspo/, crops/) are deleted from the bucket.
2. BigQuery `wiw.events` table + views, loaded with the seeded events.
3. Vertex AI Search `wiw-catalog`: schema + full document import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(DB_BACKEND="cloudsql", STORAGE_BACKEND="gcs", EVENTS_BACKEND="local", SEARCH_BACKEND="local")
os.environ.setdefault("GEMINI_MODE", "replay")


def main() -> None:
    import subprocess

    from sqlalchemy import select

    from wiw import models as m
    from wiw.catalog_search import VertexIndex, to_document
    from wiw.db import session_scope
    from wiw.events import COLUMNS, ensure_bigquery, load_events_to_bigquery
    from wiw.seed import seed_all

    subprocess.run([sys.executable, str(ROOT / "data/generate.py")], check=True)
    print("1/3 Cloud SQL + GCS ...", flush=True)
    print("   ", seed_all())

    print("2/3 BigQuery ...", flush=True)
    ensure_bigquery()
    with session_scope() as db:
        rows = []
        for ev in db.scalars(select(m.Event)):
            r = {c: getattr(ev, c) for c in COLUMNS}
            r["ts"] = r["ts"].isoformat()
            r["synthetic"] = bool(r["synthetic"])
            rows.append(r)
        products = list(db.scalars(select(m.Product)))
        docs = [to_document(p) for p in products]
    print(f"    loaded {load_events_to_bigquery(rows)} events")

    print("3/3 Vertex AI Search ...", flush=True)
    idx = VertexIndex()
    idx.put_schema()
    idx.import_documents(docs)
    print(f"    imported {len(docs)} documents")


if __name__ == "__main__":
    main()
