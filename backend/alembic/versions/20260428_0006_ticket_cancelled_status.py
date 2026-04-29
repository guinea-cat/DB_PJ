"""add cancelled status for pending-ticket user cancellation

Revision ID: 20260428_0006
Revises: 20260428_0005
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op


revision = "20260428_0006"
down_revision = "20260428_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ticket_sale") as batch_op:
        batch_op.drop_constraint("ck_ticket_sale_status", type_="check")
        batch_op.create_check_constraint(
            "ck_ticket_sale_status",
            "status IN ('PENDING_PAYMENT', 'PAID', 'EXPIRED', 'REFUNDED', 'CANCELLED')",
        )


def downgrade() -> None:
    with op.batch_alter_table("ticket_sale") as batch_op:
        batch_op.drop_constraint("ck_ticket_sale_status", type_="check")
        batch_op.create_check_constraint(
            "ck_ticket_sale_status",
            "status IN ('PENDING_PAYMENT', 'PAID', 'EXPIRED', 'REFUNDED')",
        )
