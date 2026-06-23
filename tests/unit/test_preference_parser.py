"""Unit tests for PreferenceParserTool — Ollama mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_travel_agent.parsers.preference_parser import PreferenceParserTool


@pytest.fixture
def tool() -> PreferenceParserTool:
    with patch("ai_travel_agent.parsers.preference_parser.OllamaLLM"):
        t = PreferenceParserTool()
        t._llm = MagicMock()
    return t


def _mock_llm(tool: PreferenceParserTool, payload: dict) -> None:
    tool._llm.invoke = MagicMock(return_value=json.dumps(payload))


def test_returns_dict(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "Paris", "duration_days": 5, "confidence_score": 0.9}
    )
    result = tool._run(user_input="Paris 5 days")
    assert isinstance(result, dict)


def test_destination_extracted(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "Tokyo", "duration_days": 7, "confidence_score": 0.88}
    )
    result = tool._run(user_input="Tokyo 7 days")
    assert result["destination"] == "Tokyo"


def test_duration_extracted(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "Paris", "duration_days": 5, "confidence_score": 0.9}
    )
    result = tool._run(user_input="Paris 5 days")
    assert result["duration_days"] == 5


def test_budget_extracted(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool,
        {
            "destination": "Paris",
            "duration_days": 5,
            "budget_usd": 3000.0,
            "confidence_score": 0.9,
        },
    )
    result = tool._run(user_input="Paris 5 days $3000")
    assert result["budget_usd"] == 3000.0


def test_raw_input_preserved(tool: PreferenceParserTool) -> None:
    raw = "Bali 10 days adventure"
    _mock_llm(
        tool, {"destination": "Bali", "duration_days": 10, "confidence_score": 0.85}
    )
    result = tool._run(user_input=raw)
    assert result["raw_input"] == raw


def test_confidence_score_in_range(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "NYC", "duration_days": 3, "confidence_score": 0.75}
    )
    result = tool._run(user_input="NYC 3 days")
    assert 0.0 <= result["confidence_score"] <= 1.0


def test_fallback_on_invalid_json(tool: PreferenceParserTool) -> None:
    tool._llm.invoke = MagicMock(return_value="not json at all")
    result = tool._run(user_input="anything")
    assert result["destination"] == "Unknown"
    assert result["confidence_score"] == 0.0


def test_fallback_on_llm_exception(tool: PreferenceParserTool) -> None:
    tool._llm.invoke = MagicMock(side_effect=Exception("Ollama offline"))
    result = tool._run(user_input="anything")
    assert result["destination"] == "Unknown"
    assert result["confidence_score"] == 0.0


def test_strips_markdown_fences(tool: PreferenceParserTool) -> None:
    payload = {"destination": "Rome", "duration_days": 4, "confidence_score": 0.8}
    tool._llm.invoke = MagicMock(return_value=f"```json\n{json.dumps(payload)}\n```")
    result = tool._run(user_input="Rome 4 days")
    assert result["destination"] == "Rome"


def test_activity_types_extracted(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool,
        {
            "destination": "Nepal",
            "duration_days": 12,
            "activity_types": ["adventure", "nature"],
            "confidence_score": 0.88,
        },
    )
    result = tool._run(user_input="trek Nepal")
    assert "adventure" in result.get("activity_types", [])


def test_travel_style_default_moderate(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "London", "duration_days": 5, "confidence_score": 0.8}
    )
    result = tool._run(user_input="London 5 days")
    assert result.get("travel_style") in (None, "moderate")


def test_num_travelers_default_one(tool: PreferenceParserTool) -> None:
    _mock_llm(
        tool, {"destination": "Berlin", "duration_days": 4, "confidence_score": 0.8}
    )
    result = tool._run(user_input="Berlin 4 days solo")
    assert result.get("num_travelers", 1) >= 1
