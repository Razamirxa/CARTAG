"""CARTAG V1 scope: contact cards, new tag states, stock status, account deletion requests

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=24)


def _check(name: str, table: str, column: str, *values: str) -> None:
    allowed = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(name, table, f"{column} IN ({allowed})")


TAG_STATUSES = ("NOT_ACTIVE", "ACTIVE", "TURNED_OFF", "RETIRED")
STOCK_STATUSES = ("IN_STOCK", "RESERVED", "SOLD", "DAMAGED", "REPLACED")
OUTCOMES = ("ACTIVE_PAGE", "NOT_ACTIVE_PAGE", "TURNED_OFF_PAGE", "RETIRED_PAGE", "NOT_FOUND")
PURPOSES = ("ACTIVATE_TAG", "RESET_PASSWORD", "CHANGE_PHONE")
USER_STATUSES = ("ACTIVE", "BLOCKED", "DELETED")
BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
DELETION_STATUSES = ("PENDING", "APPROVED", "REJECTED")


def upgrade() -> None:
    # ---- tags: new public states, separate stock status, no vehicle details, no PIN ----
    op.drop_constraint("ck_tagstatus", "tags", type_="check")
    op.drop_constraint("ck_vehicletype", "tags", type_="check")
    op.execute(
        "UPDATE tags SET status = CASE status "
        "WHEN 'UNCLAIMED' THEN 'NOT_ACTIVE' WHEN 'DEACTIVATED' THEN 'TURNED_OFF' "
        "WHEN 'DISABLED' THEN 'RETIRED' ELSE status END"
    )
    op.add_column(
        "tags",
        sa.Column("stock_status", sa.String(24), nullable=False, server_default="IN_STOCK"),
    )
    op.add_column("tags", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    # A tag somebody already activated was obviously sold.
    op.execute("UPDATE tags SET stock_status = 'SOLD' WHERE owner_id IS NOT NULL")
    op.execute("UPDATE tags SET retired_at = updated_at WHERE status = 'RETIRED'")
    _check("ck_tagstatus", "tags", "status", *TAG_STATUSES)
    _check("ck_stockstatus", "tags", "stock_status", *STOCK_STATUSES)

    op.drop_index("ix_tags_plate", table_name="tags")
    for column in (
        "vehicle_type",
        "plate",
        "make",
        "model",
        "color",
        "emergency_phone",
        "show_name",
        "show_phone",
        "allow_whatsapp",
        "show_plate",
        "show_vehicle_details",
        "show_emergency_phone",
        "pin_failures",
        "pin_locked_until",
    ):
        op.drop_column("tags", column)
    op.create_index("ix_tags_stock", "tags", ["stock_status"])
    op.drop_column("tag_batches", "require_pin")

    # ---- scan events: one outcome per state ----
    op.drop_constraint("ck_scanoutcome", "scan_events", type_="check")
    op.execute(
        "UPDATE scan_events SET outcome = CASE outcome "
        "WHEN 'UNCLAIMED_PAGE' THEN 'NOT_ACTIVE_PAGE' WHEN 'INACTIVE_PAGE' THEN 'TURNED_OFF_PAGE' "
        "ELSE outcome END"
    )
    _check("ck_scanoutcome", "scan_events", "outcome", *OUTCOMES)

    # ---- one-time codes: the purposes changed, and codes only live five minutes anyway ----
    op.execute("DELETE FROM otp_challenges")
    op.drop_constraint("ck_otppurpose", "otp_challenges", type_="check")
    _check("ck_otppurpose", "otp_challenges", "purpose", *PURPOSES)

    # ---- users ----
    op.drop_constraint("ck_userstatus", "users", type_="check")
    _check("ck_userstatus", "users", "status", *USER_STATUSES)
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # ---- new tables ----
    op.create_table(
        "contact_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("emergency_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("blood_group", _enum("ck_bloodgroup", *BLOOD_GROUPS), nullable=True),
        sa.Column("emergency_name", sa.String(80), nullable=True),
        sa.Column("emergency_relationship", sa.String(40), nullable=True),
        sa.Column("emergency_phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "account_deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", _enum("ck_deletionstatus", *DELETION_STATUSES), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["decided_by_admin_id"], ["admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deletion_status", "account_deletion_requests", ["status"])
    op.create_index("ix_deletion_user", "account_deletion_requests", ["user_id"])


def downgrade() -> None:
    raise NotImplementedError(
        "0002 drops vehicle details and activation PINs, so it cannot be undone. Restore a backup instead."
    )
