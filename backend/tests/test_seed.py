from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import func, select

from app.models import Airport, City, DemoDataVersion, FlightSchedule, FlightTemplate, Route
from app.models import Airport, City
from app.seed import seed_test_data


class RecordingSession:
    def __init__(self) -> None:
        self.operations: list[tuple[str, list[type[object]] | None]] = []

    def get(self, _model, _primary_key):
        return None

    def add_all(self, objects):
        materialized = list(objects)
        self.operations.append(
            ("add_all", [type(item) for item in materialized]),
        )

    def add(self, _object):
        self.operations.append(("add", None))

    def flush(self):
        self.operations.append(("flush", None))

    def commit(self):
        self.operations.append(("commit", None))


def test_seed_data_flushes_cities_before_airports():
    session = RecordingSession()

    seed_test_data(session)

    city_batch_index = next(
        index
        for index, operation in enumerate(session.operations)
        if operation[0] == "add_all"
        and operation[1]
        and all(item is City for item in operation[1])
    )
    flush_after_cities_index = next(
        index
        for index, operation in enumerate(session.operations)
        if index > city_batch_index and operation == ("flush", None)
    )
    airport_batch_index = next(
        index
        for index, operation in enumerate(session.operations)
        if operation[0] == "add_all"
        and operation[1]
        and all(item is Airport for item in operation[1])
    )

    assert city_batch_index < flush_after_cities_index < airport_batch_index


def test_seed_data_expands_demo_reference_counts(session):
    city_count = session.scalar(select(func.count()).select_from(City))
    airport_count = session.scalar(select(func.count()).select_from(Airport))
    route_count = session.scalar(select(func.count()).select_from(Route))
    template_count = session.scalar(select(func.count()).select_from(FlightTemplate))
    schedule_count = session.scalar(select(func.count()).select_from(FlightSchedule))

    assert city_count >= 7
    assert airport_count >= 9
    assert route_count >= 8
    assert template_count >= 12
    assert schedule_count >= 20


def test_seed_records_demo_data_version(session):
    version_row = session.get(DemoDataVersion, "demo_seed")

    assert version_row is not None
    assert version_row.version >= 1
