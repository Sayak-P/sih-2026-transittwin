# Disruption Propagation Model

## Goal
Do not merely isolate a disruption. Compute its cascading blast radius across the network as a first-class subsystem.

## Propagation Cascade (Explicit Model)
1. **Primary Disruption**: E.g., road blockage, vehicle breakdown, or extreme weather event.
2. **Vehicle Delay**: Vehicles on the affected edge, or scheduled to use it, experience immediate delay.
3. **Passenger Accumulation**: With delayed arrivals, passenger wait queues at downstream stops accumulate beyond baseline OD demand forecasts.
4. **Capacity Bottleneck**: When delayed vehicles eventually arrive, they lack capacity for the enlarged queues, leaving passengers stranded.
5. **Passenger Redistribution**: Stranded passengers seek alternative routes or modes, shifting the load across the graph.
6. **Secondary Crowding**: Alternative routes experience unexpected passenger surges at their stops.
7. **Secondary Delay**: Dwell times increase at secondary stops due to massive boarding/alighting volumes, delaying secondary vehicles.
8. **Network-wide Impact**: The cycle repeats, propagating delays and crowding outward from the primary epicenter.

## Measurement
The simulator tracks the delta between `Baseline State (No Disruption)` and `Disrupted State (No Intervention)` to measure the total propagation volume and identify critical bottlenecks before they occur.
