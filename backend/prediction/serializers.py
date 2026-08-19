from rest_framework import serializers
from .models import ODDemand

class ODDemandSerializer(serializers.ModelSerializer):
    class Meta:
        model = ODDemand
        fields = '__all__'
