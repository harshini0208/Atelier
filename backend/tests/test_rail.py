"""The rail: bought online + in store, bag and wishlist on one generic hanger; multi-folder hanging; rail styling."""
import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)

PROFILE = {"name": "Rail Tester", "city": "Bengaluru", "gender_fit": "women",
           "sizes": {"tops": "M", "bottoms": "28", "footwear": "6"}, "fit": "regular", "budgets": {},
           "preferred_materials": [], "avoid_materials": [], "avoid_colors": [], "occasions": ["work"]}


@pytest.fixture(scope="module")
def ctx():
    from fastapi.testclient import TestClient

    from wiw.seed import seed_all
    seed_all(images=False)
    from wiw.main import app
    with TestClient(app) as c:
        uid = c.post("/api/profile", json=PROFILE).json()["id"]
        yield c, {"X-User-Id": uid}


def test_new_shopper_rail_is_empty(ctx):
    c, h = ctx
    r = c.get("/api/rail", headers=h).json()
    assert r["items"] == [] and not r["member_linked"]


def test_wishlist_and_bag_show_on_the_rail(ctx):
    c, h = ctx
    assert c.post("/api/wishlist", json={"product_id": "ut-001"}, headers=h).json()["ok"]
    c.post("/api/wishlist", json={"product_id": "ut-001"}, headers=h)            # idempotent
    assert c.get("/api/wishlist", headers=h).json() == ["ut-001"]
    assert c.post("/api/wishlist", json={"product_id": "nope"}, headers=h).status_code == 404
    c.post("/api/cart", json={"product_id": "ut-002", "size": "M"}, headers=h)
    items = {e["product"]["id"]: e for e in c.get("/api/rail", headers=h).json()["items"]}
    assert [s["kind"] for s in items["ut-001"]["sources"]] == ["wishlist"]
    assert items["ut-002"]["sources"][0]["kind"] == "cart" and not items["ut-002"]["owned"]


def test_membership_brings_online_and_in_store_purchases(ctx):
    from sqlalchemy import func, select

    from wiw import models as m
    from wiw.db import session_scope
    c, h = ctx
    with session_scope() as db:
        stock_before = db.scalar(select(func.sum(m.ProductSize.stock)))
    r = c.post("/api/membership/link", json={}, headers=h).json()
    assert r["added"] >= 5 and r["rail"]["member_linked"]
    counts = r["rail"]["counts"]
    assert counts["online"] >= 2 and counts["in_store"] >= 2 and counts["bought"] == counts["online"] + counts["in_store"]
    store = next(e for e in r["rail"]["items"] if any(s["kind"] == "in_store" for s in e["sources"]))
    assert "Phoenix Marketcity" in store["sources"][0]["detail"] and store["owned"]
    assert all(e["product"]["gender_fit"] in ("women", "unisex") for e in r["rail"]["items"])
    assert c.post("/api/membership/link", json={}, headers=h).json()["added"] == 0     # only once
    with session_scope() as db:
        assert db.scalar(select(func.sum(m.ProductSize.stock))) == stock_before       # past purchases: stock untouched


def test_hang_a_rail_piece_in_several_folders(ctx):
    c, h = ctx
    work = c.post("/api/folders", json={"name": "Work"}, headers=h).json()
    trip = c.post("/api/folders", json={"name": "Goa trip"}, headers=h).json()
    pid = c.get("/api/rail", headers=h).json()["items"][0]["product"]["id"]
    r = c.put(f"/api/rail/{pid}/folders", json={"folder_ids": [work["id"], trip["id"], 99999]}, headers=h).json()
    assert r["folder_ids"] == sorted([work["id"], trip["id"]])                       # someone else's / unknown ignored
    detail = c.get(f"/api/folders/{work['id']}", headers=h).json()
    hanger = detail["hangers"][0]
    assert hanger["chosen_product_id"] == pid and hanger["from_rail"] and detail["looks"] == []
    assert c.get("/api/inspo", headers=h).json() == []                              # the hidden source isn't an upload
    item = next(e for e in c.get("/api/rail", headers=h).json()["items"] if e["product"]["id"] == pid)
    assert item["folder_ids"] == sorted([work["id"], trip["id"]])
    c.put(f"/api/rail/{pid}/folders", json={"folder_ids": [trip["id"]]}, headers=h)
    assert c.get(f"/api/folders/{work['id']}", headers=h).json()["hangers"] == []
    assert c.get(f"/api/folders/{trip['id']}", headers=h).json()["hanger_count"] == 1
    # a rail hanger works like any other: matches lead with the piece itself
    hid = c.get(f"/api/folders/{trip['id']}", headers=h).json()["hangers"][0]["id"]
    m = c.get(f"/api/hangers/{hid}/matches", headers=h).json()
    assert (m["for_you"] + m["also_view"])[0]["product"]["id"] == pid


def test_style_the_rail_and_save_a_board_look(ctx):
    c, h = ctx
    tray = c.get("/api/rail/tray", headers=h).json()["items"]
    assert len(tray) >= 6 and any(t["owned"] for t in tray)
    r = c.post("/api/rail/style", json={}, headers=h).json()
    assert r["options"] and r["options"][0]["layout"] and r["options"][0]["owned_count"] >= 1
    placements = [{"product_id": t["product"]["id"]} for t in tray[:3]]
    look = c.post("/api/rail/looks", json={"name": "Rail look", "placements": placements}, headers=h).json()
    assert len(look["items"]) == 3 and c.get("/api/rail/looks", headers=h).json()[0]["id"] == look["id"]
    assert c.delete(f"/api/rail/looks/{look['id']}", headers=h).json()["ok"]


def test_stylist_without_a_folder_styles_the_rail(ctx):
    c, h = ctx
    hello = c.get("/api/chat", headers=h).json()[0]["content"]
    assert "on your rail" in hello
    r = c.post("/api/chat", json={"message": "style an outfit for work"}, headers=h).json()
    o = r["payload"]["outfit"]
    assert o["items"] and o["owned_count"] >= 1                                     # leans on what they own
    assert o["total_inr"] == sum(i["product"]["price_inr"] for i in o["items"] if not i["owned"])   # owned pieces are free
    assert "already" in r["content"] or "nothing to buy" in r["content"]
    r = c.post("/api/chat", json={"message": "put it on the board"}, headers=h).json()
    assert c.get("/api/rail/looks", headers=h).json()                               # laid out on the rail's board


def test_delete_me_removes_rail_data(ctx):
    from sqlalchemy import func, select

    from wiw import models as m
    from wiw.db import session_scope
    c, h = ctx
    assert c.delete("/api/me", headers=h).json()["ok"]
    with session_scope() as db:
        for model in (m.WishlistItem, m.StorePurchase, m.RailLook, m.Hanger):
            assert db.scalar(select(func.count()).select_from(model).where(model.user_id == h["X-User-Id"])) == 0
