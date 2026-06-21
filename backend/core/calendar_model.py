import datetime
from typing import Union
from db.models import Factory, WorkingCalendar
from core.calendar_data import NATIONAL_HOLIDAYS, STATE_HOLIDAYS

def is_working_day(date_val: Union[datetime.date, datetime.datetime], factory_id: str, db_session) -> bool:
    """
    Returns False for national holidays, state holidays (based on factory's state),
    and manually added override days in the database.
    Returns False for Sundays, and True otherwise (including Saturdays by default).
    """
    if isinstance(date_val, datetime.datetime):
        date_obj = date_val.date()
    else:
        date_obj = date_val

    # 1. Check manually added override days in working_calendar table
    if db_session:
        override = db_session.query(WorkingCalendar).filter(
            WorkingCalendar.factory_id == factory_id,
            WorkingCalendar.date == date_obj
        ).first()
        if override is not None:
            return override.is_working

    year_str = str(date_obj.year)
    mm_dd_str = date_obj.strftime("%m-%d")

    # 2. Check national holidays
    if year_str in NATIONAL_HOLIDAYS:
        for hol_date, hol_name in NATIONAL_HOLIDAYS[year_str]:
            if hol_date == mm_dd_str:
                return False

    # Get factory state to check state holidays
    state = "Maharashtra"  # Default state
    if db_session:
        factory = db_session.query(Factory).filter(Factory.id == factory_id).first()
        if factory and factory.json_definition:
            try:
                import json
                data = json.loads(factory.json_definition)
                # Check directly or nested in calendar
                state = data.get("state") or data.get("calendar", {}).get("state") or "Maharashtra"
            except Exception:
                pass

    # 3. Check state holidays
    if state in STATE_HOLIDAYS and year_str in STATE_HOLIDAYS[state]:
        for hol_date, hol_name in STATE_HOLIDAYS[state][year_str]:
            if hol_date == mm_dd_str:
                return False

    # 4. Standard weekdays (Sunday = False, others = True)
    if date_obj.weekday() == 6:  # Sunday is 6 (Monday=0)
        return False

    return True

def get_shifts_for_day(date_val: Union[datetime.date, datetime.datetime], machine, factory_id: str, db_session) -> int:
    """
    Returns the machine's shifts_per_day unless overridden in the working_calendar table.
    """
    if isinstance(date_val, datetime.datetime):
        date_obj = date_val.date()
    else:
        date_obj = date_val

    # Check shift overrides in database
    if db_session:
        override = db_session.query(WorkingCalendar).filter(
            WorkingCalendar.factory_id == factory_id,
            WorkingCalendar.date == date_obj
        ).first()
        if override is not None and override.shift_override is not None:
            return override.shift_override

    # Fallback to machine properties
    if hasattr(machine, "shifts_per_day"):
        return machine.shifts_per_day
    elif isinstance(machine, dict):
        return machine.get("shifts_per_day", 1)
    return 1

def next_shift_start(current_datetime: datetime.datetime, machine, factory_id: str, db_session) -> datetime.datetime:
    """
    Given a datetime, returns the next datetime when the machine starts a working shift.
    Used by the simulation to skip over non-working times.
    """
    dt = current_datetime
    while True:
        current_date = dt.date()
        is_work = is_working_day(current_date, factory_id, db_session)
        if is_work:
            shifts = get_shifts_for_day(current_date, machine, factory_id, db_session)
            shift_hours = getattr(machine, "shift_hours", 8.0) if hasattr(machine, "shift_hours") else 8.0
            
            day_start = datetime.datetime.combine(current_date, datetime.time(8, 0))
            day_end = day_start + datetime.timedelta(hours=shifts * shift_hours)
            
            if dt < day_start:
                return day_start
            elif dt < day_end:
                return dt
        
        # If we are past shift hours or on a non-working day, advance to the next day
        next_day = current_date + datetime.timedelta(days=1)
        dt = datetime.datetime.combine(next_day, datetime.time(0, 0))

def sim_minutes_to_datetime(minutes_from_start: float, reference_date: Union[datetime.date, datetime.datetime]) -> datetime.datetime:
    """
    Converts simulation clock minutes to a real datetime.
    """
    if isinstance(reference_date, datetime.date) and not isinstance(reference_date, datetime.datetime):
        ref_dt = datetime.datetime.combine(reference_date, datetime.time(0, 0))
    else:
        ref_dt = reference_date
    return ref_dt + datetime.timedelta(minutes=minutes_from_start)

def datetime_to_sim_minutes(dt: datetime.datetime, reference_date: Union[datetime.date, datetime.datetime]) -> float:
    """
    Converts a real datetime to simulation clock minutes from reference start.
    """
    if isinstance(reference_date, datetime.date) and not isinstance(reference_date, datetime.datetime):
        ref_dt = datetime.datetime.combine(reference_date, datetime.time(0, 0))
    else:
        ref_dt = reference_date
    delta = dt - ref_dt
    return delta.total_seconds() / 60.0
