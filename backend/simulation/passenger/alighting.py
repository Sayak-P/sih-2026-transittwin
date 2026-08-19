def process_alighting(sim_state, vehicle_id, current_stop_id):
    """
    Removes passengers whose destination is the current stop.
    Updates vehicle occupancy and cohort states.
    Returns the number of passengers alighted.
    """
    if vehicle_id not in sim_state.vehicle_passengers:
        return 0
        
    onboard_cohorts = sim_state.vehicle_passengers[vehicle_id]
    vehicle = sim_state.vehicles[vehicle_id]
    
    total_alighted = 0
    cohorts_to_remove = []
    
    for cohort_id, count in onboard_cohorts.items():
        if count <= 0:
            continue
            
        cohort = sim_state.passenger_cohorts[cohort_id]
        
        # Check destination
        if cohort['destination_id'] == current_stop_id:
            # Alight
            total_alighted += count
            cohort['onboard'] -= count
            cohort['completed'] += count
            sim_state.metrics["passengers_served"] += count
            cohorts_to_remove.append(cohort_id)
            
    # Clean up fully alighted cohorts from this vehicle
    for c_id in cohorts_to_remove:
        del onboard_cohorts[c_id]
        
    # Free capacity
    if vehicle.get('occupancy', 0) >= total_alighted:
        vehicle['occupancy'] -= total_alighted
    else:
        vehicle['occupancy'] = 0 # Safety bounds
        
    return total_alighted
