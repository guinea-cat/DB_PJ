from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint
from sqlalchemy import Index, Integer, Numeric, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.config import settings


def utcnow_naive() -> datetime:
    return datetime.now(ZoneInfo(settings.business_timezone)).replace(tzinfo=None)


class City(Base):
    __tablename__ = "city"

    city_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    city_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)


class Airport(Base):
    __tablename__ = "airport"

    airport_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    airport_name: Mapped[str] = mapped_column(String(50), nullable=False)
    city_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("city.city_code", ondelete="RESTRICT"),
        nullable=False,
    )


class Airplane(Base):
    __tablename__ = "airplane"
    __table_args__ = (
        CheckConstraint("f_class_capacity >= 0", name="ck_airplane_f_capacity_nonneg"),
        CheckConstraint("y_class_capacity >= 0", name="ck_airplane_y_capacity_nonneg"),
    )

    airplane_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    aircraft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    f_class_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    y_class_capacity: Mapped[int] = mapped_column(Integer, nullable=False)


class UserType(Base):
    __tablename__ = "user_type"
    __table_args__ = (
        CheckConstraint("discount_rate > 0", name="ck_user_type_discount_positive"),
        CheckConstraint("discount_rate <= 1", name="ck_user_type_discount_max"),
    )

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)


class Passenger(Base):
    __tablename__ = "passenger"
    __table_args__ = (
        UniqueConstraint("id_card_hash", name="uq_passenger_id_card_hash"),
        CheckConstraint("mileage_points >= 0", name="ck_passenger_mileage_nonneg"),
    )

    passenger_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_card_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    id_card_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    id_card_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    name_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    name_masked: Mapped[str] = mapped_column(String(50), nullable=False)
    type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user_type.type_id", ondelete="RESTRICT"),
        nullable=False,
    )
    mileage_points: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    user_type: Mapped[UserType] = relationship()


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("passenger_id", name="uq_account_passenger"),
        CheckConstraint("role IN ('ADMIN', 'USER')", name="ck_account_role"),
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name="ck_account_status"),
    )

    account_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login_identifier: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    passenger_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("passenger.passenger_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
    )

    passenger: Mapped[Passenger | None] = relationship()


class Route(Base):
    __tablename__ = "route"

    route_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    route_name: Mapped[str] = mapped_column(String(100), nullable=False)


class RouteSegment(Base):
    __tablename__ = "route_segment"
    __table_args__ = (
        UniqueConstraint("route_id", "segment_order", name="uq_route_segment_order"),
        CheckConstraint("segment_order >= 1", name="ck_route_segment_order_positive"),
        CheckConstraint(
            "dep_airport_code <> arr_airport_code",
            name="ck_route_segment_distinct_airports",
        ),
    )

    segment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("route.route_id", ondelete="CASCADE"),
        nullable=False,
    )
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    dep_airport_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("airport.airport_code", ondelete="RESTRICT"),
        nullable=False,
    )
    arr_airport_code: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("airport.airport_code", ondelete="RESTRICT"),
        nullable=False,
    )
    planned_dep_time: Mapped[time] = mapped_column(Time, nullable=False)
    planned_arr_time: Mapped[time] = mapped_column(Time, nullable=False)


class RoutePricing(Base):
    __tablename__ = "route_pricing"
    __table_args__ = (
        CheckConstraint("cabin_class IN ('F', 'Y')", name="ck_route_pricing_cabin_class"),
        CheckConstraint("base_price > 0", name="ck_route_pricing_base_price_positive"),
    )

    route_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("route.route_id", ondelete="CASCADE"),
        primary_key=True,
    )
    cabin_class: Mapped[str] = mapped_column(String(20), primary_key=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class FlightTemplate(Base):
    __tablename__ = "flight_template"
    __table_args__ = (
        CheckConstraint(
            "default_flight_discount > 0",
            name="ck_flight_template_discount_positive",
        ),
        CheckConstraint(
            "default_flight_discount <= 1",
            name="ck_flight_template_discount_max",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_flight_template_status",
        ),
    )

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    route_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("route.route_id", ondelete="RESTRICT"),
        nullable=False,
    )
    default_airplane_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("airplane.airplane_id", ondelete="RESTRICT"),
        nullable=False,
    )
    default_flight_discount: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class FlightTemplateWeekday(Base):
    __tablename__ = "flight_template_weekday"
    __table_args__ = (
        CheckConstraint("weekday >= 1", name="ck_template_weekday_min"),
        CheckConstraint("weekday <= 7", name="ck_template_weekday_max"),
    )

    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("flight_template.template_id", ondelete="CASCADE"),
        primary_key=True,
    )
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)


class FlightSchedule(Base):
    __tablename__ = "flight_schedule"
    __table_args__ = (
        CheckConstraint("flight_discount > 0", name="ck_flight_schedule_discount_positive"),
        CheckConstraint("flight_discount <= 1", name="ck_flight_schedule_discount_max"),
        CheckConstraint(
            "schedule_status IN ('ACTIVE', 'CANCELLED')",
            name="ck_flight_schedule_status",
        ),
    )

    flight_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    flight_date: Mapped[date] = mapped_column(Date, primary_key=True)
    route_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("route.route_id", ondelete="RESTRICT"),
        nullable=False,
    )
    airplane_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("airplane.airplane_id", ondelete="RESTRICT"),
        nullable=False,
    )
    flight_discount: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    schedule_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )
    template_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("flight_template.template_id", ondelete="SET NULL"),
        nullable=True,
    )


class DemoDataVersion(Base):
    __tablename__ = "demo_data_version"

    version_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
        onupdate=utcnow_naive,
    )


class ScheduleInventory(Base):
    __tablename__ = "schedule_inventory"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_no", "flight_date"],
            ["flight_schedule.flight_no", "flight_schedule.flight_date"],
            ondelete="CASCADE",
        ),
        CheckConstraint("f_seats_left >= 0", name="ck_inventory_f_nonneg"),
        CheckConstraint("y_seats_left >= 0", name="ck_inventory_y_nonneg"),
        Index("ix_schedule_inventory_flight_date_no", "flight_date", "flight_no"),
    )

    flight_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    flight_date: Mapped[date] = mapped_column(Date, primary_key=True)
    segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    f_seats_left: Mapped[int] = mapped_column(Integer, nullable=False)
    y_seats_left: Mapped[int] = mapped_column(Integer, nullable=False)


class SpecialFarePlan(Base):
    __tablename__ = "special_fare_plan"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_no", "flight_date"],
            ["flight_schedule.flight_no", "flight_schedule.flight_date"],
            ondelete="CASCADE",
        ),
        Index(
            "ix_special_fare_lookup",
            "flight_no",
            "flight_date",
            "cabin_class",
            "start_segment_id",
            "end_segment_id",
            "status",
        ),
        CheckConstraint("cabin_class IN ('F', 'Y')", name="ck_special_fare_cabin_class"),
        CheckConstraint("special_price > 0", name="ck_special_fare_price_positive"),
        CheckConstraint("quota_total > 0", name="ck_special_fare_quota_total_positive"),
        CheckConstraint("quota_used >= 0", name="ck_special_fare_quota_used_nonneg"),
        CheckConstraint("quota_used <= quota_total", name="ck_special_fare_quota_used_max"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_special_fare_status"),
    )

    special_fare_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_no: Mapped[str] = mapped_column(String(20), nullable=False)
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    cabin_class: Mapped[str] = mapped_column(String(20), nullable=False)
    start_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    end_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    special_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quota_total: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sale_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sale_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class TicketSale(Base):
    __tablename__ = "ticket_sale"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_no", "flight_date"],
            ["flight_schedule.flight_no", "flight_schedule.flight_date"],
            ondelete="RESTRICT",
        ),
        Index("ix_ticket_sale_owner_date_status", "passenger_id", "flight_date", "status"),
        UniqueConstraint(
            "passenger_id",
            "flight_no",
            "flight_date",
            "is_active_ticket",
            name="uq_ticket_sale_active_flight_per_passenger",
        ),
        UniqueConstraint("payment_id", name="uq_ticket_sale_payment_id"),
        CheckConstraint("cabin_class IN ('F', 'Y')", name="ck_ticket_sale_cabin_class"),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT', 'PAID', 'EXPIRED', 'REFUNDED', 'CANCELLED')",
            name="ck_ticket_sale_status",
        ),
        CheckConstraint(
            "price_source IN ('STANDARD', 'SPECIAL')",
            name="ck_ticket_sale_price_source",
        ),
        CheckConstraint(
            "is_active_ticket IS NULL OR is_active_ticket = 1",
            name="ck_ticket_sale_is_active_ticket",
        ),
        CheckConstraint("actual_price >= 0", name="ck_ticket_sale_actual_price_nonneg"),
        CheckConstraint("base_price_snapshot >= 0", name="ck_ticket_sale_base_price_snapshot_nonneg"),
        CheckConstraint(
            "flight_discount_snapshot > 0 AND flight_discount_snapshot <= 1.20",
            name="ck_ticket_sale_flight_discount_snapshot_range",
        ),
        CheckConstraint(
            "user_discount_snapshot > 0 AND user_discount_snapshot <= 1.20",
            name="ck_ticket_sale_user_discount_snapshot_range",
        ),
        CheckConstraint(
            "inventory_factor_snapshot > 0 AND inventory_factor_snapshot <= 2.00",
            name="ck_ticket_sale_inventory_factor_snapshot_range",
        ),
    )

    ticket_no: Mapped[str] = mapped_column(String(50), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(50), nullable=False)
    flight_no: Mapped[str] = mapped_column(String(20), nullable=False)
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    passenger_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("passenger.passenger_id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    end_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    cabin_class: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active_ticket: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        server_default="1",
    )
    actual_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    base_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    flight_discount_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    user_discount_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    inventory_factor_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    price_source: Mapped[str] = mapped_column(String(20), nullable=False)
    special_fare_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("special_fare_plan.special_fare_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def is_special_fare(self) -> bool:
        return self.price_source == "SPECIAL"


class PaymentRecord(Base):
    __tablename__ = "payment_record"
    __table_args__ = (
        UniqueConstraint("ticket_no", name="uq_payment_record_ticket"),
        CheckConstraint(
            "payment_method IN ('ALIPAY', 'WECHAT', 'BANK_CARD')",
            name="ck_payment_method",
        ),
        CheckConstraint(
            "payment_status IN ('PENDING', 'PAID', 'EXPIRED', 'REFUNDED')",
            name="ck_payment_status",
        ),
        CheckConstraint("pay_amount >= 0", name="ck_payment_amount_nonneg"),
    )

    payment_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ticket_no: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("ticket_sale.ticket_no", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False, default="ALIPAY")
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    pay_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    mock_trade_no: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    payer_account_masked: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payer_account_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WaitlistRecord(Base):
    __tablename__ = "waitlist_record"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flight_no", "flight_date"],
            ["flight_schedule.flight_no", "flight_schedule.flight_date"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_waitlist_dispatch",
            "flight_no",
            "flight_date",
            "cabin_class",
            "status",
            "request_time",
        ),
        CheckConstraint("cabin_class IN ('F', 'Y')", name="ck_waitlist_cabin_class"),
        CheckConstraint(
            "status IN ('WAITING', 'RELEASED', 'FULFILLED', 'EXPIRED', 'CANCELLED')",
            name="ck_waitlist_status",
        ),
    )

    waitlist_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_no: Mapped[str] = mapped_column(String(20), nullable=False)
    flight_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    end_segment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    cabin_class: Mapped[str] = mapped_column(String(20), nullable=False)
    passenger_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("passenger.passenger_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="WAITING")
    request_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    linked_ticket_no: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OperationAuditLog(Base):
    __tablename__ = "operation_audit_log"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_account_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("account.account_id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow_naive,
        server_default=func.now(),
    )
