import uuid
from typing import List
from simulation.interventions.models import InterventionType, InterventionCandidate
from simulation.disruptions.models import Disruption
from core.models import Edge, RouteEdge, Stop
import networkx as nx

class CandidateGenerator:
    @staticmethod
    def generate_candidates(scenario_id: str, disruption: Disruption, sim_state) -> List[InterventionCandidate]:
        candidates = []
        
        # We only generate interventions if there is an actionable disruption
        if disruption.type == "ROAD_BLOCK":
            # 1. Reroute candidates
            blocked_edge_id = disruption.affected_entity_id
            candidates.extend(CandidateGenerator._generate_reroute_candidates(scenario_id, blocked_edge_id, sim_state))
            
            # 2. Spare vehicle candidates
            candidates.extend(CandidateGenerator._generate_spare_candidates(scenario_id, sim_state))
            
            # 3. Schedule mod candidates
            candidates.extend(CandidateGenerator._generate_schedule_candidates(scenario_id, sim_state))
            
        elif disruption.type == "CROWD_SURGE":
            # Temporary stop closure
            stop_id = disruption.affected_entity_id
            candidates.append(CandidateGenerator._generate_stop_closure(scenario_id, stop_id))
            
            # Generate reroute candidates bypassing this stop
            candidates.extend(CandidateGenerator._generate_stop_bypass_candidates(scenario_id, stop_id, sim_state))
            
            # Spare vehicle deployment
            candidates.extend(CandidateGenerator._generate_spare_candidates(scenario_id, sim_state))

        return candidates

    @staticmethod
    def _generate_reroute_candidates(scenario_id: str, blocked_edge_id: str, sim_state) -> List[InterventionCandidate]:
        candidates = []
        try:
            blocked_edge = Edge.objects.get(id=blocked_edge_id)
        except Edge.DoesNotExist:
            return []

        # Find vehicles directly affected (heading to this edge)
        # For Phase 7, we'll pick the first active vehicle heading that way
        affected_vehicles = [vid for vid, v in sim_state.vehicles.items() if v.get("status") == "ACTIVE"]
        
        for v_id in affected_vehicles:
            # Check if network graph allows bypassing
            from django.utils import timezone
            from datetime import timedelta
            
            G = nx.DiGraph()
            for edge in Edge.objects.all():
                if str(edge.id) != blocked_edge_id: # Remove blocked edge
                    # Calculate dynamic travel time based on live traffic
                    # Check for data staleness to prevent routing ghosts
                    is_stale = False
                    if edge.data_source == 'TOMTOM' and edge.last_updated_at:
                        age = timezone.now() - edge.last_updated_at
                        if age > timedelta(minutes=15):
                            is_stale = True
                            
                    if edge.data_source == 'ESTIMATED' or is_stale:
                        # Fallback to free flow or baseline to prevent ghost congestion routing
                        traffic_speed = max(0.1, edge.free_flow_speed if edge.free_flow_speed else edge.current_traffic_speed)
                    else:
                        traffic_speed = max(0.1, edge.current_traffic_speed) # prevent div by zero
                        
                    travel_time = edge.distance / traffic_speed
                    G.add_edge(edge.source.id, edge.target.id, edge_id=edge.id, distance=edge.distance, travel_time=travel_time)
                    
            source_node = blocked_edge.source.id
            target_node = blocked_edge.target.id
            
            try:
                # Find shortest path bypassing the block using TRAVEL TIME, not distance
                path_nodes = nx.shortest_path(G, source=source_node, target=target_node, weight='travel_time')
                
                # Convert nodes to edge IDs
                bypass_edges = []
                route_geometry = []
                for i in range(len(path_nodes)-1):
                    u = path_nodes[i]
                    v = path_nodes[i+1]
                    eid = G[u][v]['edge_id']
                    bypass_edges.append(eid)
                    edge_obj = Edge.objects.filter(id=eid).first()
                    if edge_obj and edge_obj.geometry:
                        route_geometry.extend(edge_obj.geometry)
                    
                distance = nx.shortest_path_length(G, source=source_node, target=target_node, weight='distance')
                added_distance = distance - blocked_edge.distance
                
                candidate = InterventionCandidate(
                    id=str(uuid.uuid4()),
                    scenario_id=scenario_id,
                    type=InterventionType.VEHICLE_REROUTE,
                    parameters={
                        "vehicle_id": v_id,
                        "blocked_edge": blocked_edge_id,
                        "bypass_edges": bypass_edges,
                        "added_distance": added_distance
                    },
                    description=f"Reroute {v_id} around blocked edge {blocked_edge_id} using {len(bypass_edges)} alternate edges.",
                    route=route_geometry
                )
                candidates.append(candidate)
            except nx.NetworkXNoPath:
                # Infeasible
                candidate = InterventionCandidate(
                    id=str(uuid.uuid4()),
                    scenario_id=scenario_id,
                    type=InterventionType.VEHICLE_REROUTE,
                    parameters={"vehicle_id": v_id},
                    description=f"Attempted reroute for {v_id}",
                    feasibility_status="INFEASIBLE",
                    constraint_violations=["No physical alternative route exists."]
                )
                candidates.append(candidate)
                
        return candidates

    @staticmethod
    def _generate_stop_bypass_candidates(scenario_id: str, stop_id: str, sim_state) -> List[InterventionCandidate]:
        candidates = []
        try:
            stop = Stop.objects.get(id=stop_id)
        except Stop.DoesNotExist:
            return []

        affected_vehicles = [vid for vid, v in sim_state.vehicles.items() if v.get("status") == "ACTIVE"]
        if not affected_vehicles:
            return []
            
        v_id = affected_vehicles[0]
        
        upstream_edge = stop.incoming_edges.first()
        downstream_edge = stop.outgoing_edges.first()
        
        if not upstream_edge or not downstream_edge:
            return []
            
        source_node = upstream_edge.source.id
        target_node = downstream_edge.target.id
        
        G = nx.DiGraph()
        affected_edges = set([e.id for e in stop.incoming_edges.all()] + [e.id for e in stop.outgoing_edges.all()])
        
        for edge in Edge.objects.all():
            traffic_speed = max(0.1, edge.current_traffic_speed)
            travel_time = edge.distance / traffic_speed
            
            # Apply severe crowding penalty if edge is affected by CROWD_SURGE
            if edge.id in affected_edges:
                travel_time += 99999.0
                
            G.add_edge(edge.source.id, edge.target.id, edge_id=edge.id, distance=edge.distance, travel_time=travel_time)
                
        try:
            path_nodes = nx.shortest_path(G, source=source_node, target=target_node, weight='travel_time')
            bypass_edges = []
            route_geometry = []
            for i in range(len(path_nodes)-1):
                u = path_nodes[i]
                v = path_nodes[i+1]
                eid = G[u][v]['edge_id']
                bypass_edges.append(eid)
                edge_obj = Edge.objects.filter(id=eid).first()
                if edge_obj and edge_obj.geometry:
                    route_geometry.extend(edge_obj.geometry)
                    
            distance = nx.shortest_path_length(G, source=source_node, target=target_node, weight='distance')
            
            candidate = InterventionCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                type=InterventionType.VEHICLE_REROUTE,
                parameters={
                    "vehicle_id": v_id,
                    "blocked_stop": stop_id,
                    "bypass_edges": bypass_edges,
                    "added_distance": distance
                },
                description=f"Reroute {v_id} around overloaded Stop {stop_id} using {len(bypass_edges)} alternate edges.",
                route=route_geometry
            )
            candidates.append(candidate)
        except nx.NetworkXNoPath:
            pass
            
        return candidates

    @staticmethod
    def _generate_spare_candidates(scenario_id: str, sim_state) -> List[InterventionCandidate]:
        candidates = []
        # Find spare vehicles in live state
        spares = [vid for vid, v in sim_state.vehicles.items() if v.get("status") == "SPARE"]
        
        if not spares:
            candidates.append(InterventionCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                type=InterventionType.SPARE_VEHICLE_DEPLOYMENT,
                parameters={},
                description="Deploy spare vehicle",
                feasibility_status="INFEASIBLE",
                constraint_violations=["No spare vehicles available in fleet."]
            ))
        else:
            spare_id = spares[0]
            candidates.append(InterventionCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                type=InterventionType.SPARE_VEHICLE_DEPLOYMENT,
                parameters={"vehicle_id": spare_id},
                description=f"Deploy spare vehicle {spare_id} to absorb passenger queue."
            ))
        return candidates

    @staticmethod
    def _generate_schedule_candidates(scenario_id: str, sim_state) -> List[InterventionCandidate]:
        # For simplicity, delay the departure of an active bus
        active = [vid for vid, v in sim_state.vehicles.items() if v.get("status") == "ACTIVE"]
        if active:
            vid = active[0]
            return [InterventionCandidate(
                id=str(uuid.uuid4()),
                scenario_id=scenario_id,
                type=InterventionType.SCHEDULE_MODIFICATION,
                parameters={"vehicle_id": vid, "hold_seconds": 300}, # hold for 5 minutes
                description=f"Hold vehicle {vid} for 5 minutes to space out headway."
            )]
        return []

    @staticmethod
    def _generate_stop_closure(scenario_id: str, stop_id: str) -> InterventionCandidate:
        return InterventionCandidate(
            id=str(uuid.uuid4()),
            scenario_id=scenario_id,
            type=InterventionType.TEMPORARY_STOP_CLOSURE,
            parameters={"stop_id": int(stop_id)},
            description=f"Temporarily close Stop {stop_id} to prevent unsafe boarding."
        )
