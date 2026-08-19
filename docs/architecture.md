# Architecture

## Paradigm
**Modular Monolith**
We favor strict internal module boundaries over premature microservices to simplify simulation state synchronization.

## Digital Twin Philosophy
The architecture mandates a strict separation between **LIVE STATE** and **SIMULATION STATE**. Simulation scenarios act purely on deep-copied snapshot data and must never mutate live state.

## Top-Level Modules
- `backend/`: Django/DRF application handling APIs, WebSockets, and orchestration.
- `simulation/`: Passenger flow, disruption propagation engine, and intervention evaluation sandbox.
- `prediction/`: Demand forecasting, crowding forecasting, ETA/delay prediction, and disruption risk estimation.
- `optimization/`: Google OR-Tools formulations for constraint filtering and intervention ranking.
- `frontend/`: React/TypeScript/Vite dashboard.
- `data/`: Ingestion pipelines and telemetry generation.

## Technology Stack
- **Database**: PostgreSQL with PostGIS (spatial queries), Redis (caching, WebSockets, real-time queues).
- **Backend Language**: Python 3.11+.
- **Web Framework**: Django, Django REST Framework, Django Channels.
- **Simulation**: NetworkX (graph ops), NumPy, Pandas (for demand matrix processing).
- **Optimization**: Google OR-Tools.
- **Frontend**: React, TypeScript, Tailwind CSS, shadcn/ui.
- **Mapping**: MapLibre GL JS.

*Note: Technologies are strictly limited to concrete requirements. No LLMs or generic AI models are included.*

## System Interaction Flow
1. Telemetry ingest updates Postgres (historic) and Redis (live state).
2. Django triggers `prediction/` to update forecasts and detect anomalies/threshold breaches.
3. On disruption, `simulation/` initializes an isolated clone state from the live state.
4. `simulation/` runs the Disruption Propagation Model to compute cascading impacts.
5. The system generates extensible candidate interventions based on the impact scope.
6. `optimization/` filters out candidates violating hard constraints (e.g., accessibility, capacity).
7. `simulation/` runs feasible candidates to score soft objectives (delay, energy, crowding).
8. `optimization/` ranks the feasible results.
9. `backend/` serves ranked results and explanations to React dashboard via WebSocket for human approval.
10. Operator approves an intervention via the Command Center UI.
11. The approved candidate mutates the Live State safely.
12. The `AuditService` records the `scenario_id` and action irrevocably in the `AuditLog` table.
