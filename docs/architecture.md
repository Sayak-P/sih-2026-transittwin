# TransitTwin: Digital Twin Architecture Specification (SIH 2026 S15)

## 1. System Overview
**TransitTwin** is a high-fidelity digital twin platform for urban public transit networks (bus, metro, multimodal corridor). It predicts crowding and service disruptions from live telemetry, ticketing demand, and real-world event dynamics. 

Before transit operators act, the platform simulates alternate schedules, evaluates accessible rerouting paths, and quantifies passenger delay, safety risk, and energy consumption inside an isolated sandbox.

```
                                  ┌─────────────────────────────┐
                                  │   Real-World Telemetry      │
                                  │   & Event / Demand Feeds    │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    LiveStateEngine (Twin)   │
                                  │  (Redis/In-Memory Cache)    │
                                  └──────────────┬──────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
    ┌─────────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
    │   M/M/c Dynamic Queueing    │ │   Pre-Action Sandbox      │ │    Event & Ticketing      │
    │  & RF Surge Predictor       │ │   (State Isolation)       │ │    Demand Engines         │
    └──────────────┬──────────────┘ └─────────────┬─────────────┘ └─────────────┬─────────────┘
                   │                              │                             │
                   │                              ▼                             │
                   │               ┌─────────────────────────────┐              │
                   │               │ Multi-Objective Optimization│              │
                   │               │ W(e) = α(T) + β(E) + γ(A)   │              │
                   │               └──────────────┬──────────────┘              │
                   │                              │                             │
                   └──────────────────────────────┼─────────────────────────────┘
                                                  ▼
                                   ┌─────────────────────────────┐
                                   │ Unified Operator Dashboard  │
                                   │ (React 18 + MapLibre GL)    │
                                   └─────────────────────────────┘
```

---

## 2. Core Architectural Pillars

### A. State Isolation Pattern
* **`LiveStateEngine`**: In-memory/cache source of truth representing the active state of vehicles, stops, and edges.
* **`SimulationState`**: Deep snapshot of the twin state used exclusively for simulations.
* **Invariant**: *Simulations and sandbox evaluations NEVER mutate LiveState directly.* Only explicit operator approval via the sandbox approve endpoint commits actions to the live fleet.

### B. Mathematical Formulations

#### 1. Station Crowd Dynamic Evolution (M/M/c Queueing Model)
$$\text{Crowd}(t + \Delta t) = \max\left(0, \text{Crowd}(t) + (\lambda_{\text{base}} \cdot E_{\text{event}} - \mu_{\text{boarding}}) \cdot \Delta t\right)$$
* $\lambda_{\text{base}}$: Time-of-day baseline passenger arrival rate (pax/min).
* $E_{\text{event}}$: Machine learning event surge multiplier predicted by `RandomForestRegressor`.
* $\mu_{\text{boarding}}$: Dynamic boarding throughput. When approaching vehicles are blocked or delayed, $\mu_{\text{boarding}} \to 0$, triggering predicted station crowd spikes.

#### 2. Event Distance-Decay Demand Model
$$E_{\text{event}}(s) = 1.0 + \sum_{e \in \text{Events}} \text{Intensity}_e \cdot \exp\left(-\frac{d(e, s)}{\text{Radius}_e}\right)$$

#### 3. Pre-Action Rerouting Objective Function
$$W(e) = \alpha \cdot T_e + \beta \cdot E_e + \gamma \cdot A_e$$
* $T_e$: Congestion-adjusted travel time ($D_e / V_e$).
* $E_e$: Energy consumption in kWh.
* $A_e$: Accessibility barrier penalty ($A_e = 0$ if step-free accessible, $\gamma$ if non-accessible).

---

## 3. Module Hierarchy & Directory Structure

```
backend/
├── config/              # ASGI/WSGI routing, Daphne configuration
├── core/                # Stop, Edge, Route, Vehicle, Disruption ORM models & state APIs
├── prediction/          # M/M/c queueing dynamics, MTA-trained RandomForest surge model
├── simulation/
│   ├── engine/          # PassengerFlowSimulator, PropagationEngine
│   ├── events/          # Event models & exponential distance-decay surge engine
│   ├── interventions/   # Candidate generator, multi-objective scorer, sandbox
│   ├── passenger/       # Deterministic ticketing demand simulator
│   ├── scenarios/       # What-if scenario simulation engine
│   ├── schedules/       # Schedule simulator & side-by-side comparison engine
│   └── state/           # LiveStateEngine, SimulationState, SnapshotManager
└── optimization/        # DisruptionSandboxEngine (NetworkX graph routing)

frontend/
├── src/
│   ├── App.tsx                    # Central Command Center & Live Map
│   ├── PredictionsDashboard.tsx   # Multi-horizon forecast & M/M/c equation visualizer
│   ├── ReroutingDashboard.tsx     # Multi-objective detour sandbox
│   ├── InterventionSimulator.tsx  # Schedule comparison & what-if analysis
│   └── SmartBusNavigator.tsx      # Hurdle-free driver turn-by-turn guidance
```
