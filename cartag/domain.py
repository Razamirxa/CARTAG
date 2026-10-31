"""Rules that define what a valid tag code, phone number and contact card look like."""

import re
from enum import StrEnum

import phonenumbers

# ---------- tag codes ----------
# Printed inside the QR URL: https://domain/t/<CODE>.
# Random, never derived from the serial number, so codes cannot be enumerated. Crockford-style
# alphabet without the easily confused I, L, O and U. Always upper case: an all-upper-case URL
# fits QR "alphanumeric mode", which makes a smaller symbol on a small tag.
TAG_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MIN_TAG_CODE_LENGTH = 6
MAX_TAG_CODE_LENGTH = 24
_CODE_PATTERN = re.compile(rf"^[{TAG_CODE_ALPHABET}]{{{MIN_TAG_CODE_LENGTH},{MAX_TAG_CODE_LENGTH}}}$")

MAX_BATCH_SIZE = 100_000
MAX_TAGS_PER_USER = 25


def normalize_tag_code(value: str) -> str:
    """Upper-cases and trims user or URL input. Does not validate."""
    return value.strip().upper()


def is_valid_tag_code(code: str) -> bool:
    return _CODE_PATTERN.match(code) is not None


def format_serial(serial: int) -> str:
    """Serial numbers are shown as 000001 in the team panel and the printer CSV."""
    return str(serial).zfill(6)


# ---------- enums (stored as text, so adding a value never needs a database type change) ----------
class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    DELETED = "DELETED"


class OtpPurpose(StrEnum):
    ACTIVATE_TAG = "ACTIVATE_TAG"
    RESET_PASSWORD = "RESET_PASSWORD"
    CHANGE_PHONE = "CHANGE_PHONE"


class TagStatus(StrEnum):
    """What a person who scans the tag sees."""

    NOT_ACTIVE = "NOT_ACTIVE"  # the owner has not turned it on yet
    ACTIVE = "ACTIVE"  # the owner turned it on
    TURNED_OFF = "TURNED_OFF"  # the owner turned it off for now (can be turned on again)
    RETIRED = "RETIRED"  # stopped for good by staff; never turned on again, code never reused


class StockStatus(StrEnum):
    """Where the physical tag is in the business. Separate from TagStatus: a sold tag can still be not active."""

    IN_STOCK = "IN_STOCK"
    RESERVED = "RESERVED"  # matched to an order, not shipped yet
    SOLD = "SOLD"
    DAMAGED = "DAMAGED"
    REPLACED = "REPLACED"


class BatchSource(StrEnum):
    GENERATED = "GENERATED"
    IMPORTED = "IMPORTED"


class ActorType(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"
    SYSTEM = "SYSTEM"


class ScanOutcome(StrEnum):
    ACTIVE_PAGE = "ACTIVE_PAGE"
    NOT_ACTIVE_PAGE = "NOT_ACTIVE_PAGE"
    TURNED_OFF_PAGE = "TURNED_OFF_PAGE"
    RETIRED_PAGE = "RETIRED_PAGE"
    NOT_FOUND = "NOT_FOUND"


class DeletionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BloodGroup(StrEnum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


# ---------- shop ----------
class ProductSize(StrEnum):
    COMPACT = "COMPACT"
    STANDARD = "STANDARD"
    LARGE = "LARGE"


class ProductColour(StrEnum):
    BLACK = "BLACK"
    IVORY = "IVORY"
    BURGUNDY = "BURGUNDY"
    GLACIER = "GLACIER"


PREMIUM_COLOURS = frozenset({ProductColour.BURGUNDY, ProductColour.GLACIER})


class OrderStatus(StrEnum):
    PLACED = "PLACED"
    PROCESSING = "PROCESSING"  # the team is preparing the parcel
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class PaymentMethod(StrEnum):
    COD = "COD"  # cash on delivery
    PREPAID = "PREPAID"  # paid online before dispatch


class PaymentStatus(StrEnum):
    # prepaid orders
    DUE = "DUE"
    CHECKING = "CHECKING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    # cash on delivery
    COD_PENDING = "COD_PENDING"
    COD_COLLECTED = "COD_COLLECTED"


class DeliveryStatus(StrEnum):
    NOT_BOOKED = "NOT_BOOKED"
    BOOKED = "BOOKED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETURNED = "RETURNED"


class PaymentAttemptStatus(StrEnum):
    INITIATED = "INITIATED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def format_order_number(number: int) -> str:
    """Order numbers are shown as CT-000123."""
    return f"CT-{number:06d}"


# ---------- phone numbers ----------
def normalize_pk_mobile(value: str) -> str | None:
    """Normalizes a Pakistani mobile number to E.164 (+923XXXXXXXXX).

    Accepts 03XX-XXXXXXX, 3XXXXXXXXX, 92 3XX..., +92 3XX..., 0092 3XX... and common separators.
    Returns None for anything that is not a valid Pakistani mobile number.
    """
    cleaned = re.sub(r"[\s().\-]", "", value.strip())
    if not cleaned:
        return None
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    try:
        parsed = phonenumbers.parse(cleaned, "PK")
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed) or phonenumbers.region_code_for_number(parsed) != "PK":
        return None
    # Pakistani mobile numbers are 3XX XXXXXXX (10 digits after the country code).
    if not re.fullmatch(r"3\d{9}", str(parsed.national_number)):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def format_pk_mobile(e164: str) -> str:
    """Formats an E.164 Pakistani number for display: 0300 1234567."""
    digits = e164.removeprefix("+92")
    if not re.fullmatch(r"3\d{9}", digits):
        return e164
    return f"0{digits[:3]} {digits[3:]}"


def mask_phone(e164: str) -> str:
    """Hides the middle of a number for logs: +92300****567."""
    if len(e164) < 8:
        return "****"
    return f"{e164[:6]}****{e164[-3:]}"
