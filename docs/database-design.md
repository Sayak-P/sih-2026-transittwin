# Database Design

## Strategy
PostgreSQL with PostGIS for spatial operations.

## Core Schema (High-Level)

### Static Infrastructure
- `Stop`: id, name, location (Point), is_accessible, capacity.
- `Edge`: id, source_stop, target_stop, geometry (LineString), baseline_cost, is_accessible.
- `Route`: id, name, type (bus/metro).

### Dynamic State
- `Vehicle`: id, current_location (Point), route_id, occupancy, capacity, accessible_capacity, state (active/delayed/broken).
- `ODDemand`: id, origin_stop_id, destination_stop_id, time_window_start, time_window_end, expected_passengers, passenger_group.

### Disruptions & Simulation
- `Disruption`: id, type, location_ref, start_time, expected_end_time, severity.
- `SimulationScenario`: id, base_disruption_id, created_at, status. Strictly separated from live telemetry.
- `InterventionCandidate`: id, scenario_id, type, parameters (JSON: extensible for rerouting, spare deployment, closures, etc.).
- `SimulationResult`: id, intervention_id, is_feasible, metrics (JSON: delay, wait_time, crowding, energy, cost).

### Audit
- `AuditLog`: operator_id, action, timestamp, scenario_id, applied_intervention_id.
