"""Public storefront API. Read-only published data, plus the inquiry form."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession
from app.core import ratelimit
from app.core.enums import PostStatus
from app.core.errors import NotFoundError
from app.core.utils import paginate
from app.db import utcnow
from app.models import (
    Banner,
    Brand,
    Category,
    HomepageSection,
    Inquiry,
    Post,
    Product,
    SiteSettings,
    SocialLink,
)
from app.schemas import (
    BannerOut,
    BrandOut,
    CategoryOut,
    HomepageOut,
    HomepageSectionOut,
    InquiryIn,
    MessageOut,
    OfferOut,
    Page,
    PostDetailOut,
    PostSummaryOut,
    ProductDetailOut,
    ProductSummaryOut,
    PromotionCheckIn,
    PromotionCheckOut,
    SiteSettingsOut,
    SocialLinkOut,
    SortOptionIn,
)
from app.services import catalog, pricing

router = APIRouter(prefix="/api/public", tags=["public"])


def _summaries(db: Session, products: list[Product]) -> list[ProductSummaryOut]:
    """Price a batch of products against today's automatic promotions, once."""
    promotions = pricing.live_automatic_promotions(db)
    return [
        ProductSummaryOut.build(p, pricing.price_product(p, promotions)) for p in products
    ]


@router.get("/settings", response_model=SiteSettingsOut)
def get_settings(db: DbSession) -> SiteSettings:
    settings_row = db.get(SiteSettings, 1)
    if settings_row is None:
        raise NotFoundError("Site settings have not been configured yet")
    return settings_row


@router.get("/homepage", response_model=HomepageOut)
def get_homepage(db: DbSession) -> HomepageOut:
    """Everything the homepage renders, from the CMS - no hardcoded content."""
    now = utcnow()
    sections = (
        db.execute(
            select(HomepageSection)
            .where(HomepageSection.visible.is_(True))
            .order_by(HomepageSection.sort_order)
        )
        .scalars()
        .all()
    )
    banners = (
        db.execute(
            select(Banner)
            .where(
                Banner.active.is_(True),
                (Banner.starts_at.is_(None)) | (Banner.starts_at <= now),
                (Banner.ends_at.is_(None)) | (Banner.ends_at >= now),
            )
            .order_by(Banner.sort_order)
        )
        .scalars()
        .all()
    )
    featured = (
        db.execute(
            catalog.build_catalog_query(
                catalog.CatalogFilters(featured=True, sort="featured"),
                published_only=True,
            ).limit(8)
        )
        .unique()
        .scalars()
        .all()
    )
    new_arrivals = (
        db.execute(
            catalog.build_catalog_query(
                catalog.CatalogFilters(new_arrival=True, sort="newest"),
                published_only=True,
            ).limit(8)
        )
        .unique()
        .scalars()
        .all()
    )
    posts = (
        db.execute(
            select(Post)
            .where(Post.status == PostStatus.PUBLISHED)
            .order_by(Post.published_at.desc().nullslast(), Post.id.desc())
            .limit(3)
        )
        .scalars()
        .all()
    )
    return HomepageOut(
        sections=[HomepageSectionOut.model_validate(s) for s in sections],
        banners=[BannerOut.model_validate(b) for b in banners],
        featured_products=_summaries(db, list(featured)),
        new_arrivals=_summaries(db, list(new_arrivals)),
        latest_posts=[PostSummaryOut.model_validate(p) for p in posts],
    )


@router.get("/brands", response_model=list[BrandOut])
def list_brands(db: DbSession) -> list[Brand]:
    stmt = (
        select(Brand).where(Brand.active.is_(True)).order_by(Brand.sort_order, Brand.name)
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession) -> list[Category]:
    stmt = (
        select(Category)
        .where(Category.active.is_(True))
        .order_by(Category.sort_order, Category.name)
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/products", response_model=Page[ProductSummaryOut])
def list_products(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=160)] = None,
    brand: Annotated[str | None, Query(max_length=160)] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    in_stock: bool = False,
    movement: Annotated[str | None, Query(max_length=120)] = None,
    featured: bool | None = None,
    new_arrival: bool | None = None,
    sort: SortOptionIn = "featured",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=60)] = 12,
) -> Page[ProductSummaryOut]:
    filters = catalog.CatalogFilters(
        search=q,
        category_slug=category,
        brand_slug=brand,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock,
        movement=movement,
        featured=featured,
        new_arrival=new_arrival,
        sort=sort,
    )
    stmt = catalog.build_catalog_query(filters, published_only=True)
    items, total = paginate(db, stmt, page, page_size)
    return Page(items=_summaries(db, items), total=total, page=page, page_size=page_size)


@router.get("/products/{slug}", response_model=ProductDetailOut)
def get_product(db: DbSession, slug: str) -> ProductDetailOut:
    product = catalog.get_by_slug(db, slug, published_only=True)
    if product is None:
        raise NotFoundError("Product not found")
    promotions = pricing.live_automatic_promotions(db)
    related = _summaries(db, catalog.related_products(db, product))
    return ProductDetailOut.build_detail(
        product, pricing.price_product(product, promotions), related
    )


@router.get("/offers", response_model=list[OfferOut])
def list_offers(db: DbSession) -> list[OfferOut]:
    """Live automatic promotions and the published products they cover."""
    promotions = pricing.live_automatic_promotions(db)
    if not promotions:
        return []
    published = (
        db.execute(catalog.product_query(published_only=True)).unique().scalars().all()
    )
    offers: list[OfferOut] = []
    for promotion in promotions:
        matching = [p for p in published if pricing.promotion_applies_to(promotion, p)]
        if not matching:
            continue
        offers.append(
            OfferOut(
                id=promotion.id,
                name=promotion.name,
                description=promotion.description,
                discount_type=promotion.discount_type,
                discount_value=promotion.discount_value,
                ends_at=promotion.ends_at,
                products=[
                    ProductSummaryOut.build(p, pricing.price_product(p, [promotion]))
                    for p in matching[:12]
                ],
            )
        )
    return offers


@router.post("/promotions/check", response_model=PromotionCheckOut)
def check_promotion(db: DbSession, payload: PromotionCheckIn) -> PromotionCheckOut:
    """Validate a customer-entered code server-side. The client never decides this."""
    promotion = pricing.validate_promotion_code(db, payload.code, payload.subtotal)
    discount = pricing.discount_for(promotion, payload.subtotal)
    return PromotionCheckOut(
        valid=True,
        code=promotion.code or "",
        name=promotion.name,
        discount_amount=discount,
        new_total=pricing.to_money(payload.subtotal - discount),
    )


@router.get("/posts", response_model=Page[PostSummaryOut])
def list_posts(
    db: DbSession,
    category: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=40)] = 9,
) -> Page[PostSummaryOut]:
    stmt = select(Post).where(Post.status == PostStatus.PUBLISHED)
    if category:
        stmt = stmt.where(Post.category == category)
    stmt = stmt.order_by(Post.published_at.desc().nullslast(), Post.id.desc())
    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[PostSummaryOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/posts/{slug}", response_model=PostDetailOut)
def get_post(db: DbSession, slug: str) -> Post:
    post = db.execute(
        select(Post).where(Post.slug == slug, Post.status == PostStatus.PUBLISHED)
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("Post not found")
    return post


@router.get("/social-links", response_model=list[SocialLinkOut])
def list_social_links(db: DbSession) -> list[SocialLink]:
    stmt = (
        select(SocialLink)
        .where(SocialLink.active.is_(True))
        .order_by(SocialLink.sort_order)
    )
    return list(db.execute(stmt).scalars().all())


@router.post("/inquiries", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_inquiry(db: DbSession, request: Request, payload: InquiryIn) -> MessageOut:
    """A request to buy a watch. Stored for the owner, who replies personally."""
    client_ip = request.client.host if request.client else "unknown"
    ratelimit.enforce(f"inquiry:{client_ip}", limit=5, window_seconds=600)

    product = None
    if payload.product_id is not None:
        product = db.get(Product, payload.product_id)
        if product is None or not product.active:
            raise NotFoundError("That watch is no longer listed")

    db.add(
        Inquiry(
            product_id=product.id if product else None,
            product_name_snapshot=product.name if product else None,
            full_name=payload.full_name,
            email=payload.email.lower(),
            phone=payload.phone,
            message=payload.message or None,
        )
    )
    db.commit()
    return MessageOut(message="Thank you. The store will contact you shortly.")
