"""
ai_travel_agent/utils/cost_tracker.py — Week 19

The plan's "cost tracking" step assumes hosted-LLM $/token billing
(Claude/GPT). Ollama is free and local, so there's no dollar cost to
track — instead this tracks the actual resource proxy that matters for
a local model: wall-clock generation time and token throughput
(eval_count/prompt_eval_count, which Ollama returns in every
/api/generate response). That's what tells you if a planning session
is slow because of the LLM step vs. a slow external API.

Uses the same Redis client pattern as budget_tracker.py
(ai_travel_agent.utils.cache.get_redis_client), so it persists across
requests the same way your budget ledger does.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OllamaCallRecord:
    node_name: str
    duration_seconds: float
    prompt_tokens: int
    completion_tokens: int
    model: str


def track_ollama_call(
    session_id: str,
    node_name: str,
    model: str,
    duration_seconds: float,
    ollama_response: dict[str, Any] | None = None,
) -> None:
    """Call this right after every ollama_generate()/ollama_generate_json()
    call, e.g. inside conflict_resolver._build_user_question and
    weather_scheduler._generate_narratives — pass the raw Ollama response
    dict if you switch those from ollama_generate() (text-only) back to
    the raw httpx response so prompt/completion counts are available."""
    from ai_travel_agent.utils.cache import get_redis_client

    ollama_response = ollama_response or {}
    record = OllamaCallRecord(
        node_name=node_name,
        duration_seconds=round(duration_seconds, 3),
        prompt_tokens=int(ollama_response.get("prompt_eval_count", 0)),
        completion_tokens=int(ollama_response.get("eval_count", 0)),
        model=model,
    )

    try:
        redis = get_redis_client()
        key = f"llm_usage:{session_id}"
        raw = redis.get(key)
        records: list[dict[str, Any]] = json.loads(raw) if raw else []
        records.append(asdict(record))
        redis.set(key, json.dumps(records), ex=86400)  # 24h TTL, matches session lifetime
    except Exception as exc:
        logger.warning("Could not persist LLM usage record: %s", exc)


def get_session_usage_summary(session_id: str) -> dict[str, Any]:
    """Aggregate view for a /api/trip/usage/{session_id} endpoint (add to
    main.py alongside the existing budget endpoints)."""
    from ai_travel_agent.utils.cache import get_redis_client

    try:
        redis = get_redis_client()
        raw = redis.get(f"llm_usage:{session_id}")
        records: list[dict[str, Any]] = json.loads(raw) if raw else []
    except Exception as exc:
        logger.warning("Could not read LLM usage record: %s", exc)
        records = []

    total_duration = sum(r["duration_seconds"] for r in records)
    total_prompt_tokens = sum(r["prompt_tokens"] for r in records)
    total_completion_tokens = sum(r["completion_tokens"] for r in records)

    return {
        "session_id": session_id,
        "call_count": len(records),
        "total_llm_duration_seconds": round(total_duration, 2),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "calls": records,
    }


class TimedOllamaCall:
    """Context manager for the simple case where you just want duration,
    no token counts:

        with TimedOllamaCall(session_id, "conflict_resolver") as t:
            question = ollama_generate(prompt)
        # t.duration_seconds now set, already recorded to Redis
    """

    def __init__(self, session_id: str, node_name: str, model: str = "unknown"):
        self.session_id = session_id
        self.node_name = node_name
        self.model = model
        self.duration_seconds = 0.0

    def __enter__(self) -> TimedOllamaCall:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        self.duration_seconds = time.perf_counter() - self._start
        track_ollama_call(self.session_id, self.node_name, self.model, self.duration_seconds)
