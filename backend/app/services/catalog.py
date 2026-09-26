"""Catalog querying: filters, sorting, pagination - one place, both APIs use it."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import PaymentStatus
from app.models import (
    Brand,
    Category,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductCategory,
)

SortOption = Literal["featured", "newest", "price_asc", "price_desc", "best_selling"]


@dataclass(frozen=True)
class CatalogFilters:
    search: str | None = None
    category_slug: str | None = None
    brand_slug: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False
    movement: str | None = None
    featured: bool | None = None
    new_arrival: bool | None = None
    sort: SortOption = "featured"


def product_query(*, published_only: bool) -> Select:
    stmt = select(Product).options(
        selectinload(Product.brand),
        selectinload(Product.categories),
        selectinload(Product.images),
        selectinload(Product.inventory),
    )
    if published_only:
        stmt = stmt.where(Product.active.is_(True))
    return stmt


def _best_selling_subquery():  # noqa: ANN202
    """Units sold, counted from real paid orders only. No sales, no ranking."""
    return (
        select(
            OrderItem.product_id.label("product_id"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("units_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.payment_status == PaymentStatus.PAID)
        .group_by(OrderItem.product_id)
        .subquery()
    )


def apply_filters(stmt: Select, filters: CatalogFilters) -> Select:
    if filters.search:
        pattern = f"%{filters.search.strip().lower()}%"
        stmt = stmt.outerjoin(Brand, Brand.id == Product.brand_id).where(
            or_(
                func.lower(Product.name).like(pattern),
                func.lower(Product.sku).like(pattern),
                func.lower(func.coalesce(Product.reference_number, "")).like(pattern),
                func.lower(func.coalesce(Brand.name, "")).like(pattern),
            )
        )
    if filters.brand_slug:
        stmt = stmt.where(
            Product.brand_id.in_(select(Brand.id).where(Brand.slug == filters.brand_slug))
        )
    if filters.category_slug:
        stmt = stmt.where(
            Product.id.in_(
                select(ProductCategory.product_id)
                .join(Category, Category.id == ProductCategory.category_id)
                .where(Category.slug == filters.category_slug)
            )
        )
    if filters.min_price is not None:
        stmt = stmt.where(Product.price.is_not(None), Product.price >= filters.min_price)
    if filters.max_price is not None:
        stmt = stmt.where(Product.price.is_not(None), Product.price <= filters.max_price)
    if filters.in_stock_only:
        stmt = stmt.where(
            Product.id.in_(select(Inventory.product_id).where(Inventory.quantity > 0))
        )
    if filters.movement:
        stmt = stmt.where(
            func.lower(func.coalesce(Product.movement, "")).like(
                f"%{filters.movement.strip().lower()}%"
            )
        )
    if filters.featured is not None:
        stmt = stmt.where(Product.featured.is_(filters.featured))
    if filters.new_arrival is not None:
        stmt = stmt.where(Product.new_arrival.is_(filters.new_arrival))
    return stmt


def apply_sort(stmt: Select, sort: SortOption) -> Select:
    match sort:
        case "newest":
            return stmt.order_by(Product.created_at.desc(), Product.id.desc())
        case "price_asc":
            return stmt.order_by(Product.price.is_(None), Product.price.asc())
        case "price_desc":
            return stmt.order_by(Product.price.is_(None), Product.price.desc())
        case "best_selling":
            sold = _best_selling_subquery()
            return stmt.outerjoin(sold, sold.c.product_id == Product.id).order_by(
                func.coalesce(sold.c.units_sold, 0).desc(), Product.id.desc()
            )
        case _:
            return stmt.order_by(
                Product.featured.desc(), Product.created_at.desc(), Product.id.desc()
            )


def build_catalog_query(filters: CatalogFilters, *, published_only: bool) -> Select:
    return apply_sort(
        apply_filters(product_query(published_only=published_only), filters),
        filters.sort,
    )


def get_by_slug(db: Session, slug: str, *, published_only: bool) -> Product | None:
    stmt = product_query(published_only=published_only).where(Product.slug == slug)
    return db.execute(stmt).unique().scalar_one_or_none()


def related_products(db: Session, product: Product, limit: int = 4) -> list[Product]:
    """Same brand first, then anything else published. Never the product itself."""
    stmt = (
        product_query(published_only=True)
        .where(Product.id != product.id)
        .order_by((Product.brand_id == product.brand_id).desc(), Product.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).unique().scalars().all())
