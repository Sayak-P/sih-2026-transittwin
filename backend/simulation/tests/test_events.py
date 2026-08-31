"""
Tests for Digital Twin Event Engine & Demand Modifiers.
"""

from datetime import datetime, timedelta
from django.test import TestCase
from simulation.events.models import Event, EventType, EVENTS_DB
from simulation.events.event_engine import (
    haversine_km,
    compute_event_surge_at_stop,
    get_active_events,
)
from core.models import Stop


class EventEngineTestCase(TestCase):
    def setUp(self):
        EVENTS_DB.clear()
        self.now = datetime(2026, 8, 31, 14, 0, 0)

        self.stop1 = Stop.objects.create(
            id=101, name="Kalinga Stadium", lat=20.296, lon=85.824, capacity=300, is_active=True
        )
        self.stop2 = Stop.objects.create(
            id=102, name="Master Canteen", lat=20.265, lon=85.842, capacity=250, is_active=True
        )
        self.stop3 = Stop.objects.create(
            id=103, name="Patia Terminal", lat=20.354, lon=85.818, capacity=200, is_active=True
        )

    def test_haversine_distance(self):
        # Distance between stop1 (Kalinga) and stop2 (Master Canteen) ~ 3.9 km
        d = haversine_km(self.stop1.lat, self.stop1.lon, self.stop2.lat, self.stop2.lon)
        self.assertGreater(d, 3.0)
        self.assertLess(d, 5.0)

    def test_event_surge_at_stadium(self):
        # Create a concert event at Kalinga Stadium
        event = Event(
            id=1,
            event_type=EventType.CONCERT,
            name="Mega Music Fest",
            start_time=self.now - timedelta(hours=1),
            duration_hours=4.0,
            intensity=2.0,
            location_stop_id=self.stop1.id,
            radius_km=2.5,
            is_active=True,
        )
        EVENTS_DB[1] = event

        stops_coords = {
            self.stop1.id: (self.stop1.lat, self.stop1.lon),
            self.stop2.id: (self.stop2.lat, self.stop2.lon),
            self.stop3.id: (self.stop3.lat, self.stop3.lon),
        }

        # Surge directly at stadium stop (distance 0 -> full intensity 2.0 -> total surge 3.0)
        res_stadium = compute_event_surge_at_stop(
            stop_id=self.stop1.id,
            stop_lat=self.stop1.lat,
            stop_lon=self.stop1.lon,
            current_time=self.now,
            events=[event],
            stops_coords=stops_coords,
        )
        self.assertEqual(res_stadium["event_count"], 1)
        self.assertAlmostEqual(res_stadium["total_surge"], 3.0, places=1)

        # Surge at distant stop (Master Canteen ~3.9km away, radius 2.5km -> decayed)
        res_distant = compute_event_surge_at_stop(
            stop_id=self.stop2.id,
            stop_lat=self.stop2.lat,
            stop_lon=self.stop2.lon,
            current_time=self.now,
            events=[event],
            stops_coords=stops_coords,
        )
        self.assertLess(res_distant["total_surge"], res_stadium["total_surge"])
        self.assertGreaterEqual(res_distant["total_surge"], 1.0)

    def test_inactive_event_not_counted(self):
        # Event in the past
        past_event = Event(
            id=2,
            event_type=EventType.SPORTS_EVENT,
            name="Yesterday Football Match",
            start_time=self.now - timedelta(days=1),
            duration_hours=2.0,
            intensity=1.8,
            location_stop_id=self.stop1.id,
            is_active=True,
        )
        EVENTS_DB[2] = past_event

        res = compute_event_surge_at_stop(
            stop_id=self.stop1.id,
            stop_lat=self.stop1.lat,
            stop_lon=self.stop1.lon,
            current_time=self.now,
            events=[past_event],
        )
        self.assertEqual(res["total_surge"], 1.0)
        self.assertEqual(res["event_count"], 0)
