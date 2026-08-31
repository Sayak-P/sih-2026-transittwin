from simulation.interventions.models import ObjectiveProfile, InterventionCandidate

class CandidateScorer:
    @staticmethod
    def score_candidate(candidate: InterventionCandidate, baseline_metrics: dict, disrupted_metrics: dict, profile: ObjectiveProfile):
        if candidate.feasibility_status == "INFEASIBLE":
            candidate.score = 999.0
            candidate.explanation = "Candidate is physically infeasible. " + " ".join(candidate.constraint_violations)
            return

        # Calculate benefit (Disrupted NO ACTION - Candidate)
        c_metrics = candidate.raw_metrics
        
        # Positive means candidate is better (saved time)
        saved_waiting = (disrupted_metrics.get("total_waiting_seconds", 0) - c_metrics.get("total_waiting_seconds", 0)) / 60.0
        saved_crowding = max(0, disrupted_metrics.get("max_crowding_ratio", 0) - c_metrics.get("max_crowding_ratio", 0))
        
        # Calculate Energy Delta
        # For Phase 8, use deterministic energy model
        from core.models import Vehicle
        
        added_energy = 0.0
        added_distance = 0.0
        
        if candidate.type == "VEHICLE_REROUTE":
            added_distance = candidate.parameters.get("added_distance", 0)
            v_id = candidate.parameters.get("vehicle_id")
            v_obj = Vehicle.objects.filter(identifier=v_id).first()
            rate = v_obj.energy_rate_kwh_per_km if v_obj else 1.2
            added_energy = (added_distance / 1000.0) * rate
        elif candidate.type == "SPARE_VEHICLE_DEPLOYMENT":
            v_id = candidate.parameters.get("vehicle_id")
            v_obj = Vehicle.objects.filter(identifier=v_id).first()
            rate = v_obj.energy_rate_kwh_per_km if v_obj else 1.2
            # Cost of spinning up a spare bus and driving it
            # Assume ~10km of base driving
            added_energy = 10.0 * rate
            
        accessibility_violation = (c_metrics.get("accessibility_denied_boardings", 0) - baseline_metrics.get("accessibility_denied_boardings", 0)) > 0
        
        # Save delta metrics for UI
        candidate.delta_metrics = {
            "waiting_minutes_saved": saved_waiting,
            "crowding_ratio_saved": saved_crowding,
            "energy_kwh": added_energy,
            "distance_km": added_distance,
            "accessibility_preserved": not accessibility_violation
        }

        penalty_delay = max(0, 1.0 - (saved_waiting / 500.0))
        penalty_crowding = max(0, 1.0 - (saved_crowding / 2.0))
        penalty_energy = min(1.0, added_energy / 20.0)
        penalty_safety = min(1.0, c_metrics.get("max_crowding_ratio", 0) / 1.5)
        
        weight_safety = getattr(profile, 'weight_safety', 0.0)
        
        # Composite score
        score = (penalty_delay * profile.weight_delay) + \
                (penalty_crowding * profile.weight_crowding) + \
                (penalty_energy * profile.weight_energy) + \
                (penalty_safety * weight_safety)
                
        if accessibility_violation:
            score += profile.accessibility_penalty
            
        candidate.score = score
        
        # Generate Explanation
        explanation = []
        if candidate.type == "VEHICLE_REROUTE":
            explanation.append(f"Rerouting avoids the blocked segment.")
            explanation.append(f"Adds {added_distance/1000.0:.1f} km to the route.")
        elif candidate.type == "SPARE_VEHICLE_DEPLOYMENT":
            explanation.append(f"Deploys a spare vehicle to absorb queue overload.")
        elif candidate.type == "SCHEDULE_MODIFICATION":
            explanation.append(f"Holds vehicle to improve spacing.")
        elif candidate.type == "TEMPORARY_STOP_CLOSURE":
            explanation.append(f"Closes severely overcrowded stop.")
            
        if saved_waiting > 0:
            explanation.append(f"Expected to save {saved_waiting:.1f} passenger-minutes vs doing nothing.")
        else:
            explanation.append(f"Passenger delay increases by {-saved_waiting:.1f} minutes.")
            
        candidate.explanation = " ".join(explanation)
