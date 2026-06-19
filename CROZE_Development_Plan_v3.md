# CROZE — Production Scheduling & Factory Diagnostic Tool
### Complete Development Plan — v3.0

| Parameter | Value |
|---|---|
| Build Duration | 4 Months |
| Core Language | Python (backend) + React (frontend) |
| Backend Framework | FastAPI |
| Frontend UI | React + React Flow |
| Simulation Engine | SimPy 4.x |
| Database | SQLite (via SQLAlchemy) |
| Target Market | Indian SME Manufacturers |

---

## 1. Project Philosophy and Goals

CROZE is not a research project. It is not an academic exercise in combinatorial optimisation. It is a practical decision-support tool built for factory operators, production planners, and manufacturing startups in India who need answers to real questions every working day.

The three questions CROZE is designed to answer are:

- Given my machines and my orders, what is the best sequence to run them in?
- Where is my factory losing throughput, and why?
- If something changes — a machine breaks, a new order arrives, a shift is added — what happens to my plan?

Everything in CROZE's design flows from these three questions. Features that do not serve one of them do not belong in the project.

### 1.1 The Three Problems CROZE Solves by Design

> **The Input Problem**
> Factory knowledge lives in people's heads and on paper routecards. A complex database-driven input system will never be filled in. CROZE solves this through a visual factory builder — a node-based canvas built in React Flow where machines and processes are connected graphically, matching the mental model of any production engineer.

> **The Dynamic Reality Problem**
> A schedule generated at 8am is outdated by 10am. Machines break. Urgent orders arrive. Jobs take longer than expected. CROZE solves this by being a what-if engine, not a one-time planner. Any parameter can be changed and the schedule recomputed in seconds.

> **The Adoption Problem**
> A floor supervisor who has scheduled jobs in his head for fifteen years will not blindly follow software output. CROZE solves this by explaining every scheduling decision in plain language, allowing any decision to be overridden, and showing the consequence of that override immediately.

### 1.2 What CROZE Explicitly Is Not

- Not a research benchmarking platform — no OR-Library validation, no Pareto frontiers, no academic metrics
- Not an autonomous system — CROZE recommends, the human decides
- Not an ERP replacement — it solves the scheduling and diagnostic problem only
- Not a cloud SaaS — it runs locally, deployable in factory environments with no internet
- Not an IoT platform — all inputs are manual or file-based; no live machine connectivity required

### 1.3 Target Users

| User | What They Need From CROZE |
|---|---|
| Production Planner | A schedule they can hand to the floor supervisor with confidence |
| Factory Owner / Founder | Bottleneck identification and what-if answers for capacity decisions |
| Operations Manager | Daily replanning when reality deviates from the morning plan |
| Manufacturing Startup CTO | A demonstration that intelligent scheduling is possible without ERP cost |

### 1.4 Indian Manufacturing Context

CROZE is designed specifically around the operational reality of Indian SME manufacturers. This shapes several design decisions that would be absent in a generic scheduling tool.

- Working calendar is state-aware: national holidays, regional holidays (which differ between Tamil Nadu, Maharashtra, and Punjab), and festival shutdowns are first-class inputs, not afterthoughts.
- Offline-first: many production floors in tier-2 cities have unreliable internet. CROZE runs entirely on a local machine.
- Plain-language reports are designed to be printable and hand-distributable to floor supervisors who do not use software.
- The `precision_shop.json` example factory is modelled on a real auto-ancillary component (valve body machining), not a generic textbook example.

---

## 2. System Architecture

CROZE is a full-stack application composed of two independently deployable tiers: a Python backend and a React frontend. This replaces the original Streamlit-only design and enables a production-quality user interface without sacrificing Python's simulation and optimisation ecosystem.

### 2.1 Architecture Overview

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React + React Flow + Recharts | Visual factory builder, schedule display, what-if UI |
| API Layer | FastAPI (Python) | REST endpoints, request validation, response serialisation |
| Scheduler | Pure Python + NumPy | Dispatching rules, genetic algorithm |
| Simulation Core | SimPy 4.x | Discrete event simulation of factory operations |
| Diagnostic Engine | Python + Pandas | Bottleneck analysis, throughput decomposition, report generation |
| Persistence | SQLite via SQLAlchemy | Factory definitions, order history, saved schedules, scenario logs |

### 2.2 Why FastAPI + React Instead of Streamlit

Streamlit is appropriate for internal data science tooling but signals 'prototype' to any engineering team reviewing the project. The FastAPI + React architecture demonstrates the following capabilities that Streamlit cannot:

- Separation of concerns between business logic and UI — the backend is independently testable
- React Flow provides a mature, production-used node-and-edge canvas with reliable drag, connect, and configure interactions — replacing the fragile streamlit-agraph dependency
- The REST API makes CROZE extensible: a mobile app, a CLI tool, or a future ERP integration can consume the same endpoints
- Full-stack architecture is the standard expectation at Indian product companies and startups; demonstrating it on a CV is significantly more valuable than a Streamlit app

### 2.3 Data Flow

- User builds factory graph in React Flow canvas — nodes for machines, buffers, inputs, assemblies
- Frontend serialises graph to JSON and POSTs to `/api/factory/save`
- User enters orders in the order management panel; POSTed to `/api/orders/`
- User triggers schedule generation — POST to `/api/schedule/run` with chosen algorithm
- Backend scheduler generates Schedule object, passes to SimPy simulation
- Simulation produces SimulationResult; diagnostic engine computes KPIs
- DiagnosticReport returned to frontend as JSON; rendered as Gantt chart, utilisation bars, and plain-language report
- All results persisted to SQLite; user can reload any previous run

### 2.4 Core Data Structures

These are the central data structures shared by all backend components. Defining them precisely before building any component prevents ambiguity and integration bugs.

#### Machine

```python
@dataclass
class Machine:
    id: str                        # unique identifier e.g. 'M001'
    name: str                      # human name e.g. 'CNC Lathe #1'
    operation_types: List[str]     # operation codes this machine performs
    cycle_times: Dict[str, float]  # operation_code -> minutes per unit
    setup_times: Dict[str, float]  # operation_code -> setup minutes
    shift_hours: float             # productive hours per shift
    shifts_per_day: int            # number of shifts run per day
    failure_rate: float            # mean time between failures (hours), 0 = never
    repair_time: float             # mean time to repair (hours)
    degradation_factor: float      # cycle time multiplier increase per 100 hours runtime
```

#### Order and Schedule

```python
@dataclass
class Order:
    id: str
    product_id: str
    quantity: int
    due_date: datetime
    priority: int                  # 1 = highest
    release_date: datetime         # earliest start date
    status: str                    # 'pending' | 'in_progress' | 'completed'
    remaining_time_minutes: float  # for in-progress jobs: time left on current op

@dataclass
class ScheduledJob:
    order_id: str
    operation_code: str
    machine_id: str
    start_time: float              # minutes from simulation start
    end_time: float
    setup_time: float

@dataclass
class Schedule:
    jobs: List[ScheduledJob]
    makespan: float
    algorithm_used: str
    generated_at: datetime
    factory_health_score: float    # 0-100 composite score
```

---

## 3. Persistence Layer

The original v2 plan had no persistence. CROZE v3 uses SQLite via SQLAlchemy for all stateful data. This is a non-negotiable addition: without it, CROZE is a demo tool, not a daily operations tool. SQLite requires no server process, installs with Python, and is appropriate for a single-factory deployment.

### 3.1 Database Schema

| Table | Contents | Key Fields |
|---|---|---|
| factories | Saved factory definitions as JSON blobs | id, name, json_definition, created_at, updated_at |
| orders | All orders entered for a factory | id, factory_id, product_id, quantity, due_date, priority, status |
| schedules | Generated schedules with full job assignments | id, factory_id, algorithm, generated_at, makespan, health_score, json_result |
| scenarios | What-if scenario runs and their results | id, base_schedule_id, scenario_type, params_json, result_json, created_at |
| working_calendar | Factory-specific working days and holidays | id, factory_id, date, is_working, shift_override |

### 3.2 Save / Load Factory

The frontend provides 'Save Factory', 'Load Factory', and 'Recent Factories' controls. The factory definition — the full node-and-edge graph with all machine properties — is serialised to JSON and stored in the factories table. Saved factories load instantly with all node positions preserved.

### 3.3 Schedule History

Every schedule run is saved automatically. The Schedule & Diagnostics panel includes a history sidebar showing previous runs for the same factory, with makespan and health score visible at a glance. A user can load any previous run and compare it against the current one. This allows week-over-week tracking of factory health.

---

## 4. Working Calendar

The simulation models machine availability using a working calendar — not a flat 'hours per day' assumption. This is critical for Indian factories, where national holidays, state-specific holidays, and festival shutdowns create irregular working patterns that a flat model misrepresents.

### 4.1 Calendar Inputs

- National public holidays: pre-loaded for India (Republic Day, Independence Day, Gandhi Jayanti, etc.)
- State holidays: user selects their state; state-specific holidays auto-populate (Pongal in Tamil Nadu, Gudi Padwa in Maharashtra, Baisakhi in Punjab, etc.)
- Factory-specific closures: user marks additional closure days (maintenance shutdowns, local festivals)
- Shift overrides: specific days can have custom shift patterns (e.g., half-day before Diwali)
- Overtime periods: specific weeks can have extended shifts (e.g., Q4 peak season)

### 4.2 How Calendar Affects Simulation

The SimPy simulation clock runs in minutes from a reference start datetime. Before a job can be scheduled on a machine, the scheduler checks whether the target start time falls within a working shift on a working day. Non-working time is represented as machine unavailability — the machine resource is not requestable during those windows. This means the simulation naturally pushes jobs to the next available working slot without special-case code.

### 4.3 Calendar UI

The calendar is a dedicated panel in the React frontend — a monthly grid view where each day is colour-coded: green (working, standard shifts), amber (working, reduced shifts), red (non-working). Users can click any day to override its status. The calendar definition is stored per-factory in the `working_calendar` table.

---

## 5. The Visual Factory Builder

The visual factory builder is implemented as a React Flow canvas — a production-quality, actively maintained library used by companies including Stripe and Typeform for node-and-edge interfaces. This replaces the fragile streamlit-agraph dependency from v2 and eliminates the entire category of UI reliability risk.

### 5.1 Node Types

| Node Type | Visual Style | Properties |
|---|---|---|
| Machine Node | Blue rounded rectangle | Name, operation types, cycle times, setup times, shift pattern, failure rate, degradation |
| Buffer Node | Orange diamond | Name, capacity (max units), queue discipline (FIFO/LIFO/Priority) |
| Input Node | Green circle | Material name, current stock quantity |
| Output Node | Red circle | Product name, represents routing completion |
| Assembly Node | Purple hexagon | Merges parallel process streams; requires all inputs before proceeding |

### 5.2 React Flow Implementation

```javascript
// Node types registered with React Flow
const nodeTypes = {
  machine: MachineNode,
  buffer: BufferNode,
  input: InputNode,
  output: OutputNode,
  assembly: AssemblyNode,
};

// Each custom node renders with React Flow's Handle components
// Handles define connection points; React Flow enforces valid edge creation
function MachineNode({ data, selected }) {
  return (
    <div className={`machine-node ${selected ? 'selected' : ''}`}>
      <Handle type='target' position={Position.Left} />
      <div className='node-label'>{data.name}</div>
      <div className='node-ops'>{data.operation_types.join(', ')}</div>
      <Handle type='source' position={Position.Right} />
    </div>
  );
}
```

### 5.3 Node Configuration Panel

Clicking any node opens a slide-in configuration panel on the right side of the canvas. The panel is context-sensitive — machine nodes show different fields than buffer nodes. All changes are applied immediately and reflected in the canvas. The factory definition is auto-saved to the backend every 30 seconds, with a manual Save button for explicit saves.

### 5.4 Validation

Before a schedule can be generated, the frontend validates the factory graph and highlights errors inline on the offending nodes:

- Every machine must have at least one operation type with a non-zero cycle time
- The routing graph must be a directed acyclic graph — cycles are highlighted in red
- Every product routing must have a reachable path from at least one Input node to the Output node
- Assembly nodes must have at least two incoming process edges
- Setup times must be non-negative

---

## 6. The Simulation Core

The simulation core is the engine that everything else depends on. It must be correct before anything else is built. CROZE uses SimPy, a discrete event simulation library for Python. In discrete event simulation, the system state changes only at discrete points in time. Between events, nothing changes. This matches manufacturing exactly.

### 6.1 SimPy Concepts Mapped to Manufacturing

| SimPy Concept | Factory Mapping |
|---|---|
| `simpy.Environment` | The simulation clock. All events scheduled relative to `env.now` (in minutes) |
| `simpy.Resource` | A machine. `capacity=1` means one job at a time |
| `resource.request()` | A job requesting access to a machine; waits if machine is busy |
| `env.timeout(duration)` | Time passing — processing, setup, repair, or shift gap |
| `simpy.Process` | A job moving through its routing, or a failure cycle running concurrently |
| `simpy.Container` | A buffer with finite capacity |

### 6.2 Shift-Aware Simulation Clock

A key addition in v3 is shift-aware time handling. The simulation does not simply run machines continuously. Before every `env.timeout` call, the scheduler checks whether the machine is in an active shift window. If not, the job waits until the next shift start. This is implemented as a helper that computes the next available working minute given the current simulation time and the working calendar.

```python
def next_working_minute(current_time: float, machine: Machine,
                        calendar: WorkingCalendar) -> float:
    """
    Given current simulation time (minutes from epoch),
    return the next minute at which this machine is available.
    Returns current_time if already in a working shift.
    """
    dt = sim_time_to_datetime(current_time)
    if calendar.is_working_time(dt, machine):
        return current_time
    next_dt = calendar.next_shift_start(dt, machine)
    return datetime_to_sim_time(next_dt)
```

### 6.3 Partial Schedule Support

A critical v3 addition: the simulation supports a factory that is already mid-production. Jobs with `status='in_progress'` are initialised with a `remaining_time_minutes` value — the estimated time left on their current operation. These jobs enter the simulation already in progress, meaning the resulting schedule correctly represents the current state of the floor, not a hypothetical clean start. This makes same-day replanning accurate.

### 6.4 Machine Failure Model

Machine failures run as concurrent SimPy processes, independent of job processes. A failure process interrupts any job currently on the machine. The job is re-queued and resumes processing after repair. Inter-failure times and repair times are sampled from exponential distributions parameterised by the machine's `failure_rate` and `repair_time` properties.

### 6.5 Feasibility Check

Before running the full simulation, CROZE performs a rapid feasibility check: can the total work content of all orders be completed within their due dates given the available machine capacity and the working calendar? If not, a clear infeasibility report is returned immediately, distinguishing between two cases:

- **Scheduling infeasibility:** capacity exists, but the sequencing is wrong — solvable by the scheduler
- **Capacity infeasibility:** the orders cannot be completed even with perfect scheduling — requires due date negotiation, overtime, or additional machines. The report names the specific orders at risk and quantifies the shortfall in machine-hours.

---

## 7. The Scheduler and Optimiser

The scheduler assigns jobs to machines and determines their execution order. CROZE implements two scheduling modes: a fast reactive mode using dispatching rules, and a deliberate planning mode using a genetic algorithm with a configurable time budget.

### 7.1 Dispatching Rules (Fast Mode)

Dispatching rules are simple priority functions that decide which job in a machine's queue gets processed next. They run in microseconds and produce reasonable schedules for daily replanning.

| Rule | Priority Logic | Best Used When |
|---|---|---|
| Shortest Processing Time (SPT) | Job with shortest remaining processing time goes first | All jobs equally important; minimise average completion time |
| Earliest Due Date (EDD) | Job with nearest due date goes first | Deadlines are contractual; missing any one is costly |
| Critical Ratio (CR) | Ratio of time remaining to work remaining. CR < 1 = behind schedule | Mixed-deadline environments; most useful rule in practice |
| Minimum Setup (MS) | Prefer job requiring least setup on current machine | When setup times are large relative to cycle times (precision machining) |

### 7.2 The Genetic Algorithm (Planning Mode)

The genetic algorithm searches for a job sequence that minimises a weighted objective function. In v3, the GA runs within a configurable time budget — it does not run for a fixed number of generations. This prevents the UI from appearing frozen and makes the tool usable in practice.

#### Time-Bounded GA Loop

```python
def genetic_algorithm(factory_model, orders, weights,
                      time_budget_seconds=120,   # default: 2 minutes
                      population_size=100,
                      elite_fraction=0.1):
    start_time = time.time()
    population = [random.sample(range(len(orders)), len(orders))
                  for _ in range(population_size)]
    best_chromosome = population[0]
    best_fitness = float('inf')
    generation = 0

    while (time.time() - start_time) < time_budget_seconds:
        fitnesses = [fitness(c, factory_model, orders, weights)
                     for c in population]
        gen_best = min(range(len(fitnesses)), key=lambda i: fitnesses[i])
        if fitnesses[gen_best] < best_fitness:
            best_fitness = fitnesses[gen_best]
            best_chromosome = population[gen_best].copy()
        population = evolve(population, fitnesses, elite_fraction)
        generation += 1

    return best_chromosome, best_fitness, generation
```

#### Fitness Function

The fitness function evaluates a chromosome by converting it to a schedule, running the simulation, and computing a weighted sum of objectives. The weights are user-configurable in the UI.

```python
def fitness(chromosome, factory_model, orders, weights):
    schedule = chromosome_to_schedule(chromosome, factory_model, orders)
    result = run_simulation(factory_model, schedule)

    makespan_score = result.makespan / max_possible_makespan
    tardiness_score = result.total_tardiness / (len(orders) * max_ref_tardiness)
    utilisations = [s.utilisation for s in result.machine_stats.values()]
    balance_score = statistics.stdev(utilisations) if len(utilisations) > 1 else 0

    return (weights['makespan']            * makespan_score +
            weights['tardiness']           * tardiness_score +
            weights['utilisation_balance'] * balance_score)
```

---

## 8. The Diagnostic Engine

The diagnostic engine transforms CROZE from a simulation tool into a decision-support tool. It consumes the SimulationResult and produces human-readable, actionable insight. Every output must be interpretable by someone who has never seen the code.

### 8.1 Factory Health Score

The health score is a single number from 0 to 100 representing the overall operational condition of the factory for a given schedule. It is computed from three normalised components:

| Component | Weight | Computation |
|---|---|---|
| On-time delivery rate | 40% | Fraction of orders completed before due date |
| Bottleneck utilisation balance | 35% | Inverse of standard deviation of machine utilisations; higher is more balanced |
| Setup efficiency | 25% | 1 minus the ratio of total setup time to total available time |

The health score is stored with every schedule run, enabling week-over-week comparison. A factory owner can track a single number and see whether changes they made — adding a shift, adjusting a due date, changing a job sequence — moved the score up or down.

### 8.2 Bottleneck Identification

A bottleneck is identified using a weighted combination of machine utilisation and average queue length, both normalised to [0,1]. The machine with the highest combined score is the bottleneck. The diagnostic output explains this in plain language and quantifies the throughput impact of relieving it.

### 8.3 Feasibility and Infeasibility Reporting

When the feasibility check (Section 6.5) identifies capacity infeasibility, the diagnostic engine produces a structured report that a factory owner can act on immediately:

```
CAPACITY INFEASIBILITY REPORT

The following orders CANNOT be completed on time with current capacity,
even with optimal scheduling.

  ORD-047  (200 units Product A, due 15-Mar)  -->  Shortfall: 8.4 machine-hours
             Root cause: M003 (Surface Grinder) has insufficient shift capacity
             Options: (1) Add one shift to M003  (2) Push due date by 1.5 days
                      (3) Split order: external grinding for 80 units

  ORD-052  (150 units Product B, due 16-Mar)  -->  Shortfall: 3.1 machine-hours
             Root cause: ORD-047 consuming M003 capacity needed by ORD-052
             Resolves automatically if ORD-047 due date is pushed.
```

### 8.4 Export

Every diagnostic run can be exported in two formats:

- **PDF diagnostic report:** one-page summary with bottleneck identification, throughput losses, deadline risk table, and Gantt chart. Generated using ReportLab. Designed to be printable and distributable to floor supervisors.
- **Excel export:** full event log, machine utilisation table, job statistics, and schedule as a Gantt data table. Generated using openpyxl. For factory owners who want to work further in spreadsheets.

---

## 9. The What-If Engine

The what-if engine allows any factory parameter to be changed, the schedule recomputed, and the results compared side-by-side against the baseline. Every scenario is a modified copy of the FactoryModel or OrderList fed to the same simulation and diagnostic pipeline — no special-case code.

### 9.1 Pre-Built Scenario Types

| Scenario | User Inputs | Output |
|---|---|---|
| New Order Feasibility | Product ID, quantity, desired due date | Can this be delivered on time? Which existing orders are displaced and by how much? |
| Machine Breakdown | Machine, breakdown start, expected repair time | Which orders are now late? What is the fastest recovery path? |
| Add a Shift | Machine, number of additional shifts | Throughput increase, bottleneck change, on-time rate change, health score delta |
| Add a Machine | New machine node with full configuration | New bottleneck, throughput increase, makespan reduction |
| Supplier Delay | Material, delay in days | Cascade of affected orders, revised schedule, new late orders |

### 9.2 Scenario Comparison Output

| Metric | Baseline | Scenario: Add Grinder Shift |
|---|---|---|
| Makespan | 5 days 4.2 hrs | 4 days 7.1 hrs  ▼ 17% |
| On-time rate | 74% | 91%  ▲ 17pp |
| Total tardiness | 18.4 hrs | 3.1 hrs  ▼ 83% |
| Factory health score | 61 / 100 | 84 / 100  ▲ 23pts |
| Bottleneck | M003 Surface Grinder (91.4%) | M002 Milling Centre (76.2%) |

---

## 10. The React Frontend

The frontend is a React single-page application with four main panels accessible via a sidebar navigation. The design aesthetic is a professional operations dashboard — dark sidebar, clean white content area, data-dense but not cluttered.

### 10.1 Panel Layout

| Panel | Contents and Purpose |
|---|---|
| Factory Builder | React Flow canvas. Node palette on left. Configuration panel slides in on node click. Save/load/recent controls in header. |
| Orders | Table of current orders. Add/edit/delete. CSV import. Status indicators (on-track, at-risk, late). Working calendar access. |
| Schedule & Diagnostics | Algorithm selector (dispatching rule vs GA) with time budget slider for GA. Run button. Plotly Gantt chart. Health score gauge. Diagnostic report. Machine utilisation bars. Export buttons. |
| What-If | Scenario selector. Parameter inputs. Side-by-side comparison table. Scenario Gantt overlaid on baseline in a different colour. Scenario history. |

### 10.2 Technology Choices

| Component | Library | Reason |
|---|---|---|
| Factory canvas | React Flow | Production-quality node-and-edge canvas; reliable drag/connect/configure; replaces fragile streamlit-agraph |
| Gantt chart | Plotly.js via react-plotly.js | Interactive, hoverable bars; native support for colour-coding by order; exportable |
| Utilisation charts | Recharts | Lightweight bar and gauge charts; React-native; easy to theme |
| UI components | shadcn/ui + Tailwind CSS | Consistent, professional component library; no design overhead |
| State management | React Query | Server state synchronisation; handles loading/error states for all API calls |
| API communication | Axios | REST calls to FastAPI backend |

### 10.3 The Gantt Chart

Each bar represents one job on one machine. Bars are colour-coded by order. Hovering shows job ID, operation, start time, end time, queue wait time, and on-time status. A vertical line marks the current simulation time. Red-bordered bars indicate tardy jobs. Shift boundaries are shown as subtle vertical shading — grey for non-working hours, white for working hours. This makes it immediately visible when jobs are being delayed by shift boundaries versus machine queues.

---

## 11. The FastAPI Backend

The FastAPI backend exposes all scheduling, simulation, and diagnostic functionality as REST endpoints. It is the only component the React frontend communicates with. The simulation and optimisation code is entirely backend-side; the frontend is purely a display and input layer.

### 11.1 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/factory/save` | Save or update a factory definition |
| GET | `/api/factory/{id}` | Load a saved factory |
| GET | `/api/factory/list` | List all saved factories with metadata |
| POST | `/api/orders/` | Add or update an order |
| GET | `/api/orders/{factory_id}` | Get all orders for a factory |
| POST | `/api/schedule/run` | Generate a schedule; returns schedule + diagnostic report |
| GET | `/api/schedule/history/{factory_id}` | List previous schedule runs |
| POST | `/api/whatif/run` | Run a what-if scenario against a base schedule |
| GET | `/api/calendar/{factory_id}` | Get working calendar for a factory |
| PUT | `/api/calendar/{factory_id}` | Update working calendar |
| POST | `/api/export/pdf/{schedule_id}` | Generate and return PDF diagnostic report |
| POST | `/api/export/excel/{schedule_id}` | Generate and return Excel export |

### 11.2 Schedule Run Response

The `/api/schedule/run` endpoint is the core endpoint. It accepts a factory ID, order list, algorithm choice, and algorithm parameters. It returns a comprehensive response including the full schedule, simulation result, and diagnostic report — everything the frontend needs to render all panels.

```json
// POST /api/schedule/run
// Request body:
{
  "factory_id": "F001",
  "algorithm": "genetic",
  "time_budget_seconds": 120,
  "weights": {"makespan": 0.3, "tardiness": 0.5, "utilisation_balance": 0.2}
}

// Response:
{
  "schedule": { "jobs": [...], "makespan": 4821.3, "health_score": 84 },
  "machine_stats": { "M001": { "utilisation": 0.82, "avg_queue": 1.2 } },
  "job_stats": { "ORD-047": { "on_time": true, "margin_minutes": 92 } },
  "bottleneck": { "machine_id": "M002", "explanation": "..." },
  "throughput_losses": { "M001": { "idle": 0.11, "setup": 0.04, "failure": 0.03 } },
  "deadline_risks": [ { "order_id": "ORD-052", "status": "AT_RISK" } ],
  "plain_language_report": "..."
}
```

---

## 12. Real-World Data Validation

The project's strongest differentiator is validation against real Indian manufacturing data. This section defines the outreach strategy, what data to ask for, and how it is used in the project.

### 12.1 LinkedIn Outreach Strategy

The goal is to obtain anonymised factory data from 2–4 Indian SME manufacturers before or during Month 2, so the example factories in CROZE reflect real operational parameters rather than textbook approximations.

#### Who to Approach

- Production managers, operations heads, and founders at auto-ancillary manufacturers in Pune and Chennai
- Precision engineering shops in Coimbatore (pumps, motors, castings)
- Fastener and engineering goods manufacturers in Rajkot and Ludhiana
- CII (Confederation of Indian Industry) MSME network contacts
- Startup founders in the manufacturing-tech space who have worked with shop floors

#### What to Ask For

Do not ask for sensitive data cold. Sequence the outreach correctly:

- First message: request a 20-minute conversation to understand their production planning challenges — not data
- In the conversation: ask about machine count, product types, typical order volumes, biggest scheduling pain points
- If trust is established: ask for anonymised data — machine cycle times, typical routing sequences, shift patterns. Offer a simple NDA upfront.
- What you do not need: customer names, order values, pricing, proprietary product designs

#### How It Appears in the Project

- The `precision_shop.json` example factory is modelled on a real product type (e.g., valve body machining or pump casing)
- The README states "validated against operational data from Indian SME manufacturers"
- In an interview: "I spoke with three production managers in Coimbatore and Pune and used their cycle time ranges and shift patterns to build the example factory"

---

## 13. Build Plan: Four Months

The build plan restructures the original three-month plan into four months. The fourth month is not scope expansion — it is realism. Month 3 in v2 attempted diagnostics, what-if engine, and a complete interface in four weeks. That was underscoped. The extra month is spent on integration, validation, and polish.

### Month 1 — Simulation Core + Persistence

> **Goal:** A working SimPy simulation that correctly models a small factory, produces numbers you can manually verify, and saves/loads factory definitions from SQLite.

#### Week 1–2: Data Model and Simulation Foundation

- Set up project structure: `/backend` (FastAPI + SimPy + scheduler + diagnostics), `/frontend` (React), `/tests`
- Implement all dataclasses: Machine, Product, Operation, Order, Schedule, SimulationResult
- Implement SQLAlchemy models and SQLite schema: factories, orders, schedules, scenarios, working_calendar tables
- Implement `job_process` generator for single-operation jobs with shift-aware clock
- Write validation test: 3 machines, 5 jobs, verify completion times by hand

#### Week 3: Multi-Operation Routing, Failures, Partial Schedules

- Extend `job_process` to handle multi-operation routings
- Implement `machine_failure_process` with preemption
- Implement machine degradation: cycle time drift with runtime
- Implement partial schedule support: in-progress jobs initialised with `remaining_time_minutes`
- Implement working calendar model with national and state holidays

#### Week 4: FastAPI Foundation + Assembly

- Implement FastAPI app with all endpoints stubbed
- Wire simulation to `/api/schedule/run` endpoint; test end-to-end with curl
- Implement `assembly_process` with SimPy AllOf synchronisation
- Implement save/load factory to SQLite via `/api/factory` endpoints
- Implement feasibility check with infeasibility report

---

### Month 2 — Scheduler, Optimiser, and React Foundation

> **Goal:** Working dispatching rules and GA that demonstrably outperforms any single rule; React frontend connected to the backend with factory builder and order panel functional.

#### Week 5–6: Dispatching Rules and React Setup

- Implement SPT, EDD, Critical Ratio, and Minimum Setup dispatching rules
- Set up React project with React Flow, Recharts, Tailwind, shadcn/ui
- Implement basic four-panel layout with sidebar navigation
- Implement React Flow canvas with all five node types
- Connect factory builder save to `/api/factory/save` — round-trip test

#### Week 7–8: Genetic Algorithm + Order Panel

- Implement GA with time-bounded loop, tournament selection, Order Crossover, swap mutation, elitism
- Implement fitness function with configurable weights
- Convergence test: fitness must decrease or plateau over time budget
- Comparison test: GA must outperform best dispatching rule on 20-job, 6-machine instance
- Implement order management panel with add/edit/delete and CSV import
- Implement working calendar UI panel
- **Begin LinkedIn outreach to Indian manufacturers this week**

---

### Month 3 — Diagnostics, What-If, and Interface Integration

> **Goal:** Complete, connected application: factory builder to schedule to diagnostics to what-if, all working end-to-end with real data in the example factories.

#### Week 9–10: Diagnostic Engine

- Implement factory health score computation
- Implement bottleneck identification with plain-language explanation
- Implement throughput analysis with idle/failure/setup loss decomposition
- Implement deadline risk analysis with infeasibility reports
- Implement plain-language report generator
- Connect diagnostics to frontend: health score gauge, utilisation bars, report panel

#### Week 11–12: What-If Engine + Gantt Chart

- Implement all five what-if scenario types
- Implement scenario comparison table generator
- Connect what-if to frontend with scenario selector and comparison table
- Implement Plotly Gantt chart with shift boundary shading and tardiness highlighting
- End-to-end test: describe a real factory (from LinkedIn data), generate schedule, read report, run two what-if scenarios

---

### Month 4 — Export, Polish, and CV Packaging

> **Goal:** A project that is publicly demonstrable, professionally documented, and ready to discuss in an interview. No new features — only quality.

#### Week 13–14: Export and Example Factories

- Implement PDF diagnostic report export using ReportLab
- Implement Excel export using openpyxl
- Build `simple_factory.json`: 3-machine, 5-job demo, runnable in under 10 seconds
- Build `precision_shop.json`: 6-machine factory modelled on real Indian manufacturing data from outreach
- Write pytest test suite covering simulation correctness, GA convergence, OX validity

#### Week 15–16: Documentation and Demo

- Write README with problem statement, architecture diagram, installation instructions, and demo walkthrough
- Record a 3-minute screen demo: load precision_shop, run GA schedule, read diagnostic report, run one what-if scenario
- Write LIMITATIONS.md: processing time variance, GA non-optimality, manual input requirement, single-factory deployment
- Clean up GitHub repository: clear commit history, `.gitignore`, `requirements.txt`, `package.json` pinned
- Prepare the 30-second and 2-minute verbal pitches from Section 17

---

## 14. Technical Stack

| Component | Library / Tool | Reason for Choice |
|---|---|---|
| Simulation | SimPy 4.x | Industry-standard discrete event simulation for Python; generator-based, readable |
| Genetic Algorithm | Pure Python + NumPy | No external dependency; NumPy for fast array operations on population |
| Data Model | Python dataclasses | Typed, lightweight, no ORM overhead |
| Backend API | FastAPI | Fastest Python web framework; automatic OpenAPI docs; async support |
| Database ORM | SQLAlchemy + SQLite | Zero-config database; SQLAlchemy provides migration path to PostgreSQL if needed |
| Frontend Framework | React 18 | Industry standard; required skill at most Indian product companies |
| Factory Canvas | React Flow | Production-quality node-and-edge canvas; replaces fragile streamlit-agraph |
| Gantt Chart | Plotly.js / react-plotly.js | Interactive, hoverable, exportable; native support for manufacturing visualisations |
| UI Charts | Recharts | Lightweight React-native charts for utilisation bars and health score gauge |
| UI Components | shadcn/ui + Tailwind CSS | Consistent professional design without custom CSS overhead |
| PDF Export | ReportLab | Python-native PDF generation; no external dependencies |
| Excel Export | openpyxl | Python-native .xlsx generation |
| Testing | pytest | Unit tests for simulation correctness, scheduler validation, GA properties |
| Serialisation | JSON + SQLAlchemy | Factory model save/load; human-readable, version-controllable JSON |

---

## 15. Project Structure

```
croze/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/
│   │   ├── factory.py           # /api/factory endpoints
│   │   ├── orders.py            # /api/orders endpoints
│   │   ├── schedule.py          # /api/schedule endpoints
│   │   ├── whatif.py            # /api/whatif endpoints
│   │   ├── calendar.py          # /api/calendar endpoints
│   │   └── export.py            # /api/export endpoints
│   ├── core/
│   │   ├── models.py            # All dataclasses
│   │   ├── simulation.py        # SimPy simulation engine
│   │   ├── calendar_model.py    # Working calendar logic
│   │   └── factory_model.py     # FactoryModel and graph serialisation
│   ├── scheduler/
│   │   ├── dispatching.py       # SPT, EDD, Critical Ratio, Minimum Setup
│   │   ├── genetic.py           # Time-bounded GA
│   │   └── scheduler.py         # Scheduler orchestrator
│   ├── diagnostics/
│   │   ├── bottleneck.py
│   │   ├── throughput.py
│   │   ├── deadline.py
│   │   ├── health_score.py      # Factory health score computation
│   │   ├── feasibility.py       # Infeasibility detection and reporting
│   │   ├── report.py            # Plain language report generator
│   │   └── whatif_engine.py
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine and session
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── migrations/
│   └── export/
│       ├── pdf_exporter.py      # ReportLab PDF generation
│       └── excel_exporter.py    # openpyxl Excel generation
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── panels/
│   │   │   ├── FactoryBuilder/
│   │   │   │   ├── index.jsx
│   │   │   │   ├── nodes/       # MachineNode, BufferNode, etc.
│   │   │   │   └── ConfigPanel.jsx
│   │   │   ├── Orders/
│   │   │   ├── ScheduleDiagnostics/
│   │   │   │   ├── GanttChart.jsx
│   │   │   │   ├── HealthScore.jsx
│   │   │   │   └── DiagnosticReport.jsx
│   │   │   └── WhatIf/
│   │   ├── components/          # Shared UI components
│   │   └── api/                 # Axios API client
│   ├── package.json
│   └── tailwind.config.js
├── tests/
│   ├── test_simulation.py
│   ├── test_scheduler.py
│   ├── test_diagnostics.py
│   └── test_ga_properties.py
├── examples/
│   ├── simple_factory.json
│   └── precision_shop.json
├── requirements.txt
├── README.md
└── LIMITATIONS.md
```

---

## 16. Testing and Validation Strategy

A simulation that produces wrong numbers is worse than no simulation at all. The testing strategy covers simulation correctness, scheduler properties, GA mathematical validity, and end-to-end pipeline verification.

### 16.1 Simulation Correctness Tests

| Test | Setup | Expected Result |
|---|---|---|
| Single machine, single job | 1 machine, cycle time 10 min/unit, 1 job of 50 units, no failures | Completion at exactly 500 minutes. Tolerance: 0.01%. |
| Two machines in series | Machine A: 8 min/unit. Machine B: 12 min/unit. 10 jobs of 1 unit. | Queue builds in front of B. A not always busy. Manual makespan verifiable. |
| Machine utilisation | 1 machine, 480 available minutes, 300 minutes of work | Utilisation = 62.5% within 0.1%. |
| Assembly synchronisation | Parallel lines: A=100 min, B=150 min, converge at assembly node | Assembly starts at t=150, not t=100. Validates AllOf. |
| Shift boundary | 8-hour shift, job released at shift end | Job deferred to next shift start; no fractional shift processing. |
| Partial schedule | Job in_progress with 30 min remaining | Job completes 30 min into simulation, not from scratch. |

### 16.2 Scheduler and GA Tests

- EDD must produce lower maximum tardiness than SPT on a due-date-varied instance (provably true; implementation must agree)
- GA fitness must strictly decrease or plateau over the time budget — never increase from generation to generation
- GA must outperform best dispatching rule on a 20-job, 6-machine instance (measured over 5 independent runs)
- Order Crossover validity: for 10,000 random parent pairs, every child must be a valid permutation (no repeats, no missing genes)
- Time budget: GA must return within 5 seconds of the requested `time_budget_seconds`

### 16.3 End-to-End Validation

Build the `precision_shop.json` example factory: 6 machines, 3 product types, 12 orders over 5 working days. Run full pipeline. Verify:

- Bottleneck identified is consistent with manual utilisation calculation from the event log
- All on-time orders have completion times before their due dates in the event log
- "Add a shift to bottleneck" what-if scenario strictly increases on-time rate (cannot decrease it)
- GA produces strictly lower makespan than best dispatching rule
- Factory health score increases after every what-if scenario that adds capacity
- Save factory, restart server, load factory — all nodes, edges, and properties preserved exactly

---

## 17. The Internship Pitch

When you sit in front of an engineering team and they ask what you built, here is the complete answer. Every word is true, every claim is backed by what you have built.

### 17.1 The 30-Second Version

> I built CROZE — a production scheduling and factory diagnostic tool targeting Indian SME manufacturers. You describe your factory: machines, products, process flows, orders, and working calendar including Indian holidays. CROZE simulates your production, generates an optimised schedule using a genetic algorithm, identifies your bottleneck in plain English, tells you where your throughput is being lost, and lets you run what-if scenarios in seconds. It outputs a printable diagnostic report and Gantt chart. I validated it against operational data from manufacturers in Coimbatore and Pune.

### 17.2 Technical Depth for an Engineering Interview

> The simulation core uses SimPy discrete event simulation with a shift-aware clock that respects an Indian working calendar — national holidays, state holidays, and overtime periods. Machine failures run as concurrent preemptible processes. The scheduler implements four dispatching rules and a time-bounded genetic algorithm: you tell it how long to run and it returns the best solution found. The GA uses permutation encoding with Order Crossover — standard crossover doesn't work on permutations because it creates duplicate jobs. The fitness function is a weighted combination of makespan, total tardiness, and utilisation balance. The diagnostic engine computes a factory health score, identifies the bottleneck using utilisation-queue weighting, decomposes throughput losses into idle, failure, and setup components, and generates a plain-language report for floor supervisors. The backend is FastAPI with SQLite persistence; the frontend is React with React Flow for the factory builder and Plotly for the Gantt chart.

### 17.3 Questions They Will Ask

| Question | Answer |
|---|---|
| Why GA and not linear programming? | Job shop scheduling is NP-hard. LP relaxations become computationally intractable at realistic sizes — 20+ jobs, 5+ machines — due to combinatorial explosion in binary assignment variables. A time-bounded GA finds a good solution in 2 minutes. For a production planner running a morning plan, that tradeoff is strictly better than a 6-hour exact solver. |
| How do you know the schedule is good? | I compared GA output against all four dispatching rules on the same instances. The GA consistently produces lower makespan and lower total tardiness. I also tracked fitness convergence to verify the GA is genuinely improving, not randomly searching. |
| Why FastAPI + React instead of Streamlit? | Streamlit is appropriate for internal data science notebooks. A production tool for daily factory operations needs a persistent state layer, a reliable interactive canvas, and a separation between business logic and UI that Streamlit cannot provide. The FastAPI + React architecture also demonstrates full-stack capability, which Streamlit doesn't. |
| What are the limitations? | Processing times are assumed deterministic; in reality they have variance. The GA finds good solutions but not provably optimal ones. Initial factory setup requires some effort from the user. These are known and documented — there are clear directions to address each one. |

---

*CROZE Development Plan v3.0*

**Build it. Four months. Ship it.**
