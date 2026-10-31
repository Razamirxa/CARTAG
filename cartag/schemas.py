"""Request bodies. Field names are camelCase on the wire (the React app sends them that way)."""

import re
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from cartag.domain import (
    MAX_BATCH_SIZE,
    MAX_TAG_CODE_LENGTH,
    MIN_TAG_CODE_LENGTH,
    BloodGroup,
    DeliveryStatus,
    OrderStatus,
    PaymentMethod,
    is_valid_tag_code,
    normalize_pk_mobile,
    normalize_tag_code,
)


def _bad(message: str) -> Any:
    raise ValueError(message)


# ---------- reusable field types ----------
def _phone(value: str) -> str:
    normalized = normalize_pk_mobile(value)
    if normalized is None:
        raise ValueError("Enter a valid Pakistani mobile number (03XX XXXXXXX)")
    return normalized


def _optional_phone(value: str | None) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _phone(str(value))


def _name(value: str) -> str:
    value = value.strip()
    if len(value) < 2:
        raise ValueError("Enter a name")
    if len(value) > 80:
        raise ValueError("Name is too long")
    return value


def _password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value) > 128:
        raise ValueError("Password is too long")
    return value


def _digits(length: int, message: str):
    def check(value: str) -> str:
        if not re.fullmatch(rf"\d{{{length}}}", value):
            raise ValueError(message)
        return value

    return check


def _tag_code(value: str) -> str:
    code = normalize_tag_code(value)
    if len(code) > MAX_TAG_CODE_LENGTH + 8 or not is_valid_tag_code(code):
        raise ValueError(f"Tag code must be {MIN_TAG_CODE_LENGTH}-{MAX_TAG_CODE_LENGTH} letters and digits")
    return code


def optional_text(limit: int):
    def clean(value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > limit:
            raise ValueError(f"Must be {limit} characters or fewer")
        return value or None

    return clean


def _batch_name(value: str) -> str:
    value = value.strip()
    if not 2 <= len(value) <= 80:
        raise ValueError("Batch name must be 2 to 80 characters")
    return value


def _email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) or len(value) > 255:
        raise ValueError("Enter a valid email address")
    return value


Phone = Annotated[str, AfterValidator(_phone)]
OptionalPhone = Annotated[str | None, AfterValidator(_optional_phone)]
Name = Annotated[str, AfterValidator(_name)]
Password = Annotated[str, AfterValidator(_password)]
AnyPassword = Annotated[str, AfterValidator(lambda v: v if 1 <= len(v) <= 128 else _bad("Enter your password"))]
OtpCode = Annotated[str, AfterValidator(_digits(6, "Enter the 6-digit code"))]
TagCode = Annotated[str, AfterValidator(_tag_code)]
BatchName = Annotated[str, AfterValidator(_batch_name)]
Email = Annotated[str, AfterValidator(_email)]
Text40 = Annotated[str | None, AfterValidator(optional_text(40))]
Text80 = Annotated[str | None, AfterValidator(optional_text(80))]
Text60 = Annotated[str | None, AfterValidator(optional_text(60))]
Text200 = Annotated[str | None, AfterValidator(optional_text(200))]
Text300 = Annotated[str | None, AfterValidator(optional_text(300))]
Text500 = Annotated[str | None, AfterValidator(optional_text(500))]


class Body(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


# ---------- auth ----------
class RegisterIn(Body):
    phone: Phone
    name: Name
    password: Password


class LoginIn(Body):
    phone: Phone
    password: AnyPassword


class PasswordResetRequestIn(Body):
    phone: Phone


class PasswordResetIn(Body):
    phone: Phone
    otp: OtpCode
    new_password: Password


class AdminLoginIn(Body):
    email: Email
    password: AnyPassword


# ---------- owner account ----------
class UpdateProfileIn(Body):
    name: Name


class ContactCardIn(Body):
    """The owner's Contact Card. Emergency Mode is optional; when it is on, the contact is required."""

    display_name: Name
    emergency_enabled: StrictBool = False
    blood_group: BloodGroup | None = None
    emergency_name: Text80 = Field(default=None, validate_default=True)
    emergency_relationship: Text40 = Field(default=None, validate_default=True)
    emergency_phone: OptionalPhone = Field(default=None, validate_default=True)

    @field_validator("emergency_name", "emergency_relationship", "emergency_phone")
    @classmethod
    def _required_when_enabled(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("emergency_enabled") and not value:
            labels = {
                "emergency_name": "Enter the emergency contact's name",
                "emergency_relationship": "Enter how this person is related to you",
                "emergency_phone": "Enter the emergency contact's mobile number",
            }
            raise ValueError(labels[info.field_name or "emergency_name"])
        return value


class ActivateTagIn(Body):
    code: TagCode
    otp: OtpCode
    # Needed when the owner has no card yet; otherwise it updates the existing card.
    card: ContactCardIn | None = None


class PhoneChangeRequestIn(Body):
    phone: Phone
    password: AnyPassword


class PhoneChangeConfirmIn(Body):
    phone: Phone
    otp: OtpCode


class DeleteAccountIn(Body):
    password: AnyPassword
    reason: Text500 = None


# ---------- team panel ----------
class GenerateBatchIn(Body):
    name: BatchName
    quantity: StrictInt

    @model_validator(mode="after")
    def _quantity_in_range(self) -> "GenerateBatchIn":
        if not 1 <= self.quantity <= MAX_BATCH_SIZE:
            raise ValueError(f"Quantity must be between 1 and {MAX_BATCH_SIZE:,}")
        return self


class ImportBatchIn(Body):
    name: BatchName
    # One tag code per line, or CSV whose first column is the code. A header row is ignored.
    csv: Annotated[str, AfterValidator(lambda v: v if 1 <= len(v) <= 5_000_000 else _bad("Paste or upload some codes"))]


class RetireTagIn(Body):
    reason: Text200 = None


class DecisionIn(Body):
    note: Text500 = None


# ---------- shop ----------
def _address(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    if not 5 <= len(value) <= 300:
        raise ValueError("Enter the full delivery address")
    return value


def _city(value: str) -> str:
    value = value.strip()
    if not 2 <= len(value) <= 60:
        raise ValueError("Enter the city")
    return value


class OrderLineIn(Body):
    sku: Annotated[
        str, AfterValidator(lambda v: v.strip().upper() if 1 <= len(v.strip()) <= 40 else _bad("Unknown product"))
    ]
    quantity: StrictInt

    @model_validator(mode="after")
    def _quantity(self) -> "OrderLineIn":
        if not 1 <= self.quantity <= 20:
            raise ValueError("Quantity must be between 1 and 20")
        return self


class CreateOrderIn(Body):
    items: Annotated[list[OrderLineIn], Field(min_length=1, max_length=12)]
    recipient_name: Name
    recipient_phone: Phone
    address: Annotated[str, AfterValidator(_address)]
    city: Annotated[str, AfterValidator(_city)]
    notes: Text300 = None
    payment_method: PaymentMethod

    @model_validator(mode="after")
    def _no_repeated_products(self) -> "CreateOrderIn":
        skus = [line.sku for line in self.items]
        if len(set(skus)) != len(skus):
            raise ValueError("Each product can appear only once. Change its quantity instead.")
        return self


class UpdateProductIn(Body):
    price: StrictInt | None = None
    active: StrictBool | None = None
    description: Text500 = None

    @model_validator(mode="after")
    def _valid(self) -> "UpdateProductIn":
        if not self.model_fields_set:
            raise ValueError("Nothing to update")
        if "price" in self.model_fields_set and (self.price is None or not 0 <= self.price <= 1_000_000):
            raise ValueError("Price must be between 0 and 1,000,000")
        if "active" in self.model_fields_set and self.active is None:
            raise ValueError("Active must be true or false")
        return self


class OrderStatusIn(Body):
    status: OrderStatus


class DeliveryUpdateIn(Body):
    courier: Text40 = None
    tracking_number: Text60 = None
    delivery_status: DeliveryStatus | None = None

    @model_validator(mode="after")
    def _something(self) -> "DeliveryUpdateIn":
        if not self.model_fields_set:
            raise ValueError("Nothing to update")
        return self


class MockPaymentOutcomeIn(Body):
    outcome: Annotated[str, AfterValidator(lambda v: v if v in {"success", "failure"} else _bad("Unknown outcome"))]
