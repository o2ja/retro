"""Admin orders, inquiries, customers and promotions."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentAdmin, DbSession
from app.core.enums import InquiryStatus, OrderStatus, PaymentStatus
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.utils import paginate
from app.models import Category, Customer, Inquiry, Order, Product, Promotion
from app.payments import get_provider
from app.schemas import (
    CustomerDetailOut,
    CustomerOut,
    DashboardOut,
    InquiryOut,
    InquiryStatusIn,
    MessageOut,
    OrderDetailOut,
    OrderStatusUpdateIn,
    OrderSummaryOut,
    Page,
    PaymentRecordIn,
    PromotionIn,
    PromotionOut,
    PromotionUpdate,
    RefundIn,
    SaleIn,
)
from app.services import analytics, audit, fulfilment
from app.services import orders as order_service

router = APIRouter(prefix="/api/admin", tags=["admin:commerce"])


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #


def _order_detail_query():  # noqa: ANN202
    return select(Order).options(
        selectinload(Order.items),
        selectinload(Order.payments),
        selectinload(Order.status_history),
    )


@router.get("/orders", response_model=Page[OrderSummaryOut])
def list_orders(
    db: DbSession,
    admin: CurrentAdmin,
    q: Annotated[str | None, Query(max_length=120)] = None,
    order_status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[OrderSummaryOut]:
    stmt = select(Order)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Order.order_number).like(pattern),
                func.lower(Order.shipping_name).like(pattern),
                func.lower(Order.shipping_email).like(pattern),
            )
        )
    if order_status:
        stmt = stmt.where(Order.order_status == order_status)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc())

    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[OrderSummaryOut.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{order_number}", response_model=OrderDetailOut)
def get_order(db: DbSession, admin: CurrentAdmin, order_number: str) -> Order:
    order = (
        db.execute(_order_detail_query().where(Order.order_number == order_number))
        .unique()
        .scalar_one_or_none()
    )
    if order is None:
        raise NotFoundError("Order not found")
    return order


@router.patch("/orders/{order_number}/status", response_model=OrderDetailOut)
def update_order_status(
    db: DbSession,
    admin: CurrentAdmin,
    order_number: str,
    payload: OrderStatusUpdateIn,
) -> Order:
    """Only transitions allowed by the workflow are accepted."""
    order = (
        db.execute(_order_detail_query().where(Order.order_number == order_number))
        .unique()
        .scalar_one_or_none()
    )
    if order is None:
        raise NotFoundError("Order not found")
    if payload.order_status is OrderStatus.PAYMENT_CONFIRMED:
        # Paid is a payment fact, not a status to pick: it must go through
        # record_payment so the payment row and revenue figures agree.
        raise ConflictError("Use 'Record payment' to mark an order paid.")

    order_service.transition(
        db,
        order,
        payload.order_status,
        admin_user_id=admin.id,
        note=payload.note,
    )
    if payload.order_status is OrderStatus.CANCELLED:
        # The watch is back in stock, so the conversation that sold it reopens.
        for inquiry in db.execute(
            select(Inquiry).where(Inquiry.order_id == order.id)
        ).scalars():
            inquiry.status = InquiryStatus.CONTACTED
            inquiry.order_id = None
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_number}/payments", response_model=OrderDetailOut)
def record_payment(
    db: DbSession, admin: CurrentAdmin, order_number: str, payload: PaymentRecordIn
) -> Order:
    """Record money taken in person or by transfer."""
    order = fulfilment.find_order(db, order_number)
    if order is None:
        raise NotFoundError("Order not found")
    fulfilment.record_offline_payment(db, order, payload.method, payload.reference)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="order.payment_recorded",
        entity_type="order",
        entity_id=order.id,
        summary=f"{payload.method} {order.total} {order.currency}",
    )
    db.commit()
    return (
        db.execute(_order_detail_query().where(Order.id == order.id))
        .unique()
        .scalar_one()
    )


# --------------------------------------------------------------------------- #
# Inquiries
# --------------------------------------------------------------------------- #


@router.get("/inquiries", response_model=Page[InquiryOut])
def list_inquiries(
    db: DbSession,
    admin: CurrentAdmin,
    status_filter: Annotated[InquiryStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[InquiryOut]:
    stmt = select(Inquiry)
    if status_filter is not None:
        stmt = stmt.where(Inquiry.status == status_filter)
    stmt = stmt.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[InquiryOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/inquiries/{inquiry_id}", response_model=InquiryOut)
def update_inquiry(
    db: DbSession, admin: CurrentAdmin, inquiry_id: int, payload: InquiryStatusIn
) -> Inquiry:
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFoundError("Inquiry not found")
    if payload.status is InquiryStatus.SOLD:
        raise ConflictError("Use 'Record sale' so the order is created with it.")
    if inquiry.status is InquiryStatus.SOLD:
        raise ConflictError("This request became a sale. Cancel the order to reopen it.")
    inquiry.status = payload.status
    audit.record(
        db,
        admin_user_id=admin.id,
        action="inquiry.status",
        entity_type="inquiry",
        entity_id=inquiry.id,
        summary=f"Marked {payload.status.value.lower()}",
    )
    db.commit()
    db.refresh(inquiry)
    return inquiry


@router.post(
    "/inquiries/{inquiry_id}/sale",
    response_model=InquiryOut,
    status_code=status.HTTP_201_CREATED,
)
def record_sale(
    db: DbSession, admin: CurrentAdmin, inquiry_id: int, payload: SaleIn
) -> Inquiry:
    """Close a request as sold: creates the order, holds the watch, and
    optionally records the payment in the same step."""
    inquiry = db.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFoundError("Inquiry not found")
    if inquiry.status is InquiryStatus.SOLD:
        raise ConflictError("This request is already recorded as a sale.")

    product_id = payload.product_id or inquiry.product_id
    if product_id is None:
        raise AppError("Choose which watch was sold.", code="product_required")
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")

    order = fulfilment.open_sale(db, inquiry, product, payload.price, payload.note)
    if payload.payment:
        fulfilment.record_offline_payment(
            db, order, payload.payment.method, payload.payment.reference
        )
    inquiry.status = InquiryStatus.SOLD
    inquiry.order_id = order.id
    audit.record(
        db,
        admin_user_id=admin.id,
        action="inquiry.sold",
        entity_type="order",
        entity_id=order.id,
        summary=f"{product.name} to {inquiry.full_name}, {order.total} {order.currency}",
    )
    db.commit()
    db.refresh(inquiry)
    return inquiry


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #


@router.get("/customers", response_model=Page[CustomerOut])
def list_customers(
    db: DbSession,
    admin: CurrentAdmin,
    q: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[CustomerOut]:
    stmt = select(Customer)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Customer.email).like(pattern),
                func.lower(func.coalesce(Customer.full_name, "")).like(pattern),
                func.lower(func.coalesce(Customer.phone, "")).like(pattern),
            )
        )
    stmt = stmt.order_by(Customer.created_at.desc(), Customer.id.desc())
    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[CustomerOut.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
def get_customer(
    db: DbSession, admin: CurrentAdmin, customer_id: int
) -> CustomerDetailOut:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFoundError("Customer not found")

    customer_orders = list(
        db.execute(
            select(Order)
            .where(Order.customer_id == customer.id)
            .order_by(Order.created_at.desc())
        )
        .scalars()
        .all()
    )
    # Spend counts verified-paid orders only.
    total_spent = sum(
        (o.total for o in customer_orders if o.payment_status is PaymentStatus.PAID),
        Decimal("0.00"),
    )
    return CustomerDetailOut(
        **CustomerOut.model_validate(customer).model_dump(),
        order_count=len(customer_orders),
        total_spent=total_spent,
        orders=[OrderSummaryOut.model_validate(o) for o in customer_orders],
    )


# --------------------------------------------------------------------------- #
# Promotions
# --------------------------------------------------------------------------- #


def _load_promotion(db, promotion_id: int) -> Promotion:  # noqa: ANN001
    promotion = (
        db.execute(
            select(Promotion)
            .options(selectinload(Promotion.products), selectinload(Promotion.categories))
            .where(Promotion.id == promotion_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if promotion is None:
        raise NotFoundError("Promotion not found")
    return promotion


def _resolve(db, model, ids: list[int]):  # noqa: ANN001, ANN202
    if not ids:
        return []
    rows = list(db.execute(select(model).where(model.id.in_(ids))).scalars().all())
    missing = set(ids) - {r.id for r in rows}
    if missing:
        raise NotFoundError(f"Unknown {model.__name__} ids: {sorted(missing)}")
    return rows


@router.get("/promotions", response_model=list[PromotionOut])
def list_promotions(db: DbSession, admin: CurrentAdmin) -> list[PromotionOut]:
    promotions = (
        db.execute(
            select(Promotion)
            .options(selectinload(Promotion.products), selectinload(Promotion.categories))
            .order_by(Promotion.active.desc(), Promotion.id.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    return [PromotionOut.build(p) for p in promotions]


@router.post(
    "/promotions", response_model=PromotionOut, status_code=status.HTTP_201_CREATED
)
def create_promotion(
    db: DbSession, admin: CurrentAdmin, payload: PromotionIn
) -> PromotionOut:
    if (
        payload.code
        and db.execute(
            select(Promotion.id).where(func.upper(Promotion.code) == payload.code)
        ).first()
    ):
        raise ConflictError("A promotion with this code already exists.")

    promotion = Promotion(**payload.model_dump(exclude={"product_ids", "category_ids"}))
    promotion.products = _resolve(db, Product, payload.product_ids)
    promotion.categories = _resolve(db, Category, payload.category_ids)
    db.add(promotion)
    db.flush()
    audit.record(
        db,
        admin_user_id=admin.id,
        action="promotion.created",
        entity_type="promotion",
        entity_id=promotion.id,
        summary=promotion.name,
    )
    db.commit()
    return PromotionOut.build(_load_promotion(db, promotion.id))


@router.patch("/promotions/{promotion_id}", response_model=PromotionOut)
def update_promotion(
    db: DbSession, admin: CurrentAdmin, promotion_id: int, payload: PromotionUpdate
) -> PromotionOut:
    promotion = _load_promotion(db, promotion_id)
    changes = payload.model_dump(exclude_unset=True)

    if "product_ids" in changes:
        promotion.products = _resolve(db, Product, changes.pop("product_ids") or [])
    if "category_ids" in changes:
        promotion.categories = _resolve(db, Category, changes.pop("category_ids") or [])
    for field, value in changes.items():
        setattr(promotion, field, value)

    # Re-validate the merged state, not just the submitted fields.
    if (
        promotion.starts_at
        and promotion.ends_at
        and promotion.ends_at <= promotion.starts_at
    ):
        raise ConflictError("ends_at must be after starts_at.")

    audit.record(
        db,
        admin_user_id=admin.id,
        action="promotion.updated",
        entity_type="promotion",
        entity_id=promotion.id,
        summary=", ".join(sorted(changes)) or "targeting",
    )
    db.commit()
    return PromotionOut.build(_load_promotion(db, promotion_id))


@router.delete("/promotions/{promotion_id}", response_model=MessageOut)
def deactivate_promotion(
    db: DbSession, admin: CurrentAdmin, promotion_id: int
) -> MessageOut:
    """Promotions are deactivated, never deleted: past orders reference them."""
    promotion = _load_promotion(db, promotion_id)
    promotion.active = False
    audit.record(
        db,
        admin_user_id=admin.id,
        action="promotion.deactivated",
        entity_type="promotion",
        entity_id=promotion.id,
        summary=promotion.name,
    )
    db.commit()
    return MessageOut(message="Promotion deactivated.")


# --------------------------------------------------------------------------- #
# Dashboard & refunds
# --------------------------------------------------------------------------- #


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: DbSession,
    admin: CurrentAdmin,
    range: Annotated[str, Query(pattern="^(today|week|month|year|custom)$")] = "month",
    start: datetime | None = None,
    end: datetime | None = None,
) -> DashboardOut:
    """Every figure is aggregated from real rows; nothing is estimated."""
    if range == "custom" and (start is None or end is None):
        raise AppError("A custom range needs both start and end.", code="invalid_range")
    window = analytics.resolve_range(range, start, end)
    return DashboardOut.build(analytics.dashboard(db, window))


@router.post("/orders/{order_number}/refund", response_model=OrderDetailOut)
def refund_order(
    db: DbSession, admin: CurrentAdmin, order_number: str, payload: RefundIn
) -> Order:
    """Refund through the payment provider, then record what it actually did.

    The order is only marked refunded once the provider confirms it; there is no
    way to mark a refund from the dashboard alone.
    """
    order = fulfilment.find_order(db, order_number)
    if order is None:
        raise NotFoundError("Order not found")
    if order.payment_status is not PaymentStatus.PAID:
        raise ConflictError("Only a paid order can be refunded.")

    payment = next((p for p in order.payments if p.status is PaymentStatus.PAID), None)
    if payment is None or not payment.provider_payment_id:
        raise ConflictError("No completed payment to refund.")

    verification = get_provider(payment.provider).refund(
        payment.provider_payment_id, payload.amount or order.total
    )
    fulfilment.confirm_payment(db, order, payment.provider, verification)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="order.refunded",
        entity_type="order",
        entity_id=order.id,
        summary=payload.reason or "Refund issued",
    )
    db.commit()
    db.refresh(order)
    return order
