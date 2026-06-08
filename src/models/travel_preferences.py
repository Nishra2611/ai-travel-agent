from datetime import date
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)


class TravelStyle(StrEnum):
    BUDGET = "budget"
    MODERATE = "moderate"
    LUXURY = "luxury"


class ActivityType(StrEnum):
    CULTURE = "culture"
    ADVENTURE = "adventure"
    RELAXATION = "relaxation"
    FOOD = "food"
    SHOPPING = "shopping"
    NATURE = "nature"


class TravelPreferences(BaseModel):
    destination: str = Field(
        ...,
        description="City or country to visit",
    )

    origin: str | None = Field(
        default=None,
        description="Departure city",
    )

    duration_days: int = Field(
        ...,
        ge=1,
        le=30,
        description="Trip length",
    )

    start_date: date | None = None
    end_date: date | None = None

    budget_usd: float | None = Field(
        None,
        gt=0,
        description="Total budget",
    )

    num_travelers: int = Field(
        default=1,
        ge=1,
        le=20,
    )

    travel_style: TravelStyle = Field(
        default=TravelStyle.MODERATE,
    )

    activity_types: list[ActivityType] = Field(
        default_factory=list,
    )

    dietary_restrictions: list[str] = Field(
        default_factory=list,
    )

    accommodation_preferences: list[str] = Field(
        default_factory=list,
    )

    raw_input: str = Field(
        ...,
        description="Original user message",
    )

    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    @field_validator("end_date")
    @classmethod
    def validate_dates(
        cls,
        v: date | None,
        info: ValidationInfo,
    ) -> date | None:
        start_date = info.data.get("start_date")

        if v and start_date and v <= start_date:
            raise ValueError("end_date must be after start_date")

        return v

    model_config = ConfigDict(use_enum_values=True)
