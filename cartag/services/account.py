import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cartag.domain import DeletionStatus, OtpPurpose, TagStatus, UserStatus
from cartag.errors import bad_request, conflict, not_found, unauthorized
from cartag.models import AccountDeletionRequest, ContactCard, Tag, User, UserSession
from cartag.security import hash_password, verify_password
from cartag.services.audit import Actor, audit
from cartag.services.otp import request_otp, verify_otp
from cartag.services.sessions import revoke_user_sessions
from cartag.services.sms import SmsProvider
from cartag.services.throttle import assert_not_locked, clear_failures, record_failure


def check_password(db: Session, user: User, password: str) -> None:
    """Asks the owner for their password before something sensitive. Repeated wrong answers lock it for a while."""
    key = f"pw:{user.id}"
    assert_not_locked(db, key)
    if not verify_password(user.password_hash, password):
        record_failure(db, key)
        raise unauthorized("That password is not correct.", "INVALID_CREDENTIALS")
    clear_failures(db, key)


# ---------- activation code ----------
def send_activation_code(db: Session, user: User, ip_hash: str | None, sms: SmsProvider) -> int:
    """Texts a one-time code to the owner's own number. Used to confirm turning a tag on."""
    return request_otp(db, phone=user.phone, purpose=OtpPurpose.ACTIVATE_TAG, ip_hash=ip_hash, eligible=True, sms=sms)


# ---------- changing the mobile number ----------
def start_phone_change(
    db: Session, user: User, new_phone: str, password: str, ip_hash: str | None, sms: SmsProvider
) -> int:
    check_password(db, user, password)
    if new_phone == user.phone:
        raise bad_request("That is already your mobile number.", "SAME_PHONE")
    taken = db.scalar(select(User.id).where(User.phone == new_phone)) is not None
    # Same answer either way, so this cannot be used to find out which numbers have accounts.
    return request_otp(
        db, phone=new_phone, purpose=OtpPurpose.CHANGE_PHONE, ip_hash=ip_hash, eligible=not taken, sms=sms
    )


def confirm_phone_change(db: Session, user: User, new_phone: str, otp: str, current_token: str | None) -> None:
    invalid = bad_request("That code is incorrect or has expired.", "INVALID_OTP")
    if not verify_otp(db, new_phone, OtpPurpose.CHANGE_PHONE, otp):
        raise invalid

    user.phone = new_phone
    user.phone_verified_at = datetime.now(UTC)
    audit(db, Actor.user(user.id), "user.change_phone", "User", user.id)
    try:
        db.commit()
    except IntegrityError:
        # Someone took the number between the code and now. Do not say so.
        db.rollback()
        raise invalid from None
    # A new number is a good moment to end every other session.
    revoke_user_sessions(db, user.id, keep_token=current_token)


# ---------- closing the account ----------
def pending_deletion(db: Session, user: User) -> AccountDeletionRequest | None:
    return db.scalar(
        select(AccountDeletionRequest).where(
            AccountDeletionRequest.user_id == user.id, AccountDeletionRequest.status == DeletionStatus.PENDING
        )
    )


def deletion_view(request: AccountDeletionRequest | None) -> dict[str, Any] | None:
    if request is None:
        return None
    return {
        "id": str(request.id),
        "status": request.status.value,
        "reason": request.reason,
        "requestedAt": request.requested_at,
        "decidedAt": request.decided_at,
    }


def request_deletion(db: Session, user: User, password: str, reason: str | None) -> AccountDeletionRequest:
    check_password(db, user, password)
    if pending_deletion(db, user) is not None:
        raise conflict("You have already asked us to close your account. We will look at it soon.", "ALREADY_REQUESTED")
    request = AccountDeletionRequest(user_id=user.id, reason=reason)
    db.add(request)
    audit(db, Actor.user(user.id), "account.deletion_requested", "User", user.id)
    db.commit()
    return request


def decide_deletion(
    db: Session, admin_id: uuid.UUID, request_id: uuid.UUID, approve: bool, note: str | None
) -> AccountDeletionRequest:
    """Approving removes the owner's public details and retires their tags. Orders and audit records stay."""
    request = db.get(AccountDeletionRequest, request_id)
    if request is None:
        raise not_found("Request not found", "REQUEST_NOT_FOUND")
    if request.status != DeletionStatus.PENDING:
        raise conflict("This request has already been decided.", "REQUEST_DECIDED")

    now = datetime.now(UTC)
    request.status = DeletionStatus.APPROVED if approve else DeletionStatus.REJECTED
    request.decided_at = now
    request.decided_by_admin_id = admin_id
    request.note = note

    if approve:
        user = db.get(User, request.user_id)
        assert user is not None
        # Their tags can never belong to anyone else, so they are retired, not just turned off.
        db.execute(
            update(Tag)
            .where(Tag.owner_id == user.id, Tag.status != TagStatus.RETIRED)
            .values(status=TagStatus.RETIRED, retired_at=now)
        )
        db.execute(delete(ContactCard).where(ContactCard.user_id == user.id))
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        # Keep the row (orders and audit records point at it) but nothing that identifies the person.
        user.name = "Deleted customer"
        # Not a valid number, unique per account, and short enough for the phone column.
        user.phone = f"deleted:{user.id.hex[:12]}"
        user.password_hash = hash_password(uuid.uuid4().hex + uuid.uuid4().hex)
        user.status = UserStatus.DELETED
        user.deleted_at = now
        user.phone_verified_at = None

    audit(
        db,
        Actor.admin(admin_id),
        "account.deletion_approved" if approve else "account.deletion_rejected",
        "User",
        request.user_id,
        {"note": note},
    )
    db.commit()
    return request
