import datetime
import math

def get_operation_for_machine(order, machine):
    """
    Helper to get the operation for the order's product that matches the machine.
    """
    product = getattr(order, "product", None)
    if not product:
        return None
    for op in product.routing:
        if op.code in machine.operation_types:
            return op
    return None

def spt_priority(order, machine, current_time) -> float:
    """
    Shortest Processing Time (SPT)
    Priority = total remaining processing time for this job on this machine.
    Lower value = higher priority.
    """
    op = get_operation_for_machine(order, machine)
    if op:
        cycle_time = machine.cycle_times.get(op.code, 0.0)
        return cycle_time * order.quantity
    return 0.0

def edd_priority(order, machine, current_time) -> float:
    """
    Earliest Due Date (EDD)
    Priority = due_date as a numeric timestamp.
    Lower value = higher priority.
    """
    return order.due_date.timestamp()

def cr_priority(order, machine, current_time) -> float:
    """
    Critical Ratio (CR)
    CR = time_remaining_to_due_date / total_remaining_processing_time
    Lower value = higher priority.
    If remaining processing time is 0: return -inf.
    """
    # Calculate remaining processing time on this machine
    op = get_operation_for_machine(order, machine)
    total_remaining_processing_time = 0.0
    if op:
        cycle_time = machine.cycle_times.get(op.code, 0.0)
        total_remaining_processing_time = cycle_time * order.quantity
        
    if total_remaining_processing_time <= 0:
        return -math.inf
        
    # Calculate time remaining to due date (in minutes)
    if isinstance(current_time, (int, float)):
        # If current_time is numeric, assume it is simulation minutes
        # We need order's reference_date (or default) to convert due_date to simulation minutes
        ref_date = getattr(order, "reference_date", None)
        if ref_date:
            due_minutes = (order.due_date - ref_date).total_seconds() / 60.0
            time_remaining = due_minutes - current_time
        else:
            time_remaining = (order.due_date - datetime.datetime.now()).total_seconds() / 60.0
    else:
        # current_time is a datetime object
        time_remaining = (order.due_date - current_time).total_seconds() / 60.0
        
    return time_remaining / total_remaining_processing_time

def ms_priority(order, machine, current_time) -> float:
    """
    Minimum Setup (MS)
    Priority = setup time required on current machine for this job.
    Lower setup time = higher priority.
    If same operation as last job: setup time = 0.
    """
    op = get_operation_for_machine(order, machine)
    if not op:
        return 0.0
        
    last_op = getattr(machine, "last_operation", None)
    if last_op == op.code:
        return 0.0
        
    return machine.setup_times.get(op.code, 0.0)
