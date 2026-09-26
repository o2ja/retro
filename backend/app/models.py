"""ORM models for Obaidi Time.

Kept in one module on purpose: the schema is a single cohesive unit and the
relationships read better together than spread over twenty files.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    DiscountType,
    HomepageSectionType,
    InquiryStatus,
    InventoryReason,
    OrderStatus,
    PaymentStatus,
    PostStatus,
    ProductCondition,
)
from app.db import Base, Money, UTCDateTime


def _enum(python_enum: type) -> SAEnum:
    """Store enums as validated strings; avoids native PG enum migration pain."""
    return SAEnum(python_enum, native_enum=False, length=40, validate_strings=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_order_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    orders: Mapped[list[Order]] = relationship(back_populates="customer")


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #


class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    products: Mapped[list[Product]] = relationship(back_populates="brand")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    products: Mapped[list[Product]] = relationship(
        secondary="product_categories", back_populates="categories"
    )


class ProductCategory(Base):
    __tablename__ = "product_categories"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )


class Product(TimestampMixin, Base):
    """A watch listing.

    ``price`` is the admin-controlled selling price and is intentionally
    nullable: the initial catalog has no confirmed selling prices, and inventing
    one is forbidden. ``estimated_market_price`` is reference data only and is
    never used as the selling price.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "price IS NULL OR price >= 0", name="ck_products_price_non_negative"
        ),
        Index("ix_products_active_featured", "active", "featured"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    brand_id: Mapped[int | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"), index=True
    )

    short_description: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    price: Mapped[Decimal | None] = mapped_column(Money)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Money)
    estimated_market_price: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    reference_number: Mapped[str | None] = mapped_column(String(64), index=True)

    condition: Mapped[ProductCondition | None] = mapped_column(_enum(ProductCondition))
    production_year: Mapped[int | None] = mapped_column(Integer)
    movement: Mapped[str | None] = mapped_column(String(120))
    case_material: Mapped[str | None] = mapped_column(String(120))
    case_size: Mapped[str | None] = mapped_column(String(60))
    dial: Mapped[str | None] = mapped_column(String(120))
    crystal: Mapped[str | None] = mapped_column(String(120))
    strap_material: Mapped[str | None] = mapped_column(String(120))
    water_resistance: Mapped[str | None] = mapped_column(String(60))
    included_items: Mapped[str | None] = mapped_column(String(255))
    limited_edition: Mapped[str | None] = mapped_column(String(160))
    warranty_information: Mapped[str | None] = mapped_column(Text)
    shipping_information: Mapped[str | None] = mapped_column(Text)
    instagram_post_url: Mapped[str | None] = mapped_column(String(500))
    # Background-free image of the watch, shown on the homepage wrist.
    cutout_url: Mapped[str | None] = mapped_column(String(500))

    # One-of-a-kind pre-owned piece: at zero stock it reads SOLD, not restockable.
    is_unique: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    featured: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    new_arrival: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    brand: Mapped[Brand | None] = relationship(back_populates="products")
    categories: Mapped[list[Category]] = relationship(
        secondary="product_categories", back_populates="products"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
    )
    inventory: Mapped[Inventory | None] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(500))
    alt_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="images")


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), unique=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="inventory")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    change_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[InventoryReason] = mapped_column(_enum(InventoryReason))
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False, index=True
    )


# --------------------------------------------------------------------------- #
# Promotions
# --------------------------------------------------------------------------- #


class Promotion(TimestampMixin, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_promotions_discount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[DiscountType] = mapped_column(_enum(DiscountType))
    discount_value: Mapped[Decimal] = mapped_column(Money, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    minimum_order_value: Mapped[Decimal | None] = mapped_column(Money)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    products: Mapped[list[Product]] = relationship(secondary="promotion_products")
    categories: Mapped[list[Category]] = relationship(secondary="promotion_categories")


class PromotionProduct(Base):
    __tablename__ = "promotion_products"

    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )


class PromotionCategory(Base):
    __tablename__ = "promotion_categories"

    promotion_id: Mapped[int] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )


# --------------------------------------------------------------------------- #
# Orders & payments
# --------------------------------------------------------------------------- #


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_status_created", "order_status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )

    subtotal: Mapped[Decimal] = mapped_column(Money, nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(
        Money, nullable=False, default=Decimal("0")
    )
    shipping_total: Mapped[Decimal] = mapped_column(
        Money, nullable=False, default=Decimal("0")
    )
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    payment_status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True
    )
    order_status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus),
        default=OrderStatus.PENDING_PAYMENT,
        nullable=False,
        index=True,
    )

    promotion_id: Mapped[int | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="SET NULL")
    )
    promotion_code_snapshot: Mapped[str | None] = mapped_column(String(64))

    shipping_name: Mapped[str] = mapped_column(String(255))
    shipping_email: Mapped[str] = mapped_column(String(255))
    shipping_phone: Mapped[str | None] = mapped_column(String(40))
    shipping_address: Mapped[str] = mapped_column(String(500))
    shipping_city: Mapped[str] = mapped_column(String(160))
    shipping_country: Mapped[str] = mapped_column(String(120))
    shipping_postal_code: Mapped[str | None] = mapped_column(String(32))
    customer_note: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.id",
    )


class OrderItem(Base):
    """Purchase snapshot. Never reconstruct a past order from the live product row."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )

    product_name_snapshot: Mapped[str] = mapped_column(String(255))
    brand_name_snapshot: Mapped[str | None] = mapped_column(String(160))
    sku_snapshot: Mapped[str] = mapped_column(String(64))
    reference_number_snapshot: Mapped[str | None] = mapped_column(String(64))
    image_url_snapshot: Mapped[str | None] = mapped_column(String(500))

    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Money, nullable=False, default=Decimal("0")
    )
    line_total: Mapped[Decimal] = mapped_column(Money, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(TimestampMixin, Base):
    """Provider references only. Card data is never stored."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_payment_id", name="uq_payments_provider_ref"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(60))
    provider_payment_id: Mapped[str | None] = mapped_column(String(160), index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False, index=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    order: Mapped[Order] = relationship(back_populates="payments")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(_enum(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(_enum(OrderStatus))
    note: Mapped[str | None] = mapped_column(String(255))
    changed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="status_history")


# --------------------------------------------------------------------------- #
# Content / CMS
# --------------------------------------------------------------------------- #


class Post(TimestampMixin, Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    excerpt: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    author_name: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[PostStatus] = mapped_column(
        _enum(PostStatus), default=PostStatus.DRAFT, nullable=False, index=True
    )
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)


class HomepageSection(TimestampMixin, Base):
    """CMS-controlled homepage content: content and visibility, not app logic."""

    __tablename__ = "homepage_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_type: Mapped[HomepageSectionType] = mapped_column(
        _enum(HomepageSectionType), unique=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    subtitle: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    cta_label: Mapped[str | None] = mapped_column(String(120))
    cta_url: Mapped[str | None] = mapped_column(String(500))
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Banner(TimestampMixin, Base):
    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500))
    image_url: Mapped[str | None] = mapped_column(String(500))
    cta_label: Mapped[str | None] = mapped_column(String(120))
    cta_url: Mapped[str | None] = mapped_column(String(500))
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SocialLink(TimestampMixin, Base):
    __tablename__ = "social_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SiteSettings(TimestampMixin, Base):
    """Single row (id=1). Non-secret configuration only - never payment secrets."""

    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    brand_name: Mapped[str] = mapped_column(String(160), default="Retro Watches")
    owner_name: Mapped[str | None] = mapped_column(String(160))
    tagline: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    favicon_url: Mapped[str | None] = mapped_column(String(500))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(500))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    shipping_information: Mapped[str | None] = mapped_column(Text)
    return_policy: Mapped[str | None] = mapped_column(Text)
    warranty_information: Mapped[str | None] = mapped_column(Text)
    seo_title: Mapped[str | None] = mapped_column(String(255))
    seo_description: Mapped[str | None] = mapped_column(String(500))


class AuditLog(Base):
    """Meaningful admin/business actions. Never holds secrets or credentials."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, server_default=func.now(), nullable=False, index=True
    )


# --------------------------------------------------------------------------- #
# Inquiries: how a customer asks to buy. The owner follows up by hand.
# --------------------------------------------------------------------------- #


class Inquiry(TimestampMixin, Base):
    __tablename__ = "inquiries"
    __table_args__ = (Index("ix_inquiries_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    # Kept even if the product is renamed or deleted later.
    product_name_snapshot: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(40))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[InquiryStatus] = mapped_column(
        _enum(InquiryStatus), default=InquiryStatus.NEW, nullable=False
    )
    # The sale this request turned into, once one is recorded.
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )

    order: Mapped[Order | None] = relationship()

    @property
    def order_number(self) -> str | None:
        return self.order.order_number if self.order else None
