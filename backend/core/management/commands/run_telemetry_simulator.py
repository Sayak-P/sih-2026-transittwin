import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Vehicle, RouteEdge
from data.telemetry_pipeline import process_vehicle_telemetry

class Command(BaseCommand):
    help = 'Runs a deterministic telemetry simulator to move vehicles.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--ticks', type=int, default=100)
        parser.add_argument('--delay', type=float, default=1.0)

    def handle(self, *args, **options):
        from django.conf import settings
        if getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION') == 'LIVE':
            self.stdout.write(self.style.ERROR("FATAL: Telemetry simulator cannot be run in LIVE mode. Exiting to preserve data integrity."))
            return

        ticks = options['ticks']
        delay = options['delay']
        self.stdout.write("Initializing Telemetry Simulator...")

        vehicles = list(Vehicle.objects.all())
        
        # State for simulator
        sim_state = {}
        for v in vehicles:
            edges = list(RouteEdge.objects.filter(route=v.route).order_by('sequence_order'))
            if not edges:
                continue
            sim_state[v.identifier] = {
                "edges": edges,
                "current_edge_idx": 0,
                "progress": 0.0, # 0.0 to 1.0 along the edge
                "occupancy": 10
            }

        self.stdout.write(f"Simulating {len(sim_state)} vehicles for {ticks} ticks...")

        from datetime import timedelta
        
        for tick in range(ticks):
            for v_id, state in sim_state.items():
                edges = state['edges']
                idx = state['current_edge_idx']
                edge = edges[idx].edge
                
                # Check staleness and get speed
                is_stale = False
                if edge.data_source == 'TOMTOM' and edge.last_updated_at:
                    age = timezone.now() - edge.last_updated_at
                    if age > timedelta(minutes=15):
                        is_stale = True
                        
                if edge.data_source == 'ESTIMATED' or is_stale:
                    traffic_speed_ms = max(0.1, edge.free_flow_speed if edge.free_flow_speed else edge.current_traffic_speed)
                else:
                    traffic_speed_ms = max(0.1, edge.current_traffic_speed)
                
                traffic_speed_kmh = traffic_speed_ms * 3.6
                
                # Move forward based on distance and speed
                distance_m = max(1.0, edge.distance)
                progress_step = (traffic_speed_ms * delay) / distance_m
                state['progress'] += progress_step
                
                state['occupancy'] = min(60, state['occupancy'] + (1 if tick % 5 == 0 else 0))
                
                if state['progress'] >= 1.0:
                    state['progress'] = 0.0
                    state['current_edge_idx'] = (idx + 1) % len(edges)
                    edge = edges[state['current_edge_idx']].edge

                # Interpolate coords
                p1 = edge.geometry[0] # [lon, lat]
                p2 = edge.geometry[1]
                prog = min(1.0, max(0.0, state['progress']))
                lon = p1[0] + (p2[0] - p1[0]) * prog
                lat = p1[1] + (p2[1] - p1[1]) * prog

                sim_v_id = v_id if v_id.startswith("SIM-") else f"SIM-{v_id}"

                payload = {
                    "vehicle_id": sim_v_id,
                    "lat": lat,
                    "lon": lon,
                    "speed_kmh": traffic_speed_kmh,
                    "occupancy": state['occupancy'],
                    "timestamp": timezone.now().isoformat(),
                    "status": "ACTIVE",
                    "data_source": "SIMULATION"
                }

                # Push to pipeline
                process_vehicle_telemetry(payload)
                
            self.stdout.write(f"Tick {tick+1}/{ticks} processed.")
            time.sleep(delay)
