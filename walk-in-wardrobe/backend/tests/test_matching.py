"""Matching engine: style score, good-match gate, preference tiers, look coverage, complete-the-look."""
import pytest

from fixtures import CFG, PREFS, piece, product
from wiw.colors import color_distance, harmony
from wiw.matching import Matcher, MatchResult, ScoredItem, coverage_line


@pytest.fixture
def mt():
    return Matcher(CFG)


def test_identical_item_scores_100(mt):
    s, breakdown = mt.style_score(piece(), product("a", "linen_shirt", "tops"))
    assert s == pytest.approx(100.0)
    assert sum(breakdown.values()) == pytest.approx(100.0)


def test_color_distance_is_perceptual_not_string_equality():
    assert color_distance("ivory", "cream") < 10         # near-identical off-whites
    assert color_distance("ivory", "navy") > 50
    assert color_distance("sand", "beige") < color_distance("sand", "olive")


def test_score_monotonic_in_color_and_fabric(mt):
    p = piece()
    close = mt.style_score(p, product("a", "linen_shirt", "tops", color="cream"))[0]
    far = mt.style_score(p, product("b", "linen_shirt", "tops", color="red"))[0]
    poly = mt.style_score(p, product("c", "linen_shirt", "tops", fabric="polyester"))[0]
    cotton = mt.style_score(p, product("d", "linen_shirt", "tops", fabric="cotton"))[0]
    assert close > far
    assert cotton > poly  # linen~cotton share a fabric group


def test_inapplicable_attributes_are_rescaled(mt):
    shoe_piece = piece("loafers", "tan", "leather", silhouette="none")
    shoe = product("s", "loafers", "footwear", color="tan", fabric="leather", silhouette="none")
    s, breakdown = mt.style_score(shoe_piece, shoe)
    assert "silhouette" not in breakdown and s == pytest.approx(100.0)


def test_good_match_requires_threshold_subcategory_and_stock(mt):
    p = piece()
    ok = product("a", "linen_shirt", "tops")
    assert mt.is_good(p, ok, mt.style_score(p, ok)[0])
    sold_out = product("b", "linen_shirt", "tops", sizes=[{"size": "M", "stock": 0}])
    assert not mt.is_good(p, sold_out, mt.style_score(p, sold_out)[0])
    # a perfect-colour blouse is still not a linen shirt (subcategory similarity 0.5 < 0.75)
    blouse = product("c", "blouse", "tops")
    assert not mt.is_good(p, blouse, mt.style_score(p, blouse)[0])
    # shirt <-> linen_shirt are interchangeable (0.85)
    shirt = product("d", "shirt", "tops", fabric="cotton")
    assert mt.is_good(p, shirt, mt.style_score(p, shirt)[0])


def test_wide_leg_is_not_covered_by_palazzo_or_chinos(mt):
    wl = piece("wide_leg_trousers", "sand", "linen", silhouette="wide")
    for sub in ("palazzo", "chinos"):
        prod = product("x", sub, "bottoms", color="sand", fabric="linen", silhouette="wide")
        assert not mt.is_good(wl, prod, mt.style_score(wl, prod)[0]), sub


def test_preference_reasons(mt):
    over = product("a", "linen_shirt", "tops", price=3299)
    assert [r.label for r in mt.preference_reasons(over, PREFS)] == ["₹799 over budget"]
    m_sold = product("b", "linen_shirt", "tops", sizes=[{"size": "M", "stock": 0}, {"size": "L", "stock": 5}])
    assert [r.label for r in mt.preference_reasons(m_sold, PREFS)] == ["Your size M is sold out"]
    no_m = product("c", "linen_shirt", "tops", sizes=[{"size": "L", "stock": 5}])
    assert [r.code for r in mt.preference_reasons(no_m, PREFS)] == ["size"]
    poly = product("d", "linen_shirt", "tops", fabric="polyester")
    assert [r.label for r in mt.preference_reasons(poly, PREFS)] == ["Polyester"]
    orange = product("e", "linen_shirt", "tops", color="orange")
    assert [r.code for r in mt.preference_reasons(orange, PREFS)] == ["color"]
    many = product("f", "linen_shirt", "tops", fabric="polyester", price=2600, sizes=[{"size": "M", "stock": 0}, {"size": "L", "stock": 1}])
    assert {r.code for r in mt.preference_reasons(many, PREFS)} == {"budget", "size", "material"}
    free = product("g", "tote", "accessories", sizes=[{"size": "Free", "stock": 2}])
    assert mt.preference_reasons(free, PREFS) == []
    assert mt.preference_reasons(over, None) == []


def test_tiers_never_hide_preference_failures(mt):
    p = piece()
    items = [product("fy", "linen_shirt", "tops"),
             product("budget", "linen_shirt", "tops", price=3299),
             product("poly", "linen_shirt", "tops", fabric="polyester", price=1199),
             product("bad", "tshirt", "tops", color="red", fabric="cotton"),
             product("gone", "linen_shirt", "tops", sizes=[{"size": "M", "stock": 0}])]
    r = mt.rank(p, items, PREFS)
    assert [i.product["id"] for i in r.for_you] == ["fy"]
    assert {i.product["id"] for i in r.also_view} == {"budget", "poly"}
    assert all(i.reasons for i in r.also_view)
    assert r.closest == []  # there are good matches, so no "closest" fallback
    ids = [i.product["id"] for i in r.for_you + r.also_view]
    assert "bad" not in ids and "gone" not in ids


def test_sort_by_tier_then_score(mt):
    p = piece()
    r = mt.rank(p, [product("a", "linen_shirt", "tops", color="sand"), product("b", "linen_shirt", "tops"),
                    product("c", "shirt", "tops", fabric="cotton")], PREFS)
    scores = [i.display_score for i in r.for_you]
    assert scores == sorted(scores, reverse=True)


def test_closest_shown_when_no_good_match(mt):
    wl = piece("wide_leg_trousers", "sand", "linen", silhouette="wide")
    r = mt.rank(wl, [product("ch", "chinos", "bottoms", color="beige", fabric="cotton"),
                     product("pz", "palazzo", "bottoms", color="rust", fabric="viscose", pattern="print")], PREFS)
    assert not r.covered and not r.covered_in_prefs
    assert [i.product["id"] for i in r.closest][:1] == ["ch"]


def test_look_coverage_counts():
    def res(fy, av):
        dummy = ScoredItem(product={}, score=90, breakdown={}, good=True)
        return MatchResult([dummy] if fy else [], [dummy] if av else [], [])
    cov = Matcher.coverage([res(True, False), res(False, True), res(True, True), res(False, False)])
    assert (cov["covered"], cov["covered_in_prefs"], cov["total"]) == (3, 2, 4)
    assert cov["line"] == "This store covers 3 of 4 pieces (2 within your preferences)."
    assert coverage_line(0, 0, 2) == "This store covers 0 of 2 pieces."
    assert Matcher.coverage([])["total"] == 0


def test_complete_the_look(mt):
    look = [dict(subcategory="linen_shirt", primary_color="ivory", style_tags=["old_money"], occasion_tags=["brunch"]),
            dict(subcategory="chinos", primary_color="beige", style_tags=["old_money", "classic"], occasion_tags=["work"])]
    loafers = product("l", "loafers", "footwear", color="tan", fabric="leather", style_tags=["old_money", "classic"],
                      occasion_tags=["work", "brunch"])
    sneakers = product("s", "sneakers", "footwear", color="red", fabric="knit", style_tags=["athleisure"], occasion_tags=["gym"])
    assert mt.compatibility(loafers, look)[0] > mt.compatibility(sneakers, look)[0]
    assert mt.fills_gap(loafers, look)
    assert not mt.fills_gap(product("t", "tshirt", "tops"), look)           # torso already taken
    assert not mt.fills_gap(product("d", "dress", "one_piece"), look)       # full-body clashes with top+bottom
    assert harmony("ivory", "rust") == 1.0 and harmony("red", "green") < 0.7
