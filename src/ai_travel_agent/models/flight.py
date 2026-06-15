from datetime import datetime

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
    segments: list[FlightSegment]

    total_price_usd: float = Field(..., gt=0)

    currency: str = Field(default="USD")

    cabin_class: str = Field(default="ECONOMY")

    seats_available: int | None = None
    booking_url: str | None = None
    amadeus_offer_id: str | None = None

    @property
    def total_duration_minutes(self) -> int:
        return sum(segment.duration_minutes for segment in self.segments)

    @property
    def num_stops(self) -> int:
        return len(self.segments) - 1
