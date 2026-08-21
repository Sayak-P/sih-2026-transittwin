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
    # Helper to safely get numeric values, defaulting to 0 if None
    def safe_get(d, key):
        val = d.get(key, 0)
        return val if val is not None else 0

    delta_waiting = (safe_get(disrupted_metrics, "total_waiting_seconds") - safe_get(baseline_metrics, "total_waiting_seconds")) / 60.0
    delta_avg_waiting = safe_get(disrupted_metrics, "average_waiting_minutes") - safe_get(baseline_metrics, "average_waiting_minutes")
    delta_max_queue = safe_get(disrupted_metrics, "max_queue_size") - safe_get(baseline_metrics, "max_queue_size")
    delta_max_crowding = safe_get(disrupted_metrics, "max_crowding_ratio") - safe_get(baseline_metrics, "max_crowding_ratio")
    
    # Calculate affected passengers (difference in remaining passengers + denied boardings)
    affected_passengers = (safe_get(disrupted_metrics, "passengers_remaining") - safe_get(baseline_metrics, "passengers_remaining")) + \
                          (safe_get(disrupted_metrics, "capacity_denied_boardings") - safe_get(baseline_metrics, "capacity_denied_boardings"))

    # Calculate propagation depth
    propagation_depth = 0
    if causal_graph:
        propagation_depth = max([node.get("depth", 0) for node in causal_graph])
    accessibility_impact = (safe_get(disrupted_metrics, "accessibility_denied_boardings") - safe_get(baseline_metrics, "accessibility_denied_boardings")) > 0
    
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
