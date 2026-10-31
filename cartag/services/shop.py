import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from cartag.domain import (
    PREMIUM_COLOURS,
    DeliveryStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ProductColour,
    ProductSize,
    format_order_number,
)
from cartag.errors import AppError, bad_request, conflict, not_found, too_many
from cartag.models import Order, OrderItem, Product, User
from cartag.schemas import CreateOrderIn, DeliveryUpdateIn, UpdateProductIn
from cartag.services.audit import Actor, audit

MAX_ORDERS_PER_DAY = 10

# Placeholder prices from the scope document's estimates. The team sets the real ones in the team panel.
BASE_PRICE = {ProductSize.COMPACT: 800, ProductSize.STANDARD: 900, ProductSize.LARGE: 1000}
PREMIUM_EXTRA = 100


# ---------- catalogue ----------
def ensure_catalog(db: Session) -> None:
    """Creates any of the twelve products that are missing. The migration already seeds them; tests use this."""
    existing = set(db.scalars(select(Product.sku)))
    for size_index, size in enumerate(ProductSize):
        for colour_index, colour in enumerate(ProductColour):
            sku = f"{size.value}-{colour.value}"
            if sku in existing:
                continue
            price = BASE_PRICE[size] + (PREMIUM_EXTRA if colour in PREMIUM_COLOURS else 0)
            db.add(
                Product(
                    sku=sku,
                    size=size,
                    colour=colour,
                    name=f"CARTAG {size.value.title()}, {colour.value.title()}",
                    price=price,
                    sort_order=size_index * 10 + colour_index,
                )
            )
    db.commit()


def product_view(product: Product) -> dict[str, Any]:
    return {
        "sku": product.sku,
        "size": product.size.value,
        "colour": product.colour.value,
        "premium": product.colour in PREMIUM_COLOURS,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "active": product.active,
    }


def list_products(db: Session, active_only: bool = True) -> list[Product]:
    stmt = select(Product).order_by(Product.sort_order, Product.sku)
    if active_only:
        stmt = stmt.where(Product.active.is_(True))
    return list(db.scalars(stmt))


def update_product(db: Session, admin_id: uuid.UUID, sku: str, data: UpdateProductIn) -> Product:
    product = db.scalar(select(Product).where(Product.sku == sku.upper()))
    if product is None:
        raise not_found("Product not found", "PRODUCT_NOT_FOUND")
    changes: dict[str, Any] = {}
    sent = data.model_fields_set
    if "price" in sent:
        changes["price"] = data.price
    if "active" in sent:
        changes["active"] = data.active
    if "description" in sent:
        changes["description"] = data.description
    before = {key: getattr(product, key) for key in changes}
    for key, value in changes.items():
        setattr(product, key, value)
    audit(
        db,
        Actor.admin(admin_id),
        "product.update",
        "Product",
        product.id,
        {"sku": product.sku, "from": before, "to": changes},
    )
    db.commit()
    return product


# ---------- views ----------
def order_view(order: Order, *, with_items: bool = True) -> dict[str, Any]:
    view: dict[str, Any] = {
        "number": order.number,
        "label": format_order_number(order.number),
        "status": order.status.value,
        "paymentMethod": order.payment_method.value,
        "paymentStatus": order.payment_status.value,
        "subtotal": order.subtotal,
        "shippingFee": order.shipping_fee,
        "total": order.total,
        "recipient": {
            "name": order.recipient_name,
            "phone": order.recipient_phone,
            "address": order.address,
            "city": order.city,
            "notes": order.notes,
        },
        "delivery": {
            "courier": order.courier,
            "trackingNumber": order.tracking_number,
            "status": order.delivery_status.value,
        },
        "createdAt": order.created_at,
        "paidAt": order.paid_at,
        "shippedAt": order.shipped_at,
        "deliveredAt": order.delivered_at,
        "cancelledAt": order.cancelled_at,
    }
    if with_items:
        view["items"] = [
            {
                "sku": item.sku,
                "name": item.name,
                "unitPrice": item.unit_price,
                "quantity": item.quantity,
                "lineTotal": item.line_total,
            }
            for item in order.items
        ]
    return view


# ---------- placing an order ----------
def create_order(db: Session, user: User, data: CreateOrderIn, shipping_fee: int, payments_enabled: bool) -> Order:
    """Builds an order from a basket. Prices always come from the database, never from the browser."""
    if data.payment_method == PaymentMethod.PREPAID and not payments_enabled:
        raise bad_request("Online payment is not available yet. Please choose cash on delivery.", "PAYMENT_UNAVAILABLE")

    since = datetime.now(UTC) - timedelta(days=1)
    recent = (
        db.scalar(select(func.count()).select_from(Order).where(Order.user_id == user.id, Order.created_at >= since))
        or 0
    )
    if recent >= MAX_ORDERS_PER_DAY:
        raise too_many("You have placed many orders today. Please contact us if you need more.", "ORDER_LIMIT")

    wanted = {line.sku: line.quantity for line in data.items}
    products = {p.sku: p for p in db.scalars(select(Product).where(Product.sku.in_(wanted)))}
    missing = [sku for sku in wanted if sku not in products or not products[sku].active]
    if missing:
        raise AppError(
            400, "PRODUCT_UNAVAILABLE", "Some products in your basket are no longer available.", {"skus": missing}
        )

    order = Order(
        user_id=user.id,
        payment_method=data.payment_method,
        payment_status=PaymentStatus.DUE if data.payment_method == PaymentMethod.PREPAID else PaymentStatus.COD_PENDING,
        shipping_fee=shipping_fee,
        subtotal=0,
        total=0,
        recipient_name=data.recipient_name,
        recipient_phone=data.recipient_phone,
        address=data.address,
        city=data.city,
        notes=data.notes,
    )
    subtotal = 0
    for sku, quantity in wanted.items():
        product = products[sku]
        line_total = product.price * quantity
        subtotal += line_total
        order.items.append(
            OrderItem(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                unit_price=product.price,
                quantity=quantity,
                line_total=line_total,
            )
        )
    order.subtotal = subtotal
    order.total = subtotal + shipping_fee
    db.add(order)
    db.flush()
    audit(
        db,
        Actor.user(user.id),
        "order.place",
        "Order",
        order.id,
        {"number": order.number, "total": order.total, "method": order.payment_method.value},
    )
    db.commit()
    return order


# ---------- customer's own orders ----------
def list_orders_of(db: Session, user: User) -> list[Order]:
    return list(db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(50)))


def get_order_of(db: Session, user: User, number: int) -> Order:
    order = db.scalar(select(Order).where(Order.number == number, Order.user_id == user.id))
    if order is None:
        raise not_found("Order not found", "ORDER_NOT_FOUND")
    return order


def cancel_order_by_customer(db: Session, user: User, number: int) -> Order:
    order = get_order_of(db, user, number)
    if order.status != OrderStatus.PLACED:
        raise conflict("This order is already being prepared. Please contact us to change it.", "ORDER_STATE")
    if order.payment_status in {PaymentStatus.PAID, PaymentStatus.CHECKING}:
        raise conflict("This order is already paid. Please contact us and we will refund it.", "ORDER_PAID")
    order.status = OrderStatus.CANCELLED
    order.payment_status = PaymentStatus.CANCELLED
    order.cancelled_at = datetime.now(UTC)
    audit(db, Actor.user(user.id), "order.cancel", "Order", order.id, {"number": order.number})
    db.commit()
    return order


# ---------- team ----------
_ALLOWED_STATUS_CHANGES = {
    OrderStatus.PLACED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
    OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def get_order(db: Session, number: int) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.number == number)
        .options(joinedload(Order.user), joinedload(Order.items), joinedload(Order.payments))
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise not_found("Order not found", "ORDER_NOT_FOUND")
    return order


def set_order_status(db: Session, admin_id: uuid.UUID, number: int, new_status: OrderStatus) -> Order:
    order = get_order(db, number)
    if new_status not in _ALLOWED_STATUS_CHANGES[order.status]:
        raise conflict(
            f"An order that is {order.status.value.lower()} cannot become {new_status.value.lower()}.", "ORDER_STATE"
        )
    now = datetime.now(UTC)
    previous = order.status.value
    order.status = new_status
    if new_status == OrderStatus.SHIPPED:
        order.shipped_at = now
    elif new_status == OrderStatus.DELIVERED:
        order.delivered_at = now
        order.delivery_status = DeliveryStatus.DELIVERED
    elif new_status == OrderStatus.CANCELLED:
        order.cancelled_at = now
        # Money that never arrived is simply cancelled. Money that did arrive stays PAID until Finance refunds it.
        if order.payment_status in {
            PaymentStatus.DUE,
            PaymentStatus.FAILED,
            PaymentStatus.CHECKING,
            PaymentStatus.COD_PENDING,
        }:
            order.payment_status = PaymentStatus.CANCELLED
    audit(
        db,
        Actor.admin(admin_id),
        "order.status",
        "Order",
        order.id,
        {"number": number, "from": previous, "to": new_status.value},
    )
    db.commit()
    return order


def update_delivery(db: Session, admin_id: uuid.UUID, number: int, data: DeliveryUpdateIn) -> Order:
    order = get_order(db, number)
    sent = data.model_fields_set
    if "courier" in sent:
        order.courier = data.courier
    if "tracking_number" in sent:
        order.tracking_number = data.tracking_number
    if "delivery_status" in sent and data.delivery_status is not None:
        order.delivery_status = data.delivery_status
        if data.delivery_status == DeliveryStatus.DELIVERED and order.status == OrderStatus.SHIPPED:
            order.status = OrderStatus.DELIVERED
            order.delivered_at = datetime.now(UTC)
    audit(
        db,
        Actor.admin(admin_id),
        "order.delivery",
        "Order",
        order.id,
        {
            "number": number,
            "courier": order.courier,
            "tracking": order.tracking_number,
            "status": order.delivery_status.value,
        },
    )
    db.commit()
    return order


def mark_cod_collected(db: Session, admin_id: uuid.UUID, number: int) -> Order:
    order = get_order(db, number)
    if order.payment_method != PaymentMethod.COD or order.payment_status != PaymentStatus.COD_PENDING:
        raise conflict(
            "Only a cash-on-delivery order that is waiting for payment can be marked as collected.", "PAYMENT_STATE"
        )
    if order.status not in {OrderStatus.SHIPPED, OrderStatus.DELIVERED}:
        raise conflict("The courier can only collect cash once the parcel has been shipped.", "PAYMENT_STATE")
    order.payment_status = PaymentStatus.COD_COLLECTED
    order.paid_at = datetime.now(UTC)
    audit(db, Actor.admin(admin_id), "order.cod_collected", "Order", order.id, {"number": number})
    db.commit()
    return order


def mark_refunded(db: Session, admin_id: uuid.UUID, number: int) -> Order:
    order = get_order(db, number)
    if order.payment_status not in {PaymentStatus.PAID, PaymentStatus.COD_COLLECTED}:
        raise conflict("Only an order that was paid can be marked as refunded.", "PAYMENT_STATE")
    order.payment_status = PaymentStatus.REFUNDED
    audit(db, Actor.admin(admin_id), "order.refunded", "Order", order.id, {"number": number, "total": order.total})
    db.commit()
    return order
