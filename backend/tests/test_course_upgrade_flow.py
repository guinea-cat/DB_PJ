from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import services
from app.models import Passenger, PaymentRecord, ScheduleInventory, SpecialFarePlan, TicketSale


def login(client, identifier: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"login_identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_masked_passenger_profile_and_seed_encrypts_sensitive_fields(client, session):
    token = login(client, "alice01", "user123")

    me_response = client.get("/auth/me", headers=auth_header(token))

    assert me_response.status_code == 200, me_response.text
    payload = me_response.json()
    assert payload["passenger_id_card_masked"] == "110***********0011"
    assert payload["passenger_name_masked"].startswith("A")
    assert "passenger_id_card" not in payload
    assert "passenger_name" not in payload

    passenger = session.scalar(select(Passenger).where(Passenger.passenger_id == 1))
    assert passenger is not None
    assert passenger.id_card_encrypted != "110101199001010011"
    assert passenger.name_encrypted != "Alice"
    assert passenger.id_card_hash
    assert passenger.name_masked.startswith("A")

    sensitive_response = client.get("/auth/me/sensitive", headers=auth_header(token))
    assert sensitive_response.status_code == 200, sensitive_response.text
    assert sensitive_response.json()["passenger_name_full"] == "Alice"
    assert sensitive_response.json()["passenger_id_card_full"] == "110101199001010011"


def test_admin_cannot_fetch_sensitive_passenger_profile(client):
    admin_token = login(client, "admin", "admin123")

    sensitive_response = client.get(
        "/auth/me/sensitive",
        headers=auth_header(admin_token),
    )

    assert sensitive_response.status_code == 403, sensitive_response.text


def test_purchase_creates_pending_order_then_confirm_payment_marks_paid_and_upgrades_vip(client):
    token = login(client, "alice01", "user123")

    search_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert search_response.status_code == 200, search_response.text
    mu1001_row = next(row for row in search_response.json() if row["flight_no"] == "MU1001")
    assert mu1001_row["price_source"] == "STANDARD"
    assert mu1001_row["final_price"] == 720.0

    purchase_response = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_row["flight_no"],
            "flight_date": mu1001_row["flight_date"],
            "start_segment_id": mu1001_row["origin_segment_id"],
            "end_segment_id": mu1001_row["destination_segment_id"],
            "cabin_class": mu1001_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert purchase_response.status_code == 201, purchase_response.text
    purchase_payload = purchase_response.json()
    assert purchase_payload["status"] == "PENDING_PAYMENT"
    assert purchase_payload["payment_id"].startswith("P")
    assert purchase_payload["hold_expires_at"] is not None
    assert purchase_payload["price_source"] == "STANDARD"
    created_at = datetime.fromisoformat(purchase_payload["created_at"])
    hold_expires_at = datetime.fromisoformat(purchase_payload["hold_expires_at"])
    assert hold_expires_at - created_at == timedelta(minutes=15)

    me_before_payment = client.get("/auth/me", headers=auth_header(token))
    assert me_before_payment.status_code == 200, me_before_payment.text
    assert me_before_payment.json()["user_type"] == "NORMAL"
    assert me_before_payment.json()["mileage_points"] == 9900.0

    confirm_response = client.post(
        f"/payments/{purchase_payload['payment_id']}/confirm",
        json={
            "payment_method": "ALIPAY",
            "payer_account": "alice-payment-001",
        },
        headers=auth_header(token),
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirm_payload = confirm_response.json()
    assert confirm_payload["payment_status"] == "PAID"
    assert confirm_payload["payer_account_masked"].startswith("ali")

    my_orders = client.get("/me/orders", headers=auth_header(token))
    assert my_orders.status_code == 200, my_orders.text
    assert my_orders.json()[0]["status"] == "PAID"
    assert my_orders.json()[0]["payment_id"] == purchase_payload["payment_id"]

    me_after_payment = client.get("/auth/me", headers=auth_header(token))
    assert me_after_payment.status_code == 200, me_after_payment.text
    assert me_after_payment.json()["user_type"] == "VIP"
    assert me_after_payment.json()["mileage_points"] == 10620.0


def test_expired_pending_order_releases_inventory_and_special_fare_quota(client, session, monkeypatch):
    token = login(client, "bob01", "user123")

    search_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert search_response.status_code == 200, search_response.text
    mu3001_row = next(row for row in search_response.json() if row["flight_no"] == "MU3001")
    assert mu3001_row["price_source"] == "SPECIAL"
    assert mu3001_row["is_special_fare"] is True

    purchase_response = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu3001_row["flight_no"],
            "flight_date": mu3001_row["flight_date"],
            "start_segment_id": mu3001_row["origin_segment_id"],
            "end_segment_id": mu3001_row["destination_segment_id"],
            "cabin_class": mu3001_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert purchase_response.status_code == 201, purchase_response.text
    purchase_payload = purchase_response.json()
    assert purchase_payload["status"] == "PENDING_PAYMENT"
    assert purchase_payload["price_source"] == "SPECIAL"
    assert purchase_payload["is_special_fare"] is True

    original_now = services.utcnow_naive()
    monkeypatch.setattr(
        services,
        "utcnow_naive",
        lambda: original_now + timedelta(minutes=16),
    )

    refreshed_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert refreshed_search.status_code == 200, refreshed_search.text

    expired_ticket = session.scalar(
        select(TicketSale).where(TicketSale.ticket_no == purchase_payload["ticket_no"]),
    )
    assert expired_ticket is not None
    assert expired_ticket.status == "EXPIRED"
    assert expired_ticket.is_active_ticket is None

    payment_record = session.scalar(
        select(PaymentRecord).where(PaymentRecord.payment_id == purchase_payload["payment_id"]),
    )
    assert payment_record is not None
    assert payment_record.payment_status == "EXPIRED"

    special_plan = session.scalar(select(SpecialFarePlan).where(SpecialFarePlan.flight_no == "MU3001"))
    assert special_plan is not None
    assert special_plan.quota_used == 0

    inventory_rows = session.scalars(
        select(ScheduleInventory).where(
            ScheduleInventory.flight_no == "MU3001",
            ScheduleInventory.flight_date == expired_ticket.flight_date,
        ),
    ).all()
    assert inventory_rows
    assert all(row.y_seats_left == 24 for row in inventory_rows)


def test_search_uses_special_fare_and_inventory_tier_pricing(client, session):
    token = login(client, "bob01", "user123")

    mu3001_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert mu3001_response.status_code == 200, mu3001_response.text
    mu3001_row = next(row for row in mu3001_response.json() if row["flight_no"] == "MU3001")
    assert mu3001_row["price_source"] == "SPECIAL"
    assert mu3001_row["special_fare_tag"] == "SPECIAL"
    assert mu3001_row["final_price"] == 699.0

    schedule_inventory = session.scalars(
        select(ScheduleInventory).where(
            ScheduleInventory.flight_no == "MU3003",
            ScheduleInventory.flight_date == mu3001_row["flight_date"],
        ),
    ).all()
    for row in schedule_inventory:
        row.y_seats_left = 10
    session.commit()

    tiered_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "CAN",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert tiered_response.status_code == 200, tiered_response.text
    mu3003_row = next(row for row in tiered_response.json() if row["flight_no"] == "MU3003")
    assert mu3003_row["price_source"] == "STANDARD"
    assert mu3003_row["is_special_fare"] is False
    assert mu3003_row["final_price"] == float(
        (Decimal("980.00") * Decimal("0.90") * Decimal("0.90") * Decimal("1.05")).quantize(
            Decimal("0.01"),
        ),
    )


def test_services_now_uses_business_timezone() -> None:
    expected_now = datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    actual_now = services.utcnow_naive()

    assert abs((actual_now - expected_now).total_seconds()) < 5


def test_reference_cities_and_city_search_return_airport_names(client):
    cities_response = client.get("/reference/cities")
    assert cities_response.status_code == 200, cities_response.text
    cities_payload = cities_response.json()
    assert any(item["city_code"] == "SHA" and item["city_name"] == "Shanghai" for item in cities_payload)

    token = login(client, "alice01", "user123")
    search_response = client.get(
        "/flights/search",
        params={
            "origin_city_code": "SHA",
            "destination_city_code": "BJS",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert search_response.status_code == 200, search_response.text

    result = next(row for row in search_response.json() if row["flight_no"] == "MU3007")
    assert result["origin_airport"] == "PVG"
    assert result["destination_airport"] == "PEK"
    assert result["origin_airport_name"] == "Shanghai Pudong"
    assert result["destination_airport_name"] == "Beijing Capital"
