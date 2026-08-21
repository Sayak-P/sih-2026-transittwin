import pytest
from django.test import TestCase
from django.core.management import call_command
from django.conf import settings
from rest_framework.test import APIClient
from io import StringIO
from unittest.mock import patch
from data.telemetry_pipeline import process_vehicle_telemetry
from simulation.state.live_state import LiveStateEngine
from core.models import Vehicle

class TestHybridMode(TestCase):
    def setUp(self):
        self.client = APIClient()
        LiveStateEngine.VERSION_KEY = "test_live_state:version"
        LiveStateEngine.VEHICLES_KEY = "test_live_state:vehicles"
        LiveStateEngine.STOPS_KEY = "test_live_state:stops"
        
        # Create a mock vehicle
        self.vehicle = Vehicle.objects.create(
            identifier="BUS-1001",
            lat=20.29,
            lon=85.83,
            capacity=60
        )

    def test_live_mode_blocks_simulator(self):
        with patch('django.conf.settings.TRANSIT_TWIN_MODE', 'LIVE'):
            out = StringIO()
            call_command('run_telemetry_simulator', ticks=1, stdout=out)
            self.assertIn("FATAL: Telemetry simulator cannot be run in LIVE mode.", out.getvalue())

    def test_health_api_crut_separation_live(self):
        with patch('django.conf.settings.TRANSIT_TWIN_MODE', 'LIVE'):
            response = self.client.get('/api/v1/twin/status/')
            self.assertEqual(response.status_code, 200)
            providers = response.data['providers']
            self.assertEqual(providers['crut']['status'], 'OFFLINE')
            self.assertEqual(providers['simulation']['status'], 'DISABLED')

    def test_health_api_crut_separation_hybrid(self):
        with patch('django.conf.settings.TRANSIT_TWIN_MODE', 'HYBRID'):
            # First, process a simulated vehicle to make the simulation fleet active
            process_vehicle_telemetry({
                "vehicle_id": "SIM-BUS-1001",
                "lat": 20.29,
                "lon": 85.83,
                "speed_kmh": 30.0,
                "timestamp": "2026-08-20T12:00:00Z"
            })
            
            response = self.client.get('/api/v1/twin/status/')
            self.assertEqual(response.status_code, 200)
            providers = response.data['providers']
            self.assertEqual(providers['crut']['status'], 'OFFLINE')
            # It might be STALE depending on the mocked timestamp vs now, but it's not DISABLED
            self.assertNotEqual(providers['simulation']['status'], 'DISABLED')

    def test_telemetry_pipeline_injects_provider(self):
        process_vehicle_telemetry({
            "vehicle_id": "SIM-BUS-1001",
            "lat": 20.29,
            "lon": 85.83,
            "speed_kmh": 30.0,
            "timestamp": "2026-08-20T12:00:00Z"
        })
        
        state = LiveStateEngine.get_vehicle_state("SIM-BUS-1001")
        self.assertIsNotNone(state)
        self.assertEqual(state['data_source'], 'SIMULATION')
        self.assertEqual(state['provider'], 'INTERNAL')
