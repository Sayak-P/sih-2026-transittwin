from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

class InterventionType:
    VEHICLE_REROUTE = "VEHICLE_REROUTE"
    SCHEDULE_MODIFICATION = "SCHEDULE_MODIFICATION"
    SPARE_VEHICLE_DEPLOYMENT = "SPARE_VEHICLE_DEPLOYMENT"
    TEMPORARY_STOP_CLOSURE = "TEMPORARY_STOP_CLOSURE"

@dataclass
class InterventionCandidate:
    id: str
    scenario_id: str
    type: str
    parameters: dict
    description: str
    generated_at: datetime = field(default_factory=datetime.now)
    feasibility_status: str = "FEASIBLE" # FEASIBLE, INFEASIBLE
    constraint_violations: List[str] = field(default_factory=list)
    
    # Set after simulation/scoring
    score: float = 0.0
    rank: int = 0
    delta_metrics: dict = field(default_factory=dict)
    raw_metrics: dict = field(default_factory=dict)
    explanation: str = ""

@dataclass
class ObjectiveProfile:
    name: str
    weight_delay: float
    weight_crowding: float
    weight_energy: float
    accessibility_penalty: float

# Built-in profiles
PROFILES = {
    "MINIMUM_DELAY": ObjectiveProfile("MINIMUM_DELAY", 0.8, 0.1, 0.1, 999.0),
    "SAFETY_FIRST": ObjectiveProfile("SAFETY_FIRST", 0.2, 0.8, 0.0, 999.0),
    "ENERGY_EFFICIENT": ObjectiveProfile("ENERGY_EFFICIENT", 0.4, 0.1, 0.5, 999.0),
    "BALANCED": ObjectiveProfile("BALANCED", 0.33, 0.33, 0.33, 999.0),
}

@dataclass
class SandboxResult:
    scenario_id: str
    simulation_horizon_minutes: int
    objective_profile: str
    baseline_metrics: dict
    disrupted_metrics: dict
    candidates: List[InterventionCandidate]
    generated_at: datetime = field(default_factory=datetime.now)
