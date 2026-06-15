from datetime import date

from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)

    longitude: float = Field(..., ge=-180, le=180)


class HotelOption(BaseModel):
    id: str
    name: str

    star_rating: float | None = Field(None, ge=0, le=5)

    price_per_night_usd: float = Field(..., gt=0)

    total_price_usd: float = Field(..., gt=0)

    check_in: date
    check_out: date

    location: GeoLocation

    address: str

    amenities: list[str] = Field(default_factory=list)

    review_score: float | None = Field(None, ge=0, le=10)

    review_count: int | None = None
    booking_url: str | None = None
    cancellation_policy: str | None = None
