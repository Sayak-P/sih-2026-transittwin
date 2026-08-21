import dataclasses
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from simulation.disruptions.models import Disruption
from simulation.engine.propagation_engine import PropagationEngine
import uuid

# In-memory storage for Phase 6 disruptions sandbox
# Key: disruption_id, Value: Disruption
DISRUPTIONS_DB = {}

class DisruptionListView(APIView):
    def get(self, request):
        """
        Returns all active disruptions from the database, serialized.
        """
        from core.models import Disruption as DbDisruption
        from core.serializers import DisruptionSerializer
        
        # We fetch active disruptions from DB to include external ones
        disruptions = DbDisruption.objects.filter(is_active=True)
        serializer = DisruptionSerializer(disruptions, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        Creates a new disruption scenario.
        """
        data = request.data
        d_id = len(DISRUPTIONS_DB) + 1
        
        disruption = Disruption(
            id=d_id,
            type=data.get("type", "ROAD_BLOCK"),
            affected_entity_id=str(data.get("edge_id") or data.get("entity_id")),
            severity=int(data.get("severity", 4)),
            start_time=datetime.now(),
            duration_minutes=int(data.get("duration_minutes", 20)),
            description=data.get("description", "Operator created disruption")
        )
        
        DISRUPTIONS_DB[d_id] = disruption
        
        return Response({"id": d_id, "message": "Disruption created successfully"})

class DisruptionSimulateView(APIView):
    def post(self, request, pk):
        """
        Runs the propagation engine for a given disruption ID.
        """
        if pk not in DISRUPTIONS_DB:
            return Response({"error": "Disruption not found"}, status=404)
            
        disruption = DISRUPTIONS_DB[pk]
        
        # Configure a 60-minute horizon
        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=60),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        blast_radius = PropagationEngine.simulate_disruption(disruption, config)
        
        # Serialize dataclass
        result = dataclasses.asdict(blast_radius)
        
        return Response({
            "disruption": dataclasses.asdict(disruption),
            "blast_radius": result
        })
