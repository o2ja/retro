"""Development seed: `python -m app.seed`.

Loads the real Obaidi Time starting catalog (Brand_Obaidi_Time.md) through the
database, which is where the storefront reads it from - the frontend never holds
product data.

Two rules this file follows strictly:

* No selling price is invented. On the owner's instruction each watch is
  listed at its catalog estimated market value; `price` and
  `estimated_market_price` remain separate columns, and the dashboard can set a
  different selling price per watch at any time (`SeedProduct.price`).
* No specification, warranty or certification is invented. Fields absent from
  the source document stay empty rather than being filled with plausible text.

The seed is idempotent: re-running it updates the same rows by SKU/slug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    HomepageSectionType,
    InventoryReason,
    PostStatus,
    ProductCondition,
)
from app.core.security import hash_password
from app.core.utils import slugify
from app.db import SessionLocal, utcnow
from app.models import (
    AdminUser,
    Brand,
    Category,
    HomepageSection,
    Post,
    Product,
    ProductImage,
    SiteSettings,
    SocialLink,
)
from app.services import inventory

# Each watch gets two seeded images, both served from the storefront's public
# folder: an editorial photograph (frontend/public/watches/<slug>.jpg, see the
# CREDITS.md there) and the owner's own photograph of the piece in hand
# (frontend/public/products/<slug>.png). Set False to fall back to placeholders.
ATTACH_PHOTOGRAPHY = True


BRANDS = [
    ("Rolex", 1),
    ("Bulgari", 2),
    ("Hublot", 3),
    ("Franck Muller", 4),
    ("Breitling", 5),
    ("Zenith", 6),
]

CATEGORIES = [
    ("Luxury Watches", "The full Retro Watches selection.", 1),
    ("Diver", "Watches built around the dive bezel.", 2),
    ("Chronograph", "Stopwatch complications.", 3),
    ("Dress", "Refined pieces for formal wear.", 4),
    ("Sport", "Robust everyday and sports watches.", 5),
    ("Limited Edition", "Numbered and limited production runs.", 6),
]


@dataclass
class SeedProduct:
    sku: str
    name: str
    brand: str
    categories: list[str]
    estimated_market_price: Decimal
    quantity: int
    short_description: str
    description: str
    case_size: str
    condition: ProductCondition | None = None
    production_year: int | None = None
    case_material: str | None = None
    dial: str | None = None
    movement: str | None = None
    included_items: str | None = None
    limited_edition: str | None = None
    warranty_information: str | None = None
    # Overrides the listed price for this watch. None = list at market value.
    price: Decimal | None = None
    featured: bool = False
    new_arrival: bool = False
    images: list[tuple[str, str]] = field(default_factory=list)


# Source: Brand_Obaidi_Time.md. The figures below are the owner's estimated
# market values; see _upsert_products for how the listed price is derived.
CATALOG: list[SeedProduct] = [
    SeedProduct(
        sku="OT-RLX-SUB-KERMIT",
        name="Rolex Submariner Date 'Kermit'",
        brand="Rolex",
        categories=["Luxury Watches", "Diver", "Sport"],
        estimated_market_price=Decimal("20000"),
        quantity=1,
        condition=ProductCondition.EXCELLENT,
        production_year=2022,
        case_material="Steel",
        case_size="41mm",
        dial="Black dial, green bezel",
        included_items="Watch only",
        short_description="Green bezel, black dial. Steel, 41mm. Pre-owned, 2022.",
        description=(
            "A 2022 Submariner Date in steel with the green bezel and black dial, "
            "supplied as the watch only. Offered by Retro Watches as a pre-owned piece; "
            "condition and specification are described exactly as recorded in our "
            "listing."
        ),
        featured=True,
        new_arrival=True,
    ),
    SeedProduct(
        sku="OT-BVL-OCTO-ULTRANERO",
        name="Bulgari Octo Ultranero",
        brand="Bulgari",
        categories=["Luxury Watches", "Dress"],
        estimated_market_price=Decimal("20000"),
        quantity=1,
        condition=ProductCondition.EXCELLENT,
        case_material="Black steel / rose gold",
        case_size="41mm",
        included_items="Watch only",
        short_description=(
            "Black steel and rose gold, 41mm. Pre-owned, excellent condition."
        ),
        description=(
            "The Octo Ultranero in black steel with rose gold, 41mm, supplied as the "
            "watch only. A pre-owned piece in excellent condition."
        ),
        new_arrival=True,
    ),
    SeedProduct(
        sku="OT-HUB-BIGBANG-UNICO",
        name="Hublot Big Bang Unico",
        brand="Hublot",
        categories=["Luxury Watches", "Chronograph", "Sport"],
        estimated_market_price=Decimal("19000"),
        quantity=0,
        condition=ProductCondition.EXCELLENT,
        production_year=2021,
        case_size="44mm",
        movement="Automatic",
        included_items="Box and online warranty",
        short_description="44mm automatic. Pre-owned, 2021. Box and online warranty.",
        description=(
            "A 2021 Big Bang Unico, 44mm, automatic, supplied with box and online "
            "warranty as listed."
        ),
    ),
    SeedProduct(
        sku="OT-FM-VANGUARD-TIRG",
        name="Franck Muller Vanguard Titanium / Rose Gold",
        brand="Franck Muller",
        categories=["Luxury Watches", "Sport"],
        estimated_market_price=Decimal("17000"),
        quantity=0,
        condition=ProductCondition.EXCELLENT,
        case_material="Titanium / rose gold",
        case_size="45mm",
        included_items="Watch only",
        short_description="Titanium and rose gold, 45mm. Pre-owned, excellent condition.",
        description=(
            "The Vanguard in titanium and rose gold, 45mm, supplied as the watch only."
        ),
    ),
    SeedProduct(
        sku="OT-RLX-SEADWELLER",
        name="Rolex Sea-Dweller",
        brand="Rolex",
        categories=["Luxury Watches", "Diver", "Sport"],
        estimated_market_price=Decimal("12000"),
        quantity=0,
        condition=ProductCondition.VERY_GOOD,
        production_year=2018,
        case_material="Steel",
        case_size="43mm",
        included_items="Card and tag, no box",
        short_description="Steel, 43mm. Pre-owned, 2018. Card and tag, no box.",
        description=(
            "A 2018 Sea-Dweller in steel, 43mm, supplied with card and tag; no box."
        ),
    ),
    SeedProduct(
        sku="OT-RLX-DATEJUST-II",
        name="Rolex Datejust II",
        brand="Rolex",
        categories=["Luxury Watches", "Dress"],
        estimated_market_price=Decimal("11000"),
        quantity=0,
        condition=ProductCondition.EXCELLENT,
        production_year=2021,
        case_size="41mm",
        included_items="Full set with card",
        short_description="41mm. Pre-owned, 2021. Full set with card.",
        description=(
            "A 2021 Datejust II, 41mm, supplied as a full set with card. The reference "
            "number recorded for this piece is approximate and is confirmed on request."
        ),
    ),
    SeedProduct(
        sku="OT-RLX-SUB-NODATE",
        name="Rolex Submariner",
        brand="Rolex",
        categories=["Luxury Watches", "Diver", "Sport"],
        estimated_market_price=Decimal("10500"),
        quantity=0,
        condition=ProductCondition.VERY_GOOD,
        production_year=2017,
        case_material="Steel",
        case_size="40mm",
        included_items="Box, links and service card",
        short_description="Steel, 40mm. Pre-owned, 2017. Box, links and service card.",
        description=(
            "A 2017 Submariner in steel, 40mm, supplied with box, links and service card."
        ),
    ),
    SeedProduct(
        sku="OT-BRT-CHRONOMAT-B01",
        name="Breitling Chronomat B01",
        brand="Breitling",
        categories=["Luxury Watches", "Chronograph", "Sport"],
        estimated_market_price=Decimal("8000"),
        quantity=0,
        condition=ProductCondition.EXCELLENT,
        case_size="44mm",
        movement="Automatic",
        included_items="Box and warranty documents",
        warranty_information="Warranty listed as valid until 2031.",
        short_description="44mm automatic. Pre-owned. Box and warranty until 2031.",
        description=(
            "A Chronomat B01, 44mm, automatic, supplied with box and warranty "
            "documentation listed as valid until 2031."
        ),
    ),
    SeedProduct(
        sku="OT-ZEN-ELPRIMERO-LE",
        name="Zenith El Primero Chronograph Limited Edition",
        brand="Zenith",
        categories=["Luxury Watches", "Chronograph", "Limited Edition"],
        estimated_market_price=Decimal("7000"),
        quantity=0,
        condition=ProductCondition.EXCELLENT,
        case_size="42mm",
        included_items="Card, no box",
        limited_edition="Limited edition of 500 pieces",
        short_description="42mm chronograph with tricolour strap. Limited to 500 pieces.",
        description=(
            "An El Primero chronograph, 42mm, on a tricolour strap, from a limited "
            "edition of 500 pieces. Supplied with card; no box."
        ),
    ),
]

HOMEPAGE = [
    (
        HomepageSectionType.HERO,
        "Time, Kept Well",
        "Authenticated pre-owned watches, selected one piece at a time.",
        None,
        "Discover the Collection",
        "/shop",
        0,
        None,
    ),
    (
        HomepageSectionType.FEATURED_PRODUCTS,
        "The Selection",
        "Pieces currently held by Retro Watches.",
        None,
        "View all",
        "/shop",
        1,
        None,
    ),
    (
        HomepageSectionType.NEW_ARRIVALS,
        "Recently Acquired",
        "The newest additions to the collection.",
        None,
        "See what's new",
        "/shop?sort=newest",
        2,
        None,
    ),
    (
        HomepageSectionType.BRAND_STORY,
        "Retro Watches",
        None,
        (
            "Retro Watches is a private collection of fine pre-owned watches, curated by "
            "Mustafa Al Obaidi. Every piece is selected individually, described as it "
            "is, and offered to a small number of collectors."
        ),
        "About us",
        "/about",
        3,
        None,
    ),
    (
        HomepageSectionType.JOURNAL,
        "Journal",
        "Notes on collecting, condition and care.",
        None,
        "Read the journal",
        "/journal",
        4,
        None,
    ),
]

# No cover photography yet; the journal draws a dial placeholder instead.
POSTS = [
    (
        "Buying Pre-Owned: What Condition Really Means",
        "A short guide to the language used to describe a used watch, and what to "
        "ask before you buy.",
        PostStatus.PUBLISHED,
        "Guides",
        None,
    ),
    (
        "Caring for an Automatic Watch",
        "Winding, resting and servicing: the basics of living with a mechanical "
        "movement.",
        PostStatus.DRAFT,
        "Guides",
        None,
    ),
]


def _upsert_admin(db: Session) -> None:
    email = settings.admin_email.lower()
    admin = db.execute(
        select(AdminUser).where(AdminUser.email == email)
    ).scalar_one_or_none()
    if admin is None:
        db.add(
            AdminUser(
                email=email,
                full_name="Mustafa Al Obaidi",
                password_hash=hash_password(settings.admin_password),
            )
        )
        print(f"  admin created: {email}")
    else:
        print(f"  admin already exists: {email}")


def _upsert_settings(db: Session) -> None:
    row = db.get(SiteSettings, 1)
    if row is None:
        row = SiteSettings(id=1)
        db.add(row)
    row.brand_name = "Retro Watches"
    row.owner_name = "Mustafa Al Obaidi"
    row.tagline = "Authenticated pre-owned watches"
    row.currency = settings.default_currency
    row.seo_title = "Retro Watches - Fine Pre-Owned Watches"
    row.seo_description = (
        "A curated collection of authenticated pre-owned luxury watches."
    )


def _upsert_social(db: Session) -> None:
    link = db.execute(
        select(SocialLink).where(SocialLink.platform == "instagram")
    ).scalar_one_or_none()
    if link is None:
        link = SocialLink(platform="instagram")
        db.add(link)
    link.label = "@retrowhatches.jo"
    link.url = "https://www.instagram.com/retrowatches.jo/?__d=1%252F%252F"
    link.sort_order = 0


def _upsert_taxonomy(db: Session) -> tuple[dict[str, Brand], dict[str, Category]]:
    brands: dict[str, Brand] = {}
    for name, order in BRANDS:
        slug = slugify(name)
        brand = db.execute(select(Brand).where(Brand.slug == slug)).scalar_one_or_none()
        if brand is None:
            brand = Brand(name=name, slug=slug, sort_order=order)
            db.add(brand)
        brands[name] = brand

    categories: dict[str, Category] = {}
    for name, description, order in CATEGORIES:
        slug = slugify(name)
        category = db.execute(
            select(Category).where(Category.slug == slug)
        ).scalar_one_or_none()
        if category is None:
            category = Category(
                name=name, slug=slug, description=description, sort_order=order
            )
            db.add(category)
        categories[name] = category

    db.flush()
    return brands, categories


def _upsert_products(
    db: Session, brands: dict[str, Brand], categories: dict[str, Category]
) -> None:
    for entry in CATALOG:
        product = db.execute(
            select(Product).where(Product.sku == entry.sku)
        ).scalar_one_or_none()
        created = product is None
        if product is None:
            product = Product(sku=entry.sku, slug=slugify(entry.name))
            db.add(product)

        product.name = entry.name
        product.brand = brands[entry.brand]
        product.categories = [categories[c] for c in entry.categories]
        product.short_description = entry.short_description
        product.description = entry.description
        # Owner instruction: list at the catalog's estimated market value unless a
        # specific price is given. The dashboard overrides this at any time.
        product.price = entry.price or entry.estimated_market_price
        product.estimated_market_price = entry.estimated_market_price
        product.currency = settings.default_currency
        product.condition = entry.condition
        product.production_year = entry.production_year
        product.case_material = entry.case_material
        product.case_size = entry.case_size
        product.dial = entry.dial
        product.movement = entry.movement
        product.included_items = entry.included_items
        product.limited_edition = entry.limited_edition
        product.warranty_information = entry.warranty_information
        product.is_unique = True
        product.active = True
        product.featured = entry.featured
        product.new_arrival = entry.new_arrival
        db.flush()

        record = inventory.ensure_record(db, product.id)
        if created and entry.quantity:
            inventory.adjust(
                db,
                product.id,
                entry.quantity,
                InventoryReason.INITIAL_STOCK,
                reference_type="seed",
                note="Initial catalog import",
            )
        record.low_stock_threshold = 1
        _upsert_primary_image(db, product, entry)
    db.flush()


def _upsert_primary_image(db: Session, product: Product, entry: SeedProduct) -> None:
    """Attach the seeded photographs. Images added in the dashboard are left alone."""
    seeded = [
        (f"/watches/{product.slug}.jpg", f"{entry.name}, on the wrist"),
        (f"/products/{product.slug}.png", f"{entry.name}, photographed in hand"),
    ]
    existing = {
        image.url: image
        for image in db.execute(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).scalars()
        if image.url.startswith(("/products/", "/watches/"))
    }

    if not ATTACH_PHOTOGRAPHY:
        for image in existing.values():
            db.delete(image)
        return

    for order, (url, alt) in enumerate(seeded):
        image = existing.pop(url, None) or ProductImage(product_id=product.id, url=url)
        image.alt_text, image.sort_order, image.is_primary = alt, order, order == 0
        db.add(image)
    for stale in existing.values():
        db.delete(stale)


def _upsert_homepage(db: Session) -> None:
    for section_type, title, subtitle, body, cta_label, cta_url, order, image in HOMEPAGE:
        section = db.execute(
            select(HomepageSection).where(HomepageSection.section_type == section_type)
        ).scalar_one_or_none()
        if section is None:
            section = HomepageSection(section_type=section_type)
            db.add(section)
        section.title = title
        section.subtitle = subtitle
        section.body = body
        section.image_url = image
        section.cta_label = cta_label
        section.cta_url = cta_url
        section.sort_order = order
        section.visible = True


def _upsert_posts(db: Session) -> None:
    for title, excerpt, status, category, cover in POSTS:
        slug = slugify(title)
        post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
        if post is None:
            post = Post(slug=slug)
            db.add(post)
        post.title = title
        post.excerpt = excerpt
        post.content = excerpt
        post.category = category
        post.cover_image_url = cover
        post.author_name = "Retro Watches"
        post.status = status
        if status is PostStatus.PUBLISHED and post.published_at is None:
            post.published_at = utcnow()


def run() -> None:
    with SessionLocal() as db:
        print("Seeding Obaidi Time development data...")
        _upsert_admin(db)
        _upsert_settings(db)
        _upsert_social(db)
        brands, categories = _upsert_taxonomy(db)
        _upsert_products(db, brands, categories)
        _upsert_homepage(db)
        _upsert_posts(db)
        db.commit()
        print(
            f"  {len(BRANDS)} brands, {len(CATEGORIES)} categories, "
            f"{len(CATALOG)} products, {len(POSTS)} posts."
        )
        print(
            "Done. Watches are listed at their catalog market value; "
            "adjust any price from the dashboard."
        )


if __name__ == "__main__":
    run()
