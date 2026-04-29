"""add integrity constraints for core business tables

Revision ID: 20260428_0003
Revises: 20260428_0002
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0003"
down_revision = "20260428_0002"
branch_labels = None
depends_on = None


def _has_check_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _create_check_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    constraint_name: str,
    condition: str,
) -> None:
    if not _has_check_constraint(inspector, table_name, constraint_name):
        op.create_check_constraint(constraint_name, table_name, condition)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _create_check_if_missing(
        inspector,
        "user_type",
        "ck_user_type_discount_positive",
        "discount_rate > 0",
    )
    _create_check_if_missing(
        inspector,
        "user_type",
        "ck_user_type_discount_max",
        "discount_rate <= 1",
    )
    _create_check_if_missing(
        inspector,
        "account",
        "ck_account_role",
        "role IN ('ADMIN', 'USER')",
    )
    _create_check_if_missing(
        inspector,
        "account",
        "ck_account_status",
        "status IN ('ACTIVE', 'DISABLED')",
    )
    _create_check_if_missing(
        inspector,
        "route_segment",
        "ck_route_segment_order_positive",
        "segment_order >= 1",
    )
    _create_check_if_missing(
        inspector,
        "route_segment",
        "ck_route_segment_distinct_airports",
        "dep_airport_code <> arr_airport_code",
    )
    _create_check_if_missing(
        inspector,
        "route_pricing",
        "ck_route_pricing_cabin_class",
        "cabin_class IN ('F', 'Y')",
    )
    _create_check_if_missing(
        inspector,
        "route_pricing",
        "ck_route_pricing_base_price_positive",
        "base_price > 0",
    )
    _create_check_if_missing(
        inspector,
        "flight_template",
        "ck_flight_template_discount_positive",
        "default_flight_discount > 0",
    )
    _create_check_if_missing(
        inspector,
        "flight_template",
        "ck_flight_template_discount_max",
        "default_flight_discount <= 1",
    )
    _create_check_if_missing(
        inspector,
        "flight_template",
        "ck_flight_template_status",
        "status IN ('ACTIVE', 'INACTIVE')",
    )
    _create_check_if_missing(
        inspector,
        "flight_template_weekday",
        "ck_template_weekday_min",
        "weekday >= 1",
    )
    _create_check_if_missing(
        inspector,
        "flight_template_weekday",
        "ck_template_weekday_max",
        "weekday <= 7",
    )
    _create_check_if_missing(
        inspector,
        "flight_schedule",
        "ck_flight_schedule_discount_positive",
        "flight_discount > 0",
    )
    _create_check_if_missing(
        inspector,
        "flight_schedule",
        "ck_flight_schedule_discount_max",
        "flight_discount <= 1",
    )
    _create_check_if_missing(
        inspector,
        "flight_schedule",
        "ck_flight_schedule_status",
        "schedule_status IN ('ACTIVE', 'CANCELLED')",
    )
    _create_check_if_missing(
        inspector,
        "ticket_sale",
        "ck_ticket_sale_cabin_class",
        "cabin_class IN ('F', 'Y')",
    )
    _create_check_if_missing(
        inspector,
        "ticket_sale",
        "ck_ticket_sale_status",
        "status IN ('PAID', 'REFUNDED')",
    )
    _create_check_if_missing(
        inspector,
        "ticket_sale",
        "ck_ticket_sale_is_active_ticket",
        "is_active_ticket IN (0, 1)",
    )
    _create_check_if_missing(
        inspector,
        "ticket_sale",
        "ck_ticket_sale_actual_price_nonneg",
        "actual_price >= 0",
    )
    _create_check_if_missing(
        inspector,
        "waitlist_record",
        "ck_waitlist_cabin_class",
        "cabin_class IN ('F', 'Y')",
    )
    _create_check_if_missing(
        inspector,
        "waitlist_record",
        "ck_waitlist_status",
        "status IN ('WAITING', 'RELEASED', 'CANCELLED')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, constraint_name in [
        ("waitlist_record", "ck_waitlist_status"),
        ("waitlist_record", "ck_waitlist_cabin_class"),
        ("ticket_sale", "ck_ticket_sale_actual_price_nonneg"),
        ("ticket_sale", "ck_ticket_sale_is_active_ticket"),
        ("ticket_sale", "ck_ticket_sale_status"),
        ("ticket_sale", "ck_ticket_sale_cabin_class"),
        ("flight_schedule", "ck_flight_schedule_status"),
        ("flight_schedule", "ck_flight_schedule_discount_max"),
        ("flight_schedule", "ck_flight_schedule_discount_positive"),
        ("flight_template_weekday", "ck_template_weekday_max"),
        ("flight_template_weekday", "ck_template_weekday_min"),
        ("flight_template", "ck_flight_template_status"),
        ("flight_template", "ck_flight_template_discount_max"),
        ("flight_template", "ck_flight_template_discount_positive"),
        ("route_pricing", "ck_route_pricing_base_price_positive"),
        ("route_pricing", "ck_route_pricing_cabin_class"),
        ("route_segment", "ck_route_segment_distinct_airports"),
        ("route_segment", "ck_route_segment_order_positive"),
        ("account", "ck_account_status"),
        ("account", "ck_account_role"),
        ("user_type", "ck_user_type_discount_max"),
        ("user_type", "ck_user_type_discount_positive"),
    ]:
        if _has_check_constraint(inspector, table_name, constraint_name):
            op.drop_constraint(constraint_name, table_name, type_="check")
