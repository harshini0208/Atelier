"""Candidate retrieval behind a `CatalogSearch` interface.

- VertexCatalogSearch: Vertex AI Search (Discovery Engine) structured data store `wiw-catalog`, queried through
  the `wiw-search` app with category + gender filters. Retrieval only; ranking is the deterministic scorer.
- LocalCatalogSearch: in-memory attribute/keyword retrieval over the database, used locally and as fallback.

Stock is always re-checked from the database by the scorer, so a slightly stale search index is harmless.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .settings import get_settings
from .vocab import label

log = logging.getLogger("wiw.search")


def allowed_genders(gender_pref: str) -> list[str]:
    return ["women", "men", "unisex"] if gender_pref in ("any", "", None) else [gender_pref, "unisex"]


class CatalogSearch(Protocol):
    name: str

    def candidates(self, db: Session, *, category: str, subcategory: str, gender: str, query: str,
                   limit: int = 60) -> list[str]: ...


class LocalCatalogSearch:
    name = "local"

    def candidates(self, db: Session, *, category: str, subcategory: str, gender: str, query: str,
                   limit: int = 60) -> list[str]:
        rows = db.execute(select(m.Product.id, m.Product.subcategory, m.Product.name, m.Product.description)
                          .where(m.Product.category == category, m.Product.active.is_(True),
                                 m.Product.gender_fit.in_(allowed_genders(gender)))).all()
        terms = {t for t in query.lower().replace(",", " ").split() if len(t) > 2}

        def kw(r) -> tuple[int, int]:  # noqa: ANN001
            text = f"{r.name} {r.description}".lower()
            return (r.subcategory == subcategory, sum(t in text for t in terms))

        rows.sort(key=kw, reverse=True)
        return [r.id for r in rows[:limit]]


class VertexCatalogSearch:
    name = "vertex"

    def __init__(self) -> None:
        from google.auth.transport.requests import AuthorizedSession

        from .gcp_auth import credentials

        s = get_settings()
        self.session = AuthorizedSession(credentials())
        loc = s.search["location"]
        host = "discoveryengine.googleapis.com" if loc == "global" else f"{loc}-discoveryengine.googleapis.com"
        self.url = (f"https://{host}/v1/projects/{s.project}/locations/{loc}/collections/default_collection/"
                    f"engines/{s.search['engine']}/servingConfigs/default_search:search")
        self.local = LocalCatalogSearch()
        self.min_candidates = s.matching["retrieval"]["min_candidates"]

    def candidates(self, db: Session, *, category: str, subcategory: str, gender: str, query: str,
                   limit: int = 60) -> list[str]:
        genders = ",".join(f'"{g}"' for g in allowed_genders(gender))
        body = {"query": query, "pageSize": min(limit, 50),
                "filter": f'category: ANY("{category}") AND gender_fit: ANY({genders})'}
        ids: list[str] = []
        try:
            r = self.session.post(self.url, json=body, timeout=8)
            r.raise_for_status()
            ids = [res["document"]["id"] for res in r.json().get("results", [])]
        except Exception as e:  # noqa: BLE001
            log.warning("vertex search failed, using local retrieval: %s", e)
        if len(ids) < self.min_candidates:
            for pid in self.local.candidates(db, category=category, subcategory=subcategory, gender=gender,
                                             query=query, limit=limit):
                if pid not in ids:
                    ids.append(pid)
        return ids[:limit]


def query_text(attrs: dict) -> str:
    parts = [attrs.get("color", ""), label(attrs.get("subcategory", "")), attrs.get("fabric", ""),
             attrs.get("pattern", "") if attrs.get("pattern") != "solid" else "", " ".join(attrs.get("style_tags", []))]
    return " ".join(p.replace("_", " ") for p in parts if p).strip()


@lru_cache(maxsize=1)
def catalog_search() -> CatalogSearch:
    if get_settings().search_backend == "vertex":
        try:
            return VertexCatalogSearch()
        except Exception as e:  # noqa: BLE001
            log.warning("vertex search unavailable (%s); using local", e)
    return LocalCatalogSearch()


# ------------------------------------------------------------------ index management (used by loaders)

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "name": {"type": "string", "searchable": True, "retrievable": True},
        "description": {"type": "string", "searchable": True, "retrievable": True},
        **{f: {"type": "string", "searchable": True, "retrievable": True}
           for f in ("category_label", "subcategory_label", "silhouette_label")},
        **{f: {"type": "string", "indexable": True, "searchable": True, "retrievable": True}
           for f in ("category", "subcategory", "gender_fit", "primary_color", "color_family", "pattern", "fabric",
                     "silhouette", "store_id")},
        "style_tags": {"type": "array", "items": {"type": "string", "indexable": True, "searchable": True, "retrievable": True}},
        "occasion_tags": {"type": "array", "items": {"type": "string", "indexable": True, "searchable": True, "retrievable": True}},
        "price_inr": {"type": "number", "indexable": True, "retrievable": True},
    },
}


def to_document(p: m.Product | dict) -> dict:
    g = (lambda k: p[k]) if isinstance(p, dict) else (lambda k: getattr(p, k))
    data = {k: g(k) for k in ("name", "description", "category", "subcategory", "gender_fit", "primary_color",
                              "color_family", "pattern", "fabric", "silhouette", "store_id", "style_tags",
                              "occasion_tags", "price_inr")}
    for k in ("subcategory", "category", "silhouette"):
        data[k + "_label"] = label(data[k])
    return {"id": g("id"), "structData": data}


class VertexIndex:
    def __init__(self) -> None:
        from google.auth.transport.requests import AuthorizedSession

        from .gcp_auth import credentials

        s = get_settings()
        self.session = AuthorizedSession(credentials())
        loc = s.search["location"]
        host = "discoveryengine.googleapis.com" if loc == "global" else f"{loc}-discoveryengine.googleapis.com"
        self.host = host
        self.base = (f"https://{host}/v1/projects/{s.project}/locations/{loc}/collections/default_collection/"
                     f"dataStores/{s.search['datastore']}")

    def _wait(self, op: dict) -> dict:
        import time

        for _ in range(120):
            if op.get("done"):
                if "error" in op:
                    raise RuntimeError(op["error"])
                return op
            time.sleep(5)
            op = self.session.get(f"https://{self.host}/v1/{op['name']}", timeout=30).json()
        raise TimeoutError(op.get("name"))

    def put_schema(self) -> None:
        import json as _json

        r = self.session.patch(f"{self.base}/schemas/default_schema",
                               json={"jsonSchema": _json.dumps(SCHEMA)}, timeout=60)
        r.raise_for_status()
        self._wait(r.json())

    def import_documents(self, docs: list[dict]) -> dict:
        r = self.session.post(f"{self.base}/branches/default_branch/documents:import", timeout=120, json={
            "inlineSource": {"documents": docs}, "reconciliationMode": "INCREMENTAL"})
        r.raise_for_status()
        return self._wait(r.json())

    def upsert(self, doc: dict) -> None:
        r = self.session.patch(f"{self.base}/branches/default_branch/documents/{doc['id']}?allowMissing=true",
                               json=doc, timeout=30)
        r.raise_for_status()
