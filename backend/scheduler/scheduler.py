import datetime
from core.models import Schedule, ScheduledJob
from core.calendar_model import next_shift_start, sim_minutes_to_datetime, datetime_to_sim_minutes

def build_schedule(factory_model, orders, rule_fn, db_session=None) -> Schedule:
    """
    Main scheduler orchestrator that assigns jobs to machines and determines execution sequence
    using a dispatching rule function.
    """
    if not orders:
        return Schedule(
            jobs=[],
            makespan=0.0,
            algorithm_used=rule_fn.__name__ if hasattr(rule_fn, "__name__") else "custom",
            generated_at=datetime.datetime.now(),
            factory_health_score=0.0
        )
        
    # Reference start date of schedule
    ref_date = min(o.release_date for o in orders)
    if isinstance(ref_date, datetime.date) and not isinstance(ref_date, datetime.datetime):
        ref_date = datetime.datetime.combine(ref_date, datetime.time(8, 0))
        
    # Attach product objects and reference date to order instances temporarily for priority rules
    for order in orders:
        order.product = next(p for p in factory_model.products if p.id == order.product_id)
        order.reference_date = ref_date

    # Track scheduler state
    job_op_idx = {o.id: 0 for o in orders}
    job_next_avail = {o.id: datetime_to_sim_minutes(o.release_date, ref_date) for o in orders}
    
    machine_avail = {m.id: 0.0 for m in factory_model.machines}
    machine_runtime = {m.id: 0.0 for m in factory_model.machines}
    machine_last_op = {m.id: None for m in factory_model.machines}
    
    scheduled_jobs = []

    while True:
        # 1. Group incomplete jobs by their next machine
        queues = {m.id: [] for m in factory_model.machines}
        active_jobs = False
        
        for order in orders:
            idx = job_op_idx[order.id]
            if idx < len(order.product.routing):
                active_jobs = True
                op = order.product.routing[idx]
                # Find matching machine supporting the operation code
                machine = next((m for m in factory_model.machines if op.code in m.operation_types), None)
                if machine:
                    queues[machine.id].append(order)
                    
        if not active_jobs:
            break
            
        # Filter active queues
        active_queues = {m_id: q for m_id, q in queues.items() if q}
        if not active_queues:
            break
            
        # Select the machine that has the earliest decision time
        best_m_id = min(active_queues.keys(), key=lambda m_id: machine_avail[m_id])
        m_obj = next(m for m in factory_model.machines if m.id == best_m_id)
        
        dec_time = machine_avail[best_m_id]
        
        # Sort queue according to dispatching rule function
        sorted_q = sorted(active_queues[best_m_id], key=lambda o: rule_fn(o, m_obj, dec_time))
        selected_order = sorted_q[0]
        
        # Schedule the operation
        idx = job_op_idx[selected_order.id]
        op = selected_order.product.routing[idx]
        
        is_partial_resume = (idx == 0 and selected_order.status == 'in_progress')
        start_time = max(machine_avail[best_m_id], job_next_avail[selected_order.id])
        
        # Adjust start time for working shift calendar
        if not is_partial_resume:
            start_dt = sim_minutes_to_datetime(start_time, ref_date)
            adjusted_dt = next_shift_start(start_dt, m_obj, factory_model.id, db_session)
            start_time = datetime_to_sim_minutes(adjusted_dt, ref_date)
            
            setup_time = m_obj.setup_times.get(op.code, 0.0) if machine_last_op[best_m_id] != op.code else 0.0
            
            runtime_hours = machine_runtime[best_m_id] / 60.0
            base_cycle = m_obj.cycle_times.get(op.code, 0.0)
            degraded_cycle = base_cycle * (1 + m_obj.degradation_factor * runtime_hours / 100.0)
            processing_time = degraded_cycle * selected_order.quantity
        else:
            setup_time = 0.0
            processing_time = selected_order.remaining_time_minutes
            
        end_time = start_time + setup_time + processing_time
        
        scheduled_jobs.append(ScheduledJob(
            order_id=selected_order.id,
            operation_code=op.code,
            machine_id=best_m_id,
            start_time=start_time,
            end_time=end_time,
            setup_time=setup_time
        ))
        
        # Update trackers
        machine_avail[best_m_id] = end_time
        machine_runtime[best_m_id] += processing_time
        machine_last_op[best_m_id] = op.code
        
        job_next_avail[selected_order.id] = end_time
        job_op_idx[selected_order.id] += 1
        
    makespan = max(job_next_avail.values()) if job_next_avail else 0.0
    
    rule_name = rule_fn.__name__ if hasattr(rule_fn, "__name__") else "custom"
    
    return Schedule(
        jobs=scheduled_jobs,
        makespan=makespan,
        algorithm_used=rule_name,
        generated_at=ref_date,
        factory_health_score=0.0
    )
