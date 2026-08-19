from django.core.cache import cache
from django.utils import timezone
import copy

class LiveStateEngine:
    VERSION_KEY = "live_state:version"
    VEHICLES_KEY = "live_state:vehicles"
    STOPS_KEY = "live_state:stops"

    @classmethod
    def get_state_version(cls):
        return cache.get(cls.VERSION_KEY, 0)

    @classmethod
    def _increment_version(cls):
        # LocMemCache / Redis incr handles atomicity
        try:
            return cache.incr(cls.VERSION_KEY)
        except ValueError:
            cache.set(cls.VERSION_KEY, 1)
            return 1

    @classmethod
    def get_current_state(cls):
        return {
            "version": cls.get_state_version(),
            "vehicles": cache.get(cls.VEHICLES_KEY, {}),
            "stops": cache.get(cls.STOPS_KEY, {}),
            "timestamp": timezone.now().isoformat()
        }

    @classmethod
    def get_vehicle_state(cls, vehicle_id):
        vehicles = cache.get(cls.VEHICLES_KEY, {})
        return vehicles.get(vehicle_id)

    @classmethod
    def update_vehicle_state(cls, vehicle_id, payload):
        vehicles = cache.get(cls.VEHICLES_KEY, {})
        
        current = vehicles.get(vehicle_id)
        # Reject stale updates
        if current and payload.get('timestamp') and current.get('timestamp'):
            if payload['timestamp'] < current['timestamp']:
                return False, "Stale update rejected"

        # Update
        new_state = copy.deepcopy(current) if current else {}
        new_state.update(payload)
        new_state['state_version'] = cls._increment_version()
        
        vehicles[vehicle_id] = new_state
        cache.set(cls.VEHICLES_KEY, vehicles)
        return True, new_state

    @classmethod
    def update_stop_state(cls, stop_id, payload):
        stops = cache.get(cls.STOPS_KEY, {})
        
        current = stops.get(stop_id)
        if current and payload.get('timestamp') and current.get('timestamp'):
            if payload['timestamp'] < current['timestamp']:
                return False, "Stale update rejected"

        new_state = copy.deepcopy(current) if current else {}
        new_state.update(payload)
        new_state['state_version'] = cls._increment_version()
        
        stops[stop_id] = new_state
        cache.set(cls.STOPS_KEY, stops)
        return True, new_state
