import math
from core.models import Edge

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

def distance_point_to_segment(px, py, x1, y1, x2, y2):
    """
    Calculate distance from point (px, py) to line segment (x1, y1) -> (x2, y2).
    Using simple Euclidean for quick sorting, assuming small distances.
    For more accuracy over large distances, spherical projection is better,
    but this is sufficient for snapping to a local grid.
    """
    l2 = (x1 - x2)**2 + (y1 - y2)**2
    if l2 == 0:
        return haversine(py, px, y1, x1)
    
    # t = dot product to find projection
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
    
    # projection point
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    
    return haversine(py, px, proj_y, proj_x)

def find_nearest_edge(lat: float, lon: float, edges=None):
    """
    Snaps a geographic coordinate to the nearest Edge geometry.
    If edges are not provided, it queries all Edge objects.
    Returns the closest Edge model instance.
    """
    if edges is None:
        edges = list(Edge.objects.all())
        
    if not edges:
        return None
        
    min_dist = float('inf')
    best_edge = None
    
    for edge in edges:
        geom = edge.geometry
        if not geom or len(geom) < 2:
            continue
            
        edge_min = float('inf')
        
        # Check distance to each segment in the edge's LineString
        for i in range(len(geom) - 1):
            lon1, lat1 = geom[i]
            lon2, lat2 = geom[i+1]
            dist = distance_point_to_segment(lon, lat, lon1, lat1, lon2, lat2)
            if dist < edge_min:
                edge_min = dist
                
        if edge_min < min_dist:
            min_dist = edge_min
            best_edge = edge
            
    return best_edge
