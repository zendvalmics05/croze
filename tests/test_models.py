from datetime import datetime
from backend.core.models import (
    Machine, Operation, Product, Order, ScheduledJob,
    Schedule, MachineStats, JobStats, SimulationResult,
    FactoryModel, WorkingCalendar
)

def test_instantiate_models():
    # 1. Machine
    m = Machine(
        id="M1", name="Machine 1", operation_types=["OP1"],
        cycle_times={"OP1": 10.0}, setup_times={"OP1": 5.0},
        shift_hours=8.0, shifts_per_day=1, failure_rate=0.0,
        repair_time=0.0, degradation_factor=0.0
    )
    assert m.id == "M1"

    # 2. Operation
    op = Operation(code="OP1", machine_type="type1", sequence_index=0, parallel_capable=False)
    assert op.code == "OP1"

    # 3. Product
    p = Product(id="P1", name="Product 1", routing=[op], batch_size=1)
    assert p.id == "P1"

    # 4. Order
    o = Order(
        id="O1", product_id="P1", quantity=10, due_date=datetime.now(),
        priority=1, release_date=datetime.now(), status="pending"
    )
    assert o.id == "O1"

    # 5. ScheduledJob
    sj = ScheduledJob(order_id="O1", operation_code="OP1", machine_id="M1", start_time=0.0, end_time=100.0, setup_time=5.0)
    assert sj.order_id == "O1"

    # 6. Schedule
    s = Schedule(jobs=[sj], makespan=105.0, algorithm_used="test", generated_at=datetime.now(), factory_health_score=100.0)
    assert s.makespan == 105.0

    # 7. MachineStats
    ms = MachineStats(machine_id="M1", total_busy_time=100.0, total_setup_time=5.0, total_idle_time=0.0, total_failure_time=0.0, utilisation=0.9, average_queue_length=0.0, max_queue_length=0, jobs_processed=1)
    assert ms.machine_id == "M1"

    # 8. JobStats
    js = JobStats(job_id="O1", total_time=105.0, total_processing_time=100.0, total_wait_time=0.0, total_setup_time=5.0, on_time=True, tardiness=0.0)
    assert js.job_id == "O1"

    # 9. SimulationResult
    sr = SimulationResult(machine_stats={"M1": ms}, job_stats={"O1": js}, makespan=105.0, event_log=[], simulation_duration=105.0, total_tardiness=0.0, on_time_rate=1.0)
    assert sr.makespan == 105.0

    # 10. FactoryModel
    fm = FactoryModel(id="F1", name="Factory 1", machines=[m], products=[p], routing_graph={"M1": []})
    assert fm.id == "F1"

    # 11. WorkingCalendar
    wc = WorkingCalendar(factory_id="F1", state="Maharashtra", overrides={}, shift_overrides={})
    assert wc.factory_id == "F1"
