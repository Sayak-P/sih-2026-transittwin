# TransitTwin: Data Provenance & Freshness

To maintain operator trust, TransitTwin strictly enforces data provenance and visualizes staleness. Operators must always know where data comes from, if it is real or simulated, and how old it is.

## 1. Data Truth Table

The following table explicitly defines the data reality based on the active deployment mode:

| Mode | Traffic | Incidents | Vehicles |
|---|---|---|---|
| **LIVE** | Real TomTom Only | Real TomTom Only | CRUT Only (Currently OFFLINE)* |
| **HYBRID** | Real TomTom Only | Real TomTom Only | Simulation (Explicitly Labeled) |
| **SIMULATION** | Simulation (Mocked) | Simulation (Mocked) | Simulation (Mocked) |

*(CRUT B2B live telemetry integration is structurally prepared but currently offline due to a lack of official credentials and API documentation. No fake data will be presented as CRUT data.)*

## 2. Provenance Architecture

Data entering the system is irreversibly tagged with its source:
- `data_source` (e.g., `TOMTOM`, `CRUT`, `SIMULATION`)
- `provider` (e.g., `INTERNAL`, `TOMTOM`)

In the Command Center UI:
- **Simulated Vehicles** carry a visible "SIM" badge on the map and side-panel.
- **Incidents** explicitly state "Source: TOMTOM" when clicked.
- **Provider HUD** explicitly shows the active mode (e.g., "Simulation Fleet: ACTIVE", "CRUT Telemetry: OFFLINE").

## 3. Freshness & Staleness

Both the backend and frontend implement cascading safety protocols for aging data.

### TomTom Traffic / Incidents
- **< 5 Minutes**: Fresh (`ONLINE`). Edges/markers pulse brightly on the map.
- **5–15 Minutes**: Aging (`STALE`). The Data Provider HUD flashes yellow. Map edges fade visually.
- **> 15 Minutes**: Severely Stale. The prediction engine fallback logic stops trusting the real-time congestion and reverts to historical/estimated routing parameters to prevent permanent gridlock from broken API feeds.

### Vehicle Telemetry
- **< 15 Minutes**: Vehicle remains active and visible.
- **> 15 Minutes**: Vehicle is aggressively culled from the `LiveStateEngine` to prevent ghost buses from accumulating memory and cluttering the UI.
