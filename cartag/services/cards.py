from typing import Any

from sqlalchemy.orm import Session

from cartag.models import ContactCard, User
from cartag.schemas import ContactCardIn
from cartag.services.audit import Actor, audit


def card_view(card: ContactCard | None) -> dict[str, Any] | None:
    """The owner's own view of their card (they may see the emergency numbers they typed)."""
    if card is None:
        return None
    return {
        "displayName": card.display_name,
        "emergencyEnabled": card.emergency_enabled,
        "bloodGroup": card.blood_group.value if card.blood_group else None,
        "emergencyName": card.emergency_name,
        "emergencyRelationship": card.emergency_relationship,
        "emergencyPhone": card.emergency_phone,
    }


def upsert_card(db: Session, user: User, data: ContactCardIn) -> ContactCard:
    """Creates or updates the owner's Contact Card. Does not commit: the caller commits with its own change."""
    card = user.card
    created = card is None
    if card is None:
        card = ContactCard(user_id=user.id, display_name=data.display_name)
        db.add(card)
    card.display_name = data.display_name
    card.emergency_enabled = data.emergency_enabled
    card.blood_group = data.blood_group
    card.emergency_name = data.emergency_name
    card.emergency_relationship = data.emergency_relationship
    card.emergency_phone = data.emergency_phone
    user.card = card
    audit(
        db,
        Actor.user(user.id),
        "card.create" if created else "card.update",
        "User",
        user.id,
        {"emergencyEnabled": data.emergency_enabled},
    )
    return card
