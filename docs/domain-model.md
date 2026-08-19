# Domain Model

## Core Entities
- **Stop/Station/Point**: Node in the graph. Holds accessibility flags, current wait queues.
- **Edge/Segment**: Directed link between nodes. Holds travel time, congestion, accessibility flags.
- **Route**: Ordered collection of edges and stops. Transport-mode agnostic.
- **Vehicle**: Current location, route assignment, occupancy, capacity, accessibility capabilities.
- **Event/Disruption**: An anomaly affecting an edge, stop, or vehicle with temporal bounds.

## Passenger Demand Model
- **Passenger Group**: Classifies passenger accessibility needs (e.g., normal, mobility-constrained, wheelchair users, step-free-required).
- **OD Demand Matrix**: Origin-Destination (OD) demand representation. Contains `origin_stop`, `destination_stop`, `time_window`, `expected_passengers`, and `passenger_group`.
- **Occupancy**: Current passenger load on a vehicle, tracked by passenger group to ensure accessible spaces are managed.
- **Wait Queue**: Passengers waiting at a stop, sensitive to cascading delays, tracked by destination and passenger group.

## Simulation Context
- **Live State**: The authoritative snapshot of the network. Mutated only by real-time telemetry.
- **Simulation State**: An isolated deep copy of the network state. Mutated by what-if logic. Must never bleed into Live State.

## Interventions
An extensible, polymorphic system of actions. Candidates include:
- `VehicleRerouting`
- `ScheduleModification`
- `SpareVehicleDeployment`
- `EmergencyShuttleDeployment`
- `ServiceFrequencyAdjustment`
- `VehicleRedistribution`
- `TemporaryStopClosure`
