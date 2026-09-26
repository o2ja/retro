"""Admin catalog management: products, images, inventory, brands, categories."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentAdmin, DbSession
from app.core.enums import InventoryReason
from app.core.errors import ConflictError, NotFoundError
from app.core.utils import paginate, unique_slug
from app.models import (
    Brand,
    Category,
    Inventory,
    InventoryTransaction,
    OrderItem,
    Product,
    ProductCategory,
    ProductImage,
)
from app.schemas import (
    AdminBrandOut,
    AdminCategoryOut,
    AdminProductOut,
    BrandIn,
    BrandUpdate,
    CategoryIn,
    CategoryUpdate,
    InventoryAdjustIn,
    InventoryOut,
    InventorySetIn,
    InventoryTransactionOut,
    MessageOut,
    Page,
    ProductImageIn,
    ProductImageOut,
    ProductIn,
    ProductUpdate,
    SortOptionIn,
)
from app.services import audit, catalog, inventory

router = APIRouter(prefix="/api/admin", tags=["admin:catalog"])


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #


def _load_product(db, product_id: int) -> Product:  # noqa: ANN001
    product = (
        db.execute(
            catalog.product_query(published_only=False).where(Product.id == product_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if product is None:
        raise NotFoundError("Product not found")
    return product


def _resolve_categories(db, category_ids: list[int]) -> list[Category]:  # noqa: ANN001
    if not category_ids:
        return []
    categories = list(
        db.execute(select(Category).where(Category.id.in_(category_ids))).scalars().all()
    )
    missing = set(category_ids) - {c.id for c in categories}
    if missing:
        raise NotFoundError(f"Unknown category ids: {sorted(missing)}")
    return categories


def _assert_sku_free(db, sku: str, *, exclude_id: int | None = None) -> None:  # noqa: ANN001
    stmt = select(Product.id).where(func.lower(Product.sku) == sku.lower())
    if exclude_id is not None:
        stmt = stmt.where(Product.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise ConflictError(f"SKU '{sku}' is already used by another product.")


@router.get("/products", response_model=Page[AdminProductOut])
def list_products(
    db: DbSession,
    admin: CurrentAdmin,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=160)] = None,
    brand: Annotated[str | None, Query(max_length=160)] = None,
    active: bool | None = None,
    low_stock: bool = False,
    sort: SortOptionIn = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AdminProductOut]:
    filters = catalog.CatalogFilters(
        search=q, category_slug=category, brand_slug=brand, sort=sort
    )
    stmt = catalog.build_catalog_query(filters, published_only=False)
    if active is not None:
        stmt = stmt.where(Product.active.is_(active))
    if low_stock:
        stmt = stmt.where(
            Product.is_unique.is_(False),
            Product.id.in_(
                select(Inventory.product_id).where(
                    Inventory.quantity <= Inventory.low_stock_threshold
                )
            ),
        )
    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[AdminProductOut.build(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{product_id}", response_model=AdminProductOut)
def get_product(db: DbSession, admin: CurrentAdmin, product_id: int) -> AdminProductOut:
    return AdminProductOut.build(_load_product(db, product_id))


@router.post(
    "/products", response_model=AdminProductOut, status_code=status.HTTP_201_CREATED
)
def create_product(
    db: DbSession, admin: CurrentAdmin, payload: ProductIn
) -> AdminProductOut:
    _assert_sku_free(db, payload.sku)
    data = payload.model_dump(
        exclude={"category_ids", "slug", "stock_quantity", "low_stock_threshold"}
    )
    product = Product(**data, slug=unique_slug(db, Product, payload.slug or payload.name))
    product.categories = _resolve_categories(db, payload.category_ids)
    db.add(product)
    db.flush()

    record = inventory.ensure_record(db, product.id)
    record.low_stock_threshold = payload.low_stock_threshold
    if payload.stock_quantity:
        inventory.adjust(
            db,
            product.id,
            payload.stock_quantity,
            InventoryReason.INITIAL_STOCK,
            reference_type="product",
            reference_id=str(product.id),
        )

    audit.record(
        db,
        admin_user_id=admin.id,
        action="product.created",
        entity_type="product",
        entity_id=product.id,
        summary=product.name,
    )
    db.commit()
    return AdminProductOut.build(_load_product(db, product.id))


@router.patch("/products/{product_id}", response_model=AdminProductOut)
def update_product(
    db: DbSession, admin: CurrentAdmin, product_id: int, payload: ProductUpdate
) -> AdminProductOut:
    product = _load_product(db, product_id)
    changes = payload.model_dump(exclude_unset=True)

    if "sku" in changes and changes["sku"]:
        _assert_sku_free(db, changes["sku"], exclude_id=product.id)
    if "category_ids" in changes:
        product.categories = _resolve_categories(db, changes.pop("category_ids") or [])
    if changes.get("slug"):
        changes["slug"] = unique_slug(db, Product, changes["slug"], exclude_id=product.id)
    else:
        changes.pop("slug", None)

    for field, value in changes.items():
        setattr(product, field, value)

    audit.record(
        db,
        admin_user_id=admin.id,
        action="product.updated",
        entity_type="product",
        entity_id=product.id,
        summary=", ".join(sorted(changes)) or "categories",
    )
    db.commit()
    return AdminProductOut.build(_load_product(db, product.id))


@router.delete("/products/{product_id}", response_model=MessageOut)
def delete_product(db: DbSession, admin: CurrentAdmin, product_id: int) -> MessageOut:
    """Hard-delete only when no order ever referenced the product; archive otherwise."""
    product = _load_product(db, product_id)
    referenced = db.execute(
        select(OrderItem.id).where(OrderItem.product_id == product.id).limit(1)
    ).first()

    if referenced:
        product.active = False
        action, message = "product.archived", "Product archived (it appears in orders)."
    else:
        db.delete(product)
        action, message = "product.deleted", "Product deleted."

    audit.record(
        db,
        admin_user_id=admin.id,
        action=action,
        entity_type="product",
        entity_id=product_id,
        summary=product.name,
    )
    db.commit()
    return MessageOut(message=message)


# --------------------------------------------------------------------------- #
# Product images
# --------------------------------------------------------------------------- #


@router.post(
    "/products/{product_id}/images",
    response_model=ProductImageOut,
    status_code=status.HTTP_201_CREATED,
)
def add_product_image(
    db: DbSession, admin: CurrentAdmin, product_id: int, payload: ProductImageIn
) -> ProductImage:
    product = _load_product(db, product_id)
    image = ProductImage(product_id=product.id, **payload.model_dump())
    if payload.is_primary or not product.images:
        for existing in product.images:
            existing.is_primary = False
        image.is_primary = True
    db.add(image)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="product.image_added",
        entity_type="product",
        entity_id=product.id,
    )
    db.commit()
    db.refresh(image)
    return image


@router.delete("/products/{product_id}/images/{image_id}", response_model=MessageOut)
def delete_product_image(
    db: DbSession, admin: CurrentAdmin, product_id: int, image_id: int
) -> MessageOut:
    image = db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id, ProductImage.product_id == product_id
        )
    ).scalar_one_or_none()
    if image is None:
        raise NotFoundError("Image not found")
    was_primary = image.is_primary
    db.delete(image)
    db.flush()
    if was_primary:
        remaining = db.execute(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort_order)
            .limit(1)
        ).scalar_one_or_none()
        if remaining:
            remaining.is_primary = True
    db.commit()
    return MessageOut(message="Image removed.")


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #


def _inventory_out(product: Product) -> InventoryOut:
    record = product.inventory
    return InventoryOut(
        product_id=product.id,
        quantity=record.quantity if record else 0,
        low_stock_threshold=record.low_stock_threshold if record else 0,
        availability=inventory.availability(product),
        updated_at=record.updated_at if record else product.updated_at,
    )


@router.get("/products/{product_id}/inventory", response_model=InventoryOut)
def get_inventory(db: DbSession, admin: CurrentAdmin, product_id: int) -> InventoryOut:
    return _inventory_out(_load_product(db, product_id))


@router.put("/products/{product_id}/inventory", response_model=InventoryOut)
def set_inventory(
    db: DbSession, admin: CurrentAdmin, product_id: int, payload: InventorySetIn
) -> InventoryOut:
    product = _load_product(db, product_id)
    record = inventory.ensure_record(db, product.id)
    if payload.low_stock_threshold is not None:
        record.low_stock_threshold = payload.low_stock_threshold
    inventory.set_quantity(db, product.id, payload.quantity, note=payload.note)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="inventory.set",
        entity_type="product",
        entity_id=product.id,
        summary=f"quantity={payload.quantity}",
    )
    db.commit()
    return _inventory_out(_load_product(db, product_id))


@router.post("/products/{product_id}/inventory/adjust", response_model=InventoryOut)
def adjust_inventory(
    db: DbSession, admin: CurrentAdmin, product_id: int, payload: InventoryAdjustIn
) -> InventoryOut:
    product = _load_product(db, product_id)
    inventory.adjust(db, product.id, payload.change, payload.reason, note=payload.note)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="inventory.adjusted",
        entity_type="product",
        entity_id=product.id,
        summary=f"change={payload.change} reason={payload.reason.value}",
    )
    db.commit()
    return _inventory_out(_load_product(db, product_id))


@router.get(
    "/products/{product_id}/inventory/history",
    response_model=list[InventoryTransactionOut],
)
def inventory_history(
    db: DbSession,
    admin: CurrentAdmin,
    product_id: int,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[InventoryTransaction]:
    stmt = (
        select(InventoryTransaction)
        .where(InventoryTransaction.product_id == product_id)
        .order_by(InventoryTransaction.id.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/inventory/low-stock", response_model=list[AdminProductOut])
def low_stock_products(db: DbSession, admin: CurrentAdmin) -> list[AdminProductOut]:
    # One-of-a-kind pieces are excluded: a single unit is not a low-stock warning.
    stmt = (
        catalog.product_query(published_only=False)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(
            Product.is_unique.is_(False),
            Inventory.quantity <= Inventory.low_stock_threshold,
        )
        .order_by(Inventory.quantity)
    )
    return [AdminProductOut.build(p) for p in db.execute(stmt).unique().scalars().all()]


# --------------------------------------------------------------------------- #
# Brands & categories
# --------------------------------------------------------------------------- #


def _product_counts(db, column) -> dict[int, int]:  # noqa: ANN001
    rows = db.execute(select(column, func.count(Product.id)).group_by(column)).all()
    return {key: count for key, count in rows if key is not None}


@router.get("/brands", response_model=list[AdminBrandOut])
def list_brands(db: DbSession, admin: CurrentAdmin) -> list[AdminBrandOut]:
    brands = (
        db.execute(select(Brand).order_by(Brand.sort_order, Brand.name)).scalars().all()
    )
    counts = _product_counts(db, Product.brand_id)
    out = []
    for brand in brands:
        item = AdminBrandOut.model_validate(brand)
        item.product_count = counts.get(brand.id, 0)
        out.append(item)
    return out


@router.post("/brands", response_model=AdminBrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(db: DbSession, admin: CurrentAdmin, payload: BrandIn) -> Brand:
    brand = Brand(
        **payload.model_dump(exclude={"slug"}),
        slug=unique_slug(db, Brand, payload.slug or payload.name),
    )
    db.add(brand)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="brand.created",
        entity_type="brand",
        summary=brand.name,
    )
    db.commit()
    db.refresh(brand)
    return brand


@router.patch("/brands/{brand_id}", response_model=AdminBrandOut)
def update_brand(
    db: DbSession, admin: CurrentAdmin, brand_id: int, payload: BrandUpdate
) -> Brand:
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("slug"):
        changes["slug"] = unique_slug(db, Brand, changes["slug"], exclude_id=brand.id)
    else:
        changes.pop("slug", None)
    for field, value in changes.items():
        setattr(brand, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="brand.updated",
        entity_type="brand",
        entity_id=brand.id,
    )
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/brands/{brand_id}", response_model=MessageOut)
def delete_brand(db: DbSession, admin: CurrentAdmin, brand_id: int) -> MessageOut:
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise NotFoundError("Brand not found")
    in_use = db.execute(
        select(Product.id).where(Product.brand_id == brand.id).limit(1)
    ).first()
    if in_use:
        raise ConflictError(
            "This brand still has products. Deactivate it instead of deleting."
        )
    db.delete(brand)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="brand.deleted",
        entity_type="brand",
        entity_id=brand_id,
        summary=brand.name,
    )
    db.commit()
    return MessageOut(message="Brand deleted.")


@router.get("/categories", response_model=list[AdminCategoryOut])
def list_categories(db: DbSession, admin: CurrentAdmin) -> list[AdminCategoryOut]:
    categories = (
        db.execute(select(Category).order_by(Category.sort_order, Category.name))
        .scalars()
        .all()
    )
    rows = db.execute(
        select(
            ProductCategory.category_id, func.count(ProductCategory.product_id)
        ).group_by(ProductCategory.category_id)
    ).all()
    counts = dict(rows)
    out = []
    for category in categories:
        item = AdminCategoryOut.model_validate(category)
        item.product_count = counts.get(category.id, 0)
        out.append(item)
    return out


@router.post(
    "/categories", response_model=AdminCategoryOut, status_code=status.HTTP_201_CREATED
)
def create_category(db: DbSession, admin: CurrentAdmin, payload: CategoryIn) -> Category:
    category = Category(
        **payload.model_dump(exclude={"slug", "logo_url"}),
        slug=unique_slug(db, Category, payload.slug or payload.name),
    )
    db.add(category)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="category.created",
        entity_type="category",
        summary=category.name,
    )
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=AdminCategoryOut)
def update_category(
    db: DbSession, admin: CurrentAdmin, category_id: int, payload: CategoryUpdate
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    changes = payload.model_dump(exclude_unset=True, exclude={"logo_url"})
    if changes.get("slug"):
        changes["slug"] = unique_slug(
            db, Category, changes["slug"], exclude_id=category.id
        )
    else:
        changes.pop("slug", None)
    for field, value in changes.items():
        setattr(category, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="category.updated",
        entity_type="category",
        entity_id=category.id,
    )
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", response_model=MessageOut)
def delete_category(db: DbSession, admin: CurrentAdmin, category_id: int) -> MessageOut:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    in_use = db.execute(
        select(ProductCategory.product_id)
        .where(ProductCategory.category_id == category.id)
        .limit(1)
    ).first()
    if in_use:
        raise ConflictError(
            "This category still has products. Deactivate it instead of deleting."
        )
    db.delete(category)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="category.deleted",
        entity_type="category",
        entity_id=category_id,
        summary=category.name,
    )
    db.commit()
    return MessageOut(message="Category deleted.")
