"""Sales employee status fields and owner employee role."""

from alembic import op
import sqlalchemy as sa

revision = "20260320_0023"
down_revision = "20260320_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_sales_employees",
        sa.Column("date_of_joining", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
    )
    op.add_column(
        "platform_sales_employees",
        sa.Column(
            "employment_status",
            sa.Enum(
                "active",
                "blocked",
                "suspended",
                "left",
                "part_time",
                "probation",
                "on_leave",
                name="sales_employment_status",
                native_enum=False,
                length=32,
            ),
            server_default="active",
            nullable=False,
        ),
    )
    op.add_column(
        "platform_sales_employees",
        sa.Column(
            "behavior_status",
            sa.Enum(
                "good",
                "in_doubt",
                "angry",
                "sharp",
                "cooperative",
                "needs_attention",
                name="sales_behavior_status",
                native_enum=False,
                length=32,
            ),
            server_default="good",
            nullable=False,
        ),
    )
    op.add_column(
        "platform_sales_employees",
        sa.Column(
            "professional_status",
            sa.Enum(
                "good",
                "sales_expert",
                "sharp",
                "fresher",
                "rising_star",
                "mentor",
                name="sales_professional_status",
                native_enum=False,
                length=32,
            ),
            server_default="good",
            nullable=False,
        ),
    )
    op.alter_column("platform_sales_employees", "date_of_joining", server_default=None)

    op.alter_column(
        "business_owners",
        "role",
        existing_type=sa.Enum(
            "owner",
            "admin",
            "worker",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        type_=sa.Enum(
            "owner",
            "admin",
            "worker",
            "employee",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "business_owners",
        "role",
        existing_type=sa.Enum(
            "owner",
            "admin",
            "worker",
            "employee",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        type_=sa.Enum(
            "owner",
            "admin",
            "worker",
            name="owner_role",
            native_enum=False,
            length=16,
        ),
        existing_nullable=False,
    )
    op.drop_column("platform_sales_employees", "professional_status")
    op.drop_column("platform_sales_employees", "behavior_status")
    op.drop_column("platform_sales_employees", "employment_status")
    op.drop_column("platform_sales_employees", "date_of_joining")
