# TransitTwin: LIVE, HYBRID & SIMULATION Architecture

The TransitTwin application is strictly divided into three operational modes, controlled by the `TRANSIT_TWIN_MODE` environment variable. This ensures strict isolation between real and fake data, preserving data provenance and operator trust.

## The Modes

### LIVE Mode
Strict production mode. Absolutely no simulated data is allowed to enter the LiveStateEngine.
- **Traffic**: Real TomTom only.
- **Incidents**: Real TomTom only.
- **Vehicles**: CRUT only (currently OFFLINE due to B2B integration blockers).
- **Simulation**: Forced DISABLED. `run_telemetry_simulator` will exit immediately.
- **Demo Reset**: Disabled. Any attempt to hit `/api/v1/system/demo-reset/` returns a `403 Forbidden`.

### HYBRID Mode
The required configuration for the SIH Demonstration. Marries real-world intelligence with fleet simulation.
- **Traffic**: Real TomTom.
- **Incidents**: Real TomTom.
- **Vehicles**: Internal Simulation.
- **Constraint**: Simulation vehicles must always be tagged `data_source=SIMULATION`, `provider=INTERNAL` and be visually explicit in the UI with a "SIM" badge.

### SIMULATION Mode
A fully mocked environment used for deterministic testing and algorithm tuning.
- **Traffic**: Simulation (Randomized/Mocked).
- **Incidents**: Simulation (Randomized/Mocked).
- **Vehicles**: Simulation.

## The Pre-Action Sandbox
Regardless of the active mode, the Pre-Action Sandbox ALWAYS operates in a simulated environment. When an operator clicks `OPEN PRE-ACTION SANDBOX`, the system forks the `LiveStateEngine` into an isolated context. Candidate interventions are run against this clone to predict consequences (e.g., delays, load impact) without ever touching the actual Live state.

## Operator Approval
The simulated prediction becomes reality ONLY when the operator selects `APPROVE & DISPATCH`. This triggers a strict validation process, mutates the Live State, and records the intervention immutably in the `AuditLog`.
