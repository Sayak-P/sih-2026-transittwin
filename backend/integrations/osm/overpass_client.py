import requests
import json
import logging

logger = logging.getLogger(__name__)

# Bounding box for central Bhubaneswar (Janpath corridor)
BBOX_SOUTH = 20.2600
BBOX_WEST = 85.8100
BBOX_NORTH = 20.3200
BBOX_EAST = 85.8500

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

def fetch_osm_network():
    """
    Fetches major roads and intersections from OSM for the target bounding box.
    """
    query = f"""[out:json][timeout:25];
(
  way["highway"~"primary|secondary|tertiary|trunk|motorway"]({BBOX_SOUTH},{BBOX_WEST},{BBOX_NORTH},{BBOX_EAST});
);
(._;>;);
out body;
"""
    
    logger.info("Fetching OSM data for Bhubaneswar corridor...")
    
    try:
        headers = {
            'User-Agent': 'TransitTwin SIH Demo / 1.0 (contact@transittwin.example.com)'
        }
        response = requests.post(OVERPASS_URL, data={'data': query}, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Successfully fetched {len(data.get('elements', []))} OSM elements.")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch OSM data: {e}")
        return None
