import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from cartag.domain import MAX_TAGS_PER_USER, OtpPurpose, StockStatus, TagStatus, format_serial
from cartag.errors import bad_request, conflict, forbidden, not_found
from cartag.models import Tag, User
from cartag.schemas import ActivateTagIn
from cartag.services.audit import Actor, audit
from cartag.services.cards import upsert_card
from cartag.services.otp import verify_otp


# ---------- views (the JSON the React app reads) ----------
def owner_tag_view(tag: Tag) -> dict[str, Any]:
    """What an owner sees about their own tag."""
    return {
        "code": tag.code,
        "serial": format_serial(tag.serial),
        "status": tag.status.value,
        "activatedAt": tag.activated_at,
    }


# ---------- owner actions ----------
def activate_tag(db: Session, user: User, data: ActivateTagIn) -> Tag:
    """Turns a tag on for its owner.

    Rules: the tag must have been sold by the team, it must not be on yet, the owner confirms their
    mobile number with a one-time code, and the owner has a Contact Card.
    """
    tag = db.scalar(select(Tag).where(Tag.code == data.code))
    if tag is None:
        raise not_found("We could not find that tag. Check the code and try again.", "TAG_NOT_FOUND")
    if tag.status != TagStatus.NOT_ACTIVE:
        raise conflict("This tag has already been activated.", "TAG_NOT_AVAILABLE")
    # An unsold tag on a shop shelf must not be claimable by whoever scans it first.
    if tag.stock_status != StockStatus.SOLD:
        raise conflict(
            "This tag has not been sold yet. Please buy it from CARTAG or an official seller.", "TAG_NOT_READY"
        )

    owned = db.scalar(select(func.count()).select_from(Tag).where(Tag.owner_id == user.id)) or 0
    if owned >= MAX_TAGS_PER_USER:
        raise forbidden(f"You can link up to {MAX_TAGS_PER_USER} tags to one account.", "TAG_LIMIT")
    if user.card is None and data.card is None:
        raise bad_request("Add your contact details to turn the tag on.", "CARD_REQUIRED")

    # Checked after the tag, so a tag that cannot be activated never burns the owner's code.
    if not verify_otp(db, user.phone, OtpPurpose.ACTIVATE_TAG, data.otp):
        raise bad_request("That code is incorrect or has expired.", "INVALID_OTP")

    if data.card is not None:
        upsert_card(db, user, data.card)

    # The condition on status makes this the atomic claim: if two people activate the same tag at
    # the same moment, exactly one update matches.
    now = datetime.now(UTC)
    claimed = db.execute(
        update(Tag)
        .where(Tag.id == tag.id, Tag.status == TagStatus.NOT_ACTIVE, Tag.stock_status == StockStatus.SOLD)
        .values(status=TagStatus.ACTIVE, owner_id=user.id, activated_at=now)
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise conflict("This tag has already been activated.", "TAG_NOT_AVAILABLE")

    if user.phone_verified_at is None:
        user.phone_verified_at = now
    audit(db, Actor.user(user.id), "tag.activate", "Tag", tag.id, {"code": tag.code})
    db.commit()
    db.refresh(tag)
    return tag


def list_owned_tags(db: Session, user_id: uuid.UUID) -> list[Tag]:
    return list(db.scalars(select(Tag).where(Tag.owner_id == user_id).order_by(Tag.activated_at.desc())))


def get_owned_tag(db: Session, user_id: uuid.UUID, code: str) -> Tag:
    """Returns the tag only if this user owns it. Anyone else gets "not found", never "forbidden"."""
    tag = db.scalar(select(Tag).where(Tag.code == code, Tag.owner_id == user_id))
    if tag is None:
        raise not_found("Tag not found", "TAG_NOT_FOUND")
    return tag


def set_owned_tag_on(db: Session, user: User, code: str, on: bool) -> Tag:
    """The owner turns a tag off (ACTIVE to TURNED_OFF) or back on. A retired tag can never be turned on."""
    tag = get_owned_tag(db, user.id, code)
    source = TagStatus.TURNED_OFF if on else TagStatus.ACTIVE
    target = TagStatus.ACTIVE if on else TagStatus.TURNED_OFF

    if tag.status == TagStatus.RETIRED:
        raise forbidden("This tag has been retired and cannot be turned on again.", "TAG_RETIRED")
    if tag.status != source:
        raise conflict("This tag is already on." if on else "This tag is already off.", "TAG_STATE")

    result = db.execute(update(Tag).where(Tag.id == tag.id, Tag.status == source).values(status=target))
    if result.rowcount != 1:
        db.rollback()
        raise conflict("The tag changed. Please refresh and try again.", "TAG_STATE")
    audit(db, Actor.user(user.id), "tag.turn_on" if on else "tag.turn_off", "Tag", tag.id, {"code": tag.code})
    db.commit()
    db.refresh(tag)
    return tag


# ---------- team actions ----------
def tag_by_code(db: Session, code: str) -> Tag:
    tag = db.scalar(select(Tag).where(Tag.code == code))
    if tag is None:
        raise not_found("Tag not found", "TAG_NOT_FOUND")
    return tag


def mark_tag_sold(db: Session, admin_id: uuid.UUID, code: str) -> Tag:
    """Records that the tag was sold (shipped with an order or handed over in person). Only then can it be activated."""
    tag = tag_by_code(db, code)
    if tag.status == TagStatus.RETIRED:
        raise conflict("This tag is retired.", "TAG_STATE")
    if tag.stock_status == StockStatus.SOLD:
        raise conflict("This tag is already marked as sold.", "TAG_STATE")
    if tag.stock_status not in {StockStatus.IN_STOCK, StockStatus.RESERVED}:
        raise conflict(f"A {tag.stock_status.value.lower()} tag cannot be sold.", "TAG_STATE")
    previous = tag.stock_status.value
    tag.stock_status = StockStatus.SOLD
    audit(db, Actor.admin(admin_id), "tag.mark_sold", "Tag", tag.id, {"from": previous})
    db.commit()
    return tag


def mark_batch_sold(db: Session, admin_id: uuid.UUID, batch_id: uuid.UUID) -> int:
    """Marks every tag of a batch that is still in stock as sold. Returns how many changed."""
    result = db.execute(
        update(Tag)
        .where(Tag.batch_id == batch_id, Tag.stock_status == StockStatus.IN_STOCK, Tag.status != TagStatus.RETIRED)
        .values(stock_status=StockStatus.SOLD)
    )
    count = result.rowcount or 0
    audit(db, Actor.admin(admin_id), "batch.mark_sold", "TagBatch", batch_id, {"count": count})
    db.commit()
    return count


def retire_tag(db: Session, admin_id: uuid.UUID, code: str, reason: str | None) -> Tag:
    """Stops a tag for good. It can never be turned on again and its code is never given to anyone else."""
    tag = tag_by_code(db, code)
    if tag.status == TagStatus.RETIRED:
        raise conflict("This tag is already retired.", "TAG_STATE")
    previous = tag.status.value
    tag.status = TagStatus.RETIRED
    tag.retired_at = datetime.now(UTC)
    audit(db, Actor.admin(admin_id), "tag.retire", "Tag", tag.id, {"from": previous, "reason": reason})
    db.commit()
    return tag
