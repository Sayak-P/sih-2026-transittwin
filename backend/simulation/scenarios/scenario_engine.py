"""
Scenario Engine — What-If simulation for the Digital Twin.

Allows operators to ask: "What if this happens?" and see predicted impacts
without affecting the live system.

Scenario Types:
    ROAD_BLOCKED: Block an edge and see cascade effects
    DEMAND_SURGE: Simulate sudden demand increase at a stop
    BUS_DELAYED: Delay a specific vehicle
    EVENT_STARTS: Simulate an event near a stop
    VEHICLE_UNAVAILABLE: Remove a vehicle from service
    FREQUENCY_CHANGE: Change headway on a route

Each scenario:
    1. Snapshots the current Digital Twin state
    2. Applies the scenario conditions to an isolated state
    3. Runs the PassengerFlowSimulator
    4. Compares against baseline (no-scenario)
    5. Returns delta metrics for operator decision support
"""

import copy
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator
from simulation.disruptions.applicator import apply_disruption
from simulation.disruptions.models import Disruption


class ScenarioType:
    ROAD_BLOCKED = "ROAD_BLOCKED"
    DEMAND_SURGE = "DEMAND_SURGE"
    BUS_DELAYED = "BUS_DELAYED"
    EVENT_STARTS = "EVENT_STARTS"
    VEHICLE_UNAVAILABLE = "VEHICLE_UNAVAILABLE"
    FREQUENCY_CHANGE = "FREQUENCY_CHANGE"


SCENARIO_LABELS = {
    ScenarioType.ROAD_BLOCKED: "Road Blockage / Closure",
    ScenarioType.DEMAND_SURGE: "Sudden Demand Surge",
    ScenarioType.BUS_DELAYED: "Bus Delay / Breakdown",
    ScenarioType.EVENT_STARTS: "Event Near Stop",
    ScenarioType.VEHICLE_UNAVAILABLE: "Vehicle Taken Out of Service",
    ScenarioType.FREQUENCY_CHANGE: "Service Frequency Change",
}


@dataclass
class ScenarioResult:
    """Result of a what-if scenario simulation."""
    scenario_id: str
    scenario_type: str
    scenario_label: str
    parameters: dict
    baseline_metrics: dict
    scenario_metrics: dict
    delta_metrics: dict
    impact_summary: str
    severity: str  # MINIMAL, MODERATE, SIGNIFICANT, CRITICAL
    generated_at: datetime = field(default_factory=datetime.now)
    data_source: str = "SIMULATION"

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type,
            "scenario_label": self.scenario_label,
            "parameters": self.parameters,
            "baseline_metrics": self.baseline_metrics,
            "scenario_metrics": self.scenario_metrics,
            "delta_metrics": self.delta_metrics,
            "impact_summary": self.impact_summary,
            "severity": self.severity,
            "generated_at": self.generated_at.isoformat(),
            "data_source": self.data_source,
        }


class ScenarioEngine:
    """
    What-If simulation engine.
    Runs scenarios in isolated state without affecting the live system.
    """

    @staticmethod
    def simulate_scenario(
        scenario_type: str,
        parameters: dict,
        horizon_minutes: int = 30,
        timestep_seconds: int = 10,
    ) -> ScenarioResult:
        """
        Runs a what-if scenario simulation.

        Args:
            scenario_type: One of ScenarioType constants
            parameters: Scenario-specific parameters
            horizon_minutes: Simulation lookahead
            timestep_seconds: Simulation time step

        Returns:
            ScenarioResult with baseline vs scenario comparison
        """
        scenario_id = str(uuid.uuid4())

        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=horizon_minutes),
            "timestep_seconds": timestep_seconds,
            "random_seed": 42,
        }

        # 1. Run Baseline
        _, baseline_state = StateSnapshotManager.create_snapshot()
        baseline_sim = PassengerFlowSimulator(baseline_state, config)
        baseline_metrics, _ = baseline_sim.run()

        # 2. Run Scenario
        _, scenario_state = StateSnapshotManager.create_snapshot()
        ScenarioEngine._apply_scenario(scenario_state, scenario_type, parameters)
        scenario_sim = PassengerFlowSimulator(scenario_state, config)
        scenario_metrics, _ = scenario_sim.run()

        # 3. Compute Deltas
        delta_metrics = ScenarioEngine._compute_delta(baseline_metrics, scenario_metrics)

        # 4. Assess Impact
        severity, summary = ScenarioEngine._assess_impact(delta_metrics, scenario_type, parameters)

        return ScenarioResult(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            scenario_label=SCENARIO_LABELS.get(scenario_type, scenario_type),
            parameters=parameters,
            baseline_metrics=baseline_metrics,
            scenario_metrics=scenario_metrics,
            delta_metrics=delta_metrics,
            impact_summary=summary,
            severity=severity,
        )

    @staticmethod
    def _apply_scenario(sim_state, scenario_type: str, params: dict) -> None:
        """Applies scenario conditions to the isolated SimulationState."""

        if scenario_type == ScenarioType.ROAD_BLOCKED:
            edge_id = str(params.get("edge_id", "1"))
            severity = int(params.get("severity", 4))
            disruption = Disruption(
                id=0,
                type="ROAD_BLOCK",
                affected_entity_id=edge_id,
                severity=severity,
                start_time=datetime.now(),
                duration_minutes=params.get("duration_minutes", 30),
                description="What-if road blockage scenario",
            )
            apply_disruption(sim_state, disruption)

        elif scenario_type == ScenarioType.DEMAND_SURGE:
            stop_id = int(params.get("stop_id", 1))
            surge_multiplier = float(params.get("surge_multiplier", 2.0))
            for cohort in sim_state.passenger_cohorts.values():
                if cohort.get("origin_id") == stop_id:
                    cohort["total_generated"] = int(cohort["total_generated"] * surge_multiplier)

        elif scenario_type == ScenarioType.BUS_DELAYED:
            vehicle_id = params.get("vehicle_id")
            delay_seconds = int(params.get("delay_seconds", 600))
            if vehicle_id and vehicle_id in sim_state.vehicles:
                if "holds" not in sim_state.metrics:
                    sim_state.metrics["holds"] = {}
                sim_state.metrics["holds"][vehicle_id] = delay_seconds

        elif scenario_type == ScenarioType.EVENT_STARTS:
            stop_id = int(params.get("stop_id", 1))
            intensity = float(params.get("intensity", 2.0))
            # Simulate event demand surge at the affected stop
            surge_multiplier = 1.0 + intensity
            for cohort in sim_state.passenger_cohorts.values():
                if cohort.get("origin_id") == stop_id:
                    cohort["total_generated"] = int(cohort["total_generated"] * surge_multiplier)

        elif scenario_type == ScenarioType.VEHICLE_UNAVAILABLE:
            vehicle_id = params.get("vehicle_id")
            if vehicle_id and vehicle_id in sim_state.vehicles:
                sim_state.vehicles[vehicle_id]["status"] = "BROKEN_DOWN"
                sim_state.vehicles[vehicle_id]["capacity"] = 0

        elif scenario_type == ScenarioType.FREQUENCY_CHANGE:
            route_id = params.get("route_id")
            action = params.get("action", "increase")  # "increase" or "decrease"
            if action == "decrease":
                # Remove one vehicle from route
                for vid, vdata in sim_state.vehicles.items():
                    if vdata.get("route_id") == route_id and vdata.get("status") == "ACTIVE":
                        vdata["status"] = "INACTIVE"
                        break
            else:
                # Add virtual vehicle
                virtual_id = f"SCENARIO-{uuid.uuid4().hex[:8]}"
                sim_state.vehicles[virtual_id] = {
                    "status": "ACTIVE",
                    "route_id": route_id,
                    "capacity": 50,
                    "occupancy": 0,
                    "accessible_capacity": 5,
                }

    @staticmethod
    def _compute_delta(baseline: dict, scenario: dict) -> dict:
        """Computes delta metrics between baseline and scenario."""
        def safe(d, k):
            v = d.get(k, 0)
            return v if v is not None else 0

        return {
            "delta_total_waiting_sec": round(safe(scenario, "total_waiting_seconds") - safe(baseline, "total_waiting_seconds"), 1),
            "delta_avg_waiting_min": round(safe(scenario, "average_waiting_minutes") - safe(baseline, "average_waiting_minutes"), 2),
            "delta_max_queue": safe(scenario, "max_queue_size") - safe(baseline, "max_queue_size"),
            "delta_max_crowding": round(safe(scenario, "max_crowding_ratio") - safe(baseline, "max_crowding_ratio"), 3),
            "delta_passengers_served": safe(scenario, "passengers_served") - safe(baseline, "passengers_served"),
            "delta_denied_boardings": safe(scenario, "capacity_denied_boardings") - safe(baseline, "capacity_denied_boardings"),
            "delta_accessibility": safe(scenario, "accessibility_denied_boardings") - safe(baseline, "accessibility_denied_boardings"),
        }

    @staticmethod
    def _assess_impact(deltas: dict, scenario_type: str, params: dict) -> tuple:
        """Returns (severity, summary) based on delta metrics."""
        d_wait = deltas.get("delta_avg_waiting_min", 0)
        d_crowd = deltas.get("delta_max_crowding", 0)
        d_denied = deltas.get("delta_denied_boardings", 0)

        # Severity classification
        if d_wait > 5.0 or d_crowd > 0.5 or d_denied > 50:
            severity = "CRITICAL"
        elif d_wait > 2.0 or d_crowd > 0.25 or d_denied > 20:
            severity = "SIGNIFICANT"
        elif d_wait > 0.5 or d_crowd > 0.1 or d_denied > 5:
            severity = "MODERATE"
        else:
            severity = "MINIMAL"

        # Summary
        parts = []
        label = SCENARIO_LABELS.get(scenario_type, scenario_type)
        parts.append(f"{label} scenario")

        if d_wait > 0:
            parts.append(f"increases avg wait by {d_wait:.1f} min")
        elif d_wait < 0:
            parts.append(f"reduces avg wait by {-d_wait:.1f} min")

        if d_crowd > 0:
            parts.append(f"raises max crowding by {d_crowd:.2f}")

        if d_denied > 0:
            parts.append(f"causes {d_denied} additional denied boardings")

        if len(parts) == 1:
            parts.append("has minimal impact on operations")

        summary = ": ".join([parts[0], ", ".join(parts[1:])])

        return severity, summary
