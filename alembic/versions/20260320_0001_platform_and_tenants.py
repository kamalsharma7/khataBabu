"""platform admins and tenant onboarding tables

Revision ID: 20260320_0001
Revises:
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260320_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_password_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("mobile"),
    )
    op.create_index("ix_platform_admins_username", "platform_admins", ["username"], unique=False)

    op.create_table(
        "platform_login_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=True),
        sa.Column("otp_attempts", sa.Integer(), nullable=False),
        sa.Column("password_verified", sa.Boolean(), nullable=False),
        sa.Column("otp_verified", sa.Boolean(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_login_sessions_admin_id", "platform_login_sessions", ["admin_id"])

    op.create_table(
        "platform_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_audit_logs_admin_id", "platform_audit_logs", ["admin_id"])

    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column(
            "business_type",
            sa.Enum(
                "restaurant",
                "restaurant_and_snooker",
                "cafe",
                "bar",
                "multi_venue",
                "other",
                name="business_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("primary_phone", sa.String(length=20), nullable=False),
        sa.Column("primary_email", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("gst_registered", sa.Boolean(), nullable=False),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("fssai", sa.String(length=32), nullable=True),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column(
            "plan_tier",
            sa.Enum("basic", "pro", "enterprise", name="plan_tier", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "suspended", name="tenant_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("onboarded_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["onboarded_by_admin_id"], ["platform_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_businesses_primary_email", "businesses", ["primary_email"])

    op.create_table(
        "outlets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address_line", sa.String(length=512), nullable=False),
        sa.Column("pincode", sa.String(length=12), nullable=False),
        sa.Column("outlet_phone", sa.String(length=20), nullable=True),
        sa.Column("operating_models", sa.JSON(), nullable=False),
        sa.Column("venue_kinds", sa.JSON(), nullable=False),
        sa.Column("time_based_billing_enabled", sa.Boolean(), nullable=False),
        sa.Column("rough_scale_notes", sa.String(length=512), nullable=True),
        sa.Column("ref_code", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "suspended", name="outlet_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ref_code", name="uq_outlets_ref_code"),
    )
    op.create_index("ix_outlets_business_id", "outlets", ["business_id"])
    op.create_index("ix_outlets_ref_code", "outlets", ["ref_code"])

    op.create_table(
        "business_owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("mobile", sa.String(length=20), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", name="owner_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_business_owners_email"),
        sa.UniqueConstraint("mobile", name="uq_business_owners_mobile"),
        sa.UniqueConstraint("username", name="uq_business_owners_username"),
    )
    op.create_index("ix_business_owners_business_id", "business_owners", ["business_id"])


def downgrade() -> None:
    op.drop_table("business_owners")
    op.drop_table("outlets")
    op.drop_table("businesses")
    op.drop_table("platform_audit_logs")
    op.drop_table("platform_login_sessions")
    op.drop_table("platform_admins")
