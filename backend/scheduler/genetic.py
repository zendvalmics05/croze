import time
import random
import math
import statistics
from core.models import Schedule
from core.simulation import run_simulation
from scheduler.scheduler import build_schedule

def chromosome_to_schedule(chromosome, factory_model, orders, db_session=None) -> Schedule:
    """
    Converts a priority ordering (chromosome) into a Schedule by running the baseline scheduler.
    """
    def priority_fn(order, machine, current_time):
        order_idx = next(i for i, o in enumerate(orders) if o.id == order.id)
        return chromosome.index(order_idx)
    return build_schedule(factory_model, orders, priority_fn, db_session=db_session)

def fitness(chromosome, factory_model, orders, weights, max_possible_makespan=1.0, db_session=None) -> float:
    """
    Evaluates fitness of a chromosome by running the schedule generation + SimPy simulation.
    """
    schedule = chromosome_to_schedule(chromosome, factory_model, orders, db_session=db_session)
    result = run_simulation(factory_model, schedule, orders, None, factory_model.id, db_session=db_session)
    
    # 1. Normalized Makespan
    makespan_score = result.makespan / max_possible_makespan
    
    # 2. Normalized Tardiness
    max_ref_tardiness = 1440.0  # 24 hours in minutes
    tardiness_score = result.total_tardiness / (len(orders) * max_ref_tardiness) if orders else 0.0
    
    # 3. Utilization Balance (stdev of machine utilizations)
    utilisations = [s.utilisation for s in result.machine_stats.values()]
    balance_score = statistics.stdev(utilisations) if len(utilisations) > 1 else 0.0
    
    return (weights.get('makespan', 0.3) * makespan_score +
          weights.get('tardiness', 0.5) * tardiness_score +
          weights.get('utilisation_balance', 0.2) * balance_score)

def tournament_select(population, fitnesses, k=3):
    """
    Tournament selection: picks k individuals randomly and returns the one with the best (lowest) fitness.
    """
    # fitnesses is aligned with population
    candidates = random.sample(list(range(len(population))), min(k, len(population)))
    best_idx = min(candidates, key=lambda idx: fitnesses[idx])
    return population[best_idx]

def order_crossover(parent1, parent2):
    """
    Order Crossover (OX) for permutation chromosomes.
    """
    size = len(parent1)
    if size < 2:
        return list(parent1)
        
    child = [None] * size
    
    # Select random segment
    start, end = sorted(random.sample(range(size), 2))
    
    # Copy segment from parent1
    for i in range(start, end + 1):
        child[i] = parent1[i]
        
    # Fill remaining slots from parent2 in order
    p2_idx = 0
    for i in range(size):
        if child[i] is None:
            while parent2[p2_idx] in child:
                p2_idx += 1
            child[i] = parent2[p2_idx]
            
    return child

def swap_mutate(chromosome, mutation_rate=0.1):
    """
    Swap mutation: swaps elements with a certain probability.
    """
    mutated = list(chromosome)
    size = len(mutated)
    if size < 2:
        return mutated
        
    for i in range(size):
        if random.random() < mutation_rate:
            j = random.randint(0, size - 1)
            mutated[i], mutated[j] = mutated[j], mutated[i]
    return mutated

def genetic_algorithm(factory_model, orders, weights, time_budget_seconds=120, population_size=100, elite_fraction=0.1, db_session=None):
    """
    Time-bounded Genetic Algorithm optimizer.
    """
    start_time = time.time()
    n = len(orders)
    if n == 0:
        return [], 0.0, 0
        
    population = [random.sample(range(n), n) for _ in range(population_size)]
    best_chromosome = population[0]
    best_fitness = float('inf')
    generation = 0
    
    # Precompute total work for normalization
    total_work = 0.0
    for o in orders:
        prod = next(p for p in factory_model.products if p.id == o.product_id)
        for op in prod.routing:
            mach = next((m for m in factory_model.machines if op.code in m.operation_types), None)
            if mach:
                total_work += mach.cycle_times.get(op.code, 0.0) * o.quantity + mach.setup_times.get(op.code, 0.0)
    max_possible_makespan = max(1.0, total_work)
    
    while (time.time() - start_time) < time_budget_seconds:
        fitnesses = []
        # Evaluate fitness of population while budget permits
        for chrom in population:
            if (time.time() - start_time) >= time_budget_seconds:
                break
            fit_val = fitness(chrom, factory_model, orders, weights, max_possible_makespan, db_session)
            fitnesses.append((chrom, fit_val))
            
        if not fitnesses:
            break
            
        # Sort by fitness (lower is better)
        fitnesses.sort(key=lambda x: x[1])
        
        # Track global best
        if fitnesses[0][1] < best_fitness:
            best_fitness = fitnesses[0][1]
            best_chromosome = list(fitnesses[0][0])
            
        # Elitism
        num_elites = max(1, int(population_size * elite_fraction))
        elites = [x[0] for x in fitnesses[:num_elites]]
        
        new_population = list(elites)
        
        current_pop_chroms = [x[0] for x in fitnesses]
        current_pop_fits = [x[1] for x in fitnesses]
        
        # Populate next generation
        while len(new_population) < population_size:
            if (time.time() - start_time) >= time_budget_seconds:
                break
            p1 = tournament_select(current_pop_chroms, current_pop_fits, k=3)
            p2 = tournament_select(current_pop_chroms, current_pop_fits, k=3)
            child = order_crossover(p1, p2)
            child = swap_mutate(child, mutation_rate=0.1)
            new_population.append(child)
            
        population = new_population
        generation += 1
        
    return best_chromosome, best_fitness, generation
