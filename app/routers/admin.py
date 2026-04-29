from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
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
    Route,
    RoutePricing,
    RouteSegment,
    SpecialFarePlan,
    TicketSale,
)
from app.schemas import (
    AdminTicketResponse,
    AirplanePayload,
    AirplaneResponse,
    AirportPayload,
    AirportResponse,
    AuditResponse,
    CancelScheduleResponse,
    CityPayload,
    CityResponse,
    FlightTemplatePayload,
    FlightTemplateResponse,
    GenerateScheduleRequest,
    GenerateScheduleResponse,
    RoutePayload,
    RouteResponse,
    SpecialFarePlanPayload,
    SpecialFarePlanResponse,
)
from app.services import cancel_schedule, create_audit_log, generate_schedules, mask_id_card

router = APIRouter(prefix="/admin", tags=["admin"])


def _city_reference_state(db: Session, city_code: str) -> tuple[bool, str | None]:
    referenced_airport = db.scalar(
        select(Airport.airport_code)
        .where(Airport.city_code == city_code)
        .limit(1),
    )
    if referenced_airport is not None:
        return True, "City is still referenced by airports."
    return False, None


def _airport_reference_state(db: Session, airport_code: str) -> tuple[bool, str | None]:
    referenced_segment = db.scalar(
        select(RouteSegment.segment_id)
        .where(
            or_(
                RouteSegment.dep_airport_code == airport_code,
                RouteSegment.arr_airport_code == airport_code,
            ),
        )
        .limit(1),
    )
    if referenced_segment is not None:
        return True, "Airport is still referenced by route segments."
    return False, None


def _airplane_reference_state(db: Session, airplane_id: str) -> tuple[bool, str | None]:
    referenced_template = db.scalar(
        select(FlightTemplate.template_id)
        .where(FlightTemplate.default_airplane_id == airplane_id)
        .limit(1),
    )
    if referenced_template is not None:
        return True, "Airplane is still referenced by flight templates."

    referenced_schedule = db.scalar(
        select(FlightSchedule.flight_no)
        .where(FlightSchedule.airplane_id == airplane_id)
        .limit(1),
    )
    if referenced_schedule is not None:
        return True, "Airplane is still referenced by flight schedules."
    return False, None


def _route_reference_state(db: Session, route_id: str) -> tuple[bool, str | None]:
    referenced_template = db.scalar(
        select(FlightTemplate.template_id)
        .where(FlightTemplate.route_id == route_id)
        .limit(1),
    )
    if referenced_template is not None:
        return True, "Route is still referenced by flight templates."

    referenced_schedule = db.scalar(
        select(FlightSchedule.flight_no)
        .where(FlightSchedule.route_id == route_id)
        .limit(1),
    )
    if referenced_schedule is not None:
        return True, "Route is still referenced by flight schedules."
    return False, None


def _build_city_response(db: Session, city: City) -> CityResponse:
    is_referenced, blocked_reason = _city_reference_state(db, city.city_code)
    return CityResponse(
        city_code=city.city_code,
        city_name=city.city_name,
        is_referenced=is_referenced,
        can_edit=not is_referenced,
        can_delete=not is_referenced,
        blocked_reason=blocked_reason,
    )


def _build_airport_response(db: Session, airport: Airport) -> AirportResponse:
    is_referenced, blocked_reason = _airport_reference_state(db, airport.airport_code)
    return AirportResponse(
        airport_code=airport.airport_code,
        airport_name=airport.airport_name,
        city_code=airport.city_code,
        is_referenced=is_referenced,
        can_edit=not is_referenced,
        can_delete=not is_referenced,
        blocked_reason=blocked_reason,
    )


def _build_airplane_response(db: Session, airplane: Airplane) -> AirplaneResponse:
    is_referenced, blocked_reason = _airplane_reference_state(db, airplane.airplane_id)
    return AirplaneResponse(
        airplane_id=airplane.airplane_id,
        aircraft_type=airplane.aircraft_type,
        f_class_capacity=airplane.f_class_capacity,
        y_class_capacity=airplane.y_class_capacity,
        is_referenced=is_referenced,
        can_edit=not is_referenced,
        can_delete=not is_referenced,
        blocked_reason=blocked_reason,
    )


def _build_route_response(db: Session, route: Route) -> RouteResponse:
    segments = db.scalars(
        select(RouteSegment)
        .where(RouteSegment.route_id == route.route_id)
        .order_by(RouteSegment.segment_order),
    ).all()
    pricing = db.scalars(
        select(RoutePricing)
        .where(RoutePricing.route_id == route.route_id)
        .order_by(RoutePricing.cabin_class),
    ).all()
    is_referenced, blocked_reason = _route_reference_state(db, route.route_id)
    return RouteResponse(
        route_id=route.route_id,
        route_name=route.route_name,
        segments=[
            {
                "segment_id": segment.segment_id,
                "segment_order": segment.segment_order,
                "dep_airport_code": segment.dep_airport_code,
                "arr_airport_code": segment.arr_airport_code,
                "planned_dep_time": segment.planned_dep_time,
                "planned_arr_time": segment.planned_arr_time,
            }
            for segment in segments
        ],
        pricing=[
            {
                "cabin_class": item.cabin_class,
                "base_price": float(item.base_price),
            }
            for item in pricing
        ],
        is_referenced=is_referenced,
        can_edit=not is_referenced,
        can_delete=not is_referenced,
        blocked_reason=blocked_reason,
    )


def _build_template_response(
    db: Session,
    template: FlightTemplate,
) -> FlightTemplateResponse:
    weekdays = db.scalars(
        select(FlightTemplateWeekday.weekday).where(
            FlightTemplateWeekday.template_id == template.template_id,
        ),
    ).all()
    return FlightTemplateResponse(
        template_id=template.template_id,
        flight_no=template.flight_no,
        route_id=template.route_id,
        default_airplane_id=template.default_airplane_id,
        default_flight_discount=float(template.default_flight_discount),
        status=template.status,
        weekdays=sorted(weekdays),
    )


def _build_special_fare_response(plan: SpecialFarePlan) -> SpecialFarePlanResponse:
    return SpecialFarePlanResponse(
        special_fare_id=plan.special_fare_id,
        flight_no=plan.flight_no,
        flight_date=plan.flight_date,
        cabin_class=plan.cabin_class,
        start_segment_id=plan.start_segment_id,
        end_segment_id=plan.end_segment_id,
        special_price=float(plan.special_price),
        quota_total=plan.quota_total,
        quota_used=plan.quota_used,
        sale_start=plan.sale_start,
        sale_end=plan.sale_end,
        status=plan.status,
    )


def _ensure_city_deleteable(db: Session, city_code: str) -> None:
    is_referenced, blocked_reason = _city_reference_state(db, city_code)
    if is_referenced:
        raise HTTPException(
            status_code=409,
            detail=blocked_reason or "City is still referenced.",
        )


def _ensure_airport_deleteable(db: Session, airport_code: str) -> None:
    is_referenced, blocked_reason = _airport_reference_state(db, airport_code)
    if is_referenced:
        raise HTTPException(
            status_code=409,
            detail=blocked_reason or "Airport is still referenced.",
        )


def _ensure_airplane_deleteable(db: Session, airplane_id: str) -> None:
    is_referenced, blocked_reason = _airplane_reference_state(db, airplane_id)
    if is_referenced:
        raise HTTPException(
            status_code=409,
            detail=blocked_reason or "Airplane is still referenced.",
        )


def _ensure_route_deleteable(db: Session, route_id: str) -> None:
    is_referenced, blocked_reason = _route_reference_state(db, route_id)
    if is_referenced:
        raise HTTPException(
            status_code=409,
            detail=blocked_reason or "Route is still referenced.",
        )


@router.get("/cities", response_model=list[CityResponse])
def list_cities(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[CityResponse]:
    cities = db.scalars(select(City).order_by(City.city_code)).all()
    return [_build_city_response(db, city) for city in cities]


@router.post("/cities", response_model=CityResponse, status_code=status.HTTP_201_CREATED)
def create_city(
    payload: CityPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> CityResponse:
    city = City(**payload.model_dump())
    db.add(city)
    create_audit_log(db, admin, "CREATE_CITY", "City", city.city_code, city.city_name)
    db.commit()
    db.refresh(city)
    return _build_city_response(db, city)


@router.put("/cities/{city_code}", response_model=CityResponse)
def update_city(
    city_code: str,
    payload: CityPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> CityResponse:
    city = db.get(City, city_code)
    if city is None:
        raise HTTPException(status_code=404, detail="City not found.")
    _ensure_city_deleteable(db, city_code)
    city.city_name = payload.city_name
    create_audit_log(db, admin, "UPDATE_CITY", "City", city_code, payload.city_name)
    db.commit()
    db.refresh(city)
    return _build_city_response(db, city)


@router.delete("/cities/{city_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_city(
    city_code: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    city = db.get(City, city_code)
    if city is None:
        raise HTTPException(status_code=404, detail="City not found.")
    _ensure_city_deleteable(db, city_code)
    db.delete(city)
    create_audit_log(db, admin, "DELETE_CITY", "City", city_code, "")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="City is still referenced.") from exc


@router.get("/airports", response_model=list[AirportResponse])
def list_airports(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[AirportResponse]:
    airports = db.scalars(select(Airport).order_by(Airport.airport_code)).all()
    return [_build_airport_response(db, airport) for airport in airports]


@router.post("/airports", response_model=AirportResponse, status_code=status.HTTP_201_CREATED)
def create_airport(
    payload: AirportPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> AirportResponse:
    airport = Airport(**payload.model_dump())
    db.add(airport)
    create_audit_log(
        db,
        admin,
        "CREATE_AIRPORT",
        "Airport",
        airport.airport_code,
        airport.airport_name,
    )
    db.commit()
    db.refresh(airport)
    return _build_airport_response(db, airport)


@router.put("/airports/{airport_code}", response_model=AirportResponse)
def update_airport(
    airport_code: str,
    payload: AirportPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> AirportResponse:
    airport = db.get(Airport, airport_code)
    if airport is None:
        raise HTTPException(status_code=404, detail="Airport not found.")
    _ensure_airport_deleteable(db, airport_code)
    airport.airport_name = payload.airport_name
    airport.city_code = payload.city_code
    create_audit_log(
        db,
        admin,
        "UPDATE_AIRPORT",
        "Airport",
        airport_code,
        payload.airport_name,
    )
    db.commit()
    db.refresh(airport)
    return _build_airport_response(db, airport)


@router.delete("/airports/{airport_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_airport(
    airport_code: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    airport = db.get(Airport, airport_code)
    if airport is None:
        raise HTTPException(status_code=404, detail="Airport not found.")
    _ensure_airport_deleteable(db, airport_code)
    db.delete(airport)
    create_audit_log(db, admin, "DELETE_AIRPORT", "Airport", airport_code, "")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Airport is still referenced.") from exc


@router.get("/airplanes", response_model=list[AirplaneResponse])
def list_airplanes(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[AirplaneResponse]:
    airplanes = db.scalars(select(Airplane).order_by(Airplane.airplane_id)).all()
    return [_build_airplane_response(db, airplane) for airplane in airplanes]


@router.post("/airplanes", response_model=AirplaneResponse, status_code=status.HTTP_201_CREATED)
def create_airplane(
    payload: AirplanePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> AirplaneResponse:
    airplane = Airplane(**payload.model_dump())
    db.add(airplane)
    create_audit_log(
        db,
        admin,
        "CREATE_AIRPLANE",
        "Airplane",
        airplane.airplane_id,
        airplane.aircraft_type,
    )
    db.commit()
    db.refresh(airplane)
    return _build_airplane_response(db, airplane)


@router.put("/airplanes/{airplane_id}", response_model=AirplaneResponse)
def update_airplane(
    airplane_id: str,
    payload: AirplanePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> AirplaneResponse:
    airplane = db.get(Airplane, airplane_id)
    if airplane is None:
        raise HTTPException(status_code=404, detail="Airplane not found.")
    _ensure_airplane_deleteable(db, airplane_id)
    airplane.aircraft_type = payload.aircraft_type
    airplane.f_class_capacity = payload.f_class_capacity
    airplane.y_class_capacity = payload.y_class_capacity
    create_audit_log(
        db,
        admin,
        "UPDATE_AIRPLANE",
        "Airplane",
        airplane_id,
        payload.aircraft_type,
    )
    db.commit()
    db.refresh(airplane)
    return _build_airplane_response(db, airplane)


@router.delete("/airplanes/{airplane_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_airplane(
    airplane_id: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    airplane = db.get(Airplane, airplane_id)
    if airplane is None:
        raise HTTPException(status_code=404, detail="Airplane not found.")
    _ensure_airplane_deleteable(db, airplane_id)
    db.delete(airplane)
    create_audit_log(db, admin, "DELETE_AIRPLANE", "Airplane", airplane_id, "")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Airplane is still referenced.") from exc


@router.get("/routes", response_model=list[RouteResponse])
def list_routes(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[RouteResponse]:
    routes = db.scalars(select(Route).order_by(Route.route_id)).all()
    return [_build_route_response(db, route) for route in routes]


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RoutePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> RouteResponse:
    route = Route(route_id=payload.route_id, route_name=payload.route_name)
    db.add(route)
    db.flush()
    for segment in payload.segments:
        db.add(RouteSegment(route_id=route.route_id, **segment.model_dump()))
    for pricing in payload.pricing:
        db.add(
            RoutePricing(
                route_id=route.route_id,
                cabin_class=pricing.cabin_class,
                base_price=pricing.base_price,
            ),
        )
    create_audit_log(db, admin, "CREATE_ROUTE", "Route", route.route_id, route.route_name)
    db.commit()
    db.refresh(route)
    return _build_route_response(db, route)


@router.put("/routes/{route_id}", response_model=RouteResponse)
def update_route(
    route_id: str,
    payload: RoutePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> RouteResponse:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    _ensure_route_deleteable(db, route_id)
    route.route_name = payload.route_name
    db.execute(delete(RouteSegment).where(RouteSegment.route_id == route_id))
    db.execute(delete(RoutePricing).where(RoutePricing.route_id == route_id))
    db.flush()
    for segment in payload.segments:
        db.add(RouteSegment(route_id=route_id, **segment.model_dump()))
    for pricing in payload.pricing:
        db.add(
            RoutePricing(
                route_id=route_id,
                cabin_class=pricing.cabin_class,
                base_price=pricing.base_price,
            ),
        )
    create_audit_log(db, admin, "UPDATE_ROUTE", "Route", route_id, payload.route_name)
    db.commit()
    db.refresh(route)
    return _build_route_response(db, route)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(
    route_id: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    route = db.get(Route, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    _ensure_route_deleteable(db, route_id)
    db.delete(route)
    create_audit_log(db, admin, "DELETE_ROUTE", "Route", route_id, "")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Route is still referenced.") from exc


@router.get("/flight-templates", response_model=list[FlightTemplateResponse])
def list_templates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[FlightTemplateResponse]:
    templates = db.scalars(select(FlightTemplate).order_by(FlightTemplate.template_id)).all()
    return [_build_template_response(db, template) for template in templates]


@router.post(
    "/flight-templates",
    response_model=FlightTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    payload: FlightTemplatePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> FlightTemplateResponse:
    template = FlightTemplate(
        flight_no=payload.flight_no,
        route_id=payload.route_id,
        default_airplane_id=payload.default_airplane_id,
        default_flight_discount=payload.default_flight_discount,
        status=payload.status,
    )
    db.add(template)
    db.flush()
    for weekday in payload.weekdays:
        db.add(FlightTemplateWeekday(template_id=template.template_id, weekday=weekday))
    create_audit_log(
        db,
        admin,
        "CREATE_TEMPLATE",
        "FlightTemplate",
        str(template.template_id),
        payload.flight_no,
    )
    db.commit()
    db.refresh(template)
    return _build_template_response(db, template)


@router.put("/flight-templates/{template_id}", response_model=FlightTemplateResponse)
def update_template(
    template_id: int,
    payload: FlightTemplatePayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> FlightTemplateResponse:
    template = db.get(FlightTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    template.flight_no = payload.flight_no
    template.route_id = payload.route_id
    template.default_airplane_id = payload.default_airplane_id
    template.default_flight_discount = payload.default_flight_discount
    template.status = payload.status
    db.execute(
        delete(FlightTemplateWeekday).where(
            FlightTemplateWeekday.template_id == template_id,
        ),
    )
    db.flush()
    for weekday in payload.weekdays:
        db.add(FlightTemplateWeekday(template_id=template_id, weekday=weekday))
    create_audit_log(
        db,
        admin,
        "UPDATE_TEMPLATE",
        "FlightTemplate",
        str(template_id),
        payload.flight_no,
    )
    db.commit()
    db.refresh(template)
    return _build_template_response(db, template)


@router.delete("/flight-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    template = db.get(FlightTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    db.delete(template)
    create_audit_log(db, admin, "DELETE_TEMPLATE", "FlightTemplate", str(template_id), "")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Template is still referenced.") from exc


@router.post("/schedules/generate", response_model=GenerateScheduleResponse, status_code=201)
def generate(
    payload: GenerateScheduleRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> GenerateScheduleResponse:
    summary = generate_schedules(
        db,
        admin,
        payload.template_id,
        payload.start_date,
        payload.end_date,
    )
    return GenerateScheduleResponse(
        template_id=summary.template_id,
        template_weekdays=summary.template_weekdays,
        matched_dates=summary.matched_dates,
        generated_count=len(summary.generated_dates),
        generated_dates=summary.generated_dates,
        skipped_existing_dates=summary.skipped_existing_dates,
    )


@router.get("/special-fares", response_model=list[SpecialFarePlanResponse])
def list_special_fares(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[SpecialFarePlanResponse]:
    plans = db.scalars(
        select(SpecialFarePlan).order_by(
            SpecialFarePlan.flight_date.desc(),
            SpecialFarePlan.flight_no,
            SpecialFarePlan.special_fare_id.desc(),
        ),
    ).all()
    return [_build_special_fare_response(plan) for plan in plans]


@router.post("/special-fares", response_model=SpecialFarePlanResponse, status_code=status.HTTP_201_CREATED)
def create_special_fare(
    payload: SpecialFarePlanPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> SpecialFarePlanResponse:
    plan = SpecialFarePlan(**payload.model_dump())
    db.add(plan)
    db.flush()
    create_audit_log(
        db,
        admin,
        "CREATE_SPECIAL_FARE",
        "SpecialFarePlan",
        str(plan.special_fare_id),
        f"{plan.flight_no}/{plan.flight_date}",
    )
    db.commit()
    db.refresh(plan)
    return _build_special_fare_response(plan)


@router.put("/special-fares/{special_fare_id}", response_model=SpecialFarePlanResponse)
def update_special_fare(
    special_fare_id: int,
    payload: SpecialFarePlanPayload,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> SpecialFarePlanResponse:
    plan = db.get(SpecialFarePlan, special_fare_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Special fare plan not found.")
    for field, value in payload.model_dump().items():
        setattr(plan, field, value)
    create_audit_log(
        db,
        admin,
        "UPDATE_SPECIAL_FARE",
        "SpecialFarePlan",
        str(special_fare_id),
        f"{plan.flight_no}/{plan.flight_date}",
    )
    db.commit()
    db.refresh(plan)
    return _build_special_fare_response(plan)


@router.delete("/special-fares/{special_fare_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_special_fare(
    special_fare_id: int,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> None:
    plan = db.get(SpecialFarePlan, special_fare_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Special fare plan not found.")
    db.delete(plan)
    create_audit_log(
        db,
        admin,
        "DELETE_SPECIAL_FARE",
        "SpecialFarePlan",
        str(special_fare_id),
        "",
    )
    db.commit()


@router.post(
    "/schedules/{flight_no}/{flight_date}/cancel",
    response_model=CancelScheduleResponse,
)
def cancel(
    flight_no: str,
    flight_date: date,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[Account, Depends(require_admin)],
) -> CancelScheduleResponse:
    refunded_tickets = cancel_schedule(db, admin, flight_no, flight_date)
    return CancelScheduleResponse(
        flight_no=flight_no,
        flight_date=flight_date,
        refunded_tickets=refunded_tickets,
    )


@router.get("/orders", response_model=list[AdminTicketResponse])
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[AdminTicketResponse]:
    tickets = db.scalars(select(TicketSale).order_by(TicketSale.created_at.desc())).all()
    responses: list[AdminTicketResponse] = []
    for ticket in tickets:
        passenger = db.get(Passenger, ticket.passenger_id)
        payment = db.scalar(select(PaymentRecord).where(PaymentRecord.payment_id == ticket.payment_id))
        responses.append(
            AdminTicketResponse(
                ticket_no=ticket.ticket_no,
                payment_id=ticket.payment_id,
                flight_no=ticket.flight_no,
                flight_date=ticket.flight_date,
                passenger_id_card_masked=passenger.id_card_masked if passenger else "UNKNOWN",
                passenger_name_masked=passenger.name_masked if passenger else "UNKNOWN",
                start_segment_id=ticket.start_segment_id,
                end_segment_id=ticket.end_segment_id,
                cabin_class=ticket.cabin_class,
                status=ticket.status,
                actual_price=float(ticket.actual_price),
                price_source=ticket.price_source,
                payment_status=payment.payment_status if payment else "UNKNOWN",
                payer_account_masked=payment.payer_account_masked if payment else None,
                created_at=ticket.created_at,
                hold_expires_at=ticket.hold_expires_at,
                paid_at=ticket.paid_at,
                refunded_at=ticket.refunded_at,
            ),
        )
    return responses


@router.get("/audits", response_model=list[AuditResponse])
def list_audits(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Account, Depends(require_admin)],
) -> list[OperationAuditLog]:
    return db.scalars(
        select(OperationAuditLog).order_by(OperationAuditLog.created_at.desc()),
    ).all()
