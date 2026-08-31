"""
Tests for Passenger Ticketing Simulator.
"""

from datetime import datetime
from django.test import TestCase
from simulation.passenger.ticketing_simulator import TicketingSimulator


class TicketingSimulatorTestCase(TestCase):
    def setUp(self):
        self.stops = [
            {"id": 1, "name": "Central Hub", "capacity": 250, "lat": 20.26, "lon": 85.84},
            {"id": 2, "name": "Residential North", "capacity": 100, "lat": 20.35, "lon": 85.81},
        ]

    def test_deterministic_output_with_same_seed(self):
        sim1 = TicketingSimulator(seed=123)
        sim2 = TicketingSimulator(seed=123)

        dt = datetime(2026, 8, 31, 8, 30, 0) # Monday 8:30 AM
        snap1 = sim1.generate_current_snapshot(self.stops, current_time=dt)
        snap2 = sim2.generate_current_snapshot(self.stops, current_time=dt)

        self.assertEqual(len(snap1), len(snap2))
        self.assertAlmostEqual(snap1[0].arrivals_per_minute, snap2[0].arrivals_per_minute, places=4)
        self.assertEqual(snap1[0].demand_level, snap2[0].demand_level)

    def test_time_of_day_rush_hour(self):
        sim = TicketingSimulator(seed=42)
        
        peak_time = datetime(2026, 8, 31, 8, 0, 0) # 8 AM Peak
        offpeak_time = datetime(2026, 8, 31, 2, 0, 0) # 2 AM Night

        peak_snap = sim.generate_current_snapshot(self.stops, current_time=peak_time)
        offpeak_snap = sim.generate_current_snapshot(self.stops, current_time=offpeak_time)

        self.assertGreater(peak_snap[0].arrivals_per_minute, offpeak_snap[0].arrivals_per_minute)
        self.assertEqual(peak_snap[0].demand_level, "PEAK")
        self.assertEqual(offpeak_snap[0].demand_level, "LOW")

    def test_historical_demand_curve(self):
        sim = TicketingSimulator(seed=42)
        curve = sim.generate_historical_demand(stop_id=1, stop_name="Central Hub", stop_capacity=250, hours=24)
        
        self.assertEqual(len(curve), 24)
        # Peak at hour 8 or 18
        h8 = next(p for p in curve if p.hour == 8)
        h2 = next(p for p in curve if p.hour == 2)
        self.assertGreater(h8.arrivals, h2.arrivals)
