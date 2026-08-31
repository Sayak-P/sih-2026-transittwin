"""
Schedule simulation data models.

These dataclasses define the input and output structures for the schedule
simulation engine. They are in-memory objects — NOT Django ORM models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict


class ScheduleInterventionType:
    """All supported schedule intervention types."""
    INCREASE_FREQUENCY = "INCREASE_FREQUENCY"
    DECREASE_FREQUENCY = "DECREASE_FREQUENCY"
    DISPATCH_ADDITIONAL = "DISPATCH_ADDITIONAL"
    CHANGE_DEPARTURE = "CHANGE_DEPARTURE"
    HOLD_BUS = "HOLD_BUS"
    REASSIGN_VEHICLE = "REASSIGN_VEHICLE"
    SKIP_STOP = "SKIP_STOP"
    REROUTE = "REROUTE"
    COMBINED = "COMBINED"


INTERVENTION_LABELS = {
    ScheduleInterventionType.INCREASE_FREQUENCY: "Increase Service Frequency",
    ScheduleInterventionType.DECREASE_FREQUENCY: "Decrease Service Frequency",
    ScheduleInterventionType.DISPATCH_ADDITIONAL: "Dispatch Additional Vehicle",
    ScheduleInterventionType.CHANGE_DEPARTURE: "Change Departure Time",
    ScheduleInterventionType.HOLD_BUS: "Hold Bus at Stop",
    ScheduleInterventionType.REASSIGN_VEHICLE: "Reassign Vehicle to Route",
    ScheduleInterventionType.SKIP_STOP: "Skip Stop",
    ScheduleInterventionType.REROUTE: "Reroute Vehicle",
    ScheduleInterventionType.COMBINED: "Combined Intervention",
}


@dataclass
class ScheduleIntervention:
    """
    Defines a single schedule modification to test.

    Attributes:
        intervention_type: One of ScheduleInterventionType constants
        parameters: Type-specific parameters, e.g.:
            INCREASE_FREQUENCY: {route_id, new_headway_minutes}
            DECREASE_FREQUENCY: {route_id, new_headway_minutes}
            DISPATCH_ADDITIONAL: {vehicle_id, route_id}
            CHANGE_DEPARTURE: {vehicle_id, delay_minutes}
            HOLD_BUS: {vehicle_id, stop_id, hold_seconds}
            REASSIGN_VEHICLE: {vehicle_id, from_route_id, to_route_id}
            SKIP_STOP: {vehicle_id, skip_stop_id}
            REROUTE: {vehicle_id, blocked_edge_id}
            COMBINED: {interventions: List[ScheduleIntervention]}
        label: Human-readable label (auto-generated if not provided)
    """
    intervention_type: str
    parameters: dict = field(default_factory=dict)
    label: Optional[str] = None

    def __post_init__(self):
        if self.label is None:
            self.label = INTERVENTION_LABELS.get(
                self.intervention_type, self.intervention_type
            )

    def to_dict(self) -> dict:
        return {
            "intervention_type": self.intervention_type,
            "label": self.label,
            "parameters": self.parameters,
        }


@dataclass
class ScheduleSimulationMetrics:
    """
    Aggregated metrics from a single simulation run.
    These are the key indicators used for comparison.
    """
    total_waiting_seconds: float = 0.0
    average_waiting_minutes: float = 0.0
    passengers_generated: int = 0
    passengers_served: int = 0
    passengers_remaining: int = 0
    max_queue_size: int = 0
    max_crowding_ratio: float = 0.0
    capacity_denied_boardings: int = 0
    accessibility_denied_boardings: int = 0
    total_energy_kwh: float = 0.0
    total_distance_km: float = 0.0
    vehicles_used: int = 0
    safety_risk_index: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_waiting_seconds": round(self.total_waiting_seconds, 1),
            "average_waiting_minutes": round(self.average_waiting_minutes, 2),
            "passengers_generated": self.passengers_generated,
            "passengers_served": self.passengers_served,
            "passengers_remaining": self.passengers_remaining,
            "max_queue_size": self.max_queue_size,
            "max_crowding_ratio": round(self.max_crowding_ratio, 3),
            "capacity_denied_boardings": self.capacity_denied_boardings,
            "accessibility_denied_boardings": self.accessibility_denied_boardings,
            "total_energy_kwh": round(self.total_energy_kwh, 2),
            "total_distance_km": round(self.total_distance_km, 2),
            "vehicles_used": self.vehicles_used,
            "safety_risk_index": round(self.safety_risk_index, 2),
        }


@dataclass
class ScheduleSimulationResult:
    """
    Complete result of a schedule intervention simulation.

    Contains the intervention definition, metrics, and comparison deltas.
    """
    intervention: ScheduleIntervention
    metrics: ScheduleSimulationMetrics
    delta_vs_baseline: Dict = field(default_factory=dict)
    rank: int = 0
    score: float = 0.0
    explanation: str = ""
    event_log: List[Dict] = field(default_factory=list)
    is_feasible: bool = True
    constraint_violations: List[str] = field(default_factory=list)
    data_source: str = "SIMULATION"

    def to_dict(self) -> dict:
        return {
            "intervention": self.intervention.to_dict(),
            "metrics": self.metrics.to_dict(),
            "delta_vs_baseline": self.delta_vs_baseline,
            "rank": self.rank,
            "score": round(self.score, 4),
            "explanation": self.explanation,
            "is_feasible": self.is_feasible,
            "constraint_violations": self.constraint_violations,
            "data_source": self.data_source,
            "event_log_count": len(self.event_log),
        }


@dataclass
class ComparisonResult:
    """
    Side-by-side comparison of Baseline + N intervention variants.
    """
    scenario_id: str
    baseline_metrics: Dict
    intervention_results: List[ScheduleSimulationResult]
    recommended_index: int = 0
    recommendation_explanation: str = ""
    simulation_horizon_minutes: int = 30
    objective_profile: str = "BALANCED"
    generated_at: datetime = field(default_factory=datetime.now)
    data_source: str = "SIMULATION"

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "baseline_metrics": self.baseline_metrics,
            "intervention_results": [r.to_dict() for r in self.intervention_results],
            "recommended_index": self.recommended_index,
            "recommendation_explanation": self.recommendation_explanation,
            "simulation_horizon_minutes": self.simulation_horizon_minutes,
            "objective_profile": self.objective_profile,
            "generated_at": self.generated_at.isoformat(),
            "data_source": self.data_source,
        }
