from __future__ import annotations

from datetime import date, datetime, time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _normalize_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be blank.")
    return normalized


def _normalize_upper_non_empty(value: str) -> str:
    return _normalize_non_empty(value).upper()


def _normalize_cabin_class(value: str) -> str:
    normalized = _normalize_upper_non_empty(value)
    if normalized not in {"F", "Y"}:
        raise ValueError("Cabin class must be F or Y.")
    return normalized


def _normalize_template_status(value: str) -> str:
    normalized = _normalize_upper_non_empty(value)
    if normalized not in {"ACTIVE", "INACTIVE"}:
        raise ValueError("Template status must be ACTIVE or INACTIVE.")
    return normalized


def _normalize_payment_method(value: str) -> str:
    normalized = _normalize_upper_non_empty(value)
    if normalized not in {"ALIPAY", "WECHAT", "BANK_CARD"}:
        raise ValueError("Payment method must be ALIPAY, WECHAT, or BANK_CARD.")
    return normalized


TrimmedNonEmptyStr = Annotated[str, AfterValidator(_normalize_non_empty)]
UpperCodeStr = Annotated[str, AfterValidator(_normalize_upper_non_empty)]
CabinClassStr = Annotated[str, AfterValidator(_normalize_cabin_class)]
TemplateStatusStr = Annotated[str, AfterValidator(_normalize_template_status)]
PaymentMethodStr = Annotated[str, AfterValidator(_normalize_payment_method)]


class LoginRequest(BaseModel):
    login_identifier: TrimmedNonEmptyStr
    password: TrimmedNonEmptyStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    login_identifier: str
    role: str
    passenger_id: int | None = None
    passenger_id_card_masked: str | None = None
    passenger_name_masked: str | None = None
    user_type: str | None = None
    mileage_points: float | None = None


class MeSensitiveResponse(BaseModel):
    passenger_name_full: str
    passenger_id_card_full: str


class ReferenceCityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_code: str
    city_name: str


class SearchFlightResponse(BaseModel):
    flight_no: str
    flight_date: date
    origin_airport: str
    destination_airport: str
    origin_airport_name: str
    destination_airport_name: str
    origin_segment_id: int
    destination_segment_id: int
    cabin_class: str
    available_seats: int
    final_price: float
    departure_time: time
    arrival_time: time
    price_source: str
    is_special_fare: bool
    special_fare_tag: str | None = None


class SearchFlightQuery(BaseModel):
    origin_airport_code: UpperCodeStr | None = None
    destination_airport_code: UpperCodeStr | None = None
    origin_city_code: UpperCodeStr | None = None
    destination_city_code: UpperCodeStr | None = None
    flight_date: date
    cabin_class: CabinClassStr

    @model_validator(mode="after")
    def validate_location_filters(self) -> SearchFlightQuery:
        has_airport_filter = self.origin_airport_code is not None or self.destination_airport_code is not None
        has_city_filter = self.origin_city_code is not None or self.destination_city_code is not None
        if has_airport_filter:
            if self.origin_airport_code is None or self.destination_airport_code is None:
                raise ValueError(
                    "Origin and destination airport codes must be provided together.",
                )
        if has_airport_filter and has_city_filter:
            raise ValueError("Airport-code filters and city-code filters cannot be mixed.")
        return self


class SearchFlightRangeQuery(BaseModel):
    origin_airport_code: UpperCodeStr | None = None
    destination_airport_code: UpperCodeStr | None = None
    origin_city_code: UpperCodeStr | None = None
    destination_city_code: UpperCodeStr | None = None
    start_date: date
    end_date: date
    cabin_class: CabinClassStr

    @model_validator(mode="after")
    def validate_range_filters(self) -> SearchFlightRangeQuery:
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date.")

        has_origin_airport = self.origin_airport_code is not None
        has_destination_airport = self.destination_airport_code is not None
        if has_origin_airport != has_destination_airport:
            raise ValueError(
                "Origin and destination airport codes must be provided together.",
            )
        has_city_filter = self.origin_city_code is not None or self.destination_city_code is not None
        if has_origin_airport and has_city_filter:
            raise ValueError("Airport-code filters and city-code filters cannot be mixed.")
        return self


class PurchaseTicketRequest(BaseModel):
    flight_no: UpperCodeStr
    flight_date: date
    start_segment_id: int = Field(ge=1)
    end_segment_id: int = Field(ge=1)
    cabin_class: CabinClassStr


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_no: str
    payment_id: str
    flight_no: str
    flight_date: date
    passenger_id: int
    start_segment_id: int
    end_segment_id: int
    cabin_class: str
    status: str
    actual_price: float
    price_source: str
    is_special_fare: bool
    origin_city_name: str | None = None
    destination_city_name: str | None = None
    created_at: datetime
    hold_expires_at: datetime | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None


class AdminTicketResponse(BaseModel):
    ticket_no: str
    payment_id: str
    flight_no: str
    flight_date: date
    passenger_id_card_masked: str
    passenger_name_masked: str
    start_segment_id: int
    end_segment_id: int
    cabin_class: str
    status: str
    actual_price: float
    price_source: str
    payment_status: str
    payer_account_masked: str | None = None
    created_at: datetime
    hold_expires_at: datetime | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None


class PaymentConfirmRequest(BaseModel):
    payment_method: PaymentMethodStr
    payer_account: TrimmedNonEmptyStr


class PaymentResponse(BaseModel):
    payment_id: str
    ticket_no: str
    payment_method: str
    payment_status: str
    pay_amount: float
    mock_trade_no: str | None = None
    payer_account_masked: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    refunded_at: datetime | None = None


class WaitlistCreateRequest(BaseModel):
    flight_no: UpperCodeStr
    flight_date: date
    start_segment_id: int = Field(ge=1)
    end_segment_id: int = Field(ge=1)
    cabin_class: CabinClassStr


class WaitlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    waitlist_id: int
    flight_no: str
    flight_date: date
    start_segment_id: int
    end_segment_id: int
    cabin_class: str
    passenger_id: int
    status: str
    origin_city_name: str | None = None
    destination_city_name: str | None = None
    request_time: datetime
    released_at: datetime | None = None
    linked_ticket_no: str | None = None
    offer_expires_at: datetime | None = None


class GenerateScheduleRequest(BaseModel):
    template_id: int
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> GenerateScheduleRequest:
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date.")
        return self


class GenerateScheduleResponse(BaseModel):
    template_id: int
    template_weekdays: list[int]
    matched_dates: list[date]
    generated_count: int
    generated_dates: list[date]
    skipped_existing_dates: list[date]


class CityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    city_code: str
    city_name: str
    is_referenced: bool = False
    can_edit: bool = True
    can_delete: bool = True
    blocked_reason: str | None = None


class CityPayload(BaseModel):
    city_code: UpperCodeStr
    city_name: TrimmedNonEmptyStr


class AirportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    airport_code: str
    airport_name: str
    city_code: str
    is_referenced: bool = False
    can_edit: bool = True
    can_delete: bool = True
    blocked_reason: str | None = None


class AirportPayload(BaseModel):
    airport_code: UpperCodeStr
    airport_name: TrimmedNonEmptyStr
    city_code: UpperCodeStr


class AirplaneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    airplane_id: str
    aircraft_type: str
    f_class_capacity: int
    y_class_capacity: int
    is_referenced: bool = False
    can_edit: bool = True
    can_delete: bool = True
    blocked_reason: str | None = None


class AirplanePayload(BaseModel):
    airplane_id: UpperCodeStr
    aircraft_type: TrimmedNonEmptyStr
    f_class_capacity: int = Field(ge=0)
    y_class_capacity: int = Field(ge=0)


class RouteSegmentPayload(BaseModel):
    segment_order: int = Field(ge=1)
    dep_airport_code: UpperCodeStr
    arr_airport_code: UpperCodeStr
    planned_dep_time: time
    planned_arr_time: time

    @model_validator(mode="after")
    def validate_segment_airports(self) -> RouteSegmentPayload:
        if self.dep_airport_code == self.arr_airport_code:
            raise ValueError("Departure and arrival airports must be different.")
        return self


class RouteSegmentResponse(BaseModel):
    segment_id: int
    segment_order: int
    dep_airport_code: str
    arr_airport_code: str
    planned_dep_time: time
    planned_arr_time: time


class RoutePricingPayload(BaseModel):
    cabin_class: CabinClassStr
    base_price: float = Field(gt=0)


class RoutePricingResponse(BaseModel):
    cabin_class: str
    base_price: float


class RoutePayload(BaseModel):
    route_id: UpperCodeStr
    route_name: TrimmedNonEmptyStr
    segments: list[RouteSegmentPayload]
    pricing: list[RoutePricingPayload]

    @model_validator(mode="after")
    def validate_route_structure(self) -> RoutePayload:
        if not self.segments:
            raise ValueError("At least one route segment is required.")
        if not self.pricing:
            raise ValueError("At least one cabin pricing row is required.")

        segment_orders = sorted(segment.segment_order for segment in self.segments)
        expected_orders = list(range(1, len(self.segments) + 1))
        if segment_orders != expected_orders:
            raise ValueError("Route segments must use continuous ordering starting at 1.")

        cabin_classes = [pricing.cabin_class for pricing in self.pricing]
        if len(set(cabin_classes)) != len(cabin_classes):
            raise ValueError("Duplicate cabin pricing is not allowed.")
        return self


class RouteResponse(BaseModel):
    route_id: str
    route_name: str
    segments: list[RouteSegmentResponse]
    pricing: list[RoutePricingResponse]
    is_referenced: bool = False
    can_edit: bool = True
    can_delete: bool = True
    blocked_reason: str | None = None


class FlightTemplatePayload(BaseModel):
    flight_no: UpperCodeStr
    route_id: UpperCodeStr
    default_airplane_id: UpperCodeStr
    default_flight_discount: float = Field(gt=0, le=1)
    status: TemplateStatusStr = "ACTIVE"
    weekdays: list[Annotated[int, Field(ge=1, le=7)]]

    @model_validator(mode="after")
    def validate_weekdays(self) -> FlightTemplatePayload:
        if not self.weekdays:
            raise ValueError("At least one weekday is required.")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("Duplicate weekdays are not allowed.")
        return self


class FlightTemplateResponse(BaseModel):
    template_id: int
    flight_no: str
    route_id: str
    default_airplane_id: str
    default_flight_discount: float
    status: str
    weekdays: list[int]


class SpecialFarePlanPayload(BaseModel):
    flight_no: UpperCodeStr
    flight_date: date
    cabin_class: CabinClassStr
    start_segment_id: int = Field(ge=1)
    end_segment_id: int = Field(ge=1)
    special_price: float = Field(gt=0)
    quota_total: int = Field(gt=0)
    sale_start: datetime
    sale_end: datetime
    status: TemplateStatusStr = "ACTIVE"

    @model_validator(mode="after")
    def validate_sale_window(self) -> SpecialFarePlanPayload:
        if self.sale_end <= self.sale_start:
            raise ValueError("sale_end must be later than sale_start.")
        return self


class SpecialFarePlanResponse(BaseModel):
    special_fare_id: int
    flight_no: str
    flight_date: date
    cabin_class: str
    start_segment_id: int
    end_segment_id: int
    special_price: float
    quota_total: int
    quota_used: int
    sale_start: datetime
    sale_end: datetime
    status: str


class CancelScheduleResponse(BaseModel):
    flight_no: str
    flight_date: date
    refunded_tickets: int


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: int
    actor_account_id: int | None
    action: str
    entity_type: str
    entity_id: str
    detail: str
    created_at: datetime
