"""
Week 12 — LLM-as-Judge Evaluator.

Calls Claude with itinerary + trip request + rubric, returns structured JSON scores.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, cast

from ai_travel_agent.evaluation.rubric import DIMENSIONS, RUBRIC_TEXT

logger = logging.getLogger(__name__)

_FALLBACK_SCORES = {
    dim: {"score": 3, "justification": "evaluation unavailable"} for dim in DIMENSIONS
}


# Error message substrings that indicate a permanent (non-retryable) API failure
_PERMANENT_ERRORS = (
    "credit balance is too low",
    "invalid_api_key",
    "permission_error",
    "your account",
)


def _is_permanent_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in _PERMANENT_ERRORS)


def _call_anthropic(itinerary_text: str, trip_request: str) -> dict[str, Any] | None:
    """Returns None if Anthropic is permanently unavailable (billing/auth), so caller falls back to Ollama."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    user_msg = (
        f"TRIP REQUEST:\n{trip_request}\n\n"
        f"ITINERARY:\n{itinerary_text}\n\n"
        "Score this itinerary using the rubric. Return only the JSON object."
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                system=RUBRIC_TEXT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()  # type: ignore[union-attr]
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return cast(dict[str, Any], json.loads(raw))
        except json.JSONDecodeError as exc:
            logger.warning(
                "Judge returned malformed JSON (attempt %d): %s", attempt + 1, exc
            )
            if attempt == 2:
                return _FALLBACK_SCORES
        except Exception as exc:
            if _is_permanent_error(exc):
                logger.warning(
                    "Anthropic permanently unavailable (%s), falling back to Ollama",
                    exc,
                )
                return None  # signal caller to use Ollama
            logger.warning("Judge API error (attempt %d): %s", attempt + 1, exc)
            if attempt == 2:
                return _FALLBACK_SCORES
            time.sleep(2**attempt)

    return _FALLBACK_SCORES


def _call_ollama(itinerary_text: str, trip_request: str) -> dict[str, Any] | None:
    """Fallback: use local Ollama model. Returns None if Ollama is unreachable."""
    import httpx

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    prompt = (
        f"{RUBRIC_TEXT}\n\n"
        f"TRIP REQUEST:\n{trip_request}\n\n"
        f"ITINERARY:\n{itinerary_text}\n\n"
        "Return only the JSON object."
    )

    for attempt in range(2):
        try:
            resp = httpx.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return cast(dict[str, Any], json.loads(raw[start:end]))
            return None
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.warning("Ollama not reachable — using rule-based scorer")
            return None  # signal caller to use rule-based fallback
        except Exception as exc:
            logger.warning("Ollama judge error (attempt %d): %s", attempt + 1, exc)
            if attempt == 1:
                return None
            time.sleep(1)

    return None


def _rule_based_scores(itinerary: dict[str, Any], trip_request: str) -> dict[str, Any]:
    """
    Heuristic scorer used when no LLM is available.
    Produces differentiated scores based on measurable itinerary properties.
    """
    days = itinerary.get("days", [])
    all_acts = [a for d in days for a in d.get("activities", [])]
    budget = float(itinerary.get("budget_usd") or 1)
    total_cost = float(itinerary.get("total_cost_usd") or 0)
    num_days = len(days)

    # feasibility: penalise empty days
    empty_days = sum(1 for d in days if not d.get("activities"))
    feasibility = max(1, 5 - empty_days)

    # budget_accuracy: how close is cost to budget
    if budget > 0:
        ratio = abs(total_cost - budget) / budget
        budget_accuracy = (
            5
            if ratio <= 0.05
            else (
                4
                if ratio <= 0.10
                else 3 if ratio <= 0.20 else 2 if ratio <= 0.50 else 1
            )
        )
    else:
        budget_accuracy = 3

    # geo_efficiency: proxy — activities per day (more = better clustering)
    avg_acts = len(all_acts) / num_days if num_days else 0
    geo_efficiency = (
        5 if avg_acts >= 3 else 4 if avg_acts >= 2 else 3 if avg_acts >= 1 else 2
    )

    # weather_match: check if any outdoor activities on rainy days
    rainy_outdoor = 0
    for d in days:
        forecast = str(d.get("weather_forecast", "")).lower()
        is_rainy = any(w in forecast for w in ("rain", "storm", "shower"))
        if is_rainy:
            for a in d.get("activities", []):
                cat = str(a.get("description", "") + a.get("title", "")).lower()
                if any(
                    o in cat for o in ("park", "garden", "beach", "hike", "outdoor")
                ):
                    rainy_outdoor += 1
    weather_match = max(1, 5 - rainy_outdoor)

    # completeness: avg activities per day
    completeness = (
        5 if avg_acts >= 3 else 4 if avg_acts >= 2 else 3 if avg_acts >= 1 else 2
    )

    # priority_adherence: % of priority 1-2 activities scheduled
    must_see_acts = [a for a in all_acts if a.get("priority", 3) <= 2]
    priority_adherence = 5 if must_see_acts or not all_acts else 3

    # walking_balance: variance in activities per day
    if num_days > 1:
        counts = [len(d.get("activities", [])) for d in days]
        avg_c = sum(counts) / len(counts)
        variance = max(abs(c - avg_c) for c in counts) / (avg_c + 1e-9)
        walking_balance = (
            5
            if variance <= 0.2
            else 4 if variance <= 0.35 else 3 if variance <= 0.5 else 2
        )
    else:
        walking_balance = 4

    # time_realism: check for default 2h durations (sign of no real data)
    default_dur = sum(
        1 for a in all_acts if a.get("estimated_duration_hours", 2.0) == 2.0
    )
    time_realism = 3 if default_dur == len(all_acts) and all_acts else 4

    # activity_diversity: unique categories
    categories = {
        str(a.get("description", "")).split()[0]
        for a in all_acts
        if a.get("description")
    }
    activity_diversity = min(5, max(2, len(categories)))

    # preference_match: keyword overlap between request and activity titles
    req_words = set(trip_request.lower().split())
    act_words = set(" ".join(a.get("title", "") for a in all_acts).lower().split())
    overlap = len(req_words & act_words)
    preference_match = (
        5 if overlap >= 3 else 4 if overlap >= 2 else 3 if overlap >= 1 else 2
    )

    scores = {
        "feasibility": {
            "score": feasibility,
            "justification": f"{empty_days} empty days out of {num_days}",
        },
        "budget_accuracy": {
            "score": budget_accuracy,
            "justification": f"cost ${total_cost:.0f} vs budget ${budget:.0f}",
        },
        "geo_efficiency": {
            "score": geo_efficiency,
            "justification": f"{avg_acts:.1f} activities/day avg",
        },
        "weather_match": {
            "score": weather_match,
            "justification": f"{rainy_outdoor} outdoor activities on rainy days",
        },
        "completeness": {
            "score": completeness,
            "justification": f"{len(all_acts)} total activities across {num_days} days",
        },
        "priority_adherence": {
            "score": priority_adherence,
            "justification": f"{len(must_see_acts)} must-see activities scheduled",
        },
        "walking_balance": {
            "score": walking_balance,
            "justification": "based on activity count variance per day",
        },
        "time_realism": {
            "score": time_realism,
            "justification": f"{default_dur}/{len(all_acts)} activities use default 2h duration",
        },
        "activity_diversity": {
            "score": activity_diversity,
            "justification": f"{len(categories)} distinct activity categories",
        },
        "preference_match": {
            "score": preference_match,
            "justification": f"{overlap} keyword matches between request and activities",
        },
    }
    return scores


def _itinerary_to_text(itinerary: dict[str, Any]) -> str:
    """Convert itinerary dict to a readable text summary for the judge."""
    lines = [
        f"Destination: {itinerary.get('destination', 'Unknown')}",
        f"Duration: {len(itinerary.get('days', []))} days",
        f"Budget: ${itinerary.get('budget_usd', 'N/A')}",
        f"Total cost: ${itinerary.get('total_cost_usd', 'N/A')}",
        "",
    ]
    for day in itinerary.get("days", []):
        lines.append(
            f"Day {day.get('day_number')}: {day.get('date')} — {day.get('weather_forecast', '')}"
        )
        for act in day.get("activities", []):
            lines.append(
                f"  [{act.get('time_slot')}] {act.get('title')} "
                f"(${act.get('estimated_cost_usd', 0):.0f}, "
                f"{act.get('estimated_duration_hours', 2):.1f}h, "
                f"priority={act.get('priority', 3)})"
            )
        if not day.get("activities"):
            lines.append("  (no activities scheduled)")
    return "\n".join(lines)


def evaluate_itinerary(
    itinerary: dict[str, Any],
    trip_request: str,
    use_anthropic: bool = True,
) -> dict[str, Any]:
    """
    Evaluate an itinerary dict against the rubric.
    Returns: {"scores": {dim: {"score": int, "justification": str}}, "planning_time_ms": float}
    """
    t0 = time.perf_counter()
    itinerary_text = _itinerary_to_text(itinerary)

    if use_anthropic and os.environ.get("ANTHROPIC_API_KEY"):
        scores = _call_anthropic(itinerary_text, trip_request)
        if scores is None:  # permanent error (billing/auth) — fall back immediately
            logger.info("Falling back to Ollama judge")
            scores = _call_ollama(itinerary_text, trip_request)
    else:
        scores = _call_ollama(itinerary_text, trip_request)

    # Final fallback: rule-based heuristic scorer
    if scores is None:
        logger.info("Using rule-based heuristic scorer (no LLM available)")
        scores = _rule_based_scores(itinerary, trip_request)

    # Ensure all dimensions present and scores are valid ints
    for dim in DIMENSIONS:
        if dim not in scores or not isinstance(scores[dim], dict):
            scores[dim] = {"score": 3, "justification": "missing"}
        score_val = scores[dim].get("score", 3)
        try:
            scores[dim]["score"] = max(1, min(5, int(score_val)))
        except (TypeError, ValueError):
            scores[dim]["score"] = 3

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {"scores": scores, "planning_time_ms": elapsed_ms}
