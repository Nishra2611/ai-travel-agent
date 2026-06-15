from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from ai_travel_agent.models.travel_preferences import TravelPreferences


class PreferenceParserInput(BaseModel):
    user_input: str = Field(
        ...,
        description="Natural language travel request",
    )


class PreferenceParserTool(BaseTool):
    name: str = "preference_parser"

    description: str = "Extracts structured travel preferences from natural language"

    args_schema: type[BaseModel] = PreferenceParserInput

    def _run(self, user_input: str) -> dict[str, object]:
        prefs = TravelPreferences(
            destination="Paris",
            duration_days=5,
            budget_usd=3000,
            raw_input=user_input,
        )

        return prefs.model_dump()

    async def _arun(self, user_input: str) -> dict[str, object]:
        prefs = TravelPreferences(
            destination="Paris",
            duration_days=5,
            budget_usd=3000,
            raw_input=user_input,
        )

        return prefs.model_dump()
