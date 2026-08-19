import copy

class SimulationState:
    def __init__(self, state_dict):
        # Deep copy ensures complete isolation from LiveState references
        self.version = state_dict.get('version', 0)
        self.vehicles = copy.deepcopy(state_dict.get('vehicles', {}))
        self.stops = copy.deepcopy(state_dict.get('stops', {}))
        self.timestamp = state_dict.get('timestamp')

        # Phase 4: Passenger flow state
        self.passenger_cohorts = {}  # { cohort_id: {origin, destination, group, count, status, etc.} }
        self.stop_queues = {}        # { stop_id: { cohort_id: waiting_count } }
        self.vehicle_passengers = {} # { vehicle_id: { cohort_id: onboard_count } }
        self.metrics = {
            "total_waiting_seconds": 0,
            "passengers_generated": 0,
            "passengers_served": 0,
            "passengers_remaining": 0,
            "capacity_denied_boardings": 0,
            "accessibility_denied_boardings": 0,
            "max_queue_size": 0,
            "max_crowding_ratio": 0.0
        }


    def get_vehicle_state(self, vehicle_id):
        return self.vehicles.get(vehicle_id)

    def update_vehicle_state(self, vehicle_id, payload):
        """Mutates ONLY this simulation state, explicitly leaving LiveState untouched."""
        if vehicle_id not in self.vehicles:
            self.vehicles[vehicle_id] = {}
        self.vehicles[vehicle_id].update(payload)
        return self.vehicles[vehicle_id]

    def update_stop_state(self, stop_id, payload):
        if stop_id not in self.stops:
            self.stops[stop_id] = {}
        self.stops[stop_id].update(payload)
        return self.stops[stop_id]
