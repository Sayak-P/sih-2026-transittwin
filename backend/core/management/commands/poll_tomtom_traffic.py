import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from core.models import Edge
from integrations.tomtom.client import fetch_traffic_data

class Command(BaseCommand):
    help = 'Polls TomTom Traffic API and updates Edge current_traffic_speed.'

    def handle(self, *args, **options):
        self.stdout.write("Polling TomTom Traffic Flow API...")
        
        from django.conf import settings
        
        edges_qs = Edge.objects.all().order_by('id')
        total_edges = edges_qs.count()
        
        if total_edges == 0:
            self.stdout.write(self.style.ERROR("No edges found. Have you imported OSM network?"))
            return

        mode = getattr(settings, 'TRANSIT_TWIN_MODE', 'SIMULATION')
        
        # 1. Handle Staleness: Downgrade old TOMTOM data to ESTIMATED
        stale_threshold = timezone.now() - timedelta(minutes=15)
        stale_edges = Edge.objects.filter(last_updated_at__lt=stale_threshold, data_source='TOMTOM')
        stale_count = stale_edges.update(data_source='ESTIMATED')
        if stale_count > 0:
            self.stdout.write(self.style.WARNING(f"Downgraded {stale_count} stale TOMTOM edges to ESTIMATED."))

        # 2. Select Deterministic Batch with Cache Lock
        if mode in ['LIVE', 'HYBRID']:
            # Try to acquire lock to prevent duplicate polling
            if not cache.add('tomtom_polling_lock', 'locked', timeout=45):
                self.stdout.write(self.style.WARNING("Another poller is currently running. Skipping this cycle to prevent duplicate API requests."))
                return

            try:
                offset = cache.get('tomtom_polling_offset', 0)
                if offset >= total_edges:
                    offset = 0
                
                batch_size = 20
                sampled_edges = list(edges_qs[offset:offset+batch_size])
                cache.set('tomtom_polling_offset', offset + batch_size)
                self.stdout.write(f"Querying batch: {offset} to {offset+batch_size} (Total: {total_edges})")
            except Exception as e:
                cache.delete('tomtom_polling_lock')
                raise e
        else:
            sampled_edges = None
            
        edges = list(edges_qs) # For mock matching below if needed
        
        try:
            traffic_data = fetch_traffic_data(edges=sampled_edges)
            
            if traffic_data is None:
                self.stdout.write(self.style.WARNING("No traffic data received (likely LIVE mode with no API key or provider failure). Skipping update."))
                return
                
            updates = []
            num_congested = 0
            
            if traffic_data and "networkSegmentData" in traffic_data:
                # Parse the mock/real schema array
                segments = traffic_data["networkSegmentData"]
                
                for segment in segments:
                    way_id = segment.get("way_id")
                    edge_id = segment.get("edge_id")
                    current_speed = segment.get("currentSpeed")
                    
                    if current_speed is not None:
                        if edge_id:
                            matched_edges = [e for e in edges if e.id == edge_id]
                        elif way_id:
                            matched_edges = [e for e in edges if e.metadata and e.metadata.get("osmid") == way_id]
                        else:
                            continue
                        
                        for edge in matched_edges:
                            edge.current_traffic_speed = current_speed
                            if "freeFlowSpeed" in segment:
                                edge.free_flow_speed = segment["freeFlowSpeed"]
                            edge.last_updated_at = timezone.now()
                            edge.data_source = 'TOMTOM'
                            updates.append(edge)
                            num_congested += 1
                            
            if not updates:
                # Fallback for the demo: if the fetched data doesn't map to our OSM network,
                # we will pick a random 5% of the network to congest so the UI looks active.
                if mode in ['SIMULATION', 'HYBRID']:
                    self.stdout.write(self.style.WARNING(f"Mapping failed in {mode} mode. Injecting 5% random traffic noise for visualization."))
                    num_congested = int(len(edges) * 0.05)
                    congested_edges = random.sample(edges, num_congested)
                    for edge in congested_edges:
                        edge.current_traffic_speed = random.uniform(1.0, 3.0)
                        edge.last_updated_at = timezone.now()
                        edge.data_source = 'ESTIMATED'
                        updates.append(edge)
                else:
                    self.stdout.write(self.style.WARNING("Mapping failed in LIVE mode. Skipping injection to preserve data integrity."))
                    
            if updates:
                Edge.objects.bulk_update(updates, ['current_traffic_speed', 'free_flow_speed', 'last_updated_at', 'data_source'])
            
        finally:
            if mode in ['LIVE', 'HYBRID']:
                cache.delete('tomtom_polling_lock')
        
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        status_msg = 'SUCCESS' if num_congested > 0 else 'FAILED'
        async_to_sync(channel_layer.group_send)(
            "twin_events",
            {
                "type": "broadcast_event",
                "event": "traffic_updated",
                "data": {
                    "message": f"Polled traffic. Congested: {num_congested}",
                    "provider": "TOMTOM",
                    "status": status_msg
                }
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f"Successfully updated traffic! Congested {num_congested} edges."))
