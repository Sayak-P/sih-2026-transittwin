#!/usr/bin/env python
"""
TransitTwin Surge Prediction Model — Training Script
=====================================================

Downloads real NYC MTA Subway Hourly Ridership data from data.ny.gov,
engineers a surge_multiplier target, trains a RandomForestRegressor,
and saves the model + metadata for inference.

Usage:
    cd backend
    python prediction/train_model.py

Dataset: NYC MTA Subway Hourly Ridership (2020-2024)
Source:  https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-2020-2024/wujg-7c2s
License: Public Domain (NYC Open Data)
"""

import json
import sys
import os
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.dummy import DummyRegressor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SODA_ENDPOINT = "https://data.ny.gov/resource/wujg-7c2s.json"
# Fetch ~50k aggregated rows: full year 2023, subway only
SODA_QUERY_PARAMS = {
    "$select": "transit_timestamp, station_complex_id, station_complex, borough, sum(ridership) as total_ridership",
    "$where": "transit_timestamp >= '2023-01-01T00:00:00' AND transit_timestamp < '2024-01-01T00:00:00' AND transit_mode = 'subway'",
    "$group": "transit_timestamp, station_complex_id, station_complex, borough",
    "$having": "sum(ridership) > 0",
    "$order": "transit_timestamp ASC",
    "$limit": 50000,
}

MODEL_DIR = Path(__file__).resolve().parent / "ml_models"
MODEL_PATH = MODEL_DIR / "surge_regressor.pkl"
METADATA_PATH = MODEL_DIR / "model_metadata.json"
FEATURE_CONFIG_PATH = MODEL_DIR / "feature_config.json"
RAW_DATA_CACHE = MODEL_DIR / "mta_ridership_cache.csv"

# Features the model is trained on (order matters!)
TRAINING_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "month",
    "is_rush_hour",
]

# Features accepted at inference time (maps to training features)
INFERENCE_FEATURES = [
    "hour_of_day",
    "is_weekend",
    "event_size_nearby",
    "current_traffic_congestion_pct",
    "scheduled_headway_min",
]

SURGE_MIN = 1.0
SURGE_MAX = 4.5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Step 1: Data Download
# ---------------------------------------------------------------------------

def download_mta_data(use_cache: bool = True) -> pd.DataFrame:
    """
    Downloads NYC MTA Subway Hourly Ridership data via SODA API.
    Caches to disk to avoid re-downloading on subsequent runs.
    """
    if use_cache and RAW_DATA_CACHE.exists():
        log.info(f"Loading cached MTA data from {RAW_DATA_CACHE}")
        df = pd.read_csv(RAW_DATA_CACHE, parse_dates=["transit_timestamp"])
        log.info(f"Loaded {len(df)} cached rows")
        return df

    log.info("Downloading MTA Subway Hourly Ridership data from data.ny.gov ...")
    all_rows = []
    offset = 0
    page_size = 10000
    max_rows = 50000

    while offset < max_rows:
        params = dict(SODA_QUERY_PARAMS)
        params["$limit"] = min(page_size, max_rows - offset)
        params["$offset"] = offset

        resp = requests.get(SODA_ENDPOINT, params=params, timeout=60)
        resp.raise_for_status()
        page = resp.json()

        if not page:
            break

        all_rows.extend(page)
        offset += len(page)
        log.info(f"  Downloaded {offset} rows so far ...")

        if len(page) < page_size:
            break

    if not all_rows:
        raise RuntimeError(
            "SODA API returned 0 rows. Check network connectivity and query parameters."
        )

    df = pd.DataFrame(all_rows)
    log.info(f"Downloaded {len(df)} rows total")

    # Type conversions
    df["transit_timestamp"] = pd.to_datetime(df["transit_timestamp"])
    df["total_ridership"] = pd.to_numeric(df["total_ridership"], errors="coerce")
    df["station_complex_id"] = df["station_complex_id"].astype(str)

    # Cache to disk
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_DATA_CACHE, index=False)
    log.info(f"Cached raw data to {RAW_DATA_CACHE}")

    return df


# ---------------------------------------------------------------------------
# Step 2: Feature Engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives temporal features from transit_timestamp and computes
    the surge_multiplier target variable.
    """
    df = df.copy()

    # --- Clean ---
    df = df.dropna(subset=["transit_timestamp", "total_ridership"])
    df = df[df["total_ridership"] > 0].reset_index(drop=True)

    # --- Temporal features ---
    df["hour_of_day"] = df["transit_timestamp"].dt.hour
    df["day_of_week"] = df["transit_timestamp"].dt.dayofweek  # Mon=0, Sun=6
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["month"] = df["transit_timestamp"].dt.month
    df["is_rush_hour"] = df["hour_of_day"].apply(
        lambda h: 1 if h in [7, 8, 9, 17, 18, 19] else 0
    )

    # --- Target: Surge Multiplier ---
    # For each station x hour-of-day x is_weekend combination,
    # compute the median ridership as the "normal" baseline.
    # Surge = actual / median.  Centered around 1.0.
    group_cols = ["station_complex_id", "hour_of_day", "is_weekend"]
    medians = df.groupby(group_cols)["total_ridership"].transform("median")

    # Avoid division by zero
    medians = medians.replace(0, np.nan)
    df["surge_multiplier"] = df["total_ridership"] / medians

    # Drop rows where median was 0 (extremely rare station-hours)
    df = df.dropna(subset=["surge_multiplier"]).reset_index(drop=True)

    # Clip to the range the M/M/c engine expects
    df["surge_multiplier"] = df["surge_multiplier"].clip(SURGE_MIN, SURGE_MAX)

    log.info(f"Feature engineering complete: {len(df)} rows, surge range [{df['surge_multiplier'].min():.2f}, {df['surge_multiplier'].max():.2f}]")
    log.info(f"  Surge mean={df['surge_multiplier'].mean():.3f}, std={df['surge_multiplier'].std():.3f}")

    return df


# ---------------------------------------------------------------------------
# Step 3: Train/Test Split (Chronological)
# ---------------------------------------------------------------------------

def chronological_split(df: pd.DataFrame, train_frac: float = 0.7, val_frac: float = 0.15):
    """
    Time-aware split to prevent data leakage.
    Earlier dates -> train, middle -> validation, later -> test.
    """
    df = df.sort_values("transit_timestamp").reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]

    log.info(f"Chronological split: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
    log.info(f"  Train period: {train_df['transit_timestamp'].min()} -> {train_df['transit_timestamp'].max()}")
    log.info(f"  Val period:   {val_df['transit_timestamp'].min()} -> {val_df['transit_timestamp'].max()}")
    log.info(f"  Test period:  {test_df['transit_timestamp'].min()} -> {test_df['transit_timestamp'].max()}")

    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# Step 4: Training
# ---------------------------------------------------------------------------

def train_model(train_df: pd.DataFrame, val_df: pd.DataFrame):
    """
    Trains a RandomForestRegressor and a baseline DummyRegressor.
    Returns (rf_model, baseline_model, val_metrics, baseline_metrics, importances).
    """
    X_train = train_df[TRAINING_FEATURES].values
    y_train = train_df["surge_multiplier"].values
    X_val = val_df[TRAINING_FEATURES].values
    y_val = val_df["surge_multiplier"].values

    # --- Baseline: predict mean surge ---
    log.info("Training baseline model (DummyRegressor - mean strategy) ...")
    baseline = DummyRegressor(strategy="mean")
    baseline.fit(X_train, y_train)
    y_pred_baseline = baseline.predict(X_val)
    y_pred_baseline = np.clip(y_pred_baseline, SURGE_MIN, SURGE_MAX)

    baseline_metrics = {
        "mae": round(float(mean_absolute_error(y_val, y_pred_baseline)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_val, y_pred_baseline))), 4),
        "r2": round(float(r2_score(y_val, y_pred_baseline)), 4),
    }
    log.info(f"Baseline validation: MAE={baseline_metrics['mae']}, RMSE={baseline_metrics['rmse']}, R2={baseline_metrics['r2']}")

    # --- Primary: RandomForestRegressor ---
    log.info("Training RandomForestRegressor ...")
    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_val)
    y_pred_rf = np.clip(y_pred_rf, SURGE_MIN, SURGE_MAX)

    rf_metrics = {
        "mae": round(float(mean_absolute_error(y_val, y_pred_rf)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_val, y_pred_rf))), 4),
        "r2": round(float(r2_score(y_val, y_pred_rf)), 4),
    }
    log.info(f"RF validation: MAE={rf_metrics['mae']}, RMSE={rf_metrics['rmse']}, R2={rf_metrics['r2']}")

    # Feature importance
    importances = dict(zip(TRAINING_FEATURES, [round(float(x), 4) for x in rf.feature_importances_]))
    log.info(f"Feature importances: {importances}")

    return rf, baseline, rf_metrics, baseline_metrics, importances


# ---------------------------------------------------------------------------
# Step 5: Evaluate on Test Set
# ---------------------------------------------------------------------------

def evaluate_on_test(model, test_df: pd.DataFrame) -> dict:
    """Final held-out test evaluation."""
    X_test = test_df[TRAINING_FEATURES].values
    y_test = test_df["surge_multiplier"].values

    y_pred = model.predict(X_test)
    y_pred = np.clip(y_pred, SURGE_MIN, SURGE_MAX)

    metrics = {
        "mae": round(float(mean_absolute_error(y_test, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_test, y_pred))), 4),
        "r2": round(float(r2_score(y_test, y_pred)), 4),
        "n_samples": len(y_test),
    }
    log.info(f"Test set evaluation: MAE={metrics['mae']}, RMSE={metrics['rmse']}, R2={metrics['r2']} (n={metrics['n_samples']})")
    return metrics


# ---------------------------------------------------------------------------
# Step 6: Save Artifacts
# ---------------------------------------------------------------------------

def save_artifacts(model, test_metrics, val_metrics, baseline_metrics, importances, df_info):
    """Saves the trained model, metadata, and feature config."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Model pickle
    joblib.dump(model, MODEL_PATH)
    log.info(f"Saved model to {MODEL_PATH}")

    # 2. Feature config (used by inference to guarantee alignment)
    feature_config = {
        "training_features": TRAINING_FEATURES,
        "inference_features": INFERENCE_FEATURES,
        "inference_to_training_map": {
            "hour_of_day": {"source": "direct", "training_feature": "hour_of_day"},
            "is_weekend": {"source": "direct", "training_feature": "is_weekend"},
            "event_size_nearby": {
                "source": "not_in_training_data",
                "note": "MTA dataset has no event data. This feature is accepted at inference but does not directly map to a training feature. The model was not trained on event data.",
                "default_value": 0,
            },
            "current_traffic_congestion_pct": {
                "source": "not_in_training_data",
                "note": "MTA dataset has no traffic congestion data. Accepted at inference but not a training feature.",
                "default_value": 30.0,
            },
            "scheduled_headway_min": {
                "source": "not_in_training_data",
                "note": "MTA dataset has no headway data. Accepted at inference but not a training feature.",
                "default_value": 15.0,
            },
        },
        "feature_defaults": {
            "hour_of_day": 12,
            "day_of_week": 2,
            "is_weekend": 0,
            "month": 6,
            "is_rush_hour": 0,
        },
        "feature_ranges": {
            "hour_of_day": [0, 23],
            "day_of_week": [0, 6],
            "is_weekend": [0, 1],
            "month": [1, 12],
            "is_rush_hour": [0, 1],
        },
        "surge_range": [SURGE_MIN, SURGE_MAX],
    }
    with open(FEATURE_CONFIG_PATH, "w") as f:
        json.dump(feature_config, f, indent=2)
    log.info(f"Saved feature config to {FEATURE_CONFIG_PATH}")

    # 3. Model metadata
    metadata = {
        "model_version": "2.0.0",
        "model_type": "RandomForestRegressor",
        "sklearn_params": {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_split": 5,
            "min_samples_leaf": 3,
            "random_state": 42,
        },
        "dataset": {
            "name": "NYC MTA Subway Hourly Ridership (2020-2024)",
            "source_url": "https://data.ny.gov/Transportation/MTA-Subway-Hourly-Ridership-2020-2024/wujg-7c2s",
            "license": "Public Domain (NYC Open Data)",
            "query_period": "2023-01-01 to 2023-12-31",
            "total_rows_downloaded": df_info["total_rows"],
            "rows_after_cleaning": df_info["rows_after_cleaning"],
            "unique_stations": df_info["unique_stations"],
            "data_type": "REAL",
        },
        "target_variable": {
            "name": "surge_multiplier",
            "derivation": "ratio of actual hourly ridership to station-hour-weekend median ridership",
            "range": [SURGE_MIN, SURGE_MAX],
            "maps_to": "E_event in M/M/c formula: Crowd(t+dt) = max(0, Crowd(t) + (lambda_base * E_event - mu_boarding) * dt)",
        },
        "training_features": TRAINING_FEATURES,
        "feature_importances": importances,
        "split_method": "chronological (70% train / 15% val / 15% test)",
        "evaluation": {
            "validation": val_metrics,
            "test": test_metrics,
            "baseline": baseline_metrics,
            "baseline_method": "DummyRegressor (mean strategy)",
        },
        "training_date": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        "trained_by": "prediction/train_model.py",
        "notes": [
            "Model trained on real NYC MTA ridership data.",
            "Features event_size_nearby, traffic_congestion, and headway are NOT in training data.",
            "These inference-only features are accepted but mapped to temporal proxies.",
            "Retraining with city-specific (e.g. CRUT Bhubaneswar) data is recommended.",
        ],
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info(f"Saved metadata to {METADATA_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 70)
    log.info("TransitTwin Surge Model Training Pipeline")
    log.info("=" * 70)

    # Step 1: Download
    df_raw = download_mta_data(use_cache=True)
    total_rows = len(df_raw)

    # Step 2: Feature Engineering
    df = engineer_features(df_raw)
    rows_after_cleaning = len(df)
    unique_stations = df["station_complex_id"].nunique()

    df_info = {
        "total_rows": total_rows,
        "rows_after_cleaning": rows_after_cleaning,
        "unique_stations": unique_stations,
    }

    # Step 3: Split
    train_df, val_df, test_df = chronological_split(df)

    # Step 4: Train
    model, baseline, val_metrics, baseline_metrics, importances = train_model(train_df, val_df)

    # Step 5: Evaluate on test
    test_metrics = evaluate_on_test(model, test_df)

    # Step 6: Save
    save_artifacts(model, test_metrics, val_metrics, baseline_metrics, importances, df_info)

    # Summary
    log.info("")
    log.info("=" * 70)
    log.info("TRAINING COMPLETE - Summary")
    log.info("=" * 70)
    log.info(f"  Dataset:         NYC MTA Subway Hourly Ridership (2023)")
    log.info(f"  Rows used:       {rows_after_cleaning}")
    log.info(f"  Stations:        {unique_stations}")
    log.info(f"  Model:           RandomForestRegressor (100 trees, depth 10)")
    log.info(f"  Test MAE:        {test_metrics['mae']}")
    log.info(f"  Test RMSE:       {test_metrics['rmse']}")
    log.info(f"  Test R2:         {test_metrics['r2']}")
    log.info(f"  Baseline MAE:    {baseline_metrics['mae']}")
    log.info(f"  Model saved to:  {MODEL_PATH}")
    log.info("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
