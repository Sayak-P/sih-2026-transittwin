import requests
import logging
import time

logger = logging.getLogger(__name__)

# Bounding box for Bhubaneswar metro area (covers main city + extends towards Cuttack)
BBOX_SOUTH = 20.2000
BBOX_WEST = 85.7500
BBOX_NORTH = 20.3800
BBOX_EAST = 85.9200

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# Known Mo Bus route mappings (OSM ref -> display name)
# These help us identify and label routes even if OSM tagging is inconsistent
MO_BUS_KNOWN_ROUTES = {
    "9": "Route 9 — Railway Station to Patia",
    "10": "Route 10 — Airport to Cuttack",
    "11": "Route 11 — Railway Station to Nandankanan",
    "16": "Route 16 — Railway Station to Cuttack (NH)",
    "19": "Route 19 — AIIMS to OMP Square",
    "20": "Route 20 — Railway Station to Khordha",
    "21": "Route 21 — Railway Station to Khordha (Alt)",
    "23": "Route 23 — Railway Station to SUM Hospital",
    "32": "Route 32 — Baramunda to Lingaraj Temple",
    "50": "Route 50 — Bhubaneswar to Puri",
    "51": "Route 51 — Baramunda to Puri",
    "70": "Route 70 — Railway Station to Konark",
}

# Hardcoded real Mo Bus routes with actual stop coordinates
# This serves as fallback when OSM data is incomplete
FALLBACK_ROUTES = [
    {
        "name": "Mo Bus Route 9",
        "ref": "9",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "AG Square", "lat": 20.2820, "lon": 85.8399},
            {"name": "Vani Vihar", "lat": 20.2897, "lon": 85.8398},
            {"name": "Acharya Vihar", "lat": 20.2960, "lon": 85.8380},
            {"name": "Jaydev Vihar Square", "lat": 20.2982, "lon": 85.8256},
            {"name": "Kalinga Hospital", "lat": 20.3010, "lon": 85.8173},
            {"name": "Patia Square", "lat": 20.3120, "lon": 85.8162},
            {"name": "Infocity", "lat": 20.3222, "lon": 85.8170},
        ],
        "num_vehicles": 5,
    },
    {
        "name": "Mo Bus Route 10",
        "ref": "10",
        "transport_type": "BUS",
        "stops": [
            {"name": "Biju Patnaik Airport", "lat": 20.2544, "lon": 85.8175},
            {"name": "Khandagiri Square", "lat": 20.2550, "lon": 85.7875},
            {"name": "Baramunda ISBT", "lat": 20.2665, "lon": 85.7979},
            {"name": "Sishu Bhawan Square", "lat": 20.2736, "lon": 85.8310},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "Ram Mandir", "lat": 20.2880, "lon": 85.8400},
            {"name": "Jaydev Vihar Square", "lat": 20.2982, "lon": 85.8256},
            {"name": "Nandankanan Road", "lat": 20.3260, "lon": 85.8240},
            {"name": "Nandankanan Zoo", "lat": 20.3950, "lon": 85.8240},
        ],
        "num_vehicles": 4,
    },
    {
        "name": "Mo Bus Route 11",
        "ref": "11",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "AG Square", "lat": 20.2820, "lon": 85.8399},
            {"name": "KIIT Square", "lat": 20.3536, "lon": 85.8209},
            {"name": "Patia Square", "lat": 20.3120, "lon": 85.8162},
            {"name": "Chandaka", "lat": 20.3550, "lon": 85.7900},
            {"name": "Nandankanan Zoo", "lat": 20.3950, "lon": 85.8240},
        ],
        "num_vehicles": 4,
    },
    {
        "name": "Mo Bus Route 16",
        "ref": "16",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Vani Vihar", "lat": 20.2897, "lon": 85.8398},
            {"name": "Acharya Vihar", "lat": 20.2960, "lon": 85.8380},
            {"name": "Kalinga Nagar", "lat": 20.3100, "lon": 85.8400},
            {"name": "Phulnakhara", "lat": 20.3600, "lon": 85.8600},
            {"name": "Cuttack Badambadi", "lat": 20.4625, "lon": 85.8830},
            {"name": "Biju Patnaik Park Cuttack", "lat": 20.4700, "lon": 85.8900},
        ],
        "num_vehicles": 5,
    },
    {
        "name": "Mo Bus Route 19",
        "ref": "19",
        "transport_type": "BUS",
        "stops": [
            {"name": "AIIMS Bhubaneswar", "lat": 20.2395, "lon": 85.7743},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "Vani Vihar", "lat": 20.2897, "lon": 85.8398},
            {"name": "Rasulgarh", "lat": 20.2950, "lon": 85.8610},
            {"name": "Phulnakhara", "lat": 20.3600, "lon": 85.8600},
            {"name": "OMP Square Cuttack", "lat": 20.4600, "lon": 85.8800},
        ],
        "num_vehicles": 4,
    },
    {
        "name": "Mo Bus Route 20",
        "ref": "20",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Pokhariput", "lat": 20.2380, "lon": 85.7920},
            {"name": "Khandagiri", "lat": 20.2550, "lon": 85.7875},
            {"name": "Jatni", "lat": 20.1660, "lon": 85.7144},
            {"name": "Khordha Bus Stand", "lat": 20.1820, "lon": 85.6210},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 23",
        "ref": "23",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "AG Square", "lat": 20.2820, "lon": 85.8399},
            {"name": "Damana Square", "lat": 20.3000, "lon": 85.8360},
            {"name": "KIIT University", "lat": 20.3536, "lon": 85.8209},
            {"name": "SUM Hospital", "lat": 20.3630, "lon": 85.8207},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 32",
        "ref": "32",
        "transport_type": "BUS",
        "stops": [
            {"name": "Baramunda ISBT", "lat": 20.2665, "lon": 85.7979},
            {"name": "Sishu Bhawan Square", "lat": 20.2736, "lon": 85.8310},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "Capital Hospital", "lat": 20.2700, "lon": 85.8415},
            {"name": "Lingaraj Temple", "lat": 20.2385, "lon": 85.8335},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 50",
        "ref": "50",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Biju Patnaik Airport", "lat": 20.2544, "lon": 85.8175},
            {"name": "Pipili", "lat": 20.1170, "lon": 85.8310},
            {"name": "Nimapara", "lat": 20.0540, "lon": 85.9700},
            {"name": "Puri Bus Stand", "lat": 19.8134, "lon": 85.8312},
        ],
        "num_vehicles": 4,
    },
    {
        "name": "Mo Bus Route 70",
        "ref": "70",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Pipili", "lat": 20.1170, "lon": 85.8310},
            {"name": "Kakatpur", "lat": 19.9830, "lon": 86.0470},
            {"name": "Konark Sun Temple", "lat": 19.8876, "lon": 86.0945},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 15",
        "ref": "15",
        "transport_type": "BUS",
        "stops": [
            {"name": "Baramunda ISBT", "lat": 20.2665, "lon": 85.7979},
            {"name": "Khandagiri Square", "lat": 20.2550, "lon": 85.7875},
            {"name": "Biju Patnaik Airport", "lat": 20.2544, "lon": 85.8175},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "AG Square", "lat": 20.2820, "lon": 85.8399},
            {"name": "Rasulgarh", "lat": 20.2950, "lon": 85.8610},
            {"name": "Mancheswar", "lat": 20.3100, "lon": 85.8700},
        ],
        "num_vehicles": 4,
    },
    {
        "name": "Mo Bus Route 25",
        "ref": "25",
        "transport_type": "BUS",
        "stops": [
            {"name": "Baramunda ISBT", "lat": 20.2665, "lon": 85.7979},
            {"name": "Sishu Bhawan Square", "lat": 20.2736, "lon": 85.8310},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "Vani Vihar", "lat": 20.2897, "lon": 85.8398},
            {"name": "Acharya Vihar", "lat": 20.2960, "lon": 85.8380},
            {"name": "Jaydev Vihar Square", "lat": 20.2982, "lon": 85.8256},
            {"name": "Nayapalli", "lat": 20.2990, "lon": 85.8100},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 33",
        "ref": "33",
        "transport_type": "BUS",
        "stops": [
            {"name": "Lingaraj Temple", "lat": 20.2385, "lon": 85.8335},
            {"name": "Capital Hospital", "lat": 20.2700, "lon": 85.8415},
            {"name": "Rajmahal Square", "lat": 20.2764, "lon": 85.8405},
            {"name": "AG Square", "lat": 20.2820, "lon": 85.8399},
            {"name": "Vani Vihar", "lat": 20.2897, "lon": 85.8398},
            {"name": "Saheed Nagar", "lat": 20.2930, "lon": 85.8470},
            {"name": "Rasulgarh", "lat": 20.2950, "lon": 85.8610},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 7",
        "ref": "7",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Sishu Bhawan Square", "lat": 20.2736, "lon": 85.8310},
            {"name": "Baramunda ISBT", "lat": 20.2665, "lon": 85.7979},
            {"name": "AIIMS Bhubaneswar", "lat": 20.2395, "lon": 85.7743},
        ],
        "num_vehicles": 3,
    },
    {
        "name": "Mo Bus Route 14",
        "ref": "14",
        "transport_type": "BUS",
        "stops": [
            {"name": "Bhubaneswar Railway Station", "lat": 20.2707, "lon": 85.8430},
            {"name": "Master Canteen Square", "lat": 20.2725, "lon": 85.8408},
            {"name": "Unit 9 (PMG)", "lat": 20.2603, "lon": 85.8393},
            {"name": "Kalpana Square", "lat": 20.2500, "lon": 85.8040},
            {"name": "Pokhariput", "lat": 20.2380, "lon": 85.7920},
            {"name": "Bhubaneswar Club", "lat": 20.2260, "lon": 85.8200},
            {"name": "Old Town", "lat": 20.2350, "lon": 85.8360},
        ],
        "num_vehicles": 3,
    },
]


def fetch_osm_bus_routes():
    """
    Attempts to fetch bus route relations from OSM for Bhubaneswar.
    Falls back to hardcoded route data if OSM query fails or returns sparse data.
    """
    query = f"""[out:json][timeout:60];
(
  relation["route"="bus"]({BBOX_SOUTH},{BBOX_WEST},{BBOX_NORTH},{BBOX_EAST});
);
(._;>;);
out body;
"""
    
    logger.info("Fetching OSM bus route data for Bhubaneswar...")
    
    try:
        headers = {
            'User-Agent': 'TransitTwin SIH Demo / 1.0 (contact@transittwin.example.com)'
        }
        response = requests.post(OVERPASS_URL, data={'data': query}, headers=headers, timeout=90)
        response.raise_for_status()
        data = response.json()
        
        elements = data.get('elements', [])
        relations = [e for e in elements if e['type'] == 'relation']
        
        logger.info(f"Fetched {len(relations)} bus route relations, {len(elements)} total elements from OSM.")
        
        if len(relations) >= 5:
            return data, 'OSM'
        else:
            logger.warning(f"Only {len(relations)} bus routes found in OSM. Falling back to hardcoded routes.")
            return FALLBACK_ROUTES, 'FALLBACK'
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch OSM bus routes: {e}. Using fallback routes.")
        return FALLBACK_ROUTES, 'FALLBACK'


def fetch_road_geometry_between_stops(stops_coords):
    """
    Fetches the actual road geometry between a list of stop coordinates
    using OSRM (Open Source Routing Machine) public demo server.
    Returns a list of [lon, lat] coordinates forming the full road path.
    """
    if len(stops_coords) < 2:
        return [[s['lon'], s['lat']] for s in stops_coords]
    
    # Build OSRM coordinate string
    coords_str = ";".join([f"{s['lon']},{s['lat']}" for s in stops_coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') == 'Ok' and data.get('routes'):
            geometry = data['routes'][0]['geometry']['coordinates']  # [[lon, lat], ...]
            return geometry
        else:
            logger.warning(f"OSRM returned no route. Using straight lines.")
            return [[s['lon'], s['lat']] for s in stops_coords]
            
    except Exception as e:
        logger.warning(f"OSRM request failed: {e}. Using straight lines.")
        return [[s['lon'], s['lat']] for s in stops_coords]
