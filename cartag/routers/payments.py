import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from cartag.db import SessionLocal, get_db
from cartag.deps import payment_provider_dep, require_user
from cartag.errors import AppError, not_found
from cartag.models import Payment, User
from cartag.schemas import MockPaymentOutcomeIn
from cartag.services import payments
from cartag.services.payments import MockProvider, PaymentProvider

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook/{provider_name}")
async def webhook(
    provider_name: str,
    request: Request,
    provider: PaymentProvider | None = Depends(payment_provider_dep),
):
    """The payment provider calls this when a payment succeeds or fails. No login: the signature is the proof."""
    if provider is None or provider.name != provider_name:
        raise AppError(404, "NOT_FOUND", "Not found")
    body = await request.body()
    event = provider.verify_webhook({k.lower(): v for k, v in request.headers.items()}, body)

    def work() -> None:
        with SessionLocal() as db:
            payments.apply_payment_event(db, event)

    await run_in_threadpool(work)
    return {"ok": True}


# ---------- the pretend provider's checkout page (development and tests only) ----------
def _own_mock_payment(db: Session, user: User, payment_id: uuid.UUID, provider: PaymentProvider | None) -> Payment:
    if not isinstance(provider, MockProvider):
        raise not_found()
    payment = db.scalar(select(Payment).where(Payment.id == payment_id))
    if payment is None or payment.order.user_id != user.id:
        raise not_found("Payment not found", "PAYMENT_NOT_FOUND")
    return payment


@router.get("/mock/{payment_id}")
def mock_payment(
    payment_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider | None = Depends(payment_provider_dep),
):
    payment = _own_mock_payment(db, user, payment_id, provider)
    return {"orderNumber": payment.order.number, "amount": payment.amount, "status": payment.status.value}


@router.post("/mock/{payment_id}/complete")
def mock_complete(
    payment_id: uuid.UUID,
    body: MockPaymentOutcomeIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    provider: PaymentProvider | None = Depends(payment_provider_dep),
):
    """Plays the part of the provider: builds a signed message and handles it the same way a real webhook is."""
    payment = _own_mock_payment(db, user, payment_id, provider)
    assert isinstance(provider, MockProvider)
    message, headers = provider.build_message(payment, succeeded=body.outcome == "success")
    payments.apply_payment_event(db, provider.verify_webhook(headers, message))
    return {"ok": True}
