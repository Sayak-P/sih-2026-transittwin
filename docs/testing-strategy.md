# Testing Strategy

## Layers
1. **Unit Tests (Pytest)**: Fast, isolated tests for algorithms (e.g., OR-Tools constraints, NetworkX shortest path).
2. **API Tests**: DRF test client to validate JSON contracts and authentication.
3. **Simulation Tests**: Deterministic state-machine tests. Given state A + disruption B -> verify state C matches expected math.
4. **Accessibility Tests**: Ensure inaccessible routing constraints are strictly enforced.
5. **Frontend Tests**: React Testing Library for the Operator Dashboard component logic.

## Quality Rules
- Mock only external APIs or hardware telemetry.
- Do NOT mock the simulation engine's core math during integration tests.
- Maintain a separate deterministic "test network graph" (e.g., 5 stops, 2 routes) for predictable assertions.
