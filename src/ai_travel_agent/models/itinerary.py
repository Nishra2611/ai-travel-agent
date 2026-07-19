from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel, Field

from ai_travel_agent.models.flight import FlightOption
from ai_travel_agent.models.hotel import HotelOption


class TimeSlot(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class ItineraryActivity(BaseModel):
    time_slot: TimeSlot

    start_time: time | None = None
    end_time: time | None = None

    attraction_id: str | None = None

    title: str
    description: str
    location_name: str

    estimated_cost_usd: float = Field(default=0.0, ge=0)
    estimated_duration_hours: float = Field(default=2.0, gt=0)

    # 1-2 = must-see (hard constraint), 3-5 = nice-to-have
    priority: int = Field(default=3, ge=1, le=5)

    lat: float | None = None
    lng: float | None = None

    travel_time_to_next_minutes: int | None = None
    notes: str | None = None


class DayPlan(BaseModel):
    date: date

    day_number: int = Field(..., ge=1)

    theme: str | None = None

    activities: list[ItineraryActivity] = Field(default_factory=list)

    daily_budget_usd: float = Field(default=0.0, ge=0)

    weather_forecast: str | None = None


class Itinerary(BaseModel):
    id: str
    title: str
    destination: str

    start_date: date
    end_date: date

    num_travelers: int = Field(..., ge=1)

    days: list[DayPlan] = Field(default_factory=list)

    outbound_flight: FlightOption | None = None
    return_flight: FlightOption | None = None
    hotel: HotelOption | None = None

    total_cost_usd: float = Field(default=0.0, ge=0)

    budget_usd: float | None = None

    generated_at: str = ""

    version: int = Field(default=1)

    @property
    def is_within_budget(self) -> bool:
        if self.budget_usd is None:
            return True

        return self.total_cost_usd <= self.budget_usd
