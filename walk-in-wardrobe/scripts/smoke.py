"""API smoke test against a running server (local or Cloud Run).

    python scripts/smoke.py https://wiw-app-xxxx.run.app
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
    s = requests.Session()
    ok = lambda r: (r.raise_for_status(), r.json())[1]  # noqa: E731
    t0 = time.time()
    h = ok(s.get(f"{base}/api/health", timeout=60))
    print("health", h)
    assert s.get(base, timeout=30).text.lower().count("<div id=\"root\">") == 1, "frontend not served"
    assert s.get(f"{base}/api/me", timeout=30).status_code == 401  # fresh visitors have no profile
    uid = ok(s.post(f"{base}/api/profile", json={"name": "Smoke Test", "city": "Pune", "gender_fit": "men",
                                                 "sizes": {"tops": "L", "bottoms": "32", "footwear": "9"}}))["id"]
    s.headers["X-User-Id"] = uid
    shop = ok(s.get(f"{base}/api/shop?gender=men&category=tops"))
    print("shop:", shop["count"], "men's tops")
    f = ok(s.post(f"{base}/api/folders", json={"name": f"Smoke {int(time.time())}", "description": "smoke test"}))
    img = (ROOT / "demo/inspo/generated/street_men.png").read_bytes()
    t = time.time()
    inspo = ok(s.post(f"{base}/api/folders/{f['id']}/inspo", files={"file": ("street.png", img, "image/png")}, timeout=120))
    print(f"detect: {inspo['status']} via {inspo['source']} in {time.time() - t:.1f}s -> {[p['name'] for p in inspo['pieces']]}")
    assert inspo["pieces"], "no pieces detected"
    assert s.get(f"{base}{inspo['pieces'][0]['crop_url']}", timeout=30).status_code == 200
    piece = inspo["pieces"][0]
    m = ok(s.get(f"{base}/api/inspo/{inspo['id']}/pieces/{piece['id']}/matches"))
    print("matches:", len(m["for_you"]), "for you,", len(m["also_view"]), "also view")
    top = (m["for_you"] or m["also_view"] or m["closest"])[0]["product"]
    h = ok(s.post(f"{base}/api/inspo/{inspo['id']}/pieces/{piece['id']}/hang", json={"product_id": top["id"]}))
    assert h["chosen_product_id"] == top["id"]
    sel = ok(s.post(f"{base}/api/inspo/{inspo['id']}/select", json={"piece_ids": [piece["id"]]}))
    print("coverage:", sel["coverage"]["line"])
    look = ok(s.post(f"{base}/api/folders/{f['id']}/looks", json={"placements": [{"product_id": top["id"], "x": 20, "y": 10, "w": 40, "z": 10}]}))
    assert look["items"][0]["x"] == 20
    t = time.time()
    chat = ok(s.post(f"{base}/api/chat", json={"message": "Style this for a weekend brunch", "folder_id": f["id"]}, timeout=120))
    print(f"chat via {chat['payload'].get('source')} in {time.time() - t:.1f}s: {chat['content'][:120]}")
    r = s.get(f"{base}/api/retailer", timeout=120)
    print("brand insights without admin token:", r.status_code)
    ok(s.delete(f"{base}/api/me"))
    assert s.get(f"{base}/api/me", timeout=30).status_code == 401  # smoke shopper and all their data removed
    print(f"SMOKE OK in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
