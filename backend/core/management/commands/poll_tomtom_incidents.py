import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from dateutil import parser
from core.models import Disruption, Edge
from integrations.tomtom.client import fetch_incidents
from integrations.tomtom.matcher import find_nearest_edge
from simulation.engine.propagation_engine import PropagationEngine
from core.api_sandbox_views import SANDBOX_RESULTS_DB
from simulation.interventions.generator import CandidateGenerator
from simulation.state.snapshot_manager import StateSnapshotManager

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Polls TomTom Incidents API and safely ingests them into the Sandbox pipeline.'

    def handle(self, *args, **options):
        self.stdout.write("Polling TomTom Incidents API...")
        
        raw_data = fetch_incidents()
        
        if raw_data is None:
            self.stdout.write(self.style.WARNING("No incident data received (likely LIVE mode with no API key or provider failure). Skipping update."))
            return
            
        parsed_incidents = []
        if isinstance(raw_data, dict) and "incidents" in raw_data:
            # Parse real TomTom API schema
            for inc in raw_data["incidents"]:
                props = inc.get("properties", {})
                geom = inc.get("geometry", {})
                coords = geom.get("coordinates", [])
                
                if coords:
                    if geom.get("type") == "LineString":
                        lon, lat = coords[0][0], coords[0][1]
                    else:
                        lon, lat = coords[0], coords[1]
                else:
                    continue
                    
                parsed_incidents.append({
                    "provider": "TOMTOM",
                    "provider_incident_id": props.get("id"),
                    "incident_type": "ROAD_BLOCK" if props.get("iconCategory") in [1, 2, 3] else "WARNING",
                    "severity": "HIGH" if props.get("magnitudeOfDelay") in [3, 4] else "MEDIUM",
                    "description": props.get("description", "Unknown Incident"),
                    "latitude": lat,
                    "longitude": lon,
                    "start_time": props.get("startTime", timezone.now().isoformat()),
                    "status": "ACTIVE"
                })
        elif isinstance(raw_data, list):
            # Parse Mock fallback
            parsed_incidents = raw_data
            
        edges = list(Edge.objects.all())
        if not edges:
            self.stdout.write(self.style.ERROR("No edges found. Have you imported OSM network?"))
            return

        for inc in parsed_incidents:
            provider_id = inc["provider_incident_id"]
            lat = inc["latitude"]
            lon = inc["longitude"]
            
            # Spatial Matching
            nearest_edge = find_nearest_edge(lat, lon, edges)
            
            if not nearest_edge:
                self.stdout.write(self.style.WARNING(f"Could not match incident {provider_id} to an edge. Skipping."))
                continue
                
            # Parse time
            try:
                start_time = parser.parse(inc["start_time"])
            except:
                start_time = timezone.now()

            # Idempotent creation/update
            disruption, created = Disruption.objects.update_or_create(
                provider_incident_id=provider_id,
                defaults={
                    "source": "EXTERNAL",
                    "data_source": inc["provider"],
                    "disruption_type": "ROAD_BLOCK" if inc["incident_type"] == "ACCIDENT" else inc["incident_type"],
                    "severity": inc["severity"],
                    "description": inc["description"],
                    "affected_edge": nearest_edge,
                    "start_time": start_time,
                    "is_active": inc["status"] == "ACTIVE"
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f"Ingested new external incident: {provider_id} mapped to Edge {nearest_edge.id}"))
                
                # Push the new incident through the Sandbox pipeline!
                # Generate Blast Radius (Impact)
                from datetime import timedelta
                from simulation.disruptions.models import Disruption as MemoryDisruption
                
                mem_disruption = MemoryDisruption(
                    id=disruption.id,
                    type=disruption.disruption_type,
                    affected_entity_id=str(nearest_edge.id),
                    severity=disruption.severity,
                    start_time=disruption.start_time,
                    duration_minutes=60,
                    description=disruption.description
                )
                
                config = {
                    "start_time": timezone.now(),
                    "end_time": timezone.now() + timedelta(minutes=60),
                    "timestep_seconds": 10,
                    "random_seed": 42
                }
                
                blast_radius = PropagationEngine.simulate_disruption(mem_disruption, config)
                
                # Generate Rerouting Candidates
                _, sim_state = StateSnapshotManager.create_snapshot()
                candidates = CandidateGenerator.generate_candidates(str(disruption.id), mem_disruption, sim_state)
                
                # Store in Sandbox
                sandbox_entry = {
                    "disruption": {
                        "id": disruption.id,
                        "type": disruption.disruption_type,
                        "severity": disruption.severity,
                        "description": disruption.description,
                        "affected_entity": f"Edge {nearest_edge.id}"
                    },
                    "impact": blast_radius.__dict__,
                    "candidates": [c.__dict__ for c in candidates],
                    "status": "PENDING_APPROVAL"
                }
                SANDBOX_RESULTS_DB[str(disruption.id)] = sandbox_entry
                self.stdout.write(self.style.SUCCESS(f"Successfully generated Sandbox candidates for {provider_id}"))
                    
            else:
                self.stdout.write(f"Updated existing external incident: {provider_id}")

        # Broadcast via WebSockets
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "twin_events",
            {
                "type": "broadcast_event",
                "event": "incident_created",
                "data": {"message": f"Polled and processed {len(parsed_incidents)} external incidents."}
            }
        )
        
        self.stdout.write(self.style.SUCCESS("Incident polling complete."))
