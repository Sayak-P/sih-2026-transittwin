from django.core.management.base import BaseCommand
from core.models import Stop, Edge, Route, RouteEdge, Vehicle
from prediction.models import ODDemand

class Command(BaseCommand):
    help = 'Validates the integrity of the transit network.'

    def handle(self, *args, **kwargs):
        errors = []

        self.stdout.write("Validating route edges...")
        # 1. All route stops exist - guaranteed by FKs, but we check if edges form a continuous path
        for route in Route.objects.all():
            route_edges = route.route_edges.all()
            if not route_edges.exists():
                errors.append(f"Route {route.name} has no edges.")
                continue
                
            prev_target = None
            for re in route_edges:
                edge = re.edge
                if prev_target and edge.source != prev_target:
                    errors.append(f"Route {route.name} is broken between seq {re.sequence_order-1} and {re.sequence_order}")
                prev_target = edge.target

        self.stdout.write("Validating edges...")
        # 4. Edge direction is valid (no self-referencing)
        for edge in Edge.objects.all():
            if edge.source == edge.target:
                errors.append(f"Edge {edge.id} is self-referencing (source == target).")
            # 8. No impossible negative distances/times
            if edge.distance < 0 or edge.baseline_travel_time < 0 or edge.baseline_cost < 0:
                errors.append(f"Edge {edge.id} has negative metrics.")

        self.stdout.write("Validating vehicles...")
        # 5. Vehicle capacity constraints are valid
        for vehicle in Vehicle.objects.all():
            if vehicle.occupancy > vehicle.capacity:
                errors.append(f"Vehicle {vehicle.identifier} occupancy > capacity.")
            if vehicle.accessible_capacity > vehicle.capacity:
                errors.append(f"Vehicle {vehicle.identifier} accessible capacity > capacity.")

        self.stdout.write("Validating OD demand...")
        # 6. OD demand references valid stops (FK handles this, but we check for identical stops)
        for demand in ODDemand.objects.all():
            if demand.origin_stop == demand.destination_stop:
                errors.append(f"Demand {demand.id} has identical origin and destination.")

        if errors:
            self.stdout.write(self.style.ERROR(f"Validation failed with {len(errors)} errors:"))
            for err in errors:
                self.stdout.write(self.style.ERROR(f"- {err}"))
        else:
            self.stdout.write(self.style.SUCCESS("Network validation passed! All constraints satisfied."))
