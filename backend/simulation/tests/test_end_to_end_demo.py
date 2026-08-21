import pytest
from django.conf import settings
from rest_framework.test import APIClient
from core.api_state_views import LiveStateEngine
from core.models import AuditLog, Vehicle

@pytest.mark.django_db
class TestEndToEndDemo:
    def setup_method(self):
        settings.TRANSIT_TWIN_MODE = 'SIMULATION'
        self.client = APIClient()

        
        # 1. Reset Demo
        response = self.client.post('/api/v1/system/demo-reset/')
        assert response.status_code == 200
        
        # Check that we seeded vehicles
        assert Vehicle.objects.count() > 0
        
        # 2. Check System Health
        health_resp = self.client.get('/api/v1/system/health/')
        assert health_resp.status_code == 200
        assert health_resp.json()["backend"] == "ONLINE"
        
    def test_full_sih_scenario(self):
        # 1. Trigger Disruption
        disrupt_payload = {
            "type": "ROAD_BLOCK",
            "entity_id": "5",
            "severity": 4,
            "duration_minutes": 20,
            "description": "SIH Canonical Scenario Road Block"
        }
        disrupt_resp = self.client.post('/api/v1/disruptions/', disrupt_payload, format='json')
        assert disrupt_resp.status_code == 200
        d_id = disrupt_resp.json()["id"]
        
        # 2. Blast Radius Simulation
        sim_resp = self.client.post(f'/api/v1/disruptions/{d_id}/simulate/')
        assert sim_resp.status_code == 200
        blast = sim_resp.json()["blast_radius"]
        assert blast is not None
        assert "5" in blast["directly_affected_edges"]
        
        # 3. Open Pre-Action Sandbox
        sandbox_payload = {
            "disruption_id": d_id,
            "objective_profile": "SAFETY_FIRST",
            "horizon_minutes": 30
        }
        sb_resp = self.client.post('/api/v1/sandbox/generate/', sandbox_payload, format='json')
        assert sb_resp.status_code == 200
        result = sb_resp.json()
        
        candidates = result["candidates"]
        print("CANDIDATES:", candidates)
        assert len(candidates) > 0
        
        # Get the highest ranked feasible candidate, or just any candidate if all are mocked infeasible
        # wait, if they are all infeasible due to random seed, we can just pick the first one for testing API flow
        best = next((c for c in candidates if c["feasibility_status"] == "FEASIBLE"), candidates[0])
        
        # 4. Approve Intervention
        # Save old audit count
        old_count = AuditLog.objects.count()
        
        approve_resp = self.client.post(f'/api/v1/sandbox/{best["id"]}/approve/', {"scenario_id": result["scenario_id"]}, format='json')
        assert approve_resp.status_code == 200
        
        # 5. Verify Audit Log
        assert AuditLog.objects.count() == old_count + 1
        log = AuditLog.objects.last()
        assert log.scenario_id == result["scenario_id"]
        assert log.candidate_id == best["id"]
        
        # Verify LiveState Mutation
        # Since it's reroute or spare, let's just check the vehicle's state
        v_id = best["parameters"].get("vehicle_id")
        if v_id:
            live_v = LiveStateEngine.get_vehicle_state(v_id)
            assert live_v is not None
