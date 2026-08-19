from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class Disruption:
    id: int
    type: str  # ROAD_BLOCK, VEHICLE_BREAKDOWN, CROWD_SURGE, WEATHER_HAZARD
    affected_entity_id: str  # Can be edge_id, vehicle_id, or stop_id depending on type
    severity: int  # 1 to 5
    start_time: datetime
    duration_minutes: int
    description: str
    
@dataclass
class BlastRadiusResult:
    disruption_id: int
    directly_affected_edges: List[str]
    directly_affected_vehicles: List[str]
    directly_affected_stops: List[str]
    indirectly_affected_vehicles: List[str]
    indirectly_affected_stops: List[str]
    affected_passengers: int
    propagation_depth: int
    accessibility_impact: bool
    
    # Delta metrics (Disrupted - Baseline)
    delta_passenger_waiting_minutes: float
    delta_average_waiting_minutes: float
    delta_max_queue: int
    delta_max_crowding: float
    
    # Baseline & Disrupted Raw metrics (for frontend viz)
    baseline_metrics: dict
    disrupted_metrics: dict
    
    # Causal chain for explainability
    causal_graph: List[dict]  # [{"depth": 1, "entity": "BUS-01", "reason": "delayed by ROAD_BLOCK"}, ...]
