import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from cartag.domain import ScanOutcome, StockStatus, TagStatus, UserStatus, is_valid_tag_code, normalize_tag_code
from cartag.models import ScanEvent, Tag

log = logging.getLogger("cartag")


@dataclass(frozen=True)
class ScanContext:
    ip_hash: str | None
    user_agent: str | None


_OUTCOME = {
    "not_found": ScanOutcome.NOT_FOUND,
    "not_active": ScanOutcome.NOT_ACTIVE_PAGE,
    "turned_off": ScanOutcome.TURNED_OFF_PAGE,
    "retired": ScanOutcome.RETIRED_PAGE,
    "active": ScanOutcome.ACTIVE_PAGE,
}


def lookup_public_tag(db: Session, raw_code: str, scan: ScanContext, record: bool = True) -> dict[str, Any]:
    """Looks up a tag for a person who just scanned it, and returns only what a finder may see.

    The result always has a "state": not_found, not_active, turned_off, retired or active. Only the
    active state carries owner details, and the phone numbers are only for the Call buttons.
    A scan is recorded unless the caller is the website checking a tag's state (record=False).
    """
    code = normalize_tag_code(raw_code)
    tag = None
    if is_valid_tag_code(code):
        tag = db.scalar(select(Tag).where(Tag.code == code).options(joinedload(Tag.owner)))

    result: dict[str, Any]
    if tag is None:
        result = {"state": "not_found"}
    elif tag.status == TagStatus.NOT_ACTIVE:
        result = {"state": "not_active", "code": tag.code, "ready": tag.stock_status == StockStatus.SOLD}
    elif tag.status == TagStatus.RETIRED:
        result = {"state": "retired"}
    elif tag.status == TagStatus.TURNED_OFF or tag.owner is None or tag.owner.status != UserStatus.ACTIVE:
        result = {"state": "turned_off"}
    else:
        owner = tag.owner
        card = owner.card
        emergency = None
        if card is not None and card.emergency_enabled:
            emergency = {
                "bloodGroup": card.blood_group.value if card.blood_group else None,
                "contactName": card.emergency_name,
                "relationship": card.emergency_relationship,
                "contactPhone": card.emergency_phone,
            }
        result = {
            "state": "active",
            "code": tag.code,
            "owner": {"name": card.display_name if card else owner.name, "phone": owner.phone},
            "emergency": emergency,
        }

    if not record:
        return result
    # A logging problem must never stop someone from reaching the owner.
    try:
        db.add(
            ScanEvent(
                tag_id=tag.id if tag else None,
                code_attempted=code[:32],
                outcome=_OUTCOME[result["state"]],
                ip_hash=scan.ip_hash,
                user_agent=scan.user_agent[:200] if scan.user_agent else None,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.warning("Could not record scan event", exc_info=True)
    return result
