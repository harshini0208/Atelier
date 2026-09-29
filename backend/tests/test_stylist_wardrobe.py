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
    seed_all(with_history=False)
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


def test_mannequin_and_cart_via_chat(demo_folder):
    c, fid = demo_folder
    c.post("/api/chat", json={"message": "Make it work for a beach wedding under ₹5,000", "folder_id": fid}, headers=H)
    r = c.post("/api/chat", json={"message": "put it on the mannequin", "folder_id": fid}, headers=H).json()
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


def test_look_validation(demo_folder):
    c, fid = demo_folder
    bad = c.post(f"/api/folders/{fid}/looks", json={"placements": [{"product_id": "ut-001"}, {"product_id": "ut-008"}]}, headers=H)
    assert bad.status_code == 422  # two tops in one slot
    assert c.post(f"/api/folders/{fid}/looks", json={"placements": [{"product_id": "nope"}]}, headers=H).status_code == 404
    ok = c.post(f"/api/folders/{fid}/looks", json={"name": "Mine", "placements": [{"product_id": "ut-001"}, {"product_id": "ut-030"}]}, headers=H)
    assert ok.status_code == 200 and ok.json()["total_inr"] > 0


def test_mannequin_geometry_and_avatar(demo_folder):
    c, _ = demo_folder
    g = c.get("/api/mannequin?presentation=men&body_type=broad&height_band=tall&skin_tone=7").json()
    assert g["body"].startswith("<") and "linen_shirt" in g["transforms"] and "feet" in g["drop_zones"]
    assert c.get("/api/mannequin?presentation=women&body_type=broad").json()["transforms"]  # invalid combo repaired
    d = c.post("/api/avatar/describe", json={"text": "tall, athletic guy with a buzz cut and deep brown skin"}, headers=H).json()
    assert (d["presentation"], d["body_type"], d["height_band"], d["hair_style"]) == ("men", "athletic", "tall", "buzz")
    assert d["skin_tone"] >= 6
    saved = c.put("/api/avatar", json={**{k: v for k, v in d.items() if k != "source"}}, headers=H).json()
    assert saved["body_type"] == "athletic"


def test_tool_rejects_unknown_products():
    from wiw.stylist import Ctx, execute
    with session_scope() as db:
        ctx = Ctx(db=db, user=db.get(m.User, "aanya"), folder=db.scalars(select(m.Folder).where(m.Folder.user_id == "aanya")).first(), hangers=[])
        assert "error" in execute(ctx, "place_on_mannequin", {"product_ids": ["ut-999"]})
        assert execute(ctx, "add_to_cart", {"product_ids": ["ut-999"]}) == {"added": [], "needs_size_choice": []}
        assert "error" in execute(ctx, "get_hanger_matches", {"hanger": 42})
        assert "error" in execute(ctx, "nonexistent_tool", {})
        db.rollback()
