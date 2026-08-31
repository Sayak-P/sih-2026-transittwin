"""
Event Engine — computes demand surge at transit stops from nearby events.

Mathematical Model:
    For each active event e near stop s:
        surge_contribution(e, s) = intensity_e * exp(-d(e, s) / radius_km_e)

    where d(e, s) is the haversine distance in km between the event
    location stop and stop s.

    Total event surge at stop s:
        E_event(s) = 1.0 + sum(surge_contribution(e, s) for e in active_events)

    This multiplier is applied to lambda_base in the M/M/c formula:
        effective_arrival_rate = lambda_base * E_event

Design Notes:
    - Distance-decay uses exponential falloff (realistic spatial influence).
    - Multiple events near the same stop stack additively.
    - Events with no location_stop_id apply globally (e.g., WEEKEND, MARKET_DAY).
"""

import math
from datetime import datetime
from typing import List, Dict, Optional

from simulation.events.models import Event, EVENTS_DB


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two (lat, lon) points in kilometers."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_event_surge_at_stop(
    stop_id: int,
    stop_lat: float,
    stop_lon: float,
    current_time: datetime,
    events: Optional[List[Event]] = None,
    stops_coords: Optional[Dict[int, tuple]] = None,
) -> Dict:
    """
    Computes the total demand surge multiplier at a given stop from nearby active events.

    Args:
        stop_id: The stop to compute surge for.
        stop_lat: Latitude of the stop.
        stop_lon: Longitude of the stop.
        current_time: Current datetime to check event activity.
        events: List of events (defaults to EVENTS_DB if None).
        stops_coords: Dict mapping stop_id -> (lat, lon) for event location lookup.

    Returns:
        Dictionary with:
            - total_surge: float — the overall surge multiplier (>= 1.0)
            - contributing_events: list — individual event contributions
            - event_count: int — number of active events affecting this stop
    """
    if events is None:
        events = list(EVENTS_DB.values())

    if stops_coords is None:
        stops_coords = {}

    contributing_events = []
    total_additional_surge = 0.0

    for event in events:
        if not event.is_happening_at(current_time):
            continue

        # Calculate distance from event to this stop
        if event.location_stop_id is not None:
            # Event is anchored to a specific stop
            event_coords = stops_coords.get(event.location_stop_id)
            if event_coords:
                event_lat, event_lon = event_coords
            elif event.location_stop_id == stop_id:
                # Event is at this stop — distance = 0
                event_lat, event_lon = stop_lat, stop_lon
            else:
                # Unknown event location stop; apply global effect at reduced intensity
                event_lat, event_lon = stop_lat, stop_lon  # distance = 0 fallback
                # But reduce intensity for unknown locations
                distance_km = event.radius_km * 0.5
                surge = event.intensity * math.exp(-distance_km / max(0.1, event.radius_km))
                total_additional_surge += surge
                contributing_events.append({
                    "event_id": event.id,
                    "event_name": event.name,
                    "event_type": event.event_type,
                    "distance_km": round(distance_km, 2),
                    "surge_contribution": round(surge, 3),
                    "data_source": event.data_source,
                })
                continue

            distance_km = haversine_km(stop_lat, stop_lon, event_lat, event_lon)
        else:
            # Global event (e.g., WEEKEND, MARKET_DAY) — affects all stops equally
            distance_km = 0.0

        # Exponential distance-decay: contribution = intensity * exp(-d / radius)
        if event.radius_km > 0:
            surge_contribution = event.intensity * math.exp(-distance_km / event.radius_km)
        else:
            # Zero radius = only affects the exact stop
            surge_contribution = event.intensity if distance_km < 0.01 else 0.0

        if surge_contribution > 0.01:  # Threshold to avoid noise
            total_additional_surge += surge_contribution
            contributing_events.append({
                "event_id": event.id,
                "event_name": event.name,
                "event_type": event.event_type,
                "distance_km": round(distance_km, 2),
                "surge_contribution": round(surge_contribution, 3),
                "data_source": event.data_source,
            })

    # Total surge multiplier (minimum 1.0 = no effect)
    total_surge = 1.0 + total_additional_surge

    return {
        "total_surge": round(total_surge, 3),
        "contributing_events": contributing_events,
        "event_count": len(contributing_events),
    }


def get_active_events(current_time: Optional[datetime] = None) -> List[Event]:
    """Returns all currently active events from the in-memory store."""
    if current_time is None:
        from django.utils import timezone
        current_time = timezone.now()

    return [e for e in EVENTS_DB.values() if e.is_happening_at(current_time)]


def get_stop_coords_map() -> Dict[int, tuple]:
    """Builds a {stop_id: (lat, lon)} mapping from the database."""
    from core.models import Stop
    return {
        s.id: (s.lat, s.lon)
        for s in Stop.objects.filter(is_active=True).only('id', 'lat', 'lon')
    }
