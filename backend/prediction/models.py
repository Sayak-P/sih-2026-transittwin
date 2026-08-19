from django.db import models
from core.models import Stop

class ODDemand(models.Model):
    PASSENGER_GROUP_CHOICES = (
        ('NORMAL', 'Normal'),
        ('MOBILITY_CONSTRAINED', 'Mobility Constrained'),
        ('WHEELCHAIR', 'Wheelchair'),
        ('STEP_FREE_REQUIRED', 'Step-Free Required'),
    )
    origin_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='demand_origins')
    destination_stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name='demand_destinations')
    time_window_start = models.DateTimeField()
    time_window_end = models.DateTimeField()
    expected_passenger_count = models.PositiveIntegerField(default=0)
    passenger_group = models.CharField(max_length=50, choices=PASSENGER_GROUP_CHOICES, default='NORMAL')

    class Meta:
        constraints = [
            models.CheckConstraint(check=~models.Q(origin_stop=models.F('destination_stop')), name='prevent_self_referencing_demand'),
        ]

    def __str__(self):
        return f"{self.origin_stop.name} to {self.destination_stop.name} ({self.expected_passenger_count} {self.passenger_group})"
