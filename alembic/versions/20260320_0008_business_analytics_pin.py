"""Business overview analytics PIN."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260320_0008"
down_revision = "20260320_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("analytics_pin_hash", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "analytics_pin_hash")
