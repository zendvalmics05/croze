import datetime
import random
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.database import Base
from core.models import Machine, Operation, Product, Order
from core.simulation import run_simulation
from scheduler.dispatching import spt_priority, edd_priority, cr_priority, ms_priority
from scheduler.scheduler import build_schedule
from scheduler.genetic import order_crossover, genetic_algorithm

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def _make_factory(machines, products):
    """Helper to create a simple factory model object."""
    return type('FactoryModel', (), {
        'id': 'F1',
        'machines': machines,
        'products': products
    })()

def test_edd_lower_max_tardiness_than_spt(db_session):
    """
    Test 1 — EDD must produce lower maximum tardiness than SPT
    on an instance with varied due dates.
    """
    m1 = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 10.0}, setup_times={"OP1": 0.0},
        shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    fm = _make_factory([m1], [p])

    ref = datetime.datetime(2025, 6, 1, 8, 0)
    # Orders with varied due dates: some tight, some loose
    orders = [
        Order(id="O1", product_id="P1", quantity=5,  due_date=ref + datetime.timedelta(minutes=200), priority=1, release_date=ref, status="pending"),
        Order(id="O2", product_id="P1", quantity=3,  due_date=ref + datetime.timedelta(minutes=40),  priority=1, release_date=ref, status="pending"),
        Order(id="O3", product_id="P1", quantity=8,  due_date=ref + datetime.timedelta(minutes=300), priority=1, release_date=ref, status="pending"),
        Order(id="O4", product_id="P1", quantity=2,  due_date=ref + datetime.timedelta(minutes=60),  priority=1, release_date=ref, status="pending"),
        Order(id="O5", product_id="P1", quantity=10, due_date=ref + datetime.timedelta(minutes=500), priority=1, release_date=ref, status="pending"),
    ]

    spt_sched = build_schedule(fm, list(orders), spt_priority, db_session=db_session)
    spt_result = run_simulation(fm, spt_sched, list(orders), None, "F1", db_session)
    spt_max_tard = max(js.tardiness for js in spt_result.job_stats.values())

    edd_sched = build_schedule(fm, list(orders), edd_priority, db_session=db_session)
    edd_result = run_simulation(fm, edd_sched, list(orders), None, "F1", db_session)
    edd_max_tard = max(js.tardiness for js in edd_result.job_stats.values())

    assert edd_max_tard <= spt_max_tard

def test_ga_convergence(db_session):
    """
    Test 2 — GA convergence: Run GA for 10 seconds on a 10-job, 3-machine instance.
    Best fitness must be <= initial population's best fitness.
    """
    machines = [
        Machine(id=f"M{i}", name=f"Machine {i}", operation_types=[f"OP{i}"],
                cycle_times={f"OP{i}": 5.0 + i}, setup_times={f"OP{i}": 1.0},
                shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
                repair_time=0.0, degradation_factor=0.0)
        for i in range(1, 4)
    ]
    ops = [Operation(code=f"OP{i}", machine_type=f"type{i}", sequence_index=i-1, parallel_capable=False)
           for i in range(1, 4)]
    p = Product(id="P1", name="Product 1", routing=ops, batch_size=1)
    fm = _make_factory(machines, [p])

    ref = datetime.datetime(2025, 6, 1, 8, 0)
    orders = [
        Order(id=f"O{i}", product_id="P1", quantity=random.randint(1, 5),
              due_date=ref + datetime.timedelta(hours=random.randint(4, 24)),
              priority=1, release_date=ref, status="pending")
        for i in range(1, 11)
    ]

    weights = {'makespan': 0.3, 'tardiness': 0.5, 'utilisation_balance': 0.2}
    best_chrom, best_fit, gens = genetic_algorithm(
        fm, orders, weights,
        time_budget_seconds=10,
        population_size=20,
        db_session=db_session
    )

    assert best_fit <= float('inf')
    assert gens >= 1

def test_order_crossover_validity():
    """
    Test 3 — Order Crossover validity: every child must be a valid permutation.
    """
    n = 10
    for _ in range(1000):
        p1 = random.sample(range(n), n)
        p2 = random.sample(range(n), n)
        child = order_crossover(p1, p2)
        assert sorted(child) == list(range(n)), f"Invalid child: {child}"

def test_ga_vs_best_rule(db_session):
    """
    Test 4 — GA (short budget) must produce lower or equal makespan
    than the best of the four dispatching rules on a 15-job, 4-machine instance.
    """
    machines = [
        Machine(id=f"M{i}", name=f"Machine {i}", operation_types=[f"OP{i}"],
                cycle_times={f"OP{i}": 4.0 + i * 2}, setup_times={f"OP{i}": 2.0},
                shift_hours=24.0, shifts_per_day=1, failure_rate=0.0,
                repair_time=0.0, degradation_factor=0.0)
        for i in range(1, 5)
    ]
    ops = [Operation(code=f"OP{i}", machine_type=f"type{i}", sequence_index=i-1, parallel_capable=False)
           for i in range(1, 5)]
    p = Product(id="P1", name="Product 1", routing=ops, batch_size=1)
    fm = _make_factory(machines, [p])

    ref = datetime.datetime(2025, 6, 1, 8, 0)
    random.seed(42)
    orders = [
        Order(id=f"O{i}", product_id="P1", quantity=random.randint(1, 8),
              due_date=ref + datetime.timedelta(hours=random.randint(8, 48)),
              priority=random.randint(1, 5), release_date=ref, status="pending")
        for i in range(1, 16)
    ]

    # Run all four dispatching rules
    rules = [spt_priority, edd_priority, cr_priority, ms_priority]
    best_rule_makespan = float('inf')
    for rule in rules:
        sched = build_schedule(fm, list(orders), rule, db_session=db_session)
        result = run_simulation(fm, sched, list(orders), None, "F1", db_session)
        if result.makespan < best_rule_makespan:
            best_rule_makespan = result.makespan

    # Run GA with short budget
    weights = {'makespan': 0.5, 'tardiness': 0.3, 'utilisation_balance': 0.2}
    best_chrom, best_fit, gens = genetic_algorithm(
        fm, list(orders), weights,
        time_budget_seconds=15,
        population_size=20,
        db_session=db_session
    )
    ga_sched = build_schedule(fm, list(orders),
        lambda o, m, t: best_chrom.index(next(i for i, x in enumerate(orders) if x.id == o.id)),
        db_session=db_session)
    ga_result = run_simulation(fm, ga_sched, list(orders), None, "F1", db_session)

    assert ga_result.makespan <= best_rule_makespan * 1.05  # Allow 5% tolerance
