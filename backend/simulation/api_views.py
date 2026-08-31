"""
API views for Events, Ticketing, Schedules, and Scenarios.

All new endpoints follow the existing /api/v1/ convention.
"""

from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response

from simulation.events.models import Event, EVENTS_DB, EventType, EVENT_DEFAULT_INTENSITY, EVENT_LABELS
from simulation.events.event_engine import get_active_events, compute_event_surge_at_stop, get_stop_coords_map
from simulation.passenger.ticketing_simulator import TicketingSimulator
from simulation.schedules.models import ScheduleIntervention, ScheduleInterventionType, INTERVENTION_LABELS
from simulation.schedules.schedule_simulator import ScheduleSimulator
from simulation.scenarios.scenario_engine import ScenarioEngine, ScenarioType, SCENARIO_LABELS
from core.models import Stop


# ──────────────────────────────────────────────────────────
# Event API Views
# ──────────────────────────────────────────────────────────

class EventListView(APIView):
    """
    GET: Returns all events (active and inactive).
    POST: Creates a new event.
    """
    def get(self, request):
        events = [e.to_dict() for e in EVENTS_DB.values()]
        return Response({
            "events": events,
            "total": len(events),
            "event_types": list(EVENT_LABELS.items()),
        })

    def post(self, request):
        data = request.data
        event_id = max(EVENTS_DB.keys(), default=0) + 1

        event_type = data.get("event_type", EventType.CONCERT)
        intensity = float(data.get("intensity", EVENT_DEFAULT_INTENSITY.get(event_type, 1.5)))

        # Parse start_time
        start_time_str = data.get("start_time")
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
            except (ValueError, TypeError):
                start_time = datetime.now()
        else:
            start_time = datetime.now()

        event = Event(
            id=event_id,
            event_type=event_type,
            name=data.get("name", f"{EVENT_LABELS.get(event_type, event_type)} #{event_id}"),
            start_time=start_time,
            duration_hours=float(data.get("duration_hours", 3.0)),
            intensity=intensity,
            location_stop_id=data.get("location_stop_id"),
            radius_km=float(data.get("radius_km", 2.0)),
            description=data.get("description", ""),
            is_active=True,
        )

        EVENTS_DB[event_id] = event
        return Response({"id": event_id, "event": event.to_dict()}, status=201)


class ActiveEventsView(APIView):
    """Returns only currently active events."""
    def get(self, request):
        active = get_active_events()
        return Response({
            "active_events": [e.to_dict() for e in active],
            "count": len(active),
        })


# ──────────────────────────────────────────────────────────
# Ticketing API Views
# ──────────────────────────────────────────────────────────

class TicketingCurrentView(APIView):
    """Returns current simulated ticketing snapshot for all stops."""
    def get(self, request):
        stops = list(Stop.objects.filter(is_active=True).values('id', 'name', 'capacity', 'lat', 'lon'))

        # Get event surges for each stop
        from django.utils import timezone
        now = timezone.now()
        active_events = get_active_events(now)
        stops_coords = get_stop_coords_map()

        event_surges = {}
        for stop in stops:
            result = compute_event_surge_at_stop(
                stop_id=stop["id"],
                stop_lat=stop["lat"],
                stop_lon=stop["lon"],
                current_time=now,
                events=active_events,
                stops_coords=stops_coords,
            )
            event_surges[stop["id"]] = result["total_surge"]

        simulator = TicketingSimulator(seed=42)
        snapshots = simulator.generate_current_snapshot(stops, event_surges=event_surges)

        return Response({
            "timestamp": now.isoformat(),
            "snapshots": [s.to_dict() for s in snapshots],
            "total_stops": len(snapshots),
            "data_source": "SIMULATED_TICKETING",
        })


class TicketingHistoricalView(APIView):
    """Returns historical demand curve for a specific stop."""
    def get(self, request):
        stop_id = request.query_params.get("stop_id")
        hours = int(request.query_params.get("hours", 24))

        if stop_id:
            stop = Stop.objects.filter(id=stop_id, is_active=True).first()
            if not stop:
                return Response({"error": "Stop not found"}, status=404)
            stops_to_query = [stop]
        else:
            stops_to_query = list(Stop.objects.filter(is_active=True)[:5])

        from django.utils import timezone
        now = timezone.now()
        is_weekend = now.weekday() >= 5

        simulator = TicketingSimulator(seed=42)
        results = {}

        for stop in stops_to_query:
            points = simulator.generate_historical_demand(
                stop_id=stop.id,
                stop_name=stop.name,
                stop_capacity=stop.capacity,
                hours=hours,
                is_weekend=is_weekend,
            )
            results[stop.id] = {
                "stop_name": stop.name,
                "is_weekend": is_weekend,
                "demand_curve": [p.to_dict() for p in points],
            }

        return Response({
            "historical_data": results,
            "data_source": "SIMULATED_TICKETING",
        })


# ──────────────────────────────────────────────────────────
# Schedule Simulation API Views
# ──────────────────────────────────────────────────────────

class ScheduleSimulateView(APIView):
    """Runs a single schedule intervention simulation."""
    def post(self, request):
        data = request.data
        intervention_type = data.get("intervention_type")
        parameters = data.get("parameters", {})
        horizon_minutes = int(data.get("horizon_minutes", 30))

        if not intervention_type:
            return Response({"error": "intervention_type is required"}, status=400)

        intervention = ScheduleIntervention(
            intervention_type=intervention_type,
            parameters=parameters,
            label=data.get("label"),
        )

        result = ScheduleSimulator.simulate_single(
            intervention=intervention,
            horizon_minutes=horizon_minutes,
        )

        return Response(result.to_dict())


class ScheduleCompareView(APIView):
    """Compares multiple schedule interventions side-by-side."""
    def post(self, request):
        data = request.data
        interventions_data = data.get("interventions", [])
        horizon_minutes = int(data.get("horizon_minutes", 30))
        profile_name = data.get("objective_profile", "BALANCED")

        if not interventions_data:
            return Response({"error": "At least one intervention is required"}, status=400)

        interventions = []
        for item in interventions_data:
            interventions.append(ScheduleIntervention(
                intervention_type=item.get("intervention_type", ""),
                parameters=item.get("parameters", {}),
                label=item.get("label"),
            ))

        comparison = ScheduleSimulator.compare_interventions(
            interventions=interventions,
            horizon_minutes=horizon_minutes,
            profile_name=profile_name,
        )

        return Response(comparison.to_dict())


# ──────────────────────────────────────────────────────────
# Scenario / What-If API Views
# ──────────────────────────────────────────────────────────

class ScenarioSimulateView(APIView):
    """Runs a what-if scenario simulation."""
    def post(self, request):
        data = request.data
        scenario_type = data.get("scenario_type")
        parameters = data.get("parameters", {})
        horizon_minutes = int(data.get("horizon_minutes", 30))

        if not scenario_type:
            return Response({"error": "scenario_type is required"}, status=400)

        valid_types = [
            ScenarioType.ROAD_BLOCKED, ScenarioType.DEMAND_SURGE,
            ScenarioType.BUS_DELAYED, ScenarioType.EVENT_STARTS,
            ScenarioType.VEHICLE_UNAVAILABLE, ScenarioType.FREQUENCY_CHANGE,
        ]
        if scenario_type not in valid_types:
            return Response({
                "error": f"Invalid scenario_type. Must be one of: {valid_types}"
            }, status=400)

        result = ScenarioEngine.simulate_scenario(
            scenario_type=scenario_type,
            parameters=parameters,
            horizon_minutes=horizon_minutes,
        )

        return Response(result.to_dict())

    def get(self, request):
        """Returns available scenario types and their labels."""
        return Response({
            "scenario_types": [
                {"type": k, "label": v} for k, v in SCENARIO_LABELS.items()
            ],
            "intervention_types": [
                {"type": k, "label": v} for k, v in INTERVENTION_LABELS.items()
            ],
        })
