from typing import Dict, List
from simulation.disruptions.models import BlastRadiusResult

def calculate_blast_radius(disruption_id: int, 
                           baseline_metrics: dict, 
                           disrupted_metrics: dict,
                           causal_graph: List[dict],
                           directly_affected_vehicles: set,
                           directly_affected_stops: set,
                           indirectly_affected_stops: set) -> BlastRadiusResult:
    """
    Compares baseline vs disrupted metrics to determine the network blast radius.
    """
    delta_waiting = (disrupted_metrics.get("total_waiting_seconds", 0) - baseline_metrics.get("total_waiting_seconds", 0)) / 60.0
    delta_avg_waiting = disrupted_metrics.get("average_waiting_minutes", 0) - baseline_metrics.get("average_waiting_minutes", 0)
    delta_max_queue = disrupted_metrics.get("max_queue_size", 0) - baseline_metrics.get("max_queue_size", 0)
    delta_max_crowding = disrupted_metrics.get("max_crowding_ratio", 0) - baseline_metrics.get("max_crowding_ratio", 0)
    
    # Calculate affected passengers (difference in remaining passengers + denied boardings)
    affected_passengers = (disrupted_metrics.get("passengers_remaining", 0) - baseline_metrics.get("passengers_remaining", 0)) + \
                          (disrupted_metrics.get("capacity_denied_boardings", 0) - baseline_metrics.get("capacity_denied_boardings", 0))

    # Calculate propagation depth
    propagation_depth = 0
    if causal_graph:
        propagation_depth = max([node.get("depth", 0) for node in causal_graph])
        
    accessibility_impact = (disrupted_metrics.get("accessibility_denied_boardings", 0) - baseline_metrics.get("accessibility_denied_boardings", 0)) > 0
    
    return BlastRadiusResult(
        disruption_id=disruption_id,
        directly_affected_edges=[], # To be filled based on disruption
        directly_affected_vehicles=list(directly_affected_vehicles),
        directly_affected_stops=list(directly_affected_stops),
        indirectly_affected_vehicles=[], # Vehicles stuck behind direct vehicles
        indirectly_affected_stops=list(indirectly_affected_stops),
        affected_passengers=affected_passengers,
        propagation_depth=propagation_depth,
        accessibility_impact=accessibility_impact,
        delta_passenger_waiting_minutes=delta_waiting,
        delta_average_waiting_minutes=delta_avg_waiting,
        delta_max_queue=delta_max_queue,
        delta_max_crowding=delta_max_crowding,
        baseline_metrics=baseline_metrics,
        disrupted_metrics=disrupted_metrics,
        causal_graph=causal_graph
    )
