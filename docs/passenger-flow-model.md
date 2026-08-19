# Passenger Flow Model

This document outlines the deterministic passenger flow simulation engine implemented in Phase 4.

## 1. Passenger Demand Representation
Passengers are modeled as **Aggregated Cohorts**, not individual Python objects, drastically improving performance. Each cohort maps directly to a generated `ODDemand` entry.

## 2. OD Model
Demand is generated strictly as Origin-Destination pairs matching the `ODDemand` table.

## 3. Passenger Cohorts
A cohort state is tracked within `SimulationState.passenger_cohorts`. It records:
- Origin and Destination Stops
- `passenger_group` (e.g., NORMAL, STEP_FREE_REQUIRED)
- `total_generated`, `waiting`, `onboard`, `completed`

## 4. Queue Mechanics
When demand is generated, cohorts are mapped into `SimulationState.stop_queues`. They remain here until an eligible vehicle with available capacity arrives.

## 5. Boarding Mechanics
When a vehicle arrives at a stop, boarding is processed iteratively across the queue up to the strict limit of `vehicle.capacity - vehicle.occupancy`.

## 6. Alighting Mechanics
Alighting is processed **before** boarding. Passengers onboard with a destination matching the current stop are removed from the vehicle and marked as `completed`.

## 7. Capacity Constraints
A strict invariant guarantees that `occupancy <= capacity`. If the queue exceeds capacity, the remaining passengers are left behind (recorded as `capacity_denied_boardings`).

## 8. Accessibility Handling
If a passenger group is `STEP_FREE_REQUIRED`, they are explicitly barred from boarding if the vehicle's `accessible_capacity` is 0 or the current stop `is_accessible == False`.

## 9. Waiting-Time Calculation
Waiting time is calculated precisely every simulation tick using:
`total_waiting_seconds += total_waiting_passengers_in_network * timestep_seconds`.

## 10. Passenger Conservation
A hard invariant (`Conservation Law`) ensures that at the end of every simulation tick:
`total_generated == (total_waiting + total_onboard + total_completed)`.
The simulation crashes immediately if this invariant is violated.

## 11. Simulation Clock
The simulation runs on a discretized, configurable `timestep_seconds` (default: 10s). It operates completely independently of wall-clock time.

## 12. Determinism
Given the exact same initial state, demand parameters, and time configurations, the simulator mathematically interpolates vehicle progress and passenger spawning. It produces 100% identical outputs when run repeatedly.

## 13. Known Limitations
- Disruptions and cascade delays are not yet modeled.
- Dynamic rerouting of vehicles is not implemented.
- Machine Learning predictions for passenger arrival variance is not implemented.
- Transfer nodes / multi-leg journeys are currently deferred. Passengers rely exclusively on single-leg transit availability.

## 14. Deferred Multi-Leg Journeys
Multi-leg passenger journeys are intentionally deferred to a later routing/intervention phase. Currently, a passenger boards a vehicle only if that vehicle is directly assigned to the route containing both origin and destination.
