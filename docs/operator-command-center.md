# Operator Command Center

The Operator Command Center is the Phase 8 culmination of the TransitTwin project. It serves as the unified dashboard for transit network operators, seamlessly integrating all underlying engines built in previous phases.

## Core Principles

1. **Live State Isolation**: The Command Center reads from the LiveStateEngine. It NEVER mutates live state directly without explicit operator authorization through the Pre-Action Sandbox.
2. **Explainable Prediction**: Early warnings are flagged securely, highlighting predicted queue overflows or network bottlenecks before they happen.
3. **Pre-Action Sandbox (What-If Simulation)**: Operators can simulate disruptions and generate ranked interventions based on multiple objective profiles (Safety First, Minimum Delay, Energy Efficient, Balanced).
4. **Deterministic Auditing**: All approved interventions are persistently logged into the PostgreSQL Database via the `AuditLog` for compliance and post-incident analysis.

## Workflow 

1. **Monitoring**: The system displays Live KPIs (Active Vehicles, Passengers, Avg Wait Time) and system health.
2. **Early Warning**: Predictive algorithms flag future issues (e.g., STOP 11 queue accumulation).
3. **Impact Analysis (Blast Radius)**: The operator triggers a disruption simulation (e.g., ROAD BLOCK on Edge 5). The system visualizes the causal cascade (Wait Time, Max Queue) without affecting the live network.
4. **Intervention Generation**: The Pre-Action Sandbox automatically generates candidate interventions (Vehicle Reroute, Spare Deployment, Stop Closure).
5. **Trade-off Evaluation**: Candidates are scored deterministically based on Wait Time Saved vs Energy Cost (`distance * 1.2 kWh/km`). Feasible candidates are ranked based on the operator's chosen objective.
6. **Approval & Dispatch**: The operator selects the best candidate and approves it. The system updates the LiveState and persists the action in the `AuditLog`.

## SIH Canonical Demo Workflow

A built-in `/api/v1/system/demo-reset/` endpoint instantly clears transient caches, reseeds the database, and pre-warms the live state cache for deterministic evaluations during the SIH presentation.
