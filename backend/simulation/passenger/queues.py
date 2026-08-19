def add_to_queue(sim_state, stop_id, cohort_id, count):
    """
    Adds passengers to a stop's waiting queue.
    """
    if stop_id not in sim_state.stop_queues:
        sim_state.stop_queues[stop_id] = {}
        
    if cohort_id not in sim_state.stop_queues[stop_id]:
        sim_state.stop_queues[stop_id][cohort_id] = 0
        
    sim_state.stop_queues[stop_id][cohort_id] += count
    
    # Update cohort state
    sim_state.passenger_cohorts[cohort_id]['waiting'] += count
    
    # Update max queue size metric
    total_waiting_at_stop = sum(sim_state.stop_queues[stop_id].values())
    if total_waiting_at_stop > sim_state.metrics["max_queue_size"]:
        sim_state.metrics["max_queue_size"] = total_waiting_at_stop
        
    # Update max crowding ratio metric
    stop = sim_state.stops.get(stop_id, {})
    capacity = stop.get('capacity', 0)
    if capacity > 0:
        crowding_ratio = total_waiting_at_stop / capacity
        if crowding_ratio > sim_state.metrics["max_crowding_ratio"]:
            sim_state.metrics["max_crowding_ratio"] = crowding_ratio
def calculate_waiting_time(sim_state, timestep_seconds):
    """
    Called every tick to accumulate waiting time.
    """
    total_waiting_this_tick = 0
    for stop_queues in sim_state.stop_queues.values():
        for count in stop_queues.values():
            total_waiting_this_tick += count
            
    sim_state.metrics["total_waiting_seconds"] += (total_waiting_this_tick * timestep_seconds)
