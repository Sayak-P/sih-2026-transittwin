from django.db import models
from django.core.validators import MinValueValidator

DATA_SOURCE_CHOICES = (
    ('TOMTOM', 'TomTom API'),
    ('CRUT', 'CRUT Telemetry'),
    ('SIMULATION', 'Simulation Engine'),
    ('ESTIMATED', 'Estimated/Fallback'),
)

class Stop(models.Model):
    name = models.CharField(max_length=255)
    lat = models.FloatField(default=0.0)
    lon = models.FloatField(default=0.0)
    is_accessible = models.BooleanField(default=True)
    capacity = models.PositiveIntegerField(help_text="Maximum passenger queue capacity")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name

class Edge(models.Model):
    source = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='outgoing_edges')
    target = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='incoming_edges')
    geometry = models.JSONField(default=list, help_text="List of [lon, lat] coordinates representing a LineString")
    distance = models.FloatField(validators=[MinValueValidator(0.0)], help_text="Distance in meters")
    baseline_travel_time = models.FloatField(validators=[MinValueValidator(0.0)], help_text="Time in seconds")
    baseline_cost = models.FloatField(validators=[MinValueValidator(0.0)], default=0.0)
    current_traffic_speed = models.FloatField(default=10.0, help_text="Current live traffic speed in m/s")
    free_flow_speed = models.FloatField(default=10.0, help_text="Free flow speed in m/s")
    data_source = models.CharField(max_length=20, choices=DATA_SOURCE_CHOICES, default='ESTIMATED')
    last_updated_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(auto_now=True)
    is_accessible = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'target'], name='unique_edge_direction'),
            models.CheckConstraint(check=~models.Q(source=models.F('target')), name='prevent_self_referencing_edge'),
        ]

    def __str__(self):
        return f"{self.source.name} -> {self.target.name}"

class Route(models.Model):
    TRANSPORT_CHOICES = (
        ('BUS', 'Bus'),
        ('METRO', 'Metro'),
        ('TRAM', 'Tram'),
    )
    name = models.CharField(max_length=255, unique=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES, default='BUS')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class RouteEdge(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='route_edges')
    edge = models.ForeignKey(Edge, on_delete=models.CASCADE, related_name='used_by_routes')
    sequence_order = models.PositiveIntegerField()

    class Meta:
        ordering = ['sequence_order']
        constraints = [
            models.UniqueConstraint(fields=['route', 'edge'], name='unique_route_edge'),
            models.UniqueConstraint(fields=['route', 'sequence_order'], name='unique_route_order')
        ]

class Vehicle(models.Model):
    STATE_CHOICES = (
        ('ACTIVE', 'Active'),
        ('DELAYED', 'Delayed'),
        ('BROKEN', 'Broken'),
        ('INACTIVE', 'Inactive'),
    )
    identifier = models.CharField(max_length=100, unique=True)
    vehicle_type = models.CharField(max_length=50)
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    occupancy = models.PositiveIntegerField(default=0)
    capacity = models.PositiveIntegerField()
    accessible_capacity = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='INACTIVE')
    energy_rate_kwh_per_km = models.FloatField(default=1.2, help_text="Energy consumption per km")

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(occupancy__lte=models.F('capacity')), name='occupancy_lte_capacity'),
            models.CheckConstraint(check=models.Q(accessible_capacity__lte=models.F('capacity')), name='accessible_capacity_lte_capacity')
        ]

    def __str__(self):
        return self.identifier

class Disruption(models.Model):
    SEVERITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )
    SOURCE_CHOICES = (
        ('OPERATOR', 'Operator'),
        ('EXTERNAL', 'External'),
        ('SIMULATION', 'Simulation'),
    )
    disruption_type = models.CharField(max_length=100)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='OPERATOR')
    data_source = models.CharField(max_length=20, choices=DATA_SOURCE_CHOICES, default='OPERATOR')
    provider_incident_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    affected_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, null=True, blank=True)
    affected_edge = models.ForeignKey(Edge, on_delete=models.CASCADE, null=True, blank=True)
    start_time = models.DateTimeField()
    expected_end_time = models.DateTimeField(null=True, blank=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    received_at = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.disruption_type} ({self.severity})"

class AuditLog(models.Model):
    operator_identifier = models.CharField(max_length=255)
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    scenario_id = models.CharField(max_length=255, null=True, blank=True)
    candidate_id = models.CharField(max_length=255, null=True, blank=True)
    previous_state_reference = models.CharField(max_length=255, null=True, blank=True)
    resulting_state_reference = models.CharField(max_length=255, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.operator_identifier} - {self.action} at {self.timestamp}"
