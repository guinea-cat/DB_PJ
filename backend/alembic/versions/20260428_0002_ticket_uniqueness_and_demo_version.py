"""ticket uniqueness and demo data version

Revision ID: 20260428_0002
Revises: 20260428_0001
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0002"
down_revision = "20260428_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "demo_data_version" not in inspector.get_table_names():
        op.create_table(
            "demo_data_version",
            sa.Column("version_key", sa.String(length=50), primary_key=True, nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    ticket_columns = {column["name"] for column in inspector.get_columns("ticket_sale")}
    if "is_active_ticket" not in ticket_columns:
        op.add_column(
            "ticket_sale",
            sa.Column(
                "is_active_ticket",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
        )

    bind.execute(
        sa.text(
            """
            UPDATE ticket_sale
            SET is_active_ticket = CASE
                WHEN status = 'REFUNDED' THEN 0
                ELSE 1
            END
            """
        )
    )

    owner_column = None
    if "id_card" in ticket_columns:
        owner_column = "id_card"
    elif "passenger_id" in ticket_columns:
        owner_column = "passenger_id"

    if owner_column is not None:
        duplicate_rows = bind.execute(
            sa.text(
                f"""
                SELECT {owner_column} AS owner_key, flight_no, flight_date, COUNT(*) AS ticket_count
                FROM ticket_sale
                WHERE is_active_ticket = 1
                GROUP BY {owner_column}, flight_no, flight_date
                HAVING COUNT(*) > 1
                """
            )
        ).fetchall()
        if duplicate_rows:
            duplicate_descriptions = ", ".join(
                f"{row.owner_key}/{row.flight_no}/{row.flight_date}"
                for row in duplicate_rows
            )
            raise RuntimeError(
                "Cannot apply active ticket uniqueness because duplicate active tickets exist: "
                f"{duplicate_descriptions}"
            )

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("ticket_sale")
        if constraint["name"]
    }
    if "uq_ticket_sale_active_flight_per_passenger" not in unique_constraints and owner_column is not None:
        op.create_unique_constraint(
            "uq_ticket_sale_active_flight_per_passenger",
            "ticket_sale",
            [owner_column, "flight_no", "flight_date", "is_active_ticket"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    unique_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("ticket_sale")
        if constraint["name"]
    }
    if "uq_ticket_sale_active_flight_per_passenger" in unique_constraints:
        op.drop_constraint(
            "uq_ticket_sale_active_flight_per_passenger",
            "ticket_sale",
            type_="unique",
        )

    ticket_columns = {column["name"] for column in inspector.get_columns("ticket_sale")}
    if "is_active_ticket" in ticket_columns:
        op.drop_column("ticket_sale", "is_active_ticket")

    if "demo_data_version" in inspector.get_table_names():
        op.drop_table("demo_data_version")
