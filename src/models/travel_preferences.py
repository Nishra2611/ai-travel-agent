from datetime import date
from enum import Enum
from typing import List, Optional


from pydantic import BaseModel, Field, field_validator


class TravelStyle(str, Enum):
    BUDGET = "budget"
    MODERATE = "moderate"
    LUXURY = "luxury"


class ActivityType(str, Enum):
    CULTURE = "culture"
    ADVENTURE = "adventure"
    RELAXATION = "relaxation"
    FOOD = "food"
    SHOPPING = "shopping"
    NATURE = "nature"


class TravelPreferences(BaseModel):
    destination: str = Field(
        ...,
        description="City or country to visit"
    )

    origin: Optional[str] = Field(
        None,
        description="Departure city"
    )

    duration_days: int = Field(
        ...,
        ge=1,
        le=30,
        description="Trip length"
    )

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    budget_usd: Optional[float] = Field(
        None,
        gt=0,
        description="Total budget"
    )

    num_travelers: int = Field(
        default=1,
        ge=1,
        le=20
    )

    travel_style: TravelStyle = Field(
        default=TravelStyle.MODERATE
    )

    activity_types: List[ActivityType] = Field(
        default_factory=list
    )

    dietary_restrictions: List[str] = Field(
        default_factory=list
    )

    accommodation_preferences: List[str] = Field(
        default_factory=list
    )

    raw_input: str = Field(
        ...,
        description="Original user message"
    )

    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0
    )

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        start_date = info.data.get("start_date")

        if v and start_date and v <= start_date:
            raise ValueError(
                "end_date must be after start_date"
            )

        return v

   
from pydantic import ConfigDict
model_config = ConfigDict(
    use_enum_values=True
)