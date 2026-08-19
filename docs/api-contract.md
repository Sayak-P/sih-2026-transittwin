# API Contract

## Versioning
All endpoints are prefix with `/api/v1/`.

## REST Endpoints
- `GET /network/state/`: Returns current nodes, edges, vehicles.
- `POST /disruptions/`: Inject a new real or simulated disruption.
- `POST /simulations/`: Trigger a what-if simulation run.
- `GET /simulations/{id}/results/`: Poll or fetch comparison metrics.
- `POST /simulations/{id}/approve/`: Operator approval for an intervention.
- `GET /metrics/health/`: Network health summary.

## WebSockets
- `ws://.../ws/network/live/`: Real-time coordinate updates for vehicles and live stop crowding.
- `ws://.../ws/simulations/{id}/`: Streaming updates as a simulation processes its scenario tree.

## Security
- JWT-based authentication.
- Read/Write scopes tailored to Operator vs Viewer roles.
