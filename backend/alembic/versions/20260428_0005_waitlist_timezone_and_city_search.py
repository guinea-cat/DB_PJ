"""add waitlist offer fields and support business timezone rollout

Revision ID: 20260428_0005
Revises: 20260428_0004
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0005"
down_revision = "20260428_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns("waitlist_record")
    }
    if "linked_ticket_no" not in existing_columns:
        op.add_column(
            "waitlist_record",
            sa.Column("linked_ticket_no", sa.String(length=50), nullable=True),
        )
    if "offer_expires_at" not in existing_columns:
        op.add_column(
            "waitlist_record",
            sa.Column("offer_expires_at", sa.DateTime(), nullable=True),
        )
    with op.batch_alter_table("waitlist_record") as batch_op:
        batch_op.drop_constraint("ck_waitlist_status", type_="check")
        batch_op.create_check_constraint(
            "ck_waitlist_status",
            "status IN ('WAITING', 'RELEASED', 'FULFILLED', 'EXPIRED', 'CANCELLED')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns("waitlist_record")
    }
    with op.batch_alter_table("waitlist_record") as batch_op:
        batch_op.drop_constraint("ck_waitlist_status", type_="check")
        batch_op.create_check_constraint(
            "ck_waitlist_status",
            "status IN ('WAITING', 'RELEASED', 'CANCELLED')",
        )
    if "offer_expires_at" in existing_columns:
        op.drop_column("waitlist_record", "offer_expires_at")
    if "linked_ticket_no" in existing_columns:
        op.drop_column("waitlist_record", "linked_ticket_no")
