"""Dashboard analytics.

Every figure comes from SQL aggregation over real rows. Nothing is estimated,
extrapolated or filled in: with no paid orders, the dashboard reports zero and
the charts render their empty state. "Best selling" means units in orders whose
payment is PAID, and nothing else.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, PaymentStatus
from app.db import utcnow
from app.models import (
    Brand,
    Category,
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductCategory,
)

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class DateRange:
    start: datetime
    end: datetime

    @property
    def days(self) -> int:
        return max((self.end.date() - self.start.date()).days + 1, 1)


def resolve_range(
    preset: str | None, start: datetime | None, end: datetime | None
) -> DateRange:
    """Turn a preset (or an explicit custom range) into concrete bounds."""
    now = utcnow()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if preset == "custom" and start and end:
        return DateRange(start=start, end=end)

    starts = {
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "week": now - timedelta(days=6),
        "month": now - timedelta(days=29),
        "year": now - timedelta(days=364),
    }
    begin = starts.get(preset or "month", starts["month"])
    return DateRange(
        start=begin.replace(hour=0, minute=0, second=0, microsecond=0), end=end_of_day
    )


def _paid_orders(window: DateRange) -> Select:
    return select(Order).where(
        Order.payment_status == PaymentStatus.PAID,
        Order.order_status != OrderStatus.REFUNDED,
        Order.created_at >= window.start,
        Order.created_at <= window.end,
    )


def _as_money(value: object) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


def _fill_days(rows: dict[str, Decimal | int], window: DateRange) -> list[dict]:
    """One point per day in the range, so a quiet day reads as 0, not as a gap."""
    points: list[dict] = []
    cursor: date = window.start.date()
    last: date = window.end.date()
    while cursor <= last:
        key = cursor.isoformat()
        points.append({"date": key, "value": rows.get(key, 0)})
        cursor += timedelta(days=1)
    return points


def _day(column) -> object:  # noqa: ANN001
    # func.date works on both SQLite and PostgreSQL.
    return func.date(column)


def dashboard(db: Session, window: DateRange) -> dict:
    paid = _paid_orders(window).subquery()

    revenue = _as_money(db.execute(select(func.sum(paid.c.total))).scalar())
    order_count = db.execute(select(func.count()).select_from(paid)).scalar_one()
    average_order_value = (
        (revenue / order_count).quantize(Decimal("0.01")) if order_count else ZERO
    )

    new_customers = db.execute(
        select(func.count(Customer.id)).where(
            Customer.created_at >= window.start, Customer.created_at <= window.end
        )
    ).scalar_one()

    # Counters that describe "right now", not the selected window.
    totals = {
        "customers": db.execute(select(func.count(Customer.id))).scalar_one(),
        "products": db.execute(
            select(func.count(Product.id)).where(Product.active.is_(True))
        ).scalar_one(),
        "low_stock": db.execute(
            select(func.count(Inventory.id))
            .join(Product, Product.id == Inventory.product_id)
            .where(
                Product.is_unique.is_(False),
                Inventory.quantity <= Inventory.low_stock_threshold,
            )
        ).scalar_one(),
        "out_of_stock": db.execute(
            select(func.count(Inventory.id)).where(Inventory.quantity <= 0)
        ).scalar_one(),
        "pending_payments": db.execute(
            select(func.count(Order.id)).where(
                Order.payment_status.in_(
                    [PaymentStatus.PENDING, PaymentStatus.AUTHORIZED]
                )
            )
        ).scalar_one(),
        "pending_orders": db.execute(
            select(func.count(Order.id)).where(
                Order.order_status.in_(
                    [OrderStatus.PAYMENT_CONFIRMED, OrderStatus.PROCESSING]
                )
            )
        ).scalar_one(),
    }

    revenue_rows = {
        str(day): _as_money(total)
        for day, total in db.execute(
            select(_day(paid.c.created_at), func.sum(paid.c.total)).group_by(
                _day(paid.c.created_at)
            )
        ).all()
    }
    order_rows = {
        str(day): int(count)
        for day, count in db.execute(
            select(_day(paid.c.created_at), func.count()).group_by(
                _day(paid.c.created_at)
            )
        ).all()
    }
    customer_rows = {
        str(day): int(count)
        for day, count in db.execute(
            select(_day(Customer.created_at), func.count())
            .where(Customer.created_at >= window.start, Customer.created_at <= window.end)
            .group_by(_day(Customer.created_at))
        ).all()
    }

    items = (
        select(
            OrderItem.product_id.label("product_id"),
            OrderItem.product_name_snapshot.label("name"),
            func.sum(OrderItem.quantity).label("units"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(paid, paid.c.id == OrderItem.order_id)
        .group_by(OrderItem.product_id, OrderItem.product_name_snapshot)
        .subquery()
    )

    best_selling = [
        {"label": name, "units": int(units), "revenue": str(_as_money(rev))}
        for _, name, units, rev in db.execute(
            select(items.c.product_id, items.c.name, items.c.units, items.c.revenue)
            .order_by(items.c.units.desc())
            .limit(8)
        ).all()
    ]

    by_brand = [
        {"label": name, "revenue": str(_as_money(rev))}
        for name, rev in db.execute(
            select(Brand.name, func.sum(items.c.revenue))
            .join(Product, Product.id == items.c.product_id)
            .join(Brand, Brand.id == Product.brand_id)
            .group_by(Brand.name)
            .order_by(func.sum(items.c.revenue).desc())
            .limit(8)
        ).all()
    ]

    by_category = [
        {"label": name, "revenue": str(_as_money(rev))}
        for name, rev in db.execute(
            select(Category.name, func.sum(items.c.revenue))
            .join(ProductCategory, ProductCategory.product_id == items.c.product_id)
            .join(Category, Category.id == ProductCategory.category_id)
            .group_by(Category.name)
            .order_by(func.sum(items.c.revenue).desc())
            .limit(8)
        ).all()
    ]

    recent_orders = list(
        db.execute(
            select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(8)
        )
        .scalars()
        .all()
    )
    recent_customers = list(
        db.execute(
            select(Customer)
            .order_by(Customer.created_at.desc(), Customer.id.desc())
            .limit(8)
        )
        .scalars()
        .all()
    )
    low_stock_products = list(
        db.execute(
            select(Product)
            .join(Inventory, Inventory.product_id == Product.id)
            .where(
                Product.is_unique.is_(False),
                Inventory.quantity <= Inventory.low_stock_threshold,
            )
            .order_by(Inventory.quantity)
            .limit(8)
        )
        .scalars()
        .all()
    )

    return {
        "range": {"start": window.start, "end": window.end, "days": window.days},
        "kpis": {
            "revenue": str(revenue),
            "orders": order_count,
            "average_order_value": str(average_order_value),
            "new_customers": new_customers,
            **totals,
        },
        "revenue_series": _fill_days(revenue_rows, window),
        "orders_series": _fill_days(order_rows, window),
        "customer_series": _fill_days(customer_rows, window),
        "sales_by_category": by_category,
        "sales_by_brand": by_brand,
        "best_selling_products": best_selling,
        "recent_orders": recent_orders,
        "recent_customers": recent_customers,
        "low_stock_products": low_stock_products,
    }
