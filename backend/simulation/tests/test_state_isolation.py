import pytest
from simulation.state.live_state import LiveStateEngine
from simulation.state.snapshot_manager import StateSnapshotManager

@pytest.mark.django_db
class TestStateIsolation:
    def test_simulation_mutation_does_not_affect_live(self):
        # 1. Setup Live State
        payload = {
            "vehicle_id": "TEST-99",
            "occupancy": 30
        }
        LiveStateEngine.update_vehicle_state("TEST-99", payload)
        
        # 2. Create Snapshot
        scenario, sim_state = StateSnapshotManager.create_snapshot()
        
        assert sim_state.vehicles["TEST-99"]["occupancy"] == 30
        
        # 3. Mutate Simulation State
        sim_state.update_vehicle_state("TEST-99", {"occupancy": 50})
        
        # 4. Verify Isolation
        assert sim_state.vehicles["TEST-99"]["occupancy"] == 50
        
        live_veh = LiveStateEngine.get_vehicle_state("TEST-99")
        assert live_veh["occupancy"] == 30
