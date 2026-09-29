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
    seed_all(personas=True)
    from wiw.main import app
    with TestClient(app) as c:
        yield c


def upload(client, folder_id, name, headers=H):
    data = (ROOT / "demo/inspo/generated" / f"{name}.png").read_bytes()
    r = client.post(f"/api/folders/{folder_id}/inspo", files={"file": (f"{name}.png", data, "image/png")}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_onboarding_creates_a_profile(client):
    assert client.get("/api/me").status_code == 401                       # no default shopper any more
    assert client.get("/api/me", headers={"X-User-Id": "nobody"}).status_code == 401
    body = {"name": "Harshini", "city": "Bengaluru", "gender_fit": "women", "sizes": {"tops": "S", "bottoms": "26", "footwear": "5"},
            "fit": "relaxed", "budgets": {"tops": [500, 2000]}, "preferred_materials": ["linen"], "avoid_materials": ["polyester"],
            "avoid_colors": [], "occasions": ["work"]}
    assert client.post("/api/profile", json={**body, "name": ""}).status_code == 422
    uid = client.post("/api/profile", json=body).json()["id"]
    me = client.get("/api/me", headers={"X-User-Id": uid}).json()
    assert (me["name"], me["city"], me["preferences"]["sizes"]["tops"]) == ("Harshini", "Bengaluru", "S")
    assert client.get("/api/folders", headers={"X-User-Id": uid}).json() == []  # starts empty
    client.patch("/api/me", json={"name": "Harshini S", "city": "Mumbai"}, headers={"X-User-Id": uid})
    assert client.get("/api/me", headers={"X-User-Id": uid}).json()["name"] == "Harshini S"


def test_tap_a_piece_then_hang_a_store_product(client):
    folder = client.post("/api/folders", json={"name": "Tap to hang"}, headers=H).json()
    inspo = upload(client, folder["id"], "old_money_summer")
    shirt = next(p for p in inspo["pieces"] if p["subcategory"] == "linen_shirt")
    m = client.get(f"/api/inspo/{inspo['id']}/pieces/{shirt['id']}/matches", headers=H).json()
    assert m["for_you"] and m["hanger"] is None
    pick = m["for_you"][0]["product"]
    h = client.post(f"/api/inspo/{inspo['id']}/pieces/{shirt['id']}/hang", json={"product_id": pick["id"]}, headers=H).json()
    assert h["chosen_product_id"] == pick["id"] and h["chosen_size"] == "M"   # the store product is on the hanger
    again = client.get(f"/api/inspo/{inspo['id']}/pieces/{shirt['id']}/matches", headers=H).json()
    assert again["hanger"]["chosen_product_id"] == pick["id"]
    # switching the pick keeps one hanger per piece
    other = (m["for_you"] + m["also_view"])[1]["product"]["id"]
    h2 = client.post(f"/api/inspo/{inspo['id']}/pieces/{shirt['id']}/hang", json={"product_id": other}, headers=H).json()
    assert h2["id"] == h["id"] and h2["chosen_product_id"] == other
    # nothing close in store: save as a wish
    resort = upload(client, folder["id"], "resort_linen")
    wide = next(p for p in resort["pieces"] if p["subcategory"] == "wide_leg_trousers")
    gap = client.get(f"/api/inspo/{resort['id']}/pieces/{wide['id']}/matches", headers=H).json()
    assert not gap["covered"] and "wish" in gap["gap_message"]
    wish = client.post(f"/api/inspo/{resort['id']}/pieces/{wide['id']}/hang", json={}, headers=H).json()
    assert wish["chosen_product_id"] is None
    assert client.post(f"/api/inspo/{resort['id']}/pieces/{wide['id']}/hang", json={"product_id": "nope"}, headers=H).status_code == 404
    # "Done" records the untouched pieces as skipped, without duplicating hangers
    done = client.post(f"/api/inspo/{inspo['id']}/select", json={"piece_ids": [shirt["id"]]}, headers=H).json()
    assert done["created"] == []


def test_shop_is_a_storefront(client):
    women = client.get("/api/shop?gender=women").json()
    men = client.get("/api/shop?gender=men").json()
    assert all(p["gender_fit"] in ("women", "unisex") for p in women["products"])
    assert all(p["gender_fit"] in ("men", "unisex") for p in men["products"])
    assert sum(c["count"] for c in women["categories"]) == women["count"]
    tops = client.get("/api/shop?gender=women&category=tops&sort=price_asc").json()
    prices = [p["price_inr"] for p in tops["products"]]
    assert prices == sorted(prices) and tops["subcategories"]
    shirts = client.get("/api/shop?gender=women&category=tops&subcategory=linen_shirt").json()
    assert shirts["count"] and all(p["subcategory"] == "linen_shirt" for p in shirts["products"])
    assert client.get("/api/shop?gender=women&q=linen shirt").json()["count"] >= 3


def test_admin_endpoints_need_a_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert client.get("/api/retailer").status_code == 403
    assert client.post("/api/demo/new-arrival/2").status_code == 403
    assert client.get("/api/retailer", headers={"X-Admin-Token": "s3cret"}).status_code == 200
    assert client.get("/api/shop").status_code == 200  # the storefront stays public


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


def test_delete_my_profile_removes_everything(client):
    uid = client.post("/api/profile", json={"name": "Temp", "city": "Pune"}).json()["id"]
    hh = {"X-User-Id": uid}
    f = client.post("/api/folders", json={"name": "Temp folder"}, headers=hh).json()
    inspo = upload(client, f["id"], "street_men", headers=hh)
    piece = inspo["pieces"][0]
    client.post(f"/api/inspo/{inspo['id']}/pieces/{piece['id']}/hang", json={}, headers=hh)
    assert client.delete("/api/me", headers=hh).json() == {"ok": True}
    assert client.get("/api/me", headers=hh).status_code == 401
    from sqlalchemy import func, select

    from wiw import models as m
    from wiw.db import session_scope
    with session_scope() as db:
        for model in (m.Folder, m.Hanger, m.InspoImage, m.Event, m.TasteSignal):
            assert db.scalar(select(func.count()).select_from(model).where(model.user_id == uid)) == 0
