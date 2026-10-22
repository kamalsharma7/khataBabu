"""Normalize business_owners.role to lowercase enum values."""

from alembic import op

revision = "20260320_0024"
down_revision = "20260320_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE business_owners
        SET role = lower(role)
        WHERE role <> lower(role)
        """,
    )


def downgrade() -> None:
    pass
