"""Stylist tools + offline planner, outfit building, mannequin looks, avatar description fallback."""
import pytest
from sqlalchemy import select

from wiw import models as m
from wiw.db import session_scope
from wiw.settings import ROOT
from wiw.stylist import chat, parse_budget, parse_formality, parse_occasion, parse_pref_change, subcategories_in

H = {"X-User-Id": "aanya"}


def test_parsers():
    assert parse_budget("make it work for a beach wedding under ₹5,000") == 5000
    assert parse_budget("under 5k please") == 5000
    assert parse_budget("below rs 3500") == 3500
    assert parse_budget("no budget talk") is None
    assert parse_occasion("make it work for a beach wedding") == "beach wedding"
    assert parse_occasion("something for my cousin's sangeet") == "festive"
    assert parse_occasion("for the office") == "work"
    assert parse_formality("make it more casual") == "more_casual"
    assert parse_formality("dress it up a bit") == "more_formal"
    assert parse_pref_change("I hate polyester") == {"add_avoid_materials": ["polyester"]}
    assert parse_pref_change("I'm a size L")["sizes"] == {"tops": "L"}
    assert subcategories_in("find me a white tshirt") == ["tshirt"]
    assert "sunglasses" in subcategories_in("need some shades")


@pytest.fixture(scope="module")
def demo_folder():
    """Aanya's scripted demo folder: old-money look (3 of 5) + the resort look (all 4), offline mode."""
    from fastapi.testclient import TestClient

    from wiw.seed import seed_all
    seed_all(personas=True)
    from wiw.main import app
    c = TestClient(app)
    f = c.post("/api/folders", json={"name": "Old-money summer", "description": "Linen, loafers and long lunches"}, headers=H).json()
    for name, pick in (("old_money_summer", {"linen_shirt", "chinos", "loafers"}), ("resort_linen", None)):
        data = (ROOT / "demo/inspo/generated" / f"{name}.png").read_bytes()
        r = c.post(f"/api/folders/{f['id']}/inspo", files={"file": (f"{name}.png", data, "image/png")}, headers=H).json()
        ids = [p["id"] for p in r["pieces"] if pick is None or p["subcategory"] in pick]
        c.post(f"/api/inspo/{r['id']}/select", json={"piece_ids": ids}, headers=H)
    return c, f["id"]


def test_beach_wedding_under_budget_is_grounded(demo_folder):
    c, fid = demo_folder
    r = c.post("/api/chat", json={"message": "Make it work for a beach wedding under ₹5,000", "folder_id": fid}, headers=H).json()
    o = r["payload"]["outfit"]
    assert o and o["within_budget"] and o["total_inr"] <= 5000
    with session_scope() as db:
        prices = {p.id: p.price_inr for p in db.scalars(select(m.Product))}
    assert all(i["product"]["id"] in prices for i in o["items"])                       # real products only
    assert o["total_inr"] == sum(prices[i["product"]["id"]] for i in o["items"])       # total from the DB
    assert {i["product"]["slot"] for i in o["items"]} >= {"torso", "legs", "feet"}
    assert any(i["product"]["subcategory"] == "sandals" for i in o["items"])           # beach beats loafers on budget
    assert "wide-leg" in r["content"].lower()                                          # honest about the gap


def test_preference_change_needs_confirmation(demo_folder):
    c, fid = demo_folder
    r = c.post("/api/chat", json={"message": "I really can't stand polyester", "folder_id": fid}, headers=H).json()
    assert r["payload"]["pending_preferences"]["summary"] == "avoid polyester"
    before = c.get("/api/preferences", headers=H).json()
    c.post(f"/api/chat/{r['id']}/confirm", json={"accept": False}, headers=H)
    assert c.get("/api/preferences", headers=H).json() == before
    r2 = c.post("/api/chat", json={"message": "I hate chiffon", "folder_id": fid}, headers=H).json()
    c.post(f"/api/chat/{r2['id']}/confirm", json={"accept": True}, headers=H)
    assert "chiffon" in c.get("/api/preferences", headers=H).json()["avoid_materials"]


def test_board_and_cart_via_chat(demo_folder):
    c, fid = demo_folder
    c.post("/api/chat", json={"message": "Make it work for a beach wedding under ₹5,000", "folder_id": fid}, headers=H)
    r = c.post("/api/chat", json={"message": "put it on my board", "folder_id": fid}, headers=H).json()
    assert r["payload"]["actions"]
    looks = c.get(f"/api/folders/{fid}/looks", headers=H).json()
    assert looks[0]["name"].startswith("Stylist pick") and len(looks[0]["items"]) >= 3
    r = c.post("/api/chat", json={"message": "add the look to my cart", "folder_id": fid}, headers=H).json()
    assert "cart" in r["content"].lower()
    assert c.get("/api/cart", headers=H).json()["count"] >= 3


def test_style_it_for_me(demo_folder):
    c, fid = demo_folder
    st = c.post(f"/api/folders/{fid}/style", json={}, headers=H).json()
    assert 1 <= len(st["options"]) <= 3
    keys = {tuple(i["product"]["id"] for i in o["items"]) for o in st["options"]}
    assert len(keys) == len(st["options"])  # distinct combinations
    assert all(o["reason"] for o in st["options"])
    casual = c.post(f"/api/folders/{fid}/style", json={"formality": "more_casual"}, headers=H).json()
    assert casual["options"]


def test_board_looks_keep_positions_and_layers(demo_folder):
    c, fid = demo_folder
    dup = c.post(f"/api/folders/{fid}/looks", json={"placements": [{"product_id": "ut-001"}, {"product_id": "ut-001"}]}, headers=H)
    assert dup.status_code == 422
    assert c.post(f"/api/folders/{fid}/looks", json={"placements": [{"product_id": "nope"}]}, headers=H).status_code == 404
    assert c.post(f"/api/folders/{fid}/looks", json={"placements": []}, headers=H).status_code == 422
    # free canvas: a shirt with a blazer layered OVER it (outside), and a tee layered UNDER the shirt (inside)
    body = {"name": "Layers", "placements": [
        {"product_id": "ut-001", "x": 30, "y": 5, "w": 40, "z": 20},
        {"product_id": "ut-058", "x": 25, "y": 3, "w": 46, "z": 30},
        {"product_id": "ut-013", "x": 33, "y": 8, "w": 36, "z": 10},
        {"product_id": "ut-030"}]}  # no position: gets a sensible default
    look = c.post(f"/api/folders/{fid}/looks", json=body, headers=H).json()
    items = {i["product"]["id"]: i for i in look["items"]}
    assert items["ut-058"]["z"] > items["ut-001"]["z"] > items["ut-013"]["z"]
    assert all(items["ut-030"][k] is not None for k in ("x", "y", "w", "z"))
    assert c.get(f"/api/folders/{fid}/looks", headers=H).json()[0]["id"] == look["id"]


def test_style_it_returns_a_board_layout(demo_folder):
    c, fid = demo_folder
    st = c.post(f"/api/folders/{fid}/style", json={}, headers=H).json()
    o = st["options"][0]
    assert {d["product_id"] for d in o["layout"]} == {i["product"]["id"] for i in o["items"]}
    assert c.get("/api/avatar", headers=H).status_code == 404  # the mannequin is gone


def test_product_photos(tmp_path, monkeypatch):
    from PIL import Image

    from wiw import product_images as pi
    monkeypatch.setattr(pi, "PHOTO_DIR", tmp_path)
    Image.new("RGB", (1800, 2400), "white").save(tmp_path / "ut-001.jpg")
    Image.new("RGBA", (400, 400), (0, 0, 0, 0)).save(tmp_path / "ut-002.png")
    with session_scope() as db:
        assert pi.apply_photos(db) == 2
        a, b = db.get(m.Product, "ut-001"), db.get(m.Product, "ut-002")
        assert a.image_url.endswith("/products/photos/ut-001.jpg") and b.image_url.endswith(".png")
        assert db.get(m.Product, "ut-003").image_url.endswith(".svg")          # no photo: keeps the flat-lay
        manifest = pi.write_manifest(db, tmp_path / "manifest.csv").read_text()
        assert "ut-001.jpg,ut-001,Ivory linen relaxed shirt" in manifest
        db.rollback()
    from wiw.storage import storage
    img = Image.open(__import__("io").BytesIO(storage().get("products/photos/ut-001.jpg")))
    assert max(img.size) <= pi.MAX_SIDE


def test_tool_rejects_unknown_products():
    from wiw.stylist import Ctx, execute
    with session_scope() as db:
        ctx = Ctx(db=db, user=db.get(m.User, "aanya"), folder=db.scalars(select(m.Folder).where(m.Folder.user_id == "aanya")).first(), hangers=[])
        assert "error" in execute(ctx, "place_on_mannequin", {"product_ids": ["ut-999"]})
        assert execute(ctx, "add_to_cart", {"product_ids": ["ut-999"]}) == {"added": [], "needs_size_choice": []}
        assert "error" in execute(ctx, "get_hanger_matches", {"hanger": 42})
        assert "error" in execute(ctx, "nonexistent_tool", {})
        db.rollback()
