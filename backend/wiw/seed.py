"""Load the generated catalog + personas into the configured database and media storage."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models as m
from .db import engine, session_scope
from .settings import ROOT


def load_json(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text())


def reset_schema() -> None:
    m.Base.metadata.drop_all(engine())
    m.Base.metadata.create_all(engine())


def ensure_schema() -> None:
    m.Base.metadata.create_all(engine())


def product_from_dict(p: dict) -> m.Product:
    return m.Product(
        id=p["id"], store_id=p["store_id"], brand=p["brand"], name=p["name"], description=p["description"],
        category=p["category"], subcategory=p["subcategory"], gender_fit=p["gender_fit"],
        primary_color=p["primary_color"], secondary_color=p.get("secondary_color"), color_family=p["color_family"],
        pattern=p["pattern"], fabric=p["fabric"], silhouette=p["silhouette"], length=p["length"],
        neckline=p["neckline"], sleeve=p["sleeve"], occasion_tags=p["occasion_tags"], style_tags=p["style_tags"],
        season=p["season"], price_inr=p["price_inr"], mrp_inr=p["mrp_inr"], image_url=p["image_url"],
        added_at=datetime.fromisoformat(p["added_at"]))


def load_catalog(db: Session, catalog: dict) -> None:
    st = catalog["store"]
    db.add(m.Store(id=st["id"], name=st["name"], warehouse_city=st["warehouse_city"], description=st["description"]))
    db.flush()
    db.add(m.Brand(id=st["id"], store_id=st["id"], name=st["brand"]))
    db.flush()
    for p in catalog["products"]:
        db.add(product_from_dict(p))
    db.flush()
    pos: dict[str, int] = {}
    for s in catalog["product_sizes"]:
        pos[s["product_id"]] = pos.get(s["product_id"], -1) + 1
        db.add(m.ProductSize(product_id=s["product_id"], size=s["size"], stock=s["stock"], position=pos[s["product_id"]]))
    for ph in catalog["price_history"]:
        db.add(m.PriceHistory(product_id=ph["product_id"], price_inr=ph["price_inr"], mrp_inr=ph["mrp_inr"],
                              changed_at=datetime.fromisoformat(ph["changed_at"])))
    for se in catalog["stock_events"]:
        db.add(m.StockEvent(product_id=se["product_id"], size=se["size"], delta=se["delta"], new_stock=se["new_stock"],
                            kind=se["kind"], at=datetime.fromisoformat(se["at"])))


def load_personas(db: Session, personas: dict, catalog: dict) -> dict[str, list[int]]:
    """Create personas; returns {user_id: [folder ids]} so inspo can be attached afterwards."""
    ids = {p["name"]: p["id"] for p in catalog["products"]}
    price = {p["id"]: p["price_inr"] for p in catalog["products"]}
    folders: dict[str, list[int]] = {}
    base = datetime(2026, 9, 1, 12, 0)
    for i, pr in enumerate(personas["personas"]):
        db.add(m.User(id=pr["id"], name=pr["name"], city=pr["city"], tagline=pr["tagline"]))
        db.flush()
        prefs = pr["preferences"]
        db.add(m.Preferences(user_id=pr["id"], budgets=prefs["budgets"], sizes=prefs["sizes"], fit=prefs["fit"],
                             preferred_materials=prefs["preferred_materials"], avoid_materials=prefs["avoid_materials"],
                             avoid_colors=prefs["avoid_colors"], occasions=prefs["occasions"], gender_fit=prefs["gender_fit"]))
        db.add(m.Avatar(user_id=pr["id"], **pr["avatar"]))
        folders[pr["id"]] = []
        for f in pr["folders"]:
            fo = m.Folder(user_id=pr["id"], name=f["name"], description=f["description"])
            db.add(fo)
            db.flush()
            folders[pr["id"]].append(fo.id)
        for j, (name, size) in enumerate(pr["orders"]):
            pid = ids[name]
            when = base - timedelta(days=20 + 9 * j + i)
            order = m.Order(user_id=pr["id"], total_inr=price[pid], status="delivered", city=pr["city"],
                            delivery_days=3, created_at=when)
            order.items.append(m.OrderItem(product_id=pid, size=size, qty=1, price_inr=price[pid]))
            db.add(order)
    return folders


def write_product_images(catalog: dict) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from make_images import product_svg  # type: ignore

    from .storage import storage

    st = storage()
    for p in catalog["products"]:
        st.put(f"products/{p['id']}.svg", product_svg(p).encode(), "image/svg+xml")


def seed_all(images: bool = True, with_inspo: bool = True, with_history: bool = True) -> dict:
    catalog, personas = load_json("catalog.json"), load_json("personas.json")
    reset_schema()
    if images:
        write_product_images(catalog)
    with session_scope() as db:
        load_catalog(db, catalog)
        folders = load_personas(db, personas, catalog)
    if with_inspo:
        from .seed_inspo import attach_persona_inspo

        attach_persona_inspo(personas, folders)
    if with_history:
        from .seed_history import seed_synthetic_history

        seed_synthetic_history()
    return {"products": len(catalog["products"]), "personas": len(personas["personas"])}
