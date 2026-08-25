import time
import math
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Vehicle, RouteEdge
from data.telemetry_pipeline import process_vehicle_telemetry


def interpolate_along_geometry(geometry, progress):
    """
    Interpolate a position along a multi-point geometry.
    progress: 0.0 = start, 1.0 = end
    geometry: list of [lon, lat] coordinates
    Returns: (lon, lat, heading_degrees)
    """
    if not geometry or len(geometry) < 2:
        if geometry:
            return geometry[0][0], geometry[0][1], 0.0
        return 0.0, 0.0, 0.0

    progress = max(0.0, min(1.0, progress))

    # Calculate cumulative distances
    distances = [0.0]
    for i in range(1, len(geometry)):
        lon1, lat1 = geometry[i - 1]
        lon2, lat2 = geometry[i]
        d = math.sqrt((lon2 - lon1) ** 2 + (lat2 - lat1) ** 2)
        distances.append(distances[-1] + d)

    total_dist = distances[-1]
    if total_dist == 0:
        return geometry[0][0], geometry[0][1], 0.0

    target_dist = progress * total_dist

    # Find the segment containing the target distance
    for i in range(1, len(distances)):
        if distances[i] >= target_dist:
            seg_start = distances[i - 1]
            seg_end = distances[i]
            seg_len = seg_end - seg_start
            if seg_len == 0:
                t = 0.0
            else:
                t = (target_dist - seg_start) / seg_len

            lon1, lat1 = geometry[i - 1]
            lon2, lat2 = geometry[i]
            lon = lon1 + (lon2 - lon1) * t
            lat = lat1 + (lat2 - lat1) * t

            # Calculate heading
            heading = math.degrees(math.atan2(lon2 - lon1, lat2 - lat1)) % 360

            return lon, lat, heading

    # Fallback to last point
    return geometry[-1][0], geometry[-1][1], 0.0


class Command(BaseCommand):
    help = 'Runs a realistic bus telemetry simulator for the Bhubaneswar Mo Bus network.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=42, help='Random seed for determinism')
        parser.add_argument('--ticks', type=int, default=1000, help='Number of simulation ticks')
        parser.add_argument('--delay', type=float, default=1.0, help='Seconds between ticks')

    def handle(self, *args, **options):
        from django.conf import settings
        if getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION') == 'LIVE':
            self.stdout.write(self.style.ERROR(
                "FATAL: Telemetry simulator cannot be run in LIVE mode. "
                "Exiting to preserve data integrity."
            ))
            return

        ticks = options['ticks']
        delay = options['delay']
        rng = random.Random(options['seed'])

        self.stdout.write(self.style.WARNING("="*60))
        self.stdout.write(self.style.WARNING("  BHUBANESWAR MO BUS TELEMETRY SIMULATOR"))
        self.stdout.write(self.style.WARNING("="*60))

        vehicles = list(Vehicle.objects.select_related('route').all())

        # Initialize simulation state for each vehicle
        sim_state = {}
        for v in vehicles:
            edges = list(
                RouteEdge.objects.filter(route=v.route)
                .select_related('edge', 'edge__source', 'edge__target')
                .order_by('sequence_order')
            )
            if not edges:
                continue

            # Stagger initial positions: each vehicle starts at a different point in the route
            num_edges = len(edges)
            vehicle_index = int(v.identifier.split('-')[-1]) if '-' in v.identifier else 0
            start_edge = (vehicle_index * num_edges // max(1, self._count_vehicles_on_route(v.route, vehicles))) % num_edges

            sim_state[v.identifier] = {
                "edges": edges,
                "current_edge_idx": start_edge,
                "progress": rng.uniform(0.0, 0.5),  # Random initial progress
                "occupancy": rng.randint(5, 25),
                "direction": 1,  # 1 = forward, -1 = reverse
                "dwell_remaining": 0.0,  # Seconds of dwell time remaining at stop
                "is_at_stop": False,
                "trips_completed": 0,
                "max_capacity": v.capacity,
            }

        self.stdout.write(f"Simulating {len(sim_state)} vehicles for {ticks} ticks (delay={delay}s)...")
        self.stdout.write("")

        for tick in range(ticks):
            try:
                active_count = 0
                for v_id, state in sim_state.items():
                    edges = state['edges']
                    idx = state['current_edge_idx']
                    edge = edges[idx].edge

                    # ── Handle dwell at stop ─────────────────
                    if state['dwell_remaining'] > 0:
                        state['dwell_remaining'] -= delay
                        # Passengers board/alight during dwell
                        if state['is_at_stop']:
                            boarding = rng.randint(0, 8)
                            alighting = rng.randint(0, min(5, state['occupancy']))
                            state['occupancy'] = max(0, min(
                                state['max_capacity'],
                                state['occupancy'] + boarding - alighting
                            ))
                        
                        # Emit position at stop (stationary)
                        source = edge.source if state['direction'] == 1 else edge.target
                        payload = self._build_payload(
                            v_id, source.lat, source.lon, 0.0,
                            state['occupancy'], 'AT_STOP'
                        )
                        process_vehicle_telemetry(payload)
                        active_count += 1
                        continue

                    state['is_at_stop'] = False

                    # ── Calculate movement speed ─────────────
                    # Check if edge has real traffic data
                    is_stale = False
                    if edge.data_source == 'TOMTOM' and edge.last_updated_at:
                        age = timezone.now() - edge.last_updated_at
                        if age > timedelta(minutes=15):
                            is_stale = True

                    if edge.data_source == 'ESTIMATED' or is_stale:
                        speed_ms = max(0.5, edge.free_flow_speed if edge.free_flow_speed else 6.94)
                    else:
                        speed_ms = max(0.5, edge.current_traffic_speed)

                    # Add some natural variation (+/- 15%)
                    speed_ms *= rng.uniform(0.85, 1.15)
                    speed_kmh = speed_ms * 3.6

                    # ── Move vehicle along edge ──────────────
                    distance_m = max(10.0, edge.distance)
                    progress_step = (speed_ms * delay) / distance_m
                    state['progress'] += progress_step

                    # ── Check if reached end of edge ─────────
                    if state['progress'] >= 1.0:
                        state['progress'] = 0.0

                        # Move to next edge
                        next_idx = state['current_edge_idx'] + state['direction']

                        if next_idx >= len(edges):
                            # Reached terminus — reverse direction
                            state['direction'] = -1
                            next_idx = len(edges) - 1
                            state['trips_completed'] += 1
                            # Longer dwell at terminus (30-60s)
                            state['dwell_remaining'] = rng.uniform(30.0, 60.0)
                            state['is_at_stop'] = True
                            # Many passengers alight at terminus
                            state['occupancy'] = max(0, state['occupancy'] - rng.randint(10, 25))
                        elif next_idx < 0:
                            # Reached other terminus — reverse again
                            state['direction'] = 1
                            next_idx = 0
                            state['trips_completed'] += 1
                            state['dwell_remaining'] = rng.uniform(30.0, 60.0)
                            state['is_at_stop'] = True
                            state['occupancy'] = max(0, state['occupancy'] - rng.randint(10, 25))
                        else:
                            # Normal stop — dwell 15-30s
                            state['dwell_remaining'] = rng.uniform(15.0, 30.0)
                            state['is_at_stop'] = True

                        state['current_edge_idx'] = next_idx
                        edge = edges[state['current_edge_idx']].edge

                    # ── Interpolate position along geometry ───
                    geom = edge.geometry
                    if state['direction'] == -1:
                        geom = geom[::-1]  # Reverse geometry for return trip

                    lon, lat, heading = interpolate_along_geometry(geom, state['progress'])

                    # ── Build and send telemetry ─────────────
                    status = 'ACTIVE'
                    if speed_kmh < 2.0 and not state['is_at_stop']:
                        status = 'DELAYED'

                    payload = self._build_payload(
                        v_id, lat, lon, speed_kmh,
                        state['occupancy'], status
                    )
                    payload['heading'] = round(heading, 1)
                    payload['route_name'] = edges[0].edge.source.name  # Approximate

                    process_vehicle_telemetry(payload)
                    active_count += 1

                if (tick + 1) % 10 == 0 or tick == 0:
                    self.stdout.write(
                        f"  Tick {tick + 1:>4}/{ticks} | "
                        f"Active: {active_count} vehicles"
                    )

            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f"  Simulator caught exception: {e}. Re-initializing state..."
                ))
                # Re-initialize
                vehicles = list(Vehicle.objects.select_related('route').all())
                sim_state = {}
                for v in vehicles:
                    edges = list(
                        RouteEdge.objects.filter(route=v.route)
                        .select_related('edge', 'edge__source', 'edge__target')
                        .order_by('sequence_order')
                    )
                    if not edges:
                        continue
                    sim_state[v.identifier] = {
                        "edges": edges,
                        "current_edge_idx": 0,
                        "progress": 0.0,
                        "occupancy": 10,
                        "direction": 1,
                        "dwell_remaining": 0.0,
                        "is_at_stop": False,
                        "trips_completed": 0,
                        "max_capacity": v.capacity,
                    }

            time.sleep(delay)

        self.stdout.write(self.style.SUCCESS("\n  Simulation complete."))

    def _build_payload(self, vehicle_id, lat, lon, speed_kmh, occupancy, status):
        """Build a standardized telemetry payload."""
        sim_v_id = vehicle_id if vehicle_id.startswith("SIM-") else f"SIM-{vehicle_id}"
        return {
            "vehicle_id": sim_v_id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "speed_kmh": round(speed_kmh, 1),
            "occupancy": occupancy,
            "timestamp": timezone.now().isoformat(),
            "status": status,
            "data_source": "SIMULATION",
            "provider": "CRUT_SIM",
        }

    def _count_vehicles_on_route(self, route, all_vehicles):
        """Count how many vehicles are assigned to a specific route."""
        return sum(1 for v in all_vehicles if v.route_id == route.id)
