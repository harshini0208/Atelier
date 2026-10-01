"""Operational schema (identical on SQLite and Cloud SQL for PostgreSQL)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(40), default="Mumbai")
    tagline: Mapped[str] = mapped_column(String(120), default="")
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Preferences(Base):
    __tablename__ = "preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    budgets: Mapped[dict] = mapped_column(JSON, default=dict)            # {category: [min, max]}
    sizes: Mapped[dict] = mapped_column(JSON, default=dict)              # {tops, bottoms, footwear}
    fit: Mapped[str] = mapped_column(String(20), default="regular")
    preferred_materials: Mapped[list] = mapped_column(JSON, default=list)
    avoid_materials: Mapped[list] = mapped_column(JSON, default=list)
    avoid_colors: Mapped[list] = mapped_column(JSON, default=list)
    occasions: Mapped[list] = mapped_column(JSON, default=list)
    gender_fit: Mapped[str] = mapped_column(String(10), default="women")  # which catalog section to shop
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class InspoImage(Base):
    __tablename__ = "inspo_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    image_url: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="analyzed")  # analyzed | no_apparel | low_quality | failed
    message: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="")        # live | cache | fallback
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    pieces: Mapped[list[DetectedPiece]] = relationship(back_populates="inspo", order_by="DetectedPiece.idx",
                                                       cascade="all, delete-orphan")


class DetectedPiece(Base):
    __tablename__ = "detected_pieces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspo_id: Mapped[int] = mapped_column(ForeignKey("inspo_images.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))
    subcategory: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    gender_fit: Mapped[str] = mapped_column(String(10), default="unisex")
    color: Mapped[str] = mapped_column(String(20))
    secondary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pattern: Mapped[str] = mapped_column(String(20), default="solid")
    fabric: Mapped[str] = mapped_column(String(20), default="cotton")
    silhouette: Mapped[str] = mapped_column(String(20), default="regular")
    length: Mapped[str] = mapped_column(String(20), default="none")
    neckline: Mapped[str] = mapped_column(String(20), default="none")
    sleeve: Mapped[str] = mapped_column(String(20), default="none")
    style_tags: Mapped[list] = mapped_column(JSON, default=list)
    occasion_tags: Mapped[list] = mapped_column(JSON, default=list)
    box: Mapped[list | None] = mapped_column(JSON, nullable=True)       # [ymin, xmin, ymax, xmax] on 0..1000
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    crop_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    selected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)
    inspo: Mapped[InspoImage] = relationship(back_populates="pieces")


class Hanger(Base):
    __tablename__ = "hangers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("detected_pieces.id", ondelete="CASCADE"))
    chosen_product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    chosen_size: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    piece: Mapped[DetectedPiece] = relationship()


class Store(Base):
    __tablename__ = "stores"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    warehouse_city: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(80))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id"), index=True)
    brand: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), index=True)
    subcategory: Mapped[str] = mapped_column(String(30), index=True)
    gender_fit: Mapped[str] = mapped_column(String(10))
    primary_color: Mapped[str] = mapped_column(String(20))
    secondary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color_family: Mapped[str] = mapped_column(String(20))
    pattern: Mapped[str] = mapped_column(String(20))
    fabric: Mapped[str] = mapped_column(String(20))
    silhouette: Mapped[str] = mapped_column(String(20))
    length: Mapped[str] = mapped_column(String(20))
    neckline: Mapped[str] = mapped_column(String(20))
    sleeve: Mapped[str] = mapped_column(String(20))
    occasion_tags: Mapped[list] = mapped_column(JSON, default=list)
    style_tags: Mapped[list] = mapped_column(JSON, default=list)
    season: Mapped[str] = mapped_column(String(10))
    price_inr: Mapped[int] = mapped_column(Integer)
    mrp_inr: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(String(300))
    added_at: Mapped[datetime] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sizes: Mapped[list[ProductSize]] = relationship(order_by="ProductSize.position", cascade="all, delete-orphan",
                                                    lazy="selectin")


class ProductSize(Base):
    __tablename__ = "product_sizes"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    size: Mapped[str] = mapped_column(String(10), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    price_inr: Mapped[int] = mapped_column(Integer)
    mrp_inr: Mapped[int] = mapped_column(Integer)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StockEvent(Base):
    __tablename__ = "stock_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    size: Mapped[str] = mapped_column(String(10))
    delta: Mapped[int] = mapped_column(Integer)
    new_stock: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # initial | restock | sale | adjust
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", "size"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str] = mapped_column(String(10))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    product: Mapped[Product] = relationship(lazy="joined")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    total_inr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="placed")
    city: Mapped[str] = mapped_column(String(40))
    delivery_days: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    items: Mapped[list[OrderItem]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str] = mapped_column(String(10))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    price_inr: Mapped[int] = mapped_column(Integer)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # price_drop | restock | new_arrival | order
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text, default="")
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    hanger_id: Mapped[int | None] = mapped_column(ForeignKey("hangers.id", ondelete="SET NULL"), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # product ids, actions, pending confirmations
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TasteSignal(Base):
    __tablename__ = "taste_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int | None] = mapped_column(ForeignKey("detected_pieces.id", ondelete="SET NULL"), nullable=True)
    weight: Mapped[float] = mapped_column(Float)  # +1 selected, negative when skipped
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Look(Base):
    """A saved mannequin outfit for a folder."""
    __tablename__ = "looks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), default="My look")
    placements: Mapped[list] = mapped_column(JSON, default=list)  # [{product_id, slot, hanger_id}]
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Event(Base):
    """Behaviour events; mirrored to BigQuery `wiw.events` when EVENTS_BACKEND=bigquery."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(30), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fabric: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(20), nullable=True)
    style_tags: Mapped[str | None] = mapped_column(String(200), nullable=True)  # comma-joined for portable SQL
    product_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    matched: Mapped[int | None] = mapped_column(Integer, nullable=True)
    covered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    covered_in_prefs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Mannequin(Base):
    """The display mannequin a shopper's looks are dressed on: body type and finish (skin tone)."""
    __tablename__ = "mannequins"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    body_type: Mapped[str] = mapped_column(String(20), default="slim")
    skin_tone: Mapped[str] = mapped_column(String(20), default="tan")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class WishlistItem(Base):
    """A product the shopper hearted in the Shop. Shows on their rail."""
    __tablename__ = "wishlist_items"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StorePurchase(Base):
    """An in-store (offline) purchase linked through the shopper's membership. Online purchases are Orders."""
    __tablename__ = "store_purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    size: Mapped[str] = mapped_column(String(10))
    price_inr: Mapped[int] = mapped_column(Integer)
    store_label: Mapped[str] = mapped_column(String(80))
    receipt: Mapped[str] = mapped_column(String(20))
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RailLook(Base):
    """A look saved on the rail's style board (pieces from everything the shopper owns, carted or saved)."""
    __tablename__ = "rail_looks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), default="My look")
    placements: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
