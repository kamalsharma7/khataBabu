"""Normalize legacy enum strings in venue tables to lowercase values."""

from __future__ import annotations

from alembic import op

revision = "20260320_0011"
down_revision = "20260320_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE venue_tables SET resource_kind = lower(resource_kind)")
    op.execute("UPDATE venue_areas SET billing_mode = lower(billing_mode)")


def downgrade() -> None:
    pass
