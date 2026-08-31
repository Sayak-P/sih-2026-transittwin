"""
Ticketing Simulator — generates realistic, deterministic passenger demand data.

The problem statement explicitly allows "simulated ticketing data." This module
generates per-stop, per-hour arrival/boarding/alighting data with:
  - Time-of-day demand profile (morning rush, midday, evening rush, off-peak)
  - Weekend vs weekday adjustment
  - Event-based surge multiplier integration
  - Stop importance weighting (central/hub stops get more demand)

All data is clearly labelled as data_source: "SIMULATED_TICKETING".
"""

import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field


# ──────────────────────────────────────────────────────────
# Time-of-Day Demand Profile (hourly multiplier)
# ──────────────────────────────────────────────────────────

# Normalized demand curve: [hour] -> multiplier (0.0 - 1.0)
# Two peaks: morning rush (7-10) and evening rush (17-20)
WEEKDAY_DEMAND_PROFILE = {
    0: 0.05, 1: 0.03, 2: 0.02, 3: 0.02, 4: 0.03, 5: 0.10,
    6: 0.30, 7: 0.70, 8: 1.00, 9: 0.90, 10: 0.55, 11: 0.45,
    12: 0.50, 13: 0.50, 14: 0.45, 15: 0.50, 16: 0.60, 17: 0.85,
    18: 1.00, 19: 0.80, 20: 0.50, 21: 0.30, 22: 0.15, 23: 0.08,
}

WEEKEND_DEMAND_PROFILE = {
    0: 0.05, 1: 0.03, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.05,
    6: 0.10, 7: 0.20, 8: 0.35, 9: 0.50, 10: 0.65, 11: 0.75,
    12: 0.80, 13: 0.80, 14: 0.75, 15: 0.70, 16: 0.70, 17: 0.65,
    18: 0.60, 19: 0.55, 20: 0.45, 21: 0.30, 22: 0.15, 23: 0.08,
}


@dataclass
class TicketingSnapshot:
    """Snapshot of simulated ticketing data for a single stop at a point in time."""
    stop_id: int
    stop_name: str
    timestamp: str
    arrivals_per_minute: float
    boardings_per_minute: float
    alightings_per_minute: float
    queue_size: int
    cumulative_arrivals: int
    cumulative_boardings: int
    demand_level: str  # LOW, MODERATE, HIGH, PEAK
    is_weekend: bool
    hour_of_day: int
    data_source: str = "SIMULATED_TICKETING"

    def to_dict(self) -> dict:
        return {
            "stop_id": self.stop_id,
            "stop_name": self.stop_name,
            "timestamp": self.timestamp,
            "arrivals_per_minute": round(self.arrivals_per_minute, 2),
            "boardings_per_minute": round(self.boardings_per_minute, 2),
            "alightings_per_minute": round(self.alightings_per_minute, 2),
            "queue_size": self.queue_size,
            "cumulative_arrivals": self.cumulative_arrivals,
            "cumulative_boardings": self.cumulative_boardings,
            "demand_level": self.demand_level,
            "is_weekend": self.is_weekend,
            "hour_of_day": self.hour_of_day,
            "data_source": self.data_source,
        }


@dataclass
class HistoricalDemandPoint:
    """Single point in a historical demand curve."""
    hour: int
    arrivals: int
    boardings: int
    demand_multiplier: float

    def to_dict(self) -> dict:
        return {
            "hour": self.hour,
            "arrivals": self.arrivals,
            "boardings": self.boardings,
            "demand_multiplier": round(self.demand_multiplier, 3),
        }


class TicketingSimulator:
    """
    Generates deterministic, realistic ticketing data for transit stops.

    Uses seeded random number generation for reproducibility.
    All output is clearly labelled as SIMULATED_TICKETING.
    """

    # Base arrival rate per minute for an "average" stop
    BASE_ARRIVAL_RATE = 8.0  # pax/min at peak
    # Boarding rate as fraction of arrival rate (reflects bus frequency)
    BOARDING_EFFICIENCY = 0.85

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_current_snapshot(
        self,
        stops: List[Dict],
        current_time: Optional[datetime] = None,
        event_surges: Optional[Dict[int, float]] = None,
    ) -> List[TicketingSnapshot]:
        """
        Generates a ticketing snapshot for all stops at the given time.

        Args:
            stops: List of dicts with keys: id, name, capacity, lat, lon
            current_time: Datetime to generate for (defaults to now)
            event_surges: Optional dict {stop_id: surge_multiplier} from event engine

        Returns:
            List of TicketingSnapshot objects
        """
        if current_time is None:
            from django.utils import timezone
            current_time = timezone.now()

        if event_surges is None:
            event_surges = {}

        hour = current_time.hour
        is_weekend = current_time.weekday() >= 5
        profile = WEEKEND_DEMAND_PROFILE if is_weekend else WEEKDAY_DEMAND_PROFILE
        base_multiplier = profile.get(hour, 0.3)

        snapshots = []
        for stop in stops:
            stop_id = stop["id"]
            stop_name = stop.get("name", f"Stop {stop_id}")
            capacity = stop.get("capacity", 100)

            # Stop importance weighting
            importance = self._stop_importance(stop_name, capacity)

            # Event surge (default 1.0 = no surge)
            surge = event_surges.get(stop_id, 1.0)

            # Effective arrival rate
            effective_rate = self.BASE_ARRIVAL_RATE * base_multiplier * importance * surge

            # Add deterministic noise based on stop_id and hour
            noise = self.rng.gauss(0, 0.1 * effective_rate)
            effective_rate = max(0.5, effective_rate + noise)

            # Boarding rate (capped by bus service available)
            boarding_rate = effective_rate * self.BOARDING_EFFICIENCY

            # Alighting rate (roughly proportional to arrivals at nearby stops)
            alighting_rate = effective_rate * 0.7

            # Queue buildup
            queue = max(0, int((effective_rate - boarding_rate) * 15))  # 15-min accumulation

            # Cumulative over the hour
            cumulative_arrivals = int(effective_rate * 60)
            cumulative_boardings = int(boarding_rate * 60)

            # Demand level classification
            if base_multiplier >= 0.85:
                demand_level = "PEAK"
            elif base_multiplier >= 0.55:
                demand_level = "HIGH"
            elif base_multiplier >= 0.25:
                demand_level = "MODERATE"
            else:
                demand_level = "LOW"

            snapshots.append(TicketingSnapshot(
                stop_id=stop_id,
                stop_name=stop_name,
                timestamp=current_time.isoformat(),
                arrivals_per_minute=effective_rate,
                boardings_per_minute=boarding_rate,
                alightings_per_minute=alighting_rate,
                queue_size=queue,
                cumulative_arrivals=cumulative_arrivals,
                cumulative_boardings=cumulative_boardings,
                demand_level=demand_level,
                is_weekend=is_weekend,
                hour_of_day=hour,
            ))

        return snapshots

    def generate_historical_demand(
        self,
        stop_id: int,
        stop_name: str,
        stop_capacity: int,
        hours: int = 24,
        is_weekend: bool = False,
    ) -> List[HistoricalDemandPoint]:
        """
        Generates a 24-hour historical demand curve for a single stop.

        Args:
            stop_id: Stop identifier
            stop_name: Stop name (for importance calculation)
            stop_capacity: Stop capacity
            hours: Number of hours to generate (default 24)
            is_weekend: Whether to use weekend profile

        Returns:
            List of HistoricalDemandPoint objects
        """
        profile = WEEKEND_DEMAND_PROFILE if is_weekend else WEEKDAY_DEMAND_PROFILE
        importance = self._stop_importance(stop_name, stop_capacity)

        points = []
        for h in range(min(hours, 24)):
            multiplier = profile.get(h, 0.3)
            effective_rate = self.BASE_ARRIVAL_RATE * multiplier * importance

            # Add seeded variation
            noise_factor = 1.0 + self.rng.gauss(0, 0.05)
            effective_rate *= max(0.8, noise_factor)

            arrivals = int(effective_rate * 60)
            boardings = int(effective_rate * self.BOARDING_EFFICIENCY * 60)

            points.append(HistoricalDemandPoint(
                hour=h,
                arrivals=arrivals,
                boardings=boardings,
                demand_multiplier=multiplier,
            ))

        return points

    @staticmethod
    def _stop_importance(stop_name: str, capacity: int) -> float:
        """
        Computes stop importance as a demand multiplier.
        Central/hub stops attract more passengers.
        """
        name_upper = stop_name.upper()
        importance = 1.0

        if any(kw in name_upper for kw in ["CENTRAL", "JUNCTION", "HUB", "TERMINAL"]):
            importance = 1.8
        elif any(kw in name_upper for kw in ["PARK", "MARKET", "STADIUM", "UNIVERSITY"]):
            importance = 1.5
        elif any(kw in name_upper for kw in ["HOSPITAL", "STATION", "MALL"]):
            importance = 1.3

        # High capacity stops also get more passengers
        if capacity > 200:
            importance *= 1.2
        elif capacity > 100:
            importance *= 1.1

        return importance
