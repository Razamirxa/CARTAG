import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from cartag.config import get_settings
from cartag.domain import TAG_CODE_ALPHABET


def hmac_hex(secret: str, data: str) -> str:
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def safe_equal(a: str, b: str) -> bool:
    """Constant-time comparison of two strings of any length."""
    return hmac.compare_digest(a.encode(), b.encode())


# ---------- sessions ----------
def new_session_token() -> str:
    """256-bit random token for session cookies. Only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hmac_hex(get_settings().session_secret, f"session:{token}")


def hash_ip(ip: str | None) -> str | None:
    """One-way hash of an IP address, so scan and OTP logs never hold raw addresses."""
    if not ip:
        return None
    return hmac_hex(get_settings().ip_hash_salt, f"ip:{ip}")[:32]


# ---------- OTP ----------
def new_otp_code() -> str:
    return str(secrets.randbelow(1_000_000)).zfill(6)


def hash_otp(phone: str, purpose: str, code: str) -> str:
    return hmac_hex(get_settings().otp_secret, f"otp:{purpose}:{phone}:{code}")


# ---------- tags ----------
def new_tag_code(length: int | None = None) -> str:
    size = length or get_settings().tag_code_length
    return "".join(secrets.choice(TAG_CODE_ALPHABET) for _ in range(size))


# ---------- passwords ----------
# argon2id with 19 MiB memory and 2 passes: the OWASP-recommended minimum.
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


_DUMMY_HASH: str | None = None


def verify_against_dummy(password: str) -> None:
    """Verifying against this when the account does not exist keeps response time the same,
    so timing does not reveal which phone numbers or emails are registered."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password-for-timing")
    verify_password(_DUMMY_HASH, password)
