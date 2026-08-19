from simulation.interventions.models import InterventionType, InterventionCandidate
from simulation.state.simulation_state import SimulationState
from core.models import Edge, RouteEdge, Stop

def apply_intervention_to_state(sim_state: SimulationState, candidate: InterventionCandidate):
    """
    Applies the proposed intervention physically to the isolated SimulationState
    before it gets run through the PassengerFlowSimulator.
    """
    if candidate.type == InterventionType.VEHICLE_REROUTE:
        # Override the vehicle's edges based on bypass_edges
        # In PassengerFlowSimulator, the vehicle reads its route. We must modify sim_state.metrics or similar
        # Since PassengerFlowSimulator creates vehicle_routes internally from DB, we need to inject an override
        v_id = candidate.parameters["vehicle_id"]
        bypass_edge_ids = candidate.parameters["bypass_edges"]
        if "route_overrides" not in sim_state.metrics:
            sim_state.metrics["route_overrides"] = {}
        sim_state.metrics["route_overrides"][v_id] = bypass_edge_ids
        
    elif candidate.type == InterventionType.SPARE_VEHICLE_DEPLOYMENT:
        v_id = candidate.parameters["vehicle_id"]
        # Make the vehicle active and assign it a route/capacity
        # For Phase 7, deploy it on the first available route at Stop 1
        if v_id in sim_state.vehicles:
            sim_state.vehicles[v_id]["status"] = "ACTIVE"
            sim_state.vehicles[v_id]["capacity"] = 50
            sim_state.vehicles[v_id]["occupancy"] = 0
            # Inject route override
            if "route_overrides" not in sim_state.metrics:
                sim_state.metrics["route_overrides"] = {}
            # Assume it just follows Edge 1 for demo
            sim_state.metrics["route_overrides"][v_id] = [1]
            
    elif candidate.type == InterventionType.SCHEDULE_MODIFICATION:
        v_id = candidate.parameters["vehicle_id"]
        hold_seconds = candidate.parameters["hold_seconds"]
        if "holds" not in sim_state.metrics:
            sim_state.metrics["holds"] = {}
        sim_state.metrics["holds"][v_id] = hold_seconds
        
    elif candidate.type == InterventionType.TEMPORARY_STOP_CLOSURE:
        stop_id = candidate.parameters["stop_id"]
        if "closed_stops" not in sim_state.metrics:
            sim_state.metrics["closed_stops"] = set()
        sim_state.metrics["closed_stops"].add(stop_id)
