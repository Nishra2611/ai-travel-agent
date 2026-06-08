from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FlightSegment(BaseModel):
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    airline: str
    flight_number: str
    duration_minutes: int


class FlightOption(BaseModel):
    id: str
    segments: List[FlightSegment]

    total_price_usd: float = Field(
        ...,
        gt=0
    )

    currency: str = Field(
        default="USD"
    )

    cabin_class: str = Field(
        default="ECONOMY"
    )

    seats_available: Optional[int] = None
    booking_url: Optional[str] = None
    amadeus_offer_id: Optional[str] = None

    @property
    def total_duration_minutes(self) -> int:
        return sum(
            segment.duration_minutes
            for segment in self.segments
        )

    @property
    def num_stops(self) -> int:
        return len(self.segments) - 1