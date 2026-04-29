from __future__ import annotations

from pathlib import Path
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


def main() -> None:
    deadline = time.time() + 120
    last_error: Exception | None = None
    while time.time() < deadline:
        engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database is ready.")
            return
        except SQLAlchemyError as exc:
            last_error = exc
            time.sleep(2)
        finally:
            engine.dispose()
    raise SystemExit(f"Database did not become ready in time: {last_error}")


if __name__ == "__main__":
    main()
