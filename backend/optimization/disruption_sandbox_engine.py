r"""
Disruption Sandbox Engine Module for Transit Digital Twin.
===========================================================

A core architectural invariant of this system is that it must NEVER auto-dispatch.
It evaluates alternate transit schedules and quantifies delay, safety, and energy
impacts before human operators make an intervention decision.

Math Formulation:
1. Multi-Objective Cost Function:
   W(e) = \alpha * T_e + \beta * E_e + \gamma * A_e
   Where:
     - T_e: Travel time across edge e (minutes)
     - E_e: Energy cost across edge e (kWh)
     - A_e: Accessibility penalty (0 if step-free, otherwise penalty weight / pruned)

2. Delta Delay (Minutes):
   Aggregate time saved by taking the detour vs waiting out the blockage.

3. Safety Risk Index (0.0 to 10.0):
   M/M/c Queueing Dynamics on transfer/rerouted stops to estimate overcrowding hazard:
   Crowd(t + dt) = max(0, Q_0 + (lambda_effective - c * mu) * dt)
   Hazard = 10.0 * min(1.0, Crowd / MaxCapacity)

4. Energy Impact (kWh):
   Net delta in energy consumption caused by detour distance vs original edge.
"""

from typing import Dict, List, Any, Optional, Tuple
import math
import networkx as nx


class DisruptionSandboxEngine:
    """
    Pre-Action Sandbox Service for transit disruption rerouting.
    Evaluates alternate schedules without auto-dispatching.
    """

    DEFAULT_ALPHA: float = 1.0    # Weight for travel time (minutes)
    DEFAULT_BETA: float = 0.45    # Weight for energy consumption (kWh)
    DEFAULT_GAMMA: float = 50.0   # Penalty weight for accessibility violations
    DEFAULT_ENERGY_RATE_KWH_PER_KM: float = 1.2  # Standard electric bus consumption (kWh/km)
    DEFAULT_DISRUPTION_WAIT_MINUTES: float = 45.0  # Estimated wait time if bus remains stalled

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
        energy_rate_kwh_per_km: float = DEFAULT_ENERGY_RATE_KWH_PER_KM,
        disruption_wait_minutes: float = DEFAULT_DISRUPTION_WAIT_MINUTES,
    ) -> None:
        """
        Initialize the engine with multi-objective optimization parameters.

        :param alpha: Weight coefficient for travel time (T_e).
        :param beta: Weight coefficient for energy cost (E_e).
        :param gamma: Penalty coefficient for non-accessible segments (A_e).
        :param energy_rate_kwh_per_km: Average vehicle traction energy (kWh/km).
        :param disruption_wait_minutes: Baseline duration to clear the obstruction.
        """
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.energy_rate_kwh_per_km = energy_rate_kwh_per_km
        self.disruption_wait_minutes = disruption_wait_minutes

    def calculate_alternate_route(
        self,
        transit_graph: nx.DiGraph,
        blocked_edge_id: Any,
        require_accessibility: bool = False,
        origin_node: Optional[Any] = None,
        destination_node: Optional[Any] = None,
        dt_minutes: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Calculates an optimal detour bypassing a blocked edge and quantifies delay,
        safety risk (via M/M/c queueing), and energy impact.

        :param transit_graph: Directed NetworkX graph of stops (nodes) and road segments (edges).
        :param blocked_edge_id: Identifier of the impassable edge.
        :param require_accessibility: If True, strictly removes/penalizes non-step-free edges.
        :param origin_node: Optional starting node. If None, derived from the blocked edge source.
        :param destination_node: Optional target node. If None, derived from the blocked edge target.
        :param dt_minutes: Lookahead horizon (minutes) for M/M/c queue evaluation.
        :return: Dictionary containing:
                 - alternate_route (List[Any]): Ordered node IDs of the new path.
                 - delta_delay_minutes (float): Time saved vs waiting out the incident.
                 - safety_risk_index (float): 0.0 - 10.0 hazard score from M/M/c queue surge.
                 - energy_impact_kwh (float): Net change in energy consumption.
        """
        # 1. Identify the blocked edge endpoints in the graph
        blocked_u, blocked_v, blocked_edge_attrs = self._find_edge_by_id(transit_graph, blocked_edge_id)

        source_node = origin_node if origin_node is not None else blocked_u
        target_node = destination_node if destination_node is not None else blocked_v

        if source_node is None or target_node is None:
            raise ValueError(f"Blocked edge ID '{blocked_edge_id}' not found in the transit graph.")

        # Baseline metrics for original edge
        original_dist_m = float(blocked_edge_attrs.get("distance", 1000.0))
        original_speed_mps = float(blocked_edge_attrs.get("free_flow_speed", 10.0))
        original_time_min = (original_dist_m / max(1.0, original_speed_mps)) / 60.0
        original_energy_kwh = (original_dist_m / 1000.0) * self.energy_rate_kwh_per_km

        # 2. Build candidate subgraph with Multi-Objective Cost Function: W(e)
        subgraph = self._build_weighted_subgraph(
            transit_graph=transit_graph,
            blocked_u=blocked_u,
            blocked_v=blocked_v,
            blocked_edge_id=blocked_edge_id,
            require_accessibility=require_accessibility,
        )

        # 3. Pathfinding: Minimize W(e) = \alpha(T_e) + \beta(E_e) + \gamma(A_e)
        try:
            alternate_route = nx.shortest_path(
                subgraph,
                source=source_node,
                target=target_node,
                weight="multi_objective_weight",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # No viable alternate route exists under given constraints
            return {
                "alternate_route": [],
                "delta_delay_minutes": 0.0,
                "safety_risk_index": 10.0,  # Critical hazard: trapped passengers / dead network
                "energy_impact_kwh": 0.0,
                "status": "INFEASIBLE_NO_PATH",
            }

        # 4. Calculate Detour Route Performance (Time & Energy)
        detour_time_min, detour_energy_kwh = self._compute_route_metrics(subgraph, alternate_route)

        # Mathematical Calculation 1: Delta Delay (Minutes saved vs waiting out the incident)
        # Total time if waiting = original_time + disruption_clearance_wait
        time_if_waiting_out = original_time_min + self.disruption_wait_minutes
        delta_delay_minutes = round(max(0.0, time_if_waiting_out - detour_time_min), 2)

        # Mathematical Calculation 2: Energy Impact (kWh)
        # Net change in energy = detour energy - original baseline energy
        energy_impact_kwh = round(detour_energy_kwh - original_energy_kwh, 2)

        # Mathematical Calculation 3: Safety Risk Index (0.0 to 10.0) via M/M/c Queueing
        safety_risk_index = self._evaluate_safety_risk_mmc(
            transit_graph=transit_graph,
            route_nodes=alternate_route,
            dt_minutes=dt_minutes,
        )

        return {
            "alternate_route": alternate_route,
            "delta_delay_minutes": delta_delay_minutes,
            "safety_risk_index": round(safety_risk_index, 2),
            "energy_impact_kwh": energy_impact_kwh,
            "status": "FEASIBLE_EVALUATED",
        }

    # =========================================================================
    # Internal Mathematical Routines
    # =========================================================================

    def _build_weighted_subgraph(
        self,
        transit_graph: nx.DiGraph,
        blocked_u: Any,
        blocked_v: Any,
        blocked_edge_id: Any,
        require_accessibility: bool,
    ) -> nx.DiGraph:
        r"""
        Creates a routing graph applying edge costs:
        W(e) = \alpha * T_e + \beta * E_e + \gamma * A_e
        """
        G = transit_graph.copy()

        # Remove the impassable edge
        if G.has_edge(blocked_u, blocked_v):
            edge_data = G[blocked_u][blocked_v]
            if edge_data.get("edge_id") == blocked_edge_id or edge_data.get("id") == blocked_edge_id:
                G.remove_edge(blocked_u, blocked_v)

        edges_to_remove = []

        for u, v, data in G.edges(data=True):
            # Check edge_id in case parallel or other references
            if data.get("edge_id") == blocked_edge_id or data.get("id") == blocked_edge_id:
                edges_to_remove.append((u, v))
                continue

            # 1. Travel Time Component: T_e = Distance / Speed (in minutes)
            distance_m = float(data.get("distance", 500.0))
            speed_mps = float(data.get("current_speed", data.get("free_flow_speed", 10.0)))
            t_e_minutes = (distance_m / max(0.5, speed_mps)) / 60.0

            # 2. Energy Component: E_e = Distance (km) * Rate (kWh/km)
            distance_km = distance_m / 1000.0
            e_e_kwh = distance_km * self.energy_rate_kwh_per_km

            # 3. Accessibility Component: A_e
            is_step_free = bool(data.get("is_step_free", data.get("is_accessible", True)))
            if not is_step_free:
                if require_accessibility:
                    # Strict removal / infinite penalty
                    edges_to_remove.append((u, v))
                    continue
                else:
                    a_e_penalty = 1.0  # Normalized non-accessible penalty
            else:
                a_e_penalty = 0.0

            # Multi-Objective Weight: W(e) = \alpha(T_e) + \beta(E_e) + \gamma(A_e)
            w_e = (self.alpha * t_e_minutes) + (self.beta * e_e_kwh) + (self.gamma * a_e_penalty)

            data["travel_time_min"] = t_e_minutes
            data["energy_kwh"] = e_e_kwh
            data["multi_objective_weight"] = w_e

        for u, v in edges_to_remove:
            if G.has_edge(u, v):
                G.remove_edge(u, v)

        return G

    def _compute_route_metrics(self, graph: nx.DiGraph, route: List[Any]) -> Tuple[float, float]:
        """Sums travel time and energy across edges of a path."""
        total_time_min = 0.0
        total_energy_kwh = 0.0

        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            if graph.has_edge(u, v):
                data = graph[u][v]
                total_time_min += data.get("travel_time_min", 1.0)
                total_energy_kwh += data.get("energy_kwh", 0.5)

        return total_time_min, total_energy_kwh

    def _evaluate_safety_risk_mmc(
        self,
        transit_graph: nx.DiGraph,
        route_nodes: List[Any],
        dt_minutes: float,
    ) -> float:
        """
        Evaluates localized hazard score (0.0 to 10.0) at rerouted stops using
        standard M/M/c queueing dynamics:

        For each intermediate transfer node k:
          Crowd(t + dt) = max( 0, Queue_0 + (lambda_eff - c * mu) * dt )
          Overflow_Ratio = Crowd(t + dt) / MaxCapacity
          Hazard_Score(k) = 10.0 * min(1.0, max(0.0, (Overflow_Ratio - 0.5) / 0.5))

        The route safety risk is the worst-case hazard among detour nodes.
        """
        if len(route_nodes) <= 2:
            return 1.0  # Minimal risk on direct short bypass

        intermediate_nodes = route_nodes[1:-1]
        max_node_hazard = 0.0

        for node_id in intermediate_nodes:
            node_attrs = transit_graph.nodes.get(node_id, {})

            max_capacity = float(node_attrs.get("capacity", node_attrs.get("max_capacity", 150.0)))
            current_queue = float(node_attrs.get("current_queue", node_attrs.get("queue_count", 25.0)))
            
            # Arrival rate lambda (pax/min) + transfer surge from rerouted line
            base_lambda = float(node_attrs.get("arrival_rate", node_attrs.get("lambda_base", 6.0)))
            reroute_surge_lambda = 4.0  # Injected passenger volume from diverted line
            lambda_eff = base_lambda + reroute_surge_lambda

            # Service throughput: c servers (buses/platforms) * mu (boarding rate pax/min)
            c_servers = int(node_attrs.get("c_servers", node_attrs.get("num_buses", 2)))
            mu_rate = float(node_attrs.get("service_rate", node_attrs.get("mu_boarding", 5.0)))
            service_capacity_rate = max(1.0, c_servers * mu_rate)

            # Queueing Step: Crowd(t + dt) = max(0, Q(t) + (lambda_eff - c * mu) * dt)
            net_rate = lambda_eff - service_capacity_rate
            predicted_crowd = max(0.0, current_queue + (net_rate * dt_minutes))

            # Overflow evaluation
            occupancy_ratio = predicted_crowd / max(10.0, max_capacity)

            # Hazard Mapping: 
            # < 50% capacity -> near 0 hazard
            # 50% - 100% capacity -> scaled 0.0 to 7.0 hazard
            # > 100% capacity (Overcrowded / Crush load) -> 7.0 to 10.0 hazard
            if occupancy_ratio <= 0.5:
                hazard = (occupancy_ratio / 0.5) * 2.0
            elif occupancy_ratio <= 1.0:
                hazard = 2.0 + ((occupancy_ratio - 0.5) / 0.5) * 5.0
            else:
                crush_overshoot = min(1.0, (occupancy_ratio - 1.0) / 0.5)
                hazard = 7.0 + (crush_overshoot * 3.0)

            if hazard > max_node_hazard:
                max_node_hazard = hazard

        return min(10.0, max(0.0, max_node_hazard))

    def _find_edge_by_id(
        self,
        graph: nx.DiGraph,
        blocked_edge_id: Any,
    ) -> Tuple[Optional[Any], Optional[Any], Dict[str, Any]]:
        """Locates edge tuple (u, v) and its attribute dict by edge_id."""
        for u, v, data in graph.edges(data=True):
            if data.get("edge_id") == blocked_edge_id or data.get("id") == blocked_edge_id:
                return u, v, data
        return None, None, {}
