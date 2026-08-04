from enum import StrEnum

from pydantic import BaseModel, Field

from ai_travel_agent.models.hotel import GeoLocation


class AttractionCategory(StrEnum):
    MUSEUM = "museum"
    LANDMARK = "landmark"
    RESTAURANT = "restaurant"
    PARK = "park"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    TOUR = "tour"


class OpeningHours(BaseModel):
    monday: str | None = None
    tuesday: str | None = None
    wednesday: str | None = None
    thursday: str | None = None
    friday: str | None = None
    saturday: str | None = None
    sunday: str | None = None


class Attraction(BaseModel):
    id: str
    name: str
    category: AttractionCategory
    description: str

    location: GeoLocation

    address: str

    rating: float | None = Field(None, ge=0, le=5)

    review_count: int | None = None

    estimated_duration_hours: float = Field(default=2.0, gt=0)

    entry_price_usd: float | None = Field(None, ge=0)

    opening_hours: OpeningHours | None = None

    booking_required: bool = False

    website: str | None = None

    tags: list[str] = Field(default_factory=list)
