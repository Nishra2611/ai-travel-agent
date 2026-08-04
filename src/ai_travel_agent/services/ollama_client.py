"""
Ollama LLM client — the single place LLM calls live.

Narration (weather tips) and human-in-the-loop questions route here;
detection/scoring/scheduling logic is pure Python so it stays fast
and testable (see FakeLLM stubs in the test files).

Reads OLLAMA_BASE_URL / OLLAMA_MODEL from env (.env.example already has them).
Graceful fallback on connection error — tests never need a running server.
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"


class OllamaClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)

    def generate(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """Free-text generation. Returns fallback string on connection error."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                },
                timeout=60,
            )
            resp.raise_for_status()
            result: str = resp.json().get("response", "") or ""
            return result.strip()
        except Exception as exc:
            logger.warning("Ollama unavailable (%s) — returning fallback", exc)
            return "Unable to generate response at this time."

    def generate_json(
        self, prompt: str, system: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        """Generate and parse JSON. Returns {"raw": text} on parse failure."""
        text = self.generate(prompt, system, **kwargs)
        try:
            result: dict[str, Any] = json.loads(text)
            return result
        except json.JSONDecodeError:
            return {"raw": text}
