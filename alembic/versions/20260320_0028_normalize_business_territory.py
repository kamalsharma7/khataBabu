"""Normalize business city and state to canonical India territory lists."""

from alembic import op
import sqlalchemy as sa

from app.data.india_territory import normalize_state_city

revision = "20260320_0028"
down_revision = "20260320_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, city, state FROM businesses")).fetchall()
    for row in rows:
        business_id, city, state = row[0], row[1], row[2]
        new_state, new_city = normalize_state_city(state or "", city or "")
        conn.execute(
            sa.text("UPDATE businesses SET city = :city, state = :state WHERE id = :id"),
            {"city": new_city, "state": new_state, "id": business_id},
        )


def downgrade() -> None:
    pass
