import dataclasses
from datetime import datetime, timedelta
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from core.api_disruption_views import DISRUPTIONS_DB
from simulation.interventions.sandbox import PreActionSandbox
from core.audit import AuditService
from simulation.state.live_state import LiveStateEngine
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# In-memory storage for Sandbox Results
SANDBOX_RESULTS_DB = {}

class SandboxGenerateView(APIView):
    def post(self, request):
        """
        Generates candidates and runs sandbox simulation.
        """
        data = request.data
        disruption_id = int(data.get("disruption_id"))
        profile_name = data.get("objective_profile", "BALANCED")
        horizon_minutes = int(data.get("horizon_minutes", 30))
        
        if disruption_id not in DISRUPTIONS_DB:
            return Response({"error": "Disruption not found"}, status=404)
            
        disruption = DISRUPTIONS_DB[disruption_id]
        
        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=horizon_minutes),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        scenario_id = str(uuid.uuid4())
        
        result = PreActionSandbox.run_sandbox(scenario_id, disruption, config, profile_name)
        SANDBOX_RESULTS_DB[scenario_id] = result
        
        # Notify clients (Phase 7 WebSocket requirement)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "twin",
            {
                "type": "twin_message",
                "message": {
                    "event": "SANDBOX_COMPLETED",
                    "scenario_id": scenario_id
                }
            }
        )
        
        return Response(dataclasses.asdict(result))

class SandboxApproveView(APIView):
    def post(self, request, candidate_id):
        data = request.data
        scenario_id = data.get("scenario_id")
        
        if scenario_id not in SANDBOX_RESULTS_DB:
            return Response({"error": "Scenario not found"}, status=404)
            
        result = SANDBOX_RESULTS_DB[scenario_id]
        
        # Find candidate
        candidate = next((c for c in result.candidates if c.id == candidate_id), None)
        if not candidate:
            return Response({"error": "Candidate not found"}, status=404)
            
        # Stale Check (Simple logic for Phase 7: if > 5 minutes old, reject)
        if (datetime.now() - result.generated_at).total_seconds() > 300:
            return Response({"error": "Simulation is stale. Recalculate before approval."}, status=400)
            
        # Apply to LiveState
        if candidate.type == "VEHICLE_REROUTE":
            # For demonstration, we just update a state flag in LiveState
            LiveStateEngine.update_vehicle_state(candidate.parameters["vehicle_id"], {
                "route_override": candidate.parameters["bypass_edges"]
            })
        elif candidate.type == "SPARE_VEHICLE_DEPLOYMENT":
            LiveStateEngine.update_vehicle_state(candidate.parameters["vehicle_id"], {
                "status": "ACTIVE"
            })
            
        # Audit Log
        AuditService.log_approval(
            scenario_id=scenario_id,
            candidate_id=candidate_id,
            operator_id=request.user.username if request.user.is_authenticated else "system_operator",
            action=f"Approved {candidate.type}"
        )
        
        # WebSocket broadcast
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "twin",
            {
                "type": "twin_message",
                "message": {
                    "event": "INTERVENTION_APPLIED",
                    "candidate_id": candidate_id
                }
            }
        )
        
        return Response({"status": "Success", "message": "Intervention Approved and Dispatched"})
