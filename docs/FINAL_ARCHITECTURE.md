# TransitTwin: Final Architecture

TransitTwin is a modular monolith application serving as a decision-intelligence platform and live digital twin for the Bhubaneswar public transit network. It represents the physical network state in real-time, projects future cascading disruptions using a causal graph, and generates predictive interventions in a localized Sandbox.

## 1. System Architecture
The application runs on a **Django (Python)** backend and a **Vite/React/TypeScript** frontend. It leverages **Redis** for WebSocket streaming (Django Channels) and state synchronization. A **PostgreSQL/PostGIS** database stores network topologies, constraints, historical telemetry, and the audit log.

## 2. Backend/Frontend Communication
- **REST APIs (`/api/v1/`)**: Used for bulk data fetching on initial loads, triggering heavy backend calculations (blast radius), Sandbox generation, and submitting operator approvals.
- **WebSockets (`/ws/twin/`)**: Pushes high-frequency real-time events. As vehicles move or new TomTom traffic parameters arrive, `LiveStateEngine` broadcasts partial state updates (`vehicle.updated`, `traffic_updated`) which the React frontend intelligently merges, avoiding expensive full re-renders.

## 3. PostgreSQL Data Model
Core tables enforce geospatial topologies using PostGIS. Edges and Nodes define the road network. Vehicle instances trace telemetry paths. Rigid schema constraints prevent absurd state mutations (e.g. `occupancy_lte_capacity` or self-referencing edges). The `AuditLog` table permanently stores all human-approved interactions.

## 4. LiveStateEngine
The heart of the digital twin. This singleton-like in-memory object (backed by cache/Redis) maintains the absolute current state of the transit network. It strictly prevents direct operator mutations, enforcing read-only consumption until a Sandbox scenario has been explicitly `APPROVED`.

## 5. WebSocket/twin_events flow
Events propagate directionally:
1. Data ingested (TomTom API or Vehicle Telemetry Pipeline)
2. Validated and mapped to OSM edges
3. Mutates `LiveStateEngine`
4. Dispatched to Django Channels `twin_events` group
5. React `App.tsx` merges partial payload into local hooks.

## 6. TomTom Traffic Integration
Implemented via `poll_tomtom_traffic` management command. Fetches traffic density point-by-point, maps GPS coordinates to the nearest OSM edge, translates speed/travel-time ratios into `congestion_level`, and pushes the result to `LiveStateEngine`.

## 7. TomTom Incident Integration
Implemented via `poll_tomtom_incidents`. Fetches real-world incidents (closures, accidents, jams). Converts them to deterministic `Disruption` models mapped to geographical coordinates, triggering map alerts and blast-radius generation availability.

## 8. Vehicle Telemetry Pipeline
Ingests incoming GPS/occupancy data, validates it against physical constraints (ensuring it's on a valid route), and stamps it with explicit provenance tags (`REAL` or `SIMULATION`) before pushing to the frontend.

## 9. Pre-Action Sandbox
A temporary, isolated `LiveStateEngine` clone. When candidates are generated (e.g. detours), they run purely inside this clone to evaluate consequences (e.g. delay reduction, passenger throughput) without corrupting the actual live twin.

## 10. Routing Safety & Culling
The backend dynamically avoids routing buses through explicitly closed roads. Front-end actively dims map edges and fades vehicle icons if data surpasses freshness thresholds (5+ minutes for traffic, 15+ minutes for vehicles), explicitly signaling operators not to trust stale intelligence.
