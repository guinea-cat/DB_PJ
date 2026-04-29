from datetime import timedelta

from sqlalchemy import select

from app import services
from app.models import Account, Passenger, PaymentRecord, ScheduleInventory, SpecialFarePlan, TicketSale
from app.security import encrypt_sensitive_value, hash_password, hash_sensitive_value


def login(client, identifier: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"login_identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def confirm_pending_payment(client, token: str, payment_id: str, payer_account: str = "demo-pay-001") -> None:
    response = client.post(
        f"/payments/{payment_id}/confirm",
        json={"payment_method": "ALIPAY", "payer_account": payer_account},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text


def create_test_user(session, *, login_identifier: str, password: str, name: str, id_card: str) -> None:
    passenger = Passenger(
        id_card_hash=hash_sensitive_value(id_card),
        id_card_encrypted=encrypt_sensitive_value(id_card),
        id_card_masked=f"{id_card[:3]}{'*' * (len(id_card) - 7)}{id_card[-4:]}",
        name_encrypted=encrypt_sensitive_value(name),
        name_masked=f"{name[0]}{'*' * max(len(name) - 1, 0)}",
        type_id=1,
        mileage_points=0,
    )
    session.add(passenger)
    session.flush()
    session.add(
        Account(
            login_identifier=login_identifier,
            password_hash=hash_password(password),
            role="USER",
            status="ACTIVE",
            passenger_id=passenger.passenger_id,
        )
    )
    session.commit()


def test_user_can_login_search_purchase_and_upgrade_to_vip(client):
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
    search_payload = search_response.json()
    assert len(search_payload) >= 3
    mu1001_row = next(row for row in search_payload if row["flight_no"] == "MU1001")
    assert mu1001_row["available_seats"] == 1
    assert mu1001_row["final_price"] == 720.0
    assert mu1001_row["price_source"] == "STANDARD"

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
    assert purchase_payload["actual_price"] == 720.0

    confirm_pending_payment(client, token, purchase_payload["payment_id"], "alice-pay-001")

    me_response = client.get("/auth/me", headers=auth_header(token))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["user_type"] == "VIP"
    assert me_response.json()["mileage_points"] == 10620.0

    my_orders = client.get("/me/orders", headers=auth_header(token))
    assert my_orders.status_code == 200, my_orders.text
    assert len(my_orders.json()) == 1
    assert my_orders.json()[0]["status"] == "PAID"
    assert my_orders.json()[0]["origin_city_name"] == "Shanghai"
    assert my_orders.json()[0]["destination_city_name"] == "Kunming"


def test_same_user_cannot_purchase_same_flight_twice_even_with_different_cabin_or_segments(client):
    token = login(client, "alice01", "user123")

    first_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert first_search.status_code == 200, first_search.text
    mu1001_y_row = next(row for row in first_search.json() if row["flight_no"] == "MU1001")

    first_purchase = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_y_row["flight_no"],
            "flight_date": mu1001_y_row["flight_date"],
            "start_segment_id": mu1001_y_row["origin_segment_id"],
            "end_segment_id": mu1001_y_row["destination_segment_id"],
            "cabin_class": mu1001_y_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert first_purchase.status_code == 201, first_purchase.text

    second_same_cabin = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_y_row["flight_no"],
            "flight_date": mu1001_y_row["flight_date"],
            "start_segment_id": mu1001_y_row["origin_segment_id"],
            "end_segment_id": mu1001_y_row["destination_segment_id"],
            "cabin_class": mu1001_y_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert second_same_cabin.status_code == 409, second_same_cabin.text
    assert "one active ticket" in second_same_cabin.text

    first_class_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "F",
        },
        headers=auth_header(token),
    )
    assert first_class_search.status_code == 200, first_class_search.text
    mu1001_f_row = next(row for row in first_class_search.json() if row["flight_no"] == "MU1001")

    second_different_cabin = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_f_row["flight_no"],
            "flight_date": mu1001_f_row["flight_date"],
            "start_segment_id": mu1001_f_row["origin_segment_id"],
            "end_segment_id": mu1001_f_row["destination_segment_id"],
            "cabin_class": mu1001_f_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert second_different_cabin.status_code == 409, second_different_cabin.text
    assert "one active ticket" in second_different_cabin.text

    segment_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "CSX",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert segment_search.status_code == 200, segment_search.text
    mu1001_segment_row = next(row for row in segment_search.json() if row["flight_no"] == "MU1001")

    second_different_segment = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_segment_row["flight_no"],
            "flight_date": mu1001_segment_row["flight_date"],
            "start_segment_id": mu1001_segment_row["origin_segment_id"],
            "end_segment_id": mu1001_segment_row["destination_segment_id"],
            "cabin_class": mu1001_segment_row["cabin_class"],
        },
        headers=auth_header(token),
    )
    assert second_different_segment.status_code == 409, second_different_segment.text
    assert "one active ticket" in second_different_segment.text


def test_same_user_can_purchase_same_flight_again_after_refund(client):
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

    first_purchase = client.post(
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
    assert first_purchase.status_code == 201, first_purchase.text
    ticket_no = first_purchase.json()["ticket_no"]
    confirm_pending_payment(client, token, first_purchase.json()["payment_id"], "alice-pay-001")

    refund_response = client.post(
        f"/tickets/{ticket_no}/refund",
        headers=auth_header(token),
    )
    assert refund_response.status_code == 200, refund_response.text

    second_purchase = client.post(
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
    assert second_purchase.status_code == 201, second_purchase.text


def test_pending_order_can_be_cancelled_and_releases_inventory_and_special_fare_quota(client, session):
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

    cancel_response = client.post(
        f"/tickets/{purchase_payload['ticket_no']}/cancel",
        headers=auth_header(token),
    )
    assert cancel_response.status_code == 200, cancel_response.text
    cancelled_payload = cancel_response.json()
    assert cancelled_payload["status"] == "CANCELLED"

    cancelled_ticket = session.scalar(
        select(TicketSale).where(TicketSale.ticket_no == purchase_payload["ticket_no"])
    )
    assert cancelled_ticket is not None
    assert cancelled_ticket.is_active_ticket is None
    assert cancelled_ticket.hold_expires_at is None

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
            ScheduleInventory.flight_no == purchase_payload["flight_no"],
            ScheduleInventory.flight_date == cancelled_ticket.flight_date,
        ),
    ).all()
    assert inventory_rows
    assert all(row.y_seats_left == 24 for row in inventory_rows)

    my_orders = client.get("/me/orders", headers=auth_header(token))
    assert my_orders.status_code == 200, my_orders.text
    assert my_orders.json()[0]["status"] == "CANCELLED"


def test_paid_order_cannot_use_pending_cancel_endpoint(client):
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

    confirm_pending_payment(client, token, purchase_payload["payment_id"], "alice-pay-001")

    cancel_response = client.post(
        f"/tickets/{purchase_payload['ticket_no']}/cancel",
        headers=auth_header(token),
    )
    assert cancel_response.status_code == 400, cancel_response.text
    assert "awaiting payment" in cancel_response.text or "pending" in cancel_response.text.lower()


def test_inventory_sse_stream_emits_event_after_purchase(client):
    token = login(client, "alice01", "user123")
    bob_token = login(client, "bob01", "user123")

    with client.stream("GET", f"/flights/stream/inventory?access_token={bob_token}") as response:
        assert response.status_code == 200, response.text

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

        stream_text = ""
        for chunk in response.iter_text():
            stream_text += chunk
            if "inventory_update" in stream_text:
                break

        assert "inventory_update" in stream_text
        assert '"flight_no": "MU1001"' in stream_text
        assert '"cabin_class": "Y"' in stream_text


def test_same_user_can_refund_same_flight_across_multiple_purchase_cycles(client):
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

    first_purchase = client.post(
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
    assert first_purchase.status_code == 201, first_purchase.text
    confirm_pending_payment(client, token, first_purchase.json()["payment_id"], "alice-pay-001")

    first_refund = client.post(
        f"/tickets/{first_purchase.json()['ticket_no']}/refund",
        headers=auth_header(token),
    )
    assert first_refund.status_code == 200, first_refund.text

    second_purchase = client.post(
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
    assert second_purchase.status_code == 201, second_purchase.text
    confirm_pending_payment(client, token, second_purchase.json()["payment_id"], "alice-pay-002")

    second_refund = client.post(
        f"/tickets/{second_purchase.json()['ticket_no']}/refund",
        headers=auth_header(token),
    )
    assert second_refund.status_code == 200, second_refund.text
    assert second_refund.json()["status"] == "REFUNDED"

    my_orders = client.get("/me/orders", headers=auth_header(token))
    assert my_orders.status_code == 200, my_orders.text
    refunded_orders = [order for order in my_orders.json() if order["status"] == "REFUNDED"]
    assert len(refunded_orders) == 2


def test_refund_reverses_points_and_downgrades_vip_when_threshold_no_longer_met(client):
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
    ticket_no = purchase_response.json()["ticket_no"]
    confirm_pending_payment(client, token, purchase_response.json()["payment_id"], "alice-pay-001")

    after_purchase = client.get("/auth/me", headers=auth_header(token))
    assert after_purchase.status_code == 200, after_purchase.text
    assert after_purchase.json()["user_type"] == "VIP"
    assert after_purchase.json()["mileage_points"] == 10620.0

    refund_response = client.post(
        f"/tickets/{ticket_no}/refund",
        headers=auth_header(token),
    )
    assert refund_response.status_code == 200, refund_response.text

    after_refund = client.get("/auth/me", headers=auth_header(token))
    assert after_refund.status_code == 200, after_refund.text
    assert after_refund.json()["user_type"] == "NORMAL"
    assert after_refund.json()["mileage_points"] == 9900.0


def test_refund_releases_inventory_and_notifies_waitlist(client):
    buyer_token = login(client, "alice01", "user123")
    waiter_token = login(client, "bob01", "user123")

    initial_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(buyer_token),
    )
    assert initial_search.status_code == 200, initial_search.text
    mu1001_row = next(row for row in initial_search.json() if row["flight_no"] == "MU1001")

    purchase_response = client.post(
        "/tickets/purchase",
        json={
            "flight_no": mu1001_row["flight_no"],
            "flight_date": mu1001_row["flight_date"],
            "start_segment_id": mu1001_row["origin_segment_id"],
            "end_segment_id": mu1001_row["destination_segment_id"],
            "cabin_class": mu1001_row["cabin_class"],
        },
        headers=auth_header(buyer_token),
    )
    assert purchase_response.status_code == 201, purchase_response.text
    ticket_no = purchase_response.json()["ticket_no"]
    confirm_pending_payment(client, buyer_token, purchase_response.json()["payment_id"], "alice-pay-001")

    sold_out_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(waiter_token),
    )
    assert sold_out_search.status_code == 200, sold_out_search.text
    sold_out_row = next(row for row in sold_out_search.json() if row["flight_no"] == "MU1001")
    assert sold_out_row["available_seats"] == 0

    waitlist_response = client.post(
        "/waitlists",
        json={
            "flight_no": sold_out_row["flight_no"],
            "flight_date": sold_out_row["flight_date"],
            "start_segment_id": sold_out_row["origin_segment_id"],
            "end_segment_id": sold_out_row["destination_segment_id"],
            "cabin_class": sold_out_row["cabin_class"],
        },
        headers=auth_header(waiter_token),
    )
    assert waitlist_response.status_code == 201, waitlist_response.text
    assert waitlist_response.json()["status"] == "WAITING"

    refund_response = client.post(
        f"/tickets/{ticket_no}/refund",
        headers=auth_header(buyer_token),
    )
    assert refund_response.status_code == 200, refund_response.text
    assert refund_response.json()["status"] == "REFUNDED"

    waitlists = client.get("/me/waitlists", headers=auth_header(waiter_token))
    assert waitlists.status_code == 200, waitlists.text
    released_waitlist = waitlists.json()[0]
    assert released_waitlist["status"] == "RELEASED"
    assert released_waitlist["linked_ticket_no"] is not None
    assert released_waitlist["offer_expires_at"] is not None
    assert released_waitlist["origin_city_name"] == "Shanghai"
    assert released_waitlist["destination_city_name"] == "Kunming"

    waiter_orders = client.get("/me/orders", headers=auth_header(waiter_token))
    assert waiter_orders.status_code == 200, waiter_orders.text
    assert waiter_orders.json()[0]["ticket_no"] == released_waitlist["linked_ticket_no"]
    assert waiter_orders.json()[0]["status"] == "PENDING_PAYMENT"
    assert waiter_orders.json()[0]["origin_city_name"] == "Shanghai"
    assert waiter_orders.json()[0]["destination_city_name"] == "Kunming"

    refreshed_search = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(waiter_token),
    )
    assert refreshed_search.status_code == 200, refreshed_search.text
    refreshed_row = next(row for row in refreshed_search.json() if row["flight_no"] == "MU1001")
    assert refreshed_row["available_seats"] == 0


def test_waitlist_offer_expires_and_rolls_forward_to_next_user(client, session, monkeypatch):
    buyer_token = login(client, "alice01", "user123")
    bob_token = login(client, "bob01", "user123")

    search_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(buyer_token),
    )
    assert search_response.status_code == 200, search_response.text
    target_row = next(row for row in search_response.json() if row["flight_no"] == "MU1001")

    purchase_response = client.post(
        "/tickets/purchase",
        json={
            "flight_no": target_row["flight_no"],
            "flight_date": target_row["flight_date"],
            "start_segment_id": target_row["origin_segment_id"],
            "end_segment_id": target_row["destination_segment_id"],
            "cabin_class": target_row["cabin_class"],
        },
        headers=auth_header(buyer_token),
    )
    assert purchase_response.status_code == 201, purchase_response.text
    confirm_pending_payment(client, buyer_token, purchase_response.json()["payment_id"], "alice-pay-001")

    first_waitlist = client.post(
        "/waitlists",
        json={
            "flight_no": target_row["flight_no"],
            "flight_date": target_row["flight_date"],
            "start_segment_id": target_row["origin_segment_id"],
            "end_segment_id": target_row["destination_segment_id"],
            "cabin_class": target_row["cabin_class"],
        },
        headers=auth_header(bob_token),
    )
    assert first_waitlist.status_code == 201, first_waitlist.text

    create_test_user(
        session,
        login_identifier="charlie01",
        password="user123",
        name="Charlie",
        id_card="110101199001010033",
    )
    charlie_token = login(client, "charlie01", "user123")

    second_waitlist = client.post(
        "/waitlists",
        json={
            "flight_no": target_row["flight_no"],
            "flight_date": target_row["flight_date"],
            "start_segment_id": target_row["origin_segment_id"],
            "end_segment_id": target_row["destination_segment_id"],
            "cabin_class": target_row["cabin_class"],
        },
        headers=auth_header(charlie_token),
    )
    assert second_waitlist.status_code == 201, second_waitlist.text

    refund_response = client.post(
        f"/tickets/{purchase_response.json()['ticket_no']}/refund",
        headers=auth_header(buyer_token),
    )
    assert refund_response.status_code == 200, refund_response.text

    bob_waitlists = client.get("/me/waitlists", headers=auth_header(bob_token))
    assert bob_waitlists.status_code == 200, bob_waitlists.text
    first_offer = bob_waitlists.json()[0]
    assert first_offer["status"] == "RELEASED"
    assert first_offer["linked_ticket_no"] is not None

    original_now = services.utcnow_naive()
    monkeypatch.setattr(
        services,
        "utcnow_naive",
        lambda: original_now + timedelta(minutes=16),
    )

    trigger_response = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(charlie_token),
    )
    assert trigger_response.status_code == 200, trigger_response.text

    expired_bob_waitlists = client.get("/me/waitlists", headers=auth_header(bob_token))
    assert expired_bob_waitlists.status_code == 200, expired_bob_waitlists.text
    assert expired_bob_waitlists.json()[0]["status"] == "EXPIRED"

    charlie_waitlists = client.get("/me/waitlists", headers=auth_header(charlie_token))
    assert charlie_waitlists.status_code == 200, charlie_waitlists.text
    assert charlie_waitlists.json()[0]["status"] == "RELEASED"
    assert charlie_waitlists.json()[0]["linked_ticket_no"] is not None

    charlie_orders = client.get("/me/orders", headers=auth_header(charlie_token))
    assert charlie_orders.status_code == 200, charlie_orders.text
    assert charlie_orders.json()[0]["status"] == "PENDING_PAYMENT"


def test_waitlist_rejects_unknown_segments_instead_of_crashing(client):
    token = login(client, "bob01", "user123")

    response = client.post(
        "/waitlists",
        json={
            "flight_no": "MU1001",
            "flight_date": "2030-01-15",
            "start_segment_id": 9999,
            "end_segment_id": 9999,
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Segment not found."


def test_demo_seed_returns_multiple_sellable_flights_for_key_routes(client):
    token = login(client, "alice01", "user123")

    sha_to_kmg = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert sha_to_kmg.status_code == 200, sha_to_kmg.text
    sha_to_kmg_payload = sha_to_kmg.json()
    assert len(sha_to_kmg_payload) >= 3
    assert all(item["available_seats"] > 0 for item in sha_to_kmg_payload)
    assert sha_to_kmg_payload == sorted(
        sha_to_kmg_payload,
        key=lambda item: (item["departure_time"], item["flight_no"]),
    )

    sha_to_csx = client.get(
        "/flights/search",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "CSX",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert sha_to_csx.status_code == 200, sha_to_csx.text
    sha_to_csx_payload = sha_to_csx.json()
    assert len(sha_to_csx_payload) >= 3
    assert all(item["available_seats"] > 0 for item in sha_to_csx_payload)
    assert sha_to_csx_payload == sorted(
        sha_to_csx_payload,
        key=lambda item: (item["departure_time"], item["flight_no"]),
    )


def test_single_search_allows_origin_city_only_filter(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search",
        params={
            "origin_city_code": "SHA",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload
    assert all(item["origin_airport"] in {"SHA", "PVG"} for item in payload)
    assert any(item["destination_airport"] == "KMG" for item in payload)
    assert any(item["destination_airport"] == "CSX" for item in payload)


def test_single_search_allows_destination_city_only_filter(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search",
        params={
            "destination_city_code": "KMG",
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload
    assert all(item["destination_airport"] == "KMG" for item in payload)
    assert any(item["origin_airport"] == "SHA" for item in payload)


def test_single_search_allows_all_cities_without_filters(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search",
        params={
            "flight_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert len(payload) >= 4
    assert all(item["available_seats"] > 0 for item in payload)


def test_range_search_returns_sorted_multi_day_results(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search/range",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "start_date": "2030-01-15",
            "end_date": "2030-01-17",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert len(payload) >= 6
    assert len({item["flight_date"] for item in payload}) >= 2
    assert all(item["available_seats"] > 0 for item in payload)
    assert payload == sorted(
        payload,
        key=lambda item: (
            item["flight_date"],
            item["departure_time"],
            item["flight_no"],
        ),
    )


def test_range_search_without_airports_returns_all_sellable_flights(client):
    token = login(client, "alice01", "user123")

    all_flights_response = client.get(
        "/flights/search/range",
        params={
            "start_date": "2030-01-15",
            "end_date": "2030-01-16",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert all_flights_response.status_code == 200, all_flights_response.text
    all_flights_payload = all_flights_response.json()
    assert len(all_flights_payload) >= 8
    assert all(item["available_seats"] > 0 for item in all_flights_payload)

    targeted_response = client.get(
        "/flights/search/range",
        params={
            "origin_airport_code": "SHA",
            "destination_airport_code": "KMG",
            "start_date": "2030-01-15",
            "end_date": "2030-01-16",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert targeted_response.status_code == 200, targeted_response.text
    assert len(all_flights_payload) > len(targeted_response.json())


def test_range_search_allows_origin_city_only_filter(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search/range",
        params={
            "origin_city_code": "SHA",
            "start_date": "2030-01-15",
            "end_date": "2030-01-16",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload
    assert all(item["origin_airport"] in {"SHA", "PVG"} for item in payload)
    assert len({item["flight_date"] for item in payload}) >= 2


def test_range_search_allows_destination_city_only_filter(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search/range",
        params={
            "destination_city_code": "KMG",
            "start_date": "2030-01-15",
            "end_date": "2030-01-16",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload
    assert all(item["destination_airport"] == "KMG" for item in payload)
    assert len({item["flight_date"] for item in payload}) >= 2


def test_range_search_rejects_half_filled_airport_filters(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search/range",
        params={
            "origin_airport_code": "SHA",
            "start_date": "2030-01-15",
            "end_date": "2030-01-16",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422, response.text


def test_range_search_rejects_end_date_before_start_date(client):
    token = login(client, "alice01", "user123")

    response = client.get(
        "/flights/search/range",
        params={
            "start_date": "2030-01-16",
            "end_date": "2030-01-15",
            "cabin_class": "Y",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422, response.text
