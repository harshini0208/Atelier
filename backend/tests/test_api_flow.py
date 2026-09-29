"""End-to-end API flow on a freshly seeded temp database (GEMINI_MODE=off, local backends)."""
import io
import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)

from wiw.settings import ROOT  # noqa: E402

H = {"X-User-Id": "aanya"}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from wiw.seed import seed_all
    seed_all()
    from wiw.main import app
    with TestClient(app) as c:
        yield c


def upload(client, folder_id, name, headers=H):
    data = (ROOT / "demo/inspo/generated" / f"{name}.png").read_bytes()
    r = client.post(f"/api/folders/{folder_id}/inspo", files={"file": (f"{name}.png", data, "image/png")}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_personas_and_me(client):
    assert {p["id"] for p in client.get("/api/personas").json()} == {"aanya", "kabir", "meera", "rohan", "zoya"}
    me = client.get("/api/me", headers=H).json()
    assert me["preferences"]["sizes"]["tops"] == "M"
    assert client.get("/api/me", headers={"X-User-Id": "nobody"}).status_code == 401


def test_preferences_validation(client):
    prefs = client.get("/api/preferences", headers=H).json()
    bad = {**prefs, "avoid_materials": ["linen"], "preferred_materials": ["linen"]}
    assert client.put("/api/preferences", json=bad, headers=H).status_code == 422
    assert client.put("/api/preferences", json={**prefs, "avoid_colors": ["octarine"]}, headers=H).status_code == 422
    ok = client.put("/api/preferences", json=prefs, headers=H)
    assert ok.status_code == 200


def test_full_inspo_to_matches_flow(client):
    folder = client.post("/api/folders", json={"name": "Old-money summer", "description": "linen"}, headers=H).json()
    inspo = upload(client, folder["id"], "old_money_summer")
    assert inspo["status"] == "analyzed" and len(inspo["pieces"]) == 5
    assert all(p["crop_url"] for p in inspo["pieces"])
    assert client.get(inspo["pieces"][0]["crop_url"]).status_code == 200
    pick = [p["id"] for p in inspo["pieces"] if p["subcategory"] in ("linen_shirt", "chinos", "loafers")]
    sel = client.post(f"/api/inspo/{inspo['id']}/select", json={"piece_ids": pick}, headers=H).json()
    assert len(sel["created"]) == 3
    assert sel["coverage"]["covered"] == 3 and sel["coverage"]["total"] == 3
    # selecting again is idempotent
    again = client.post(f"/api/inspo/{inspo['id']}/select", json={"piece_ids": pick}, headers=H).json()
    assert again["created"] == []

    detail = client.get(f"/api/folders/{folder['id']}", headers=H).json()
    shirt = next(h for h in detail["hangers"] if h["piece"]["subcategory"] == "linen_shirt")
    m = client.get(f"/api/hangers/{shirt['id']}/matches", headers=H).json()
    assert m["for_you"][0]["product"]["name"] == "Ivory linen relaxed shirt"
    reasons = {r["label"] for i in m["also_view"] for r in i["reasons"]}
    assert {"Your size M is sold out", "₹799 over budget", "Polyester"} <= reasons
    # products are only ever real catalog rows
    for item in m["for_you"] + m["also_view"]:
        assert client.get(f"/api/products/{item['product']['id']}", headers=H).status_code == 200

    chosen = client.post(f"/api/hangers/{shirt['id']}/choose", json={"product_id": m["for_you"][0]["product"]["id"]},
                         headers=H).json()
    assert chosen["chosen_size"] == "M"

    # second inspo with a piece the store does not stock
    inspo2 = upload(client, folder["id"], "resort_linen")
    client.post(f"/api/inspo/{inspo2['id']}/select", json={"piece_ids": [p["id"] for p in inspo2["pieces"]]}, headers=H)
    detail = client.get(f"/api/folders/{folder['id']}", headers=H).json()
    wide = next(h for h in detail["hangers"] if h["piece"]["subcategory"] == "wide_leg_trousers")
    m2 = client.get(f"/api/hangers/{wide['id']}/matches", headers=H).json()
    assert m2["for_you"] == [] and m2["also_view"] == [] and m2["closest"]
    assert "closest from this store" in m2["gap_message"]
    assert m2["coverage"]["line"].startswith("This store covers 3 of 4 pieces")


def test_manual_piece_and_bad_uploads(client):
    folder = client.post("/api/folders", json={"name": "Misc"}, headers=H).json()
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (500, 500), "white").save(buf, "PNG")
    r = client.post(f"/api/folders/{folder['id']}/inspo", files={"file": ("x.png", buf.getvalue(), "image/png")}, headers=H).json()
    assert r["status"] in ("no_outfit", "no_apparel") and r["pieces"] == [] and r["message"]
    added = client.post(f"/api/inspo/{r['id']}/pieces", json={"subcategory": "blazer", "color": "camel", "point": [300, 500]},
                        headers=H).json()
    assert added["status"] == "analyzed" and added["pieces"][0]["manual"]
    bad = client.post(f"/api/folders/{folder['id']}/inspo", files={"file": ("x.txt", b"not an image", "text/plain")}, headers=H)
    assert bad.status_code == 415


def test_folders_are_private(client):
    kabir = {"X-User-Id": "kabir"}
    mine = client.get("/api/folders", headers=H).json()[0]
    assert client.get(f"/api/folders/{mine['id']}", headers=kabir).status_code == 404


def test_move_hanger(client):
    folders = client.get("/api/folders", headers=H).json()
    src = client.get(f"/api/folders/{folders[0]['id']}", headers=H).json()
    h = src["hangers"][0]
    moved = client.patch(f"/api/hangers/{h['id']}", json={"folder_id": folders[-1]["id"]}, headers=H).json()
    assert moved["folder_id"] == folders[-1]["id"]
