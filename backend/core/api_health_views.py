from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from core.models import Edge
from simulation.state.live_state import LiveStateEngine
import datetime
from dateutil.parser import parse as parse_date

class TwinStatusView(APIView):
    """
    Returns the overall health, mode, and staleness of the TransitTwin data streams per provider.
    """
    def get(self, request, *args, **kwargs):
        mode = getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION')
        now = timezone.now()
        
        providers = {
            "tomtom": {"status": "OFFLINE", "last_update": None},
            "crut": {"status": "OFFLINE", "last_update": None},
            "simulation": {"status": "OFFLINE", "last_update": None},
        }
        
        # 1. Check TOMTOM (from Edges)
        try:
            latest_tomtom = Edge.objects.filter(data_source='TOMTOM').latest('last_updated_at')
            if latest_tomtom and latest_tomtom.last_updated_at:
                providers["tomtom"]["last_update"] = latest_tomtom.last_updated_at.isoformat()
                age = now - latest_tomtom.last_updated_at
                if age > datetime.timedelta(minutes=5):
                    providers["tomtom"]["status"] = "STALE"
                else:
                    providers["tomtom"]["status"] = "ONLINE"
        except Edge.DoesNotExist:
            pass
            
        # 2. Check Vehicles (CRUT and SIMULATION)
        state = LiveStateEngine.get_current_state()
        vehicles = state.get("vehicles", {})
        
        latest_crut_ts = None
        latest_sim_ts = None
        
        for v_id, v in vehicles.items():
            ds = v.get("data_source", "SIMULATION")
            ts_str = v.get("received_at") or v.get("timestamp")
            if ts_str:
                try:
                    ts = parse_date(ts_str)
                    if ds == "CRUT":
                        if not latest_crut_ts or ts > latest_crut_ts:
                            latest_crut_ts = ts
                    elif ds == "SIMULATION":
                        if not latest_sim_ts or ts > latest_sim_ts:
                            latest_sim_ts = ts
                except Exception:
                    pass
                    
        if latest_crut_ts:
            providers["crut"]["last_update"] = latest_crut_ts.isoformat()
            if now - latest_crut_ts > datetime.timedelta(minutes=1):
                providers["crut"]["status"] = "STALE"
            else:
                providers["crut"]["status"] = "ONLINE"
                
        if mode == 'LIVE':
            providers["simulation"]["status"] = "DISABLED"
        else:
            if latest_sim_ts:
                providers["simulation"]["last_update"] = latest_sim_ts.isoformat()
                if now - latest_sim_ts > datetime.timedelta(minutes=1):
                    providers["simulation"]["status"] = "STALE"
                else:
                    providers["simulation"]["status"] = "ACTIVE"

        traffic_status = providers["tomtom"]["status"]
        if traffic_status == "OFFLINE" and providers["simulation"]["status"] == "ONLINE":
             traffic_status = "SIMULATED"
        traffic_source = "TOMTOM" if providers["tomtom"]["status"] != "OFFLINE" else ("SIMULATION" if providers["simulation"]["status"] != "OFFLINE" else "OFFLINE")

        return Response({
            "mode": mode,
            "traffic_source": traffic_source,
            "traffic_status": traffic_status,
            "providers": providers
        })
