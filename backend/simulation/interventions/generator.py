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
            G = nx.DiGraph()
            for edge in Edge.objects.all():
                if str(edge.id) != blocked_edge_id: # Remove blocked edge
                    G.add_edge(edge.source.id, edge.target.id, edge_id=edge.id, distance=edge.distance)
                    
            source_node = blocked_edge.source.id
            target_node = blocked_edge.target.id
            
            try:
                # Find shortest path bypassing the block
                path_nodes = nx.shortest_path(G, source=source_node, target=target_node, weight='distance')
                
                # Convert nodes to edge IDs
                bypass_edges = []
                for i in range(len(path_nodes)-1):
                    u = path_nodes[i]
                    v = path_nodes[i+1]
                    bypass_edges.append(G[u][v]['edge_id'])
                    
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
