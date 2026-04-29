from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Account,
    Airplane,
    Airport,
    City,
    DemoDataVersion,
    FlightSchedule,
    FlightTemplate,
    FlightTemplateWeekday,
    Passenger,
    Route,
    RoutePricing,
    RouteSegment,
    ScheduleInventory,
    SpecialFarePlan,
    UserType,
)
from app.security import encrypt_sensitive_value, hash_password, hash_sensitive_value

DEMO_SEED_VERSION = 3
DEMO_SEED_KEY = "demo_seed"
USER_WINDOW_START = date(2030, 1, 13)
USER_WINDOW_END = date(2030, 1, 26)


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _mask_id_card(id_card: str) -> str:
    if len(id_card) <= 7:
        return "*" * len(id_card)
    return f"{id_card[:3]}{'*' * (len(id_card) - 7)}{id_card[-4:]}"


def _mask_name(name: str) -> str:
    normalized = name.strip()
    if len(normalized) <= 1:
        return "*"
    if len(normalized) == 2:
        return f"{normalized[0]}*"
    return f"{normalized[0]}{'*' * (len(normalized) - 2)}{normalized[-1]}"


def _create_passenger(id_card: str, name: str, type_id: int, mileage_points: Decimal) -> Passenger:
    return Passenger(
        id_card_hash=hash_sensitive_value(id_card),
        id_card_encrypted=encrypt_sensitive_value(id_card),
        id_card_masked=_mask_id_card(id_card),
        name_encrypted=encrypt_sensitive_value(name),
        name_masked=_mask_name(name),
        type_id=type_id,
        mileage_points=mileage_points,
    )


def seed_test_data(db: Session) -> None:
    current_version = db.get(DemoDataVersion, DEMO_SEED_KEY)
    if current_version is not None and current_version.version >= DEMO_SEED_VERSION:
        return

    cities = [
        City(city_code="SHA", city_name="Shanghai"),
        City(city_code="CSX", city_name="Changsha"),
        City(city_code="KMG", city_name="Kunming"),
        City(city_code="BJS", city_name="Beijing"),
        City(city_code="CAN", city_name="Guangzhou"),
        City(city_code="SZX", city_name="Shenzhen"),
        City(city_code="CTU", city_name="Chengdu"),
    ]
    db.add_all(cities)
    db.flush()

    airports = [
        Airport(airport_code="SHA", airport_name="Shanghai Hongqiao", city_code="SHA"),
        Airport(airport_code="PVG", airport_name="Shanghai Pudong", city_code="SHA"),
        Airport(airport_code="CSX", airport_name="Changsha Huanghua", city_code="CSX"),
        Airport(airport_code="KMG", airport_name="Kunming Changshui", city_code="KMG"),
        Airport(airport_code="PEK", airport_name="Beijing Capital", city_code="BJS"),
        Airport(airport_code="PKX", airport_name="Beijing Daxing", city_code="BJS"),
        Airport(airport_code="CAN", airport_name="Guangzhou Baiyun", city_code="CAN"),
        Airport(airport_code="SZX", airport_name="Shenzhen Baoan", city_code="SZX"),
        Airport(airport_code="TFU", airport_name="Chengdu Tianfu", city_code="CTU"),
    ]
    db.add_all(airports)

    airplanes = [
        Airplane(
            airplane_id="A320-001",
            aircraft_type="Airbus A320",
            f_class_capacity=2,
            y_class_capacity=1,
        ),
        Airplane(
            airplane_id="B737-002",
            aircraft_type="Boeing 737-800",
            f_class_capacity=2,
            y_class_capacity=2,
        ),
        Airplane(
            airplane_id="A321-003",
            aircraft_type="Airbus A321neo",
            f_class_capacity=4,
            y_class_capacity=24,
        ),
        Airplane(
            airplane_id="C919-004",
            aircraft_type="COMAC C919",
            f_class_capacity=6,
            y_class_capacity=32,
        ),
    ]
    db.add_all(airplanes)

    db.add_all(
        [
            UserType(type_id=1, type_name="NORMAL", discount_rate=Decimal("0.90")),
            UserType(type_id=2, type_name="VIP", discount_rate=Decimal("0.80")),
        ],
    )

    alice = _create_passenger(
        id_card="110101199001010011",
        name="Alice",
        type_id=1,
        mileage_points=Decimal("9900.00"),
    )
    bob = _create_passenger(
        id_card="110101199001010022",
        name="Bob",
        type_id=1,
        mileage_points=Decimal("0.00"),
    )
    db.add_all([alice, bob])
    db.flush()

    db.add_all(
        [
            Account(
                login_identifier="alice01",
                password_hash=hash_password("user123"),
                role="USER",
                status="ACTIVE",
                passenger_id=alice.passenger_id,
            ),
            Account(
                login_identifier="bob01",
                password_hash=hash_password("user123"),
                role="USER",
                status="ACTIVE",
                passenger_id=bob.passenger_id,
            ),
            Account(
                login_identifier="admin",
                password_hash=hash_password("admin123"),
                role="ADMIN",
                status="ACTIVE",
                passenger_id=None,
            ),
        ],
    )

    route_definitions = [
        {
            "route_id": "R1001",
            "route_name": "Shanghai-Changsha-Kunming",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": time(8, 0),
                    "planned_arr_time": time(10, 0),
                },
                {
                    "segment_order": 2,
                    "dep_airport_code": "CSX",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": time(11, 0),
                    "planned_arr_time": time(13, 0),
                },
            ],
            "pricing": {
                "Y": Decimal("1000.00"),
                "F": Decimal("2000.00"),
            },
        },
        {
            "route_id": "R2001",
            "route_name": "Shanghai-Changsha",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": time(14, 0),
                    "planned_arr_time": time(16, 0),
                }
            ],
            "pricing": {
                "Y": Decimal("500.00"),
                "F": Decimal("1000.00"),
            },
        },
        {
            "route_id": "R3001",
            "route_name": "Shanghai-Kunming Express",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": time(9, 30),
                    "planned_arr_time": time(13, 10),
                }
            ],
            "pricing": {
                "Y": Decimal("1180.00"),
                "F": Decimal("2280.00"),
            },
        },
        {
            "route_id": "R3002",
            "route_name": "Shanghai-Changsha Business",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": time(10, 30),
                    "planned_arr_time": time(12, 40),
                }
            ],
            "pricing": {
                "Y": Decimal("560.00"),
                "F": Decimal("1160.00"),
            },
        },
        {
            "route_id": "R3003",
            "route_name": "Shanghai-Changsha-Guangzhou",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": time(15, 20),
                    "planned_arr_time": time(17, 20),
                },
                {
                    "segment_order": 2,
                    "dep_airport_code": "CSX",
                    "arr_airport_code": "CAN",
                    "planned_dep_time": time(18, 10),
                    "planned_arr_time": time(19, 50),
                },
            ],
            "pricing": {
                "Y": Decimal("980.00"),
                "F": Decimal("1860.00"),
            },
        },
        {
            "route_id": "R3004",
            "route_name": "Shanghai-Changsha-Kunming Evening",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": time(18, 0),
                    "planned_arr_time": time(20, 0),
                },
                {
                    "segment_order": 2,
                    "dep_airport_code": "CSX",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": time(20, 50),
                    "planned_arr_time": time(22, 50),
                },
            ],
            "pricing": {
                "Y": Decimal("1080.00"),
                "F": Decimal("2080.00"),
            },
        },
        {
            "route_id": "R3005",
            "route_name": "Beijing-Chengdu",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "PEK",
                    "arr_airport_code": "TFU",
                    "planned_dep_time": time(8, 40),
                    "planned_arr_time": time(11, 50),
                }
            ],
            "pricing": {
                "Y": Decimal("890.00"),
                "F": Decimal("1690.00"),
            },
        },
        {
            "route_id": "R3006",
            "route_name": "Guangzhou-Shenzhen Shuttle",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "CAN",
                    "arr_airport_code": "SZX",
                    "planned_dep_time": time(9, 15),
                    "planned_arr_time": time(10, 25),
                }
            ],
            "pricing": {
                "Y": Decimal("320.00"),
                "F": Decimal("620.00"),
            },
        },
        {
            "route_id": "R3007",
            "route_name": "Shanghai-Beijing Capital",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "PVG",
                    "arr_airport_code": "PEK",
                    "planned_dep_time": time(7, 30),
                    "planned_arr_time": time(9, 50),
                }
            ],
            "pricing": {
                "Y": Decimal("780.00"),
                "F": Decimal("1480.00"),
            },
        },
        {
            "route_id": "R3008",
            "route_name": "Beijing Daxing-Kunming",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "PKX",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": time(13, 20),
                    "planned_arr_time": time(17, 5),
                }
            ],
            "pricing": {
                "Y": Decimal("960.00"),
                "F": Decimal("1820.00"),
            },
        },
    ]

    db.add_all([Route(route_id=item["route_id"], route_name=item["route_name"]) for item in route_definitions])
    db.flush()

    route_segments_by_route: dict[str, list[RouteSegment]] = {}
    for route_definition in route_definitions:
        segments = [
            RouteSegment(route_id=route_definition["route_id"], **segment_definition)
            for segment_definition in route_definition["segments"]
        ]
        db.add_all(segments)
        route_segments_by_route[route_definition["route_id"]] = segments
    db.flush()

    pricing_rows: list[RoutePricing] = []
    for route_definition in route_definitions:
        pricing_rows.extend(
            [
                RoutePricing(
                    route_id=route_definition["route_id"],
                    cabin_class=cabin_class,
                    base_price=base_price,
                )
                for cabin_class, base_price in route_definition["pricing"].items()
            ],
        )
    db.add_all(pricing_rows)

    template_definitions = [
        {
            "flight_no": "MU1001",
            "route_id": "R1001",
            "default_airplane_id": "A320-001",
            "default_flight_discount": Decimal("0.80"),
            "weekdays": [2, 4, 6],
        },
        {
            "flight_no": "MU2001",
            "route_id": "R2001",
            "default_airplane_id": "B737-002",
            "default_flight_discount": Decimal("0.95"),
            "weekdays": [7],
        },
        {
            "flight_no": "MU3001",
            "route_id": "R3001",
            "default_airplane_id": "A321-003",
            "default_flight_discount": Decimal("0.88"),
            "weekdays": [1, 2, 3, 4, 5, 6],
        },
        {
            "flight_no": "MU3002",
            "route_id": "R3002",
            "default_airplane_id": "B737-002",
            "default_flight_discount": Decimal("0.92"),
            "weekdays": [2, 3, 4, 5, 6],
        },
        {
            "flight_no": "MU3003",
            "route_id": "R3003",
            "default_airplane_id": "A321-003",
            "default_flight_discount": Decimal("0.90"),
            "weekdays": [1, 2, 3, 5, 7],
        },
        {
            "flight_no": "MU3004",
            "route_id": "R3004",
            "default_airplane_id": "C919-004",
            "default_flight_discount": Decimal("0.86"),
            "weekdays": [2, 4, 6],
        },
        {
            "flight_no": "MU3005",
            "route_id": "R3005",
            "default_airplane_id": "A321-003",
            "default_flight_discount": Decimal("0.91"),
            "weekdays": [1, 4, 7],
        },
        {
            "flight_no": "MU3006",
            "route_id": "R3006",
            "default_airplane_id": "B737-002",
            "default_flight_discount": Decimal("0.95"),
            "weekdays": [1, 2, 3, 4, 5, 6, 7],
        },
        {
            "flight_no": "MU3007",
            "route_id": "R3007",
            "default_airplane_id": "A321-003",
            "default_flight_discount": Decimal("0.89"),
            "weekdays": [1, 2, 3, 4, 5],
        },
        {
            "flight_no": "MU3008",
            "route_id": "R3008",
            "default_airplane_id": "C919-004",
            "default_flight_discount": Decimal("0.87"),
            "weekdays": [2, 5, 7],
        },
        {
            "flight_no": "MU3009",
            "route_id": "R2001",
            "default_airplane_id": "A321-003",
            "default_flight_discount": Decimal("0.90"),
            "weekdays": [2, 4, 6],
        },
        {
            "flight_no": "MU3010",
            "route_id": "R3001",
            "default_airplane_id": "C919-004",
            "default_flight_discount": Decimal("0.85"),
            "weekdays": [3, 5, 7],
        },
    ]

    template_weekdays: list[tuple[FlightTemplate, list[int]]] = []
    for template_definition in template_definitions:
        template = FlightTemplate(
            flight_no=template_definition["flight_no"],
            route_id=template_definition["route_id"],
            default_airplane_id=template_definition["default_airplane_id"],
            default_flight_discount=template_definition["default_flight_discount"],
            status="ACTIVE",
        )
        db.add(template)
        template_weekdays.append((template, template_definition["weekdays"]))
    db.flush()

    weekday_rows: list[FlightTemplateWeekday] = []
    for template, weekdays in template_weekdays:
        weekday_rows.extend(
            [
                FlightTemplateWeekday(template_id=template.template_id, weekday=weekday)
                for weekday in weekdays
            ],
        )
    db.add_all(weekday_rows)

    airplanes_by_id = {airplane.airplane_id: airplane for airplane in airplanes}

    for flight_date in _date_range(USER_WINDOW_START, USER_WINDOW_END):
        for template, weekdays in template_weekdays:
            if flight_date.isoweekday() not in weekdays:
                continue

            airplane = airplanes_by_id[template.default_airplane_id]
            schedule = FlightSchedule(
                flight_no=template.flight_no,
                flight_date=flight_date,
                route_id=template.route_id,
                airplane_id=template.default_airplane_id,
                flight_discount=template.default_flight_discount,
                schedule_status="ACTIVE",
                template_id=template.template_id,
            )
            db.add(schedule)

            for segment in route_segments_by_route[template.route_id]:
                db.add(
                    ScheduleInventory(
                        flight_no=template.flight_no,
                        flight_date=flight_date,
                        segment_id=segment.segment_id,
                        f_seats_left=airplane.f_class_capacity,
                        y_seats_left=airplane.y_class_capacity,
                    ),
                )

    db.flush()

    special_route_segments = route_segments_by_route["R3001"]
    db.add(
        SpecialFarePlan(
            flight_no="MU3001",
            flight_date=date(2030, 1, 15),
            cabin_class="Y",
            start_segment_id=special_route_segments[0].segment_id,
            end_segment_id=special_route_segments[0].segment_id,
            special_price=Decimal("699.00"),
            quota_total=2,
            quota_used=0,
            sale_start=datetime(2025, 1, 10, 0, 0, 0),
            sale_end=datetime(2030, 1, 16, 23, 59, 59),
            status="ACTIVE",
        ),
    )

    if current_version is None:
        db.add(
            DemoDataVersion(
                version_key=DEMO_SEED_KEY,
                version=DEMO_SEED_VERSION,
            ),
        )
    else:
        current_version.version = DEMO_SEED_VERSION

    db.commit()
