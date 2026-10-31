import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from cartag.domain import (
    ActorType,
    BatchSource,
    BloodGroup,
    DeletionStatus,
    DeliveryStatus,
    OrderStatus,
    OtpPurpose,
    PaymentAttemptStatus,
    PaymentMethod,
    PaymentStatus,
    ProductColour,
    ProductSize,
    ScanOutcome,
    StockStatus,
    TagStatus,
    UserStatus,
)


def text_enum(enum_class: type[PyEnum]) -> Enum:
    """Stores an enum as text with a CHECK constraint, which is easy to migrate."""
    return Enum(
        enum_class,
        native_enum=False,
        length=24,
        create_constraint=True,
        values_callable=lambda e: [member.value for member in e],
        name=f"ck_{enum_class.__name__.lower()}",
    )


def now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(text_enum(UserStatus), default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the owner confirms this number with a code (during activation or when changing number).
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tags: Mapped[list["Tag"]] = relationship(back_populates="owner")
    card: Mapped["ContactCard | None"] = relationship(back_populates="user", uselist=False)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("ix_otp_phone_purpose_created", "phone", "purpose", "created_at"),
        Index("ix_otp_ip_created", "ip_hash", "created_at"),
        Index("ix_otp_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    phone: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[OtpPurpose] = mapped_column(text_enum(OtpPurpose))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = now_column()


class AuthThrottle(Base):
    """Failed-login counter keyed by identity ("user:+923001234567", "admin:a@b.com").

    Works the same whether or not the account exists, so lockouts never reveal which accounts exist.
    """

    __tablename__ = "auth_throttles"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user", "user_id"), Index("ix_user_sessions_expires", "expires_at"))

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = now_column()
    last_seen_at: Mapped[datetime] = now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship()


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now_column()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (Index("ix_admin_sessions_admin", "admin_id"), Index("ix_admin_sessions_expires", "expires_at"))

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = now_column()
    last_seen_at: Mapped[datetime] = now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_hash: Mapped[str | None] = mapped_column(String(64))

    admin: Mapped[Admin] = relationship()


class TagBatch(Base):
    __tablename__ = "tag_batches"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer)
    source: Mapped[BatchSource] = mapped_column(text_enum(BatchSource))
    # The base URL these codes were printed with (https://domain/t/CODE). Kept so a later domain
    # change never leaves us guessing what is on the physical tags.
    base_url: Mapped[str] = mapped_column(String(255))
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = now_column()

    tags: Mapped[list["Tag"]] = relationship(back_populates="batch")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        Index("ix_tags_owner", "owner_id"),
        Index("ix_tags_batch", "batch_id"),
        Index("ix_tags_status", "status"),
        Index("ix_tags_stock", "stock_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Sequential number for the team panel and the printer only. Never used in a URL.
    serial: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    # Random code printed in the QR URL. Never given to a second tag.
    code: Mapped[str] = mapped_column(String(24), unique=True)
    # What a scanner sees.
    status: Mapped[TagStatus] = mapped_column(text_enum(TagStatus), default=TagStatus.NOT_ACTIVE)
    # Where the physical tag is in the business. Only a SOLD tag can be activated.
    stock_status: Mapped[StockStatus] = mapped_column(
        text_enum(StockStatus), default=StockStatus.IN_STOCK, server_default=StockStatus.IN_STOCK.value
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tag_batches.id", ondelete="RESTRICT"))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User | None] = relationship(back_populates="tags")
    batch: Mapped[TagBatch] = relationship(back_populates="tags")


class ContactCard(Base):
    """What a finder sees about the owner. One card per account, shared by all of that owner's tags.

    The phone number is the account's verified mobile number. It is only ever used behind the Call and
    WhatsApp buttons, never printed as text.
    """

    __tablename__ = "contact_cards"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))

    # Emergency Mode is optional. These stay hidden unless the owner turns it on.
    emergency_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    blood_group: Mapped[BloodGroup | None] = mapped_column(text_enum(BloodGroup))
    emergency_name: Mapped[str | None] = mapped_column(String(80))
    emergency_relationship: Mapped[str | None] = mapped_column(String(40))
    emergency_phone: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="card")


class AccountDeletionRequest(Base):
    """A customer's request to close their account. Staff approve it; the data is removed then."""

    __tablename__ = "account_deletion_requests"
    __table_args__ = (Index("ix_deletion_status", "status"), Index("ix_deletion_user", "user_id"))

    id: Mapped[uuid.UUID] = uuid_pk()
    # No cascade: the user row is kept (anonymised) because orders and audit records still point at it.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[DeletionStatus] = mapped_column(text_enum(DeletionStatus), default=DeletionStatus.PENDING)
    reason: Mapped[str | None] = mapped_column(String(500))
    requested_at: Mapped[datetime] = now_column()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admins.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[User] = relationship()


class ScanEvent(Base):
    __tablename__ = "scan_events"
    __table_args__ = (Index("ix_scans_tag_at", "tag_id", "at"), Index("ix_scans_at", "at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tag_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tags.id", ondelete="SET NULL"))
    code_attempted: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[ScanOutcome] = mapped_column(text_enum(ScanOutcome))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    at: Mapped[datetime] = now_column()

    tag: Mapped[Tag | None] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_at", "at"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor", "actor_type", "actor_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = now_column()
    actor_type: Mapped[ActorType] = mapped_column(text_enum(ActorType))
    actor_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Product(Base):
    """One thing the shop sells: a size in a colour. Three sizes times four colours is twelve products."""

    __tablename__ = "products"
    __table_args__ = (Index("ix_products_active", "active"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    size: Mapped[ProductSize] = mapped_column(text_enum(ProductSize))
    colour: Mapped[ProductColour] = mapped_column(text_enum(ProductColour))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    # Whole rupees.
    price: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user", "user_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_payment_status", "payment_status"),
        Index("ix_orders_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Shown to people as CT-000123.
    number: Mapped[int] = mapped_column(Integer, Identity(), unique=True)
    # No cascade: a closed account is anonymised but its orders stay.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[OrderStatus] = mapped_column(text_enum(OrderStatus), default=OrderStatus.PLACED)
    payment_method: Mapped[PaymentMethod] = mapped_column(text_enum(PaymentMethod))
    payment_status: Mapped[PaymentStatus] = mapped_column(text_enum(PaymentStatus))

    subtotal: Mapped[int] = mapped_column(Integer)
    shipping_fee: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer)

    recipient_name: Mapped[str] = mapped_column(String(80))
    recipient_phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(String(300))

    courier: Mapped[str | None] = mapped_column(String(40))
    tracking_number: Mapped[str | None] = mapped_column(String(60))
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        text_enum(DeliveryStatus), default=DeliveryStatus.NOT_BOOKED, server_default=DeliveryStatus.NOT_BOOKED.value
    )

    created_at: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order", order_by="Payment.created_at")


class OrderItem(Base):
    """What was bought, copied at the time of the order so later price changes never rewrite history."""

    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order", "order_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    unit_price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    """One online payment attempt for an order. An order is marked paid only when the provider confirms it."""

    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_order", "order_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    # The provider's own reference for this payment, once known.
    reference: Mapped[str | None] = mapped_column(String(80))
    amount: Mapped[int] = mapped_column(Integer)
    status: Mapped[PaymentAttemptStatus] = mapped_column(
        text_enum(PaymentAttemptStatus), default=PaymentAttemptStatus.INITIATED
    )
    created_at: Mapped[datetime] = now_column()
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="payments")
