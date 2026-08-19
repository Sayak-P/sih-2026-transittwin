# Prediction Model

## Responsibilities
Provide forward-looking estimates of network state to feed the digital twin, disruption propagation model, and operator dashboard. It anticipates issues before they manifest as critical alerts.

## Inputs
- Historical telemetry (travel times, dwell times).
- Historical OD passenger demand matrices.
- Live telemetry streams (current vehicle locations, speeds, stop queue sizes).
- Calendar data, weather forecasts, and known scheduled events.

## Outputs
- **Passenger Demand Forecasting**: Expected arrivals at stops (OD matrix projection) for the next N hours.
- **Crowding Forecasting**: Predicted occupancy levels for vehicles and wait queues for stops.
- **ETA / Delay Prediction**: Dynamic arrival times for vehicles at downstream stops.
- **Disruption Risk Estimation**: Probability of failure or severe congestion on specific edges.

## Algorithmic Approach (Baseline)
Start with deterministic and statistical baselines to ensure explainability and robustness:
- **Demand**: Historical rolling averages grouped by time-of-day, day-of-week, and passenger group.
- **ETAs**: Kinematic equations using current speed + historical average edge traversal times.
- **Crowding**: Conservation of flow (Current Queue + Predicted Arrivals - Predicted Boarding).
- **Risk Estimation**: Static threshold triggers (e.g., if edge speed drops below 20% of limit, flag as high risk).

## Future ML Extension
Machine Learning models (e.g., Graph Neural Networks for spatial-temporal propagation, LSTMs for demand forecasting) will be introduced *only* after baselines are established.
- **Evaluation**: Any ML model must demonstrably outperform the statistical baseline in Mean Absolute Error (MAE) and inference speed before deployment.
- **Constraint**: ML predictions must not act as a black box; they must be accompanied by confidence intervals and feature importance scores (explainability).

## Assumptions & Limitations
- Assumes historical patterns are a valid proxy for future baseline demand.
- Extreme outlier events (black swan events) may degrade deterministic prediction accuracy until telemetry corrects the live state.
