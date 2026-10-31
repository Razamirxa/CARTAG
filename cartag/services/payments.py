"""Online payment.

An order is marked paid only when the payment provider tells us so in a signed message (a webhook).
Nothing the customer's browser says can mark an order paid. A real provider is added as one more class
here; the rest of the app does not change.
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from cartag.config import Settings
from cartag.domain import OrderStatus, PaymentAttemptStatus, PaymentMethod, PaymentStatus
from cartag.errors import AppError, bad_request, conflict
from cartag.models import Order, Payment
from cartag.services.audit import Actor, audit


@dataclass(frozen=True)
class PaymentEvent:
    """What a provider's webhook says happened."""

    payment_id: uuid.UUID
    succeeded: bool
    amount: int | None = None
    reference: str | None = None


class PaymentProvider(Protocol):
    name: str

    def checkout_url(self, payment: Payment, base_url: str) -> str:
        """Where to send the customer to pay."""

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        """Checks the provider's signature and reads the message. Raises bad_request when it is not genuine."""


class MockProvider:
    """A pretend provider for development and tests. It signs its messages exactly like a real one would."""

    name = "mock"
    SIGNATURE_HEADER = "x-cartag-mock-signature"

    def __init__(self, secret: str):
        self._key = hmac.new(secret.encode(), b"mock-payments", hashlib.sha256).digest()

    def sign(self, body: bytes) -> str:
        return hmac.new(self._key, body, hashlib.sha256).hexdigest()

    def checkout_url(self, payment: Payment, base_url: str) -> str:
        return f"{base_url}/pay/mock/{payment.id}"

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        signature = headers.get(self.SIGNATURE_HEADER, "")
        if not hmac.compare_digest(signature.encode(), self.sign(body).encode()):
            raise bad_request("The payment message could not be verified.", "BAD_SIGNATURE")
        try:
            data = json.loads(body)
            return PaymentEvent(
                payment_id=uuid.UUID(data["paymentId"]),
                succeeded=data["status"] == "succeeded",
                amount=data.get("amount"),
                reference=data.get("reference"),
            )
        except (ValueError, KeyError, TypeError):
            raise bad_request("The payment message is not valid.", "BAD_PAYMENT_MESSAGE") from None

    def build_message(self, payment: Payment, succeeded: bool) -> tuple[bytes, dict[str, str]]:
        """What the pretend provider would send after the customer pays (or fails to)."""
        body = json.dumps(
            {
                "paymentId": str(payment.id),
                "status": "succeeded" if succeeded else "failed",
                "amount": payment.amount,
                "reference": f"MOCK-{payment.id.hex[:10].upper()}",
            }
        ).encode()
        return body, {self.SIGNATURE_HEADER: self.sign(body)}


def create_provider(settings: Settings, name: str | None = None) -> PaymentProvider | None:
    chosen = name or settings.payment_provider
    if chosen == "mock":
        return MockProvider(settings.session_secret)
    return None


def start_payment(db: Session, order: Order, provider: PaymentProvider, base_url: str) -> str:
    """Opens a payment attempt for a prepaid order and returns the page where the customer pays."""
    if order.payment_method != PaymentMethod.PREPAID:
        raise conflict("This order is paid on delivery.", "PAYMENT_STATE")
    if order.status != OrderStatus.PLACED or order.payment_status not in {PaymentStatus.DUE, PaymentStatus.FAILED}:
        raise conflict("This order cannot be paid now.", "PAYMENT_STATE")

    payment = Payment(order_id=order.id, provider=provider.name, amount=order.total)
    db.add(payment)
    order.payment_status = PaymentStatus.DUE
    db.flush()
    audit(
        db,
        Actor.user(order.user_id),
        "payment.start",
        "Order",
        order.id,
        {"number": order.number, "paymentId": str(payment.id)},
    )
    db.commit()
    return provider.checkout_url(payment, base_url)


def apply_payment_event(db: Session, event: PaymentEvent) -> Payment:
    """Records the provider's answer. Safe to receive twice: the second copy changes nothing."""
    payment = db.scalar(select(Payment).where(Payment.id == event.payment_id).with_for_update())
    if payment is None:
        raise AppError(404, "PAYMENT_NOT_FOUND", "Unknown payment")
    if payment.status != PaymentAttemptStatus.INITIATED:
        return payment

    order = db.scalar(select(Order).where(Order.id == payment.order_id).with_for_update())
    assert order is not None
    now = datetime.now(UTC)
    system = Actor.system()

    # A confirmation for the wrong amount is never trusted as a full payment.
    if event.succeeded and event.amount is not None and event.amount != payment.amount:
        payment.status = PaymentAttemptStatus.FAILED
        if order.payment_status == PaymentStatus.DUE:
            order.payment_status = PaymentStatus.FAILED
        audit(
            db, system, "payment.amount_mismatch", "Order", order.id, {"expected": payment.amount, "got": event.amount}
        )
        db.commit()
        return payment

    payment.reference = event.reference
    payment.confirmed_at = now
    if event.succeeded:
        payment.status = PaymentAttemptStatus.SUCCEEDED
        order.payment_status = PaymentStatus.PAID
        order.paid_at = now
        # If the customer cancelled while paying, the money still arrived: Finance has to refund it.
        action = "payment.paid_after_cancel" if order.status == OrderStatus.CANCELLED else "payment.paid"
        audit(db, system, action, "Order", order.id, {"number": order.number, "amount": payment.amount})
    else:
        payment.status = PaymentAttemptStatus.FAILED
        if order.payment_status == PaymentStatus.DUE:
            order.payment_status = PaymentStatus.FAILED
        audit(db, system, "payment.failed", "Order", order.id, {"number": order.number})
    db.commit()
    return payment
