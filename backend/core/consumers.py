import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TwinEventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "twin_events"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from room group
    async def broadcast_event(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))
