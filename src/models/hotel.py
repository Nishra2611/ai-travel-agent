from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180
    )


class HotelOption(BaseModel):
    id: str
    name: str

    star_rating: Optional[float] = Field(
        None,
        ge=0,
        le=5
    )

    price_per_night_usd: float = Field(
        ...,
        gt=0
    )

    total_price_usd: float = Field(
        ...,
        gt=0
    )

    check_in: date
    check_out: date

    location: GeoLocation

    address: str

    amenities: List[str] = Field(
        default_factory=list
    )

    review_score: Optional[float] = Field(
        None,
        ge=0,
        le=10
    )

    review_count: Optional[int] = None
    booking_url: Optional[str] = None
    cancellation_policy: Optional[str] = None