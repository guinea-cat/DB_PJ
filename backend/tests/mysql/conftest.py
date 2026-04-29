from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.db_bootstrap import bootstrap_database


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "mysql_integration: requires a live MySQL database configured via TEST_MYSQL_DATABASE_URL",
    )


@pytest.fixture(scope="session")
def mysql_database_url() -> str:
    database_url = os.getenv("TEST_MYSQL_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_MYSQL_DATABASE_URL is not configured.")
    return database_url


@pytest.fixture(scope="session")
def mysql_engine(mysql_database_url: str):
    engine = create_engine(mysql_database_url, future=True, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def mysql_session(mysql_engine, mysql_database_url: str) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(
        bind=mysql_engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )
    bootstrap_database(
        reset=True,
        seed_demo=True,
        database_url=mysql_database_url,
    )
    with testing_session_local() as session:
        yield session
