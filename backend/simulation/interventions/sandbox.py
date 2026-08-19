import copy
from simulation.interventions.models import SandboxResult, PROFILES
from simulation.interventions.generator import CandidateGenerator
from simulation.interventions.applicator import apply_intervention_to_state
from simulation.interventions.scorer import CandidateScorer
from simulation.engine.passenger_flow import PassengerFlowSimulator
from simulation.disruptions.applicator import apply_disruption
from simulation.state.snapshot_manager import StateSnapshotManager

class PreActionSandbox:
    @staticmethod
    def run_sandbox(scenario_id: str, disruption, config: dict, profile_name: str) -> SandboxResult:
        # 1. Snapshot LiveState
        _, base_state = StateSnapshotManager.create_snapshot()
        
        # 2. Baseline run
        baseline_sim = PassengerFlowSimulator(copy.deepcopy(base_state), config)
        baseline_metrics, _ = baseline_sim.run()
        
        # 3. Disrupted (No Action) run
        no_action_state = copy.deepcopy(base_state)
        apply_disruption(no_action_state, disruption)
        no_action_sim = PassengerFlowSimulator(no_action_state, config)
        no_action_metrics, _ = no_action_sim.run()
        
        # 4. Generate Candidates
        candidates = CandidateGenerator.generate_candidates(scenario_id, disruption, base_state)
        
        # 5. Simulate Feasible Candidates
        profile = PROFILES.get(profile_name, PROFILES["BALANCED"])
        
        for candidate in candidates:
            if candidate.feasibility_status == "INFEASIBLE":
                CandidateScorer.score_candidate(candidate, baseline_metrics, no_action_metrics, profile)
                continue
                
            # Create isolated state for this candidate
            cand_state = copy.deepcopy(base_state)
            
            # Apply disruption
            apply_disruption(cand_state, disruption)
            
            # Apply intervention
            apply_intervention_to_state(cand_state, candidate)
            
            # Simulate
            cand_sim = PassengerFlowSimulator(cand_state, config)
            cand_metrics, _ = cand_sim.run()
            
            candidate.raw_metrics = cand_metrics
            
            # Score
            CandidateScorer.score_candidate(candidate, baseline_metrics, no_action_metrics, profile)
            
        # 6. Rank Candidates
        feasible_cands = [c for c in candidates if c.feasibility_status == "FEASIBLE"]
        feasible_cands.sort(key=lambda c: c.score)
        
        rank = 1
        for c in feasible_cands:
            c.rank = rank
            rank += 1
            
        # Add back infeasible at the bottom
        infeasible_cands = [c for c in candidates if c.feasibility_status == "INFEASIBLE"]
        for c in infeasible_cands:
            c.rank = rank
            
        ranked_candidates = feasible_cands + infeasible_cands
        
        # 7. Return Result
        return SandboxResult(
            scenario_id=scenario_id,
            simulation_horizon_minutes=int((config["end_time"] - config["start_time"]).total_seconds() / 60),
            objective_profile=profile.name,
            baseline_metrics=baseline_metrics,
            disrupted_metrics=no_action_metrics,
            candidates=ranked_candidates
        )
