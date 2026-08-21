import math
from core.models import Stop, Edge

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # Radius of earth in meters
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi_1) * math.cos(phi_2) * \
        math.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_geometry_distance(geometry):
    total = 0.0
    for i in range(len(geometry) - 1):
        lon1, lat1 = geometry[i]
        lon2, lat2 = geometry[i+1]
        total += haversine(lat1, lon1, lat2, lon2)
    return total

def build_network_from_osm(osm_data):
    """
    Parses OSM JSON and creates Stop and Edge instances.
    Does NOT save to DB directly; returns lists of objects to be bulk_created.
    """
    elements = osm_data.get('elements', [])
    
    nodes_dict = {}
    ways = []
    
    for el in elements:
        if el['type'] == 'node':
            nodes_dict[el['id']] = el
        elif el['type'] == 'way':
            ways.append(el)
            
    # Find intersections (nodes belonging to >1 way) + way endpoints
    node_usage_count = {}
    for way in ways:
        nodes = way.get('nodes', [])
        for nid in nodes:
            node_usage_count[nid] = node_usage_count.get(nid, 0) + 1
            
    stop_node_ids = set()
    for way in ways:
        nodes = way.get('nodes', [])
        if not nodes:
            continue
        stop_node_ids.add(nodes[0])
        stop_node_ids.add(nodes[-1])
        for nid in nodes:
            if node_usage_count.get(nid, 0) > 1:
                stop_node_ids.add(nid)
                
    # Create Stops
    stops_to_create = {} # node_id -> Stop dict (not model instance yet)
    
    stop_id_counter = 1
    for nid in stop_node_ids:
        if nid in nodes_dict:
            n = nodes_dict[nid]
            stops_to_create[nid] = {
                'id': stop_id_counter,
                'name': f"Intersection {stop_id_counter}",
                'lat': n['lat'],
                'lon': n['lon'],
                'capacity': 100,
                'is_accessible': True,
                'is_active': True,
                'metadata': {'osm_node_id': nid}
            }
            stop_id_counter += 1
            
    # Create Edges by splitting ways at Stops
    edges_to_create = []
    
    for way in ways:
        nodes = way.get('nodes', [])
        if not nodes:
            continue
            
        current_segment_geom = []
        current_source_nid = None
        
        tags = way.get('tags', {})
        oneway = tags.get('oneway', 'no') == 'yes'
        
        for nid in nodes:
            if nid not in nodes_dict:
                continue
                
            n = nodes_dict[nid]
            coord = [n['lon'], n['lat']]
            
            if nid in stop_node_ids:
                if current_source_nid is None:
                    current_source_nid = nid
                    current_segment_geom = [coord]
                else:
                    current_segment_geom.append(coord)
                    
                    # Complete the edge
                    dist = calculate_geometry_distance(current_segment_geom)
                    
                    edges_to_create.append({
                        'source_osm_id': current_source_nid,
                        'target_osm_id': nid,
                        'geometry': current_segment_geom,
                        'distance': dist,
                        'baseline_travel_time': dist / 10.0, # 10 m/s
                        'baseline_cost': dist / 10.0,
                        'metadata': {'osm_way_id': way['id']}
                    })
                    
                    if not oneway:
                        # Add reverse edge
                        edges_to_create.append({
                            'source_osm_id': nid,
                            'target_osm_id': current_source_nid,
                            'geometry': current_segment_geom[::-1],
                            'distance': dist,
                            'baseline_travel_time': dist / 10.0,
                            'baseline_cost': dist / 10.0,
                            'metadata': {'osm_way_id': way['id']}
                        })
                    
                    current_source_nid = nid
                    current_segment_geom = [coord]
            else:
                if current_source_nid is not None:
                    current_segment_geom.append(coord)
                    
    return list(stops_to_create.values()), edges_to_create
