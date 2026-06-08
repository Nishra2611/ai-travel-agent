from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.hotel import GeoLocation


class AttractionCategory(str, Enum):
    MUSEUM = "museum"
    LANDMARK = "landmark"
    RESTAURANT = "restaurant"
    PARK = "park"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    TOUR = "tour"


class OpeningHours(BaseModel):
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None


class Attraction(BaseModel):
    id: str
    name: str
    category: AttractionCategory
    description: str

    location: GeoLocation

    address: str

    rating: Optional[float] = Field(
        None,
        ge=0,
        le=5
    )

    review_count: Optional[int] = None

    estimated_duration_hours: float = Field(
        default=2.0,
        gt=0
    )

    entry_price_usd: Optional[float] = Field(
        None,
        ge=0
    )

    opening_hours: Optional[OpeningHours] = None

    booking_required: bool = False

    website: Optional[str] = None

    tags: List[str] = Field(
        default_factory=list
    )