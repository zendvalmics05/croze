import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import Factory, WorkingCalendar
from core.calendar_model import is_working_day, next_shift_start, get_shifts_for_day
from core.models import Machine

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_republic_day_is_not_working(db_session):
    # Jan 26, 2026 is a Monday. Republic Day holiday.
    republic_day = datetime.date(2026, 1, 26)
    assert not is_working_day(republic_day, "F1", db_session)

def test_normal_tuesday_is_working(db_session):
    # Jan 27, 2026 is a Tuesday. Not a holiday.
    tuesday = datetime.date(2026, 1, 27)
    assert is_working_day(tuesday, "F1", db_session)

def test_manual_override_working_day(db_session):
    tuesday = datetime.date(2026, 1, 27)
    # Add manual override to make it non-working
    override = WorkingCalendar(
        id="O1",
        factory_id="F1",
        date=tuesday,
        is_working=False,
        shift_override=None
    )
    db_session.add(override)
    db_session.commit()
    
    assert not is_working_day(tuesday, "F1", db_session)

def test_next_shift_start_during_shift(db_session):
    m = Machine(
        id="M1", name="Mach", operation_types=[], cycle_times={}, setup_times={},
        shift_hours=8.0, shifts_per_day=1, failure_rate=0, repair_time=0, degradation_factor=0
    )
    # Jan 27, 2026 is a Tuesday (working day). Shift starts at 08:00 AM, ends at 04:00 PM.
    # Call at 10:00 AM
    dt = datetime.datetime(2026, 1, 27, 10, 0)
    res = next_shift_start(dt, m, "F1", db_session)
    assert res == dt

def test_next_shift_start_after_shift(db_session):
    m = Machine(
        id="M1", name="Mach", operation_types=[], cycle_times={}, setup_times={},
        shift_hours=8.0, shifts_per_day=1, failure_rate=0, repair_time=0, degradation_factor=0
    )
    # Call at 5:00 PM on Tuesday Jan 27, 2026.
    # Should return Wednesday Jan 28, 2026 at 08:00 AM.
    dt = datetime.datetime(2026, 1, 27, 17, 0)
    res = next_shift_start(dt, m, "F1", db_session)
    assert res == datetime.datetime(2026, 1, 28, 8, 0)
