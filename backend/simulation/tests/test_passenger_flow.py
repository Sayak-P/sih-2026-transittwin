import pytest
from datetime import datetime, timedelta
from core.models import Vehicle, Stop, Edge, Route, RouteEdge
from prediction.models import ODDemand
from simulation.state.simulation_state import SimulationState
from simulation.passenger.queues import add_to_queue
from simulation.passenger.boarding import process_boarding
from simulation.passenger.alighting import process_alighting
from simulation.passenger.demand import generate_demand_cohorts
from simulation.engine.passenger_flow import PassengerFlowSimulator

@pytest.fixture
def base_sim_state():
    return SimulationState({
        "version": 1,
        "timestamp": "2026-08-18T10:00:00Z",
        "vehicles": {
            "BUS-1": {"vehicle_id": "BUS-1", "capacity": 50, "occupancy": 0, "accessible_capacity": 2, "lon": 0, "lat": 0}
        },
        "stops": {
            1: {"id": 1, "is_accessible": True},
            2: {"id": 2, "is_accessible": True},
            3: {"id": 3, "is_accessible": False}
        }
    })

def setup_cohort(sim_state, cohort_id, origin, dest, group, count, status="waiting"):
    sim_state.passenger_cohorts[cohort_id] = {
        "origin_id": origin,
        "destination_id": dest,
        "passenger_group": group,
        "total_generated": count,
        "waiting": 0,
        "onboard": 0,
        "completed": 0,
        "spawned": count
    }
    if status == "waiting":
        add_to_queue(sim_state, origin, cohort_id, count)
    elif status == "onboard":
        sim_state.vehicle_passengers["BUS-1"] = {cohort_id: count}
        sim_state.vehicles["BUS-1"]["occupancy"] += count
        sim_state.passenger_cohorts[cohort_id]["onboard"] = count

class TestPassengerFlowMechanics:
    def test_basic_boarding(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", origin=1, dest=2, group="NORMAL", count=10)
        base_sim_state.vehicles["BUS-1"]["occupancy"] = 20
        
        boarded = process_boarding(base_sim_state, "BUS-1", 1)
        assert boarded == 10
        assert base_sim_state.vehicles["BUS-1"]["occupancy"] == 30
        assert base_sim_state.passenger_cohorts["c1"]["waiting"] == 0
        assert base_sim_state.passenger_cohorts["c1"]["onboard"] == 10
        assert base_sim_state.stop_queues[1]["c1"] == 0

    def test_queue_accumulation_and_crowding_ratio(self, base_sim_state):
        # Stop 1 has a capacity of 20 (set for test)
        base_sim_state.stops[1]["capacity"] = 20
        
        # Add 15 passengers
        setup_cohort(base_sim_state, "c1", origin=1, dest=2, group="NORMAL", count=15)
        
        assert base_sim_state.metrics["max_queue_size"] == 15
        assert base_sim_state.metrics["max_crowding_ratio"] == 0.75
        
        # Add 10 more passengers (Queue = 25, Capacity = 20, Overcrowded!)
        setup_cohort(base_sim_state, "c2", origin=1, dest=2, group="NORMAL", count=10)
        
        assert base_sim_state.metrics["max_queue_size"] == 25
        assert base_sim_state.metrics["max_crowding_ratio"] == 1.25

    def test_capacity_limit(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", origin=1, dest=2, group="NORMAL", count=20)
        base_sim_state.vehicles["BUS-1"]["occupancy"] = 45 # Cap is 50
        
        boarded = process_boarding(base_sim_state, "BUS-1", 1)
        assert boarded == 5
        assert base_sim_state.vehicles["BUS-1"]["occupancy"] == 50
        assert base_sim_state.passenger_cohorts["c1"]["waiting"] == 15
        assert base_sim_state.stop_queues[1]["c1"] == 15
        assert base_sim_state.metrics["capacity_denied_boardings"] == 15

    def test_alighting(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", origin=1, dest=2, group="NORMAL", count=12, status="onboard")
        assert base_sim_state.vehicles["BUS-1"]["occupancy"] == 12
        
        alighted = process_alighting(base_sim_state, "BUS-1", 2)
        assert alighted == 12
        assert base_sim_state.vehicles["BUS-1"]["occupancy"] == 0
        assert base_sim_state.passenger_cohorts["c1"]["completed"] == 12

    def test_od_correctness(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", origin=1, dest=3, group="NORMAL", count=12, status="onboard")
        # Stop 2 should NOT trigger alighting for destination 3
        alighted = process_alighting(base_sim_state, "BUS-1", 2)
        assert alighted == 0
        assert base_sim_state.vehicles["BUS-1"]["occupancy"] == 12
        assert base_sim_state.passenger_cohorts["c1"]["completed"] == 0

    def test_accessibility_rejection(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", origin=3, dest=1, group="STEP_FREE_REQUIRED", count=5)
        # Stop 3 is not accessible. They should not be able to board.
        boarded = process_boarding(base_sim_state, "BUS-1", 3)
        assert boarded == 0
        assert base_sim_state.passenger_cohorts["c1"]["waiting"] == 5
        assert base_sim_state.metrics["accessibility_denied_boardings"] == 5

@pytest.mark.django_db
class TestEngineAndConservation:
    def test_engine_conservation_and_determinism(self):
        # 1. Setup minimal DB for engine
        s1 = Stop.objects.create(name="A", lat=0, lon=0, capacity=100)
        s2 = Stop.objects.create(name="B", lat=1, lon=1, capacity=100)
        route = Route.objects.create(name="R1")
        e1 = Edge.objects.create(source=s1, target=s2, distance=100, geometry=[[0,0], [1,1]], baseline_travel_time=10)
        RouteEdge.objects.create(route=route, edge=e1, sequence_order=1)
        v = Vehicle.objects.create(identifier="BUS-X", route=route, capacity=50)
        ODDemand.objects.create(origin_stop=s1, destination_stop=s2, expected_passenger_count=20, time_window_start=datetime.now(), time_window_end=datetime.now() + timedelta(minutes=30))

        # 2. Setup engine
        sim_state = SimulationState({
            "vehicles": {"BUS-X": {"occupancy": 0, "capacity": 50}},
            "stops": {s1.id: {"is_accessible": True}, s2.id: {"is_accessible": True}}
        })
        config = {
            "start_time": datetime(2026,1,1, 8, 0, 0),
            "end_time": datetime(2026,1,1, 8, 10, 0),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        sim = PassengerFlowSimulator(sim_state, config)
        metrics, log = sim.run()
        
        assert metrics["passengers_generated"] == 20
        # Conservation law is enforced inherently inside `_verify_conservation` during `run()`
        # If it completes without raising AssertionError, it conserved passengers perfectly across 60 ticks.
        
        # Test 8 Determinism
        sim_state2 = SimulationState({
            "vehicles": {"BUS-X": {"occupancy": 0, "capacity": 50}},
            "stops": {s1.id: {"is_accessible": True}, s2.id: {"is_accessible": True}}
        })
        sim2 = PassengerFlowSimulator(sim_state2, config)
        metrics2, _ = sim2.run()
        
        assert metrics == metrics2 # Identical results

    def test_state_isolation_phase4(self):
        # Just ensure SimulationState methods don't touch LiveState
        from simulation.state.live_state import LiveStateEngine
        from simulation.state.snapshot_manager import StateSnapshotManager
        
        LiveStateEngine.update_vehicle_state("BUS-ISO", {"occupancy": 0})
        
        scenario, sim_state = StateSnapshotManager.create_snapshot()
        
        # Passenger logic acts on sim_state
        sim_state.vehicles["BUS-ISO"]["occupancy"] = 50
        
        # Live state must remain 0
        live = LiveStateEngine.get_vehicle_state("BUS-ISO")
        assert live["occupancy"] == 0
