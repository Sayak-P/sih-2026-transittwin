from simulation.state.simulation_state import SimulationState
from simulation.disruptions.models import Disruption

def apply_disruption(sim_state: SimulationState, disruption: Disruption):
    """
    Applies the primary impact of a disruption to a SimulationState.
    This strictly defines the ROOT CAUSE (Depth 0) impact.
    The cascading impact happens later during passenger_flow simulation.
    """
    if disruption.type == "ROAD_BLOCK":
        # Affected entity is an Edge ID
        edge_id = disruption.affected_entity_id
        if edge_id not in sim_state.metrics:
            sim_state.metrics["blocked_edges"] = []
        sim_state.metrics["blocked_edges"].append(edge_id)
        
        # We handle the actual delay inside the movement logic of passenger_flow.py
        # by checking if a vehicle is traversing a blocked edge.
        
    elif disruption.type == "VEHICLE_BREAKDOWN":
        vehicle_id = disruption.affected_entity_id
        if vehicle_id in sim_state.vehicles:
            vehicle = sim_state.vehicles[vehicle_id]
            vehicle['capacity'] = 0
            vehicle['accessible_capacity'] = 0
            vehicle['status'] = "BROKEN_DOWN"
            
    elif disruption.type == "CROWD_SURGE":
        # We handle this by artificially inflating passenger cohorts 
        # starting at the affected stop during the simulation horizon.
        stop_id = int(disruption.affected_entity_id)
        surge_multiplier = 1.0 + (disruption.severity * 0.5) # e.g. Sev 4 = 3.0x demand
        
        for cohort in sim_state.passenger_cohorts.values():
            if cohort['origin_id'] == stop_id:
                cohort['total_generated'] = int(cohort['total_generated'] * surge_multiplier)
                
    elif disruption.type == "WEATHER_HAZARD":
        # Affected entity could be "ALL" or a specific region. 
        # For Phase 6, we'll apply a speed multiplier to all vehicles.
        multiplier = max(0.1, 1.0 - (disruption.severity * 0.15)) # e.g. Sev 4 = 40% speed
        sim_state.metrics["weather_speed_multiplier"] = multiplier

