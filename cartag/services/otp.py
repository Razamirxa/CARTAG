from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from cartag.domain import OtpPurpose
from cartag.errors import too_many
from cartag.models import OtpChallenge
from cartag.security import hash_otp, new_otp_code, safe_equal
from cartag.services.sms import SmsProvider

OTP_TTL = timedelta(minutes=5)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
OTP_MAX_PER_PHONE_PER_HOUR = 5
OTP_MAX_PER_IP_PER_HOUR = 20


def request_otp(
    db: Session,
    *,
    phone: str,
    purpose: OtpPurpose,
    ip_hash: str | None,
    eligible: bool,
    sms: SmsProvider,
) -> int:
    """Creates a challenge and, when eligible, texts the code. Returns the resend delay in seconds.

    A challenge row is recorded even when the number is not eligible (for example registering an
    already-registered number). That keeps the cooldown, the hourly caps and the response identical
    either way, so this endpoint cannot be used to find out which numbers have accounts.
    """
    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)

    latest = db.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.phone == phone, OtpChallenge.purpose == purpose)
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    if latest is not None:
        wait = OTP_RESEND_COOLDOWN - (now - latest.created_at)
        if wait.total_seconds() > 0:
            raise too_many(
                "Please wait before requesting another code.",
                "OTP_COOLDOWN",
                {"retryAfterSeconds": int(wait.total_seconds()) + 1},
            )

    per_phone = db.scalar(
        select(func.count())
        .select_from(OtpChallenge)
        .where(OtpChallenge.phone == phone, OtpChallenge.created_at >= hour_ago)
    )
    per_ip = (
        db.scalar(
            select(func.count())
            .select_from(OtpChallenge)
            .where(OtpChallenge.ip_hash == ip_hash, OtpChallenge.created_at >= hour_ago)
        )
        if ip_hash
        else 0
    )
    if (per_phone or 0) >= OTP_MAX_PER_PHONE_PER_HOUR or (per_ip or 0) >= OTP_MAX_PER_IP_PER_HOUR:
        raise too_many("Too many codes requested. Please try again in an hour.", "OTP_LIMIT")

    code = new_otp_code()
    # Only the newest code is valid.
    db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.phone == phone, OtpChallenge.purpose == purpose, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    db.add(
        OtpChallenge(
            phone=phone,
            purpose=purpose,
            code_hash=hash_otp(phone, purpose.value, code),
            expires_at=now + OTP_TTL,
            ip_hash=ip_hash,
        )
    )
    db.commit()

    if eligible:
        sms.send(phone, f"Your CARTAG code is {code}. It is valid for 5 minutes. Do not share it with anyone.")
    return int(OTP_RESEND_COOLDOWN.total_seconds())


def verify_otp(db: Session, phone: str, purpose: OtpPurpose, code: str) -> bool:
    """Checks a code and consumes it. Returns False for wrong, expired, used or locked-out codes.

    A wrong guess counts against the challenge; after five the code is dead.
    """
    challenge = db.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.phone == phone,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > datetime.now(UTC),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    if challenge is None or challenge.attempts >= OTP_MAX_ATTEMPTS:
        return False

    if not safe_equal(challenge.code_hash, hash_otp(phone, purpose.value, code)):
        db.execute(
            update(OtpChallenge).where(OtpChallenge.id == challenge.id).values(attempts=OtpChallenge.attempts + 1)
        )
        db.commit()
        return False

    # Consume atomically so one correct code cannot be used twice by parallel requests.
    result = db.execute(
        update(OtpChallenge)
        .where(OtpChallenge.id == challenge.id, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=datetime.now(UTC))
    )
    db.commit()
    return result.rowcount == 1
