import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from simulation.state.live_state import LiveStateEngine
from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Runs a lightweight daemon that advances the digital twin Live State via the Passenger Flow Simulator.'

    def add_arguments(self, parser):
        parser.add_argument('--delay', type=float, default=5.0, help='Seconds to wait between ticks')

    def handle(self, *args, **options):
        delay = options['delay']
        channel_layer = get_channel_layer()
        self.stdout.write("Starting Live Engine Daemon...")

        while True:
            try:
                # 1. Take snapshot of current Live State
                scenario, sim_state = StateSnapshotManager.create_snapshot()
                
                # 2. Configure a tiny 10-second tick
                now = datetime.now()
                config = {
                    "start_time": now,
                    "end_time": now + timedelta(seconds=10),
                    "timestep_seconds": 10,
                    "random_seed": 42
                }
                
                # 3. Step Simulator
                sim = PassengerFlowSimulator(sim_state, config)
                sim.run()
                
                # 4. Commit results back to Live State
                updated_vehicles = []
                for v_id, v_data in sim_state.vehicles.items():
                    # Update Vehicle LiveState
                    success, state = LiveStateEngine.update_vehicle_state(v_id, {
                        "lat": v_data.get('lat'),
                        "lon": v_data.get('lon'),
                        "occupancy": v_data.get('occupancy', 0),
                        "status": v_data.get('status', 'ACTIVE'),
                        "timestamp": timezone.now().isoformat()
                    })
                    if success:
                        updated_vehicles.append(state)

                for s_id, q_data in sim_state.stop_queues.items():
                    total_queue = sum(q_data.values())
                    LiveStateEngine.update_stop_state(str(s_id), {
                        "queue_count": total_queue,
                        "timestamp": timezone.now().isoformat()
                    })

                # Delete ephemeral scenario snapshot since it was just for stepping
                scenario.delete()

                # 5. Broadcast updates via Channels
                if channel_layer:
                    for v_state in updated_vehicles:
                        async_to_sync(channel_layer.group_send)(
                            "twin",
                            {
                                "type": "twin_message",
                                "message": {
                                    "event": "vehicle.updated",
                                    **v_state
                                }
                            }
                        )

            except Exception as e:
                self.stderr.write(f"Daemon Tick Error: {e}\n")
                self.stderr.flush()

            self.stdout.flush()
            time.sleep(delay)
