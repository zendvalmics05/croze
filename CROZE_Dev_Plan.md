# CROZE — Developer Task Plan
### The complete ordered checklist. Do things in the order they appear. Do not skip ahead.

---

> **How to use this document**
> Each feature block has a checkbox. Tick it when done. Sub-tasks are indented under their parent. Notes in `> blockquotes` are things to watch out for or remember while doing that task. You never need to ask "what do I do next" — just find the first unchecked box.

---

## PHASE 0 — Project Setup
*Do this before writing a single line of application code.*

---

### 0.1 — Repository and Folder Structure

- [ ] Create a GitHub repository called `croze`
- [ ] Create the following folder structure at the root:

```
croze/
├── backend/
│   ├── api/
│   ├── core/
│   ├── scheduler/
│   ├── diagnostics/
│   ├── db/
│   └── export/
├── frontend/
│   └── src/
│       ├── panels/
│       │   ├── FactoryBuilder/
│       │   ├── Orders/
│       │   ├── ScheduleDiagnostics/
│       │   └── WhatIf/
│       ├── components/
│       └── api/
├── tests/
├── examples/
├── README.md
└── LIMITATIONS.md
```

- [ ] Create a `.gitignore` — include `__pycache__`, `*.pyc`, `node_modules/`, `.env`, `*.db`
- [ ] Make an initial commit: "project scaffold"

---

### 0.2 — Backend Environment

- [ ] Create a Python virtual environment inside `/backend`: `python -m venv venv`
- [ ] Activate it and install these packages:

```
fastapi
uvicorn[standard]
simpy
sqlalchemy
numpy
pandas
pytest
reportlab
openpyxl
python-multipart
```

- [ ] Save to `requirements.txt`: `pip freeze > requirements.txt`
- [ ] Verify FastAPI works: create `backend/main.py` with a single `/ping` endpoint, run with `uvicorn main:app --reload`, visit `http://localhost:8000/ping` in browser

> **Note:** Always activate the virtual environment before running anything. `source venv/bin/activate` on Mac/Linux, `venv\Scripts\activate` on Windows.

---

### 0.3 — Frontend Environment

- [ ] From the `/frontend` folder, run: `npm create vite@latest . -- --template react`
- [ ] Install dependencies:

```
npm install react-flow-renderer @xyflow/react
npm install recharts
npm install axios
npm install @tanstack/react-query
npm install -D tailwindcss postcss autoprefixer
npm install lucide-react
```

- [ ] Run `npx tailwindcss init -p` to generate Tailwind config
- [ ] Add Tailwind directives to `src/index.css`
- [ ] Run `npm run dev` — should open a blank Vite+React page at `http://localhost:5173`
- [ ] Delete the default Vite boilerplate from `App.jsx`

> **Note:** The frontend and backend run on different ports. You will need to configure a proxy in `vite.config.js` so that frontend API calls to `/api/...` are forwarded to `http://localhost:8000`. Add this to `vite.config.js`:
> ```js
> server: { proxy: { '/api': 'http://localhost:8000' } }
> ```

---

### 0.4 — Database Setup

- [ ] Create `backend/db/database.py` — sets up SQLAlchemy engine pointing to a local `croze.db` SQLite file
- [ ] Create `backend/db/models.py` — define these five tables as SQLAlchemy ORM classes:

**Table: `factories`**
| Column | Type | Notes |
|---|---|---|
| id | String | Primary key, UUID |
| name | String | Human name e.g. "Valve Shop Floor 1" |
| json_definition | Text | The full factory graph as JSON |
| created_at | DateTime | |
| updated_at | DateTime | |

**Table: `orders`**
| Column | Type | Notes |
|---|---|---|
| id | String | Primary key, UUID |
| factory_id | String | Foreign key → factories.id |
| product_id | String | |
| quantity | Integer | |
| due_date | DateTime | |
| priority | Integer | 1 = highest |
| status | String | 'pending', 'in_progress', 'completed' |
| remaining_time_minutes | Float | Only used when status = 'in_progress' |

**Table: `schedules`**
| Column | Type | Notes |
|---|---|---|
| id | String | Primary key, UUID |
| factory_id | String | Foreign key → factories.id |
| algorithm | String | 'spt', 'edd', 'cr', 'ms', or 'genetic' |
| generated_at | DateTime | |
| makespan | Float | Total time in minutes |
| health_score | Float | 0–100 |
| json_result | Text | Full SimulationResult as JSON |

**Table: `scenarios`**
| Column | Type | Notes |
|---|---|---|
| id | String | Primary key, UUID |
| base_schedule_id | String | Foreign key → schedules.id |
| scenario_type | String | e.g. 'machine_breakdown', 'new_order' |
| params_json | Text | The scenario inputs as JSON |
| result_json | Text | The scenario result as JSON |
| created_at | DateTime | |

**Table: `working_calendar`**
| Column | Type | Notes |
|---|---|---|
| id | String | Primary key, UUID |
| factory_id | String | Foreign key → factories.id |
| date | Date | The specific date |
| is_working | Boolean | True = working day |
| shift_override | Integer | If different from factory default |

- [ ] Create `backend/db/database.py` function `init_db()` that creates all tables if they don't exist
- [ ] Call `init_db()` on FastAPI startup in `main.py`
- [ ] Test: run the app, confirm `croze.db` appears in the folder

> **Note:** SQLite stores the database as a single file. Do NOT add `croze.db` to git. Add it to `.gitignore`.

---

## PHASE 1 — Data Models
*No simulation yet. Just the Python data structures everything else will use.*

---

### 1.1 — Core Dataclasses

Create `backend/core/models.py`. Define these dataclasses exactly.

- [ ] **Machine**
```python
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
```

- [ ] **Operation**
```python
@dataclass
class Operation:
    code: str                           # e.g. 'TURN', 'MILL', 'GRIND'
    machine_type: str
    sequence_index: int
    parallel_capable: bool
```

- [ ] **Product**
```python
@dataclass
class Product:
    id: str
    name: str
    routing: List[Operation]            # ordered list of operations
    batch_size: int
```

- [ ] **Order**
```python
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
```

- [ ] **ScheduledJob**
```python
@dataclass
class ScheduledJob:
    order_id: str
    operation_code: str
    machine_id: str
    start_time: float
    end_time: float
    setup_time: float
```

- [ ] **Schedule**
```python
@dataclass
class Schedule:
    jobs: List[ScheduledJob]
    makespan: float
    algorithm_used: str
    generated_at: datetime
    factory_health_score: float
```

- [ ] **MachineStats**
```python
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
```

- [ ] **JobStats**
```python
@dataclass
class JobStats:
    job_id: str
    total_time: float
    total_processing_time: float
    total_wait_time: float
    total_setup_time: float
    on_time: bool
    tardiness: float                    # 0 if on time, else minutes late
```

- [ ] **SimulationResult**
```python
@dataclass
class SimulationResult:
    machine_stats: Dict[str, MachineStats]
    job_stats: Dict[str, JobStats]
    makespan: float
    event_log: List[tuple]
    simulation_duration: float
    total_tardiness: float
    on_time_rate: float
```

- [ ] **FactoryModel**
```python
@dataclass
class FactoryModel:
    id: str
    name: str
    machines: List[Machine]
    products: List[Product]
    routing_graph: dict                 # adjacency dict: node_id -> [node_id]
```

- [ ] **WorkingCalendar**
```python
@dataclass
class WorkingCalendar:
    factory_id: str
    state: str                          # Indian state name
    overrides: Dict[str, bool]          # 'YYYY-MM-DD' -> is_working
    shift_overrides: Dict[str, int]     # 'YYYY-MM-DD' -> shifts_per_day
```

> **Note:** All imports at top of `models.py`: `from dataclasses import dataclass, field`, `from typing import List, Dict`, `from datetime import datetime`

---

### 1.2 — Verify Models Load

- [ ] Write a 10-line test script (`tests/test_models.py`) that imports `models.py` and instantiates one of each dataclass with dummy values
- [ ] Run it: `python -m pytest tests/test_models.py -v`
- [ ] All pass → move on

---

## PHASE 2 — Working Calendar

*Build this before the simulation. The simulation depends on it.*

---

### 2.1 — Indian Holiday Data

Create `backend/core/calendar_data.py`.

- [ ] Create a dict `NATIONAL_HOLIDAYS` with all Indian national public holidays as `'YYYY' -> [('MM-DD', 'Holiday Name')]`. Include at minimum:
  - Republic Day: 01-26
  - Independence Day: 08-15
  - Gandhi Jayanti: 10-02

- [ ] Create a dict `STATE_HOLIDAYS` with at least these states and their major holidays:
  - Maharashtra (Gudi Padwa, Maharashtra Day)
  - Tamil Nadu (Pongal, Tamil New Year)
  - Punjab (Baisakhi, Guru Nanak Jayanti)
  - Gujarat (Uttarayan, Gujarat Day)
  - Uttar Pradesh (Holi additional day)

> **Note:** You only need the date (MM-DD format) and name. You don't need exact year-by-year dates for now. Fix them for 2025 and 2026 to start.

---

### 2.2 — Calendar Logic

Create `backend/core/calendar_model.py`.

- [ ] Function `is_working_day(date, factory_id, db_session) -> bool`
  - Returns False for national holidays
  - Returns False for state holidays (based on factory's state)
  - Returns False for manually added override days
  - Returns True otherwise (weekdays), False for Sundays
  - Saturdays: return True by default (most Indian factories work Saturday)

- [ ] Function `get_shifts_for_day(date, machine, factory_id, db_session) -> int`
  - Returns machine's default `shifts_per_day`
  - Unless overridden in `working_calendar` table for that date

- [ ] Function `next_shift_start(current_datetime, machine, factory_id, db_session) -> datetime`
  - Given a datetime, returns the next datetime when this machine starts a working shift
  - Used by the simulation to skip over non-working time

- [ ] Function `sim_minutes_to_datetime(minutes_from_start, reference_date) -> datetime`
  - Converts simulation clock minutes to a real datetime

- [ ] Function `datetime_to_sim_minutes(dt, reference_date) -> float`
  - Inverse of above

> **Note:** The simulation runs in "minutes from simulation start." The reference_date is the date the schedule was generated. All calendar logic converts between real dates and simulation minutes.

---

### 2.3 — Calendar Tests

- [ ] Test that Republic Day (Jan 26) returns `is_working_day = False`
- [ ] Test that a normal Tuesday returns `is_working_day = True`
- [ ] Test that a manually added override makes a Tuesday return `False`
- [ ] Test `next_shift_start` when called during a working shift returns the same time
- [ ] Test `next_shift_start` when called after shift hours returns the next morning

---

## PHASE 3 — Simulation Core

*The heart of the system. Get this right before anything else.*

---

### 3.1 — Shift-Aware Timeout Helper

Create `backend/core/simulation.py`. Start with this utility function.

- [ ] Function `wait_until_working(env, machine, calendar, factory_id, db_session)`
  - A SimPy generator
  - Computes gap between `env.now` and next working minute for this machine
  - If gap > 0: `yield env.timeout(gap)`
  - If gap = 0: returns immediately (already in working time)

> **Note:** This function must be `yield`-ed inside every job process before any processing begins. It's what makes the simulation respect shift hours and holidays.

---

### 3.2 — Job Process

- [ ] Implement `job_process(env, order, product, schedule, factory_model, calendar, machine_resources, event_log)`
  - It is a Python generator function (uses `yield`)
  - For each operation in the product's routing, in order:
    1. `yield` from `wait_until_working` for the assigned machine
    2. Log `QUEUE_ENTER` event to event_log
    3. `yield machine_resource.request()` — waits if machine is busy
    4. Log `MACHINE_START` event
    5. If last operation on this machine was different type: `yield env.timeout(setup_time)`, log `SETUP_COMPLETE`
    6. Compute degraded cycle time: `base * (1 + degradation_factor * runtime_hours / 100)`
    7. `yield env.timeout(processing_time)`
    8. Update `machine_resource.total_runtime`
    9. Log `OPERATION_COMPLETE`
  - After all operations: log `JOB_COMPLETE`

> **Note:** `machine_resources` is a dict of `machine_id -> simpy.Resource`. Each resource should have two custom attributes added after creation: `last_operation = None` and `total_runtime = 0.0`.

---

### 3.3 — Machine Failure Process

- [ ] Implement `machine_failure_process(env, machine, machine_resource, event_log)`
  - If `machine.failure_rate == 0`: return immediately (no failures)
  - Loop forever:
    - `time_to_failure = random.expovariate(1.0 / (machine.failure_rate * 60))`
    - `yield env.timeout(time_to_failure)`
    - If machine currently has a user (job in progress): interrupt it
    - Log `MACHINE_FAILURE`
    - `repair_time = random.expovariate(1.0 / (machine.repair_time * 60))`
    - `yield env.timeout(repair_time)`
    - Log `MACHINE_REPAIRED`

> **Note:** When a job is interrupted by machine failure, it must restart that operation from the beginning when the machine is repaired. Handle the `simpy.Interrupt` exception in `job_process` to re-request the machine.

---

### 3.4 — Partial Schedule Support

- [ ] In `job_process`, at the very start, check if `order.status == 'in_progress'`
  - If yes: the first operation's processing time is `order.remaining_time_minutes` instead of the full cycle time
  - Skip directly to `yield machine_resource.request()` for the first operation without going through setup

---

### 3.5 — Event Log Processing

- [ ] Function `process_event_log(event_log, factory_model, orders, simulation_end_time) -> SimulationResult`
  - Iterates through the event log tuples
  - Computes for each machine: total_busy_time, total_setup_time, total_idle_time, total_failure_time, utilisation, average_queue_length, jobs_processed
  - Computes for each job: total_time, total_processing_time, total_wait_time, on_time (compare JOB_COMPLETE time against order.due_date), tardiness
  - Returns a populated `SimulationResult`

> **Note:** Event log tuples have the format `(event_type, job_id, operation_code, machine_id, timestamp)`. Some fields are None for machine-level events.

---

### 3.6 — Main Simulation Runner

- [ ] Function `run_simulation(factory_model, schedule, orders, calendar, factory_id, db_session) -> SimulationResult`
  - Creates SimPy environment
  - Creates one `simpy.Resource(env, capacity=1)` per machine; adds `last_operation=None` and `total_runtime=0.0` attributes
  - Starts one `machine_failure_process` per machine as a SimPy process
  - Starts one `job_process` per order as a SimPy process
  - Runs `env.run()` until all jobs complete
  - Calls `process_event_log` and returns result

---

### 3.7 — Feasibility Check

- [ ] Function `check_feasibility(factory_model, orders, calendar, factory_id, db_session) -> FeasibilityReport`
  - For each machine, compute total available machine-hours over the planning horizon (from now to latest due date), respecting the working calendar
  - For each order, compute total machine-hours required across all its operations
  - Aggregate required hours per machine
  - If required > available for any machine: mark infeasible
  - Return a `FeasibilityReport` with:
    - `is_feasible: bool`
    - `infeasible_machines: List[dict]` — each with machine name, hours required, hours available, shortfall
    - `at_risk_orders: List[str]` — order IDs that cannot complete on time

---

### 3.8 — Simulation Tests

- [ ] **Test 1 — Single machine, single job:** 1 machine, cycle time 10 min/unit, 1 job of 50 units, no failures, no shifts. Expected completion: exactly 500 minutes. Tolerance: 0.1%.
- [ ] **Test 2 — Two machines in series:** Machine A: 8 min/unit, Machine B: 12 min/unit, 10 jobs of 1 unit each. Verify queue builds in front of B. Compute expected makespan by hand and verify.
- [ ] **Test 3 — Utilisation:** 1 machine, 480 available minutes, 300 minutes of work. Expected utilisation: 62.5%. Tolerance: 0.1%.
- [ ] **Test 4 — Shift boundary:** Job released at end of shift. Verify job is deferred to next shift start, not processed in non-working hours.
- [ ] **Test 5 — Partial schedule:** Order with `status='in_progress'` and `remaining_time_minutes=30`. Verify job completes at t=30, not at full cycle time.

---

## PHASE 4 — Scheduler

*Assign jobs to machines. Determine order. Two modes: fast rules and genetic algorithm.*

---

### 4.1 — Dispatching Rules

Create `backend/scheduler/dispatching.py`.

- [ ] **SPT — Shortest Processing Time**
  - Priority function returns: total remaining processing time for this job on this machine
  - Lower value = higher priority

- [ ] **EDD — Earliest Due Date**
  - Priority function returns: due_date as a numeric timestamp
  - Lower value = higher priority

- [ ] **CR — Critical Ratio**
  - `CR = time_remaining_to_due_date / total_remaining_processing_time`
  - Lower CR = more critical = higher priority
  - If remaining processing time is 0: return negative infinity (highest priority)

- [ ] **MS — Minimum Setup**
  - Priority function returns: setup time required on current machine for this job
  - Lower setup time = higher priority
  - If same operation as last job: setup time = 0

> **Note:** All four rules must have the same function signature: `priority(order, machine, current_time) -> float`. Lower return value = higher priority for all rules.

---

### 4.2 — Baseline Scheduler

Create `backend/scheduler/scheduler.py`.

- [ ] Function `build_schedule(factory_model, orders, rule_fn) -> Schedule`
  - For each machine, maintains a queue of jobs waiting for it
  - Assigns jobs to machines based on their routing
  - Uses `rule_fn` to sort the queue at each decision point
  - Returns a `Schedule` object with all `ScheduledJob` entries filled in

---

### 4.3 — Genetic Algorithm

Create `backend/scheduler/genetic.py`.

- [ ] **Chromosome representation:** a list of integers — a permutation of job indices. Position = priority. Example: `[3, 0, 4, 1, 2]` means job 3 has highest priority.

- [ ] Function `chromosome_to_schedule(chromosome, factory_model, orders) -> Schedule`
  - Converts a priority ordering into a Schedule by running the baseline scheduler with that ordering

- [ ] Function `fitness(chromosome, factory_model, orders, weights) -> float`
  - Calls `chromosome_to_schedule`, then `run_simulation`
  - Returns: `weights['makespan'] * normalised_makespan + weights['tardiness'] * normalised_tardiness + weights['utilisation_balance'] * stdev_of_utilisations`
  - Lower = better

- [ ] Function `tournament_select(population, fitnesses, k=3) -> chromosome`
  - Randomly pick k chromosomes, return the one with lowest fitness

- [ ] Function `order_crossover(parent1, parent2) -> child`
  - Pick a random segment from parent1
  - Copy segment directly to child at same positions
  - Fill remaining positions with genes from parent2 in their original order, skipping genes already in the child
  - Verify: child must contain every job index exactly once

- [ ] Function `swap_mutate(chromosome, mutation_rate=0.1) -> chromosome`
  - For each position, with probability `mutation_rate`, swap it with a random other position

- [ ] Function `genetic_algorithm(factory_model, orders, weights, time_budget_seconds=120, population_size=100, elite_fraction=0.1) -> (best_chromosome, best_fitness, generations_run)`
  - Initialise population with random permutations
  - Loop until `time.time() - start_time >= time_budget_seconds`:
    - Evaluate fitness of all chromosomes
    - Keep top `elite_fraction` unchanged (elitism)
    - Fill rest with crossover + mutation
    - Track best chromosome seen so far
  - Return best chromosome found

> **Note:** The GA runs the full simulation for every chromosome in every generation. With population_size=100 and a 2-minute budget, this might run 5–20 generations depending on factory size. That is fine. Do not try to speed this up prematurely.

---

### 4.4 — Scheduler Tests

- [ ] **Test 1 — EDD:** Generate jobs with varied due dates. EDD must produce lower maximum tardiness than SPT on this instance.
- [ ] **Test 2 — GA convergence:** Run GA for 60 seconds on a 10-job, 3-machine instance. Best fitness must be strictly lower than or equal to the initial population's best fitness.
- [ ] **Test 3 — Order Crossover validity:** Run `order_crossover` 1000 times on random parents. Every child must be a valid permutation (no duplicates, no missing indices). Use `assert sorted(child) == list(range(n))`.
- [ ] **Test 4 — GA vs best rule:** On a 15-job, 4-machine instance, GA (2 min budget) must produce lower makespan than the best of the four dispatching rules.

---

## PHASE 5 — Diagnostic Engine

*Turns raw simulation numbers into human-readable insight.*

---

### 5.1 — Factory Health Score

Create `backend/diagnostics/health_score.py`.

- [ ] Function `compute_health_score(result: SimulationResult) -> float`
  - Component 1 (40%): `on_time_rate` — fraction of orders completed before due date
  - Component 2 (35%): utilisation balance score = `1 - stdev(all machine utilisations)` — normalised to [0,1]
  - Component 3 (25%): setup efficiency = `1 - (total_setup_time / total_available_time)`
  - Final score: weighted sum × 100, clamped to [0, 100]
  - Return as a float

---

### 5.2 — Bottleneck Identification

Create `backend/diagnostics/bottleneck.py`.

- [ ] Function `identify_bottleneck(result: SimulationResult) -> dict`
  - For each machine compute: `score = 0.6 * normalised_utilisation + 0.4 * normalised_avg_queue`
  - Machine with highest score is the bottleneck
  - Return dict with:
    - `machine_id`
    - `score`
    - `utilisation` (as percentage)
    - `avg_queue`
    - `explanation` — plain English string, e.g. "Machine M003 (Surface Grinder) is your bottleneck. It is busy 91.4% of the time with 4.2 jobs waiting on average."
    - `all_scores` — dict of all machine scores for ranking

---

### 5.3 — Throughput Loss Analysis

Create `backend/diagnostics/throughput.py`.

- [ ] Function `throughput_analysis(result: SimulationResult) -> dict`
  - For each machine compute:
    - `productive_fraction`: `busy_time / total_available_time`
    - `idle_fraction`: `idle_time / total_available_time`
    - `failure_fraction`: `failure_time / total_available_time`
    - `setup_fraction`: `setup_time / total_available_time`
  - Return dict keyed by machine_id, each with the above four fractions

---

### 5.4 — Deadline Risk Analysis

Create `backend/diagnostics/deadline.py`.

- [ ] Function `deadline_risk_analysis(result: SimulationResult, orders: List[Order]) -> List[dict]`
  - For each order:
    - If `job_stat.on_time`: status = 'ON_TIME', include margin in minutes
    - If not on time: status = 'LATE', include tardiness in minutes
    - Scan event log to find which machine caused the longest wait for this job — that's `delay_source_machine`
  - Return list sorted by tardiness descending (worst first)

---

### 5.5 — Infeasibility Report

Create `backend/diagnostics/feasibility.py`.

- [ ] Function `format_infeasibility_report(feasibility_result) -> str`
  - Takes output of `check_feasibility` from Phase 3.7
  - Returns a plain-English string formatted like:

```
CAPACITY INFEASIBILITY REPORT

These orders CANNOT be completed on time with current capacity.

  ORD-047 (200 units Product A, due 15-Mar)
    Shortfall: 8.4 machine-hours on M003 (Surface Grinder)
    Options:
      1. Add one shift to M003
      2. Push due date by 1.5 days
      3. External process 80 units

  ORD-052 (150 units Product B, due 16-Mar)
    Resolves if ORD-047 due date is pushed.
```

---

### 5.6 — Plain Language Report Generator

Create `backend/diagnostics/report.py`.

- [ ] Function `generate_report(result: SimulationResult, bottleneck: dict, throughput: dict, risks: List[dict], health_score: float, schedule: Schedule) -> str`
  - Returns a multi-section plain text report
  - Sections: FACTORY HEALTH / BOTTLENECK / THROUGHPUT LOSSES / DEADLINE RISK
  - Each section uses plain English, no jargon, no numbers without units
  - All percentages rounded to 1 decimal place
  - All times expressed in hours and minutes, not raw minutes

> **Sample output format:**
```
FACTORY DIAGNOSTIC REPORT
Generated: 15-Mar-2025 08:42  |  Algorithm: Genetic  |  Health Score: 84/100

BOTTLENECK
M003 (Surface Grinder) is your bottleneck.
It is busy 91.4% of the time with 4.2 jobs waiting on average.
Adding one shift to this machine would increase weekly throughput by ~18%.

THROUGHPUT LOSSES
M001 (CNC Lathe):        82% working  |  11% idle  |  4% setup  |  3% breakdown
M003 (Surface Grinder):  91% working  |   3% idle  |  5% setup  |  1% breakdown

DEADLINE STATUS
AT RISK:  ORD-047 — 6.2 hours behind. Cause: queue at M003.
ON TIME:  ORD-048, ORD-049, ORD-051 — all with >8 hours margin.
```

---

### 5.7 — Diagnostic Tests

- [ ] Health score for a perfect schedule (100% on time, balanced utilisations, no setup waste) should be near 100
- [ ] Health score for all-late, unbalanced, high-setup schedule should be near 0
- [ ] Bottleneck identified by the function must match the machine with highest utilisation in a simple 2-machine test
- [ ] Plain language report must contain the word "bottleneck" and the name of the bottleneck machine

---

## PHASE 6 — What-If Engine

*Runs the full simulation pipeline with a modified input.*

---

Create `backend/diagnostics/whatif_engine.py`.

### 6.1 — Scenario: New Order

- [ ] Function `scenario_new_order(factory_model, existing_orders, new_order, algorithm, weights, calendar, factory_id, db_session) -> WhatIfResult`
  - Add `new_order` to `existing_orders`
  - Run full scheduler + simulation + diagnostics on combined list
  - Return: new schedule, new diagnostic report, list of previously on-time orders that are now late

---

### 6.2 — Scenario: Machine Breakdown

- [ ] Function `scenario_machine_breakdown(factory_model, orders, machine_id, breakdown_start_minutes, repair_duration_minutes, ...) -> WhatIfResult`
  - Create a modified copy of `factory_model`
  - Set the target machine's `failure_rate` to force a failure at `breakdown_start_minutes` with `repair_duration_minutes` repair time
  - Run full pipeline
  - Return: new schedule, orders now late, suggested recovery actions

---

### 6.3 — Scenario: Add a Shift

- [ ] Function `scenario_add_shift(factory_model, orders, machine_id, additional_shifts, ...) -> WhatIfResult`
  - Create modified copy of factory_model
  - Increase target machine's `shifts_per_day` by `additional_shifts`
  - Run full pipeline
  - Return: new schedule, on-time rate change, bottleneck change, health score change

---

### 6.4 — Scenario: Supplier Delay

- [ ] Function `scenario_supplier_delay(factory_model, orders, material_name, delay_days, ...) -> WhatIfResult`
  - Push `release_date` of all orders that require `material_name` forward by `delay_days`
  - Run full pipeline
  - Return: cascade of affected orders, revised schedule

---

### 6.5 — WhatIfResult Structure

- [ ] Define `WhatIfResult` dataclass:
```python
@dataclass
class WhatIfResult:
    scenario_type: str
    baseline_schedule: Schedule
    scenario_schedule: Schedule
    baseline_health_score: float
    scenario_health_score: float
    baseline_on_time_rate: float
    scenario_on_time_rate: float
    baseline_makespan: float
    scenario_makespan: float
    newly_late_orders: List[str]
    newly_on_time_orders: List[str]
    bottleneck_changed: bool
    new_bottleneck: str
    plain_comparison: str           # one-paragraph plain English comparison
```

---

## PHASE 7 — Export

---

### 7.1 — PDF Export

Create `backend/export/pdf_exporter.py`.

- [ ] Function `export_diagnostic_pdf(result: SimulationResult, report_text: str, schedule: Schedule, output_path: str)`
  - Use ReportLab
  - Page 1: factory name, date, health score, bottleneck section, throughput losses table
  - Page 2: Gantt chart as a simple ReportLab drawing (horizontal bars by machine, time on x-axis)
  - Page 3: Deadline risk table (order ID, due date, status, margin or tardiness)
  - Save to `output_path`

> **Note:** The Gantt chart in PDF does not need to be interactive. Simple coloured bars are fine. Use ReportLab's `Drawing` and `Rect` primitives.

---

### 7.2 — Excel Export

Create `backend/export/excel_exporter.py`.

- [ ] Function `export_schedule_excel(result: SimulationResult, schedule: Schedule, orders: List[Order], output_path: str)`
  - Use openpyxl
  - Sheet 1 "Schedule": one row per ScheduledJob — order ID, machine, operation, start time, end time, setup time
  - Sheet 2 "Machine Stats": one row per machine — all MachineStats fields
  - Sheet 3 "Job Stats": one row per order — all JobStats fields
  - Sheet 4 "Event Log": full raw event log
  - Auto-size columns
  - Header row bold with light blue background

---

## PHASE 8 — FastAPI Endpoints

*Wire everything built so far into a REST API. The frontend will call these.*

---

Create files in `backend/api/`.

### 8.1 — Factory Endpoints (`api/factory.py`)

- [ ] `POST /api/factory/save` — body: factory name + json_definition. Save to DB. Return factory ID.
- [ ] `GET /api/factory/{factory_id}` — return factory definition JSON
- [ ] `GET /api/factory/list` — return list of all saved factories with id, name, created_at, updated_at
- [ ] `DELETE /api/factory/{factory_id}` — delete factory and all associated orders/schedules

---

### 8.2 — Order Endpoints (`api/orders.py`)

- [ ] `POST /api/orders/` — body: order fields + factory_id. Save to DB. Return order ID.
- [ ] `GET /api/orders/{factory_id}` — return all orders for this factory
- [ ] `PUT /api/orders/{order_id}` — update an order
- [ ] `DELETE /api/orders/{order_id}` — delete an order
- [ ] `POST /api/orders/import-csv/{factory_id}` — accept a CSV file upload, parse into orders, save all to DB. CSV columns: product_id, quantity, due_date, priority

---

### 8.3 — Schedule Endpoints (`api/schedule.py`)

- [ ] `POST /api/schedule/run` — the main endpoint
  - Body: `{ factory_id, algorithm, time_budget_seconds, weights }`
  - Loads factory + orders from DB
  - Runs feasibility check — if infeasible, returns infeasibility report immediately (HTTP 200 with `feasible: false`)
  - If feasible: runs scheduler + simulation + diagnostics
  - Saves result to `schedules` table
  - Returns full response (see structure below)
- [ ] `GET /api/schedule/history/{factory_id}` — return list of previous schedule runs with id, algorithm, generated_at, makespan, health_score
- [ ] `GET /api/schedule/{schedule_id}` — return full schedule result JSON

**Schedule run response structure:**
```json
{
  "feasible": true,
  "schedule_id": "...",
  "schedule": { "jobs": [...], "makespan": 4821, "health_score": 84 },
  "machine_stats": { "M001": { "utilisation": 0.82, ... } },
  "job_stats": { "ORD-047": { "on_time": true, "margin_minutes": 92 } },
  "bottleneck": { "machine_id": "M002", "explanation": "..." },
  "throughput_losses": { "M001": { "idle": 0.11, "setup": 0.04, "failure": 0.03 } },
  "deadline_risks": [ { "order_id": "ORD-052", "status": "AT_RISK", ... } ],
  "plain_language_report": "..."
}
```

---

### 8.4 — What-If Endpoints (`api/whatif.py`)

- [ ] `POST /api/whatif/run`
  - Body: `{ base_schedule_id, scenario_type, params }`
  - `scenario_type` is one of: `new_order`, `machine_breakdown`, `add_shift`, `supplier_delay`
  - `params` is scenario-specific JSON
  - Runs the appropriate scenario function from Phase 6
  - Saves result to `scenarios` table
  - Returns `WhatIfResult` as JSON
- [ ] `GET /api/whatif/history/{schedule_id}` — return all scenario runs for a base schedule

---

### 8.5 — Calendar Endpoints (`api/calendar.py`)

- [ ] `GET /api/calendar/{factory_id}` — return working calendar for factory
- [ ] `PUT /api/calendar/{factory_id}` — update calendar (overrides, shift overrides, state selection)
- [ ] `GET /api/calendar/holidays?state=Maharashtra&year=2025` — return list of non-working days for a state and year

---

### 8.6 — Export Endpoints (`api/export.py`)

- [ ] `GET /api/export/pdf/{schedule_id}` — generate PDF and return as file download
- [ ] `GET /api/export/excel/{schedule_id}` — generate Excel and return as file download

---

### 8.7 — API Test

- [ ] Use `curl` or the FastAPI auto-docs at `http://localhost:8000/docs` to test every endpoint manually
- [ ] Save a factory, retrieve it, confirm the JSON matches exactly
- [ ] Post an order, list orders, confirm it appears
- [ ] Run a schedule on a hand-crafted small factory, confirm response structure matches the spec above

---

## PHASE 9 — React Frontend

*Do Phases 0–8 fully before touching the frontend.*

---

### 9.1 — App Shell

- [ ] Create `src/App.jsx` — four-tab layout with a left sidebar for navigation
- [ ] Sidebar tabs: Factory Builder | Orders | Schedule & Diagnostics | What-If
- [ ] Each tab renders its panel component
- [ ] Active tab highlighted in sidebar
- [ ] Factory name displayed at top of sidebar
- [ ] "Load Factory" and "New Factory" buttons in sidebar header

> **Note:** Use Tailwind for all layout. No custom CSS files unless absolutely necessary. Keep the design simple — dark sidebar (#1B4F8A blue), white content area. No animations.

---

### 9.2 — API Client

Create `src/api/client.js`.

- [ ] Axios instance with `baseURL: '/api'`
- [ ] Functions for every backend endpoint, named clearly:
  - `saveFactory(name, jsonDefinition)`
  - `loadFactory(factoryId)`
  - `listFactories()`
  - `saveOrder(orderData)`
  - `getOrders(factoryId)`
  - `updateOrder(orderId, orderData)`
  - `deleteOrder(orderId)`
  - `runSchedule(factoryId, algorithm, timeBudget, weights)`
  - `getScheduleHistory(factoryId)`
  - `runWhatIf(baseScheduleId, scenarioType, params)`
  - `getCalendar(factoryId)`
  - `updateCalendar(factoryId, calendarData)`
  - `exportPdf(scheduleId)`
  - `exportExcel(scheduleId)`

---

### 9.3 — Factory Builder Panel

Create `src/panels/FactoryBuilder/index.jsx`.

- [ ] React Flow canvas filling the main content area
- [ ] Left palette with five draggable node types: Machine (blue), Buffer (orange), Input (green), Output (red), Assembly (purple)
- [ ] Drag a node from palette onto canvas to create it
- [ ] Nodes can be connected by dragging from one handle to another
- [ ] Click a node → opens configuration panel on the right side

**Node configuration panel (`src/panels/FactoryBuilder/ConfigPanel.jsx`):**
- [ ] Machine node fields: name, operation types (add/remove), cycle time per operation, setup time per operation, shifts per day, hours per shift, failure rate, repair time, degradation factor
- [ ] Buffer node fields: name, capacity
- [ ] Input node fields: material name, current stock
- [ ] Assembly node fields: name, assembly time
- [ ] Output node fields: product name
- [ ] "Apply" button saves the configuration to the node's data in React Flow state
- [ ] Auto-save to backend every 60 seconds (call `saveFactory`)
- [ ] Manual "Save Factory" button in panel header
- [ ] "Load Factory" button opens a dropdown of saved factories from `listFactories()`

> **Note:** React Flow stores node and edge data in component state via `useState`. The factory JSON sent to the backend is simply `JSON.stringify({ nodes, edges })`. The backend stores it as-is and returns it as-is. Deserialisation happens on load in the frontend.

> **Note:** React Flow `@xyflow/react` is the current package name. Import: `import ReactFlow from '@xyflow/react'`. Do not install the old `react-flow-renderer` package — it is deprecated.

---

### 9.4 — Orders Panel

Create `src/panels/Orders/index.jsx`.

- [ ] Table showing all orders for the current factory
- [ ] Columns: Order ID | Product | Quantity | Due Date | Priority | Status
- [ ] "Add Order" button opens a form modal with all order fields
- [ ] Each row has Edit and Delete buttons
- [ ] "Import CSV" button opens file picker, uploads to `/api/orders/import-csv/{factory_id}`
- [ ] Due dates close to today shown in amber; overdue in red

---

### 9.5 — Schedule & Diagnostics Panel

Create `src/panels/ScheduleDiagnostics/index.jsx`.

- [ ] **Algorithm selector:** Radio buttons — SPT | EDD | Critical Ratio | Min Setup | Genetic Algorithm
- [ ] **Time budget slider:** Only visible when Genetic Algorithm is selected. Range: 30 seconds to 5 minutes.
- [ ] **Weight sliders:** Only visible when Genetic Algorithm is selected. Three sliders: Makespan weight | Tardiness weight | Balance weight. Must sum to 1.0 (auto-adjust the third).
- [ ] **Run button:** Calls `runSchedule`. Shows loading spinner. Displays "Running genetic algorithm... (up to 2 minutes)" if GA selected.
- [ ] **Health score gauge:** Large number 0–100 with colour coding (red <50, amber 50–75, green >75)
- [ ] **Gantt chart** (see 9.5.1 below)
- [ ] **Machine utilisation bars:** One horizontal bar per machine, showing productive/idle/setup/failure fractions in different colours. Label with percentages.
- [ ] **Plain language report:** Rendered as formatted text below the charts
- [ ] **Export buttons:** "Download PDF Report" and "Download Excel" — trigger respective export endpoints

**9.5.1 — Gantt Chart (`src/panels/ScheduleDiagnostics/GanttChart.jsx`):**
- [ ] Use `react-plotly.js`
- [ ] X-axis: time (in hours from schedule start)
- [ ] Y-axis: machine names
- [ ] Each bar: one job-operation
- [ ] Colour: by order ID (each order gets a distinct colour)
- [ ] Bar border: red if the job is tardy, green if on time
- [ ] Hover tooltip: order ID, operation, start time, end time, queue wait time, on-time status
- [ ] Vertical dashed line at current real-world time (relative to schedule start)
- [ ] Grey shading for non-working hours (shift boundaries from calendar)

> **Note:** Plotly uses the `gantt` trace type or you can build it from bar charts. The simpler approach is using Plotly's `Figure.add_shape` from Python — but since this is React, use `react-plotly.js` with `data` and `layout` props. Refer to Plotly.js documentation for horizontal bar chart implementation.

---

### 9.6 — What-If Panel

Create `src/panels/WhatIf/index.jsx`.

- [ ] Dropdown to select scenario type: New Order | Machine Breakdown | Add a Shift | Supplier Delay
- [ ] Parameter form changes based on selected scenario type:
  - New Order: product ID, quantity, due date
  - Machine Breakdown: machine selector, breakdown start, repair duration
  - Add a Shift: machine selector, number of shifts to add
  - Supplier Delay: material name, delay in days
- [ ] "Run Scenario" button calls `runWhatIf`
- [ ] Results displayed as a comparison table: Baseline vs Scenario for makespan, on-time rate, health score, bottleneck
- [ ] List of "Newly Late Orders" and "Newly On Time Orders" below table
- [ ] Plain comparison paragraph from `WhatIfResult.plain_comparison`
- [ ] Scenario history: list of previous scenarios run on the current base schedule

---

### 9.7 — Calendar Panel

Create `src/panels/Calendar/index.jsx`.

- [ ] Monthly grid showing each day colour-coded: green (working), amber (reduced shifts), red (non-working)
- [ ] Click a day to toggle working/non-working or override shift count
- [ ] State selector dropdown at top: selects Indian state for auto-populating state holidays
- [ ] "Reset to defaults" button restores national + state holidays without custom overrides
- [ ] Saves to backend via `updateCalendar` on every change

> **Note:** Calendar panel can be accessed from a button in the Orders panel header or as a fifth sidebar item. It does not need to be in the main four-tab navigation.

---

## PHASE 10 — Example Factories

*These are the demo files anyone can use to test CROZE immediately.*

---

### 10.1 — Simple Factory

Create `examples/simple_factory.json`.

- [ ] 3 machines: CNC Lathe, Milling Centre, Inspection Bench
- [ ] 1 product: a simple turned-and-milled component
- [ ] 5 orders of varying quantities and due dates
- [ ] No failures, single shift
- [ ] GA should finish in under 20 seconds on this factory
- [ ] Document in README: "Use this to verify your installation works"

---

### 10.2 — Precision Shop Factory

Create `examples/precision_shop.json`.

- [ ] 6 machines: CNC Lathe ×2, Vertical Machining Centre, Surface Grinder, Coordinate Measuring Machine, Heat Treatment Furnace
- [ ] 3 products with different routings (e.g., valve body, pump shaft, bearing housing)
- [ ] 12 orders spread over 5 working days
- [ ] Machine failure rates based on real-world approximate MTBF values for CNC equipment
- [ ] Two-shift operation
- [ ] Designed so that the Surface Grinder is the bottleneck (adjust cycle times to achieve this)
- [ ] Designed so that 2–3 orders are at risk without optimisation but all deliverable with GA scheduling
- [ ] Document in README: "This is the full demonstration factory. Use it to explore all features."

> **Note:** If you got real cycle time data from your LinkedIn outreach, use those numbers here. Attribute it in the README: "Machine parameters validated against data provided by [anonymous] auto-ancillary manufacturer, Coimbatore, 2025."

---

## PHASE 11 — Testing and Validation

*Run through these after all phases are complete. These are the checks that prove the system works.*

---

### 11.1 — End-to-End Validation (precision_shop.json)

- [ ] Load `precision_shop.json` via the UI
- [ ] Enter 12 orders with the dates specified in the JSON
- [ ] Run with Earliest Due Date rule → note health score
- [ ] Run with Genetic Algorithm (2 minutes) → confirm health score is higher than EDD
- [ ] Confirm: bottleneck identified is the Surface Grinder
- [ ] Run "Add a Shift" scenario on Surface Grinder → confirm health score increases
- [ ] Run "Machine Breakdown" scenario on CNC Lathe → confirm at least one order is newly late
- [ ] Download PDF export → open it, confirm it contains the bottleneck name and a Gantt chart
- [ ] Download Excel export → open it, confirm it has 4 sheets with data

### 11.2 — Data Persistence Validation

- [ ] Save `precision_shop.json` factory via UI
- [ ] Stop the backend server
- [ ] Restart it
- [ ] Load the factory → confirm all nodes, edges, and machine properties are identical to what was saved

### 11.3 — Calendar Validation

- [ ] Set factory state to Maharashtra
- [ ] Check that Republic Day (Jan 26) shows as red (non-working) in calendar
- [ ] Schedule with an order due the day after Republic Day — confirm the simulation does not schedule work on Jan 26

### 11.4 — Feasibility Validation

- [ ] Create a factory with 1 machine, 1 shift of 8 hours
- [ ] Add an order requiring 100 hours of work on that machine, due tomorrow
- [ ] Run schedule → system must return infeasibility report, not a schedule
- [ ] Confirm infeasibility report names the machine and the hour shortfall

---

## PHASE 12 — Documentation

---

### 12.1 — README.md

- [ ] Project title and one-paragraph description
- [ ] "Who is this for" — production planners, factory owners, operations managers
- [ ] Installation instructions (step by step, assume reader has Python and Node installed):
  1. Clone repo
  2. Backend setup (venv, pip install)
  3. Frontend setup (npm install)
  4. Run backend: `uvicorn main:app --reload` from `/backend`
  5. Run frontend: `npm run dev` from `/frontend`
  6. Open browser at `http://localhost:5173`
  7. Load `examples/simple_factory.json` to verify
- [ ] "Quick Demo" section: step-by-step to run the precision_shop example end to end
- [ ] Architecture overview: two sentences on FastAPI + React + SimPy + SQLite
- [ ] "Validated with data from Indian manufacturing partners" (only if you did the outreach)
- [ ] Link to LIMITATIONS.md

### 12.2 — LIMITATIONS.md

- [ ] Processing times are assumed deterministic; real variance not modelled
- [ ] GA finds near-optimal solutions, not provably optimal ones
- [ ] Factory must be fully described before analysis; no partial input mode
- [ ] Single-factory deployment; no multi-user access
- [ ] No live machine connectivity; all inputs manual
- [ ] Calendar pre-loaded for 2025–2026; will need updating for future years

---

## PHASE 13 — CV and Interview Preparation

*Do this after everything else is built and working.*

---

### 13.1 — GitHub Repository

- [ ] Clean commit history — squash any "fix typo" commits
- [ ] All files committed, nothing sensitive (no .db file, no .env)
- [ ] README renders correctly on GitHub (check headings, code blocks)
- [ ] Repository set to Public

### 13.2 — Demo Video

- [ ] Record a 3-minute screen recording (no audio needed, or brief narration):
  1. Open CROZE with precision_shop loaded (0:00)
  2. Show factory builder — pan around nodes (0:20)
  3. Show orders panel — 12 orders visible (0:40)
  4. Run GA — show loading, then result (1:00)
  5. Point at health score and bottleneck in diagnostic report (1:30)
  6. Run "Add a Shift" what-if — show comparison table (2:00)
  7. Download PDF export — show it open (2:30)
- [ ] Upload to YouTube (unlisted is fine) or attach to GitHub README as a GIF for key moments

### 13.3 — Verbal Pitches

Memorise these. Practice saying them out loud.

- [ ] **30-second version:** "I built CROZE — a production scheduling and factory diagnostic tool for Indian SME manufacturers. You describe your factory, enter your orders, and it generates an optimised schedule using a genetic algorithm. It tells you where your factory is losing throughput, identifies the bottleneck in plain language, and lets you run what-if scenarios — what happens if a machine breaks, a new order comes in, or you add a shift. It accounts for Indian holidays and runs entirely offline. I validated it against data from manufacturers in [city]."

- [ ] **Answer: Why GA not linear programming?** "Job shop scheduling is NP-hard. LP formulations become computationally intractable at realistic sizes due to the combinatorial explosion in binary assignment variables. A time-bounded GA finds a good solution in 2 minutes. For a production planner running a morning plan, that is strictly more useful than waiting 6 hours for an exact solver."

- [ ] **Answer: How do you know the schedule is good?** "I compared GA output against all four dispatching rules on the same instances. The GA consistently produces lower makespan and lower total tardiness. I also verified fitness convergence — the GA genuinely improves over time, not random search."

- [ ] **Answer: What are the limitations?** "Processing times are assumed deterministic. The GA finds near-optimal solutions, not provably optimal ones. Initial factory setup has some overhead. All of these are documented in LIMITATIONS.md and each has a clear direction to address."

---

## QUICK REFERENCE — What To Do Right Now

Find the first unchecked box in this document. That is what you do next.

If you are blocked on a box, skip it and note it, but come back — later phases depend on earlier ones.

**Never start Phase N+1 before the tests at the end of Phase N pass.**

---

*CROZE Dev Plan — Last updated v3.0*
