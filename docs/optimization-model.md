# Optimization Model

## Engine
Google OR-Tools (Routing / Constraint Programming) paired with custom graph heuristics.

## Constraint Separation
The optimizer strictly separates mathematical feasibility from outcome quality. It must only rank feasible solutions.

### Hard Constraints (Feasibility)
Solutions violating these are immediately discarded:
1. **Vehicle Capacity**: Passenger count cannot exceed vehicle limits.
2. **Physical Feasibility**: Vehicles cannot traverse blocked edges; travel times from depots must be mathematically sound.
3. **Accessibility Requirements**: The optimizer must never choose an inaccessible route or vehicle for passengers requiring step-free/wheelchair access.
4. **Route Availability**: Vehicles must be compatible with the route infrastructure (e.g., bus vs. tram lines).
5. **Intervention Feasibility**: Operator limits (e.g., maximum spare vehicles available).

### Soft Objectives (Ranking)
Feasible solutions are ranked by minimizing a weighted sum of normalized metrics:
`Minimize: (w1 * Passenger Delay) + (w2 * Waiting Time) + (w3 * Overcrowding) + (w4 * Energy) + (w5 * Operational Cost)`

## Objective Profiles
1. **Minimum Delay**: Prioritizes travel time (w1, w2 high).
2. **Safety First**: Prioritizes reducing overcrowding (w3 high).
3. **Resource Efficient**: Minimizes energy and operational cost (w4, w5 high).
4. **Balanced**: Equal weights across all soft objectives.
