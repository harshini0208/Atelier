"""Behaviour events: always written to the operational DB; mirrored to BigQuery `wiw.events` when enabled.

The retailer views are plain, portable SQL so the same text runs on SQLite (local) and BigQuery (cloud).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models as m
from .settings import get_settings

log = logging.getLogger("wiw.events")

EVENT_TYPES = {"piece_detected", "piece_selected", "piece_skipped", "match_viewed", "coverage_computed",
               "hanger_no_match", "add_to_look", "add_to_cart", "purchase", "alert_sent"}
COLUMNS = ["event_type", "user_id", "ts", "subcategory", "color", "fabric", "pattern", "style_tags", "product_id",
           "matched", "covered", "covered_in_prefs", "total", "value_inr", "synthetic"]
_pool = ThreadPoolExecutor(max_workers=2)


def emit(db: Session, event_type: str, user_id: str, **fields) -> m.Event:
    assert event_type in EVENT_TYPES, event_type
    if isinstance(fields.get("style_tags"), list):
        fields["style_tags"] = ",".join(fields["style_tags"])
    ev = m.Event(event_type=event_type, user_id=user_id, ts=fields.pop("ts", None) or datetime.utcnow(), **fields)
    db.add(ev)
    if get_settings().events_backend == "bigquery":
        row = {c: getattr(ev, c) for c in COLUMNS}
        row["ts"] = row["ts"].isoformat()
        row["synthetic"] = bool(row["synthetic"])
        _pool.submit(_stream, [row])
    return ev


def piece_fields(p) -> dict:  # noqa: ANN001  (DetectedPiece or dict)
    g = (lambda k: p.get(k)) if isinstance(p, dict) else (lambda k: getattr(p, k))
    return {"subcategory": g("subcategory"), "color": g("color"), "fabric": g("fabric"), "pattern": g("pattern"),
            "style_tags": g("style_tags") or []}


# ------------------------------------------------------------------ BigQuery

@lru_cache(maxsize=1)
def _bq():
    from google.cloud import bigquery

    from .gcp_auth import credentials

    s = get_settings()
    return bigquery.Client(project=s.project, credentials=credentials(), location=s.bq_location)


def bq_table() -> str:
    s = get_settings()
    return f"{s.project}.{s.bq_dataset}.events"


def _stream(rows: list[dict]) -> None:
    try:
        errors = _bq().insert_rows_json(bq_table(), rows)
        if errors:
            log.warning("bigquery insert errors: %s", errors)
    except Exception as e:  # noqa: BLE001
        log.warning("bigquery mirror failed: %s", e)


def bq_schema():
    from google.cloud import bigquery as bq

    S = bq.SchemaField
    return [S("event_type", "STRING", "REQUIRED"), S("user_id", "STRING"), S("ts", "TIMESTAMP"),
            S("subcategory", "STRING"), S("color", "STRING"), S("fabric", "STRING"), S("pattern", "STRING"),
            S("style_tags", "STRING"), S("product_id", "STRING"), S("matched", "INT64"), S("covered", "INT64"),
            S("covered_in_prefs", "INT64"), S("total", "INT64"), S("value_inr", "INT64"), S("synthetic", "BOOL")]


# Views: identical SQL for SQLite and BigQuery ({events} is substituted).
VIEWS = {
    "gap_report": """
        SELECT subcategory, fabric, color, COUNT(*) AS saves,
               SUM(CASE WHEN matched = 1 THEN 1 ELSE 0 END) AS saves_with_match,
               SUM(CASE WHEN matched = 1 THEN 0 ELSE 1 END) AS saves_without_match
        FROM {events} WHERE event_type = 'piece_selected'
        GROUP BY subcategory, fabric, color
        HAVING SUM(CASE WHEN matched = 1 THEN 0 ELSE 1 END) > 0
        ORDER BY saves_without_match DESC, saves DESC""",
    "top_saved_attributes": """
        SELECT 'subcategory' AS attribute, subcategory AS value, COUNT(*) AS saves FROM {events}
          WHERE event_type = 'piece_selected' GROUP BY subcategory
        UNION ALL
        SELECT 'color' AS attribute, color AS value, COUNT(*) AS saves FROM {events}
          WHERE event_type = 'piece_selected' GROUP BY color
        UNION ALL
        SELECT 'fabric' AS attribute, fabric AS value, COUNT(*) AS saves FROM {events}
          WHERE event_type = 'piece_selected' GROUP BY fabric
        UNION ALL
        SELECT 'pattern' AS attribute, pattern AS value, COUNT(*) AS saves FROM {events}
          WHERE event_type = 'piece_selected' GROUP BY pattern""",
    "coverage_summary": """
        SELECT COUNT(*) AS looks,
               SUM(covered) AS pieces_covered, SUM(covered_in_prefs) AS pieces_covered_in_prefs, SUM(total) AS pieces,
               SUM(CASE WHEN covered = total THEN 1 ELSE 0 END) AS fully_covered_looks,
               MIN(covered * 1.0 / total) AS min_coverage, MAX(covered * 1.0 / total) AS max_coverage
        FROM {events} WHERE event_type = 'coverage_computed' AND total > 0""",
    "inspo_to_cart_funnel": """
        SELECT 1 AS step_order, 'Inspo uploaded' AS step, COUNT(DISTINCT user_id) AS shoppers, COUNT(*) AS events
          FROM {events} WHERE event_type = 'piece_detected'
        UNION ALL SELECT 2, 'Pieces saved', COUNT(DISTINCT user_id), COUNT(*) FROM {events} WHERE event_type = 'piece_selected'
        UNION ALL SELECT 3, 'Matches viewed', COUNT(DISTINCT user_id), COUNT(*) FROM {events} WHERE event_type = 'match_viewed'
        UNION ALL SELECT 4, 'Added to look', COUNT(DISTINCT user_id), COUNT(*) FROM {events} WHERE event_type = 'add_to_look'
        UNION ALL SELECT 5, 'Added to cart', COUNT(DISTINCT user_id), COUNT(*) FROM {events} WHERE event_type = 'add_to_cart'
        UNION ALL SELECT 6, 'Purchased', COUNT(DISTINCT user_id), COUNT(*) FROM {events} WHERE event_type = 'purchase'
        ORDER BY step_order""",
}


def ensure_bigquery() -> None:
    """Create wiw.events and the four views (idempotent)."""
    from google.cloud import bigquery as bq

    client = _bq()
    s = get_settings()
    table = bq.Table(bq_table(), schema=bq_schema())
    table.time_partitioning = bq.TimePartitioning(field="ts")
    client.create_table(table, exists_ok=True)
    for name, sql in VIEWS.items():
        view = bq.Table(f"{s.project}.{s.bq_dataset}.{name}")
        view.view_query = sql.format(events=f"`{bq_table()}`")
        client.delete_table(view, not_found_ok=True)  # our own views only
        client.create_table(view)


def load_events_to_bigquery(rows: list[dict]) -> int:
    from google.cloud import bigquery as bq

    job = _bq().load_table_from_json(rows, bq_table(), job_config=bq.LoadJobConfig(
        schema=bq_schema(), write_disposition="WRITE_TRUNCATE"))
    job.result()
    return len(rows)


def query_view(db: Session, name: str) -> list[dict]:
    s = get_settings()
    if s.events_backend == "bigquery":
        try:
            rows = _bq().query(f"SELECT * FROM `{s.project}.{s.bq_dataset}.{name}`").result()
            return [dict(r.items()) for r in rows]
        except Exception as e:  # noqa: BLE001
            log.warning("bigquery view %s failed, using local: %s", name, e)
    res = db.execute(text(VIEWS[name].format(events="events")))
    return [dict(r._mapping) for r in res]
