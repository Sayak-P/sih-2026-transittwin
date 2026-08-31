import json
import pytest
import numpy as np
from pathlib import Path
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from core.models import Stop
from prediction.models import ODDemand
from simulation.state.live_state import LiveStateEngine
from prediction.surge_model import (
    predict_event_surge,
    get_surge_model,
    get_model_metadata,
    get_feature_config,
    is_synthetic_model,
    MODEL_DIR,
    MODEL_PATH,
    FEATURE_CONFIG_PATH,
    METADATA_PATH,
    SURGE_MIN,
    SURGE_MAX,
)


# ===================================================================
# Existing Tests (preserved from original tests.py)
# ===================================================================

@pytest.mark.django_db
class TestPredictionEarlyWarning:
    def setup_method(self):
        self.client = APIClient()
        self.now = timezone.now()

        # Create Stops
        self.stop_normal = Stop.objects.create(name="Normal Stop", lat=0, lon=0, capacity=100)
        self.stop_warning = Stop.objects.create(name="Warning Stop", lat=0, lon=0, capacity=100)
        self.stop_critical = Stop.objects.create(name="Critical Stop", lat=0, lon=0, capacity=100)

        # Populate demands
        ODDemand.objects.create(
            origin_stop=self.stop_normal,
            destination_stop=self.stop_critical,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=10
        )

        ODDemand.objects.create(
            origin_stop=self.stop_warning,
            destination_stop=self.stop_critical,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=85
        )

        ODDemand.objects.create(
            origin_stop=self.stop_critical,
            destination_stop=self.stop_normal,
            time_window_start=self.now,
            time_window_end=self.now + timedelta(minutes=10),
            expected_passenger_count=110
        )

        # Clear LiveState to ensure clean slate
        from django.core.cache import cache
        cache.clear()

    def test_prediction_thresholds(self):
        from core.models import Disruption
        # Create disruption near critical stop to drop boarding throughput mu_boarding to 0
        Disruption.objects.create(
            affected_stop=self.stop_critical,
            disruption_type="ROAD_BLOCK",
            severity="CRITICAL",
            start_time=self.now,
            is_active=True
        )

        response = self.client.get('/api/v1/predictions/early-warnings/')
        assert response.status_code == 200
        data = response.json()

        assert "stations" in data
        assert len(data["stations"]) > 0

        # Check critical stop has CRITICAL severity
        st_crit = next((s for s in data["stations"] if s["id"] == self.stop_critical.id), None)
        assert st_crit is not None
        assert st_crit["severity"] == "CRITICAL"
        assert st_crit["mu_boarding"] == 0.0

    def test_live_state_queue_integration(self):
        from core.models import Disruption
        Disruption.objects.create(
            affected_stop=self.stop_normal,
            disruption_type="ROAD_BLOCK",
            severity="HIGH",
            start_time=self.now,
            is_active=True
        )
        # Add 90 people to the queue of the Normal stop via LiveStateEngine
        LiveStateEngine.update_stop_state(str(self.stop_normal.id), {
            "queue_count": 90
        })

        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()
        assert "stations" in data

        st_norm = next((s for s in data["stations"] if s["id"] == self.stop_normal.id), None)
        assert st_norm is not None
        assert st_norm["current_queue"] == 90
        assert st_norm["severity"] in ["CRITICAL", "WARNING"]


# ===================================================================
# New Tests: Model Loading and Integrity
# ===================================================================

class TestModelLoading:
    """Tests that the ML model loads correctly and is the right type."""

    def test_model_loads_successfully(self):
        """Model .pkl loads and is a RandomForestRegressor."""
        from sklearn.ensemble import RandomForestRegressor
        model = get_surge_model()
        assert model is not None
        assert isinstance(model, RandomForestRegressor), (
            f"Expected RandomForestRegressor, got {type(model).__name__}"
        )

    def test_model_file_exists(self):
        """The model pickle file exists on disk (or is created by fallback)."""
        # Trigger model loading (creates fallback if missing)
        get_surge_model()
        assert MODEL_PATH.exists(), f"Model file not found at {MODEL_PATH}"

    def test_model_has_estimators(self):
        """Model has the expected number of estimators."""
        model = get_surge_model()
        assert hasattr(model, 'n_estimators')
        assert model.n_estimators > 0


# ===================================================================
# New Tests: Predictions
# ===================================================================

class TestPredictions:
    """Tests that the predict_event_surge function works correctly."""

    def test_valid_feature_vector_produces_prediction(self):
        """Standard inputs produce a valid float prediction."""
        result = predict_event_surge(
            hour_of_day=12,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=30.0,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_range_peak_hour(self):
        """Rush hour prediction stays within valid surge range."""
        result = predict_event_surge(
            hour_of_day=18,
            is_weekend=0,
            event_size_nearby=2,
            current_traffic_congestion_pct=85.0,
            scheduled_headway_min=25.0
        )
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_range_quiet_hour(self):
        """Off-peak prediction stays within valid surge range."""
        result = predict_event_surge(
            hour_of_day=3,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=10.0,
            scheduled_headway_min=10.0
        )
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_range_weekend(self):
        """Weekend prediction stays within valid surge range."""
        result = predict_event_surge(
            hour_of_day=14,
            is_weekend=1,
            event_size_nearby=1,
            current_traffic_congestion_pct=40.0,
            scheduled_headway_min=15.0
        )
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_extreme_congestion(self):
        """Maximum congestion still produces a bounded prediction."""
        result = predict_event_surge(
            hour_of_day=8,
            is_weekend=0,
            event_size_nearby=3,
            current_traffic_congestion_pct=100.0,
            scheduled_headway_min=30.0
        )
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_all_zeros(self):
        """All-zero inputs produce a valid prediction (edge case)."""
        result = predict_event_surge(
            hour_of_day=0,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=0.0,
            scheduled_headway_min=1.0
        )
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_prediction_returns_two_decimal_places(self):
        """Prediction is rounded to 2 decimal places."""
        result = predict_event_surge(hour_of_day=12)
        # Check that it has at most 2 decimal places
        assert result == round(result, 2)

    def test_multiple_predictions_deterministic(self):
        """Same inputs produce same outputs (deterministic model)."""
        kwargs = dict(
            hour_of_day=9,
            is_weekend=0,
            event_size_nearby=1,
            current_traffic_congestion_pct=50.0,
            scheduled_headway_min=15.0
        )
        r1 = predict_event_surge(**kwargs)
        r2 = predict_event_surge(**kwargs)
        assert r1 == r2


# ===================================================================
# New Tests: Input Validation
# ===================================================================

class TestInputValidation:
    """Tests that invalid/missing inputs are handled gracefully."""

    def test_none_hour_uses_default(self):
        """None hour_of_day defaults to 12 without crashing."""
        result = predict_event_surge(
            hour_of_day=None,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=30.0,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_negative_hour_clamped(self):
        """Negative hour_of_day is clamped to 0."""
        result = predict_event_surge(
            hour_of_day=-5,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=30.0,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_excessive_hour_clamped(self):
        """Hour > 23 is clamped to 23."""
        result = predict_event_surge(
            hour_of_day=50,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=30.0,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_none_congestion_uses_default(self):
        """None congestion defaults without crashing."""
        result = predict_event_surge(
            hour_of_day=12,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=None,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX

    def test_negative_congestion_clamped(self):
        """Negative congestion is clamped to 0."""
        result = predict_event_surge(
            hour_of_day=12,
            is_weekend=0,
            event_size_nearby=0,
            current_traffic_congestion_pct=-20.0,
            scheduled_headway_min=15.0
        )
        assert isinstance(result, float)
        assert SURGE_MIN <= result <= SURGE_MAX


# ===================================================================
# New Tests: Feature Configuration Alignment
# ===================================================================

class TestFeatureConfig:
    """Tests that feature configuration exists and is consistent."""

    def test_feature_config_file_exists(self):
        """feature_config.json exists after model is loaded."""
        get_surge_model()  # Ensure model + config are created
        assert FEATURE_CONFIG_PATH.exists(), f"Feature config not found at {FEATURE_CONFIG_PATH}"

    def test_feature_config_has_required_keys(self):
        """Feature config contains the required structural keys."""
        get_surge_model()
        config = get_feature_config()
        assert config is not None, "Feature config returned None"
        assert "training_features" in config, "Missing 'training_features' key"
        assert "inference_features" in config, "Missing 'inference_features' key"
        assert "surge_range" in config, "Missing 'surge_range' key"

    def test_feature_config_training_features_are_list(self):
        """training_features is a non-empty list of strings."""
        get_surge_model()
        config = get_feature_config()
        tf = config["training_features"]
        assert isinstance(tf, list)
        assert len(tf) > 0
        assert all(isinstance(f, str) for f in tf)

    def test_feature_ordering_matches_model(self):
        """The number of training features matches model's n_features_in_."""
        model = get_surge_model()
        config = get_feature_config()
        training_features = config["training_features"]
        if hasattr(model, 'n_features_in_'):
            assert model.n_features_in_ == len(training_features), (
                f"Model expects {model.n_features_in_} features but config has {len(training_features)}"
            )

    def test_surge_range_valid(self):
        """Surge range is [1.0, 4.5]."""
        get_surge_model()
        config = get_feature_config()
        sr = config["surge_range"]
        assert sr[0] == SURGE_MIN
        assert sr[1] == SURGE_MAX


# ===================================================================
# New Tests: Model Metadata
# ===================================================================

class TestModelMetadata:
    """Tests that model_metadata.json is valid and contains key information."""

    def test_metadata_exists_or_is_synthetic(self):
        """Metadata file exists for real models, or is_synthetic is True."""
        get_surge_model()
        if not is_synthetic_model():
            assert METADATA_PATH.exists(), "Real model should have model_metadata.json"
        # For synthetic, metadata is optional

    def test_metadata_has_required_fields(self):
        """If metadata exists, it has the required fields."""
        metadata = get_model_metadata()
        if metadata is not None:
            required_keys = ["model_version", "model_type", "training_features"]
            for key in required_keys:
                assert key in metadata, f"Metadata missing required key: {key}"

    def test_metadata_has_evaluation_metrics(self):
        """If metadata exists, it contains evaluation metrics."""
        metadata = get_model_metadata()
        if metadata is not None and "evaluation" in metadata:
            eval_data = metadata["evaluation"]
            if "test" in eval_data:
                test_metrics = eval_data["test"]
                assert "mae" in test_metrics, "Test metrics missing MAE"
                assert "rmse" in test_metrics, "Test metrics missing RMSE"
                assert "r2" in test_metrics, "Test metrics missing R2"

    def test_metadata_dataset_info(self):
        """If metadata exists, it documents the dataset used."""
        metadata = get_model_metadata()
        if metadata is not None and "dataset" in metadata:
            ds = metadata["dataset"]
            assert "name" in ds, "Dataset info missing name"
            assert "data_type" in ds, "Dataset info missing data_type"
            assert ds["data_type"] in ["REAL", "SYNTHETIC"], (
                f"Unexpected data_type: {ds['data_type']}"
            )


# ===================================================================
# New Tests: API Integration
# ===================================================================

@pytest.mark.django_db
class TestEarlyWarningAPI:
    """Tests that the early-warning API returns valid prediction data."""

    def setup_method(self):
        self.client = APIClient()
        # Create at least one active stop
        Stop.objects.create(name="API Test Stop", lat=0, lon=0, capacity=100, is_active=True)
        from django.core.cache import cache
        cache.clear()

    def test_api_returns_200(self):
        """GET /api/v1/predictions/early-warnings/ returns 200."""
        response = self.client.get('/api/v1/predictions/early-warnings/')
        assert response.status_code == 200

    def test_api_response_structure(self):
        """API response contains the expected top-level keys."""
        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()

        # Top-level keys expected by the frontend
        assert "timestamp" in data
        assert "system_health" in data
        assert "active_predictions_count" in data
        assert "critical_alerts_count" in data
        assert "stations" in data
        assert "warnings" in data
        assert "vehicle_delays" in data

    def test_api_stations_have_e_event(self):
        """Each station in the response has an e_event value."""
        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()

        for station in data.get("stations", []):
            assert "e_event" in station, f"Station {station.get('name')} missing e_event"
            assert isinstance(station["e_event"], (int, float))
            assert SURGE_MIN <= station["e_event"] <= SURGE_MAX

    def test_api_stations_have_mmc_params(self):
        """Each station has the M/M/c queue parameters."""
        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()

        for station in data.get("stations", []):
            assert "lambda_base" in station
            assert "mu_boarding" in station
            assert "net_arrival_rate" in station
            assert "predicted_crowd_15m" in station
            assert "crowding_ratio" in station

    def test_api_warnings_structure(self):
        """Warnings have the expected structure for the frontend."""
        response = self.client.get('/api/v1/predictions/early-warnings/')
        data = response.json()

        for w in data.get("warnings", []):
            assert "stop_id" in w
            assert "stop_name" in w
            assert "severity" in w
            assert w["severity"] in ["CRITICAL", "WARNING"]
            assert "e_event" in w
            assert "lambda_base" in w
            assert "mu_boarding" in w
            assert "explanation" in w

    def test_api_accepts_query_params(self):
        """API accepts horizon and dt query parameters."""
        response = self.client.get('/api/v1/predictions/early-warnings/?horizon=30&dt=10')
        assert response.status_code == 200


# ===================================================================
# New Tests: No Data Leakage (Documented)
# ===================================================================

class TestNoDataLeakage:
    """
    Verifies that the training pipeline uses a chronological split,
    preventing future data from leaking into training.

    Note: This test validates the training script's split function
    directly. The actual model is trained by train_model.py, not
    during test execution.
    """

    def test_chronological_split_preserves_time_order(self):
        """
        The chronological_split function ensures train data
        is strictly before validation data, which is strictly
        before test data.
        """
        import pandas as pd
        from prediction.train_model import chronological_split

        # Create a simple time-ordered DataFrame
        dates = pd.date_range("2023-01-01", periods=100, freq="h")
        df = pd.DataFrame({
            "transit_timestamp": dates,
            "hour_of_day": dates.hour,
            "day_of_week": dates.dayofweek,
            "is_weekend": (dates.dayofweek >= 5).astype(int),
            "month": dates.month,
            "is_rush_hour": [1 if h in [7, 8, 9, 17, 18, 19] else 0 for h in dates.hour],
            "surge_multiplier": np.random.uniform(1.0, 2.5, 100),
        })

        train, val, test = chronological_split(df, train_frac=0.7, val_frac=0.15)

        # Train max timestamp < Val min timestamp
        assert train["transit_timestamp"].max() < val["transit_timestamp"].min(), (
            "Data leakage: train data overlaps with validation data!"
        )

        # Val max timestamp < Test min timestamp
        assert val["transit_timestamp"].max() < test["transit_timestamp"].min(), (
            "Data leakage: validation data overlaps with test data!"
        )

    def test_chronological_split_sizes(self):
        """Split preserves approximate ratios."""
        import pandas as pd
        from prediction.train_model import chronological_split

        dates = pd.date_range("2023-01-01", periods=1000, freq="h")
        df = pd.DataFrame({
            "transit_timestamp": dates,
            "hour_of_day": dates.hour,
            "day_of_week": dates.dayofweek,
            "is_weekend": (dates.dayofweek >= 5).astype(int),
            "month": dates.month,
            "is_rush_hour": [1 if h in [7, 8, 9, 17, 18, 19] else 0 for h in dates.hour],
            "surge_multiplier": np.random.uniform(1.0, 2.5, 1000),
        })

        train, val, test = chronological_split(df, train_frac=0.7, val_frac=0.15)

        total = len(train) + len(val) + len(test)
        assert total == 1000
        assert 650 <= len(train) <= 750  # ~70%
        assert 100 <= len(val) <= 200    # ~15%
        assert 100 <= len(test) <= 200   # ~15%


# ===================================================================
# Multi-Horizon & Event Engine Integration Tests
# ===================================================================

@pytest.mark.django_db
class TestMultiHorizonAndEvents:
    def test_multi_horizon_forecast_generation(self):
        from prediction.queue_dynamics import QueueDynamicsEngine
        from core.models import Stop

        Stop.objects.create(name="Forecast Stop", lat=20.29, lon=85.82, capacity=100, is_active=True)

        res = QueueDynamicsEngine.compute_station_crowd_predictions(horizon_minutes=60, dt_minutes=15)
        assert "stations" in res
        assert len(res["stations"]) > 0

        st = res["stations"][0]
        assert "forecast" in st
        assert len(st["forecast"]) == 4  # 15m, 30m, 45m, 60m
        horizons = [f["horizon_minutes"] for f in st["forecast"]]
        assert horizons == [15, 30, 45, 60]

        assert "contributing_factors" in st
        assert "recommended_action" in st
        assert "action" in st["recommended_action"]
        assert "model_info" in res
        assert "event_engine" in res["model_info"]
