from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from core.models import Stop
from prediction.models import ODDemand
from simulation.state.live_state import LiveStateEngine
from django.db.models import Sum

import math

class EarlyWarningView(APIView):
    def get(self, request):
        now = timezone.now()
        horizon = now + timedelta(minutes=30)
        
        # Get live queues and vehicles from LiveStateEngine
        live_state = LiveStateEngine.get_current_state()
        live_state_stops = live_state.get('stops', {})
        live_state_vehicles = live_state.get('vehicles', {})
        
        # Aggregate demand by origin stop
        demands = ODDemand.objects.filter(
            time_window_start__lte=horizon,
            time_window_end__gte=now
        ).values('origin_stop').annotate(
            total_expected=Sum('expected_passenger_count')
        )
        
        demand_dict = {d['origin_stop']: d['total_expected'] for d in demands}
        
        warnings = []
        for stop in Stop.objects.all():
            predicted_arrivals = demand_dict.get(stop.id, 0)
            live_stop_data = live_state_stops.get(str(stop.id), {})
            current_queue = live_stop_data.get('queue_count', 0)
            
            capacity = stop.capacity
            predicted_crowd = current_queue + predicted_arrivals
            
            if capacity > 0:
                ratio = predicted_crowd / capacity
            else:
                ratio = 0.0
                
            if ratio > 1.0:
                severity = "CRITICAL"
            elif ratio > 0.8:
                severity = "WARNING"
            else:
                continue # NORMAL, don't emit warning
                
            
            # Calculate minimal deterministic ETA using active vehicles
            # 1 degree of lat/lon is approx 111,000 meters
            min_eta_minutes = None
            speed_mps = 10.0 # Standard simulation speed
            speed_mpm = speed_mps * 60.0
            
            for v_id, v_data in live_state_vehicles.items():
                if v_data.get('status') in ['ACTIVE', 'DELAYED'] or v_data.get('state') in ['ACTIVE', 'DELAYED']:
                    v_lat = v_data.get('lat')
                    v_lon = v_data.get('lon')
                    if v_lat is not None and v_lon is not None:
                        dist_deg = math.hypot(stop.lat - v_lat, stop.lon - v_lon)
                        dist_meters = dist_deg * 111000.0
                        eta_minutes = dist_meters / speed_mpm
                        if min_eta_minutes is None or eta_minutes < min_eta_minutes:
                            min_eta_minutes = int(eta_minutes)

            warnings.append({
                "stop_id": stop.id,
                "stop_name": stop.name,
                "current_queue": current_queue,
                "predicted_arrivals": predicted_arrivals,
                "available_capacity": max(0, capacity - current_queue),
                "predicted_crowd": predicted_crowd,
                "crowding_ratio": round(ratio, 4),
                "severity": severity,
                "minutes_to_impact": min_eta_minutes,
                "explanation": "Expected arrivals exceed available boarding capacity." if severity == "CRITICAL" else "Stop nearing maximum capacity."
            })
            
        warnings.sort(key=lambda x: (x["severity"] != "CRITICAL", -x["crowding_ratio"]))
        
        return Response({
            "timestamp": now.isoformat(),
            "warnings": warnings
        })
