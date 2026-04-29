import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.inventory_stream import build_sse_message, inventory_event_broker
from app.models import Account
from app.schemas import (
    ReferenceCityResponse,
    SearchFlightQuery,
    SearchFlightRangeQuery,
    SearchFlightResponse,
)
from app.security import decode_access_token
from app.services import list_reference_cities, search_flights, search_flights_in_range

router = APIRouter(tags=["flights"])


def get_account_from_access_token(
    access_token: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> Account:
    try:
        payload = decode_access_token(access_token)
    except Exception as exc:  # pragma: no cover - defensive branch
        raise HTTPException(status_code=401, detail="Invalid access token.") from exc
    account = db.get(Account, int(payload["sub"]))
    if account is None or account.status != "ACTIVE":
        raise HTTPException(status_code=401, detail="Account not available.")
    return account


def build_search_query(
    flight_date: Annotated[date, Query()],
    cabin_class: Annotated[str, Query(pattern="^(F|Y)$")],
    origin_airport_code: Annotated[str | None, Query()] = None,
    destination_airport_code: Annotated[str | None, Query()] = None,
    origin_city_code: Annotated[str | None, Query()] = None,
    destination_city_code: Annotated[str | None, Query()] = None,
) -> SearchFlightQuery:
    try:
        return SearchFlightQuery(
            origin_airport_code=origin_airport_code,
            destination_airport_code=destination_airport_code,
            origin_city_code=origin_city_code,
            destination_city_code=destination_city_code,
            flight_date=flight_date,
            cabin_class=cabin_class,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


def build_range_query(
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    cabin_class: Annotated[str, Query(pattern="^(F|Y)$")],
    origin_airport_code: Annotated[str | None, Query()] = None,
    destination_airport_code: Annotated[str | None, Query()] = None,
    origin_city_code: Annotated[str | None, Query()] = None,
    destination_city_code: Annotated[str | None, Query()] = None,
) -> SearchFlightRangeQuery:
    try:
        return SearchFlightRangeQuery(
            origin_airport_code=origin_airport_code,
            destination_airport_code=destination_airport_code,
            origin_city_code=origin_city_code,
            destination_city_code=destination_city_code,
            start_date=start_date,
            end_date=end_date,
            cabin_class=cabin_class,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/reference/cities", response_model=list[ReferenceCityResponse])
def reference_cities(
    db: Annotated[Session, Depends(get_db)],
) -> list[ReferenceCityResponse]:
    return list_reference_cities(db)


@router.get("/flights/search", response_model=list[SearchFlightResponse])
def flights_search(
    search_query: Annotated[SearchFlightQuery, Depends(build_search_query)],
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> list[SearchFlightResponse]:
    return search_flights(
        db,
        current_account,
        search_query,
    )


@router.get("/flights/search/range", response_model=list[SearchFlightResponse])
def flights_search_range(
    range_query: Annotated[SearchFlightRangeQuery, Depends(build_range_query)],
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> list[SearchFlightResponse]:
    return search_flights_in_range(db, current_account, range_query)


@router.get("/flights/stream/inventory")
async def inventory_stream(
    _: Annotated[Account, Depends(get_account_from_access_token)],
) -> StreamingResponse:
    queue = inventory_event_broker.subscribe()

    async def event_generator():
        try:
            yield build_sse_message("connected", {"status": "ok"})
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield build_sse_message("inventory_update", payload)
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            inventory_event_broker.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
