from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from itertools import product
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.inventory_stream import inventory_event_broker
from app.models import (
    Account,
    Airplane,
    Airport,
    City,
    FlightSchedule,
    FlightTemplate,
    FlightTemplateWeekday,
    OperationAuditLog,
    Passenger,
    PaymentRecord,
    RoutePricing,
    RouteSegment,
    ScheduleInventory,
    SpecialFarePlan,
    TicketSale,
    UserType,
    WaitlistRecord,
)
from app.schemas import SearchFlightQuery, SearchFlightRangeQuery
from app.security import hash_sensitive_value


@dataclass(frozen=True)
class GenerateScheduleSummary:
    template_id: int
    template_weekdays: list[int]
    matched_dates: list[date]
    generated_dates: list[date]
    skipped_existing_dates: list[date]


@dataclass(frozen=True)
class PriceComputation:
    final_price: Decimal
    base_price: Decimal
    flight_discount: Decimal
    user_discount: Decimal
    inventory_factor: Decimal
    price_source: str
    special_fare_id: int | None
    is_special_fare: bool
    special_fare_tag: str | None


def utcnow_naive() -> datetime:
    return datetime.now(ZoneInfo(settings.business_timezone)).replace(tzinfo=None)


def decimal_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_audit_log(
    db: Session,
    actor: Account | None,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: str,
) -> None:
    db.add(
        OperationAuditLog(
            actor_account_id=actor.account_id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
        ),
    )


def publish_inventory_update(
    flight_no: str,
    flight_date: date,
    cabin_class: str,
    start_segment_id: int,
    end_segment_id: int,
    reason: str,
) -> None:
    inventory_event_broker.publish(
        {
            "flight_no": flight_no,
            "flight_date": flight_date.isoformat(),
            "cabin_class": cabin_class,
            "start_segment_id": start_segment_id,
            "end_segment_id": end_segment_id,
            "reason": reason,
        }
    )


def mask_id_card(id_card: str) -> str:
    if len(id_card) <= 7:
        return "*" * len(id_card)
    return f"{id_card[:3]}{'*' * (len(id_card) - 7)}{id_card[-4:]}"


def mask_name(name: str) -> str:
    normalized = name.strip()
    if len(normalized) <= 1:
        return "*"
    if len(normalized) == 2:
        return f"{normalized[0]}*"
    return f"{normalized[0]}{'*' * (len(normalized) - 2)}{normalized[-1]}"


def mask_payment_account(account: str) -> str:
    normalized = account.strip()
    if len(normalized) <= 6:
        return normalized[0] + "*" * max(len(normalized) - 1, 0)
    return f"{normalized[:3]}{'*' * (len(normalized) - 5)}{normalized[-2:]}"


def get_passenger_for_account(db: Session, account: Account) -> Passenger:
    if account.passenger_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current account is not bound to a passenger profile.",
        )
    passenger = db.get(Passenger, account.passenger_id)
    if passenger is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passenger profile not found.",
        )
    return passenger


def get_user_type_by_name(db: Session, type_name: str) -> UserType:
    user_type = db.scalar(select(UserType).where(UserType.type_name == type_name))
    if user_type is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{type_name} user type is not configured.",
        )
    return user_type


def get_vip_type(db: Session) -> UserType:
    return get_user_type_by_name(db, "VIP")


def get_normal_type(db: Session) -> UserType:
    return get_user_type_by_name(db, "NORMAL")


def get_segment_range(
    db: Session,
    route_id: str,
    start_segment_id: int,
    end_segment_id: int,
) -> list[RouteSegment]:
    start_segment = db.get(RouteSegment, start_segment_id)
    end_segment = db.get(RouteSegment, end_segment_id)
    if start_segment is None or end_segment is None:
        raise HTTPException(status_code=404, detail="Segment not found.")
    if start_segment.route_id != route_id or end_segment.route_id != route_id:
        raise HTTPException(status_code=400, detail="Segments do not belong to route.")
    if start_segment.segment_order > end_segment.segment_order:
        raise HTTPException(status_code=400, detail="Segment order is invalid.")
    segments = db.scalars(
        select(RouteSegment)
        .where(
            RouteSegment.route_id == route_id,
            RouteSegment.segment_order >= start_segment.segment_order,
            RouteSegment.segment_order <= end_segment.segment_order,
        )
        .order_by(RouteSegment.segment_order),
    ).all()
    if len(segments) != end_segment.segment_order - start_segment.segment_order + 1:
        raise HTTPException(status_code=400, detail="Segment range is not continuous.")
    return segments


def _lock_inventories(
    db: Session,
    flight_no: str,
    flight_date: date,
    segment_ids: list[int],
) -> list[ScheduleInventory]:
    inventories = db.scalars(
        select(ScheduleInventory)
        .where(
            ScheduleInventory.flight_no == flight_no,
            ScheduleInventory.flight_date == flight_date,
            ScheduleInventory.segment_id.in_(segment_ids),
        )
        .with_for_update(),
    ).all()
    if len(inventories) != len(segment_ids):
        raise HTTPException(status_code=400, detail="Inventory rows missing.")
    inventory_map = {inventory.segment_id: inventory for inventory in inventories}
    return [inventory_map[segment_id] for segment_id in segment_ids]


def _sync_passenger_type(db: Session, passenger: Passenger) -> None:
    vip_type = get_vip_type(db)
    if passenger.mileage_points >= Decimal("10000.00"):
        if passenger.type_id != vip_type.type_id:
            passenger.type_id = vip_type.type_id
        return

    normal_type = get_normal_type(db)
    if passenger.type_id != normal_type.type_id:
        passenger.type_id = normal_type.type_id


def _reverse_passenger_points(passenger: Passenger, amount: Decimal) -> None:
    updated_points = passenger.mileage_points - amount
    if updated_points < Decimal("0.00"):
        updated_points = Decimal("0.00")
    passenger.mileage_points = decimal_money(updated_points)


def _inventory_factor(min_seats_left: int, total_capacity: int) -> Decimal:
    if total_capacity <= 0:
        return Decimal("1.10")
    remaining_ratio = Decimal(min_seats_left) / Decimal(total_capacity)
    if remaining_ratio >= Decimal("0.50"):
        return Decimal("1.00")
    if remaining_ratio >= Decimal("0.20"):
        return Decimal("1.05")
    return Decimal("1.10")


def _load_special_fare(
    db: Session,
    flight_no: str,
    flight_date: date,
    cabin_class: str,
    start_segment_id: int,
    end_segment_id: int,
    *,
    for_update: bool = False,
) -> SpecialFarePlan | None:
    statement = (
        select(SpecialFarePlan)
        .where(
            SpecialFarePlan.flight_no == flight_no,
            SpecialFarePlan.flight_date == flight_date,
            SpecialFarePlan.cabin_class == cabin_class,
            SpecialFarePlan.start_segment_id == start_segment_id,
            SpecialFarePlan.end_segment_id == end_segment_id,
            SpecialFarePlan.status == "ACTIVE",
        )
        .order_by(SpecialFarePlan.special_fare_id)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def _compute_price_for_match(
    db: Session,
    schedule: FlightSchedule,
    passenger: Passenger,
    cabin_class: str,
    start_segment_id: int,
    end_segment_id: int,
    inventories: list[ScheduleInventory],
) -> PriceComputation:
    route_price = db.get(RoutePricing, {"route_id": schedule.route_id, "cabin_class": cabin_class})
    if route_price is None:
        raise HTTPException(status_code=404, detail="Cabin pricing not found.")

    passenger_type = db.get(UserType, passenger.type_id)
    if passenger_type is None:
        raise HTTPException(status_code=500, detail="Passenger user type missing.")

    special_fare = _load_special_fare(
        db,
        schedule.flight_no,
        schedule.flight_date,
        cabin_class,
        start_segment_id,
        end_segment_id,
    )
    now = utcnow_naive()
    if (
        special_fare is not None
        and special_fare.sale_start <= now <= special_fare.sale_end
        and special_fare.quota_used < special_fare.quota_total
    ):
        return PriceComputation(
            final_price=decimal_money(special_fare.special_price),
            base_price=route_price.base_price,
            flight_discount=schedule.flight_discount,
            user_discount=passenger_type.discount_rate,
            inventory_factor=Decimal("1.00"),
            price_source="SPECIAL",
            special_fare_id=special_fare.special_fare_id,
            is_special_fare=True,
            special_fare_tag="SPECIAL",
        )

    min_seats_left = min(
        inventory.f_seats_left if cabin_class == "F" else inventory.y_seats_left
        for inventory in inventories
    )
    airplane = db.get(Airplane, schedule.airplane_id)
    if airplane is None:
        raise HTTPException(status_code=500, detail="Airplane configuration missing.")
    total_capacity = airplane.f_class_capacity if cabin_class == "F" else airplane.y_class_capacity
    inventory_factor = _inventory_factor(min_seats_left, total_capacity)
    total = (
        route_price.base_price
        * schedule.flight_discount
        * passenger_type.discount_rate
        * inventory_factor
    )
    return PriceComputation(
        final_price=decimal_money(total),
        base_price=route_price.base_price,
        flight_discount=schedule.flight_discount,
        user_discount=passenger_type.discount_rate,
        inventory_factor=inventory_factor,
        price_source="STANDARD",
        special_fare_id=None,
        is_special_fare=False,
        special_fare_tag=None,
    )


def list_reference_cities(db: Session) -> list[City]:
    return db.scalars(select(City).order_by(City.city_name, City.city_code)).all()


def _get_airport_name_map(db: Session) -> dict[str, str]:
    airports = db.scalars(select(Airport)).all()
    return {airport.airport_code: airport.airport_name for airport in airports}


def _expand_city_to_airports(db: Session, city_code: str | None) -> set[str] | None:
    if city_code is None:
        return None
    airports = db.scalars(select(Airport).where(Airport.city_code == city_code)).all()
    return {airport.airport_code for airport in airports}


def expire_pending_orders(db: Session) -> None:
    now = utcnow_naive()
    expired_tickets = db.scalars(
        select(TicketSale)
        .where(
            TicketSale.status == "PENDING_PAYMENT",
            TicketSale.hold_expires_at.is_not(None),
            TicketSale.hold_expires_at <= now,
        )
        .order_by(TicketSale.created_at)
    ).all()
    if not expired_tickets:
        return

    for ticket in expired_tickets:
        schedule = db.get(
            FlightSchedule,
            {"flight_no": ticket.flight_no, "flight_date": ticket.flight_date},
        )
        if schedule is None:
            continue
        segment_range = get_segment_range(
            db,
            schedule.route_id,
            ticket.start_segment_id,
            ticket.end_segment_id,
        )
        inventories = _lock_inventories(
            db,
            ticket.flight_no,
            ticket.flight_date,
            [segment.segment_id for segment in segment_range],
        )
        for inventory in inventories:
            if ticket.cabin_class == "F":
                inventory.f_seats_left += 1
            else:
                inventory.y_seats_left += 1

        if ticket.special_fare_id is not None:
            special_fare = db.get(SpecialFarePlan, ticket.special_fare_id)
            if special_fare is not None and special_fare.quota_used > 0:
                special_fare.quota_used -= 1

        payment = db.scalar(select(PaymentRecord).where(PaymentRecord.payment_id == ticket.payment_id))
        if payment is not None:
            payment.payment_status = "EXPIRED"

        ticket.status = "EXPIRED"
        ticket.is_active_ticket = None
        linked_waitlist = db.scalar(
            select(WaitlistRecord).where(WaitlistRecord.linked_ticket_no == ticket.ticket_no),
        )
        if linked_waitlist is not None:
            linked_waitlist.status = "EXPIRED"
            linked_waitlist.offer_expires_at = ticket.hold_expires_at
        create_audit_log(
            db,
            None,
            "EXPIRE_TICKET",
            "TicketSale",
            ticket.ticket_no,
            f"{ticket.flight_no}/{ticket.flight_date}",
        )
        _dispatch_waitlist_offer(
            db,
            ticket.flight_no,
            ticket.flight_date,
            ticket.start_segment_id,
            ticket.end_segment_id,
            ticket.cabin_class,
        )
        publish_inventory_update(
            ticket.flight_no,
            ticket.flight_date,
            ticket.cabin_class,
            ticket.start_segment_id,
            ticket.end_segment_id,
            "EXPIRE_TICKET",
        )

    db.commit()


def _build_match_result(
    db: Session,
    passenger: Passenger,
    schedule: FlightSchedule,
    cabin_class: str,
    start_segment: RouteSegment,
    end_segment: RouteSegment,
    inventories: list[ScheduleInventory],
) -> dict:
    origin_airport = db.get(Airport, start_segment.dep_airport_code)
    destination_airport = db.get(Airport, end_segment.arr_airport_code)
    seats_left = min(
        inventory.f_seats_left if cabin_class == "F" else inventory.y_seats_left
        for inventory in inventories
    )
    price = _compute_price_for_match(
        db,
        schedule,
        passenger,
        cabin_class,
        start_segment.segment_id,
        end_segment.segment_id,
        inventories,
    )
    return {
        "flight_no": schedule.flight_no,
        "flight_date": schedule.flight_date,
        "origin_airport": start_segment.dep_airport_code,
        "destination_airport": end_segment.arr_airport_code,
        "origin_airport_name": origin_airport.airport_name if origin_airport else start_segment.dep_airport_code,
        "destination_airport_name": destination_airport.airport_name if destination_airport else end_segment.arr_airport_code,
        "origin_segment_id": start_segment.segment_id,
        "destination_segment_id": end_segment.segment_id,
        "cabin_class": cabin_class,
        "available_seats": seats_left,
        "final_price": float(price.final_price),
        "departure_time": start_segment.planned_dep_time,
        "arrival_time": end_segment.planned_arr_time,
        "price_source": price.price_source,
        "is_special_fare": price.is_special_fare,
        "special_fare_tag": price.special_fare_tag,
    }


def search_flights(
    db: Session,
    account: Account,
    flight_query: SearchFlightQuery,
) -> list[dict]:
    expire_pending_orders(db)
    passenger = get_passenger_for_account(db, account)
    flight_date = flight_query.flight_date
    cabin_class = flight_query.cabin_class
    origin_airport_codes = (
        {flight_query.origin_airport_code}
        if flight_query.origin_airport_code is not None
        else _expand_city_to_airports(db, flight_query.origin_city_code)
    )
    destination_airport_codes = (
        {flight_query.destination_airport_code}
        if flight_query.destination_airport_code is not None
        else _expand_city_to_airports(db, flight_query.destination_city_code)
    )

    schedules = db.scalars(
        select(FlightSchedule).where(
            FlightSchedule.flight_date == flight_date,
            FlightSchedule.schedule_status == "ACTIVE",
        ),
    ).all()
    results: list[dict] = []
    for schedule in schedules:
        segments = db.scalars(
            select(RouteSegment)
            .where(RouteSegment.route_id == schedule.route_id)
            .order_by(RouteSegment.segment_order),
        ).all()
        if not segments:
            continue
        for start_segment, end_segment in product(segments, segments):
            if origin_airport_codes is not None and start_segment.dep_airport_code not in origin_airport_codes:
                continue
            if (
                destination_airport_codes is not None
                and end_segment.arr_airport_code not in destination_airport_codes
            ):
                continue
            if start_segment.segment_order > end_segment.segment_order:
                continue
            segment_range = get_segment_range(
                db,
                schedule.route_id,
                start_segment.segment_id,
                end_segment.segment_id,
            )
            inventories = db.scalars(
                select(ScheduleInventory).where(
                    ScheduleInventory.flight_no == schedule.flight_no,
                    ScheduleInventory.flight_date == schedule.flight_date,
                    ScheduleInventory.segment_id.in_(
                        [segment.segment_id for segment in segment_range],
                    ),
                ),
            ).all()
            if len(inventories) != len(segment_range):
                continue
            results.append(
                _build_match_result(
                    db,
                    passenger,
                    schedule,
                    cabin_class,
                    start_segment,
                    end_segment,
                    inventories,
                ),
            )
    results.sort(key=lambda item: (item["departure_time"], item["flight_no"]))
    return results


def _collect_schedule_matches(
    db: Session,
    passenger: Passenger,
    schedule: FlightSchedule,
    cabin_class: str,
    origin_airport_codes: set[str] | None = None,
    destination_airport_codes: set[str] | None = None,
) -> list[dict]:
    segments = db.scalars(
        select(RouteSegment)
        .where(RouteSegment.route_id == schedule.route_id)
        .order_by(RouteSegment.segment_order),
    ).all()
    if not segments:
        return []

    results: list[dict] = []
    for start_segment, end_segment in product(segments, segments):
        if origin_airport_codes is not None and start_segment.dep_airport_code not in origin_airport_codes:
            continue
        if destination_airport_codes is not None and end_segment.arr_airport_code not in destination_airport_codes:
            continue
        if start_segment.segment_order > end_segment.segment_order:
            continue

        segment_range = get_segment_range(
            db,
            schedule.route_id,
            start_segment.segment_id,
            end_segment.segment_id,
        )
        inventories = db.scalars(
            select(ScheduleInventory).where(
                ScheduleInventory.flight_no == schedule.flight_no,
                ScheduleInventory.flight_date == schedule.flight_date,
                ScheduleInventory.segment_id.in_(
                    [segment.segment_id for segment in segment_range],
                ),
            ),
        ).all()
        if len(inventories) != len(segment_range):
            continue

        results.append(
            _build_match_result(
                db,
                passenger,
                schedule,
                cabin_class,
                start_segment,
                end_segment,
                inventories,
            ),
        )
    return results


def _has_departed(
    db: Session,
    flight_date: date,
    start_segment_id: int,
) -> bool:
    segment = db.get(RouteSegment, start_segment_id)
    if segment is None:
        return False
    departure_dt = datetime.combine(flight_date, segment.planned_dep_time)
    return departure_dt <= utcnow_naive()


def _create_pending_ticket(
    db: Session,
    passenger: Passenger,
    schedule: FlightSchedule,
    start_segment_id: int,
    end_segment_id: int,
    cabin_class: str,
) -> TicketSale:
    existing_active_ticket = db.scalar(
        select(TicketSale).where(
            TicketSale.passenger_id == passenger.passenger_id,
            TicketSale.flight_no == schedule.flight_no,
            TicketSale.flight_date == schedule.flight_date,
            TicketSale.is_active_ticket == 1,
        ),
    )
    if existing_active_ticket is not None:
        raise HTTPException(
            status_code=409,
            detail="Same passenger can only hold one active ticket for the same flight.",
        )

    segment_range = get_segment_range(db, schedule.route_id, start_segment_id, end_segment_id)
    segment_ids = [segment.segment_id for segment in segment_range]
    inventories = _lock_inventories(db, schedule.flight_no, schedule.flight_date, segment_ids)
    available_seats = min(
        inventory.f_seats_left if cabin_class == "F" else inventory.y_seats_left
        for inventory in inventories
    )
    if available_seats <= 0:
        raise HTTPException(status_code=409, detail="No seats available.")

    price = _compute_price_for_match(
        db,
        schedule,
        passenger,
        cabin_class,
        start_segment_id,
        end_segment_id,
        inventories,
    )
    if price.special_fare_id is not None:
        special_fare = _load_special_fare(
            db,
            schedule.flight_no,
            schedule.flight_date,
            cabin_class,
            start_segment_id,
            end_segment_id,
            for_update=True,
        )
        if special_fare is None or special_fare.quota_used >= special_fare.quota_total:
            raise HTTPException(status_code=409, detail="Special fare quota is no longer available.")
        special_fare.quota_used += 1

    for inventory in inventories:
        if cabin_class == "F":
            inventory.f_seats_left -= 1
        else:
            inventory.y_seats_left -= 1

    now = utcnow_naive()
    hold_expires_at = now + timedelta(minutes=settings.payment_hold_minutes)
    payment_id = f"P{uuid4().hex[:20].upper()}"
    ticket = TicketSale(
        ticket_no=f"T{uuid4().hex[:20].upper()}",
        payment_id=payment_id,
        flight_no=schedule.flight_no,
        flight_date=schedule.flight_date,
        passenger_id=passenger.passenger_id,
        start_segment_id=start_segment_id,
        end_segment_id=end_segment_id,
        cabin_class=cabin_class,
        status="PENDING_PAYMENT",
        is_active_ticket=1,
        actual_price=price.final_price,
        base_price_snapshot=price.base_price,
        flight_discount_snapshot=price.flight_discount,
        user_discount_snapshot=price.user_discount,
        inventory_factor_snapshot=price.inventory_factor,
        price_source=price.price_source,
        special_fare_id=price.special_fare_id,
        created_at=now,
        hold_expires_at=hold_expires_at,
    )
    db.add(ticket)
    db.flush()
    db.add(
        PaymentRecord(
            payment_id=payment_id,
            ticket_no=ticket.ticket_no,
            payment_method="ALIPAY",
            payment_status="PENDING",
            pay_amount=price.final_price,
            created_at=now,
        ),
    )
    publish_inventory_update(
        schedule.flight_no,
        schedule.flight_date,
        cabin_class,
        start_segment_id,
        end_segment_id,
        "CREATE_PENDING_TICKET",
    )
    return ticket


def _dispatch_waitlist_offer(
    db: Session,
    flight_no: str,
    flight_date: date,
    start_segment_id: int,
    end_segment_id: int,
    cabin_class: str,
) -> None:
    schedule = db.get(FlightSchedule, {"flight_no": flight_no, "flight_date": flight_date})
    if schedule is None or schedule.schedule_status != "ACTIVE":
        return

    while True:
        waitlist = db.scalar(
            select(WaitlistRecord)
            .where(
                WaitlistRecord.flight_no == flight_no,
                WaitlistRecord.flight_date == flight_date,
                WaitlistRecord.start_segment_id == start_segment_id,
                WaitlistRecord.end_segment_id == end_segment_id,
                WaitlistRecord.cabin_class == cabin_class,
                WaitlistRecord.status == "WAITING",
            )
            .order_by(WaitlistRecord.request_time)
            .with_for_update()
        )
        if waitlist is None:
            return

        passenger = db.get(Passenger, waitlist.passenger_id)
        if passenger is None:
            waitlist.status = "CANCELLED"
            waitlist.linked_ticket_no = None
            waitlist.offer_expires_at = None
            continue

        existing_active_ticket = db.scalar(
            select(TicketSale).where(
                TicketSale.passenger_id == passenger.passenger_id,
                TicketSale.flight_no == flight_no,
                TicketSale.flight_date == flight_date,
                TicketSale.is_active_ticket == 1,
            ),
        )
        if existing_active_ticket is not None:
            waitlist.status = "CANCELLED"
            waitlist.linked_ticket_no = None
            waitlist.offer_expires_at = None
            continue

        try:
            ticket = _create_pending_ticket(
                db,
                passenger,
                schedule,
                start_segment_id,
                end_segment_id,
                cabin_class,
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                return
            raise

        waitlist.status = "RELEASED"
        waitlist.released_at = ticket.created_at
        waitlist.linked_ticket_no = ticket.ticket_no
        waitlist.offer_expires_at = ticket.hold_expires_at
        return


def purchase_ticket(
    db: Session,
    account: Account,
    flight_no: str,
    flight_date: date,
    start_segment_id: int,
    end_segment_id: int,
    cabin_class: str,
) -> TicketSale:
    expire_pending_orders(db)
    passenger = get_passenger_for_account(db, account)
    schedule = db.get(FlightSchedule, {"flight_no": flight_no, "flight_date": flight_date})
    if schedule is None or schedule.schedule_status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Flight schedule not available.")
    ticket = _create_pending_ticket(
        db,
        passenger,
        schedule,
        start_segment_id,
        end_segment_id,
        cabin_class,
    )
    create_audit_log(
        db,
        account,
        "CREATE_PENDING_TICKET",
        "TicketSale",
        ticket.ticket_no,
        f"{flight_no}/{flight_date} {cabin_class} {start_segment_id}->{end_segment_id} {ticket.price_source}",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Same passenger can only hold one active ticket for the same flight.",
        ) from exc
    db.refresh(ticket)
    return ticket


def confirm_payment(
    db: Session,
    account: Account,
    payment_id: str,
    payment_method: str,
    payer_account: str,
) -> PaymentRecord:
    expire_pending_orders(db)
    payment = db.scalar(
        select(PaymentRecord).where(PaymentRecord.payment_id == payment_id).with_for_update(),
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment record not found.")

    ticket = db.scalar(
        select(TicketSale).where(TicketSale.ticket_no == payment.ticket_no).with_for_update(),
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket order not found.")

    passenger = get_passenger_for_account(db, account)
    if ticket.passenger_id != passenger.passenger_id:
        raise HTTPException(status_code=403, detail="Payment record does not belong to current user.")
    if ticket.status == "EXPIRED" or payment.payment_status == "EXPIRED":
        raise HTTPException(status_code=409, detail="Payment has expired.")
    if payment.payment_status == "PAID":
        db.refresh(payment)
        return payment
    if ticket.status != "PENDING_PAYMENT":
        raise HTTPException(status_code=400, detail="Ticket is not awaiting payment.")

    now = utcnow_naive()
    payment.payment_method = payment_method
    payment.payment_status = "PAID"
    payment.mock_trade_no = f"M{uuid4().hex[:20].upper()}"
    payment.payer_account_masked = mask_payment_account(payer_account)
    payment.payer_account_hash = hash_sensitive_value(payer_account)
    payment.paid_at = now

    ticket.status = "PAID"
    ticket.paid_at = now
    ticket.hold_expires_at = None
    waitlist = db.scalar(select(WaitlistRecord).where(WaitlistRecord.linked_ticket_no == ticket.ticket_no))
    if waitlist is not None:
        waitlist.status = "FULFILLED"
        waitlist.offer_expires_at = None

    passenger.mileage_points = decimal_money(passenger.mileage_points + ticket.actual_price)
    _sync_passenger_type(db, passenger)
    create_audit_log(
        db,
        account,
        "CONFIRM_PAYMENT",
        "PaymentRecord",
        payment_id,
        f"{ticket.flight_no}/{ticket.flight_date}",
    )
    publish_inventory_update(
        ticket.flight_no,
        ticket.flight_date,
        ticket.cabin_class,
        ticket.start_segment_id,
        ticket.end_segment_id,
        "CONFIRM_PAYMENT",
    )
    db.commit()
    db.refresh(payment)
    return payment


def refund_ticket(
    db: Session,
    ticket: TicketSale,
    actor: Account,
    allow_departed: bool = False,
) -> TicketSale:
    expire_pending_orders(db)
    if ticket.status != "PAID":
        raise HTTPException(status_code=400, detail="Only paid tickets can be refunded.")
    if not allow_departed and _has_departed(db, ticket.flight_date, ticket.start_segment_id):
        raise HTTPException(status_code=400, detail="Flight has already departed.")

    schedule = db.get(
        FlightSchedule,
        {"flight_no": ticket.flight_no, "flight_date": ticket.flight_date},
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Flight schedule missing.")
    segment_range = get_segment_range(
        db,
        schedule.route_id,
        ticket.start_segment_id,
        ticket.end_segment_id,
    )
    inventories = _lock_inventories(
        db,
        ticket.flight_no,
        ticket.flight_date,
        [segment.segment_id for segment in segment_range],
    )
    for inventory in inventories:
        if ticket.cabin_class == "F":
            inventory.f_seats_left += 1
        else:
            inventory.y_seats_left += 1
    passenger = db.get(Passenger, ticket.passenger_id)
    if passenger is None:
        raise HTTPException(status_code=404, detail="Passenger profile missing.")
    _reverse_passenger_points(passenger, ticket.actual_price)
    _sync_passenger_type(db, passenger)
    ticket.status = "REFUNDED"
    ticket.is_active_ticket = None
    ticket.refunded_at = utcnow_naive()
    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.payment_id == ticket.payment_id))
    if payment is not None:
        payment.payment_status = "REFUNDED"
        payment.refunded_at = ticket.refunded_at
    linked_waitlist = db.scalar(select(WaitlistRecord).where(WaitlistRecord.linked_ticket_no == ticket.ticket_no))
    if linked_waitlist is not None and linked_waitlist.status == "FULFILLED":
        linked_waitlist.status = "CANCELLED"
        linked_waitlist.offer_expires_at = None

    _dispatch_waitlist_offer(
        db,
        ticket.flight_no,
        ticket.flight_date,
        ticket.start_segment_id,
        ticket.end_segment_id,
        ticket.cabin_class,
    )
    create_audit_log(
        db,
        actor,
        "REFUND_TICKET",
        "TicketSale",
        ticket.ticket_no,
        f"{ticket.flight_no}/{ticket.flight_date}",
    )
    publish_inventory_update(
        ticket.flight_no,
        ticket.flight_date,
        ticket.cabin_class,
        ticket.start_segment_id,
        ticket.end_segment_id,
        "REFUND_TICKET",
    )
    return ticket


def cancel_pending_ticket(
    db: Session,
    ticket: TicketSale,
    actor: Account,
) -> TicketSale:
    expire_pending_orders(db)
    if ticket.status != "PENDING_PAYMENT":
        raise HTTPException(status_code=400, detail="Only tickets awaiting payment can be cancelled.")

    schedule = db.get(
        FlightSchedule,
        {"flight_no": ticket.flight_no, "flight_date": ticket.flight_date},
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Flight schedule missing.")

    segment_range = get_segment_range(
        db,
        schedule.route_id,
        ticket.start_segment_id,
        ticket.end_segment_id,
    )
    inventories = _lock_inventories(
        db,
        ticket.flight_no,
        ticket.flight_date,
        [segment.segment_id for segment in segment_range],
    )
    for inventory in inventories:
        if ticket.cabin_class == "F":
            inventory.f_seats_left += 1
        else:
            inventory.y_seats_left += 1

    if ticket.special_fare_id is not None:
        special_fare = db.get(SpecialFarePlan, ticket.special_fare_id)
        if special_fare is not None and special_fare.quota_used > 0:
            special_fare.quota_used -= 1

    payment = db.scalar(select(PaymentRecord).where(PaymentRecord.payment_id == ticket.payment_id))
    if payment is not None:
        payment.payment_status = "EXPIRED"

    linked_waitlist = db.scalar(select(WaitlistRecord).where(WaitlistRecord.linked_ticket_no == ticket.ticket_no))
    if linked_waitlist is not None:
        linked_waitlist.status = "EXPIRED"
        linked_waitlist.offer_expires_at = utcnow_naive()
        linked_waitlist.linked_ticket_no = None

    ticket.status = "CANCELLED"
    ticket.is_active_ticket = None
    ticket.hold_expires_at = None

    create_audit_log(
        db,
        actor,
        "CANCEL_PENDING_TICKET",
        "TicketSale",
        ticket.ticket_no,
        f"{ticket.flight_no}/{ticket.flight_date}",
    )
    _dispatch_waitlist_offer(
        db,
        ticket.flight_no,
        ticket.flight_date,
        ticket.start_segment_id,
        ticket.end_segment_id,
        ticket.cabin_class,
    )
    publish_inventory_update(
        ticket.flight_no,
        ticket.flight_date,
        ticket.cabin_class,
        ticket.start_segment_id,
        ticket.end_segment_id,
        "CANCEL_PENDING_TICKET",
    )
    return ticket


def create_waitlist(
    db: Session,
    account: Account,
    flight_no: str,
    flight_date: date,
    start_segment_id: int,
    end_segment_id: int,
    cabin_class: str,
) -> WaitlistRecord:
    expire_pending_orders(db)
    passenger = get_passenger_for_account(db, account)
    start_segment = db.get(RouteSegment, start_segment_id)
    end_segment = db.get(RouteSegment, end_segment_id)
    if start_segment is None or end_segment is None:
        raise HTTPException(status_code=404, detail="Segment not found.")
    search_matches = search_flights(
        db,
        account,
        SearchFlightQuery(
            origin_airport_code=start_segment.dep_airport_code,
            destination_airport_code=end_segment.arr_airport_code,
            flight_date=flight_date,
            cabin_class=cabin_class,
        ),
    )
    matching_row = next(
        (
            row
            for row in search_matches
            if row["flight_no"] == flight_no
            and row["origin_segment_id"] == start_segment_id
            and row["destination_segment_id"] == end_segment_id
        ),
        None,
    )
    if matching_row is None:
        raise HTTPException(status_code=404, detail="Flight segment not found for waitlist.")
    if matching_row["available_seats"] > 0:
        raise HTTPException(status_code=400, detail="Seats are available. Purchase directly.")
    existing = db.scalar(
        select(WaitlistRecord).where(
            WaitlistRecord.flight_no == flight_no,
            WaitlistRecord.flight_date == flight_date,
            WaitlistRecord.start_segment_id == start_segment_id,
            WaitlistRecord.end_segment_id == end_segment_id,
            WaitlistRecord.cabin_class == cabin_class,
            WaitlistRecord.passenger_id == passenger.passenger_id,
            WaitlistRecord.status.in_(["WAITING", "RELEASED"]),
        ),
    )
    if existing is not None:
        raise HTTPException(status_code=400, detail="Waitlist already exists for this flight.")
    waitlist = WaitlistRecord(
        flight_no=flight_no,
        flight_date=flight_date,
        start_segment_id=start_segment_id,
        end_segment_id=end_segment_id,
        cabin_class=cabin_class,
        passenger_id=passenger.passenger_id,
        status="WAITING",
    )
    db.add(waitlist)
    create_audit_log(
        db,
        account,
        "CREATE_WAITLIST",
        "WaitlistRecord",
        f"{flight_no}-{flight_date}-{passenger.id_card_masked}",
        f"{cabin_class} {start_segment_id}->{end_segment_id}",
    )
    db.commit()
    db.refresh(waitlist)
    return waitlist


def search_flights_in_range(
    db: Session,
    account: Account,
    query: SearchFlightRangeQuery,
) -> list[dict]:
    expire_pending_orders(db)
    passenger = get_passenger_for_account(db, account)
    origin_airport_codes = (
        {query.origin_airport_code}
        if query.origin_airport_code is not None
        else _expand_city_to_airports(db, query.origin_city_code)
    )
    destination_airport_codes = (
        {query.destination_airport_code}
        if query.destination_airport_code is not None
        else _expand_city_to_airports(db, query.destination_city_code)
    )
    schedules = db.scalars(
        select(FlightSchedule).where(
            FlightSchedule.flight_date >= query.start_date,
            FlightSchedule.flight_date <= query.end_date,
            FlightSchedule.schedule_status == "ACTIVE",
        ),
    ).all()

    results: list[dict] = []
    for schedule in schedules:
        results.extend(
            _collect_schedule_matches(
                db,
                passenger,
                schedule,
                query.cabin_class,
                origin_airport_codes=origin_airport_codes,
                destination_airport_codes=destination_airport_codes,
            ),
        )

    results.sort(
        key=lambda item: (
            item["flight_date"],
            item["departure_time"],
            item["flight_no"],
        ),
    )
    return results


def generate_schedules(
    db: Session,
    actor: Account,
    template_id: int,
    start_date: date,
    end_date: date,
) -> GenerateScheduleSummary:
    template = db.get(FlightTemplate, template_id)
    if template is None or template.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Active flight template not found.")
    weekdays = sorted(
        item.weekday
        for item in db.scalars(
            select(FlightTemplateWeekday).where(
                FlightTemplateWeekday.template_id == template_id,
            ),
        ).all()
    )
    if not weekdays:
        raise HTTPException(status_code=400, detail="Template weekdays not configured.")
    route_segments = db.scalars(
        select(RouteSegment)
        .where(RouteSegment.route_id == template.route_id)
        .order_by(RouteSegment.segment_order),
    ).all()
    airplane = db.get(Airplane, template.default_airplane_id)
    if airplane is None or not route_segments:
        raise HTTPException(status_code=400, detail="Template dependencies are incomplete.")

    current = start_date
    matched_dates: list[date] = []
    generated_dates: list[date] = []
    skipped_existing_dates: list[date] = []
    while current <= end_date:
        if current.isoweekday() in weekdays:
            matched_dates.append(current)
            existing = db.get(
                FlightSchedule,
                {"flight_no": template.flight_no, "flight_date": current},
            )
            if existing is None:
                schedule = FlightSchedule(
                    flight_no=template.flight_no,
                    flight_date=current,
                    route_id=template.route_id,
                    airplane_id=template.default_airplane_id,
                    flight_discount=template.default_flight_discount,
                    schedule_status="ACTIVE",
                    template_id=template.template_id,
                )
                db.add(schedule)
                db.flush()
                for segment in route_segments:
                    db.add(
                        ScheduleInventory(
                            flight_no=template.flight_no,
                            flight_date=current,
                            segment_id=segment.segment_id,
                            f_seats_left=airplane.f_class_capacity,
                            y_seats_left=airplane.y_class_capacity,
                        ),
                    )
                generated_dates.append(current)
            else:
                skipped_existing_dates.append(current)
        current = current.fromordinal(current.toordinal() + 1)

    create_audit_log(
        db,
        actor,
        "GENERATE_SCHEDULES",
        "FlightTemplate",
        str(template_id),
        f"{start_date} -> {end_date}",
    )
    db.commit()
    return GenerateScheduleSummary(
        template_id=template_id,
        template_weekdays=weekdays,
        matched_dates=matched_dates,
        generated_dates=generated_dates,
        skipped_existing_dates=skipped_existing_dates,
    )


def cancel_schedule(
    db: Session,
    actor: Account,
    flight_no: str,
    flight_date: date,
) -> int:
    expire_pending_orders(db)
    schedule = db.get(FlightSchedule, {"flight_no": flight_no, "flight_date": flight_date})
    if schedule is None:
        raise HTTPException(status_code=404, detail="Flight schedule not found.")
    schedule.schedule_status = "CANCELLED"
    paid_tickets = db.scalars(
        select(TicketSale).where(
            TicketSale.flight_no == flight_no,
            TicketSale.flight_date == flight_date,
            TicketSale.status == "PAID",
        ),
    ).all()
    for ticket in paid_tickets:
        refund_ticket(db, ticket, actor, allow_departed=True)
    waiting_records = db.scalars(
        select(WaitlistRecord).where(
            WaitlistRecord.flight_no == flight_no,
            WaitlistRecord.flight_date == flight_date,
            WaitlistRecord.status.in_(["WAITING", "RELEASED"]),
        ),
    ).all()
    for record in waiting_records:
        record.status = "CANCELLED"
        record.offer_expires_at = None
    create_audit_log(
        db,
        actor,
        "CANCEL_SCHEDULE",
        "FlightSchedule",
        f"{flight_no}-{flight_date}",
        f"refunded={len(paid_tickets)}",
    )
    db.commit()
    return len(paid_tickets)
