from django.db import models
from simulation.models import SimulationScenario

class InterventionCandidate(models.Model):
    TYPE_CHOICES = (
        ('VEHICLE_REROUTING', 'Vehicle Rerouting'),
        ('SCHEDULE_MODIFICATION', 'Schedule Modification'),
        ('SPARE_DEPLOYMENT', 'Spare Vehicle Deployment'),
        ('EMERGENCY_SHUTTLE', 'Emergency Shuttle Deployment'),
        ('FREQUENCY_ADJUSTMENT', 'Service Frequency Adjustment'),
        ('VEHICLE_REDISTRIBUTION', 'Vehicle Redistribution'),
        ('STOP_CLOSURE', 'Temporary Stop Closure'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('EVALUATED', 'Evaluated'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    scenario = models.ForeignKey(SimulationScenario, on_delete=models.CASCADE, related_name='interventions')
    intervention_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    parameters = models.JSONField(default=dict, help_text="Extensible JSON for specific intervention details")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"{self.intervention_type} for Scenario {self.scenario_id}"
