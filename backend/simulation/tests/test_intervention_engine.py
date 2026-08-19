import pytest
from datetime import datetime, timedelta
from simulation.disruptions.models import Disruption
from simulation.interventions.models import ObjectiveProfile, PROFILES
from simulation.interventions.generator import CandidateGenerator
from simulation.interventions.scorer import CandidateScorer
from simulation.interventions.sandbox import PreActionSandbox
from simulation.state.simulation_state import SimulationState
from simulation.passenger.queues import add_to_queue

@pytest.fixture
def base_sim_state():
    return SimulationState({
        "version": 1,
        "vehicles": {
            "BUS-1": {"vehicle_id": "BUS-1", "capacity": 50, "occupancy": 0, "status": "ACTIVE"},
            "BUS-SPARE": {"vehicle_id": "BUS-SPARE", "capacity": 50, "occupancy": 0, "status": "SPARE"}
        },
        "stops": {
            1: {"capacity": 100},
            2: {"capacity": 100},
            3: {"capacity": 100}
        }
    })

@pytest.mark.django_db
class TestInterventionEngine:
    def test_candidate_generation(self, base_sim_state):
        from core.models import Stop, Edge
        s1 = Stop.objects.create(name="S1", lat=0, lon=0, capacity=100)
        s2 = Stop.objects.create(name="S2", lat=0.01, lon=0, capacity=100)
        s3 = Stop.objects.create(name="S3", lat=0.01, lon=0.01, capacity=100)
        e = Edge.objects.create(id=1, source=s1, target=s2, distance=1000, geometry=[[0,0], [0.01,0]], baseline_travel_time=100)
        Edge.objects.create(source=s1, target=s3, distance=600, geometry=[[0,0], [0.01,0.01]], baseline_travel_time=60)
        Edge.objects.create(source=s3, target=s2, distance=600, geometry=[[0.01,0.01], [0.01,0]], baseline_travel_time=60)
        
        disruption = Disruption(
            id=1,
            type="ROAD_BLOCK",
            affected_entity_id="1",
            severity=5,
            start_time=datetime.now(),
            duration_minutes=60,
            description="Block"
        )
        candidates = CandidateGenerator.generate_candidates("scen1", disruption, base_sim_state)
        # Should generate reroute, spare, and schedule mod
        types = [c.type for c in candidates]
        assert "VEHICLE_REROUTE" in types
        assert "SPARE_VEHICLE_DEPLOYMENT" in types
        assert "SCHEDULE_MODIFICATION" in types

    def test_scoring_and_ranking(self):
        from simulation.interventions.models import InterventionCandidate
        
        c1 = InterventionCandidate(id="1", scenario_id="s", type="REROUTE", parameters={}, description="")
        c1.raw_metrics = {"total_waiting_seconds": 0, "max_crowding_ratio": 1.0}
        
        c2 = InterventionCandidate(id="2", scenario_id="s", type="SPARE", parameters={}, description="")
        c2.raw_metrics = {"total_waiting_seconds": 500, "max_crowding_ratio": 0.0}
        
        baseline = {"total_waiting_seconds": 0, "max_crowding_ratio": 0.0}
        disrupted = {"total_waiting_seconds": 500, "max_crowding_ratio": 1.5}
        
        # Test SAFETY_FIRST (favors c2 which has lower crowding 0.0 vs 1.0)
        CandidateScorer.score_candidate(c1, baseline, disrupted, PROFILES["SAFETY_FIRST"])
        CandidateScorer.score_candidate(c2, baseline, disrupted, PROFILES["SAFETY_FIRST"])
        
        assert c2.score < c1.score
        
        # Test MINIMUM_DELAY
        CandidateScorer.score_candidate(c1, baseline, disrupted, PROFILES["MINIMUM_DELAY"])
        CandidateScorer.score_candidate(c2, baseline, disrupted, PROFILES["MINIMUM_DELAY"])
        
        assert isinstance(c1.score, float)
        assert isinstance(c2.score, float)

    def test_sandbox_canonical(self, base_sim_state):
        from core.models import Stop, Route, Edge, RouteEdge, Vehicle
        from prediction.models import ODDemand
        
        s1 = Stop.objects.create(name="S1", lat=0, lon=0, capacity=100)
        s2 = Stop.objects.create(name="S2", lat=0.01, lon=0, capacity=100)
        s3 = Stop.objects.create(name="S3", lat=0.01, lon=0.01, capacity=100)
        
        route = Route.objects.create(name="R1")
        e_blocked = Edge.objects.create(source=s1, target=s2, distance=1000, geometry=[[0,0], [0.01,0]], baseline_travel_time=100)
        
        # Alternate path
        e_alt1 = Edge.objects.create(source=s1, target=s3, distance=600, geometry=[[0,0], [0.01,0.01]], baseline_travel_time=60)
        e_alt2 = Edge.objects.create(source=s3, target=s2, distance=600, geometry=[[0.01,0.01], [0.01,0]], baseline_travel_time=60)
        
        RouteEdge.objects.create(route=route, edge=e_blocked, sequence_order=1)
        
        Vehicle.objects.create(identifier="BUS-1", route=route, capacity=50)
        
        disruption = Disruption(id=1, type="ROAD_BLOCK", affected_entity_id=str(e_blocked.id), severity=5, 
                                start_time=datetime.now(), duration_minutes=60, description="Block")
        
        config = {"start_time": datetime.now(), "end_time": datetime.now() + timedelta(minutes=10), "timestep_seconds": 10, "random_seed": 42}
        
        from simulation.state.live_state import LiveStateEngine
        LiveStateEngine.update_vehicle_state("BUS-1", {"occupancy": 0, "capacity": 50, "lat": 0, "lon": 0, "status": "ACTIVE"})
        LiveStateEngine.update_vehicle_state("BUS-SPARE", {"status": "SPARE"})
        
        result = PreActionSandbox.run_sandbox("s1", disruption, config, "BALANCED")
        
        assert result.candidates
        types = [c.type for c in result.candidates]
        assert "VEHICLE_REROUTE" in types # It should have found the alternate path e_alt1 -> e_alt2!
