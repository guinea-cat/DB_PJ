from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db_bootstrap import bootstrap_database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Alembic migrations and optionally load demo seed data.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing tables before re-running migrations.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip loading demo seed data after migrations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bootstrap_database(reset=args.reset, seed_demo=not args.no_seed)
    print("Database bootstrap completed.")


if __name__ == "__main__":
    main()
