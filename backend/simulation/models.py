from django.db import models
from core.models import Disruption

class SimulationScenario(models.Model):
    STATUS_CHOICES = (
        ('INITIALIZED', 'Initialized'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    base_disruption = models.ForeignKey(Disruption, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INITIALIZED')
    snapshot_timestamp = models.DateTimeField(help_text="The timestamp of the live state this scenario cloned")

    def __str__(self):
        return f"Scenario {self.id} - {self.status}"

class SimulationResult(models.Model):
    # Soft reference to intervention candidate to avoid circular dependency
    intervention_id = models.IntegerField()
    is_feasible = models.BooleanField(default=True)
    
    delay_metrics = models.JSONField(default=dict, blank=True)
    waiting_time_metrics = models.JSONField(default=dict, blank=True)
    crowding_metrics = models.JSONField(default=dict, blank=True)
    energy_metrics = models.JSONField(default=dict, blank=True)
    accessibility_metrics = models.JSONField(default=dict, blank=True)
    operational_cost = models.FloatField(default=0.0)
    additional_metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Result for Intervention {self.intervention_id} (Feasible: {self.is_feasible})"
