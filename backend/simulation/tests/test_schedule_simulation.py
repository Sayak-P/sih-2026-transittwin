"""
Tests for Pre-Action Schedule Simulation & Intervention Engine.
"""

from django.test import TestCase
from simulation.schedules.models import (
    ScheduleIntervention,
    ScheduleInterventionType,
    ScheduleSimulationMetrics,
)
from simulation.schedules.schedule_simulator import ScheduleSimulator
from core.models import Stop, Edge, Route, RouteEdge, Vehicle


class ScheduleSimulationTestCase(TestCase):
    def setUp(self):
        self.stop1 = Stop.objects.create(id=1, name="Hub A", lat=20.26, lon=85.84, capacity=200, is_active=True)
        self.stop2 = Stop.objects.create(id=2, name="Hub B", lat=20.30, lon=85.82, capacity=200, is_active=True)
        self.edge1 = Edge.objects.create(id=1, source=self.stop1, target=self.stop2, distance=3000, baseline_travel_time=300.0, is_active=True)
        self.route1 = Route.objects.create(id=1, name="Route 101", is_active=True)
        RouteEdge.objects.create(route=self.route1, edge=self.edge1, sequence_order=1)

        self.v1 = Vehicle.objects.create(
            id=1, identifier="BUS-101", route=self.route1, capacity=50, occupancy=10, state="ACTIVE"
        )

    def test_single_schedule_simulation_increase_frequency(self):
        intervention = ScheduleIntervention(
            intervention_type=ScheduleInterventionType.INCREASE_FREQUENCY,
            parameters={"route_id": 1, "new_headway_minutes": 8},
            label="Frequency Boost Route 101",
        )

        result = ScheduleSimulator.simulate_single(intervention, horizon_minutes=20)
        self.assertTrue(result.is_feasible)
        self.assertIsNotNone(result.metrics)
        self.assertGreaterEqual(result.metrics.vehicles_used, 1)

    def test_single_schedule_simulation_hold_bus(self):
        intervention = ScheduleIntervention(
            intervention_type=ScheduleInterventionType.HOLD_BUS,
            parameters={"vehicle_id": "BUS-101", "hold_seconds": 180},
        )

        result = ScheduleSimulator.simulate_single(intervention, horizon_minutes=20)
        self.assertTrue(result.is_feasible)

    def test_compare_interventions(self):
        intv1 = ScheduleIntervention(
            intervention_type=ScheduleInterventionType.INCREASE_FREQUENCY,
            parameters={"route_id": 1, "new_headway_minutes": 8},
            label="Option A - Frequency Up",
        )
        intv2 = ScheduleIntervention(
            intervention_type=ScheduleInterventionType.HOLD_BUS,
            parameters={"vehicle_id": "BUS-101", "hold_seconds": 120},
            label="Option B - Bus Hold",
        )

        comparison = ScheduleSimulator.compare_interventions(
            interventions=[intv1, intv2],
            horizon_minutes=20,
            profile_name="BALANCED",
        )

        self.assertIsNotNone(comparison.baseline_metrics)
        self.assertEqual(len(comparison.intervention_results), 2)
        self.assertIn(comparison.recommended_index, [0, 1])
