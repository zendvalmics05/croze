import datetime
import random
import simpy
from core.calendar_model import next_shift_start, sim_minutes_to_datetime, datetime_to_sim_minutes, is_working_day, get_shifts_for_day
from core.models import SimulationResult, MachineStats, JobStats, FeasibilityReport

def wait_until_working(env, machine, calendar, factory_id, db_session):
    """
    A SimPy generator that computes the gap between env.now and the next working minute
    for the given machine. If there is a gap, it yields a timeout event.
    """
    reference_date = getattr(env, "reference_date", datetime.datetime(2025, 1, 1, 8, 0))
    
    current_dt = sim_minutes_to_datetime(env.now, reference_date)
    next_dt = next_shift_start(current_dt, machine, factory_id, db_session)
    next_min = datetime_to_sim_minutes(next_dt, reference_date)
    
    gap = next_min - env.now
    if gap > 0:
        yield env.timeout(gap)

def job_process(env, order, product, schedule, factory_model, calendar, machine_resources, event_log):
    """
    A SimPy process representing a job moving through its routing operations.
    Supports resuming in-progress jobs for mid-day rescheduling.
    """
    factory_id = factory_model.id
    db_session = getattr(env, "db_session", None)
    reference_date = getattr(env, "reference_date", datetime.datetime(2025, 1, 1, 8, 0))
    
    # 0. Wait until the order release date
    release_time = datetime_to_sim_minutes(order.release_date, reference_date)
    if release_time > env.now:
        yield env.timeout(release_time - env.now)
    
    is_first_op = True
    for operation in product.routing:
        # Find the ScheduledJob to determine assigned machine
        scheduled_job = next(
            (sj for sj in schedule.jobs if sj.order_id == order.id and sj.operation_code == operation.code),
            None
        )
        if not scheduled_job:
            continue
            
        machine_id = scheduled_job.machine_id
        machine = next((m for m in factory_model.machines if m.id == machine_id), None)
        if not machine:
            continue
            
        machine_resource = machine_resources[machine_id]
        is_partial_resume = (is_first_op and order.status == 'in_progress')
        
        while True:
            # 1. Wait until working hours (skipped if partial resume on first attempt)
            if not is_partial_resume:
                yield from wait_until_working(env, machine, calendar, factory_id, db_session)
            
            # 2. Log QUEUE_ENTER event
            event_log.append(("QUEUE_ENTER", order.id, operation.code, machine.id, env.now))
            
            # 3. Request machine resource
            req = machine_resource.request()
            yield req
            
            try:
                # 4. Log MACHINE_START event
                event_log.append(("MACHINE_START", order.id, operation.code, machine.id, env.now))
                
                # 5. Check if setup is needed (skipped if partial resume)
                if not is_partial_resume:
                    setup_time = machine.setup_times.get(operation.code, 0.0)
                    if setup_time > 0 and machine_resource.last_operation != operation.code:
                        yield env.timeout(setup_time)
                        event_log.append(("SETUP_COMPLETE", order.id, operation.code, machine.id, env.now))
                
                # 6. Compute processing time (degraded or remaining time)
                if is_partial_resume:
                    processing_time = order.remaining_time_minutes
                else:
                    runtime_hours = machine_resource.total_runtime / 60.0
                    base_cycle_time = machine.cycle_times.get(operation.code, 0.0)
                    degraded_cycle_time = base_cycle_time * (1 + machine.degradation_factor * runtime_hours / 100.0)
                    processing_time = degraded_cycle_time * order.quantity
                
                # 7. Processing timeout
                yield env.timeout(processing_time)
                
                # 8. Update machine runtime and last operation
                machine_resource.total_runtime += processing_time
                machine_resource.last_operation = operation.code
                
                # 9. Log OPERATION_COMPLETE
                event_log.append(("OPERATION_COMPLETE", order.id, operation.code, machine.id, env.now))
                break
                
            except simpy.Interrupt:
                # Interrupted by machine failure, operation will restart from scratch after repair
                # If we were in a partial resume state, it is now cancelled since the process was interrupted
                is_partial_resume = False
            finally:
                machine_resource.release(req)
                
        is_first_op = False
                
    # After all operations complete
    event_log.append(("JOB_COMPLETE", order.id, None, None, env.now))

def machine_failure_process(env, machine, machine_resource, event_log):
    """
    A SimPy process running concurrently that models machine failures and repairs.
    """
    if machine.failure_rate == 0:
        return
        
    while True:
        # Time to next failure in minutes (failure_rate is in hours)
        time_to_failure = random.expovariate(1.0 / (machine.failure_rate * 60.0))
        yield env.timeout(time_to_failure)
        
        # Interrupted active job if any
        if machine_resource.users:
            active_process = machine_resource.users[0]
            active_process.interrupt("Machine failure!")
            
        # Log MACHINE_FAILURE
        event_log.append(("MACHINE_FAILURE", None, None, machine.id, env.now))
        
        # Time to repair in minutes (repair_time is in hours)
        repair_time = random.expovariate(1.0 / (machine.repair_time * 60.0))
        yield env.timeout(repair_time)
        
        # Log MACHINE_REPAIRED
        event_log.append(("MACHINE_REPAIRED", None, None, machine.id, env.now))

def process_event_log(event_log, factory_model, orders, simulation_end_time, reference_date) -> SimulationResult:
    """
    Processes the simulation event log to compute machine and job statistics.
    """
    # 1. Initialize machine statistics tracking
    state_start_time = {m.id: 0.0 for m in factory_model.machines}
    current_state = {m.id: "IDLE" for m in factory_model.machines}
    last_operation = {m.id: None for m in factory_model.machines}
    
    busy_time = {m.id: 0.0 for m in factory_model.machines}
    setup_time = {m.id: 0.0 for m in factory_model.machines}
    idle_time = {m.id: 0.0 for m in factory_model.machines}
    failure_time = {m.id: 0.0 for m in factory_model.machines}
    
    queue_size = {m.id: 0 for m in factory_model.machines}
    queue_area = {m.id: 0.0 for m in factory_model.machines}
    last_queue_change = {m.id: 0.0 for m in factory_model.machines}
    max_queue = {m.id: 0 for m in factory_model.machines}
    jobs_processed = {m.id: 0 for m in factory_model.machines}

    # 2. Initialize job statistics tracking
    start_time = {o.id: None for o in orders}
    end_time = {o.id: None for o in orders}
    job_processing_time = {o.id: 0.0 for o in orders}
    job_setup_time = {o.id: 0.0 for o in orders}
    
    # Auxiliary trackers to compute exact setup/processing times per operation
    op_setup_start = {}     # (job_id, op_code) -> float
    op_processing_start = {} # (job_id, op_code) -> float

    # Sort events chronologically
    sorted_events = sorted(event_log, key=lambda x: x[4])

    for event_type, job_id, op_code, machine_id, timestamp in sorted_events:
        # Update queue tracking for machines
        if machine_id:
            duration = timestamp - last_queue_change[machine_id]
            queue_area[machine_id] += queue_size[machine_id] * duration
            last_queue_change[machine_id] = timestamp
            
            if event_type == "QUEUE_ENTER":
                queue_size[machine_id] += 1
                if queue_size[machine_id] > max_queue[machine_id]:
                    max_queue[machine_id] = queue_size[machine_id]
            elif event_type == "MACHINE_START":
                queue_size[machine_id] = max(0, queue_size[machine_id] - 1)

            # Update machine state times
            delta = timestamp - state_start_time[machine_id]
            curr = current_state[machine_id]
            if curr == "IDLE":
                idle_time[machine_id] += delta
            elif curr == "SETUP":
                setup_time[machine_id] += delta
            elif curr == "BUSY":
                busy_time[machine_id] += delta
            elif curr == "FAILED":
                failure_time[machine_id] += delta
                
            state_start_time[machine_id] = timestamp

            # Transition machine state
            if event_type == "MACHINE_START":
                m_obj = next(m for m in factory_model.machines if m.id == machine_id)
                s_time = m_obj.setup_times.get(op_code, 0.0)
                if s_time > 0 and last_operation[machine_id] != op_code:
                    current_state[machine_id] = "SETUP"
                    op_setup_start[(job_id, op_code)] = timestamp
                else:
                    current_state[machine_id] = "BUSY"
                    op_processing_start[(job_id, op_code)] = timestamp
            elif event_type == "SETUP_COMPLETE":
                current_state[machine_id] = "BUSY"
                op_processing_start[(job_id, op_code)] = timestamp
                if (job_id, op_code) in op_setup_start:
                    job_setup_time[job_id] += timestamp - op_setup_start[(job_id, op_code)]
            elif event_type == "OPERATION_COMPLETE":
                current_state[machine_id] = "IDLE"
                last_operation[machine_id] = op_code
                jobs_processed[machine_id] += 1
                if (job_id, op_code) in op_processing_start:
                    job_processing_time[job_id] += timestamp - op_processing_start[(job_id, op_code)]
            elif event_type == "MACHINE_FAILURE":
                current_state[machine_id] = "FAILED"
            elif event_type == "MACHINE_REPAIRED":
                current_state[machine_id] = "IDLE"

        # Update Job lifecycle events
        if job_id:
            if event_type == "QUEUE_ENTER" and start_time[job_id] is None:
                start_time[job_id] = timestamp
            elif event_type == "JOB_COMPLETE":
                end_time[job_id] = timestamp

    # Flush remaining time at simulation end
    for m_id in state_start_time:
        delta = simulation_end_time - state_start_time[m_id]
        curr = current_state[m_id]
        if curr == "IDLE":
            idle_time[m_id] += delta
        elif curr == "SETUP":
            setup_time[m_id] += delta
        elif curr == "BUSY":
            busy_time[m_id] += delta
        elif curr == "FAILED":
            failure_time[m_id] += delta
            
        duration = simulation_end_time - last_queue_change[m_id]
        queue_area[m_id] += queue_size[m_id] * duration

    # Compile MachineStats
    machine_stats = {}
    for m in factory_model.machines:
        m_id = m.id
        avg_queue = queue_area[m_id] / simulation_end_time if simulation_end_time > 0 else 0.0
        util = (busy_time[m_id] + setup_time[m_id]) / simulation_end_time if simulation_end_time > 0 else 0.0
        
        machine_stats[m_id] = MachineStats(
            machine_id=m_id,
            total_busy_time=busy_time[m_id],
            total_setup_time=setup_time[m_id],
            total_idle_time=idle_time[m_id],
            total_failure_time=failure_time[m_id],
            utilisation=util,
            average_queue_length=avg_queue,
            max_queue_length=max_queue[m_id],
            jobs_processed=jobs_processed[m_id]
        )

    # Compile JobStats
    job_stats = {}
    total_tardiness = 0.0
    on_time_count = 0
    
    for o in orders:
        j_id = o.id
        t_start = start_time[j_id] if start_time[j_id] is not None else 0.0
        t_end = end_time[j_id] if end_time[j_id] is not None else simulation_end_time
        
        total_job_time = t_end - t_start
        wait_t = max(0.0, total_job_time - job_processing_time[j_id] - job_setup_time[j_id])
        
        # Determine due date comparison
        completion_dt = sim_minutes_to_datetime(t_end, reference_date)
        on_time = completion_dt <= o.due_date
        tardiness = max(0.0, (completion_dt - o.due_date).total_seconds() / 60.0)
        
        if on_time:
            on_time_count += 1
        total_tardiness += tardiness
        
        job_stats[j_id] = JobStats(
            job_id=j_id,
            total_time=total_job_time,
            total_processing_time=job_processing_time[j_id],
            total_wait_time=wait_t,
            total_setup_time=job_setup_time[j_id],
            on_time=on_time,
            tardiness=tardiness
        )

    on_time_rate = on_time_count / len(orders) if orders else 1.0

    return SimulationResult(
        machine_stats=machine_stats,
        job_stats=job_stats,
        makespan=simulation_end_time,
        event_log=event_log,
        simulation_duration=simulation_end_time,
        total_tardiness=total_tardiness,
        on_time_rate=on_time_rate
    )

def run_simulation(factory_model, schedule, orders, calendar, factory_id, db_session) -> SimulationResult:
    """
    Orchestrates the entire SimPy simulation run.
    """
    env = simpy.Environment()
    env.reference_date = getattr(schedule, "generated_at", None) or datetime.datetime.now()
    env.db_session = db_session
    
    machine_resources = {}
    for m in factory_model.machines:
        res = simpy.Resource(env, capacity=1)
        res.last_operation = None
        res.total_runtime = 0.0
        machine_resources[m.id] = res
        
    event_log = []
    
    for m in factory_model.machines:
        env.process(machine_failure_process(env, m, machine_resources[m.id], event_log))
        
    for order in orders:
        product = next((p for p in factory_model.products if p.id == order.product_id), None)
        if not product:
            continue
        env.process(job_process(
            env=env,
            order=order,
            product=product,
            schedule=schedule,
            factory_model=factory_model,
            calendar=calendar,
            machine_resources=machine_resources,
            event_log=event_log
        ))
        
    env.run()
    
    return process_event_log(
        event_log=event_log,
        factory_model=factory_model,
        orders=orders,
        simulation_end_time=env.now,
        reference_date=env.reference_date
    )

def check_feasibility(factory_model, orders, calendar, factory_id, db_session) -> FeasibilityReport:
    """
    Pre-run check to verify if the shop floor has sufficient machine-hour capacity
    to process the total volume of orders before their due dates.
    """
    if not orders:
        return FeasibilityReport(is_feasible=True, infeasible_machines=[], at_risk_orders=[])
        
    start_dt = min(o.release_date for o in orders)
    if isinstance(start_dt, datetime.date) and not isinstance(start_dt, datetime.datetime):
        start_dt = datetime.datetime.combine(start_dt, datetime.time(0, 0))
        
    latest_due = max(o.due_date for o in orders)
    if isinstance(latest_due, datetime.date) and not isinstance(latest_due, datetime.datetime):
        latest_due = datetime.datetime.combine(latest_due, datetime.time(23, 59, 59))
        
    available_hours = {}
    for machine in factory_model.machines:
        tot_avail_min = 0.0
        curr_date = start_dt.date()
        end_date = latest_due.date()
        
        while curr_date <= end_date:
            if is_working_day(curr_date, factory_id, db_session):
                shifts = get_shifts_for_day(curr_date, machine, factory_id, db_session)
                shift_hours = getattr(machine, "shift_hours", 8.0)
                tot_avail_min += shifts * shift_hours * 60.0
            curr_date += datetime.timedelta(days=1)
            
        available_hours[machine.id] = tot_avail_min / 60.0
        
    required_hours = {m.id: 0.0 for m in factory_model.machines}
    for order in orders:
        product = next((p for p in factory_model.products if p.id == order.product_id), None)
        if not product:
            continue
        for operation in product.routing:
            machine = next((m for m in factory_model.machines if operation.code in m.operation_types), None)
            if machine:
                base_cycle = machine.cycle_times.get(operation.code, 0.0)
                setup = machine.setup_times.get(operation.code, 0.0)
                req_min = base_cycle * order.quantity + setup
                required_hours[machine.id] += req_min / 60.0
                
    infeasible_machines = []
    at_risk_orders = set()
    
    for machine in factory_model.machines:
        req = required_hours[machine.id]
        avail = available_hours[machine.id]
        if req > avail:
            shortfall = req - avail
            infeasible_machines.append({
                "machine_name": machine.name,
                "machine_id": machine.id,
                "hours_required": round(req, 1),
                "hours_available": round(avail, 1),
                "shortfall": round(shortfall, 1)
            })
            
            for order in orders:
                product = next((p for p in factory_model.products if p.id == order.product_id), None)
                if not product:
                    continue
                if any(operation.code in machine.operation_types for operation in product.routing):
                    at_risk_orders.add(order.id)
                    
    is_feasible = len(infeasible_machines) == 0
    return FeasibilityReport(
        is_feasible=is_feasible,
        infeasible_machines=infeasible_machines,
        at_risk_orders=sorted(list(at_risk_orders))
    )
