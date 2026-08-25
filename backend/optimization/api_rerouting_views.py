import networkx as nx
from rest_framework.views import APIView
from rest_framework.response import Response
from core.models import Stop, Edge, Disruption, Vehicle
from simulation.state.live_state import LiveStateEngine
from optimization.disruption_sandbox_engine import DisruptionSandboxEngine

class ReroutingScenariosView(APIView):
    """
    Returns available edges, stops, and active disruptions for the Rerouting Sandbox.
    """
    def get(self, request):
        stops = list(Stop.objects.filter(is_active=True).values('id', 'name', 'lat', 'lon', 'capacity', 'is_accessible'))
        edges = list(Edge.objects.filter(is_active=True).values(
            'id', 'source_id', 'target_id', 'distance', 'baseline_travel_time', 
            'current_traffic_speed', 'free_flow_speed', 'is_accessible', 'geometry'
        ))
        
        disruptions = list(Disruption.objects.filter(is_active=True).values(
            'id', 'disruption_type', 'affected_stop_id', 'affected_edge_id', 'severity', 'description'
        ))
        
        vehicles = list(Vehicle.objects.filter(state__in=['ACTIVE', 'DELAYED']).values(
            'id', 'identifier', 'vehicle_type', 'route_id', 'occupancy', 'capacity'
        ))
        
        return Response({
            "stops": stops,
            "edges": edges,
            "active_disruptions": disruptions,
            "vehicles": vehicles
        })

class ReroutingCalculateView(APIView):
    """
    Executes the Pre-Action Rerouting Sandbox evaluation without auto-dispatching.
    Uses DisruptionSandboxEngine to calculate multi-objective detour and impact metrics.
    """
    def post(self, request):
        data = request.data
        blocked_edge_id = data.get('blocked_edge_id')
        require_accessibility = bool(data.get('require_accessibility', False))
        alpha = float(data.get('alpha', 1.0))
        beta = float(data.get('beta', 0.45))
        gamma = float(data.get('gamma', 50.0))
        origin_node = data.get('origin_node')
        destination_node = data.get('destination_node')

        # 1. Build NetworkX Graph from active DB Stops and Edges
        G = nx.DiGraph()
        live_state = LiveStateEngine.get_current_state()
        live_stops = live_state.get('stops', {})

        stops_qs = Stop.objects.filter(is_active=True)
        stops_map = {}
        for s in stops_qs:
            stops_map[s.id] = s
            s_live = live_stops.get(str(s.id), {})
            current_q = s_live.get('queue_count', 15)
            
            G.add_node(
                s.id,
                name=s.name,
                lat=s.lat,
                lon=s.lon,
                capacity=s.capacity or 150,
                current_queue=current_q,
                arrival_rate=8.0 if "CENTRAL" in s.name.upper() or "PARK" in s.name.upper() else 4.5,
                c_servers=2,
                service_rate=5.0,
                is_accessible=s.is_accessible
            )

        edges_qs = Edge.objects.filter(is_active=True).select_related('source', 'target')
        edge_geometries = {}
        first_edge = None
        for e in edges_qs:
            if first_edge is None:
                first_edge = e
            edge_geometries[e.id] = e.geometry
            edge_geometries[str(e.id)] = e.geometry
            
            G.add_edge(
                e.source_id,
                e.target_id,
                edge_id=e.id,
                id=e.id,
                distance=e.distance or 1000.0,
                free_flow_speed=e.free_flow_speed or 10.0,
                current_speed=e.current_traffic_speed or e.free_flow_speed or 10.0,
                is_step_free=e.is_accessible,
                is_accessible=e.is_accessible,
                geometry=e.geometry
            )

        # Default to first edge or first active disruption if blocked_edge_id not supplied
        if not blocked_edge_id:
            active_disp = Disruption.objects.filter(is_active=True, affected_edge__isnull=False).first()
            if active_disp:
                blocked_edge_id = active_disp.affected_edge_id
            elif first_edge:
                blocked_edge_id = first_edge.id

        # 2. Run DisruptionSandboxEngine
        engine = DisruptionSandboxEngine(alpha=alpha, beta=beta, gamma=gamma)
        
        try:
            result = engine.calculate_alternate_route(
                transit_graph=G,
                blocked_edge_id=int(blocked_edge_id) if str(blocked_edge_id).isdigit() else blocked_edge_id,
                require_accessibility=require_accessibility,
                origin_node=int(origin_node) if origin_node is not None and str(origin_node).isdigit() else origin_node,
                destination_node=int(destination_node) if destination_node is not None and str(destination_node).isdigit() else destination_node
            )
        except Exception as err:
            return Response({"error": f"Evaluation failed: {str(err)}"}, status=400)

        # 3. Enrich result with node details and map line geometries
        route_nodes_details = []
        route_path_coordinates = []
        
        alternate_nodes = result.get('alternate_route', [])
        for nid in alternate_nodes:
            st = stops_map.get(nid)
            if st:
                route_nodes_details.append({
                    "id": st.id,
                    "name": st.name,
                    "lat": st.lat,
                    "lon": st.lon,
                    "capacity": st.capacity,
                    "is_accessible": st.is_accessible
                })
                route_path_coordinates.append([st.lon, st.lat])

        result["route_nodes_details"] = route_nodes_details
        result["route_path_coordinates"] = route_path_coordinates
        result["blocked_edge_id"] = blocked_edge_id
        result["require_accessibility"] = require_accessibility
        result["weights"] = {"alpha": alpha, "beta": beta, "gamma": gamma}

        return Response(result)
