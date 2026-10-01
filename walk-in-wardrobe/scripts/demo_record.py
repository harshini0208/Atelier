"""Record the scripted demo against live Gemini so `GEMINI_MODE=replay` can run it with no network.

    make demo-record      # wipes cache/gemini, then records into it

Runs on a throwaway SQLite DB and media folder. The chat cache only hits in replay if the demo is performed the
same way (folder "Old-money summer" with description "Linen, loafers and long lunches", same picks, same messages).
Anything else falls back to the deterministic planner, which also works offline.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="wiw-record-"))
os.environ.update(GEMINI_MODE="live", DB_BACKEND="sqlite", STORAGE_BACKEND="local", EVENTS_BACKEND="local",
                  SEARCH_BACKEND="local", SQLITE_PATH=str(tmp / "rec.db"), MEDIA_DIR=str(tmp / "media"))
sys.path.insert(0, str(ROOT / "backend"))

FOLDER = {"name": "Old-money summer", "description": "Linen, loafers and long lunches"}
CHAT = ["Make it work for a beach wedding under ₹5,000", "Put it on my board", "Make it more casual",
        "Add the look to my cart"]


def main() -> None:
    cache = ROOT / "cache/gemini"
    if "--keep" not in sys.argv and cache.exists():
        shutil.rmtree(cache)
    from fastapi.testclient import TestClient

    from wiw.seed import seed_all
    seed_all()  # clean start: catalog only (seeding never calls live Gemini)
    from wiw.main import app

    c = TestClient(app)
    profile = {"name": "Demo Shopper", "city": "Mumbai", "gender_fit": "women", "fit": "relaxed",
               "sizes": {"tops": "M", "bottoms": "28", "footwear": "5"},
               "budgets": {"tops": [500, 2500], "bottoms": [800, 2500], "one_piece": [1500, 4000], "outerwear": [2000, 4500],
                           "footwear": [1000, 4000], "accessories": [300, 2500]},
               "preferred_materials": ["linen", "cotton"], "avoid_materials": ["polyester"], "avoid_colors": [], "occasions": ["work"]}
    H = {"X-User-Id": c.post("/api/profile", json=profile).json()["id"]}
    other = {"X-User-Id": c.post("/api/profile", json={**profile, "name": "Second Shopper"}).json()["id"]}
    step = lambda s: print(f"  - {s}", flush=True)  # noqa: E731
    # detections for every demo image (also used by persona folders)
    for name in ("old_money_summer", "resort_linen", "festive_ethnic", "street_men"):
        f = c.post("/api/folders", json={"name": f"tmp {name}"}, headers=other).json()
        c.post(f"/api/folders/{f['id']}/inspo", files={"file": (f"{name}.png", (ROOT / f"demo/inspo/generated/{name}.png").read_bytes(), "image/png")},
               headers=other)
        step(f"detect {name}")
    # the scripted demo, as performed in the UI
    f = c.post("/api/folders", json=FOLDER, headers=H).json()
    for name, pick in (("old_money_summer", {"linen_shirt", "chinos", "loafers"}), ("resort_linen", None)):
        r = c.post(f"/api/folders/{f['id']}/inspo", files={"file": (f"{name}.png", (ROOT / f"demo/inspo/generated/{name}.png").read_bytes(), "image/png")}, headers=H).json()
        for p in [p for p in r["pieces"] if pick is None or p["subcategory"] in pick]:
            m = c.get(f"/api/inspo/{r['id']}/pieces/{p['id']}/matches", headers=H).json()
            top = (m["for_you"] or m["also_view"] or [None])[0]
            c.post(f"/api/inspo/{r['id']}/pieces/{p['id']}/hang", json={"product_id": top["product"]["id"] if top else None}, headers=H)
    for msg in CHAT:
        r = c.post("/api/chat", json={"message": msg, "folder_id": f["id"]}, headers=H).json()
        step(f"chat [{r['payload'].get('source')}] {msg} -> {r['content'][:90]}")
    for body in ({}, {"formality": "more_casual"}, {"formality": "more_formal"}, {"formality": "more_festive"}):
        r = c.post(f"/api/folders/{f['id']}/style", json=body, headers=H).json()
        step(f"style {body} [{r.get('source')}]")
    step(f"taste [{c.get('/api/taste', headers=H).json()['source']}]")
    step(f"retailer memo [{c.get('/api/retailer').json()['memo_source']}]")
    n = sum(1 for _ in cache.rglob("*.json"))
    print(f"recorded {n} cache entries in {cache}")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
