import copy
from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator
from simulation.disruptions.applicator import apply_disruption
from simulation.disruptions.blast_radius import calculate_blast_radius
from simulation.disruptions.models import Disruption, BlastRadiusResult

class PropagationEngine:
    @staticmethod
    def simulate_disruption(disruption: Disruption, config: dict) -> BlastRadiusResult:
        """
        Runs the full Phase 6 comparison:
        1. Snapshots the network.
        2. Runs Baseline.
        3. Runs Disrupted.
        4. Calculates and returns the Blast Radius (Delta).
        """
        # Create identical snapshots
        _, baseline_sim_state = StateSnapshotManager.create_snapshot()
        
        # Deepcopy for the disrupted run so it starts identically
        disrupted_sim_state = copy.deepcopy(baseline_sim_state)
        
        # Run Baseline
        baseline_sim = PassengerFlowSimulator(baseline_sim_state, config)
        baseline_metrics, _ = baseline_sim.run()
        
        # Apply Disruption to second state
        apply_disruption(disrupted_sim_state, disruption)
        
        # Run Disrupted Simulation
        disrupted_sim = PassengerFlowSimulator(disrupted_sim_state, config)
        disrupted_metrics, _ = disrupted_sim.run()
        
        # Calculate Blast Radius
        blast_radius = calculate_blast_radius(
            disruption_id=disruption.id,
            baseline_metrics=baseline_metrics,
            disrupted_metrics=disrupted_metrics,
            causal_graph=disrupted_sim.causal_graph,
            directly_affected_vehicles=disrupted_sim.directly_affected_vehicles,
            directly_affected_stops=disrupted_sim.directly_affected_stops,
            indirectly_affected_stops=disrupted_sim.indirectly_affected_stops
        )
        
        if disruption.type == "ROAD_BLOCK":
            blast_radius.directly_affected_edges.append(disruption.affected_entity_id)
            
        return blast_radius
