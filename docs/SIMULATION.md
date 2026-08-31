# TransitTwin: Simulation & Intervention Engine Guide (SIH 2026 S15)

## 1. Overview
The **Simulation Subsystem** provides decision support for transit dispatchers and urban planners. It allows operators to test schedule alterations, emergency detours, and disruption scenarios in an isolated digital twin sandbox without auto-dispatching.

---

## 2. Schedule Interventions

The platform supports 9 discrete schedule and dispatch interventions:

| Intervention | Description | Parameters |
|--------------|-------------|------------|
| `INCREASE_FREQUENCY` | Injects virtual vehicles into a route to reduce headway | `route_id`, `new_headway_minutes` |
| `DECREASE_FREQUENCY` | Removes vehicles from service to save energy/operating costs | `route_id`, `new_headway_minutes` |
| `DISPATCH_ADDITIONAL` | Deploys a spare vehicle from depot onto a stressed corridor | `vehicle_id`, `route_id` |
| `CHANGE_DEPARTURE` | Modifies scheduled departure offset at a terminal | `vehicle_id`, `delay_minutes` |
| `HOLD_BUS` | Holds a bus at a transfer station to allow passenger boarding | `vehicle_id`, `stop_id`, `hold_seconds` |
| `REASSIGN_VEHICLE` | Moves a vehicle from a low-demand line to a high-demand line | `vehicle_id`, `from_route_id`, `to_route_id` |
| `SKIP_STOP` | Directs express buses to bypass overcrowded or blocked stops | `vehicle_id`, `skip_stop_id` |
| `REROUTE` | Applies NetworkX optimal hurdle-free detour around road blockage | `vehicle_id`, `blocked_edge_id` |
| `COMBINED` | Bundles multiple atomic interventions into a synchronized strategy | `interventions: []` |

---

## 3. Side-by-Side Intervention Comparison Engine

When an early warning or disruption occurs, the operator evaluates multiple options simultaneously:

```
[BASELINE (No Action)]   vs   [OPTION A: Increase Frequency]   vs   [OPTION B: Hold Bus]
        ↓                                   ↓                                  ↓
Simulate in Sandbox               Simulate in Sandbox                Simulate in Sandbox
        ↓                                   ↓                                  ↓
Avg Wait: 18.4 min                Avg Wait: 9.2 min (-9.2m)          Avg Wait: 14.1 min (-4.3m)
Max Crowding: 1.42x               Max Crowding: 0.88x (-0.54)        Max Crowding: 1.15x (-0.27)
Passengers Served: 840            Passengers Served: 1,120 (+280)    Passengers Served: 910 (+70)
        ↓                                   ↓                                  ↓
                        RECOMMENDATION: Option A (Score: 0.24)
```

### Multi-Objective Profiles:
* **`BALANCED`**: Equal weighting across Delay (0.25), Crowding (0.25), Energy (0.25), Safety (0.25).
* **`MINIMUM_DELAY`**: Prioritizes passenger throughput (Delay: 0.70, Energy: 0.10).
* **`SAFETY_FIRST`**: Prioritizes crowd density reduction and hazard avoidance (Safety: 0.70, Crowding: 0.20).
* **`ENERGY_EFFICIENT`**: Minimizes vehicle-kilometers and fuel/electricity (Energy: 0.50, Delay: 0.30).

---

## 4. What-If Scenario Engine

Operators can simulate systemic disruptions to evaluate network resilience:
1. **`ROAD_BLOCKED`**: Simulates sudden road closure / waterlogging.
2. **`DEMAND_SURGE`**: Simulates sudden passenger rush at key hubs.
3. **`BUS_DELAYED`**: Simulates vehicle breakdown or mechanical delay.
4. **`EVENT_STARTS`**: Simulates concert or stadium rush near a transit node.
5. **`VEHICLE_UNAVAILABLE`**: Evaluates fleet shortage impact.
6. **`FREQUENCY_CHANGE`**: Tests operational timetable adjustments.

---

## 5. Event Engine & Demand Modifiers

Predefined event catalog with distance-decay radius:
* `CONCERT` (Intensity: 2.0x, Radius: 2.5 km)
* `SPORTS_EVENT` (Intensity: 1.8x, Radius: 2.0 km)
* `FESTIVAL` (Intensity: 2.5x, Radius: 3.5 km)
* `EXAMINATION` (Intensity: 1.2x, Radius: 1.5 km)
* `PUBLIC_GATHERING` (Intensity: 1.5x, Radius: 2.0 km)
* `RELIGIOUS_EVENT` (Intensity: 1.8x, Radius: 2.0 km)
* `MARKET_DAY` (Intensity: 1.0x, Global)

---

## 6. Deterministic Ticketing Simulator

Generates synthetic ticketing streams (`arrivals`, `boardings`, `alightings`, `queue`) using seeded pseudo-random distributions with:
* Rush hour vs off-peak time-of-day curves.
* Weekend vs weekday demand profiles.
* Stop importance weighting (hub stops receive up to 1.8x baseline volume).
