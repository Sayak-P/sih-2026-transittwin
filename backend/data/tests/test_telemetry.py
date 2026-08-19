import pytest
from django.utils import timezone
from data.telemetry_pipeline import process_vehicle_telemetry
from simulation.state.live_state import LiveStateEngine
from core.models import Vehicle

@pytest.mark.django_db
class TestTelemetryPipeline:
    def test_invalid_negative_speed(self):
        payload = {
            "vehicle_id": "TEST-01",
            "speed_kmh": -5.0
        }
        success, err = process_vehicle_telemetry(payload)
        assert not success
        assert "Speed cannot be negative" in err

    def test_stale_update_rejection(self):
        Vehicle.objects.create(identifier="TEST-02", capacity=50)
        
        payload1 = {
            "vehicle_id": "TEST-02",
            "timestamp": "2026-08-18T10:00:00Z",
            "speed_kmh": 20.0
        }
        success, _ = process_vehicle_telemetry(payload1)
        assert success

        payload2_stale = {
            "vehicle_id": "TEST-02",
            "timestamp": "2026-08-18T09:00:00Z",
            "speed_kmh": 10.0
        }
        success, err = process_vehicle_telemetry(payload2_stale)
        assert not success
        assert "Stale update rejected" in err
