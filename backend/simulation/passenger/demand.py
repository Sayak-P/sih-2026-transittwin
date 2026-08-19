import uuid
from datetime import datetime, timedelta
from prediction.models import ODDemand

def generate_demand_cohorts(sim_state, start_time, end_time, seed=42):
    """
    Reads ODDemand from the database and initializes aggregated passenger cohorts
    in the SimulationState.
    """
    # Deterministic behavior: We seed random logic if needed, but for Phase 4
    # we just deterministically divide expected demand uniformly across the time window.
    
    # Grab all OD demand that overlaps with our simulation window
    demands = ODDemand.objects.all() # For Phase 4 demo, grab all
    
    for demand in demands:
        # We assume the demand is for this time window for the baseline
        cohort_id = str(uuid.uuid4())
        
        sim_state.passenger_cohorts[cohort_id] = {
            "origin_id": demand.origin_stop.id,
            "destination_id": demand.destination_stop.id,
            "passenger_group": demand.passenger_group,
            "total_generated": demand.expected_passenger_count,
            "waiting": 0,
            "onboard": 0,
            "completed": 0,
            "spawned": 0 # Track how many have been spawned into the queue so far
        }
    
    return len(sim_state.passenger_cohorts)

def spawn_passengers_for_tick(sim_state, tick_seconds, total_duration_seconds):
    """
    Called every simulation tick. Spawns a deterministic fraction of passengers 
    from active cohorts into the stop queues.
    """
    from .queues import add_to_queue

    fraction = tick_seconds / total_duration_seconds if total_duration_seconds > 0 else 1.0

    for cohort_id, cohort in sim_state.passenger_cohorts.items():
        if cohort['spawned'] < cohort['total_generated']:
            # Calculate how many should spawn this tick
            # deterministic math: round(total * (elapsed / total)) - spawned
            # But simple fraction accumulation works. Let's just spawn `fraction * total`
            to_spawn = int(cohort['total_generated'] * fraction)
            
            # Catch up rounding errors on the last few ticks
            if to_spawn == 0 and cohort['total_generated'] > 0:
                to_spawn = 1
                
            to_spawn = min(to_spawn, cohort['total_generated'] - cohort['spawned'])
            
            if to_spawn > 0:
                cohort['spawned'] += to_spawn
                add_to_queue(sim_state, cohort['origin_id'], cohort_id, to_spawn)
                sim_state.metrics["passengers_generated"] += to_spawn
