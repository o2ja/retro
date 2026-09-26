"""Business enums. Payment state and order state are deliberately separate."""

from enum import StrEnum


class InquiryStatus(StrEnum):
    """A purchase request is a conversation, not a transaction."""

    NEW = "NEW"
    CONTACTED = "CONTACTED"
    # Only set by recording a sale, which creates the linked order.
    SOLD = "SOLD"
    CLOSED = "CLOSED"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


# Allowed order status transitions. Anything not listed is rejected server-side.
ORDER_STATUS_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: frozenset(
        {OrderStatus.PAYMENT_CONFIRMED, OrderStatus.CANCELLED}
    ),
    # DELIVERED straight from paid/processing: a watch handed over in person.
    OrderStatus.PAYMENT_CONFIRMED: frozenset(
        {
            OrderStatus.PROCESSING,
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
        }
    ),
    OrderStatus.PROCESSING: frozenset(
        {
            OrderStatus.SHIPPED,
            OrderStatus.DELIVERED,
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
        }
    ),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED, OrderStatus.REFUNDED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}


class Availability(StrEnum):
    """Derived from inventory + publication state, never stored directly."""

    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    SOLD = "SOLD"
    HIDDEN = "HIDDEN"


class InventoryReason(StrEnum):
    INITIAL_STOCK = "INITIAL_STOCK"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    RETURN = "RETURN"
    RESTOCK = "RESTOCK"


class DiscountType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class PostStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class HomepageSectionType(StrEnum):
    HERO = "HERO"
    FEATURED_PRODUCTS = "FEATURED_PRODUCTS"
    NEW_ARRIVALS = "NEW_ARRIVALS"
    CATEGORIES = "CATEGORIES"
    BRAND_STORY = "BRAND_STORY"
    FEATURED_PRODUCT = "FEATURED_PRODUCT"
    EDITORIAL = "EDITORIAL"
    OFFERS = "OFFERS"
    JOURNAL = "JOURNAL"
    SOCIAL = "SOCIAL"
    NEWSLETTER = "NEWSLETTER"


class ProductCondition(StrEnum):
    NEW = "NEW"
    UNWORN = "UNWORN"
    EXCELLENT = "EXCELLENT"
    VERY_GOOD = "VERY_GOOD"
    GOOD = "GOOD"
