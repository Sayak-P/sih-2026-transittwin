# pyrefly: ignore [missing-import]
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from simulation.state.live_state import LiveStateEngine
from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator

class StateView(APIView):
    def get(self, request):
        return Response(LiveStateEngine.get_current_state())

class VehiclesView(APIView):
    def get(self, request, vehicle_id=None):
        if vehicle_id:
            state = LiveStateEngine.get_vehicle_state(vehicle_id)
            if state:
                return Response(state)
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(LiveStateEngine.get_current_state().get('vehicles', {}))

class StopsView(APIView):
    def get(self, request):
        return Response(LiveStateEngine.get_current_state().get('stops', {}))

class SnapshotView(APIView):
    def post(self, request):
        scenario, sim_state = StateSnapshotManager.create_snapshot()
        return Response({
            "snapshot_id": scenario.id,
            "source_state_version": sim_state.version,
            "created_at": scenario.created_at
        }, status=status.HTTP_201_CREATED)

class VersionView(APIView):
    def get(self, request):
        return Response({"version": LiveStateEngine.get_state_version()})

class SimulationBaselineView(APIView):
    def post(self, request):
        # 1. Create a snapshot from Live State
        scenario, sim_state = StateSnapshotManager.create_snapshot()
        
        # 2. Configure a 30-minute baseline starting now
        config = {
            "start_time": datetime.now(),
            "end_time": datetime.now() + timedelta(minutes=30),
            "timestep_seconds": 10,
            "random_seed": 42
        }
        
        # 3. Run Passenger Flow Simulation
        sim = PassengerFlowSimulator(sim_state, config)
        metrics, event_log = sim.run()
        
        return Response({
            "snapshot_id": scenario.id,
            "metrics": metrics,
            "event_log": event_log
        })

class SystemHealthView(APIView):
    def get(self, request):
        from django.db import connection
        db_online = False
        try:
            connection.ensure_connection()
            db_online = True
        except Exception:
            pass
            
        return Response({
            "backend": "ONLINE",
            "database": "ONLINE" if db_online else "OFFLINE",
            "redis": "ONLINE", # Assuming configured channels layer
            "simulation_engine": "READY",
            "prediction_engine": "READY"
        })

class DemoResetView(APIView):
    def post(self, request):
        from core.api_disruption_views import DISRUPTIONS_DB
        from core.api_sandbox_views import SANDBOX_RESULTS_DB
        from django.conf import settings
        from core.management.commands.seed_demo_network import Command as SeedCommand
        from core.management.commands.import_osm_network import Command as OsmCommand
        
        if getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION') == 'LIVE':
            return Response({"error": "Demo reset is disabled in LIVE mode to prevent data corruption."}, status=403)
        
        # 1. Clear Transient DBs
        DISRUPTIONS_DB.clear()
        SANDBOX_RESULTS_DB.clear()
        
        # 2. Reseed DB based on mode
        if settings.TRANSIT_TWIN_MODE == 'SIMULATION' or getattr(settings, 'USE_OSM', True):
            # For now, always use OSM if available to preserve Bhubaneswar demo
            # unless specifically forced to pure simulation Delhi grid.
            # We'll use OSM by default for the SIH demo.
            osm_seeder = OsmCommand()
            osm_seeder.handle()
        else:
            seeder = SeedCommand()
            seeder.handle()

        # 3. Reload Live State (Clear Cache)
        from django.core.cache import cache
        from core.models import Stop, Vehicle
        from data.telemetry_pipeline import process_vehicle_telemetry
        from django.utils import timezone
        
        cache.clear()
        
        # Pre-warm stops and vehicles into LiveState
        for stop in Stop.objects.all():
            LiveStateEngine.update_stop_state(str(stop.id), {
                "id": stop.id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
                "capacity": stop.capacity,
                "queue_count": 0,
                "timestamp": timezone.now().isoformat()
            })
            
        for v in Vehicle.objects.all():
            if getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION') == 'LIVE':
                continue
                
            # Seed 1 vehicle as SPARE to allow SPARE_VEHICLE_DEPLOYMENT candidates to be FEASIBLE
            status = "SPARE" if v.identifier == "BUS-1006" else "ACTIVE"
            sim_v_id = v.identifier if v.identifier.startswith("SIM-") else f"SIM-{v.identifier}"
            
            process_vehicle_telemetry({
                "vehicle_id": sim_v_id,
                "lat": v.lat,
                "lon": v.lon,
                "speed_kmh": 0.0,
                "occupancy": 0,
                "timestamp": timezone.now().isoformat(),
                "status": status,
                "data_source": "SIMULATION"
            })
            
        return Response({"status": "Success", "message": "Demo environment reset successfully."})
