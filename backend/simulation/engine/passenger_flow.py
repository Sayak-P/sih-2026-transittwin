from datetime import datetime, timedelta
import math
from core.models import Vehicle, RouteEdge, Edge
from simulation.passenger.demand import generate_demand_cohorts, spawn_passengers_for_tick
from simulation.passenger.queues import calculate_waiting_time
from simulation.passenger.alighting import process_alighting
from simulation.passenger.boarding import process_boarding

class PassengerFlowSimulator:
    def __init__(self, sim_state, config):
        self.sim_state = sim_state
        self.start_time = config.get('start_time')
        self.end_time = config.get('end_time')
        self.timestep_seconds = config.get('timestep_seconds', 10)
        self.seed = config.get('random_seed', 42)
        self.event_log = []
        
        # Disruption tracking
        self.causal_graph = [] # Phase 6 blast-radius tracking
        self.directly_affected_vehicles = set()
        self.directly_affected_stops = set()
        self.indirectly_affected_stops = set()
        
        # Calculate total ticks
        duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.total_ticks = max(1, int(duration_seconds / self.timestep_seconds))

        self._init_vehicle_routes()
        
    def _init_vehicle_routes(self):
        # Cache route geometries for interpolation
        self.vehicle_routes = {}
        for v_id, v_data in self.sim_state.vehicles.items():
            # In Phase 4, we assume the vehicles stay on their DB assigned routes
            # We fetch them once here
            vehicle = Vehicle.objects.filter(identifier=v_id).first()
            if vehicle and vehicle.route:
                edges = list(RouteEdge.objects.filter(route=vehicle.route).order_by('sequence_order'))
                route_edges = edges
                # Use route override if provided (Phase 7 Intervention)
                overrides = self.sim_state.metrics.get("route_overrides", {})
                if v_id in overrides:
                    route_edges = []
                    for e_id in overrides[v_id]:
                        e_obj = Edge.objects.get(id=e_id)
                        # Mock a RouteEdge struct
                        class MockRE:
                            pass
                        re = MockRE()
                        re.edge = e_obj
                        route_edges.append(re)
                
                if route_edges:
                    self.vehicle_routes[v_id] = {
                        "edges": route_edges,
                        "current_edge_idx": 0,
                        "progress": 0.0,
                        "last_stop_id": route_edges[0].edge.source.id
                    }
                    # Init coordinates
                    p = route_edges[0].edge.geometry[0]
                    v_data['lon'], v_data['lat'] = p[0], p[1]

    def log_event(self, time_str, message):
        self.event_log.append({
            "timestamp": time_str,
            "message": message
        })

    def run(self):
        # 1. GENERATE DEMAND
        generate_demand_cohorts(self.sim_state, self.start_time, self.end_time, self.seed)
        
        current_time = self.start_time
        
        for tick in range(self.total_ticks):
            time_str = current_time.strftime("%H:%M:%S")
            
            # 2. SPAWN DEMAND (Arrivals)
            duration_seconds = (self.end_time - self.start_time).total_seconds()
            spawn_passengers_for_tick(self.sim_state, self.timestep_seconds, duration_seconds)
            
            # 3. UPDATE VEHICLES
            self._move_vehicles(time_str)
            
            # 4. QUEUES & METRICS
            calculate_waiting_time(self.sim_state, self.timestep_seconds)
            
            # 5. CONSERVATION LAW CHECK
            self._verify_conservation(current_time)
            
            # Advance clock
            current_time += timedelta(seconds=self.timestep_seconds)
            
        # Finalize metrics
        m = self.sim_state.metrics
        m["passengers_remaining"] = m["passengers_generated"] - m["passengers_served"]
        if m["passengers_generated"] > 0:
            m["average_waiting_minutes"] = (m["total_waiting_seconds"] / 60.0) / m["passengers_generated"]
        else:
            m["average_waiting_minutes"] = 0.0
            
        return m, self.event_log

    def _move_vehicles(self, time_str):
        base_speed_mps = 10.0 # ~36 km/h for the baseline
        weather_mult = self.sim_state.metrics.get("weather_speed_multiplier", 1.0)
        speed_mps = base_speed_mps * weather_mult
        
        blocked_edges = self.sim_state.metrics.get("blocked_edges", [])
        holds = self.sim_state.metrics.get("holds", {})
        
        for v_id, routing in self.vehicle_routes.items():
            v_data = self.sim_state.vehicles[v_id]
            
            # If vehicle is broken down, it doesn't move
            if v_data.get('status') == "BROKEN_DOWN":
                self.directly_affected_vehicles.add(v_id)
                self._record_causal(1, v_id, "VEHICLE_BREAKDOWN", "Vehicle physically broken down.")
                continue

            # Check holds (Schedule Modification)
            if v_id in holds and holds[v_id] > 0:
                holds[v_id] -= self.timestep_seconds
                continue

            edges = routing["edges"]
            idx = routing["current_edge_idx"]
            edge_obj = edges[idx].edge
            
            # Check ROAD_BLOCK
            if str(edge_obj.id) in blocked_edges:
                self.directly_affected_vehicles.add(v_id)
                self._record_causal(1, v_id, f"EDGE-{edge_obj.id}", "Vehicle stuck behind ROAD_BLOCK.")
                continue # Cannot move forward

            distance = max(1.0, edge_obj.distance)
            
            # Calculate distance covered in this tick
            dist_this_tick = speed_mps * self.timestep_seconds
            prog_increase = dist_this_tick / distance
            
            routing["progress"] += prog_increase
            
            v_data = self.sim_state.vehicles[v_id]
            
            if routing["progress"] >= 1.0:
                # We arrived at the target stop!
                arrived_stop_id = edge_obj.target.id
                closed_stops = self.sim_state.metrics.get("closed_stops", set())
                
                if arrived_stop_id not in closed_stops:
                    # ALIGHT
                    alighted = process_alighting(self.sim_state, v_id, arrived_stop_id)
                    if alighted > 0:
                        self.log_event(time_str, f"{v_id} arrived at Stop {arrived_stop_id}. {alighted} passengers alighted.")
                        
                    # BOARD
                    queue_rem = 0
                    boarded = process_boarding(self.sim_state, v_id, arrived_stop_id)
                    if boarded > 0:
                        self.log_event(time_str, f"{v_id} boarded {boarded} passengers at Stop {arrived_stop_id}.")
                    queue_rem = sum(self.sim_state.stop_queues.get(arrived_stop_id, {}).values())
                    if queue_rem > 0 and boarded > 0:
                        self.log_event(time_str, f"Queue remaining at Stop {arrived_stop_id}: {queue_rem}")
                else:
                    self.log_event(time_str, f"{v_id} bypassed Stop {arrived_stop_id} (CLOSED).")

                # Move to next edge
                routing["progress"] = 0.0
                routing["current_edge_idx"] = (idx + 1) % len(edges)
                
                # Move to exactly stop coordinates
                target_p = edge_obj.geometry[1]
                v_data['lon'], v_data['lat'] = target_p[0], target_p[1]
                
                # Check for secondary crowding / capacity bottleneck
                if queue_rem > 0 and v_id in self.directly_affected_vehicles:
                    # Vehicle was delayed by a direct disruption, causing this queue overload
                    self.indirectly_affected_stops.add(arrived_stop_id)
                    self._record_causal(2, f"STOP-{arrived_stop_id}", v_id, "Secondary crowding due to capacity bottleneck from delayed vehicle.")
                    
            else:
                # Interpolate coords
                p1 = edge_obj.geometry[0]
                p2 = edge_obj.geometry[1]
                prog = routing["progress"]
                v_data['lon'] = p1[0] + (p2[0] - p1[0]) * prog
                v_data['lat'] = p1[1] + (p2[1] - p1[1]) * prog

    def _verify_conservation(self, current_time):
        total_spawned = 0
        total_waiting = 0
        total_onboard = 0
        total_completed = 0
        
        for c_id, cohort in self.sim_state.passenger_cohorts.items():
            total_spawned += cohort['spawned']
            total_waiting += cohort['waiting']
            total_onboard += cohort['onboard']
            total_completed += cohort['completed']
            
        # The sum of waiting + onboard + completed must equal total spawned so far
        if total_spawned != (total_waiting + total_onboard + total_completed):
            raise AssertionError(
                f"Conservation Law Violation at {current_time}! "
                f"Spawned: {total_spawned}, "
                f"Sum: {total_waiting + total_onboard + total_completed} "
                f"(Wait: {total_waiting}, Onboard: {total_onboard}, Comp: {total_completed})"
            )

    def _record_causal(self, depth, entity, source, reason):
        # Prevent spamming the same causal link every tick
        for cg in self.causal_graph:
            if cg["entity"] == entity and cg["source"] == source:
                return
        self.causal_graph.append({
            "depth": depth,
            "entity": entity,
            "source": source,
            "reason": reason
        })
