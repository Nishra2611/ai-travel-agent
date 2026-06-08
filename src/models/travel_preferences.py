from pydantic import BaseModel


class TravelPreferences(BaseModel):
    destination: str
    duration_days: int
    budget_usd: int
    raw_input: str = ""