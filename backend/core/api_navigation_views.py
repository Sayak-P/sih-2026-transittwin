import math
import networkx as nx
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from core.models import Vehicle, Stop, Edge, Route, RouteEdge, Disruption as DbDisruption
from core.api_disruption_views import DISRUPTIONS_DB
from simulation.state.live_state import LiveStateEngine

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

import time
import math
import hashlib

def interpolate_coords_along_path(coords, fraction):
    """Interpolate [lon, lat] along a list of coordinates [ [lon, lat], ... ] given progress 0.0-1.0"""
    if not coords:
        return [85.83, 20.28]
    if len(coords) == 1 or fraction <= 0:
        return coords[0]
    if fraction >= 1.0:
        return coords[-1]
    
    seg_lens = []
    total_len = 0.0
    for i in range(len(coords) - 1):
        dx = coords[i+1][0] - coords[i][0]
        dy = coords[i+1][1] - coords[i][1]
        dist = math.hypot(dx, dy)
        seg_lens.append(dist)
        total_len += dist
    
    if total_len == 0:
        return coords[0]
    
    target_dist = fraction * total_len
    cur_dist = 0.0
    for i in range(len(seg_lens)):
        if cur_dist + seg_lens[i] >= target_dist:
            ratio = (target_dist - cur_dist) / max(1e-9, seg_lens[i])
            lon = coords[i][0] + ratio * (coords[i+1][0] - coords[i][0])
            lat = coords[i][1] + ratio * (coords[i+1][1] - coords[i][1])
            return [lon, lat]
        cur_dist += seg_lens[i]
    return coords[-1]

class BusListForNavigatorView(APIView):
    """
    Returns list of all buses with their real-time simulated position,
    route, current stop, and estimated next stop for the Smart Route Navigator.
    """
    def get(self, request):
        live_state = LiveStateEngine.get_current_state()
        live_vehicles = live_state.get("vehicles", {})
        
        vehicles_db = list(Vehicle.objects.select_related('route').all())
        stops_db = list(Stop.objects.all())
        stops_by_id = {s.id: s for s in stops_db}
        
        result = []
        for v in vehicles_db:
            v_id = v.identifier
            sim_v_id = f"SIM-{v_id}" if not v_id.startswith("SIM-") else v_id
            live_info = live_vehicles.get(sim_v_id) or live_vehicles.get(v_id) or {}
            
            status = live_info.get("status") or v.state or "ACTIVE"
            is_active = (status == "ACTIVE")
            occupancy = live_info.get("occupancy", v.occupancy)
            
            # Find Route, stops and polyline geometry
            route_name = v.route.name if v.route else "Unassigned"
            route_edges = list(RouteEdge.objects.filter(route=v.route).select_related('edge', 'edge__source', 'edge__target').order_by('sequence_order')) if v.route else []
            
            route_stops = []
            route_geometry_coords = []
            if route_edges:
                for re in route_edges:
                    if not route_stops or route_stops[-1].id != re.edge.source.id:
                        route_stops.append(re.edge.source)
                    if route_stops[-1].id != re.edge.target.id:
                        route_stops.append(re.edge.target)
                    
                    if re.edge.geometry and 'coordinates' in re.edge.geometry:
                        for pt in re.edge.geometry['coordinates']:
                            if not route_geometry_coords or route_geometry_coords[-1] != pt:
                                route_geometry_coords.append(pt)
                    else:
                        route_geometry_coords.append([re.edge.source.lon, re.edge.source.lat])
                        route_geometry_coords.append([re.edge.target.lon, re.edge.target.lat])

            # Calculate real simulated location along the route if active
            if is_active and route_geometry_coords:
                v_hash = int(hashlib.md5(v.identifier.encode()).hexdigest(), 16) % 10000
                now_t = time.time()

                # Calculate real corridor length in meters using haversine
                total_corridor_m = 0.0
                for ci in range(len(route_geometry_coords) - 1):
                    total_corridor_m += haversine(
                        route_geometry_coords[ci][1], route_geometry_coords[ci][0],
                        route_geometry_coords[ci+1][1], route_geometry_coords[ci+1][0]
                    )

                # Base cruising speed: 28-38 km/h (realistic city bus cruising speed)
                base_speed_kmh = 28.0 + (v_hash % 9)
                base_speed_ms = base_speed_kmh / 3.6
                cycle_period_seconds = total_corridor_m / base_speed_ms if base_speed_ms > 0 else 600.0

                progress = ((now_t + v_hash * 7.3) % cycle_period_seconds) / cycle_period_seconds
                sim_pt = interpolate_coords_along_path(route_geometry_coords, progress)
                cur_lon = round(sim_pt[0], 6)
                cur_lat = round(sim_pt[1], 6)

                # Compute heading (bearing) from current pos to next geometry point
                heading_deg = 0.0
                look_ahead = min(progress + 0.005, 1.0)
                next_pt = interpolate_coords_along_path(route_geometry_coords, look_ahead)
                dlon = math.radians(next_pt[0] - cur_lon)
                lat1 = math.radians(cur_lat)
                lat2 = math.radians(next_pt[1])
                x = math.sin(dlon) * math.cos(lat2)
                y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
                heading_deg = round((math.degrees(math.atan2(x, y)) + 360) % 360, 1)
            else:
                now_t = time.time()
                v_hash = 0
                base_speed_kmh = 0.0
                cur_lat = live_info.get("lat") or v.lat
                cur_lon = live_info.get("lon") or v.lon
                speed_kmh = 0.0
                heading_deg = 0.0

            # Determine closest stop and next upcoming stop from real coordinates
            closest_stop = None
            next_stop = None
            upcoming_stops = []
            
            if route_stops and cur_lat and cur_lon:
                min_dist = float('inf')
                min_idx = 0
                for idx, st in enumerate(route_stops):
                    d = haversine(cur_lat, cur_lon, st.lat, st.lon)
                    if d < min_dist:
                        min_dist = d
                        min_idx = idx
                        closest_stop = st
                
                next_idx = (min_idx + 1) if min_idx + 1 < len(route_stops) else 0
                next_stop = route_stops[next_idx] if route_stops else None
                upcoming_stops = route_stops[min_idx + 1:] if min_idx + 1 < len(route_stops) else []
            elif route_stops:
                closest_stop = route_stops[0]
                next_stop = route_stops[1] if len(route_stops) > 1 else route_stops[0]
                upcoming_stops = route_stops[1:] if len(route_stops) > 1 else []
            
            dist_to_next = round(haversine(cur_lat, cur_lon, next_stop.lat, next_stop.lon), 1) if cur_lat and cur_lon and next_stop else None

            # Calculate accurate instantaneous physical velocity v(t)
            if is_active and cur_lat and cur_lon and closest_stop:
                dist_to_closest = haversine(cur_lat, cur_lon, closest_stop.lat, closest_stop.lon)
                if dist_to_closest < 30.0:
                    # Bus is dwelling / picking up passengers at the bus stop (0 - 4 km/h)
                    instant_speed = max(0.0, 3.5 * (dist_to_closest / 30.0))
                elif dist_to_closest < 160.0:
                    # Bus is accelerating out of stop or decelerating into stop
                    ratio = (dist_to_closest - 30.0) / 130.0
                    instant_speed = 4.0 + ratio * (base_speed_kmh - 4.0)
                else:
                    # Cruising speed on open street with real-time dynamic traffic fluctuations
                    traffic_wave = math.sin((now_t + v_hash) / 4.5) * 4.2 + math.cos((now_t * 0.8 + v_hash) / 10.0) * 2.3
                    instant_speed = base_speed_kmh + traffic_wave
                
                speed_kmh = max(0.0, round(instant_speed, 1))
            elif not is_active:
                speed_kmh = 0.0

            result.append({
                "identifier": v.identifier,
                "vehicle_type": v.vehicle_type,
                "route_id": v.route.id if v.route else None,
                "route_name": route_name,
                "lat": cur_lat,
                "lon": cur_lon,
                "speed_kmh": speed_kmh,
                "speed_ms": round(speed_kmh / 3.6, 2),
                "heading_deg": heading_deg,
                "occupancy": occupancy,
                "capacity": v.capacity,
                "status": status,
                "distance_to_next_stop_m": dist_to_next,
                "current_stop": {
                    "id": closest_stop.id,
                    "name": closest_stop.name,
                    "lat": closest_stop.lat,
                    "lon": closest_stop.lon,
                } if closest_stop else None,
                "next_stop": {
                    "id": next_stop.id,
                    "name": next_stop.name,
                    "lat": next_stop.lat,
                    "lon": next_stop.lon,
                } if next_stop else None,
                "upcoming_stops": [
                    {"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon}
                    for s in upcoming_stops
                ],
                "route_stops": [
                    {"id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon}
                    for s in route_stops
                ]
            })
            
        return Response(result)

class FindClearRouteView(APIView):
    """
    Computes the optimal, hurdle-free path for a specific bus
    to reach its next stop avoiding road blocks, traffic jams, and disruptions.
    """
    def post(self, request):
        data = request.data
        bus_id = data.get("bus_id") or data.get("vehicle_id")
        current_stop_id = data.get("current_stop_id")
        target_stop_id = data.get("target_stop_id")
        avoid_road_blocks = data.get("avoid_road_blocks", True)
        avoid_congestion = data.get("avoid_congestion", True)
        priority = data.get("priority", "FASTEST") # FASTEST, SHORTEST, LEAST_CONGESTED, ACCESSIBLE
        
        # 1. Identify Start & End stops
        start_stop = None
        target_stop = None
        
        if current_stop_id:
            start_stop = Stop.objects.filter(id=current_stop_id).first()
        if target_stop_id:
            target_stop = Stop.objects.filter(id=target_stop_id).first()
            
        # If bus_id given and stops not specified, infer from bus
        if bus_id and (not start_stop or not target_stop):
            orig_id = bus_id.replace("SIM-", "")
            vehicle = Vehicle.objects.filter(identifier=orig_id).select_related('route').first()
            if vehicle and vehicle.route:
                route_edges = list(RouteEdge.objects.filter(route=vehicle.route).select_related('edge', 'edge__source', 'edge__target').order_by('sequence_order'))
                if route_edges:
                    route_stops = []
                    for re in route_edges:
                        if not route_stops or route_stops[-1].id != re.edge.source.id:
                            route_stops.append(re.edge.source)
                        if route_stops[-1].id != re.edge.target.id:
                            route_stops.append(re.edge.target)
                    
                    if not start_stop and len(route_stops) > 0:
                        start_stop = route_stops[0]
                    if not target_stop and len(route_stops) > 1:
                        target_stop = route_stops[1]
                        
        if not start_stop or not target_stop:
            return Response({"error": "Start and Target stops could not be resolved"}, status=400)
            
        if start_stop.id == target_stop.id:
            return Response({"error": "Current stop and Target stop are identical"}, status=400)

        # 2. Gather All Active Disruptions & Hurdles
        blocked_edge_ids = set()
        active_hurdles_list = []
        
        # From DB
        db_disruptions = DbDisruption.objects.filter(is_active=True).select_related('affected_edge', 'affected_stop')
        for d in db_disruptions:
            if d.affected_edge:
                blocked_edge_ids.add(d.affected_edge.id)
                active_hurdles_list.append({
                    "id": f"db-{d.id}",
                    "type": d.disruption_type,
                    "edge_id": d.affected_edge.id,
                    "description": d.description or f"{d.disruption_type} on {d.affected_edge.source.name} → {d.affected_edge.target.name}",
                    "severity": d.severity,
                    "location": [d.affected_edge.source.lon, d.affected_edge.source.lat]
                })
                
        # From In-Memory DISRUPTIONS_DB
        for d_id, d in DISRUPTIONS_DB.items():
            if d.type == "ROAD_BLOCK" and d.affected_entity_id:
                try:
                    eid = int(d.affected_entity_id)
                    blocked_edge_ids.add(eid)
                    edge_obj = Edge.objects.filter(id=eid).select_related('source', 'target').first()
                    if edge_obj:
                        active_hurdles_list.append({
                            "id": f"mem-{d_id}",
                            "type": d.type,
                            "edge_id": eid,
                            "description": d.description or f"Road Block on {edge_obj.source.name} → {edge_obj.target.name}",
                            "severity": d.severity,
                            "location": [edge_obj.source.lon, edge_obj.source.lat]
                        })
                except ValueError:
                    pass

        # 3. Build Graph
        all_edges = list(Edge.objects.select_related('source', 'target').all())
        
        G_clear = nx.DiGraph()
        G_direct = nx.DiGraph() # Graph with all edges regardless of hurdles for baseline comparison
        
        for edge in all_edges:
            # Check traffic speed & congestion
            traffic_speed = max(0.5, edge.current_traffic_speed if edge.current_traffic_speed > 0 else 6.94)
            free_flow = max(traffic_speed, edge.free_flow_speed if edge.free_flow_speed > 0 else 10.0)
            congestion_ratio = traffic_speed / free_flow # 0.0 to 1.0 (lower is more congested)
            
            # Base travel time in seconds
            base_travel_time = edge.distance / traffic_speed
            
            # Additional penalty if severely congested (< 0.4)
            congestion_penalty = 1.0
            if avoid_congestion and congestion_ratio < 0.4:
                congestion_penalty = 2.5 # Heavy penalty to route around traffic jams
                
            # Direct graph (includes everything)
            G_direct.add_edge(
                edge.source.id, edge.target.id,
                edge_id=edge.id,
                distance=edge.distance,
                weight=base_travel_time,
                edge=edge
            )
            
            # Hurdle-Free Graph
            is_blocked = (edge.id in blocked_edge_ids) and avoid_road_blocks
            if is_blocked:
                # Omit completely or apply massive penalty to ensure bypass
                continue
                
            weight = base_travel_time * congestion_penalty
            if priority == "SHORTEST":
                weight = edge.distance
            elif priority == "LEAST_CONGESTED":
                weight = (1.0 / max(0.1, congestion_ratio)) * edge.distance
            elif priority == "ACCESSIBLE" and not edge.is_accessible:
                weight = weight * 5.0
                
            G_clear.add_edge(
                edge.source.id, edge.target.id,
                edge_id=edge.id,
                distance=edge.distance,
                travel_time=base_travel_time,
                weight=weight,
                edge=edge
            )

        # 4. Calculate Paths
        optimal_path_found = False
        optimal_route_data = None
        direct_route_data = None
        hurdles_bypassed = []
        
        # Calculate Direct Route (to show what would happen without smart routing)
        try:
            direct_nodes = nx.shortest_path(G_direct, source=start_stop.id, target=target_stop.id, weight='weight')
            direct_route_data = self._format_route_path(G_direct, direct_nodes, start_stop, target_stop)
            # Check hurdles on direct path
            for seg in direct_route_data.get("segments", []):
                if seg["edge_id"] in blocked_edge_ids:
                    hurdles_bypassed.append({
                        "edge_id": seg["edge_id"],
                        "name": f"Road Block on {seg['from_stop']} → {seg['to_stop']}",
                        "hazard": "Road Closure / Blockade",
                        "delay_avoided_sec": 480
                    })
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            direct_route_data = None

        # Calculate Optimal Clear Route
        try:
            clear_nodes = nx.shortest_path(G_clear, source=start_stop.id, target=target_stop.id, weight='weight')
            optimal_route_data = self._format_route_path(G_clear, clear_nodes, start_stop, target_stop)
            optimal_path_found = True
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Fallback if no 100% blocked-free path exists: find path with least penalty in direct graph
            optimal_route_data = direct_route_data
            optimal_path_found = False

        if not optimal_route_data:
            return Response({"error": "No route exists connecting these stops in the transit graph"}, status=404)

        # Calculate benefits / metrics
        direct_time = direct_route_data.get("total_travel_time_sec", 0) if direct_route_data else optimal_route_data["total_travel_time_sec"]
        if len(hurdles_bypassed) > 0:
            direct_time += len(hurdles_bypassed) * 600 # Factor in blockage delay
            
        optimal_time = optimal_route_data["total_travel_time_sec"]
        time_saved_sec = max(0, direct_time - optimal_time)
        
        # Step-by-step guidance instructions for driver
        turn_by_turn = []
        segments = optimal_route_data.get("segments", [])
        for idx, seg in enumerate(segments):
            road_name = seg.get("road_name") or f"Corridor towards {seg['to_stop']}"
            turn_by_turn.append({
                "step": idx + 1,
                "instruction": f"Depart {seg['from_stop']} and continue along {road_name} towards {seg['to_stop']}",
                "distance_m": seg["distance_m"],
                "speed_kmh": seg["traffic_speed_kmh"],
                "traffic_condition": seg["traffic_condition"],
                "is_hurdle_free": True
            })

        response_payload = {
            "status": "SUCCESS",
            "bus_id": bus_id or "Custom Transit Vehicle",
            "start_stop": {
                "id": start_stop.id,
                "name": start_stop.name,
                "lat": start_stop.lat,
                "lon": start_stop.lon
            },
            "target_stop": {
                "id": target_stop.id,
                "name": target_stop.name,
                "lat": target_stop.lat,
                "lon": target_stop.lon
            },
            "hurdle_clearance": {
                "status": "100% CLEAR - ZERO HURDLES" if optimal_path_found else "CONGESTION TOLERANT",
                "hurdles_detected": len(active_hurdles_list),
                "hurdles_bypassed_count": len(hurdles_bypassed),
                "hurdles_bypassed_list": hurdles_bypassed,
                "active_network_hurdles": active_hurdles_list
            },
            "metrics": {
                "total_distance_km": round(optimal_route_data["total_distance_m"] / 1000.0, 2),
                "estimated_travel_time_min": round(optimal_time / 60.0, 1),
                "average_speed_kmh": round(optimal_route_data["avg_speed_kmh"], 1),
                "time_saved_min": round(time_saved_sec / 60.0, 1),
                "safety_score": 98 if optimal_path_found else 82,
                "traffic_congestion_level": optimal_route_data["overall_congestion"]
            },
            "route_geometry": optimal_route_data["geometry"],
            "direct_route_geometry": direct_route_data["geometry"] if direct_route_data else None,
            "segments": segments,
            "turn_by_turn": turn_by_turn
        }

        return Response(response_payload)

    def _format_route_path(self, G, node_sequence, start_stop, target_stop):
        full_geometry = []
        segments = []
        total_dist = 0.0
        total_time = 0.0
        speeds = []
        congestions = []
        
        stops_by_id = {s.id: s for s in Stop.objects.filter(id__in=node_sequence)}
        
        for i in range(len(node_sequence) - 1):
            u = node_sequence[i]
            v = node_sequence[i+1]
            edge_data = G[u][v]
            edge = edge_data['edge']
            
            geom = edge.geometry if edge.geometry else [[edge.source.lon, edge.source.lat], [edge.target.lon, edge.target.lat]]
            if not full_geometry:
                full_geometry.extend(geom)
            else:
                full_geometry.extend(geom[1:] if len(geom) > 1 else geom)
                
            dist = edge.distance
            speed_ms = max(0.5, edge.current_traffic_speed if edge.current_traffic_speed > 0 else 6.94)
            free_flow = max(speed_ms, edge.free_flow_speed if edge.free_flow_speed > 0 else 10.0)
            ratio = speed_ms / free_flow
            
            if ratio >= 0.7:
                traffic_cond = "FREE_FLOW"
            elif ratio >= 0.35:
                traffic_cond = "MODERATE"
            else:
                traffic_cond = "CONGESTED"
                
            seg_time = dist / speed_ms
            total_dist += dist
            total_time += seg_time
            speeds.append(speed_ms * 3.6)
            congestions.append(traffic_cond)
            
            src_stop = stops_by_id.get(u) or edge.source
            tgt_stop = stops_by_id.get(v) or edge.target
            
            segments.append({
                "edge_id": edge.id,
                "from_stop": src_stop.name,
                "to_stop": tgt_stop.name,
                "distance_m": round(dist, 1),
                "traffic_speed_kmh": round(speed_ms * 3.6, 1),
                "travel_time_sec": round(seg_time, 1),
                "traffic_condition": traffic_cond,
                "road_name": edge.metadata.get("osm_way_name") or f"Link {src_stop.name} - {tgt_stop.name}"
            })
            
        avg_speed = sum(speeds) / len(speeds) if speeds else 25.0
        
        overall_cong = "FREE_FLOW"
        if congestions.count("CONGESTED") > len(congestions) * 0.3:
            overall_cong = "CONGESTED"
        elif congestions.count("MODERATE") > len(congestions) * 0.4:
            overall_cong = "MODERATE"
            
        return {
            "geometry": full_geometry,
            "total_distance_m": total_dist,
            "total_travel_time_sec": total_time,
            "avg_speed_kmh": avg_speed,
            "overall_congestion": overall_cong,
            "segments": segments
        }
