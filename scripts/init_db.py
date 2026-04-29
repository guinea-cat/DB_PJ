from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db_bootstrap import bootstrap_database


def main() -> None:
    bootstrap_database(reset=True, seed_demo=True)
    print("Database initialized and demo seed data loaded.")


if __name__ == "__main__":
    main()
