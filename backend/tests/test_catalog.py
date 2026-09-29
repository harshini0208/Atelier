"""Integrity of the synthetic Urban Thread catalog and personas."""
import json
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from data.generate import build_catalog, build_personas
from wiw.vocab import (COLORS, FABRICS, LENGTHS, NECKLINES, OCCASIONS, PATTERNS, SILHOUETTES, SLEEVES,
                       STYLE_TAGS, SUB_TO_CAT, size_system)


@pytest.fixture(scope="module")
def catalog():
    return build_catalog()


def stock(catalog, name):
    pid = next(p["id"] for p in catalog["products"] if p["name"] == name)
    return {s["size"]: s["stock"] for s in catalog["product_sizes"] if s["product_id"] == pid}


def test_deterministic(catalog):
    assert json.dumps(build_catalog(), sort_keys=True) == json.dumps(catalog, sort_keys=True)


def test_size_and_single_store(catalog):
    assert 85 <= len(catalog["products"]) <= 100
    assert {p["store_id"] for p in catalog["products"]} == {"urban-thread"}
    ids = [p["id"] for p in catalog["products"]]
    assert len(ids) == len(set(ids))


def test_attributes_use_vocabulary(catalog):
    for p in catalog["products"]:
        assert SUB_TO_CAT[p["subcategory"]] == p["category"], p["name"]
        assert p["primary_color"] in COLORS and (p["secondary_color"] in COLORS or p["secondary_color"] is None)
        assert p["pattern"] in PATTERNS and p["fabric"] in FABRICS
        assert p["silhouette"] in SILHOUETTES and p["length"] in LENGTHS
        assert p["neckline"] in NECKLINES and p["sleeve"] in SLEEVES
        assert set(p["occasion_tags"]) <= set(OCCASIONS) and p["occasion_tags"]
        assert set(p["style_tags"]) <= set(STYLE_TAGS) and p["style_tags"]
        assert p["gender_fit"] in ("women", "men", "unisex")


def test_prices_are_realistic(catalog):
    for p in catalog["products"]:
        assert 499 <= p["price_inr"] <= 7000, p["name"]
        assert p["mrp_inr"] >= p["price_inr"]
        assert p["price_inr"] % 100 == 99


def test_sizes_match_size_system(catalog):
    by = {}
    for s in catalog["product_sizes"]:
        assert s["stock"] >= 0
        by.setdefault(s["product_id"], []).append(s["size"])
    for p in catalog["products"]:
        assert by[p["id"]] == size_system(p["category"], p["gender_fit"])


def test_deliberate_gaps(catalog):
    subs = Counter(p["subcategory"] for p in catalog["products"])
    for gap in ("wide_leg_trousers", "lehenga", "stilettos", "kolhapuris", "shrug", "leggings"):
        assert subs[gap] == 0, gap
    assert subs["juttis"] == 1


def test_edge_cases_for_also_view(catalog):
    assert sum(p["fabric"] == "polyester" for p in catalog["products"]) >= 5
    by_pid = Counter()
    for s in catalog["product_sizes"]:
        if s["stock"] > 0:
            by_pid[s["product_id"]] += 1
    fully_out = [p for p in catalog["products"] if by_pid[p["id"]] == 0]
    assert [p["name"] for p in fully_out] == ["Pastel pink anarkali set"]
    assert any("scheduled_price_drop_inr" in p for p in catalog["products"])


def test_demo_invariants(catalog):
    assert stock(catalog, "Ivory linen relaxed shirt")["M"] > 0
    assert stock(catalog, "Ecru linen boyfriend shirt")["M"] == 0
    assert stock(catalog, "Sand tapered chinos")["28"] == 0
    assert stock(catalog, "Beige straight chinos")["28"] > 0
    assert stock(catalog, "Tan leather penny loafers")["5"] > 0
    assert stock(catalog, "Gold embroidered juttis")["6"] == 0


def test_personas_reference_real_products(catalog):
    personas = build_personas(catalog)["personas"]
    names = {p["name"]: p for p in catalog["products"]}
    assert len(personas) == 5
    for pr in personas:
        for name, size in pr["orders"]:
            p = names[name]
            assert size in size_system(p["category"], p["gender_fit"])


def test_every_product_renders_valid_svg(catalog):
    from scripts.make_images import product_svg

    for p in catalog["products"]:
        root = ET.fromstring(product_svg(p))
        assert root.get("viewBox") == "0 0 200 200"


def test_clean_start_has_no_shoppers():
    from sqlalchemy import func, select

    from wiw import models as m
    from wiw.db import session_scope
    from wiw.seed import seed_all
    out = seed_all(images=False)
    assert out["personas"] == 0
    with session_scope() as db:
        assert db.scalar(select(func.count()).select_from(m.User)) == 0
        assert db.scalar(select(func.count()).select_from(m.Event)) == 0
        assert db.scalar(select(func.count()).select_from(m.Product)) == 94
