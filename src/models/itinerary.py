from datetime import date, time
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.flight import FlightOption
from src.models.hotel import HotelOption


class TimeSlot(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class ItineraryActivity(BaseModel):
    time_slot: TimeSlot

    start_time: Optional[time] = None
    end_time: Optional[time] = None

    attraction_id: Optional[str] = None

    title: str
    description: str
    location_name: str

    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0
    )

    travel_time_to_next_minutes: Optional[int] = None
    notes: Optional[str] = None


class DayPlan(BaseModel):
    date: date

    day_number: int = Field(
        ...,
        ge=1
    )

    theme: Optional[str] = None

    activities: List[ItineraryActivity] = Field(
        default_factory=list
    )

    daily_budget_usd: float = Field(
        default=0.0,
        ge=0
    )

    weather_forecast: Optional[str] = None


class Itinerary(BaseModel):
    id: str
    title: str
    destination: str

    start_date: date
    end_date: date

    num_travelers: int = Field(
        ...,
        ge=1
    )

    days: List[DayPlan] = Field(
        default_factory=list
    )

    outbound_flight: Optional[FlightOption] = None
    return_flight: Optional[FlightOption] = None
    hotel: Optional[HotelOption] = None

    total_cost_usd: float = Field(
        default=0.0,
        ge=0
    )

    budget_usd: Optional[float] = None

    generated_at: str = ""

    version: int = Field(
        default=1
    )

    @property
    def is_within_budget(self) -> bool:
        if self.budget_usd is None:
            return True

        return self.total_cost_usd <= self.budget_usd