"""allow nullable inactive ticket marker

Revision ID: 20260428_0004
Revises: 20260428_0003
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0004"
down_revision = "20260428_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    with op.batch_alter_table("ticket_sale") as batch_op:
        existing_checks = {
            constraint.get("name")
            for constraint in inspector.get_check_constraints("ticket_sale")
            if constraint.get("name")
        }
        if "ck_ticket_sale_is_active_ticket" in existing_checks:
            batch_op.drop_constraint(
                "ck_ticket_sale_is_active_ticket",
                type_="check",
            )
        batch_op.alter_column(
            "is_active_ticket",
            existing_type=sa.Integer(),
            nullable=True,
            existing_server_default="1",
        )
        batch_op.create_check_constraint(
            "ck_ticket_sale_is_active_ticket",
            "is_active_ticket IS NULL OR is_active_ticket = 1",
        )

    bind.execute(
        sa.text(
            """
            UPDATE ticket_sale
            SET is_active_ticket = NULL
            WHERE is_active_ticket = 0
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE ticket_sale
            SET is_active_ticket = 0
            WHERE is_active_ticket IS NULL
            """
        )
    )

    with op.batch_alter_table("ticket_sale") as batch_op:
        batch_op.drop_constraint("ck_ticket_sale_is_active_ticket", type_="check")
        batch_op.alter_column(
            "is_active_ticket",
            existing_type=sa.Integer(),
            nullable=False,
            existing_server_default="1",
        )
        batch_op.create_check_constraint(
            "ck_ticket_sale_is_active_ticket",
            "is_active_ticket IN (0, 1)",
        )
