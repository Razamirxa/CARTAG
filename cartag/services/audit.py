from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from cartag.domain import ActorType
from cartag.models import AuditLog


@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: str | None = None

    @classmethod
    def admin(cls, admin_id) -> "Actor":
        return cls(ActorType.ADMIN, str(admin_id))

    @classmethod
    def user(cls, user_id) -> "Actor":
        return cls(ActorType.USER, str(user_id))

    @classmethod
    def system(cls) -> "Actor":
        return cls(ActorType.SYSTEM, None)


def audit(
    db: Session,
    actor: Actor,
    action: str,
    entity_type: str | None = None,
    entity_id: Any = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Records who did what. Added to the caller's session, so it commits together with the change."""
    db.add(
        AuditLog(
            actor_type=actor.type,
            actor_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            meta=meta,
        )
    )
