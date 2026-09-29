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
    s.headers["X-User-Id"] = "rohan"
    ok = lambda r: (r.raise_for_status(), r.json())[1]  # noqa: E731
    t0 = time.time()
    h = ok(s.get(f"{base}/api/health", timeout=60))
    print("health", h)
    assert s.get(base, timeout=30).text.lower().count("<div id=\"root\">") == 1, "frontend not served"
    assert len(ok(s.get(f"{base}/api/personas"))) == 5
    f = ok(s.post(f"{base}/api/folders", json={"name": f"Smoke {int(time.time())}", "description": "smoke test"}))
    img = (ROOT / "demo/inspo/generated/street_men.png").read_bytes()
    t = time.time()
    inspo = ok(s.post(f"{base}/api/folders/{f['id']}/inspo", files={"file": ("street.png", img, "image/png")}, timeout=120))
    print(f"detect: {inspo['status']} via {inspo['source']} in {time.time() - t:.1f}s -> {[p['name'] for p in inspo['pieces']]}")
    assert inspo["pieces"], "no pieces detected"
    assert s.get(f"{base}{inspo['pieces'][0]['crop_url']}", timeout=30).status_code == 200
    sel = ok(s.post(f"{base}/api/inspo/{inspo['id']}/select", json={"piece_ids": [p["id"] for p in inspo["pieces"]]}))
    print("coverage:", sel["coverage"]["line"])
    folder = ok(s.get(f"{base}/api/folders/{f['id']}"))
    m = ok(s.get(f"{base}/api/hangers/{folder['hangers'][0]['id']}/matches"))
    print("matches:", len(m["for_you"]), "for you,", len(m["also_view"]), "also view")
    t = time.time()
    chat = ok(s.post(f"{base}/api/chat", json={"message": "Style this for a weekend brunch", "folder_id": f["id"]}, timeout=120))
    print(f"chat via {chat['payload'].get('source')} in {time.time() - t:.1f}s: {chat['content'][:120]}")
    r = ok(s.get(f"{base}/api/retailer", timeout=120))
    print("retailer gaps:", [(g["label"], g["unmatched"]) for g in r["gaps"][:3]], "| memo via", r["memo_source"])
    ok(s.delete(f"{base}/api/folders/{f['id']}"))
    print(f"SMOKE OK in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
