from datetime import date


def login(client, identifier: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"login_identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_generate_schedule_cancel_flight_and_user_cannot_access_admin(
    client,
):
    user_token = login(client, "alice01", "user123")
    admin_token = login(client, "admin", "admin123")

    forbidden_response = client.post(
        "/admin/schedules/generate",
        json={
            "template_id": 2,
            "start_date": "2030-01-27",
            "end_date": "2030-01-27",
        },
        headers=auth_header(user_token),
    )
    assert forbidden_response.status_code == 403, forbidden_response.text

    generated_response = client.post(
        "/admin/schedules/generate",
        json={
            "template_id": 2,
            "start_date": "2030-01-27",
            "end_date": "2030-01-27",
        },
        headers=auth_header(admin_token),
    )
    assert generated_response.status_code == 201, generated_response.text
    assert generated_response.json()["generated_count"] == 1
    assert generated_response.json()["generated_dates"] == ["2030-01-27"]
    assert date.fromisoformat("2030-01-27").isoformat() == "2030-01-27"

    search_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "CSX",
            "flight_date": "2030-01-20",
            "cabin_class": "Y",
        },
        headers=auth_header(user_token),
    )
    assert search_response.status_code == 200, search_response.text
    assert any(
        row["flight_no"] == "MU2001" for row in search_response.json()
    )

    purchase_response = client.post(
        "/tickets/purchase",
        json={
            "flight_no": "MU2001",
            "flight_date": "2030-01-20",
            "start_segment_id": 3,
            "end_segment_id": 3,
            "cabin_class": "Y",
        },
        headers=auth_header(user_token),
    )
    assert purchase_response.status_code == 201, purchase_response.text

    confirm_response = client.post(
        f"/payments/{purchase_response.json()['payment_id']}/confirm",
        json={"payment_method": "ALIPAY", "payer_account": "alice-pay-001"},
        headers=auth_header(user_token),
    )
    assert confirm_response.status_code == 200, confirm_response.text

    cancel_response = client.post(
        "/admin/schedules/MU2001/2030-01-20/cancel",
        headers=auth_header(admin_token),
    )
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.json()["refunded_tickets"] == 1

    orders_response = client.get("/me/orders", headers=auth_header(user_token))
    assert orders_response.status_code == 200, orders_response.text
    assert orders_response.json()[0]["status"] == "REFUNDED"

    admin_orders = client.get("/admin/orders", headers=auth_header(admin_token))
    assert admin_orders.status_code == 200, admin_orders.text
    assert len(admin_orders.json()) >= 1
    assert "passenger_id_card_masked" in admin_orders.json()[0]
    assert "payment_status" in admin_orders.json()[0]


def test_admin_can_manage_reference_data_and_templates(client):
    admin_token = login(client, "admin", "admin123")

    city_response = client.post(
        "/admin/cities",
        json={"city_code": "XNA", "city_name": "Xian New Area"},
        headers=auth_header(admin_token),
    )
    assert city_response.status_code == 201, city_response.text

    airport_response = client.post(
        "/admin/airports",
        json={
            "airport_code": "XIY",
            "airport_name": "Xian Demo Airport",
            "city_code": "XNA",
        },
        headers=auth_header(admin_token),
    )
    assert airport_response.status_code == 201, airport_response.text

    airplane_response = client.post(
        "/admin/airplanes",
        json={
            "airplane_id": "C919-003",
            "aircraft_type": "COMAC C919",
            "f_class_capacity": 4,
            "y_class_capacity": 12,
        },
        headers=auth_header(admin_token),
    )
    assert airplane_response.status_code == 201, airplane_response.text

    route_response = client.post(
        "/admin/routes",
        json={
            "route_id": "R9001",
            "route_name": "Xian-Shanghai",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "XIY",
                    "arr_airport_code": "SHA",
                    "planned_dep_time": "09:00:00",
                    "planned_arr_time": "11:20:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 880},
                {"cabin_class": "F", "base_price": 1680},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert route_response.status_code == 201, route_response.text

    template_response = client.post(
        "/admin/flight-templates",
        json={
            "flight_no": "MU9001",
            "route_id": "R9001",
            "default_airplane_id": "C919-003",
            "default_flight_discount": 0.92,
            "status": "ACTIVE",
            "weekdays": [1, 3, 5],
        },
        headers=auth_header(admin_token),
    )
    assert template_response.status_code == 201, template_response.text

    routes_response = client.get("/admin/routes", headers=auth_header(admin_token))
    assert routes_response.status_code == 200, routes_response.text
    assert any(route["route_id"] == "R9001" for route in routes_response.json())

    templates_response = client.get(
        "/admin/flight-templates",
        headers=auth_header(admin_token),
    )
    assert templates_response.status_code == 200, templates_response.text
    assert any(
        template["flight_no"] == "MU9001" for template in templates_response.json()
    )


def test_admin_rejects_blank_reference_data_payloads(client):
    admin_token = login(client, "admin", "admin123")

    city_response = client.post(
        "/admin/cities",
        json={"city_code": "   ", "city_name": "   "},
        headers=auth_header(admin_token),
    )
    assert city_response.status_code == 422, city_response.text

    airport_response = client.post(
        "/admin/airports",
        json={
            "airport_code": "  ",
            "airport_name": "  ",
            "city_code": "SHA",
        },
        headers=auth_header(admin_token),
    )
    assert airport_response.status_code == 422, airport_response.text

    airplane_response = client.post(
        "/admin/airplanes",
        json={
            "airplane_id": "   ",
            "aircraft_type": "   ",
            "f_class_capacity": 2,
            "y_class_capacity": 10,
        },
        headers=auth_header(admin_token),
    )
    assert airplane_response.status_code == 422, airplane_response.text

    route_response = client.post(
        "/admin/routes",
        json={
            "route_id": "  ",
            "route_name": "  ",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": "09:00:00",
                    "planned_arr_time": "11:20:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 880},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert route_response.status_code == 422, route_response.text

    template_response = client.post(
        "/admin/flight-templates",
        json={
            "flight_no": "   ",
            "route_id": "R1001",
            "default_airplane_id": "A320-001",
            "default_flight_discount": 0.92,
            "status": "ACTIVE",
            "weekdays": [1, 1, 8],
        },
        headers=auth_header(admin_token),
    )
    assert template_response.status_code == 422, template_response.text


def test_admin_can_update_route_and_template(client):
    admin_token = login(client, "admin", "admin123")

    route_response = client.post(
        "/admin/routes",
        json={
            "route_id": "R9002",
            "route_name": "Beijing-Shanghai",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": "09:00:00",
                    "planned_arr_time": "11:20:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 880},
                {"cabin_class": "F", "base_price": 1680},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert route_response.status_code == 201, route_response.text

    update_route_response = client.put(
        "/admin/routes/R9002",
        json={
            "route_id": "R9002",
            "route_name": "Beijing-Shanghai Express",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": "09:30:00",
                    "planned_arr_time": "12:40:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 930},
                {"cabin_class": "F", "base_price": 1750},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert update_route_response.status_code == 200, update_route_response.text

    routes_response = client.get("/admin/routes", headers=auth_header(admin_token))
    updated_route = next(
        route for route in routes_response.json() if route["route_id"] == "R9002"
    )
    assert updated_route["route_name"] == "Beijing-Shanghai Express"
    assert updated_route["segments"][0]["arr_airport_code"] == "KMG"
    pricing_by_class = {
        item["cabin_class"]: item["base_price"] for item in updated_route["pricing"]
    }
    assert pricing_by_class["Y"] == 930.0
    assert pricing_by_class["F"] == 1750.0

    template_response = client.post(
        "/admin/flight-templates",
        json={
            "flight_no": "MU9002",
            "route_id": "R9002",
            "default_airplane_id": "A320-001",
            "default_flight_discount": 0.92,
            "status": "ACTIVE",
            "weekdays": [1, 3, 5],
        },
        headers=auth_header(admin_token),
    )
    assert template_response.status_code == 201, template_response.text
    template_id = template_response.json()["template_id"]

    update_template_response = client.put(
        f"/admin/flight-templates/{template_id}",
        json={
            "flight_no": "MU9002A",
            "route_id": "R9002",
            "default_airplane_id": "B737-002",
            "default_flight_discount": 0.85,
            "status": "ACTIVE",
            "weekdays": [2, 4, 6],
        },
        headers=auth_header(admin_token),
    )
    assert update_template_response.status_code == 200, update_template_response.text

    templates_response = client.get(
        "/admin/flight-templates",
        headers=auth_header(admin_token),
    )
    updated_template = next(
        template
        for template in templates_response.json()
        if template["template_id"] == template_id
    )
    assert updated_template["flight_no"] == "MU9002A"
    assert updated_template["default_airplane_id"] == "B737-002"
    assert updated_template["weekdays"] == [2, 4, 6]


def test_schedule_generation_response_explains_matches_and_skips(client):
    admin_token = login(client, "admin", "admin123")

    first_response = client.post(
        "/admin/schedules/generate",
        json={
            "template_id": 2,
            "start_date": "2030-01-27",
            "end_date": "2030-02-02",
        },
        headers=auth_header(admin_token),
    )
    assert first_response.status_code == 201, first_response.text
    first_payload = first_response.json()
    assert first_payload["template_weekdays"] == [date(2030, 1, 27).isoweekday()]
    assert first_payload["matched_dates"] == ["2030-01-27"]
    assert first_payload["generated_dates"] == ["2030-01-27"]
    assert first_payload["skipped_existing_dates"] == []

    second_response = client.post(
        "/admin/schedules/generate",
        json={
            "template_id": 2,
            "start_date": "2030-01-27",
            "end_date": "2030-02-02",
        },
        headers=auth_header(admin_token),
    )
    assert second_response.status_code == 201, second_response.text
    second_payload = second_response.json()
    assert second_payload["template_weekdays"] == [date(2030, 1, 27).isoweekday()]
    assert second_payload["matched_dates"] == ["2030-01-27"]
    assert second_payload["generated_dates"] == []
    assert second_payload["skipped_existing_dates"] == ["2030-01-27"]


def test_admin_can_manage_special_fares(client):
    admin_token = login(client, "admin", "admin123")

    create_response = client.post(
        "/admin/special-fares",
        json={
            "flight_no": "MU3003",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
            "start_segment_id": 6,
            "end_segment_id": 7,
            "special_price": 599,
            "quota_total": 5,
            "sale_start": "2025-01-01T00:00:00",
            "sale_end": "2030-01-15T23:59:59",
            "status": "ACTIVE",
        },
        headers=auth_header(admin_token),
    )
    assert create_response.status_code == 201, create_response.text
    special_fare_id = create_response.json()["special_fare_id"]

    list_response = client.get("/admin/special-fares", headers=auth_header(admin_token))
    assert list_response.status_code == 200, list_response.text
    assert any(item["special_fare_id"] == special_fare_id for item in list_response.json())

    update_response = client.put(
        f"/admin/special-fares/{special_fare_id}",
        json={
            "flight_no": "MU3003",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
            "start_segment_id": 6,
            "end_segment_id": 7,
            "special_price": 579,
            "quota_total": 3,
            "sale_start": "2025-01-01T00:00:00",
            "sale_end": "2030-01-15T23:59:59",
            "status": "ACTIVE",
        },
        headers=auth_header(admin_token),
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["special_price"] == 579.0
    assert update_response.json()["quota_total"] == 3


def test_admin_can_delete_unreferenced_reference_data_and_promotions(client):
    admin_token = login(client, "admin", "admin123")

    city_response = client.post(
        "/admin/cities",
        json={"city_code": "XDL", "city_name": "Delete City"},
        headers=auth_header(admin_token),
    )
    assert city_response.status_code == 201, city_response.text

    airport_response = client.post(
        "/admin/airports",
        json={
            "airport_code": "XDL1",
            "airport_name": "Delete Airport",
            "city_code": "XDL",
        },
        headers=auth_header(admin_token),
    )
    assert airport_response.status_code == 201, airport_response.text

    delete_airport = client.delete(
        "/admin/airports/XDL1",
        headers=auth_header(admin_token),
    )
    assert delete_airport.status_code == 204, delete_airport.text

    delete_city = client.delete(
        "/admin/cities/XDL",
        headers=auth_header(admin_token),
    )
    assert delete_city.status_code == 204, delete_city.text

    airplane_response = client.post(
        "/admin/airplanes",
        json={
            "airplane_id": "DEL-001",
            "aircraft_type": "Delete Plane",
            "f_class_capacity": 2,
            "y_class_capacity": 8,
        },
        headers=auth_header(admin_token),
    )
    assert airplane_response.status_code == 201, airplane_response.text

    delete_airplane = client.delete(
        "/admin/airplanes/DEL-001",
        headers=auth_header(admin_token),
    )
    assert delete_airplane.status_code == 204, delete_airplane.text

    route_response = client.post(
        "/admin/routes",
        json={
            "route_id": "RDEL1",
            "route_name": "Delete Route",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": "08:00:00",
                    "planned_arr_time": "10:20:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 600},
                {"cabin_class": "F", "base_price": 1200},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert route_response.status_code == 201, route_response.text

    delete_route = client.delete(
        "/admin/routes/RDEL1",
        headers=auth_header(admin_token),
    )
    assert delete_route.status_code == 204, delete_route.text

    template_route = client.post(
        "/admin/routes",
        json={
            "route_id": "RDEL2",
            "route_name": "Delete Template Route",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": "12:00:00",
                    "planned_arr_time": "15:30:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 700},
                {"cabin_class": "F", "base_price": 1300},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert template_route.status_code == 201, template_route.text

    template_response = client.post(
        "/admin/flight-templates",
        json={
            "flight_no": "MUDEL1",
            "route_id": "RDEL2",
            "default_airplane_id": "A320-001",
            "default_flight_discount": 0.90,
            "status": "ACTIVE",
            "weekdays": [1, 3],
        },
        headers=auth_header(admin_token),
    )
    assert template_response.status_code == 201, template_response.text
    template_id = template_response.json()["template_id"]

    delete_template = client.delete(
        f"/admin/flight-templates/{template_id}",
        headers=auth_header(admin_token),
    )
    assert delete_template.status_code == 204, delete_template.text

    delete_template_route = client.delete(
        "/admin/routes/RDEL2",
        headers=auth_header(admin_token),
    )
    assert delete_template_route.status_code == 204, delete_template_route.text

    special_fare_response = client.post(
        "/admin/special-fares",
        json={
            "flight_no": "MU3003",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
            "start_segment_id": 6,
            "end_segment_id": 7,
            "special_price": 588,
            "quota_total": 2,
            "sale_start": "2025-01-01T00:00:00",
            "sale_end": "2030-01-15T23:59:59",
            "status": "ACTIVE",
        },
        headers=auth_header(admin_token),
    )
    assert special_fare_response.status_code == 201, special_fare_response.text
    special_fare_id = special_fare_response.json()["special_fare_id"]

    delete_special_fare = client.delete(
        f"/admin/special-fares/{special_fare_id}",
        headers=auth_header(admin_token),
    )
    assert delete_special_fare.status_code == 204, delete_special_fare.text


def test_admin_lists_reference_block_flags_and_rejects_updates_for_referenced_records(client):
    admin_token = login(client, "admin", "admin123")

    cities_response = client.get("/admin/cities", headers=auth_header(admin_token))
    assert cities_response.status_code == 200, cities_response.text
    shanghai_city = next(
        city for city in cities_response.json() if city["city_code"] == "SHA"
    )
    assert shanghai_city["is_referenced"] is True
    assert shanghai_city["can_edit"] is False
    assert shanghai_city["can_delete"] is False
    assert shanghai_city["blocked_reason"]

    airports_response = client.get("/admin/airports", headers=auth_header(admin_token))
    assert airports_response.status_code == 200, airports_response.text
    shanghai_airport = next(
        airport
        for airport in airports_response.json()
        if airport["airport_code"] == "SHA"
    )
    assert shanghai_airport["is_referenced"] is True
    assert shanghai_airport["can_edit"] is False
    assert shanghai_airport["can_delete"] is False
    assert shanghai_airport["blocked_reason"]

    airplanes_response = client.get("/admin/airplanes", headers=auth_header(admin_token))
    assert airplanes_response.status_code == 200, airplanes_response.text
    seeded_airplane = next(
        airplane
        for airplane in airplanes_response.json()
        if airplane["airplane_id"] == "A320-001"
    )
    assert seeded_airplane["is_referenced"] is True
    assert seeded_airplane["can_edit"] is False
    assert seeded_airplane["can_delete"] is False
    assert seeded_airplane["blocked_reason"]

    routes_response = client.get("/admin/routes", headers=auth_header(admin_token))
    assert routes_response.status_code == 200, routes_response.text
    seeded_route = next(
        route for route in routes_response.json() if route["route_id"] == "R1001"
    )
    assert seeded_route["is_referenced"] is True
    assert seeded_route["can_edit"] is False
    assert seeded_route["can_delete"] is False
    assert seeded_route["blocked_reason"]

    update_city = client.put(
        "/admin/cities/SHA",
        json={"city_code": "SHA", "city_name": "Shanghai Updated"},
        headers=auth_header(admin_token),
    )
    assert update_city.status_code == 409, update_city.text

    update_airport = client.put(
        "/admin/airports/SHA",
        json={
            "airport_code": "SHA",
            "airport_name": "Shanghai Hongqiao Updated",
            "city_code": "SHA",
        },
        headers=auth_header(admin_token),
    )
    assert update_airport.status_code == 409, update_airport.text

    update_airplane = client.put(
        "/admin/airplanes/A320-001",
        json={
            "airplane_id": "A320-001",
            "aircraft_type": "Airbus A320 Updated",
            "f_class_capacity": 2,
            "y_class_capacity": 1,
        },
        headers=auth_header(admin_token),
    )
    assert update_airplane.status_code == 409, update_airplane.text

    update_route = client.put(
        "/admin/routes/R1001",
        json={
            "route_id": "R1001",
            "route_name": "Shanghai-Changsha-Kunming Updated",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "SHA",
                    "arr_airport_code": "CSX",
                    "planned_dep_time": "08:30:00",
                    "planned_arr_time": "10:10:00",
                },
                {
                    "segment_order": 2,
                    "dep_airport_code": "CSX",
                    "arr_airport_code": "KMG",
                    "planned_dep_time": "11:10:00",
                    "planned_arr_time": "13:10:00",
                },
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 1080},
                {"cabin_class": "F", "base_price": 2080},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert update_route.status_code == 409, update_route.text


def test_admin_delete_referenced_reference_data_returns_conflict(client):
    admin_token = login(client, "admin", "admin123")

    city_response = client.post(
        "/admin/cities",
        json={"city_code": "XRF", "city_name": "Referenced City"},
        headers=auth_header(admin_token),
    )
    assert city_response.status_code == 201, city_response.text

    airport_one = client.post(
        "/admin/airports",
        json={
            "airport_code": "XRF1",
            "airport_name": "Referenced Airport 1",
            "city_code": "XRF",
        },
        headers=auth_header(admin_token),
    )
    assert airport_one.status_code == 201, airport_one.text

    airport_two = client.post(
        "/admin/airports",
        json={
            "airport_code": "XRF2",
            "airport_name": "Referenced Airport 2",
            "city_code": "XRF",
        },
        headers=auth_header(admin_token),
    )
    assert airport_two.status_code == 201, airport_two.text

    airplane_response = client.post(
        "/admin/airplanes",
        json={
            "airplane_id": "REF-001",
            "aircraft_type": "Referenced Plane",
            "f_class_capacity": 4,
            "y_class_capacity": 10,
        },
        headers=auth_header(admin_token),
    )
    assert airplane_response.status_code == 201, airplane_response.text

    route_response = client.post(
        "/admin/routes",
        json={
            "route_id": "RREF1",
            "route_name": "Referenced Route",
            "segments": [
                {
                    "segment_order": 1,
                    "dep_airport_code": "XRF1",
                    "arr_airport_code": "XRF2",
                    "planned_dep_time": "07:30:00",
                    "planned_arr_time": "08:45:00",
                }
            ],
            "pricing": [
                {"cabin_class": "Y", "base_price": 380},
                {"cabin_class": "F", "base_price": 780},
            ],
        },
        headers=auth_header(admin_token),
    )
    assert route_response.status_code == 201, route_response.text

    template_response = client.post(
        "/admin/flight-templates",
        json={
            "flight_no": "MUREF1",
            "route_id": "RREF1",
            "default_airplane_id": "REF-001",
            "default_flight_discount": 0.95,
            "status": "ACTIVE",
            "weekdays": [2, 4],
        },
        headers=auth_header(admin_token),
    )
    assert template_response.status_code == 201, template_response.text

    delete_city = client.delete(
        "/admin/cities/XRF",
        headers=auth_header(admin_token),
    )
    assert delete_city.status_code == 409, delete_city.text

    delete_airport = client.delete(
        "/admin/airports/XRF1",
        headers=auth_header(admin_token),
    )
    assert delete_airport.status_code == 409, delete_airport.text

    delete_airplane = client.delete(
        "/admin/airplanes/REF-001",
        headers=auth_header(admin_token),
    )
    assert delete_airplane.status_code == 409, delete_airplane.text

    delete_route = client.delete(
        "/admin/routes/RREF1",
        headers=auth_header(admin_token),
    )
    assert delete_route.status_code == 409, delete_route.text
