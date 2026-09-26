"""Admin CMS: posts, homepage sections, banners, social links, site settings."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import CurrentAdmin, DbSession
from app.core.enums import PostStatus
from app.core.errors import NotFoundError
from app.core.utils import paginate, unique_slug
from app.db import utcnow
from app.models import Banner, HomepageSection, Post, SiteSettings, SocialLink
from app.schemas import (
    AdminBannerOut,
    AdminHomepageSectionOut,
    AdminPostOut,
    AdminSocialLinkOut,
    BannerIn,
    HomepageSectionIn,
    MessageOut,
    Page,
    PostIn,
    PostUpdate,
    SiteSettingsIn,
    SiteSettingsOut,
    SocialLinkIn,
)
from app.services import audit

router = APIRouter(prefix="/api/admin", tags=["admin:content"])


# --------------------------------------------------------------------------- #
# Posts
# --------------------------------------------------------------------------- #


@router.get("/posts", response_model=Page[AdminPostOut])
def list_posts(
    db: DbSession,
    admin: CurrentAdmin,
    post_status: PostStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AdminPostOut]:
    stmt = select(Post)
    if post_status:
        stmt = stmt.where(Post.status == post_status)
    stmt = stmt.order_by(Post.updated_at.desc(), Post.id.desc())
    items, total = paginate(db, stmt, page, page_size)
    return Page(
        items=[AdminPostOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/posts", response_model=AdminPostOut, status_code=status.HTTP_201_CREATED)
def create_post(db: DbSession, admin: CurrentAdmin, payload: PostIn) -> Post:
    post = Post(
        **payload.model_dump(exclude={"slug"}),
        slug=unique_slug(db, Post, payload.slug or payload.title),
    )
    if post.status is PostStatus.PUBLISHED and post.published_at is None:
        post.published_at = utcnow()
    db.add(post)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="post.created",
        entity_type="post",
        summary=post.title,
    )
    db.commit()
    db.refresh(post)
    return post


@router.patch("/posts/{post_id}", response_model=AdminPostOut)
def update_post(
    db: DbSession, admin: CurrentAdmin, post_id: int, payload: PostUpdate
) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise NotFoundError("Post not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("slug"):
        changes["slug"] = unique_slug(db, Post, changes["slug"], exclude_id=post.id)
    else:
        changes.pop("slug", None)
    for field, value in changes.items():
        setattr(post, field, value)
    # Publishing stamps the date once; unpublishing keeps the original date.
    if post.status is PostStatus.PUBLISHED and post.published_at is None:
        post.published_at = utcnow()
    audit.record(
        db,
        admin_user_id=admin.id,
        action=f"post.{post.status.value.lower()}",
        entity_type="post",
        entity_id=post.id,
        summary=post.title,
    )
    db.commit()
    db.refresh(post)
    return post


@router.delete("/posts/{post_id}", response_model=MessageOut)
def archive_post(db: DbSession, admin: CurrentAdmin, post_id: int) -> MessageOut:
    post = db.get(Post, post_id)
    if post is None:
        raise NotFoundError("Post not found")
    post.status = PostStatus.ARCHIVED
    audit.record(
        db,
        admin_user_id=admin.id,
        action="post.archived",
        entity_type="post",
        entity_id=post.id,
        summary=post.title,
    )
    db.commit()
    return MessageOut(message="Post archived.")


# --------------------------------------------------------------------------- #
# Homepage CMS
# --------------------------------------------------------------------------- #


@router.get("/homepage/sections", response_model=list[AdminHomepageSectionOut])
def list_homepage_sections(db: DbSession, admin: CurrentAdmin) -> list[HomepageSection]:
    return list(
        db.execute(select(HomepageSection).order_by(HomepageSection.sort_order))
        .scalars()
        .all()
    )


@router.put("/homepage/sections", response_model=AdminHomepageSectionOut)
def upsert_homepage_section(
    db: DbSession, admin: CurrentAdmin, payload: HomepageSectionIn
) -> HomepageSection:
    """One row per section type, so this is an upsert rather than create/update."""
    section = db.execute(
        select(HomepageSection).where(
            HomepageSection.section_type == payload.section_type
        )
    ).scalar_one_or_none()
    if section is None:
        section = HomepageSection(**payload.model_dump())
        db.add(section)
    else:
        for field, value in payload.model_dump().items():
            setattr(section, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="homepage.updated",
        entity_type="homepage_section",
        summary=payload.section_type.value,
    )
    db.commit()
    db.refresh(section)
    return section


# --------------------------------------------------------------------------- #
# Banners
# --------------------------------------------------------------------------- #


@router.get("/banners", response_model=list[AdminBannerOut])
def list_banners(db: DbSession, admin: CurrentAdmin) -> list[Banner]:
    return list(
        db.execute(select(Banner).order_by(Banner.sort_order, Banner.id)).scalars().all()
    )


@router.post(
    "/banners", response_model=AdminBannerOut, status_code=status.HTTP_201_CREATED
)
def create_banner(db: DbSession, admin: CurrentAdmin, payload: BannerIn) -> Banner:
    banner = Banner(**payload.model_dump())
    db.add(banner)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="banner.created",
        entity_type="banner",
        summary=banner.title,
    )
    db.commit()
    db.refresh(banner)
    return banner


@router.patch("/banners/{banner_id}", response_model=AdminBannerOut)
def update_banner(
    db: DbSession, admin: CurrentAdmin, banner_id: int, payload: BannerIn
) -> Banner:
    banner = db.get(Banner, banner_id)
    if banner is None:
        raise NotFoundError("Banner not found")
    for field, value in payload.model_dump().items():
        setattr(banner, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="banner.updated",
        entity_type="banner",
        entity_id=banner.id,
    )
    db.commit()
    db.refresh(banner)
    return banner


@router.delete("/banners/{banner_id}", response_model=MessageOut)
def delete_banner(db: DbSession, admin: CurrentAdmin, banner_id: int) -> MessageOut:
    banner = db.get(Banner, banner_id)
    if banner is None:
        raise NotFoundError("Banner not found")
    db.delete(banner)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="banner.deleted",
        entity_type="banner",
        entity_id=banner_id,
    )
    db.commit()
    return MessageOut(message="Banner deleted.")


# --------------------------------------------------------------------------- #
# Social links
# --------------------------------------------------------------------------- #


@router.get("/social-links", response_model=list[AdminSocialLinkOut])
def list_social_links(db: DbSession, admin: CurrentAdmin) -> list[SocialLink]:
    return list(
        db.execute(select(SocialLink).order_by(SocialLink.sort_order)).scalars().all()
    )


@router.put("/social-links", response_model=AdminSocialLinkOut)
def upsert_social_link(
    db: DbSession, admin: CurrentAdmin, payload: SocialLinkIn
) -> SocialLink:
    link = db.execute(
        select(SocialLink).where(SocialLink.platform == payload.platform)
    ).scalar_one_or_none()
    if link is None:
        link = SocialLink(**payload.model_dump())
        db.add(link)
    else:
        for field, value in payload.model_dump().items():
            setattr(link, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="social_link.updated",
        entity_type="social_link",
        summary=payload.platform,
    )
    db.commit()
    db.refresh(link)
    return link


@router.delete("/social-links/{link_id}", response_model=MessageOut)
def delete_social_link(db: DbSession, admin: CurrentAdmin, link_id: int) -> MessageOut:
    link = db.get(SocialLink, link_id)
    if link is None:
        raise NotFoundError("Social link not found")
    db.delete(link)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="social_link.deleted",
        entity_type="social_link",
        entity_id=link_id,
    )
    db.commit()
    return MessageOut(message="Social link deleted.")


# --------------------------------------------------------------------------- #
# Site settings
# --------------------------------------------------------------------------- #


@router.get("/settings", response_model=SiteSettingsOut)
def get_settings(db: DbSession, admin: CurrentAdmin) -> SiteSettings:
    row = db.get(SiteSettings, 1)
    if row is None:
        row = SiteSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.patch("/settings", response_model=SiteSettingsOut)
def update_settings(
    db: DbSession, admin: CurrentAdmin, payload: SiteSettingsIn
) -> SiteSettings:
    row = db.get(SiteSettings, 1)
    if row is None:
        row = SiteSettings(id=1)
        db.add(row)
    changes = payload.model_dump(exclude_unset=True)
    if "currency" in changes and changes["currency"]:
        changes["currency"] = changes["currency"].upper()
    for field, value in changes.items():
        setattr(row, field, value)
    audit.record(
        db,
        admin_user_id=admin.id,
        action="settings.updated",
        entity_type="site_settings",
        summary=", ".join(sorted(changes)),
    )
    db.commit()
    db.refresh(row)
    return row
