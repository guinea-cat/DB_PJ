from pathlib import Path
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import db_bootstrap


def test_bootstrap_database_runs_upgrade_before_demo_seed(monkeypatch):
    calls: list[tuple[str, tuple[str, ...] | None]] = []

    monkeypatch.setattr(
        db_bootstrap,
        "run_alembic",
        lambda *args, **kwargs: calls.append(("alembic", args)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "seed_demo_data",
        lambda *args, **kwargs: calls.append(("seed", None)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "reset_schema",
        lambda *args, **kwargs: calls.append(("reset", None)),
    )

    db_bootstrap.bootstrap_database(reset=False, seed_demo=True)

    assert calls == [
        ("alembic", ("upgrade", "head")),
        ("seed", None),
    ]


def test_bootstrap_database_resets_before_upgrade(monkeypatch):
    calls: list[tuple[str, tuple[str, ...] | None]] = []

    monkeypatch.setattr(
        db_bootstrap,
        "run_alembic",
        lambda *args, **kwargs: calls.append(("alembic", args)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "seed_demo_data",
        lambda *args, **kwargs: calls.append(("seed", None)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "reset_schema",
        lambda *args, **kwargs: calls.append(("reset", None)),
    )

    db_bootstrap.bootstrap_database(reset=True, seed_demo=False)

    assert calls == [
        ("reset", None),
        ("alembic", ("upgrade", "head")),
    ]


def test_bootstrap_database_reseed_demo_uses_forced_reseed(monkeypatch):
    calls: list[tuple[str, tuple[str, ...] | None]] = []

    monkeypatch.setattr(
        db_bootstrap,
        "run_alembic",
        lambda *args, **kwargs: calls.append(("alembic", args)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "seed_demo_data",
        lambda *args, **kwargs: calls.append(("seed", None)),
    )
    monkeypatch.setattr(
        db_bootstrap,
        "reset_schema",
        lambda *args, **kwargs: calls.append(("reset", None)),
    )

    db_bootstrap.bootstrap_database(reseed_demo=True)

    assert calls == [
        ("reset", None),
        ("alembic", ("upgrade", "head")),
        ("seed", None),
    ]


def test_bootstrap_database_reset_recreates_schema_for_sqlite():
    temp_dir = Path("backend/tests/.tmp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    database_file = temp_dir / "bootstrap-reset.db"
    if database_file.exists():
        database_file.unlink()
    database_url = f"sqlite+pysqlite:///{database_file}"

    db_bootstrap.bootstrap_database(
        reset=False,
        seed_demo=True,
        database_url=database_url,
    )
    db_bootstrap.bootstrap_database(
        reset=True,
        seed_demo=True,
        database_url=database_url,
    )

    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            city_count = connection.execute(text("SELECT COUNT(*) FROM city")).scalar_one()
    finally:
        engine.dispose()
        if database_file.exists():
            database_file.unlink()

    assert city_count >= 3
