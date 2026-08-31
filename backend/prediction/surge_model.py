import os
import json
import logging
import joblib
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor

log = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "ml_models"
MODEL_PATH = MODEL_DIR / "surge_regressor.pkl"
FEATURE_CONFIG_PATH = MODEL_DIR / "feature_config.json"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

# ---------------------------------------------------------------------------
# Feature configuration
# ---------------------------------------------------------------------------

# Default training features (used if feature_config.json is missing)
DEFAULT_TRAINING_FEATURES = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "month",
    "is_rush_hour",
]

SURGE_MIN = 1.0
SURGE_MAX = 4.5

# Valid ranges for input validation
FEATURE_VALID_RANGES = {
    "hour_of_day": (0, 23),
    "day_of_week": (0, 6),
    "is_weekend": (0, 1),
    "month": (1, 12),
    "is_rush_hour": (0, 1),
    "event_size_nearby": (0, 3),
    "current_traffic_congestion_pct": (0.0, 100.0),
    "scheduled_headway_min": (1.0, 60.0),
}


def _load_feature_config():
    """Loads feature_config.json if it exists, else returns defaults."""
    if FEATURE_CONFIG_PATH.exists():
        try:
            with open(FEATURE_CONFIG_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Failed to load feature config: {e}. Using defaults.")
    return None


def _validate_and_clamp(value, name, default=None):
    """
    Validates a single feature value. If invalid or None, returns the
    clamped/default value. Logs a warning on correction.
    """
    if value is None:
        if default is not None:
            log.debug(f"Feature '{name}' is None, using default={default}")
            return float(default)
        return 0.0

    value = float(value)
    if name in FEATURE_VALID_RANGES:
        lo, hi = FEATURE_VALID_RANGES[name]
        if value < lo or value > hi:
            clamped = max(lo, min(hi, value))
            log.debug(f"Feature '{name}'={value} out of range [{lo}, {hi}], clamped to {clamped}")
            return float(clamped)

    return float(value)


# ---------------------------------------------------------------------------
# Synthetic fallback (legacy, used only when no .pkl exists)
# ---------------------------------------------------------------------------

def _generate_synthetic_training_data(n_samples=1000, seed=42):
    """
    Generates 1,000 synthetic rows with columns:
    [hour_of_day, is_weekend, event_size_nearby, current_traffic_congestion_pct, scheduled_headway_min]
    Target: predicted_passenger_surge_factor (E_event)

    NOTE: This is a SYNTHETIC FALLBACK only used when the real-data-trained
    model file is missing. It is NOT used in production.
    """
    np.random.seed(seed)

    hour_of_day = np.random.randint(0, 24, size=n_samples)
    is_weekend = np.random.binomial(1, 0.28, size=n_samples)
    event_size_nearby = np.random.choice([0, 1, 2, 3], p=[0.75, 0.15, 0.07, 0.03], size=n_samples)
    current_traffic_congestion_pct = np.random.uniform(5.0, 95.0, size=n_samples)
    scheduled_headway_min = np.random.uniform(5.0, 30.0, size=n_samples)

    peak_morning = np.exp(-((hour_of_day - 9.0) ** 2) / 4.0) * (1.0 - 0.4 * is_weekend)
    peak_evening = np.exp(-((hour_of_day - 18.0) ** 2) / 6.0)
    event_boost = event_size_nearby * 0.85
    congestion_boost = (current_traffic_congestion_pct / 100.0) * 0.4
    headway_boost = (scheduled_headway_min / 30.0) * 0.25
    noise = np.random.normal(0.0, 0.05, size=n_samples)

    surge_factor = 1.0 + (0.6 * peak_morning) + (0.8 * peak_evening) + event_boost + congestion_boost + headway_boost + noise
    surge_factor = np.clip(surge_factor, SURGE_MIN, SURGE_MAX)

    X = np.column_stack([
        hour_of_day,
        is_weekend,
        event_size_nearby,
        current_traffic_congestion_pct,
        scheduled_headway_min
    ])
    return X, surge_factor


def _train_synthetic_fallback():
    """Trains a synthetic fallback model and saves it. Logs a clear warning."""
    log.warning(
        "=" * 60 + "\n"
        "WARNING: Training SYNTHETIC FALLBACK model.\n"
        "The real-data-trained model was not found at:\n"
        f"  {MODEL_PATH}\n"
        "Run 'python prediction/train_model.py' to train on real data.\n"
        + "=" * 60
    )
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y = _generate_synthetic_training_data(n_samples=1000)

    model = RandomForestRegressor(
        n_estimators=60,
        max_depth=8,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)

    # Save a minimal feature config for the synthetic model
    # (uses the legacy 5-feature direct mapping)
    synthetic_config = {
        "training_features": [
            "hour_of_day", "is_weekend", "event_size_nearby",
            "current_traffic_congestion_pct", "scheduled_headway_min"
        ],
        "inference_features": [
            "hour_of_day", "is_weekend", "event_size_nearby",
            "current_traffic_congestion_pct", "scheduled_headway_min"
        ],
        "model_type": "synthetic_fallback",
        "surge_range": [SURGE_MIN, SURGE_MAX],
    }
    with open(FEATURE_CONFIG_PATH, "w") as f:
        json.dump(synthetic_config, f, indent=2)

    return model


# ---------------------------------------------------------------------------
# Model loading (cached singleton)
# ---------------------------------------------------------------------------

_cached_model = None
_cached_feature_config = None
_is_synthetic = False


def get_surge_model():
    """Loads the cached model or trains a synthetic fallback if not found."""
    global _cached_model, _cached_feature_config, _is_synthetic
    if _cached_model is not None:
        return _cached_model

    # Try loading the real-data-trained model
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            _cached_feature_config = _load_feature_config()
            _is_synthetic = (
                _cached_feature_config is not None
                and _cached_feature_config.get("model_type") == "synthetic_fallback"
            )
            if _is_synthetic:
                log.warning("Loaded SYNTHETIC fallback model. Run train_model.py for real data.")
            else:
                log.info("Loaded real-data-trained surge model.")
            return _cached_model
        except Exception as e:
            log.error(f"Failed to load model from {MODEL_PATH}: {e}")

    # Fallback: train synthetic
    _cached_model = _train_synthetic_fallback()
    _cached_feature_config = _load_feature_config()
    _is_synthetic = True
    return _cached_model


def get_model_metadata():
    """Returns model metadata dict, or None if not available."""
    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def get_feature_config():
    """Returns the feature configuration dict."""
    global _cached_feature_config
    if _cached_feature_config is None:
        _cached_feature_config = _load_feature_config()
    return _cached_feature_config


def is_synthetic_model():
    """Returns True if the currently loaded model is the synthetic fallback."""
    get_surge_model()  # Ensure model is loaded
    return _is_synthetic


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict_event_surge(
    hour_of_day=12,
    is_weekend=0,
    event_size_nearby=0,
    current_traffic_congestion_pct=30.0,
    scheduled_headway_min=15.0
):
    """
    Predicts the passenger surge factor E_event using the trained model.

    Parameters match the existing M/M/c queue engine interface exactly:
      - hour_of_day (int): 0-23
      - is_weekend (int): 0 or 1
      - event_size_nearby (int): 0-3 (none/small/medium/large)
      - current_traffic_congestion_pct (float): 0-100
      - scheduled_headway_min (float): bus headway in minutes

    Returns:
      float in range [1.0, 4.5]
    """
    model = get_surge_model()
    config = get_feature_config()

    # Validate inputs
    hour_of_day = _validate_and_clamp(hour_of_day, "hour_of_day", default=12)
    is_weekend = _validate_and_clamp(is_weekend, "is_weekend", default=0)
    event_size_nearby = _validate_and_clamp(event_size_nearby, "event_size_nearby", default=0)
    current_traffic_congestion_pct = _validate_and_clamp(
        current_traffic_congestion_pct, "current_traffic_congestion_pct", default=30.0
    )
    scheduled_headway_min = _validate_and_clamp(
        scheduled_headway_min, "scheduled_headway_min", default=15.0
    )

    # Determine which feature vector to build based on the loaded model type
    if config and config.get("model_type") != "synthetic_fallback":
        # Real-data model: trained on temporal features
        training_features = config.get("training_features", DEFAULT_TRAINING_FEATURES)

        # Derive training features from inference inputs
        hour = int(hour_of_day)
        from datetime import datetime as dt
        now = dt.now()
        day_of_week = now.weekday()  # Use actual current day
        month = now.month

        is_rush = 1 if hour in [7, 8, 9, 17, 18, 19] else 0

        feature_map = {
            "hour_of_day": hour,
            "day_of_week": day_of_week,
            "is_weekend": int(is_weekend),
            "month": month,
            "is_rush_hour": is_rush,
        }

        features = np.array([[
            float(feature_map.get(f, 0)) for f in training_features
        ]])
    else:
        # Synthetic fallback: uses the original 5 direct features
        features = np.array([[
            float(hour_of_day),
            float(is_weekend),
            float(event_size_nearby),
            float(current_traffic_congestion_pct),
            float(scheduled_headway_min)
        ]])

    pred = model.predict(features)[0]
    # Clamp to valid surge range
    pred = float(np.clip(pred, SURGE_MIN, SURGE_MAX))
    return round(pred, 2)


if __name__ == "__main__":
    m = get_surge_model()
    metadata = get_model_metadata()
    if metadata:
        print(f"Model version: {metadata.get('model_version', 'unknown')}")
        print(f"Dataset: {metadata.get('dataset', {}).get('name', 'unknown')}")
        print(f"Data type: {metadata.get('dataset', {}).get('data_type', 'unknown')}")
    else:
        print("No model metadata found (synthetic fallback)")

    print(f"Is synthetic: {is_synthetic_model()}")

    sample_surge = predict_event_surge(
        hour_of_day=18, is_weekend=0, event_size_nearby=2,
        current_traffic_congestion_pct=75.0, scheduled_headway_min=20.0
    )
    print(f"Sample prediction at 6 PM with nearby event & 75% traffic congestion: E_event = {sample_surge}")

    sample_quiet = predict_event_surge(
        hour_of_day=3, is_weekend=0, event_size_nearby=0,
        current_traffic_congestion_pct=10.0, scheduled_headway_min=15.0
    )
    print(f"Sample prediction at 3 AM quiet period: E_event = {sample_quiet}")
