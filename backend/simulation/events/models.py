"""
Event models for Digital Twin demand modifiers.

Events represent real-world occurrences (concerts, festivals, sports events, etc.)
that affect passenger demand at nearby stops. They act as multipliers on the
baseline arrival rate in the M/M/c queue model.

NOTE: Events are stored in-memory (consistent with existing DISRUPTIONS_DB pattern).
They are NOT persisted to the database. This is simulated event data for demonstration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


# ──────────────────────────────────────────────────────────
# Event Type Catalog
# ──────────────────────────────────────────────────────────

class EventType:
    """Predefined event categories with default intensity ranges."""
    NORMAL_DAY = "NORMAL_DAY"
    WEEKEND = "WEEKEND"
    CONCERT = "CONCERT"
    SPORTS_EVENT = "SPORTS_EVENT"
    FESTIVAL = "FESTIVAL"
    EXAMINATION = "EXAMINATION"
    PUBLIC_GATHERING = "PUBLIC_GATHERING"
    RELIGIOUS_EVENT = "RELIGIOUS_EVENT"
    MARKET_DAY = "MARKET_DAY"


# Default intensity for each event type (0.0 = no effect, 3.0 = extreme surge)
EVENT_DEFAULT_INTENSITY = {
    EventType.NORMAL_DAY: 0.0,
    EventType.WEEKEND: 0.3,
    EventType.CONCERT: 2.0,
    EventType.SPORTS_EVENT: 1.8,
    EventType.FESTIVAL: 2.5,
    EventType.EXAMINATION: 1.2,
    EventType.PUBLIC_GATHERING: 1.5,
    EventType.RELIGIOUS_EVENT: 1.8,
    EventType.MARKET_DAY: 1.0,
}

# Human-readable labels
EVENT_LABELS = {
    EventType.NORMAL_DAY: "Normal Day",
    EventType.WEEKEND: "Weekend",
    EventType.CONCERT: "Concert / Live Performance",
    EventType.SPORTS_EVENT: "Sports Event",
    EventType.FESTIVAL: "Festival / Celebration",
    EventType.EXAMINATION: "Examination / College Event",
    EventType.PUBLIC_GATHERING: "Public Gathering / Rally",
    EventType.RELIGIOUS_EVENT: "Religious Event / Procession",
    EventType.MARKET_DAY: "Market Day / Exhibition",
}


# ──────────────────────────────────────────────────────────
# Event Data Model
# ──────────────────────────────────────────────────────────

@dataclass
class Event:
    """
    Represents a real-world event that modifies passenger demand.

    Attributes:
        id: Unique identifier
        event_type: One of EventType constants
        name: Human-readable event name
        start_time: When the event begins
        duration_hours: How long the event lasts
        intensity: Demand multiplier (0.0 = no effect, 3.0 = extreme)
        location_stop_id: The stop nearest to the event venue
        radius_km: Spatial influence radius (demand decays with distance)
        description: Optional description
        is_active: Whether this event is currently active
        data_source: Always "SIMULATED" unless real event feed is connected
    """
    id: int
    event_type: str
    name: str
    start_time: datetime
    duration_hours: float
    intensity: float
    location_stop_id: Optional[int] = None
    radius_km: float = 2.0
    description: str = ""
    is_active: bool = True
    data_source: str = "SIMULATED"

    @property
    def end_time(self) -> datetime:
        from datetime import timedelta
        return self.start_time + timedelta(hours=self.duration_hours)

    def is_happening_at(self, check_time: datetime) -> bool:
        """Returns True if the event is active at the given time."""
        return self.is_active and self.start_time <= check_time <= self.end_time

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "name": self.name,
            "label": EVENT_LABELS.get(self.event_type, self.event_type),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_hours": self.duration_hours,
            "intensity": self.intensity,
            "location_stop_id": self.location_stop_id,
            "radius_km": self.radius_km,
            "description": self.description,
            "is_active": self.is_active,
            "data_source": self.data_source,
        }


# ──────────────────────────────────────────────────────────
# In-Memory Event Store (consistent with DISRUPTIONS_DB)
# ──────────────────────────────────────────────────────────

EVENTS_DB: dict[int, Event] = {}
"""
In-memory event storage.
NOTE: This is simulated event data for demonstration purposes.
It is NOT persisted to the database and will be cleared on server restart.
"""
