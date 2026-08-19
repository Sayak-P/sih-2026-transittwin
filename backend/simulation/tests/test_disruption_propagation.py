import pytest
from datetime import datetime
from simulation.disruptions.models import Disruption
from simulation.state.simulation_state import SimulationState
from simulation.engine.propagation_engine import PropagationEngine
from simulation.passenger.queues import add_to_queue

@pytest.fixture
def base_sim_state():
    # Simple deterministic network
    return SimulationState({
        "version": 1,
        "vehicles": {
            "BUS-1": {"vehicle_id": "BUS-1", "capacity": 50, "occupancy": 0, "status": "ACTIVE"}
        },
        "stops": {
            1: {"capacity": 100},
            2: {"capacity": 100},
            3: {"capacity": 100}
        }
    })

def setup_cohort(sim_state, cohort_id, origin, dest, count):
    sim_state.passenger_cohorts[cohort_id] = {
        "origin_id": origin,
        "destination_id": dest,
        "passenger_group": "NORMAL",
        "total_generated": count,
        "waiting": count,
        "onboard": 0,
        "completed": 0,
        "spawned": count
    }
    add_to_queue(sim_state, origin, cohort_id, count)

@pytest.mark.django_db
class TestDisruptionPropagation:
    def test_vehicle_breakdown_impact(self, base_sim_state):
        setup_cohort(base_sim_state, "c1", 1, 2, 20)
        
        disruption = Disruption(
            id=1,
            type="VEHICLE_BREAKDOWN",
            affected_entity_id="BUS-1",
            severity=5,
            start_time=datetime.now(),
            duration_minutes=60,
            description="Broken down bus"
        )
        
        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now(),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        # We manually test applicator logic here before running full propagation
        from simulation.disruptions.applicator import apply_disruption
        apply_disruption(base_sim_state, disruption)
        
        assert base_sim_state.vehicles["BUS-1"]["capacity"] == 0
        assert base_sim_state.vehicles["BUS-1"]["status"] == "BROKEN_DOWN"

    def test_state_isolation(self, base_sim_state):
        from simulation.state.live_state import LiveStateEngine
        
        LiveStateEngine.update_vehicle_state("BUS-ISO", {"capacity": 50})
        
        disruption = Disruption(
            id=2,
            type="VEHICLE_BREAKDOWN",
            affected_entity_id="BUS-ISO",
            severity=5,
            start_time=datetime.now(),
            duration_minutes=60,
            description="Isolate test"
        )
        
        # Run propagation
        # It creates a snapshot, so it shouldn't modify LiveState
        PropagationEngine.simulate_disruption(disruption, {
            "start_time": datetime.now(),
            "end_time": datetime.now(),
            "timestep_seconds": 10,
            "random_seed": 42
        })
        
        # Verify LiveState remains pure
        live_veh = LiveStateEngine.get_vehicle_state("BUS-ISO")
        assert live_veh["capacity"] == 50

    def test_canonical_road_block_scenario(self):
        # We need a proper DB seeded for a real simulation run.
        # This tests the full causal chain: ROAD_BLOCK -> DELAY -> QUEUE -> BOTTLENECK
        from core.models import Stop, Route, Edge, RouteEdge, Vehicle
        from prediction.models import ODDemand
        from datetime import timedelta
        
        # 1. Setup DB
        s0 = Stop.objects.create(name="S0", lat=-0.01, lon=0, capacity=100)
        s1 = Stop.objects.create(name="S1", lat=0, lon=0, capacity=100)
        s2 = Stop.objects.create(name="S2", lat=0.01, lon=0, capacity=100)
        
        route = Route.objects.create(name="R1")
        # e0: S0 -> S1
        e0 = Edge.objects.create(source=s0, target=s1, distance=1000, geometry=[[-0.01,0], [0,0]], baseline_travel_time=100)
        # e1: S1 -> S2
        e1 = Edge.objects.create(source=s1, target=s2, distance=1000, geometry=[[0,0], [0.01,0]], baseline_travel_time=100)
        
        RouteEdge.objects.create(route=route, edge=e0, sequence_order=1)
        RouteEdge.objects.create(route=route, edge=e1, sequence_order=2)
        
        v = Vehicle.objects.create(identifier="BUS-CANON", route=route, capacity=50)
        ODDemand.objects.create(origin_stop=s1, destination_stop=s2, expected_passenger_count=30, 
                                time_window_start=datetime.now(), time_window_end=datetime.now() + timedelta(minutes=10))

        # 2. Setup Disruption - Block e0 so bus never reaches s1!
        disruption = Disruption(
            id=3,
            type="ROAD_BLOCK",
            affected_entity_id=str(e0.id),
            severity=5,
            start_time=datetime.now(),
            duration_minutes=60,
            description="Canonical block"
        )
        
        from simulation.state.live_state import LiveStateEngine
        LiveStateEngine.update_vehicle_state("BUS-CANON", {"occupancy": 0, "capacity": 50, "lat": 0, "lon": 0})
        LiveStateEngine.update_stop_state(s1.id, {"is_accessible": True, "capacity": 100})
        
        # 3. Simulate
        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=10),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        blast_radius = PropagationEngine.simulate_disruption(disruption, config)
        
        # 4. Verify Causal Chain
        assert blast_radius.propagation_depth >= 1
        assert "BUS-CANON" in blast_radius.directly_affected_vehicles
        
        # Bus didn't move because of road block! So it never reached s2.
        # Demand spawned at S1 but Bus never picked them up.
        # Wait time should be drastically higher in Disrupted vs Baseline.
        assert blast_radius.delta_passenger_waiting_minutes > 0
        assert blast_radius.delta_max_queue > 0
        
        # Verify specific causal graph
        graph_reasons = [node['reason'] for node in blast_radius.causal_graph]
        assert any("ROAD_BLOCK" in r for r in graph_reasons)
