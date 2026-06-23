import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from db.models import Factory, WorkingCalendar
from core.models import Machine, Operation, Product, Order, ScheduledJob, Schedule
from core.simulation import run_simulation

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_single_machine_single_job(db_session):
    # 1 machine, 10 min/unit, 1 job of 50 units
    m = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 10.0}, setup_times={"OP1": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    
    ref_date = datetime.datetime(2025, 1, 1, 8, 0)
    o = Order(
        id="O1", product_id="P1", quantity=50, due_date=ref_date + datetime.timedelta(days=2),
        priority=1, release_date=ref_date, status="pending"
    )
    
    sj = ScheduledJob(order_id="O1", operation_code="OP1", machine_id="M1", start_time=0.0, end_time=500.0, setup_time=0.0)
    schedule = Schedule(jobs=[sj], makespan=500.0, algorithm_used="test", generated_at=ref_date, factory_health_score=100.0)
    
    fm = FactoryModel = type('FactoryModel', (), {'id': 'F1', 'machines': [m], 'products': [p]})()
    
    res = run_simulation(fm, schedule, [o], None, "F1", db_session)
    
    # Expected completion at exactly 500 minutes
    assert abs(res.makespan - 500.0) < 0.5
    assert res.job_stats["O1"].total_processing_time == 500.0

def test_two_machines_in_series(db_session):
    m1 = Machine(
        id="M1", name="Mach 1", operation_types=["OP1"],
        cycle_times={"OP1": 8.0}, setup_times={"OP1": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    m2 = Machine(
        id="M2", name="Mach 2", operation_types=["OP2"],
        cycle_times={"OP2": 12.0}, setup_times={"OP2": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op1 = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    op2 = Operation(code="OP2", machine_type="type2", sequence_index=1, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op1, op2], batch_size=1)
    
    ref_date = datetime.datetime(2025, 1, 1, 8, 0)
    orders = []
    jobs = []
    
    for i in range(1, 11):
        o_id = f"O{i}"
        orders.append(Order(
            id=o_id, product_id="P1", quantity=1, due_date=ref_date + datetime.timedelta(days=2),
            priority=1, release_date=ref_date, status="pending"
        ))
        
        # M1: start 8*(i-1), end 8*i
        jobs.append(ScheduledJob(order_id=o_id, operation_code="OP1", machine_id="M1", start_time=8.0*(i-1), end_time=8.0*i, setup_time=0.0))
        # M2: start 8 + 12*(i-1), end 8 + 12*i
        jobs.append(ScheduledJob(order_id=o_id, operation_code="OP2", machine_id="M2", start_time=8.0 + 12.0*(i-1), end_time=8.0 + 12.0*i, setup_time=0.0))
        
    schedule = Schedule(jobs=jobs, makespan=128.0, algorithm_used="test", generated_at=ref_date, factory_health_score=100.0)
    fm = type('FactoryModel', (), {'id': 'F1', 'machines': [m1, m2], 'products': [p]})()
    
    res = run_simulation(fm, schedule, orders, None, "F1", db_session)
    
    # Expected makespan: 128 minutes
    assert abs(res.makespan - 128.0) < 0.5

def test_utilisation(db_session):
    m = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 10.0}, setup_times={"OP1": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    
    ref_date = datetime.datetime(2025, 1, 1, 8, 0)
    # Order for 300 minutes of work (30 units * 10 mins)
    o1 = Order(
        id="O1", product_id="P1", quantity=30, due_date=ref_date + datetime.timedelta(days=2),
        priority=1, release_date=ref_date, status="pending"
    )
    # Dummy order scheduled at t=480 to force simulation duration to 480 minutes
    o2 = Order(
        id="O2", product_id="P1", quantity=1, due_date=ref_date + datetime.timedelta(days=2),
        priority=1, release_date=ref_date + datetime.timedelta(minutes=479.9), status="pending"
    )
    
    sj1 = ScheduledJob(order_id="O1", operation_code="OP1", machine_id="M1", start_time=0.0, end_time=300.0, setup_time=0.0)
    sj2 = ScheduledJob(order_id="O2", operation_code="OP1", machine_id="M1", start_time=479.9, end_time=480.0, setup_time=0.0)
    
    schedule = Schedule(jobs=[sj1, sj2], makespan=480.0, algorithm_used="test", generated_at=ref_date, factory_health_score=100.0)
    fm = type('FactoryModel', (), {'id': 'F1', 'machines': [m], 'products': [p]})()
    
    res = run_simulation(fm, schedule, [o1, o2], None, "F1", db_session)
    
    # Utilisation should be 300 / 480 = 62.5%
    util = res.machine_stats["M1"].utilisation
    assert abs(util - 0.625) < 0.01

def test_shift_boundary(db_session):
    # Machine runs 8 hours per day (8:00 AM to 4:00 PM)
    m = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 10.0}, setup_times={"OP1": 0.0},
        shift_hours=8.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    
    # 2026-01-27 is a Tuesday (working day)
    ref_date = datetime.datetime(2026, 1, 27, 8, 0)
    # Release at 4:00 PM (end of shift)
    o = Order(
        id="O1", product_id="P1", quantity=1, due_date=ref_date + datetime.timedelta(days=2),
        priority=1, release_date=ref_date + datetime.timedelta(hours=8), status="pending"
    )
    
    # Scheduled starting at 8 hours (480 minutes) from start
    sj = ScheduledJob(order_id="O1", operation_code="OP1", machine_id="M1", start_time=480.0, end_time=490.0, setup_time=0.0)
    schedule = Schedule(jobs=[sj], makespan=490.0, algorithm_used="test", generated_at=ref_date, factory_health_score=100.0)
    fm = type('FactoryModel', (), {'id': 'F1', 'machines': [m], 'products': [p]})()
    
    res = run_simulation(fm, schedule, [o], None, "F1", db_session)
    
    # The job must wait until next morning 8:00 AM.
    # Wednesday 8:00 AM is 1440 minutes from Tuesday 8:00 AM.
    # Processing takes 10 mins, so it should finish at 1450 minutes from start.
    job_stat = res.job_stats["O1"]
    assert abs(res.makespan - 1450.0) < 1.0

def test_partial_schedule(db_session):
    m = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 100.0}, setup_times={"OP1": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    
    ref_date = datetime.datetime(2025, 1, 1, 8, 0)
    # Order is in_progress with remaining_time = 30 mins
    o = Order(
        id="O1", product_id="P1", quantity=1, due_date=ref_date + datetime.timedelta(days=2),
        priority=1, release_date=ref_date, status="in_progress", remaining_time_minutes=30.0
    )
    
    sj = ScheduledJob(order_id="O1", operation_code="OP1", machine_id="M1", start_time=0.0, end_time=30.0, setup_time=0.0)
    schedule = Schedule(jobs=[sj], makespan=30.0, algorithm_used="test", generated_at=ref_date, factory_health_score=100.0)
    fm = type('FactoryModel', (), {'id': 'F1', 'machines': [m], 'products': [p]})()
    
    res = run_simulation(fm, schedule, [o], None, "F1", db_session)
    
    # Expected completion at t=30
    assert abs(res.makespan - 30.0) < 0.5
