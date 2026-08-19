from rest_framework import viewsets
from .models import ODDemand
from .serializers import ODDemandSerializer

class ODDemandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ODDemand.objects.all()
    serializer_class = ODDemandSerializer
    filterset_fields = ['passenger_group']
