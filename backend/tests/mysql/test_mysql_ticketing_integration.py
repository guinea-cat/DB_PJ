from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import sys

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.models import Account, ScheduleInventory, TicketSale, WaitlistRecord
from app.db_bootstrap import bootstrap_database
from app.services import confirm_payment, create_waitlist, purchase_ticket, refund_ticket


def _load_account(session: Session, login_identifier: str) -> Account:
    return session.scalar(
        select(Account).where(Account.login_identifier == login_identifier),
    )


@pytest.mark.mysql_integration
def test_mysql_concurrent_purchase_only_allows_one_success(mysql_engine, mysql_database_url: str):
    bootstrap_database(
        reset=True,
        seed_demo=True,
        database_url=mysql_database_url,
    )
    session_factory = sessionmaker(
        bind=mysql_engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )

    def buy(identifier: str) -> str:
        with session_factory() as session:
            account = _load_account(session, identifier)
            try:
                ticket = purchase_ticket(
                    session,
                    account,
                    "MU1001",
                    date(2030, 1, 15),
                    1,
                    2,
                    "Y",
                )
                return f"success:{ticket.ticket_no}"
            except Exception as exc:  # pragma: no cover - asserted by prefix
                session.rollback()
                return f"error:{exc}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                buy,
                ["alice01", "bob01"],
            ),
        )

    success_count = sum(result.startswith("success:") for result in results)
    error_count = sum(result.startswith("error:") for result in results)

    with session_factory() as session:
        tickets = session.scalars(
            select(TicketSale).where(
                TicketSale.flight_no == "MU1001",
                TicketSale.flight_date == date(2030, 1, 15),
                TicketSale.cabin_class == "Y",
            ),
        ).all()
        inventories = session.scalars(
            select(ScheduleInventory).where(
                ScheduleInventory.flight_no == "MU1001",
                ScheduleInventory.flight_date == date(2030, 1, 15),
            ),
        ).all()

    assert success_count == 1
    assert error_count == 1
    assert len(tickets) == 1
    assert all(inventory.y_seats_left == 0 for inventory in inventories)


@pytest.mark.mysql_integration
def test_mysql_same_user_concurrent_duplicate_purchase_only_allows_one_success(
    mysql_engine,
    mysql_database_url: str,
):
    bootstrap_database(
        reset=True,
        seed_demo=True,
        database_url=mysql_database_url,
    )
    session_factory = sessionmaker(
        bind=mysql_engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )

    def buy() -> str:
        with session_factory() as session:
            account = _load_account(session, "alice01")
            try:
                ticket = purchase_ticket(
                    session,
                    account,
                    "MU1001",
                    date(2030, 1, 15),
                    1,
                    2,
                    "Y",
                )
                return f"success:{ticket.ticket_no}"
            except Exception as exc:  # pragma: no cover - asserted by prefix
                session.rollback()
                return f"error:{exc}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: buy(), [1, 2]))

    success_count = sum(result.startswith("success:") for result in results)
    error_count = sum(result.startswith("error:") for result in results)

    with session_factory() as session:
        tickets = session.scalars(
            select(TicketSale).where(
                TicketSale.flight_no == "MU1001",
                TicketSale.flight_date == date(2030, 1, 15),
                TicketSale.passenger_id == 1,
                TicketSale.is_active_ticket == 1,
            ),
        ).all()

    assert success_count == 1
    assert error_count == 1
    assert len(tickets) == 1


@pytest.mark.mysql_integration
def test_mysql_refund_releases_waitlist_fifo(mysql_session: Session):
    buyer = _load_account(mysql_session, "alice01")
    waiter = _load_account(mysql_session, "bob01")

    ticket = purchase_ticket(
        mysql_session,
        buyer,
        "MU1001",
        date(2030, 1, 15),
        1,
        2,
        "Y",
    )
    confirm_payment(mysql_session, buyer, ticket.payment_id, "ALIPAY", "mysql-pay-001")
    waitlist = create_waitlist(
        mysql_session,
        waiter,
        "MU1001",
        date(2030, 1, 15),
        1,
        2,
        "Y",
    )

    refund_ticket(mysql_session, ticket, buyer)
    mysql_session.commit()
    mysql_session.refresh(waitlist)

    assert waitlist.status == "RELEASED"
    assert waitlist.released_at is not None
    assert waitlist.linked_ticket_no is not None
    assert waitlist.offer_expires_at is not None

    inventories = mysql_session.scalars(
        select(ScheduleInventory).where(
            ScheduleInventory.flight_no == "MU1001",
            ScheduleInventory.flight_date == date(2030, 1, 15),
        ),
    ).all()
    assert all(inventory.y_seats_left == 0 for inventory in inventories)
