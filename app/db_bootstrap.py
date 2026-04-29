from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine
from app.seed import seed_test_data

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "backend" / "alembic.ini"


def _build_env(database_url: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if database_url:
        env["DATABASE_URL"] = database_url
    return env


def run_alembic(*args: str, database_url: str | None = None) -> None:
    command = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_INI),
        *args,
    ]
    subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=_build_env(database_url),
        check=True,
    )


def reset_schema(database_url: str | None = None) -> None:
    target_engine = engine if database_url is None else create_engine(database_url, future=True)
    try:
        Base.metadata.drop_all(bind=target_engine)
        with target_engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        if database_url is not None:
            target_engine.dispose()


def seed_demo_data(database_url: str | None = None) -> None:
    target_engine = None
    if database_url is None:
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    else:
        target_engine = create_engine(database_url, future=True, pool_pre_ping=True)
        session_factory = sessionmaker(
            bind=target_engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
    try:
        with session_factory() as session:
            seed_test_data(session)
    finally:
        if target_engine is not None:
            target_engine.dispose()


def reseed_demo_data(database_url: str | None = None) -> None:
    reset_schema(database_url)
    run_alembic("upgrade", "head", database_url=database_url)
    seed_demo_data(database_url)


def bootstrap_database(
    *,
    reset: bool = False,
    seed_demo: bool = True,
    reseed_demo: bool = False,
    database_url: str | None = None,
) -> None:
    if reseed_demo:
        reseed_demo_data(database_url)
        return
    if reset:
        reset_schema(database_url)
    run_alembic("upgrade", "head", database_url=database_url)
    if seed_demo:
        seed_demo_data(database_url)
