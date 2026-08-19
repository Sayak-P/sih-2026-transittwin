# System Requirements

## Functional Requirements
1. **Network Representation**: Model stops, edges, routes, vehicles, and dynamic edge costs in a transport-mode agnostic way.
2. **Passenger Demand**: Support origin-destination (OD) demand matrices, representing expected passenger flow between stops within time windows.
3. **Accessibility**: Support passenger demand groups (normal, mobility-constrained, wheelchair users, step-free-required) and treat accessibility needs as hard constraints in routing and interventions.
4. **State Syncing**: Consume telemetry to update the real state.
5. **Prediction**: Forecast passenger demand, crowding, ETA/delays, and disruption risks using deterministic baselines before introducing ML.
6. **Disruption Injection**: Support vehicle breakdowns, road blockages, crowd surges, weather hazards.
7. **Simulation Engine**: Clone network state to test hypothetical interventions. Simulation scenarios must never mutate live state.
8. **Intervention Engine**: Suggest extensible interventions (vehicle rerouting, schedule modification, spare vehicle deployment, emergency shuttle deployment, service frequency adjustment, vehicle redistribution, temporary stop closure).
9. **Optimization**: Rank feasible solutions based on soft objectives after filtering out mathematically infeasible solutions via hard constraints.
10. **Operator Dashboard**: Live map, predictions, what-if sandbox, comparison tables, and approval workflows.
11. **Commuter View**: Provide dynamic ETAs, accessibility alerts, and alternative routes.

## Non-Functional Requirements
1. **Performance**: Fast what-if simulations to allow rapid decision making.
2. **Scalability**: Capable of handling demand matrices and metropolitan-scale graphs and fleet sizes without performance degradation.
3. **Explainability**: Outputs must mathematically justify recommendations.
4. **Isolation**: Strict separation of live state datastore and simulation environments.
5. **Technology Discipline**: Do not add technologies unless they solve a concrete requirement. No LLM chatbots or generic AI assistants are to be included.

## Security & Compliance
1. Role-based access control (Operator/Admin).
2. Comprehensive audit logs for operator actions.
3. API authentication and validation.
