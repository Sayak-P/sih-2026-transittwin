from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Stop, Edge, Route, RouteEdge, Vehicle, Disruption
from prediction.models import ODDemand

class Command(BaseCommand):
    help = 'Seeds a deterministic small campus/local bus network for TransitTwin.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Clearing existing network data..."))
        
        # Clear data in reverse dependency order
        ODDemand.objects.all().delete()
        Disruption.objects.all().delete()
        Vehicle.objects.all().delete()
        RouteEdge.objects.all().delete()
        Route.objects.all().delete()
        Edge.objects.all().delete()
        Stop.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Creating 20 Stops..."))
        
        # Coordinates roughly around a fictional campus
        base_lon, base_lat = 77.1025, 28.7041 # Example: Delhi coordinates roughly
        
        stops = []
        for i in range(1, 21):
            lon = base_lon + (i * 0.001) if i <= 10 else base_lon - ((i - 10) * 0.001)
            lat = base_lat + (i * 0.001 * (1 if i % 2 == 0 else -1))
            is_accessible = i % 5 != 0 # Every 5th stop is NOT accessible
            
            stop = Stop.objects.create(
                name=f"Campus Stop {i}",
                lat=lat,
                lon=lon,
                is_accessible=is_accessible,
                capacity=100 + (i * 10),
                is_active=True
            )
            stops.append(stop)

        self.stdout.write(self.style.SUCCESS("Creating Edges to form a connected network..."))
        
        edges = []
        # Create a loop connecting 1->2->3...->20->1
        for i in range(len(stops)):
            source = stops[i]
            target = stops[(i + 1) % len(stops)]
            
            # Forward edge
            edge_fwd = Edge.objects.create(
                source=source,
                target=target,
                geometry=[[source.lon, source.lat], [target.lon, target.lat]],
                distance=300.0,
                baseline_travel_time=120.0,
                baseline_cost=10.0,
                is_accessible=source.is_accessible and target.is_accessible
            )
            edges.append(edge_fwd)
            
            # Reverse edge
            edge_rev = Edge.objects.create(
                source=target,
                target=source,
                geometry=[[target.lon, target.lat], [source.lon, source.lat]],
                distance=300.0,
                baseline_travel_time=120.0,
                baseline_cost=10.0,
                is_accessible=source.is_accessible and target.is_accessible
            )
            edges.append(edge_rev)

        # Add cross connections for realism
        cross_pairs = [(0, 10), (5, 15), (2, 18)]
        for s1_idx, s2_idx in cross_pairs:
            source = stops[s1_idx]
            target = stops[s2_idx]
            Edge.objects.create(
                source=source,
                target=target,
                geometry=[[source.lon, source.lat], [target.lon, target.lat]],
                distance=800.0,
                baseline_travel_time=300.0,
                baseline_cost=25.0,
                is_accessible=True
            )
            Edge.objects.create(
                source=target,
                target=source,
                geometry=[[target.lon, target.lat], [source.lon, source.lat]],
                distance=800.0,
                baseline_travel_time=300.0,
                baseline_cost=25.0,
                is_accessible=True
            )

        self.stdout.write(self.style.SUCCESS("Creating 3 Routes..."))
        
        # Route 1: Outer Loop Clockwise
        r1 = Route.objects.create(name="Campus Outer Loop (CW)", transport_type="BUS")
        # Route 2: Outer Loop Counter-Clockwise
        r2 = Route.objects.create(name="Campus Outer Loop (CCW)", transport_type="BUS")
        # Route 3: Cross Campus Express
        r3 = Route.objects.create(name="Cross Campus Express", transport_type="BUS")

        # Assign edges to Route 1
        seq = 1
        for i in range(0, len(stops) * 2, 2): # Pick the forward edges
            RouteEdge.objects.create(route=r1, edge=edges[i], sequence_order=seq)
            seq += 1
            
        # Assign edges to Route 2
        seq = 1
        for i in range(1, len(stops) * 2, 2): # Pick the reverse edges
            RouteEdge.objects.create(route=r2, edge=edges[i], sequence_order=seq)
            seq += 1

        self.stdout.write(self.style.SUCCESS("Creating 6 Vehicles..."))
        for i in range(1, 7):
            route = r1 if i % 2 != 0 else r2
            start_stop = route.route_edges.first().edge.source if route.route_edges.exists() else None
            Vehicle.objects.create(
                identifier=f"BUS-{1000 + i}",
                vehicle_type="Standard Bus",
                route=route,
                lat=start_stop.lat if start_stop else None,
                lon=start_stop.lon if start_stop else None,
                occupancy=0,
                capacity=60,
                accessible_capacity=2,
                state="ACTIVE"
            )

        self.stdout.write(self.style.SUCCESS("Creating OD Demand Samples..."))
        now = timezone.now()
        ODDemand.objects.create(
            origin_stop=stops[0],
            destination_stop=stops[10],
            time_window_start=now,
            time_window_end=now + timedelta(hours=1),
            expected_passenger_count=45,
            passenger_group="NORMAL"
        )
        ODDemand.objects.create(
            origin_stop=stops[5],
            destination_stop=stops[15],
            time_window_start=now,
            time_window_end=now + timedelta(hours=1),
            expected_passenger_count=2,
            passenger_group="WHEELCHAIR"
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded the network!"))
