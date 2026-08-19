import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from core.models import Stop
from prediction.models import ODDemand
from simulation.state.live_state import LiveStateEngine

@pytest.mark.django_db
class TestPredictionEarlyWarning:
    def setup_method(self):
        self.client = APIClient()
        self.now = timezone.now()
        
        # Create Stops
        self.stop_normal = Stop.objects.create(name="Normal Stop", lat=0, lon=0, capacity=100)
        self.stop_warning = Stop.objects.create(name="Warning Stop", lat=0, lon=0, capacity=100)
        self.stop_critical = Stop.objects.create(name="Critical Stop", lat=0, lon=0, capacity=100)
        
        # Populate demands
        ODDemand.objects.create(
            origin_stop=self.stop_normal,
            destination_stop=self.stop_critical,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=10
        )
        
        ODDemand.objects.create(
            origin_stop=self.stop_warning,
            destination_stop=self.stop_critical,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=85
        )
        
        ODDemand.objects.create(
            origin_stop=self.stop_critical,
            destination_stop=self.stop_normal,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=110
        )
        
        # Clear LiveState to ensure clean slate
        from django.core.cache import cache
        cache.clear()

    def test_prediction_thresholds(self):
        response = self.client.get('/api/v1/predictions/early-warnings/')
        assert response.status_code == 200
        data = response.json()
        
        warnings = data.get("warnings", [])
        
        # The Normal Stop has 10 pax demand / 100 capacity = 0.1 ratio. Should NOT be in warnings.
        assert not any(w["stop_id"] == self.stop_normal.id for w in warnings)
        
        # The Warning Stop has 85 pax demand / 100 capacity = 0.85 ratio. Should be WARNING.
        w_warn = next((w for w in warnings if w["stop_id"] == self.stop_warning.id), None)
        assert w_warn is not None
        assert w_warn["severity"] == "WARNING"
        assert w_warn["predicted_crowd"] == 85
        
        # The Critical Stop has 110 pax demand / 100 capacity = 1.10 ratio. Should be CRITICAL.
        w_crit = next((w for w in warnings if w["stop_id"] == self.stop_critical.id), None)
        assert w_crit is not None
        assert w_crit["severity"] == "CRITICAL"
        assert w_crit["predicted_crowd"] == 110

    def test_live_state_queue_integration(self):
        # Add 20 people to the queue of the Normal stop via LiveStateEngine
        LiveStateEngine.update_stop_state(str(self.stop_normal.id), {
            "queue_count": 80
        })
        
        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()
        warnings = data.get("warnings", [])
        
        # Normal stop now has 80 queue + 10 demand = 90 / 100 capacity = 0.9. Should be WARNING.
        w_norm = next((w for w in warnings if w["stop_id"] == self.stop_normal.id), None)
        assert w_norm is not None
        assert w_norm["severity"] == "WARNING"
        assert w_norm["current_queue"] == 80
        assert w_norm["predicted_arrivals"] == 10
        assert w_norm["predicted_crowd"] == 90
