# TransitTwin Surge Prediction Model — Training Documentation

## Overview

The TransitTwin prediction engine uses a **RandomForestRegressor** to predict the **E_event (surge multiplier)** — a dimensionless factor representing how much passenger demand at a station exceeds its normal baseline. This value feeds directly into the M/M/c queueing formula:

```
Crowd(t + Δt) = max(0, Crowd(t) + (λ_base × E_event − μ_boarding) × Δt)
```

Where:
- **λ_base**: Baseline passenger arrival rate (time-of-day driven)
- **E_event**: ML-predicted surge multiplier (this model's output)
- **μ_boarding**: Boarding throughput (drops to 0 when buses are delayed)

---

## Dataset

| Property | Value |
|---|---|
| **Name** | NYC MTA Subway Hourly Ridership (2020–2024) |
| **Source** | [data.ny.gov](https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-2020-2024/wujg-7c2s) |
| **License** | Public Domain (NYC Open Data) |
| **Query Period** | 2023-01-01 to 2023-12-31 |
| **Granularity** | Hourly ridership per station complex |
| **Download Method** | SODA API (`data.ny.gov/resource/wujg-7c2s.json`) |
| **Data Type** | **REAL** (not synthetic) |

### Why This Dataset?

The NYC MTA dataset is one of the most granular, publicly available transit ridership datasets. It provides:
- **Hourly resolution** — capturing intra-day demand patterns
- **Per-station breakdown** — enabling station-level surge detection
- **Full calendar year** — covering weekdays, weekends, holidays, seasonal variation
- **Millions of observations** — sufficient statistical power

### What the Dataset Does NOT Contain

The following features are accepted at inference time but were **NOT available in the training data**:

| Feature | Status | Handling |
|---|---|---|
| `event_size_nearby` | ❌ Not in dataset | Accepted at inference; model not trained on it |
| `current_traffic_congestion_pct` | ❌ Not in dataset | Accepted at inference; model not trained on it |
| `scheduled_headway_min` | ❌ Not in dataset | Accepted at inference; model not trained on it |

These features are part of the `predict_event_surge()` API contract required by the M/M/c queue engine. When real city data (e.g., CRUT Bhubaneswar GPS, traffic, and event feeds) becomes available, the model should be retrained with these additional features.

---

## Target Variable

| Property | Value |
|---|---|
| **Name** | `surge_multiplier` (maps to `E_event`) |
| **Derivation** | `actual_ridership / median_ridership_for_station_hour_weekend_slot` |
| **Range** | Clipped to [1.0, 4.5] |
| **Interpretation** | 1.0 = normal demand, 2.0 = double normal, 4.5 = extreme surge |

### Derivation Methodology

For each combination of `(station_complex_id, hour_of_day, is_weekend)`, the **median ridership** is computed across all observations in the dataset. The surge multiplier for each individual observation is then:

```
surge_multiplier = actual_ridership / median_ridership
```

This produces a value centered around 1.0, with natural peaks during:
- Rush hours (7–9 AM, 5–7 PM)
- Special events (elevated station ridership vs. historical norm)
- Anomalous days (weather disruptions, holidays, service changes)

---

## Input Features

### Training Features (used by the model)

| Feature | Type | Range | Description |
|---|---|---|---|
| `hour_of_day` | int | 0–23 | Hour extracted from `transit_timestamp` |
| `day_of_week` | int | 0–6 | Monday=0, Sunday=6 |
| `is_weekend` | int | 0/1 | 1 if Saturday or Sunday |
| `month` | int | 1–12 | Month for seasonal patterns |
| `is_rush_hour` | int | 0/1 | 1 if hour in {7, 8, 9, 17, 18, 19} |

### Inference Features (accepted by the API)

The `predict_event_surge()` function accepts these 5 parameters (unchanged from the original API):

| Parameter | Maps To | Notes |
|---|---|---|
| `hour_of_day` | `hour_of_day` | Direct mapping |
| `is_weekend` | `is_weekend` | Direct mapping |
| `event_size_nearby` | — | Not a training feature; accepted for API compatibility |
| `current_traffic_congestion_pct` | — | Not a training feature; accepted for API compatibility |
| `scheduled_headway_min` | — | Not a training feature; accepted for API compatibility |

At inference time, `day_of_week`, `month`, and `is_rush_hour` are derived from the current system clock and the provided `hour_of_day`.

---

## Preprocessing

1. **Cleaning**: Drop rows with null timestamps or ridership ≤ 0
2. **Feature extraction**: Extract temporal features from `transit_timestamp`
3. **Target computation**: Compute per-station-hour-weekend median, divide actual by median
4. **Clipping**: Clip surge multiplier to [1.0, 4.5]
5. **No scaling/normalization**: Random Forest is invariant to feature scale

---

## Train/Test Methodology

### Chronological Split (No Data Leakage)

| Split | Fraction | Purpose |
|---|---|---|
| **Train** | 70% (earliest dates) | Model fitting |
| **Validation** | 15% (middle dates) | Hyperparameter tuning, baseline comparison |
| **Test** | 15% (latest dates) | Final held-out evaluation |

The split is **strictly chronological**: the training set contains only observations from earlier dates than the validation set, which in turn contains only earlier dates than the test set. This prevents temporal data leakage.

---

## Model Architecture

| Property | Value |
|---|---|
| **Algorithm** | `sklearn.ensemble.RandomForestRegressor` |
| **n_estimators** | 100 |
| **max_depth** | 10 |
| **min_samples_split** | 5 |
| **min_samples_leaf** | 3 |
| **random_state** | 42 |
| **n_jobs** | -1 (all cores) |

### Why Random Forest?

1. **Existing architecture** — The original codebase already used RandomForestRegressor
2. **No feature scaling required** — Simplifies the inference pipeline
3. **Feature importance** — Provides interpretable feature contributions
4. **Robustness** — Handles non-linear relationships without overfitting
5. **Fast inference** — Sub-millisecond prediction latency

---

## Evaluation Metrics

Metrics are computed on the held-out **test set** (chronologically latest 15% of data):

| Metric | Description |
|---|---|
| **MAE** | Mean Absolute Error — average prediction error magnitude |
| **RMSE** | Root Mean Squared Error — penalizes large errors |
| **R²** | Coefficient of determination — fraction of variance explained |

### Baseline Comparison

A `DummyRegressor(strategy="mean")` baseline is trained and evaluated on the same splits. The Random Forest model must outperform this baseline on all metrics to be considered valid.

---

## Saved Artifacts

| File | Description |
|---|---|
| `ml_models/surge_regressor.pkl` | Trained RandomForestRegressor model (joblib) |
| `ml_models/model_metadata.json` | Training date, metrics, dataset info, version |
| `ml_models/feature_config.json` | Feature ordering, defaults, valid ranges |
| `ml_models/mta_ridership_cache.csv` | Cached raw MTA data (avoids re-downloading) |

---

## Limitations

1. **Geographic scope**: Model trained on NYC subway data, not Indian bus transit. Temporal patterns (rush hours, weekend behavior) may differ.
2. **Missing features**: Event proximity, traffic congestion, and bus headway are not in the training data. The model cannot currently learn event-driven surges from data.
3. **Homogeneous stations**: The model does not differentiate between stations (no station embeddings). All predictions are based purely on temporal features.
4. **Fixed time window**: Trained on 2023 data only. Seasonal patterns from other years are not captured.
5. **Surge ceiling**: The target is clipped to [1.0, 4.5], which may under-represent extreme outlier events.

---

## How to Retrain the Model

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run Training
```bash
cd backend
python prediction/train_model.py
```

This will:
1. Download MTA ridership data (or use cached version)
2. Engineer features and compute surge multiplier
3. Perform chronological train/val/test split
4. Train RandomForestRegressor
5. Evaluate against baseline
6. Save model, metadata, and feature config

### Force Fresh Download
Delete the cache file to re-download data:
```bash
rm prediction/ml_models/mta_ridership_cache.csv
python prediction/train_model.py
```

### Retrain with Custom Data
Modify `train_model.py`:
- Replace `download_mta_data()` with a function that loads your city's data
- Ensure the DataFrame has columns: `transit_timestamp`, `total_ridership`, `station_complex_id`
- The rest of the pipeline (feature engineering, training, evaluation) works unchanged

---

## How E_event Connects to the M/M/c Prediction Engine

```
┌─────────────────────┐
│  train_model.py     │  (Training time — offline)
│  NYC MTA Data →     │
│  RandomForest →     │
│  surge_regressor.pkl│
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  surge_model.py     │  (Inference time — per-request)
│  predict_event_surge│
│  → returns E_event  │
│    (float 1.0-4.5)  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  queue_dynamics.py                          │
│  QueueDynamicsEngine                        │
│                                             │
│  e_event = predict_event_surge(hour, ...)   │
│                                             │
│  net_rate = λ_base × E_event − μ_boarding   │
│  Crowd(t+Δt) = max(0, Crowd(t) + net × Δt) │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  api_prediction_views.py                    │
│  EarlyWarningView.get()                     │
│  → JSON response with stations, warnings,   │
│    e_event, lambda_base, mu_boarding, etc.  │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  PredictionsDashboard.tsx (React Frontend)  │
│  Fetches /api/v1/predictions/early-warnings │
│  Displays M/M/c parameters, surge values,  │
│  station alerts, and capacity forecasts     │
└─────────────────────────────────────────────┘
```
