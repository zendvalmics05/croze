from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime

@dataclass
class Machine:
    id: str
    name: str
    operation_types: List[str]
    cycle_times: Dict[str, float]       # operation_code -> minutes per unit
    setup_times: Dict[str, float]       # operation_code -> minutes
    shift_hours: float                  # hours per shift (default 8)
    shifts_per_day: int                 # 1, 2, or 3
    failure_rate: float                 # mean hours between failures; 0 = never fails
    repair_time: float                  # mean hours to repair
    degradation_factor: float           # how much cycle time grows with runtime

@dataclass
class Operation:
    code: str                           # e.g. 'TURN', 'MILL', 'GRIND'
    machine_type: str
    sequence_index: int
    parallel_capable: bool

@dataclass
class Product:
    id: str
    name: str
    routing: List[Operation]            # ordered list of operations
    batch_size: int

@dataclass
class Order:
    id: str
    product_id: str
    quantity: int
    due_date: datetime
    priority: int
    release_date: datetime
    status: str                         # 'pending', 'in_progress', 'completed'
    remaining_time_minutes: float = 0.0

@dataclass
class ScheduledJob:
    order_id: str
    operation_code: str
    machine_id: str
    start_time: float
    end_time: float
    setup_time: float

@dataclass
class Schedule:
    jobs: List[ScheduledJob]
    makespan: float
    algorithm_used: str
    generated_at: datetime
    factory_health_score: float

@dataclass
class MachineStats:
    machine_id: str
    total_busy_time: float
    total_setup_time: float
    total_idle_time: float
    total_failure_time: float
    utilisation: float
    average_queue_length: float
    max_queue_length: int
    jobs_processed: int

@dataclass
class JobStats:
    job_id: str
    total_time: float
    total_processing_time: float
    total_wait_time: float
    total_setup_time: float
    on_time: bool
    tardiness: float                    # 0 if on time, else minutes late

@dataclass
class SimulationResult:
    machine_stats: Dict[str, MachineStats]
    job_stats: Dict[str, JobStats]
    makespan: float
    event_log: List[tuple]
    simulation_duration: float
    total_tardiness: float
    on_time_rate: float

@dataclass
class FactoryModel:
    id: str
    name: str
    machines: List[Machine]
    products: List[Product]
    routing_graph: dict                 # adjacency dict: node_id -> [node_id]

@dataclass
class WorkingCalendar:
    factory_id: str
    state: str                          # Indian state name
    overrides: Dict[str, bool]          # 'YYYY-MM-DD' -> is_working
    shift_overrides: Dict[str, int]     # 'YYYY-MM-DD' -> shifts_per_day
