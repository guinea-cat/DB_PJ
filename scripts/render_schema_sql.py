from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database import Base
from app.models import *  # noqa: F401,F403


def main() -> None:
    dialect = mysql.dialect()
    output = [
        "-- Auto-generated from SQLAlchemy metadata.",
        "CREATE DATABASE IF NOT EXISTS FlightTicketingDB DEFAULT CHARSET utf8mb4;",
        "USE FlightTicketingDB;",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        output.append(str(CreateTable(table).compile(dialect=dialect)).rstrip() + ";")
        output.append("")
        for index in table.indexes:
            output.append(str(CreateIndex(index).compile(dialect=dialect)).rstrip() + ";")
            output.append("")

    target = Path("flight_ticketing_db.sql")
    target.write_text("\n".join(output), encoding="utf-8")
    print(f"Wrote schema SQL to {target}")


if __name__ == "__main__":
    main()
