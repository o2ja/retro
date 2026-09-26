"""Pydantic v2 request/response contracts.

Response models also own the mapping from ORM object to payload, so the API
layer stays thin and no endpoint can accidentally leak an internal column.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.core.enums import (
    Availability,
    DiscountType,
    HomepageSectionType,
    InquiryStatus,
    InventoryReason,
    OrderStatus,
    PaymentStatus,
    PostStatus,
    ProductCondition,
)
from app.services.inventory import availability as derive_availability
from app.services.pricing import ProductPricing

Slug = Annotated[
    str, Field(min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


class MessageOut(BaseModel):
    message: str


# --------------------------------------------------------------------------- #
# Public catalog
# --------------------------------------------------------------------------- #


class BrandOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None


class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None


class ProductImageOut(ORMModel):
    id: int
    url: str
    alt_text: str | None = None
    sort_order: int
    is_primary: bool


class PriceOut(BaseModel):
    """Server-calculated pricing. The client renders these numbers, never derives them."""

    currency: str
    price: Decimal | None
    compare_at_price: Decimal | None
    estimated_market_price: Decimal | None
    discount_amount: Decimal
    final_price: Decimal | None
    discount_percent: int | None
    promotion_name: str | None
    price_on_request: bool

    @classmethod
    def build(cls, currency: str, pricing: ProductPricing) -> PriceOut:
        return cls(currency=currency, **pricing.__dict__)


class ProductSummaryOut(BaseModel):
    id: int
    name: str
    slug: str
    short_description: str | None
    brand: BrandOut | None
    primary_image: ProductImageOut | None
    pricing: PriceOut
    availability: Availability
    featured: bool
    new_arrival: bool
    condition: ProductCondition | None
    # The watch alone on a transparent background, for the wrist stage.
    cutout_url: str | None = None

    @classmethod
    def build(cls, product, pricing: ProductPricing) -> ProductSummaryOut:  # noqa: ANN001
        primary = next(
            (i for i in product.images if i.is_primary),
            product.images[0] if product.images else None,
        )
        return cls(
            id=product.id,
            name=product.name,
            slug=product.slug,
            short_description=product.short_description,
            brand=BrandOut.model_validate(product.brand) if product.brand else None,
            primary_image=(ProductImageOut.model_validate(primary) if primary else None),
            pricing=PriceOut.build(product.currency, pricing),
            availability=derive_availability(product),
            featured=product.featured,
            new_arrival=product.new_arrival,
            condition=product.condition,
            cutout_url=product.cutout_url,
        )


class ProductSpecificationsOut(BaseModel):
    """Only populated fields are returned, so the UI never renders empty rows."""

    model_config = ConfigDict(extra="forbid")

    reference_number: str | None = None
    sku: str | None = None
    condition: ProductCondition | None = None
    production_year: int | None = None
    movement: str | None = None
    case_material: str | None = None
    case_size: str | None = None
    dial: str | None = None
    crystal: str | None = None
    strap_material: str | None = None
    water_resistance: str | None = None
    included_items: str | None = None
    limited_edition: str | None = None


class ProductDetailOut(ProductSummaryOut):
    description: str | None
    images: list[ProductImageOut]
    categories: list[CategoryOut]
    specifications: ProductSpecificationsOut
    warranty_information: str | None
    shipping_information: str | None
    stock_quantity: int
    related: list[ProductSummaryOut] = []

    @classmethod
    def build_detail(  # noqa: ANN001
        cls, product, pricing: ProductPricing, related: list[ProductSummaryOut]
    ) -> ProductDetailOut:
        summary = ProductSummaryOut.build(product, pricing)
        return cls(
            **summary.model_dump(),
            description=product.description,
            images=[ProductImageOut.model_validate(i) for i in product.images],
            categories=[CategoryOut.model_validate(c) for c in product.categories],
            specifications=ProductSpecificationsOut(
                reference_number=product.reference_number,
                sku=product.sku,
                condition=product.condition,
                production_year=product.production_year,
                movement=product.movement,
                case_material=product.case_material,
                case_size=product.case_size,
                dial=product.dial,
                crystal=product.crystal,
                strap_material=product.strap_material,
                water_resistance=product.water_resistance,
                included_items=product.included_items,
                limited_edition=product.limited_edition,
            ),
            warranty_information=product.warranty_information,
            shipping_information=product.shipping_information,
            stock_quantity=product.inventory.quantity if product.inventory else 0,
            related=related,
        )


# --------------------------------------------------------------------------- #
# Public content
# --------------------------------------------------------------------------- #


class PostSummaryOut(ORMModel):
    id: int
    title: str
    slug: str
    excerpt: str | None = None
    cover_image_url: str | None = None
    category: str | None = None
    author_name: str | None = None
    featured: bool
    published_at: datetime | None = None


class PostDetailOut(PostSummaryOut):
    content: str | None = None


class SocialLinkOut(ORMModel):
    platform: str
    label: str | None = None
    url: str


class BannerOut(ORMModel):
    id: int
    title: str
    description: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    cta_url: str | None = None


class HomepageSectionOut(ORMModel):
    section_type: HomepageSectionType
    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    image_url: str | None = None
    cta_label: str | None = None
    cta_url: str | None = None
    sort_order: int


class SiteSettingsOut(ORMModel):
    brand_name: str
    owner_name: str | None = None
    tagline: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    currency: str
    shipping_information: str | None = None
    return_policy: str | None = None
    warranty_information: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None


class OfferOut(BaseModel):
    id: int
    name: str
    description: str | None
    discount_type: DiscountType
    discount_value: Decimal
    ends_at: datetime | None
    products: list[ProductSummaryOut]


class HomepageOut(BaseModel):
    sections: list[HomepageSectionOut]
    banners: list[BannerOut]
    featured_products: list[ProductSummaryOut]
    new_arrivals: list[ProductSummaryOut]
    latest_posts: list[PostSummaryOut]


# --------------------------------------------------------------------------- #
# Admin: auth
# --------------------------------------------------------------------------- #


class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class AdminMeOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    last_login_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Admin: catalog
# --------------------------------------------------------------------------- #


class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: Slug | None = None
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    active: bool = True
    sort_order: int = 0


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: Slug | None = None
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    sort_order: int | None = None


class AdminBrandOut(BrandOut):
    active: bool
    sort_order: int
    product_count: int = 0


class CategoryIn(BrandIn):
    image_url: str | None = Field(default=None, max_length=500)
    logo_url: None = None


class CategoryUpdate(BrandUpdate):
    image_url: str | None = Field(default=None, max_length=500)
    logo_url: None = None


class AdminCategoryOut(CategoryOut):
    active: bool
    sort_order: int
    product_count: int = 0


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: Slug | None = None
    brand_id: int | None = None
    category_ids: list[int] = []
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None

    price: NonNegativeMoney | None = None
    compare_at_price: NonNegativeMoney | None = None
    estimated_market_price: NonNegativeMoney | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)

    sku: str = Field(min_length=1, max_length=64)
    reference_number: str | None = Field(default=None, max_length=64)

    condition: ProductCondition | None = None
    production_year: int | None = Field(default=None, ge=1900, le=2100)
    movement: str | None = Field(default=None, max_length=120)
    case_material: str | None = Field(default=None, max_length=120)
    case_size: str | None = Field(default=None, max_length=60)
    dial: str | None = Field(default=None, max_length=120)
    crystal: str | None = Field(default=None, max_length=120)
    strap_material: str | None = Field(default=None, max_length=120)
    water_resistance: str | None = Field(default=None, max_length=60)
    included_items: str | None = Field(default=None, max_length=255)
    limited_edition: str | None = Field(default=None, max_length=160)
    warranty_information: str | None = None
    shipping_information: str | None = None
    instagram_post_url: str | None = Field(default=None, max_length=500)
    cutout_url: str | None = Field(default=None, max_length=500)

    is_unique: bool = True
    active: bool = True
    featured: bool = False
    new_arrival: bool = False

    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=1, ge=0)

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, value: str) -> str:
        return value.upper()


class ProductUpdate(BaseModel):
    """Every field optional: PATCH semantics, only what is sent is changed."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: Slug | None = None
    brand_id: int | None = None
    category_ids: list[int] | None = None
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    price: NonNegativeMoney | None = None
    compare_at_price: NonNegativeMoney | None = None
    estimated_market_price: NonNegativeMoney | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    reference_number: str | None = Field(default=None, max_length=64)
    condition: ProductCondition | None = None
    production_year: int | None = Field(default=None, ge=1900, le=2100)
    movement: str | None = Field(default=None, max_length=120)
    case_material: str | None = Field(default=None, max_length=120)
    case_size: str | None = Field(default=None, max_length=60)
    dial: str | None = Field(default=None, max_length=120)
    crystal: str | None = Field(default=None, max_length=120)
    strap_material: str | None = Field(default=None, max_length=120)
    water_resistance: str | None = Field(default=None, max_length=60)
    included_items: str | None = Field(default=None, max_length=255)
    limited_edition: str | None = Field(default=None, max_length=160)
    warranty_information: str | None = None
    shipping_information: str | None = None
    instagram_post_url: str | None = Field(default=None, max_length=500)
    cutout_url: str | None = Field(default=None, max_length=500)
    is_unique: bool | None = None
    active: bool | None = None
    featured: bool | None = None
    new_arrival: bool | None = None


class ProductImageIn(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=255)
    sort_order: int = 0
    is_primary: bool = False


_EDITABLE_TEXT = (
    "short_description",
    "description",
    "reference_number",
    "production_year",
    "movement",
    "case_material",
    "case_size",
    "dial",
    "crystal",
    "strap_material",
    "water_resistance",
    "included_items",
    "limited_edition",
    "warranty_information",
    "shipping_information",
    "instagram_post_url",
    "cutout_url",
)


class AdminProductOut(BaseModel):
    id: int
    name: str
    slug: str
    sku: str
    # Everything the edit form shows, so saving it never blanks a field it didn't load.
    short_description: str | None = None
    description: str | None = None
    reference_number: str | None = None
    condition: ProductCondition | None = None
    production_year: int | None = None
    movement: str | None = None
    case_material: str | None = None
    case_size: str | None = None
    dial: str | None = None
    crystal: str | None = None
    strap_material: str | None = None
    water_resistance: str | None = None
    included_items: str | None = None
    limited_edition: str | None = None
    warranty_information: str | None = None
    shipping_information: str | None = None
    instagram_post_url: str | None = None
    cutout_url: str | None = None
    brand: BrandOut | None
    categories: list[CategoryOut]
    price: Decimal | None
    compare_at_price: Decimal | None
    estimated_market_price: Decimal | None
    currency: str
    stock_quantity: int
    low_stock_threshold: int
    availability: Availability
    active: bool
    featured: bool
    new_arrival: bool
    is_unique: bool
    primary_image: ProductImageOut | None
    updated_at: datetime

    @classmethod
    def build(cls, product) -> AdminProductOut:  # noqa: ANN001
        primary = next(
            (i for i in product.images if i.is_primary),
            product.images[0] if product.images else None,
        )
        return cls(
            id=product.id,
            name=product.name,
            slug=product.slug,
            sku=product.sku,
            **{field: getattr(product, field) for field in _EDITABLE_TEXT},
            condition=product.condition,
            brand=BrandOut.model_validate(product.brand) if product.brand else None,
            categories=[CategoryOut.model_validate(c) for c in product.categories],
            price=product.price,
            compare_at_price=product.compare_at_price,
            estimated_market_price=product.estimated_market_price,
            currency=product.currency,
            stock_quantity=product.inventory.quantity if product.inventory else 0,
            low_stock_threshold=(
                product.inventory.low_stock_threshold if product.inventory else 0
            ),
            availability=derive_availability(product),
            active=product.active,
            featured=product.featured,
            new_arrival=product.new_arrival,
            is_unique=product.is_unique,
            primary_image=ProductImageOut.model_validate(primary) if primary else None,
            updated_at=product.updated_at,
        )


# --------------------------------------------------------------------------- #
# Admin: inventory
# --------------------------------------------------------------------------- #


class InventorySetIn(BaseModel):
    quantity: int = Field(ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=255)


class InventoryAdjustIn(BaseModel):
    change: int = Field(description="Signed delta; negative removes stock")
    reason: InventoryReason = InventoryReason.MANUAL_ADJUSTMENT
    note: str | None = Field(default=None, max_length=255)

    @field_validator("change")
    @classmethod
    def _non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("change must not be zero")
        return value


class InventoryOut(BaseModel):
    product_id: int
    quantity: int
    low_stock_threshold: int
    availability: Availability
    updated_at: datetime


class InventoryTransactionOut(ORMModel):
    id: int
    product_id: int
    change_quantity: int
    quantity_after: int
    reason: InventoryReason
    reference_type: str | None = None
    reference_id: str | None = None
    note: str | None = None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Admin: promotions
# --------------------------------------------------------------------------- #


class PromotionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    discount_type: DiscountType
    discount_value: PositiveMoney
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    minimum_order_value: NonNegativeMoney | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    active: bool = True
    product_ids: list[int] = []
    category_ids: list[int] = []

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() or None if value else None

    @model_validator(mode="after")
    def _check_rules(self) -> PromotionIn:
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if (
            self.discount_type is DiscountType.PERCENTAGE
            and self.discount_value is not None
            and self.discount_value > 100
        ):
            raise ValueError("percentage discount cannot exceed 100")
        return self


class PromotionUpdate(PromotionIn):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    discount_type: DiscountType | None = None
    discount_value: PositiveMoney | None = None
    product_ids: list[int] | None = None
    category_ids: list[int] | None = None
    active: bool | None = None


class PromotionOut(ORMModel):
    id: int
    name: str
    code: str | None = None
    description: str | None = None
    discount_type: DiscountType
    discount_value: Decimal
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    minimum_order_value: Decimal | None = None
    usage_limit: int | None = None
    usage_count: int
    active: bool
    product_ids: list[int] = []
    category_ids: list[int] = []

    @classmethod
    def build(cls, promotion) -> PromotionOut:  # noqa: ANN001
        out = cls.model_validate(promotion)
        out.product_ids = [p.id for p in promotion.products]
        out.category_ids = [c.id for c in promotion.categories]
        return out


class PromotionCheckIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    subtotal: NonNegativeMoney


class PromotionCheckOut(BaseModel):
    valid: bool
    code: str
    name: str
    discount_amount: Decimal
    new_total: Decimal


# --------------------------------------------------------------------------- #
# Admin: orders & customers
# --------------------------------------------------------------------------- #


class OrderItemOut(ORMModel):
    id: int
    product_id: int | None = None
    product_name_snapshot: str
    brand_name_snapshot: str | None = None
    sku_snapshot: str
    reference_number_snapshot: str | None = None
    image_url_snapshot: str | None = None
    unit_price: Decimal
    quantity: int
    discount_amount: Decimal
    line_total: Decimal


class OrderStatusHistoryOut(ORMModel):
    from_status: OrderStatus | None = None
    to_status: OrderStatus
    note: str | None = None
    created_at: datetime


class PaymentOut(ORMModel):
    id: int
    provider: str
    provider_payment_id: str | None = None
    amount: Decimal
    currency: str
    status: PaymentStatus
    failure_reason: str | None = None
    created_at: datetime


class OrderSummaryOut(ORMModel):
    id: int
    order_number: str
    customer_id: int | None = None
    shipping_name: str
    shipping_email: EmailStr
    total: Decimal
    currency: str
    payment_status: PaymentStatus
    order_status: OrderStatus
    created_at: datetime


class OrderDetailOut(OrderSummaryOut):
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    promotion_code_snapshot: str | None = None
    shipping_phone: str | None = None
    shipping_address: str
    shipping_city: str
    shipping_country: str
    shipping_postal_code: str | None = None
    customer_note: str | None = None
    items: list[OrderItemOut]
    payments: list[PaymentOut]
    status_history: list[OrderStatusHistoryOut]


class OrderStatusUpdateIn(BaseModel):
    order_status: OrderStatus
    note: str | None = Field(default=None, max_length=255)


class CustomerOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str | None = None
    phone: str | None = None
    is_active: bool
    last_order_at: datetime | None = None
    created_at: datetime


class CustomerDetailOut(CustomerOut):
    order_count: int
    total_spent: Decimal
    orders: list[OrderSummaryOut]


# --------------------------------------------------------------------------- #
# Admin: content & settings
# --------------------------------------------------------------------------- #


class PostIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: Slug | None = None
    excerpt: str | None = Field(default=None, max_length=500)
    content: str | None = None
    cover_image_url: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=120)
    author_name: str | None = Field(default=None, max_length=160)
    status: PostStatus = PostStatus.DRAFT
    featured: bool = False
    published_at: datetime | None = None


class PostUpdate(PostIn):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: PostStatus | None = None
    featured: bool | None = None


class AdminPostOut(PostDetailOut):
    status: PostStatus
    updated_at: datetime


class HomepageSectionIn(BaseModel):
    section_type: HomepageSectionType
    title: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=255)
    body: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    cta_label: str | None = Field(default=None, max_length=120)
    cta_url: str | None = Field(default=None, max_length=500)
    visible: bool = True
    sort_order: int = 0


class AdminHomepageSectionOut(HomepageSectionOut):
    id: int
    visible: bool
    updated_at: datetime


class BannerIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    cta_label: str | None = Field(default=None, max_length=120)
    cta_url: str | None = Field(default=None, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True
    sort_order: int = 0


class AdminBannerOut(BannerOut):
    active: bool
    sort_order: int
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class SocialLinkIn(BaseModel):
    platform: str = Field(min_length=1, max_length=60)
    label: str | None = Field(default=None, max_length=120)
    url: str = Field(min_length=1, max_length=500)
    active: bool = True
    sort_order: int = 0


class AdminSocialLinkOut(SocialLinkOut):
    id: int
    active: bool
    sort_order: int


class SiteSettingsIn(BaseModel):
    """Non-secret settings only. Payment credentials stay in the environment."""

    model_config = ConfigDict(extra="forbid")

    brand_name: str | None = Field(default=None, min_length=1, max_length=160)
    owner_name: str | None = Field(default=None, max_length=160)
    tagline: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    favicon_url: str | None = Field(default=None, max_length=500)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    shipping_information: str | None = None
    return_policy: str | None = None
    warranty_information: str | None = None
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- #
# Checkout
# --------------------------------------------------------------------------- #


class CartLineIn(BaseModel):
    """All the client is trusted to send: what, and how many."""

    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=20)


class CheckoutQuoteIn(BaseModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=50)
    promotion_code: str | None = Field(default=None, max_length=64)


class QuoteLineOut(BaseModel):
    product_id: int
    slug: str
    name: str
    brand_name: str | None
    sku: str
    image_url: str | None
    unit_price: Decimal
    quantity: int
    discount_amount: Decimal
    line_total: Decimal
    availability: Availability


class QuoteIssueOut(BaseModel):
    product_id: int
    product_name: str | None = None
    code: str
    message: str


class CheckoutQuoteOut(BaseModel):
    """Server-calculated totals. The client displays these and computes nothing."""

    lines: list[QuoteLineOut]
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    total: Decimal
    currency: str
    promotion_code: str | None = None
    promotion_name: str | None = None
    issues: list[QuoteIssueOut] = []
    is_payable: bool

    @classmethod
    def build(cls, quote) -> CheckoutQuoteOut:  # noqa: ANN001
        return cls(
            lines=[QuoteLineOut(**line.__dict__) for line in quote.lines],
            subtotal=quote.subtotal,
            discount_total=quote.discount_total,
            shipping_total=quote.shipping_total,
            total=quote.total,
            currency=quote.currency,
            promotion_code=quote.promotion.code if quote.promotion else None,
            promotion_name=quote.promotion.name if quote.promotion else None,
            issues=[QuoteIssueOut(**i) for i in quote.issues],
            is_payable=quote.is_payable,
        )


class ShippingDetailsIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=160)
    country: str = Field(min_length=1, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=1000)


class PaymentSessionIn(CheckoutQuoteIn):
    shipping: ShippingDetailsIn


class PaymentSessionOut(BaseModel):
    provider: str
    provider_payment_id: str
    redirect_url: str | None = None
    client_secret: str | None = None
    order_number: str
    total: Decimal
    currency: str


class PublicOrderOut(BaseModel):
    """What a customer may see about their own order.

    No internal ids, no provider references, no payment credentials.
    """

    order_number: str
    placed_at: datetime
    payment_status: PaymentStatus
    order_status: OrderStatus
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    total: Decimal
    promotion_code: str | None = None
    shipping_name: str
    shipping_email: EmailStr
    shipping_address: str
    shipping_city: str
    shipping_country: str
    shipping_postal_code: str | None = None
    items: list[OrderItemOut]

    @classmethod
    def build(cls, order) -> PublicOrderOut:  # noqa: ANN001
        return cls(
            order_number=order.order_number,
            placed_at=order.created_at,
            payment_status=order.payment_status,
            order_status=order.order_status,
            currency=order.currency,
            subtotal=order.subtotal,
            discount_total=order.discount_total,
            shipping_total=order.shipping_total,
            total=order.total,
            promotion_code=order.promotion_code_snapshot,
            shipping_name=order.shipping_name,
            shipping_email=order.shipping_email,
            shipping_address=order.shipping_address,
            shipping_city=order.shipping_city,
            shipping_country=order.shipping_country,
            shipping_postal_code=order.shipping_postal_code,
            items=[OrderItemOut.model_validate(i) for i in order.items],
        )


# --------------------------------------------------------------------------- #
# Admin dashboard
# --------------------------------------------------------------------------- #


class SeriesPoint(BaseModel):
    date: str
    value: Decimal


class LabelledValue(BaseModel):
    label: str
    revenue: Decimal | None = None
    units: int | None = None


class DashboardKpis(BaseModel):
    revenue: Decimal
    orders: int
    average_order_value: Decimal
    new_customers: int
    customers: int
    products: int
    low_stock: int
    out_of_stock: int
    pending_payments: int
    pending_orders: int


class DashboardRange(BaseModel):
    start: datetime
    end: datetime
    days: int


class DashboardOut(BaseModel):
    range: DashboardRange
    kpis: DashboardKpis
    revenue_series: list[SeriesPoint]
    orders_series: list[SeriesPoint]
    customer_series: list[SeriesPoint]
    sales_by_category: list[LabelledValue]
    sales_by_brand: list[LabelledValue]
    best_selling_products: list[LabelledValue]
    recent_orders: list[OrderSummaryOut]
    recent_customers: list[CustomerOut]
    low_stock_products: list[AdminProductOut]

    @classmethod
    def build(cls, data: dict) -> DashboardOut:
        return cls(
            range=DashboardRange(**data["range"]),
            kpis=DashboardKpis(**data["kpis"]),
            revenue_series=[SeriesPoint(**p) for p in data["revenue_series"]],
            orders_series=[SeriesPoint(**p) for p in data["orders_series"]],
            customer_series=[SeriesPoint(**p) for p in data["customer_series"]],
            sales_by_category=[LabelledValue(**r) for r in data["sales_by_category"]],
            sales_by_brand=[LabelledValue(**r) for r in data["sales_by_brand"]],
            best_selling_products=[
                LabelledValue(**r) for r in data["best_selling_products"]
            ],
            recent_orders=[
                OrderSummaryOut.model_validate(o) for o in data["recent_orders"]
            ],
            recent_customers=[
                CustomerOut.model_validate(c) for c in data["recent_customers"]
            ],
            low_stock_products=[
                AdminProductOut.build(p) for p in data["low_stock_products"]
            ],
        )


class RefundIn(BaseModel):
    amount: PositiveMoney | None = None
    reason: str | None = Field(default=None, max_length=255)


SortOptionIn = Literal["featured", "newest", "price_asc", "price_desc", "best_selling"]


# --------------------------------------------------------------------------- #
# Inquiries
# --------------------------------------------------------------------------- #


class InquiryIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=40, pattern=r"^[0-9+()\-.\s]+$")
    product_id: int | None = None
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("full_name", "phone", "message", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class InquiryOut(ORMModel):
    id: int
    product_id: int | None = None
    product_name_snapshot: str | None = None
    full_name: str
    email: EmailStr
    phone: str
    message: str | None = None
    status: InquiryStatus
    order_number: str | None = None
    created_at: datetime


class InquiryStatusIn(BaseModel):
    status: InquiryStatus


class PaymentRecordIn(BaseModel):
    """A payment taken outside the website, attested by the admin recording it."""

    method: Literal["cash", "bank_transfer", "card_in_store"]
    reference: str | None = Field(default=None, max_length=160)


class SaleIn(BaseModel):
    """Turn a request into a sale. The price is what was actually agreed."""

    product_id: int | None = None
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment: PaymentRecordIn | None = None
    note: str | None = Field(default=None, max_length=2000)
