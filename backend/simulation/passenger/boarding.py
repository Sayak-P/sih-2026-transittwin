def process_boarding(sim_state, vehicle_id, current_stop_id):
    """
    Boards waiting passengers onto the vehicle up to its available capacity.
    Respects accessibility requirements.
    """
    if current_stop_id not in sim_state.stop_queues:
        return 0
        
    vehicle = sim_state.vehicles[vehicle_id]
    capacity = vehicle.get('capacity', 50) # Fallback to 50 if missing
    occupancy = vehicle.get('occupancy', 0)
    
    available_capacity = capacity - occupancy
    if available_capacity <= 0:
        return 0
        
    queue = sim_state.stop_queues[current_stop_id]
    
    if vehicle_id not in sim_state.vehicle_passengers:
        sim_state.vehicle_passengers[vehicle_id] = {}
        
    onboard = sim_state.vehicle_passengers[vehicle_id]
    
    total_boarded = 0
    
    # Simple FIFO/iterative boarding for Phase 4
    # Note: In a real scenario, we might sort by wait time.
    for cohort_id, waiting_count in list(queue.items()):
        if waiting_count <= 0:
            continue
            
        cohort = sim_state.passenger_cohorts[cohort_id]
        
        # Accessibility check
        if cohort['passenger_group'] == "STEP_FREE_REQUIRED":
            # Very basic check: If the stop or vehicle is not explicitly accessible, reject
            stop = sim_state.stops.get(current_stop_id, {})
            # For phase 4, assume vehicle accessibility via accessible_capacity > 0
            if vehicle.get('accessible_capacity', 0) <= 0 or not stop.get('is_accessible', True):
                sim_state.metrics["accessibility_denied_boardings"] += waiting_count
                continue # Skip this cohort, they cannot board
                
        # Calculate how many can board
        can_board = min(waiting_count, available_capacity)
        
        if can_board > 0:
            total_boarded += can_board
            available_capacity -= can_board
            
            # Update Queue
            queue[cohort_id] -= can_board
            cohort['waiting'] -= can_board
            
            # Update Onboard
            cohort['onboard'] += can_board
            if cohort_id not in onboard:
                onboard[cohort_id] = 0
            onboard[cohort_id] += can_board
            
        # Capacity check
        if available_capacity <= 0:
            # We reached max capacity. Count the remaining queue for metrics
            remaining_in_queue = sum(queue.values())
            sim_state.metrics["capacity_denied_boardings"] += remaining_in_queue
            break
            
    vehicle['occupancy'] += total_boarded
    return total_boarded
