import os
import joblib
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor

MODEL_DIR = Path(__file__).resolve().parent / "ml_models"
MODEL_PATH = MODEL_DIR / "surge_regressor.pkl"

def generate_synthetic_training_data(n_samples=1000, seed=42):
    """
    Generates 1,000 synthetic rows with columns:
    [hour_of_day, is_weekend, event_size_nearby, current_traffic_congestion_pct, scheduled_headway_min]
    Target: predicted_passenger_surge_factor (E_event)
    """
    np.random.seed(seed)
    
    # 1. hour_of_day: 0 to 23
    hour_of_day = np.random.randint(0, 24, size=n_samples)
    
    # 2. is_weekend: 0 or 1
    is_weekend = np.random.binomial(1, 0.28, size=n_samples)
    
    # 3. event_size_nearby: 0 (none), 1 (small/500-2k), 2 (medium/2k-10k), 3 (large/concert/10k+)
    event_size_nearby = np.random.choice([0, 1, 2, 3], p=[0.75, 0.15, 0.07, 0.03], size=n_samples)
    
    # 4. current_traffic_congestion_pct: 0.0 to 100.0%
    current_traffic_congestion_pct = np.random.uniform(5.0, 95.0, size=n_samples)
    
    # 5. scheduled_headway_min: 5 to 30 minutes
    scheduled_headway_min = np.random.uniform(5.0, 30.0, size=n_samples)
    
    # Synthetic target formula with realistic non-linear transit relationships:
    # Baseline multiplier = 1.0
    # Peak hours (8-10 AM, 5-8 PM) add 0.3 - 0.7
    # Weekend shifts peak to afternoon/evening
    # Events scale multiplier dramatically: +0.5 (small), +1.2 (medium), +2.5 (large)
    # Traffic congestion and headway delays cause passenger clustering surges
    
    peak_morning = np.exp(-((hour_of_day - 9.0) ** 2) / 4.0) * (1.0 - 0.4 * is_weekend)
    peak_evening = np.exp(-((hour_of_day - 18.0) ** 2) / 6.0)
    event_boost = event_size_nearby * 0.85
    congestion_boost = (current_traffic_congestion_pct / 100.0) * 0.4
    headway_boost = (scheduled_headway_min / 30.0) * 0.25
    noise = np.random.normal(0.0, 0.05, size=n_samples)
    
    surge_factor = 1.0 + (0.6 * peak_morning) + (0.8 * peak_evening) + event_boost + congestion_boost + headway_boost + noise
    surge_factor = np.clip(surge_factor, 1.0, 4.5)
    
    X = np.column_stack([
        hour_of_day,
        is_weekend,
        event_size_nearby,
        current_traffic_congestion_pct,
        scheduled_headway_min
    ])
    y = surge_factor
    
    return X, y

def train_and_save_model():
    """Trains the RandomForestRegressor and saves it to disk."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y = generate_synthetic_training_data(n_samples=1000)
    
    model = RandomForestRegressor(
        n_estimators=60,
        max_depth=8,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)
    return model

_cached_model = None

def get_surge_model():
    """Loads the cached model or trains a new one if not found."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    
    if MODEL_PATH.exists():
        try:
            _cached_model = joblib.load(MODEL_PATH)
            return _cached_model
        except Exception:
            pass
            
    _cached_model = train_and_save_model()
    return _cached_model

def predict_event_surge(hour_of_day=12, is_weekend=0, event_size_nearby=0, current_traffic_congestion_pct=30.0, scheduled_headway_min=15.0):
    """
    Predicts the passenger surge factor E_event using the trained Random Forest model.
    Returns float in range [1.0, 4.5]
    """
    model = get_surge_model()
    features = np.array([[
        float(hour_of_day),
        float(is_weekend),
        float(event_size_nearby),
        float(current_traffic_congestion_pct),
        float(scheduled_headway_min)
    ]])
    pred = model.predict(features)[0]
    return float(np.round(pred, 2))

if __name__ == "__main__":
    m = train_and_save_model()
    print(f"RandomForestRegressor trained and saved to {MODEL_PATH}")
    sample_surge = predict_event_surge(hour_of_day=18, is_weekend=0, event_size_nearby=2, current_traffic_congestion_pct=75.0, scheduled_headway_min=20.0)
    print(f"Sample prediction at 6 PM with nearby event & 75% traffic congestion: E_event = {sample_surge}")
