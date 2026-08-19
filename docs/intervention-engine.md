# Intervention Engine

## Purpose
Generate actionable, extensible responses to disruptions that an operator can review, compare, and approve.

## Extensible Candidate Pool
The engine supports generating polymorphic intervention strategies:
1. **Vehicle Rerouting**: Temporarily alter a vehicle's path to bypass a blockage.
2. **Schedule Modification**: Delay, hold, or speed up departures to space out vehicles (headway management).
3. **Spare Vehicle Deployment**: Inject a reserve vehicle from a depot to clear a crowded stop.
4. **Emergency Shuttle Deployment**: Create a temporary point-to-point shuttle route bridging a broken segment.
5. **Service Frequency Adjustment**: Increase vehicle frequency on routes absorbing secondary crowding.
6. **Vehicle Redistribution**: Short-turn a vehicle or deadhead it to a high-demand origin.
7. **Temporary Stop Closure**: Prevent boarding/alighting at severely overcrowded or unsafe points.

## Multi-Objective Evaluation
Every generated intervention is run through the Simulation Engine and scored against the Optimization Model's soft objectives (Delay, Waiting Time, Overcrowding, Energy, Operational Cost) after passing hard constraints.
