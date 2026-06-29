"""
ai_travel_agent/parsers/preference_parser.py

PreferenceParserTool — converts a natural-language travel request into a
structured TravelPreferences dict using a local Ollama LLM.

Uses langchain-ollama (already in pyproject.toml).
Default model: llama3.2  (change via OLLAMA_MODEL env var or config).

Why Ollama and not Anthropic?
  - langchain-anthropic is NOT in pyproject.toml
  - langchain-ollama IS in pyproject.toml
  - Ollama runs locally, zero API cost, no rate limits for dev

Input:  user_input: str  e.g. "Paris 5 days in July under $3000"
Output: dict matching TravelPreferences fields (validated by Pydantic)
        returned as model_dump() — a plain dict, ready for state["preferences"]
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from langchain_ollama import OllamaLLM
from pydantic import BaseModel, Field

from ai_travel_agent.models.travel_preferences import TravelPreferences
from ai_travel_agent.tools.base import BaseTravelTool
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# ── system prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a travel preference extraction system.
Extract structured travel preferences from natural language.
Respond ONLY with valid JSON. No markdown fences, no explanation.

Extract these fields:
  destination        (string, required) city or country name
  origin             (string, optional) departure city, default null
  duration_days      (integer, required) number of days
  start_date         (string, optional) YYYY-MM-DD, null if not given
  end_date           (string, optional) YYYY-MM-DD, null if not given
  budget_usd         (float, optional) total budget in USD, null if not given
  num_travelers      (integer, default 1)
  travel_style       one of: budget | moderate | luxury  (default moderate)
  activity_types     list from: culture adventure relaxation food shopping nature
  dietary_restrictions list of strings, empty if none
  confidence_score   float 0.0-1.0 how confident you are

Rules:
- If month mentioned without year, use next upcoming occurrence from today.
- If duration not mentioned but start+end given, calculate it.
- If city is ambiguous use the most famous one.
- Return ONLY the JSON object, nothing else."""


class PreferenceParserInput(BaseModel):
    user_input: str = Field(..., description="Natural language travel request")


class PreferenceParserTool(BaseTravelTool):
    name: str = "preference_parser"
    description: str = (
        "Parses a natural-language travel request into structured preferences. "
        "Always call this first before any search tool."
    )
    args_schema: type[BaseModel] = PreferenceParserInput
    cache_namespace: str = "preferences"
    cache_ttl: int = 300  # 5 min — user may refine quickly

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self._llm = OllamaLLM(
            model=model_name,
            temperature=0,
        )
        logger.info("PreferenceParserTool: using Ollama model=%s", model_name)

    def _run(self, user_input: str) -> dict[str, Any]:
        logger.info("PreferenceParserTool: parsing %r", user_input[:80])

        prompt = f"{_SYSTEM_PROMPT}\n\nUser request: {user_input}"

        try:
            raw: str = self._llm.invoke(prompt)
        except Exception as exc:
            logger.error("Ollama call failed: %s", exc)
            return self._fallback(user_input)

        return self._parse_llm_output(raw, user_input)

    def _parse_llm_output(self, raw: str, original: str) -> dict[str, Any]:
        """Extract JSON from LLM output and validate through Pydantic."""
        # strip markdown fences if Ollama adds them anyway
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

        # find first { ... } block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("No JSON found in LLM output — using fallback")
            return self._fallback(original)

        try:
            data: dict[str, Any] = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse failed: %s — using fallback", exc)
            return self._fallback(original)

        # normalise date strings → date objects for Pydantic
        for field in ("start_date", "end_date"):
            val = data.get(field)
            if isinstance(val, str):
                try:
                    data[field] = datetime.strptime(val, "%Y-%m-%d").date()
                except ValueError:
                    data[field] = None

        data["raw_input"] = original

        try:
            prefs = TravelPreferences(**data)
            logger.info(
                "Parsed: destination=%s days=%s budget=%s",
                prefs.destination,
                prefs.duration_days,
                prefs.budget_usd,
            )
            return prefs.model_dump()
        except Exception as exc:
            logger.warning("Pydantic validation failed: %s — using fallback", exc)
            return self._fallback(original)

    def _fallback(self, user_input: str) -> dict[str, Any]:
        """
        Minimal safe fallback when LLM or JSON parsing fails.
        Returns a TravelPreferences with confidence=0 so the supervisor
        can detect a low-quality parse and ask for clarification.
        """
        prefs = TravelPreferences(
            destination="Unknown",
            duration_days=7,
            budget_usd=None,
            raw_input=user_input,
            confidence_score=0.0,
        )
        return prefs.model_dump()

    # not used but satisfies BaseTravelTool abstract methods
    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _mock_data(self, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError
