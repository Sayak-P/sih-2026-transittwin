# TransitTwin Project Rules

## 1. Core Principles
- **Human-in-the-Loop**: Never silently execute high-impact operational changes. The system recommends; the operator approves.
- **Explainability**: Every recommendation must explain why it was selected, alternatives, and expected impacts (delay, safety, energy, accessibility).
- **Digital Twin & Simulation**: Real state must be completely isolated from simulation state. What-if scenarios must clone state.
- **Disruption Propagation**: Model secondary effects (vehicle → stop → passenger → route → connection → network).
- **Accessibility as Constraint**: Treat accessibility as a real constraint (step-free, accessible vehicles), not just UI.
- **Multi-Objective Decision Making**: Evaluate passenger delay, waiting time, overcrowding, safety, energy, accessibility, and feasibility.
- **Measurable Results**: Delay reduction = `baseline_disruption_delay - intervention_delay`. Safety risk increases with occupancy.

## 2. Technology & Architecture
- **Stack**: Python, Django, DRF, PostgreSQL, PostGIS, Redis, NetworkX, OR-Tools, React, TS, Vite, MapLibre.
- **Pattern**: Modular monolith with clear boundaries (`backend/`, `simulation/`, `prediction/`, `optimization/`, `frontend/`, `data/`).
- **AI/ML**: Use deterministic/statistical baselines first. ML must prove measurable value against baselines (MAE/RMSE/MAPE).

## 3. Quality & Implementation
- No fake implementations to fake completeness. Document mocks clearly.
- Work one phase at a time and seek approval.
- Small, logical Git commits (`feat: ...`, `test: ...`).
- Keep documentation synchronized with major algorithms.
