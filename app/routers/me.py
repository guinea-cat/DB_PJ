from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.models import Account, Airport, City, RouteSegment, TicketSale, WaitlistRecord
from app.schemas import TicketResponse, WaitlistResponse

router = APIRouter(prefix="/me", tags=["me"])


def _resolve_segment_city_names(
    db: Session,
    start_segment_id: int,
    end_segment_id: int,
) -> tuple[str, str]:
    start_segment = db.get(RouteSegment, start_segment_id)
    end_segment = db.get(RouteSegment, end_segment_id)

    origin_label = "-"
    destination_label = "-"

    if start_segment is not None:
        origin_airport = db.get(Airport, start_segment.dep_airport_code)
        if origin_airport is not None:
            origin_city = db.get(City, origin_airport.city_code)
            origin_label = (
                origin_city.city_name
                if origin_city is not None
                else origin_airport.airport_name or origin_airport.airport_code
            )
        else:
            origin_label = start_segment.dep_airport_code

    if end_segment is not None:
        destination_airport = db.get(Airport, end_segment.arr_airport_code)
        if destination_airport is not None:
            destination_city = db.get(City, destination_airport.city_code)
            destination_label = (
                destination_city.city_name
                if destination_city is not None
                else destination_airport.airport_name or destination_airport.airport_code
            )
        else:
            destination_label = end_segment.arr_airport_code

    return origin_label, destination_label


@router.get("/orders", response_model=list[TicketResponse])
def my_orders(
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> list[TicketResponse]:
    orders = db.scalars(
        select(TicketSale)
        .where(TicketSale.passenger_id == current_account.passenger_id)
        .order_by(TicketSale.created_at.desc()),
    ).all()

    responses: list[TicketResponse] = []
    for order in orders:
        origin_city_name, destination_city_name = _resolve_segment_city_names(
            db,
            order.start_segment_id,
            order.end_segment_id,
        )
        responses.append(
            TicketResponse(
                ticket_no=order.ticket_no,
                payment_id=order.payment_id,
                flight_no=order.flight_no,
                flight_date=order.flight_date,
                passenger_id=order.passenger_id,
                start_segment_id=order.start_segment_id,
                end_segment_id=order.end_segment_id,
                cabin_class=order.cabin_class,
                status=order.status,
                actual_price=float(order.actual_price),
                price_source=order.price_source,
                is_special_fare=order.is_special_fare,
                origin_city_name=origin_city_name,
                destination_city_name=destination_city_name,
                created_at=order.created_at,
                hold_expires_at=order.hold_expires_at,
                paid_at=order.paid_at,
                refunded_at=order.refunded_at,
            )
        )
    return responses


@router.get("/waitlists", response_model=list[WaitlistResponse])
def my_waitlists(
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> list[WaitlistResponse]:
    waitlists = db.scalars(
        select(WaitlistRecord)
        .where(WaitlistRecord.passenger_id == current_account.passenger_id)
        .order_by(WaitlistRecord.request_time.desc()),
    ).all()

    responses: list[WaitlistResponse] = []
    for waitlist in waitlists:
        origin_city_name, destination_city_name = _resolve_segment_city_names(
            db,
            waitlist.start_segment_id,
            waitlist.end_segment_id,
        )
        responses.append(
            WaitlistResponse(
                waitlist_id=waitlist.waitlist_id,
                flight_no=waitlist.flight_no,
                flight_date=waitlist.flight_date,
                start_segment_id=waitlist.start_segment_id,
                end_segment_id=waitlist.end_segment_id,
                cabin_class=waitlist.cabin_class,
                passenger_id=waitlist.passenger_id,
                status=waitlist.status,
                origin_city_name=origin_city_name,
                destination_city_name=destination_city_name,
                request_time=waitlist.request_time,
                released_at=waitlist.released_at,
                linked_ticket_no=waitlist.linked_ticket_no,
                offer_expires_at=waitlist.offer_expires_at,
            )
        )
    return responses
