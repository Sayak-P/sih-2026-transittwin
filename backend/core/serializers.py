from rest_framework import serializers
from .models import Stop, Edge, Route, RouteEdge, Vehicle, Disruption

class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stop
        fields = '__all__'

class EdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edge
        fields = '__all__'

class RouteEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteEdge
        fields = '__all__'

class RouteSerializer(serializers.ModelSerializer):
    route_edges = RouteEdgeSerializer(many=True, read_only=True)
    
    class Meta:
        model = Route
        fields = '__all__'

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class DisruptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disruption
        fields = '__all__'
