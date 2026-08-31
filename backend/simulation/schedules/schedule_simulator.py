"""
Schedule Simulator — tests alternate transit schedules WITHOUT modifying live state.

Core invariant: NEVER auto-dispatch. Evaluates alternate schedules and quantifies
delay, safety, and energy impacts before operators act.

Workflow:
    1. Snapshot current Digital Twin state (LiveState -> SimulationState)
    2. Apply schedule intervention to the isolated state
    3. Run PassengerFlowSimulator on the modified state
    4. Collect metrics
    5. Return results (DO NOT modify LiveState)

Supported interventions:
    INCREASE_FREQUENCY: Simulate more buses on a route (add virtual vehicles)
    DECREASE_FREQUENCY: Remove buses from a route
    DISPATCH_ADDITIONAL: Deploy a specific vehicle onto a route
    CHANGE_DEPARTURE: Delay a vehicle's departure
    HOLD_BUS: Hold a vehicle at a stop for N seconds
    REASSIGN_VEHICLE: Move a bus from one route to another
    SKIP_STOP: Have a vehicle bypass a specific stop
    REROUTE: Change vehicle path via DisruptionSandboxEngine
    COMBINED: Apply multiple interventions simultaneously
"""

import copy
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator
from simulation.schedules.models import (
    ScheduleIntervention,
    ScheduleInterventionType,
    ScheduleSimulationMetrics,
    ScheduleSimulationResult,
    ComparisonResult,
)
from simulation.interventions.models import ObjectiveProfile, PROFILES


class ScheduleSimulator:
    """
    Pre-Action Schedule Simulation Engine.
    Tests alternate schedules without auto-dispatching.
    """

    @staticmethod
    def simulate_single(
        intervention: ScheduleIntervention,
        horizon_minutes: int = 30,
        timestep_seconds: int = 10,
    ) -> ScheduleSimulationResult:
        """
        Runs a single schedule intervention in an isolated sandbox.

        Returns:
            ScheduleSimulationResult with metrics and event log.
        """
        # 1. Snapshot current state (creates isolated SimulationState)
        _, sim_state = StateSnapshotManager.create_snapshot()

        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=horizon_minutes),
            "timestep_seconds": timestep_seconds,
            "random_seed": 42,
        }

        # 2. Apply the schedule intervention to the isolated state
        violations = ScheduleSimulator._apply_intervention(sim_state, intervention)

        if violations:
            return ScheduleSimulationResult(
                intervention=intervention,
                metrics=ScheduleSimulationMetrics(),
                is_feasible=False,
                constraint_violations=violations,
                explanation="Intervention is infeasible: " + "; ".join(violations),
            )

        # 3. Run PassengerFlowSimulator on modified state
        try:
            simulator = PassengerFlowSimulator(sim_state, config)
            metrics_dict, event_log = simulator.run()
        except Exception as e:
            return ScheduleSimulationResult(
                intervention=intervention,
                metrics=ScheduleSimulationMetrics(),
                is_feasible=False,
                constraint_violations=[f"Simulation failed: {str(e)}"],
                explanation=f"Simulation engine error: {str(e)}",
            )

        # 4. Convert raw metrics dict to structured ScheduleSimulationMetrics
        sim_metrics = ScheduleSimulator._extract_metrics(metrics_dict, sim_state)

        return ScheduleSimulationResult(
            intervention=intervention,
            metrics=sim_metrics,
            event_log=event_log,
            is_feasible=True,
        )

    @staticmethod
    def compare_interventions(
        interventions: List[ScheduleIntervention],
        horizon_minutes: int = 30,
        timestep_seconds: int = 10,
        profile_name: str = "BALANCED",
    ) -> ComparisonResult:
        """
        Runs baseline + N intervention variants side-by-side for comparison.

        Returns:
            ComparisonResult with ranked intervention results.
        """
        scenario_id = str(uuid.uuid4())

        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=horizon_minutes),
            "timestep_seconds": timestep_seconds,
            "random_seed": 42,
        }

        # A. Run Baseline (no intervention)
        _, baseline_state = StateSnapshotManager.create_snapshot()
        baseline_sim = PassengerFlowSimulator(baseline_state, config)
        baseline_metrics_dict, _ = baseline_sim.run()

        baseline_metrics = ScheduleSimulator._extract_metrics(baseline_metrics_dict, baseline_state)

        # B. Run each intervention
        results = []
        for intervention in interventions:
            result = ScheduleSimulator.simulate_single(
                intervention=intervention,
                horizon_minutes=horizon_minutes,
                timestep_seconds=timestep_seconds,
            )

            # Compute delta vs baseline
            if result.is_feasible:
                result.delta_vs_baseline = ScheduleSimulator._compute_deltas(
                    baseline_metrics, result.metrics
                )

            results.append(result)

        # C. Score and rank using multi-objective profile
        profile = PROFILES.get(profile_name, PROFILES["BALANCED"])
        ScheduleSimulator._score_and_rank(results, baseline_metrics, profile)

        # D. Identify recommended option
        feasible = [r for r in results if r.is_feasible]
        recommended_idx = 0
        recommendation = "No feasible intervention found."

        if feasible:
            best = min(feasible, key=lambda r: r.score)
            recommended_idx = results.index(best)
            recommendation = best.explanation

        return ComparisonResult(
            scenario_id=scenario_id,
            baseline_metrics=baseline_metrics.to_dict(),
            intervention_results=results,
            recommended_index=recommended_idx,
            recommendation_explanation=recommendation,
            simulation_horizon_minutes=horizon_minutes,
            objective_profile=profile_name,
        )

    # ─────────────────────────────────────────────────
    # Intervention Application (to isolated state only)
    # ─────────────────────────────────────────────────

    @staticmethod
    def _apply_intervention(sim_state, intervention: ScheduleIntervention) -> List[str]:
        """
        Mutates the isolated SimulationState according to the intervention.
        Returns list of constraint violations (empty if successful).
        """
        violations = []
        params = intervention.parameters
        itype = intervention.intervention_type

        if itype == ScheduleInterventionType.INCREASE_FREQUENCY:
            # Simulate by adding a virtual bus to the route
            route_id = params.get("route_id")
            new_headway = params.get("new_headway_minutes", 10)
            if route_id is None:
                violations.append("route_id is required for INCREASE_FREQUENCY")
                return violations

            # Add a virtual vehicle to simulate increased frequency
            virtual_id = f"VIRTUAL-{uuid.uuid4().hex[:8]}"
            sim_state.vehicles[virtual_id] = {
                "status": "ACTIVE",
                "route_id": route_id,
                "capacity": 50,
                "occupancy": 0,
                "accessible_capacity": 5,
                "lat": 0, "lon": 0,
            }

        elif itype == ScheduleInterventionType.DECREASE_FREQUENCY:
            route_id = params.get("route_id")
            if route_id is None:
                violations.append("route_id is required for DECREASE_FREQUENCY")
                return violations

            # Remove one active vehicle from this route
            for vid, vdata in list(sim_state.vehicles.items()):
                if vdata.get("route_id") == route_id and vdata.get("status") == "ACTIVE":
                    vdata["status"] = "INACTIVE"
                    break

        elif itype == ScheduleInterventionType.DISPATCH_ADDITIONAL:
            vehicle_id = params.get("vehicle_id")
            route_id = params.get("route_id")
            if not vehicle_id:
                violations.append("vehicle_id is required for DISPATCH_ADDITIONAL")
                return violations

            if vehicle_id in sim_state.vehicles:
                sim_state.vehicles[vehicle_id]["status"] = "ACTIVE"
                if route_id:
                    sim_state.vehicles[vehicle_id]["route_id"] = route_id
            else:
                # Create new entry
                sim_state.vehicles[vehicle_id] = {
                    "status": "ACTIVE",
                    "route_id": route_id,
                    "capacity": 50,
                    "occupancy": 0,
                    "accessible_capacity": 5,
                }

        elif itype == ScheduleInterventionType.CHANGE_DEPARTURE:
            vehicle_id = params.get("vehicle_id")
            delay_minutes = params.get("delay_minutes", 5)
            if not vehicle_id:
                violations.append("vehicle_id is required for CHANGE_DEPARTURE")
                return violations

            if "holds" not in sim_state.metrics:
                sim_state.metrics["holds"] = {}
            sim_state.metrics["holds"][vehicle_id] = delay_minutes * 60

        elif itype == ScheduleInterventionType.HOLD_BUS:
            vehicle_id = params.get("vehicle_id")
            hold_seconds = params.get("hold_seconds", 300)
            if not vehicle_id:
                violations.append("vehicle_id is required for HOLD_BUS")
                return violations

            if "holds" not in sim_state.metrics:
                sim_state.metrics["holds"] = {}
            sim_state.metrics["holds"][vehicle_id] = hold_seconds

        elif itype == ScheduleInterventionType.REASSIGN_VEHICLE:
            vehicle_id = params.get("vehicle_id")
            to_route_id = params.get("to_route_id")
            if not vehicle_id or not to_route_id:
                violations.append("vehicle_id and to_route_id required for REASSIGN_VEHICLE")
                return violations

            if vehicle_id in sim_state.vehicles:
                sim_state.vehicles[vehicle_id]["route_id"] = to_route_id
                sim_state.vehicles[vehicle_id]["status"] = "ACTIVE"
            else:
                violations.append(f"Vehicle {vehicle_id} not found in state")

        elif itype == ScheduleInterventionType.SKIP_STOP:
            vehicle_id = params.get("vehicle_id")
            skip_stop_id = params.get("skip_stop_id")
            if not vehicle_id or not skip_stop_id:
                violations.append("vehicle_id and skip_stop_id required for SKIP_STOP")
                return violations

            if "closed_stops" not in sim_state.metrics:
                sim_state.metrics["closed_stops"] = set()
            sim_state.metrics["closed_stops"].add(int(skip_stop_id))

        elif itype == ScheduleInterventionType.REROUTE:
            vehicle_id = params.get("vehicle_id")
            blocked_edge_id = params.get("blocked_edge_id")
            bypass_edges = params.get("bypass_edges", [])
            if not vehicle_id:
                violations.append("vehicle_id is required for REROUTE")
                return violations

            if "route_overrides" not in sim_state.metrics:
                sim_state.metrics["route_overrides"] = {}
            if bypass_edges:
                sim_state.metrics["route_overrides"][vehicle_id] = bypass_edges

        elif itype == ScheduleInterventionType.COMBINED:
            sub_interventions = params.get("interventions", [])
            for sub_params in sub_interventions:
                sub = ScheduleIntervention(
                    intervention_type=sub_params.get("intervention_type", ""),
                    parameters=sub_params.get("parameters", {}),
                )
                sub_violations = ScheduleSimulator._apply_intervention(sim_state, sub)
                violations.extend(sub_violations)
        else:
            violations.append(f"Unknown intervention type: {itype}")

        return violations

    # ─────────────────────────────────────────────────
    # Metric Extraction & Scoring
    # ─────────────────────────────────────────────────

    @staticmethod
    def _extract_metrics(raw_metrics: dict, sim_state) -> ScheduleSimulationMetrics:
        """Converts raw simulation output dict to ScheduleSimulationMetrics."""
        active_vehicles = sum(
            1 for v in sim_state.vehicles.values()
            if v.get("status") == "ACTIVE"
        )

        return ScheduleSimulationMetrics(
            total_waiting_seconds=raw_metrics.get("total_waiting_seconds", 0),
            average_waiting_minutes=raw_metrics.get("average_waiting_minutes", 0),
            passengers_generated=raw_metrics.get("passengers_generated", 0),
            passengers_served=raw_metrics.get("passengers_served", 0),
            passengers_remaining=raw_metrics.get("passengers_remaining", 0),
            max_queue_size=raw_metrics.get("max_queue_size", 0),
            max_crowding_ratio=raw_metrics.get("max_crowding_ratio", 0),
            capacity_denied_boardings=raw_metrics.get("capacity_denied_boardings", 0),
            accessibility_denied_boardings=raw_metrics.get("accessibility_denied_boardings", 0),
            vehicles_used=active_vehicles,
        )

    @staticmethod
    def _compute_deltas(
        baseline: ScheduleSimulationMetrics,
        candidate: ScheduleSimulationMetrics,
    ) -> dict:
        """Computes per-metric difference: candidate - baseline."""
        return {
            "waiting_minutes_saved": round(
                baseline.average_waiting_minutes - candidate.average_waiting_minutes, 2
            ),
            "total_waiting_delta_sec": round(
                candidate.total_waiting_seconds - baseline.total_waiting_seconds, 1
            ),
            "queue_size_delta": candidate.max_queue_size - baseline.max_queue_size,
            "crowding_ratio_delta": round(
                candidate.max_crowding_ratio - baseline.max_crowding_ratio, 3
            ),
            "passengers_served_delta": candidate.passengers_served - baseline.passengers_served,
            "denied_boardings_delta": candidate.capacity_denied_boardings - baseline.capacity_denied_boardings,
            "accessibility_delta": candidate.accessibility_denied_boardings - baseline.accessibility_denied_boardings,
            "vehicles_used_delta": candidate.vehicles_used - baseline.vehicles_used,
        }

    @staticmethod
    def _score_and_rank(
        results: List[ScheduleSimulationResult],
        baseline: ScheduleSimulationMetrics,
        profile: ObjectiveProfile,
    ) -> None:
        """
        Scores each result using multi-objective weights and ranks them.
        Lower score = better intervention.
        """
        for result in results:
            if not result.is_feasible:
                result.score = 999.0
                continue

            deltas = result.delta_vs_baseline
            m = result.metrics

            # Normalize metrics (0-1 scale, lower is better)
            # Waiting: saved minutes / max possible (use baseline as reference)
            saved_waiting = deltas.get("waiting_minutes_saved", 0)
            penalty_delay = max(0, 1.0 - (saved_waiting / max(1, baseline.average_waiting_minutes)))

            # Crowding: lower ratio is better
            penalty_crowding = min(1.0, m.max_crowding_ratio)

            # Energy: more vehicles = more energy (simple proxy)
            penalty_energy = min(1.0, deltas.get("vehicles_used_delta", 0) / 5.0) if deltas.get("vehicles_used_delta", 0) > 0 else 0.0

            # Composite score
            score = (
                penalty_delay * profile.weight_delay
                + penalty_crowding * profile.weight_crowding
                + penalty_energy * profile.weight_energy
            )

            # Accessibility penalty
            if m.accessibility_denied_boardings > baseline.accessibility_denied_boardings:
                score += profile.accessibility_penalty

            result.score = score

            # Generate explanation
            explanations = []
            if saved_waiting > 0:
                explanations.append(f"Saves {saved_waiting:.1f} min avg passenger wait")
            elif saved_waiting < 0:
                explanations.append(f"Increases avg wait by {-saved_waiting:.1f} min")

            if deltas.get("crowding_ratio_delta", 0) < 0:
                explanations.append(f"Reduces crowding by {-deltas['crowding_ratio_delta']:.2f}")

            if deltas.get("passengers_served_delta", 0) > 0:
                explanations.append(f"Serves {deltas['passengers_served_delta']} more passengers")

            result.explanation = ". ".join(explanations) if explanations else "Neutral impact."

        # Rank feasible results
        feasible = sorted(
            [r for r in results if r.is_feasible],
            key=lambda r: r.score
        )
        for rank, r in enumerate(feasible, 1):
            r.rank = rank

        # Infeasible get last rank
        infeasible = [r for r in results if not r.is_feasible]
        for r in infeasible:
            r.rank = len(feasible) + 1
