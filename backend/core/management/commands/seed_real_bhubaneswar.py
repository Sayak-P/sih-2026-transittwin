import math
import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Stop, Edge, Route, RouteEdge, Vehicle, Disruption
from prediction.models import ODDemand
from integrations.osm.overpass_bus_routes import (
    fetch_osm_bus_routes, fetch_road_geometry_between_stops, FALLBACK_ROUTES
)

logger = logging.getLogger(__name__)


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lon points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_geometry_distance(geometry):
    """Calculate total distance along a geometry (list of [lon, lat])."""
    total = 0.0
    for i in range(len(geometry) - 1):
        lon1, lat1 = geometry[i]
        lon2, lat2 = geometry[i + 1]
        total += haversine(lat1, lon1, lat2, lon2)
    return total


class Command(BaseCommand):
    help = 'Seeds real Bhubaneswar Mo Bus network with actual routes, stops, and road geometry.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-osrm', action='store_true',
            help='Skip OSRM road geometry lookup (use straight lines between stops)'
        )
        parser.add_argument(
            '--fallback-only', action='store_true',
            help='Skip OSM query and use hardcoded route data directly'
        )

    def handle(self, *args, **options):
        skip_osrm = options.get('skip_osrm', False)
        fallback_only = options.get('fallback_only', False)

        self.stdout.write(self.style.WARNING("="*60))
        self.stdout.write(self.style.WARNING("  SEEDING REAL BHUBANESWAR MO BUS NETWORK"))
        self.stdout.write(self.style.WARNING("="*60))

        # ── Step 1: Clear existing data ──────────────────────────
        self.stdout.write("Clearing existing network data...")
        ODDemand.objects.all().delete()
        Disruption.objects.all().delete()
        Vehicle.objects.all().delete()
        RouteEdge.objects.all().delete()
        Route.objects.all().delete()
        Edge.objects.all().delete()
        Stop.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("[OK] Cleared all existing data."))

        # ── Step 2: Fetch route data ─────────────────────────────
        if fallback_only:
            routes_data = FALLBACK_ROUTES
            source = 'FALLBACK'
            self.stdout.write("Using hardcoded fallback routes (--fallback-only).")
        else:
            routes_data, source = fetch_osm_bus_routes()
            if source == 'FALLBACK':
                self.stdout.write(self.style.WARNING("OSM data insufficient. Using fallback routes."))
            else:
                self.stdout.write(f"Fetched {len(routes_data)} route relations from OSM.")
                # Parse OSM data into the same format as fallback
                routes_data = self._parse_osm_routes(routes_data)

        self.stdout.write(f"Processing {len(routes_data)} routes from {source}...")

        # ── Step 3: De-duplicate stops ───────────────────────────
        # Many routes share stops (e.g., "Master Canteen Square" appears on 10+ routes)
        # We de-duplicate by name to avoid creating duplicate Stop records
        stop_registry = {}  # name -> Stop instance
        all_stops_data = []
        for route_data in routes_data:
            for s in route_data['stops']:
                key = s['name']
                if key not in stop_registry:
                    all_stops_data.append(s)
                    stop_registry[key] = None  # placeholder

        self.stdout.write(f"Creating {len(all_stops_data)} unique stops...")

        for i, s_data in enumerate(all_stops_data):
            # Determine accessibility (major stops are accessible)
            is_accessible = not any(kw in s_data['name'].lower() for kw in ['temple', 'old town'])
            
            stop = Stop.objects.create(
                name=s_data['name'],
                lat=s_data['lat'],
                lon=s_data['lon'],
                is_accessible=is_accessible,
                capacity=150 + (i * 5),  # Vary capacity
                is_active=True,
                metadata={
                    'source': source,
                    'city': 'Bhubaneswar',
                }
            )
            stop_registry[s_data['name']] = stop

        self.stdout.write(self.style.SUCCESS(f"[OK] Created {len(all_stops_data)} stops."))

        # ── Step 4: Create routes with edges ─────────────────────
        total_edges = 0
        total_vehicles = 0

        for idx, route_data in enumerate(routes_data):
            route_name = route_data['name']
            ref = route_data.get('ref', str(idx + 1))
            self.stdout.write(f"\n  Processing {route_name}...")

            # Create Route
            route = Route.objects.create(
                name=route_name,
                transport_type=route_data.get('transport_type', 'BUS'),
            )

            # Get road geometry between stops
            stops_list = route_data['stops']
            
            if not skip_osrm and len(stops_list) >= 2:
                self.stdout.write(f"    Fetching road geometry from OSRM...")
                full_geometry = fetch_road_geometry_between_stops(stops_list)
                time.sleep(1)  # Rate-limit OSRM requests
            else:
                full_geometry = [[s['lon'], s['lat']] for s in stops_list]

            # Create edges between consecutive stops
            seq_order = 1
            for j in range(len(stops_list) - 1):
                source_stop = stop_registry[stops_list[j]['name']]
                target_stop = stop_registry[stops_list[j + 1]['name']]

                # Extract geometry segment for this edge
                edge_geom = self._extract_edge_geometry(
                    full_geometry, stops_list[j], stops_list[j + 1]
                )
                
                distance = calculate_geometry_distance(edge_geom)
                if distance < 1.0:
                    distance = haversine(
                        source_stop.lat, source_stop.lon,
                        target_stop.lat, target_stop.lon
                    )

                # Estimate travel time (assume avg 25 km/h in city)
                avg_speed_ms = 25 / 3.6  # ~6.94 m/s
                travel_time = distance / avg_speed_ms

                # Create forward edge (or reuse existing one between shared stops)
                edge_fwd, created = Edge.objects.get_or_create(
                    source=source_stop,
                    target=target_stop,
                    defaults={
                        'geometry': edge_geom,
                        'distance': round(distance, 1),
                        'baseline_travel_time': round(travel_time, 1),
                        'baseline_cost': round(travel_time, 1),
                        'current_traffic_speed': avg_speed_ms,
                        'free_flow_speed': avg_speed_ms * 1.2,
                        'data_source': 'ESTIMATED',
                        'is_accessible': source_stop.is_accessible and target_stop.is_accessible,
                        'metadata': {
                            'route_ref': ref,
                            'osm_source': source,
                        }
                    }
                )
                if created:
                    total_edges += 1

                RouteEdge.objects.create(
                    route=route, edge=edge_fwd, sequence_order=seq_order
                )
                seq_order += 1

                # Create reverse edge for return trip
                reversed_geom = edge_geom[::-1]
                _, rev_created = Edge.objects.get_or_create(
                    source=target_stop,
                    target=source_stop,
                    defaults={
                        'geometry': reversed_geom,
                        'distance': round(distance, 1),
                        'baseline_travel_time': round(travel_time, 1),
                        'baseline_cost': round(travel_time, 1),
                        'current_traffic_speed': avg_speed_ms,
                        'free_flow_speed': avg_speed_ms * 1.2,
                        'data_source': 'ESTIMATED',
                        'is_accessible': source_stop.is_accessible and target_stop.is_accessible,
                        'metadata': {
                            'route_ref': ref,
                            'osm_source': source,
                        }
                    }
                )
                if rev_created:
                    total_edges += 1

            # Create vehicles for this route
            num_vehicles = route_data.get('num_vehicles', 3)
            for v_idx in range(1, num_vehicles + 1):
                start_stop = stop_registry[stops_list[0]['name']]
                vehicle = Vehicle.objects.create(
                    identifier=f"BUS-R{ref}-{v_idx:02d}",
                    vehicle_type="Mo Bus",
                    route=route,
                    lat=start_stop.lat,
                    lon=start_stop.lon,
                    occupancy=0,
                    capacity=60,
                    accessible_capacity=2,
                    state='ACTIVE',
                    energy_rate_kwh_per_km=1.2,
                )
                total_vehicles += 1

            self.stdout.write(self.style.SUCCESS(
                f"    [OK] {route_name}: {seq_order - 1} edges, {num_vehicles} vehicles"
            ))

        # ── Step 5: Create OD Demand samples ─────────────────────
        self.stdout.write("\nCreating OD Demand samples...")
        now = timezone.now()
        
        # High-demand OD pairs (based on common commuter patterns)
        demand_pairs = [
            ("Bhubaneswar Railway Station", "Patia Square", 80, "NORMAL"),
            ("Baramunda ISBT", "Rajmahal Square", 65, "NORMAL"),
            ("Bhubaneswar Railway Station", "Nandankanan Zoo", 45, "NORMAL"),
            ("AIIMS Bhubaneswar", "Master Canteen Square", 30, "NORMAL"),
            ("Bhubaneswar Railway Station", "KIIT University", 55, "NORMAL"),
            ("Baramunda ISBT", "Lingaraj Temple", 40, "NORMAL"),
            ("Bhubaneswar Railway Station", "Puri Bus Stand", 35, "NORMAL"),
            ("Bhubaneswar Railway Station", "SUM Hospital", 3, "WHEELCHAIR"),
            ("Baramunda ISBT", "Capital Hospital", 2, "WHEELCHAIR"),
            ("Khandagiri Square", "AIIMS Bhubaneswar", 4, "WHEELCHAIR"),
        ]

        for origin_name, dest_name, count, group in demand_pairs:
            origin = stop_registry.get(origin_name)
            dest = stop_registry.get(dest_name)
            if origin and dest:
                ODDemand.objects.create(
                    origin_stop=origin,
                    destination_stop=dest,
                    time_window_start=now,
                    time_window_end=now + timedelta(hours=1),
                    expected_passenger_count=count,
                    passenger_group=group,
                )

        # ── Summary ──────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("="*60))
        self.stdout.write(self.style.SUCCESS("  SEEDING COMPLETE"))
        self.stdout.write(self.style.SUCCESS("="*60))
        self.stdout.write(f"  Stops:    {Stop.objects.count()}")
        self.stdout.write(f"  Edges:    {Edge.objects.count()}")
        self.stdout.write(f"  Routes:   {Route.objects.count()}")
        self.stdout.write(f"  Vehicles: {Vehicle.objects.count()}")
        self.stdout.write(f"  Demands:  {ODDemand.objects.count()}")
        self.stdout.write(f"  Source:   {source}")
        self.stdout.write(self.style.SUCCESS("="*60))

    def _parse_osm_routes(self, osm_data):
        """Parse raw OSM relation data into the standardized route format."""
        elements = osm_data.get('elements', [])
        nodes_dict = {}
        relations = []

        for el in elements:
            if el['type'] == 'node':
                nodes_dict[el['id']] = el
            elif el['type'] == 'relation':
                relations.append(el)

        parsed_routes = []
        for rel in relations:
            tags = rel.get('tags', {})
            name = tags.get('name', tags.get('ref', 'Unknown Route'))
            ref = tags.get('ref', '')

            # Extract stop members
            stops = []
            for member in rel.get('members', []):
                if member['type'] == 'node' and member.get('role', '') in ('stop', 'platform', ''):
                    node = nodes_dict.get(member['ref'])
                    if node:
                        node_tags = node.get('tags', {})
                        stop_name = node_tags.get('name', f"Stop at {node['lat']:.4f},{node['lon']:.4f}")
                        stops.append({
                            'name': stop_name,
                            'lat': node['lat'],
                            'lon': node['lon'],
                        })

            if len(stops) >= 2:
                parsed_routes.append({
                    'name': f"Mo Bus {name}",
                    'ref': ref or str(len(parsed_routes) + 1),
                    'transport_type': 'BUS',
                    'stops': stops,
                    'num_vehicles': max(3, len(stops) // 3),
                })

        # If we parsed fewer than 5 routes from OSM, supplement with fallback
        if len(parsed_routes) < 5:
            logger.warning(f"Only parsed {len(parsed_routes)} routes from OSM. Supplementing with fallback data.")
            existing_refs = {r['ref'] for r in parsed_routes}
            for fb_route in FALLBACK_ROUTES:
                if fb_route['ref'] not in existing_refs:
                    parsed_routes.append(fb_route)

        return parsed_routes

    def _extract_edge_geometry(self, full_geometry, source_stop, target_stop):
        """
        Extract the portion of full_geometry between two stops.
        Finds the closest points in the geometry to each stop.
        """
        if len(full_geometry) < 2:
            return [
                [source_stop['lon'], source_stop['lat']],
                [target_stop['lon'], target_stop['lat']]
            ]

        def closest_index(geom, lat, lon):
            min_dist = float('inf')
            min_idx = 0
            for i, coord in enumerate(geom):
                d = (coord[0] - lon) ** 2 + (coord[1] - lat) ** 2
                if d < min_dist:
                    min_dist = d
                    min_idx = i
            return min_idx

        src_idx = closest_index(full_geometry, source_stop['lat'], source_stop['lon'])
        tgt_idx = closest_index(full_geometry, target_stop['lat'], target_stop['lon'])

        if src_idx == tgt_idx:
            return [
                [source_stop['lon'], source_stop['lat']],
                [target_stop['lon'], target_stop['lat']]
            ]

        start = min(src_idx, tgt_idx)
        end = max(src_idx, tgt_idx) + 1
        segment = full_geometry[start:end]

        # Ensure segment goes in the right direction
        if src_idx > tgt_idx:
            segment = segment[::-1]

        # Ensure we have at least 2 points
        if len(segment) < 2:
            segment = [
                [source_stop['lon'], source_stop['lat']],
                [target_stop['lon'], target_stop['lat']]
            ]

        return segment
