from django.urls import path
from core.consumers import TwinEventConsumer

websocket_urlpatterns = [
    path('ws/twin/', TwinEventConsumer.as_asgi()),
]
