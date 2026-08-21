import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from simulation.state.live_state import LiveStateEngine
from core.models import Vehicle

def process_vehicle_telemetry(payload):
    """
    Validates and processes incoming vehicle telemetry.
    Expected payload:
    {
      "vehicle_id": "BUS-01",
      "lat": 20.29,
      "lon": 85.82,
      "speed_kmh": 22.4,
      "occupancy": 31,
      "timestamp": "2026-08-18T12:00:00Z"
    }
    """
    vehicle_id = payload.get('vehicle_id')
    if not vehicle_id:
        return False, "Missing vehicle_id"

    # 1. Validation
    if payload.get('speed_kmh', 0) < 0:
        return False, "Speed cannot be negative"
    
    occupancy = payload.get('occupancy', 0)
    if occupancy < 0:
        return False, "Occupancy cannot be negative"
        
    # Default data_source if not provided
    if 'data_source' not in payload:
        payload['data_source'] = 'SIMULATION'

    if 'provider' not in payload:
        payload['provider'] = 'INTERNAL' if payload['data_source'] == 'SIMULATION' else 'CHALO'

    # Optional: check DB if vehicle exists (skipped for speed if cached, but we can do a quick check)
    original_id = vehicle_id.replace("SIM-", "") if vehicle_id.startswith("SIM-") else vehicle_id
    if not Vehicle.objects.filter(identifier=original_id).exists():
        return False, "Unknown vehicle ID"

    # 2. Update Live State
    success, new_state = LiveStateEngine.update_vehicle_state(vehicle_id, payload)
    
    if not success:
        return False, new_state # 'new_state' contains error message here

    # 3. Publish WebSocket Event
    channel_layer = get_channel_layer()
    event_data = {
        "type": "broadcast_event",
        "event": "vehicle.updated",
        "state_version": new_state['state_version'],
        "vehicle_id": vehicle_id,
        "lat": payload.get('lat'),
        "lon": payload.get('lon'),
        "speed_kmh": payload.get('speed_kmh'),
        "occupancy": occupancy,
        "status": payload.get('status', 'ACTIVE'),
        "data_source": new_state.get('data_source'),
        "provider": new_state.get('provider'),
        "last_updated_at": payload.get('timestamp'),
        "received_at": new_state.get('received_at')
    }
    
    async_to_sync(channel_layer.group_send)(
        "twin_events",
        event_data
    )

    return True, new_state
