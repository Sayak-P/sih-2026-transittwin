import os
import django
import time
from datetime import datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from simulation.state.live_state import LiveStateEngine
from simulation.state.snapshot_manager import StateSnapshotManager
from simulation.engine.passenger_flow import PassengerFlowSimulator
from core.models import Vehicle, RouteEdge

def main():
    print("--- PHASE 4 SIMULATION VERIFICATION ---")
    
    # Pre-seed LiveState with DB vehicles since telemetry simulator isn't running
    for v in Vehicle.objects.all():
        start_stop = v.route.route_edges.first().edge.source if v.route and v.route.route_edges.exists() else None
        LiveStateEngine.update_vehicle_state(v.identifier, {
            "vehicle_id": v.identifier,
            "lat": start_stop.lat if start_stop else 0,
            "lon": start_stop.lon if start_stop else 0,
            "capacity": v.capacity,
            "accessible_capacity": v.accessible_capacity,
            "occupancy": 0
        })

    print("Creating snapshot from seeded Live State...")
    scenario, sim_state = StateSnapshotManager.create_snapshot()
    
    # Configure a realistic 60-minute simulation
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=60)
    
    config = {
        "start_time": start_time,
        "end_time": end_time,
        "timestep_seconds": 10,
        "random_seed": 42
    }
    
    print(f"Starting Passenger Flow Simulator...")
    print(f"Time Window: {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
    print(f"Timestep: {config['timestep_seconds']} seconds")
    
    start_cpu_time = time.time()
    
    sim = PassengerFlowSimulator(sim_state, config)
    metrics, event_log = sim.run()
    
    exec_time = time.time() - start_cpu_time
    
    print("\n--- SIMULATION COMPLETE ---")
    print(f"Execution Time: {exec_time:.3f} seconds\n")
    
    # Calculate onboard
    onboard = sum(
        sum(cohorts.values()) 
        for vehicle_id, cohorts in sim_state.vehicle_passengers.items()
    )
    
    print("--- COMPUTED RESULTS ---")
    print(f"Passengers Generated:           {metrics['passengers_generated']}")
    print(f"Passengers Served (Completed):  {metrics['passengers_served']}")
    print(f"Passengers Remaining (Queue):   {metrics['passengers_remaining']}")
    print(f"Passengers Onboard:             {onboard}")
    print(f"Total Waiting Minutes:          {metrics['total_waiting_seconds'] / 60.0:.2f}")
    print(f"Average Waiting Time (min):     {metrics['average_waiting_minutes']:.2f}")
    print(f"Maximum Queue Size:             {metrics['max_queue_size']}")
    print(f"Maximum Crowding Ratio:         {metrics['max_crowding_ratio']:.2f}")
    print(f"Capacity-Denied Boardings:      {metrics['capacity_denied_boardings']}")
    print(f"Accessibility-Denied Boardings: {metrics['accessibility_denied_boardings']}")
    
    print("\n--- EVENT LOG ---")
    for event in event_log[:20]:
        print(f"[{event['timestamp']}] {event['message']}")
    if len(event_log) > 20:
        print(f"... and {len(event_log) - 20} more events")

if __name__ == "__main__":
    main()
