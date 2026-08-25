import math
from rest_framework.views import APIView
from rest_framework.response import Response
from core.models import Vehicle, Stop, Edge, Route, RouteEdge
from simulation.state.live_state import LiveStateEngine


def haversine(lat1, lon1, lat2, lon2):
    """Distance between two lat/lon points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class BusAvailabilityView(APIView):
    """
    Returns bus availability and estimated arrival times for a specific stop
    or for all stops within a geographic radius.

    Query Parameters:
      - stop_id (int): ID of the stop to check.
      - area_lat (float), area_lon (float), radius_km (float):
        Find all stops within radius and return availability for each.
    """

    def get(self, request):
        stop_id = request.query_params.get('stop_id')
        area_lat = request.query_params.get('area_lat')
        area_lon = request.query_params.get('area_lon')
        radius_km = request.query_params.get('radius_km', '2.0')

        if stop_id:
            # Single stop mode
            try:
                stop = Stop.objects.get(id=int(stop_id))
            except (Stop.DoesNotExist, ValueError):
                return Response({"error": "Stop not found"}, status=404)

            result = self._get_availability_for_stop(stop)
            return Response(result)

        elif area_lat and area_lon:
            # Area mode — find nearby stops
            try:
                lat = float(area_lat)
                lon = float(area_lon)
                radius = float(radius_km)
            except ValueError:
                return Response({"error": "Invalid lat/lon/radius values"}, status=400)

            all_stops = Stop.objects.filter(is_active=True)
            nearby_stops = []
            for s in all_stops:
                dist_m = haversine(lat, lon, s.lat, s.lon)
                if dist_m <= radius * 1000:
                    nearby_stops.append((s, dist_m))

            nearby_stops.sort(key=lambda x: x[1])
            nearby_stops = nearby_stops[:15]  # Cap at 15 stops

            stops_availability = []
            for stop_obj, dist_m in nearby_stops:
                avail = self._get_availability_for_stop(stop_obj)
                avail['distance_from_search_m'] = round(dist_m, 1)
                stops_availability.append(avail)

            return Response({
                "search_center": {"lat": lat, "lon": lon},
                "radius_km": radius,
                "stops_found": len(stops_availability),
                "stops": stops_availability
            })

        else:
            return Response(
                {"error": "Provide either 'stop_id' or 'area_lat' & 'area_lon' query params"},
                status=400
            )

    def _get_availability_for_stop(self, stop):
        """
        For a given stop, find all routes passing through it,
        then for each route find vehicles and compute ETAs.
        """
        # Pre-fetch all route edges with related data
        all_route_edges = list(
            RouteEdge.objects.select_related(
                'route', 'edge', 'edge__source', 'edge__target'
            ).order_by('route_id', 'sequence_order')
        )

        # Build route -> ordered stops mapping
        route_stops_map = {}  # route_id -> [Stop, Stop, ...]
        route_edges_map = {}  # route_id -> [RouteEdge, ...]
        route_obj_map = {}    # route_id -> Route

        for re in all_route_edges:
            rid = re.route_id
            if rid not in route_edges_map:
                route_edges_map[rid] = []
                route_stops_map[rid] = []
                route_obj_map[rid] = re.route
            route_edges_map[rid].append(re)

        # Build ordered stop lists for each route
        for rid, edges_list in route_edges_map.items():
            ordered_stops = []
            for re_item in edges_list:
                if not ordered_stops or ordered_stops[-1].id != re_item.edge.source.id:
                    ordered_stops.append(re_item.edge.source)
                if not ordered_stops or ordered_stops[-1].id != re_item.edge.target.id:
                    ordered_stops.append(re_item.edge.target)
            route_stops_map[rid] = ordered_stops

        # Find routes that pass through this stop
        routes_serving = []
        for rid, ordered_stops in route_stops_map.items():
            stop_indices = [i for i, s in enumerate(ordered_stops) if s.id == stop.id]
            if stop_indices:
                routes_serving.append({
                    'route': route_obj_map[rid],
                    'stop_index': stop_indices[0],
                    'ordered_stops': ordered_stops,
                    'edges': route_edges_map[rid],
                })

        if not routes_serving:
            return {
                "stop": {
                    "id": stop.id,
                    "name": stop.name,
                    "lat": stop.lat,
                    "lon": stop.lon,
                },
                "routes_serving": [],
                "total_buses_approaching": 0,
                "next_bus_eta_minutes": None,
            }

        # Get live vehicle state
        live_state = LiveStateEngine.get_current_state()
        live_vehicles = live_state.get("vehicles", {})

        # Get all vehicles from DB
        vehicles_db = list(Vehicle.objects.select_related('route').all())

        # Build edge lookup for travel time computation
        all_edges = list(Edge.objects.select_related('source', 'target').all())
        edge_lookup = {}  # (source_id, target_id) -> Edge
        for e in all_edges:
            edge_lookup[(e.source_id, e.target_id)] = e

        # Process each route
        route_results = []
        all_approaching_buses = []

        for route_info in routes_serving:
            route = route_info['route']
            target_stop_index = route_info['stop_index']
            ordered_stops = route_info['ordered_stops']

            # Find vehicles on this route
            route_vehicles = [v for v in vehicles_db if v.route_id == route.id]

            buses_for_route = []
            for vehicle in route_vehicles:
                v_id = vehicle.identifier
                sim_v_id = f"SIM-{v_id}" if not v_id.startswith("SIM-") else v_id
                live_info = live_vehicles.get(sim_v_id) or live_vehicles.get(v_id) or {}

                cur_lat = live_info.get("lat") or vehicle.lat
                cur_lon = live_info.get("lon") or vehicle.lon
                occupancy = live_info.get("occupancy", vehicle.occupancy)
                speed_kmh = live_info.get("speed_kmh", 25.0)
                status = live_info.get("status", vehicle.state)

                if not cur_lat or not cur_lon:
                    continue

                # Find which stop the vehicle is closest to on this route
                min_dist = float('inf')
                vehicle_stop_index = 0
                for idx, s in enumerate(ordered_stops):
                    d = haversine(cur_lat, cur_lon, s.lat, s.lon)
                    if d < min_dist:
                        min_dist = d
                        vehicle_stop_index = idx

                # Only include buses that are BEFORE the queried stop
                # (i.e., approaching it, not past it)
                if vehicle_stop_index >= target_stop_index:
                    continue

                # Compute ETA by summing edge travel times from current position to target stop
                eta_seconds = 0.0
                total_distance_m = 0.0
                intermediate_stops = []

                for seg_idx in range(vehicle_stop_index, target_stop_index):
                    src_stop = ordered_stops[seg_idx]
                    tgt_stop = ordered_stops[seg_idx + 1]

                    edge = edge_lookup.get((src_stop.id, tgt_stop.id))
                    if edge:
                        traffic_speed = max(0.5, edge.current_traffic_speed if edge.current_traffic_speed > 0 else 6.94)
                        seg_time = edge.distance / traffic_speed
                        # Add 30 seconds dwell time per intermediate stop
                        seg_time += 30.0
                        eta_seconds += seg_time
                        total_distance_m += edge.distance
                    else:
                        # Fallback: estimate based on straight-line distance at current speed
                        d = haversine(src_stop.lat, src_stop.lon, tgt_stop.lat, tgt_stop.lon)
                        est_speed = max(5.0, speed_kmh / 3.6)
                        eta_seconds += (d / est_speed) + 30.0
                        total_distance_m += d

                    if seg_idx > vehicle_stop_index:
                        intermediate_stops.append(src_stop.name)

                # Add the first leg partial: distance from vehicle to the nearest stop
                first_stop = ordered_stops[vehicle_stop_index]
                partial_dist = haversine(cur_lat, cur_lon, first_stop.lat, first_stop.lon)
                partial_speed = max(5.0, speed_kmh / 3.6)
                eta_seconds += partial_dist / partial_speed
                total_distance_m += partial_dist

                eta_minutes = round(eta_seconds / 60.0, 1)
                stops_away = target_stop_index - vehicle_stop_index

                bus_info = {
                    "identifier": vehicle.identifier,
                    "status": status,
                    "occupancy": occupancy,
                    "capacity": vehicle.capacity,
                    "speed_kmh": round(speed_kmh, 1),
                    "lat": cur_lat,
                    "lon": cur_lon,
                    "current_stop": ordered_stops[vehicle_stop_index].name,
                    "eta_minutes": eta_minutes,
                    "distance_remaining_km": round(total_distance_m / 1000.0, 2),
                    "stops_away": stops_away,
                    "intermediate_stops": intermediate_stops,
                }
                buses_for_route.append(bus_info)
                all_approaching_buses.append(bus_info)

            # Sort buses by ETA (soonest first)
            buses_for_route.sort(key=lambda b: b['eta_minutes'])

            route_results.append({
                "route_id": route.id,
                "route_name": route.name,
                "total_stops": len(ordered_stops),
                "buses": buses_for_route,
            })

        # Sort all approaching buses for global next_bus
        all_approaching_buses.sort(key=lambda b: b['eta_minutes'])

        return {
            "stop": {
                "id": stop.id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
            },
            "routes_serving": route_results,
            "total_buses_approaching": len(all_approaching_buses),
            "next_bus_eta_minutes": all_approaching_buses[0]['eta_minutes'] if all_approaching_buses else None,
            "next_bus": all_approaching_buses[0] if all_approaching_buses else None,
        }
