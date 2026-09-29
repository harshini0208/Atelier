"""Alert triggers (price drop, restock, new arrival), taste profile, retailer numbers."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from wiw import models as m
from wiw.agents import change_price, launch_new_arrival, restock
from wiw.db import session_scope
from wiw.settings import ROOT
from wiw.taste import profile, taste_score

H = {"X-User-Id": "aanya"}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from wiw.seed import seed_all
    seed_all()
    from wiw.main import app
    c = TestClient(app)
    f = c.post("/api/folders", json={"name": "Old-money summer"}, headers=H).json()
    data = (ROOT / "demo/inspo/generated/old_money_summer.png").read_bytes()
    r = c.post(f"/api/folders/{f['id']}/inspo", files={"file": ("a.png", data, "image/png")}, headers=H).json()
    c.post(f"/api/inspo/{r['id']}/select", json={"piece_ids": [p["id"] for p in r["pieces"]
                                                               if p["subcategory"] in ("linen_shirt", "chinos", "loafers")]}, headers=H)
    return c


def notes(user_id, kind):
    with session_scope() as db:
        return [n.body for n in db.scalars(select(m.Notification).where(m.Notification.user_id == user_id, m.Notification.kind == kind))]


def test_price_drop_notifies_watchers_only(client):
    with session_scope() as db:
        out = change_price(db, "ut-007", 1299)  # Olive linen camp shirt
    assert "aanya" in out["notified"] and "kabir" not in out["notified"]
    assert any("dropped from ₹1,699 to ₹1,299" in b for b in notes("aanya", "price_drop"))
    with session_scope() as db:
        assert db.get(m.Product, "ut-007").price_inr == 1299
        assert db.scalars(select(m.PriceHistory).where(m.PriceHistory.product_id == "ut-007")).all()[-1].price_inr == 1299
        assert db.scalar(select(m.Event).where(m.Event.event_type == "alert_sent", m.Event.user_id == "aanya"))


def test_price_rise_or_tiny_drop_is_silent(client):
    with session_scope() as db:
        assert change_price(db, "ut-007", 1799)["notified"] == []
        assert change_price(db, "ut-007", 1780)["notified"] == []  # ~1% drop is below price_drop_min_pct


def test_restock_notifies_only_matching_size(client):
    with session_scope() as db:
        out = restock(db, "ut-004", "M", 3)  # Ecru linen boyfriend shirt, Aanya wears M
        assert out["notified"] == ["aanya"]
        again = restock(db, "ut-004", "M", 2)  # already in stock -> no alert
        assert again["notified"] == []
        other = restock(db, "ut-004", "S", 2)  # S was 0 but nobody watching wears S
        assert "aanya" not in other["notified"]


def test_new_arrival_threshold(client):
    with session_scope() as db:
        out = launch_new_arrival(db, 0)  # Sky stripe linen shirt
        for uid, score in out["scores"].items():
            assert (uid in out["notified"]) == (score >= out["threshold"])
        assert db.get(m.Product, out["product"]["id"]).sizes
        with pytest.raises(ValueError):
            launch_new_arrival(db, 0)


def test_taste_profile_core_and_exploring(client):
    with session_scope() as db:
        prof = profile(db, "zoya")
        assert prof["saves"] > 0
        core = {i["value"] for i in prof["core"]}
        assert "resort" in core  # repeated across Zoya's saves
        later = profile(db, "aanya", now=datetime.utcnow() + timedelta(days=60))
        assert later["exploring"] == []  # nothing is "new" two months later
        pd = {"subcategory": "linen_shirt", "primary_color": "sky_blue", "fabric": "linen", "pattern": "stripes",
              "style_tags": ["resort", "old_money"], "occasion_tags": ["vacation"]}
        assert taste_score(prof, pd) > taste_score(prof, {**pd, "subcategory": "boots", "fabric": "leather",
                                                           "primary_color": "black", "style_tags": ["edgy"], "occasion_tags": ["work"]})


def test_retailer_numbers_are_counts(client):
    r = client.get("/api/retailer").json()
    wide = next(g for g in r["gaps"] if g["label"] == "Wide-leg trousers")
    assert wide["saves_with_match"] == 0 and wide["saves"] >= 100
    steps = [s["shoppers"] for s in r["funnel"]]
    assert steps == sorted(steps, reverse=True)  # a funnel only narrows
    assert r["memo"]["headline"] and len(r["memo"]["bullets"]) >= 2
    t = client.get("/api/taste", headers=H).json()
    assert t["sentence"]
