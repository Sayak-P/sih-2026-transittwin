import random
import logging
import requests
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

# Bounding box for Bhubaneswar roughly
BHUBANESWAR_BBOX = "85.76,20.21,85.88,20.35"

def fetch_traffic_data(edges=None):
    """
    Fetches live traffic data from TomTom API if in LIVE/HYBRID mode.
    Returns mocked data in SIMULATION mode or on failure.
    """
    mode = getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION')
    api_key = getattr(settings, 'TOMTOM_API_KEY', '')
    
    if mode in ['LIVE', 'HYBRID'] and api_key and edges:
        logger.info(f"Fetching REAL live traffic data from TomTom API (Mode: {mode})...")
        results = []
        for edge in edges:
            try:
                if not edge.geometry:
                    continue
                coords = edge.geometry[0]
                lon, lat = coords[0], coords[1]
                
                url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json?point={lat},{lon}&key={api_key}"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    continue
                data = response.json().get("flowSegmentData", {})
                
                if "currentSpeed" in data:
                    results.append({
                        "edge_id": edge.id,
                        "currentSpeed": data["currentSpeed"] / 3.6,
                        "freeFlowSpeed": data.get("freeFlowSpeed", 40.0) / 3.6
                    })
            except Exception as e:
                pass
                
        if results:
            return {"networkSegmentData": results}
        elif mode == 'LIVE':
            logger.error("TomTom API failed in LIVE mode. Returning None to prevent silent fallback.")
            return None
    elif mode == 'LIVE':
        logger.error("LIVE mode requested but TOMTOM_API_KEY is missing. Returning None.")
        return None
    else:
        logger.info(f"Fetching live traffic data from TomTom API (Mocked, Mode: {mode})...")
    
    # Mock fallback
    mocked_response = {
        "networkSegmentData": [
            {
                "way_id": 15000001,
                "currentSpeed": 2.5,
                "freeFlowSpeed": 11.1,
                "confidence": 0.95
            },
            {
                "way_id": 15000002, 
                "currentSpeed": 3.0, 
                "freeFlowSpeed": 11.1,
                "confidence": 0.90
            },
            {
                "way_id": 15000003,
                "currentSpeed": 1.5,
                "freeFlowSpeed": 10.0,
                "confidence": 0.99
            }
        ]
    }
    
    return mocked_response

def fetch_incidents():
    """
    Fetches live incidents from TomTom API if in LIVE/HYBRID mode.
    Returns mocked incident data in SIMULATION mode or on failure.
    """
    mode = getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION')
    api_key = getattr(settings, 'TOMTOM_API_KEY', '')
    
    if mode in ['LIVE', 'HYBRID'] and api_key:
        logger.info(f"Fetching REAL live incidents from TomTom API (Mode: {mode})...")
        try:
            # TomTom Incident Details API
            url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?bbox={BHUBANESWAR_BBOX}&fields={{incidents{{type,geometry{{type,coordinates}},properties{{id,iconCategory,magnitudeOfDelay,startTime}}}}}}&language=en-US&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,14&timeValidityFilter=present&key={api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            if mode == 'LIVE':
                logger.error(f"TomTom API failed in LIVE mode: {e}. Returning None to prevent silent fallback.")
                return None
            else:
                logger.warning(f"TomTom API failed in HYBRID mode: {e}. Falling back to mock data.")
    elif mode == 'LIVE':
        logger.error("LIVE mode requested but TOMTOM_API_KEY is missing. Returning None.")
        return None
    else:
        logger.info(f"Fetching live incidents from TomTom API (Mocked, Mode: {mode})...")
    
    # Mock fallback
    mocked_incidents = [
        {
            "provider": "TOMTOM",
            "provider_incident_id": "tt-inc-9932",
            "incident_type": "ACCIDENT",
            "severity": "HIGH",
            "description": "Accident on NH-16 near Khandagiri",
            "latitude": 20.264,
            "longitude": 85.794,
            "start_time": timezone.now().isoformat(),
            "status": "ACTIVE"
        }
    ]
    
    return mocked_incidents
