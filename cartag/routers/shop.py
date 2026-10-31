from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cartag.config import Settings
from cartag.db import get_db
from cartag.deps import payment_provider_dep, require_user, settings_dep
from cartag.errors import bad_request
from cartag.models import User
from cartag.schemas import CreateOrderIn
from cartag.services import payments
from cartag.services import shop as shop_service
from cartag.services.payments import PaymentProvider

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("/products")
def products(db: Session = Depends(get_db)):
    return {"products": [shop_service.product_view(p) for p in shop_service.list_products(db)]}


@router.get("/config")
def config(
    settings: Settings = Depends(settings_dep), provider: PaymentProvider | None = Depends(payment_provider_dep)
):
    """What the checkout needs to know: is online payment on, and what does delivery cost."""
    return {"paymentEnabled": provider is not None, "shippingFee": settings.shipping_fee_pkr}


@router.post("/orders", status_code=201)
def place_order(
    body: CreateOrderIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    provider: PaymentProvider | None = Depends(payment_provider_dep),
):
    order = shop_service.create_order(db, user, body, settings.shipping_fee_pkr, payments_enabled=provider is not None)
    checkout_url = None
    if provider is not None and order.payment_method.value == "PREPAID":
        checkout_url = payments.start_payment(db, order, provider, settings.public_base_url)
    return {"order": shop_service.order_view(order), "checkoutUrl": checkout_url}


@router.get("/orders")
def my_orders(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"orders": [shop_service.order_view(o, with_items=False) for o in shop_service.list_orders_of(db, user)]}


@router.get("/orders/{number}")
def my_order(number: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"order": shop_service.order_view(shop_service.get_order_of(db, user, number))}


@router.post("/orders/{number}/cancel")
def cancel_order(number: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return {"order": shop_service.order_view(shop_service.cancel_order_by_customer(db, user, number))}


@router.post("/orders/{number}/pay")
def pay_order(
    number: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
    provider: PaymentProvider | None = Depends(payment_provider_dep),
):
    """Opens a new payment attempt, for example after a failed one."""
    order = shop_service.get_order_of(db, user, number)
    if provider is None:
        raise bad_request("Online payment is not available yet.", "PAYMENT_UNAVAILABLE")
    return {"checkoutUrl": payments.start_payment(db, order, provider, settings.public_base_url)}
