from rest_framework import viewsets
from .models import Stop, Edge, Route, Vehicle, Disruption
from .serializers import (
    StopSerializer, EdgeSerializer, RouteSerializer, 
    VehicleSerializer, DisruptionSerializer
)

class StopViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    filterset_fields = ['is_active', 'is_accessible']

class EdgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Edge.objects.all()
    serializer_class = EdgeSerializer
    filterset_fields = ['is_active', 'is_accessible']

class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filterset_fields = ['is_active', 'transport_type']

class VehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filterset_fields = ['state', 'vehicle_type', 'route']

class DisruptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Disruption.objects.all()
    serializer_class = DisruptionSerializer
    filterset_fields = ['severity', 'is_active', 'disruption_type']
