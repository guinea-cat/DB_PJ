from collections.abc import Generator
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import get_db
from app.db_bootstrap import bootstrap_database
from app.main import app


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    temp_dir = Path("backend/tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    database_file = temp_dir / f"test-app-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_file}"
    bootstrap_database(reset=True, seed_demo=True, database_url=database_url)
    from sqlalchemy import create_engine

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )
    with TestingSessionLocal() as db:
        yield db
    engine.dispose()
    if database_file.exists():
        database_file.unlink()


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
