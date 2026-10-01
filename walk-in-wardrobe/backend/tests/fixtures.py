"""Small fixed fixtures for matcher tests (independent of the generated catalog)."""
import yaml

from wiw.settings import ROOT

CFG = yaml.safe_load((ROOT / "config/matching.yaml").read_text())


def product(pid, sub, cat, color="ivory", fabric="linen", price=1799, sizes=None, **kw):
    base = dict(id=pid, subcategory=sub, category=cat, primary_color=color, secondary_color=None, pattern="solid",
                fabric=fabric, silhouette="relaxed", length="regular", style_tags=["old_money", "minimal"],
                occasion_tags=["brunch", "vacation"], price_inr=price, gender_fit="women",
                sizes=sizes if sizes is not None else [{"size": "S", "stock": 3}, {"size": "M", "stock": 4}])
    base.update(kw)
    return base


def piece(sub="linen_shirt", color="ivory", fabric="linen", **kw):
    base = dict(subcategory=sub, color=color, secondary_color=None, pattern="solid", fabric=fabric,
                silhouette="relaxed", style_tags=["old_money", "minimal"], occasion_tags=["brunch", "vacation"])
    base.update(kw)
    return base


PREFS = {"budgets": {"tops": [500, 2500], "bottoms": [800, 2500], "footwear": [1000, 4000], "accessories": [300, 2500]},
         "sizes": {"tops": "M", "bottoms": "28", "footwear": "5"}, "preferred_materials": ["linen", "cotton"],
         "avoid_materials": ["polyester"], "avoid_colors": ["orange"], "gender_fit": "women"}
