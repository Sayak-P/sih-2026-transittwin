import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Stop, Edge, Route, RouteEdge, Vehicle
from simulation.models import SimulationScenario, SimulationResult
from prediction.models import ODDemand
from integrations.osm.overpass_client import fetch_osm_network
from integrations.osm.network_builder import build_network_from_osm

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Imports real OSM road network for Bhubaneswar to replace demo grid.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Fetching OSM data for Bhubaneswar corridor...")
        osm_data = fetch_osm_network()
        
        if not osm_data:
            self.stdout.write(self.style.ERROR("Failed to fetch OSM data."))
            return
            
        self.stdout.write("Building network from OSM data...")
        stops_data, edges_data = build_network_from_osm(osm_data)
        
        self.stdout.write(f"Found {len(stops_data)} intersections and {len(edges_data)} road segments.")
        
        # Flush existing network
        self.stdout.write("Flushing existing static graph...")
        Edge.objects.all().delete()
        Stop.objects.all().delete()
        RouteEdge.objects.all().delete()
        Route.objects.all().delete()
        Vehicle.objects.all().delete()
        SimulationScenario.objects.all().delete()
        SimulationResult.objects.all().delete()
        ODDemand.objects.all().delete()
        
        # Create Stops
        self.stdout.write("Seeding Stops (Intersections)...")
        stops_by_osm_id = {}
        for s_data in stops_data:
            stop = Stop.objects.create(
                id=s_data['id'],
                name=s_data['name'],
                lat=s_data['lat'],
                lon=s_data['lon'],
                capacity=s_data['capacity'],
                is_accessible=s_data['is_accessible'],
                is_active=s_data['is_active'],
                metadata=s_data['metadata']
            )
            stops_by_osm_id[s_data['metadata']['osm_node_id']] = stop
            
        # Create Edges
        self.stdout.write("Seeding Edges (Road Segments)...")
        edges_to_create = []
        for e_data in edges_data:
            source = stops_by_osm_id.get(e_data['source_osm_id'])
            target = stops_by_osm_id.get(e_data['target_osm_id'])
            
            if source and target and source != target:
                edges_to_create.append(Edge(
                    source=source,
                    target=target,
                    geometry=e_data['geometry'],
                    distance=e_data['distance'],
                    baseline_travel_time=e_data['baseline_travel_time'],
                    baseline_cost=e_data['baseline_cost'],
                    metadata=e_data.get('metadata', {})
                ))
                
        # Bulk create, ignoring unique constraint violations (e.g., duplicated reverse edges if multiple ways overlap)
        Edge.objects.bulk_create(edges_to_create, ignore_conflicts=True)
        
        # Create dummy route and vehicles just for simulation sake, picking the first 10 edges
        self.stdout.write("Seeding dummy route and vehicles...")
        r = Route.objects.create(name="OSM Route 1", transport_type="BUS")
        all_edges = list(Edge.objects.all()[:20])
        
        for i, edge in enumerate(all_edges):
            RouteEdge.objects.create(route=r, edge=edge, sequence_order=i)
            
        # Add 5 vehicles
        for i in range(1, 6):
            Vehicle.objects.create(
                identifier=f"BUS-OSM-{i}",
                vehicle_type="Bus",
                route=r,
                capacity=80,
                accessible_capacity=2,
                state='ACTIVE'
            )
            
        self.stdout.write(self.style.SUCCESS(f"Successfully imported OSM network! Created {Stop.objects.count()} Stops and {Edge.objects.count()} Edges."))
