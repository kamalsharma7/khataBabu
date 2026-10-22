"""Remove legacy demo inventory rows (e.g. paneer packs)."""

from alembic import op

revision = "20260320_0016"
down_revision = "20260320_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM inventory_items
        WHERE LOWER(name) LIKE '%paneer%'
           OR LOWER(name) LIKE '%1kg pack%'
        """
    )


def downgrade() -> None:
    pass
