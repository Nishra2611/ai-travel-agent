"""Base class for all travel agent tools."""

import logging
import time
from typing import Any

from langchain.tools import BaseTool

from src.utils.exceptions import APIRateLimitError, APITimeoutError

logger = logging.getLogger(__name__)

DAILY_SERPAPI_LIMIT = 8


class BaseTravelTool(BaseTool):
    """
    Parent class for every travel tool.

    Subclasses must define:
        name, description, args_schema
        cache_namespace: str
        cache_ttl: int
        _run(self, **kwargs) -> list[dict]
        _fetch(self, **kwargs) -> list[dict]
        _mock_data(self, **kwargs) -> list[dict]

    Provides automatically:
        - Redis cache check before every API call
        - Daily SerpApi call budget (8/day) tracked in Redis
        - Retry with exponential backoff on timeout / rate limit
        - Graceful mock fallback when use_mock_on_failure=True
        - Per-call timing logged at INFO level
    """

    cache_namespace: str = "base"
    cache_ttl: int = 3600
    use_mock_on_failure: bool = True

    # ------------------------------------------------------------------
    # Subclasses implement these three
    # ------------------------------------------------------------------

    def _fetch(self, **kwargs: Any) -> list[dict]:  # type: ignore[override]
        raise NotImplementedError

    def _mock_data(self, **kwargs: Any) -> list[dict]:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Cache helpers — lazy-imported so tests can patch fakeredis
    # ------------------------------------------------------------------

    def _get_cached(self, params: dict) -> list[dict] | None:
        from src.utils.cache import cache

        return cache.get(self.cache_namespace, params)

    def _set_cached(self, params: dict, value: list[dict]) -> None:
        from src.utils.cache import cache

        cache.set(self.cache_namespace, params, value, self.cache_ttl)

    def _budget_exceeded(self) -> bool:
        from src.utils.cache import cache

        return cache.get_api_calls_today("serpapi") >= DAILY_SERPAPI_LIMIT

    def _increment_budget(self) -> None:
        from src.utils.cache import cache

        cache.increment_api_calls("serpapi")

    # ------------------------------------------------------------------
    # Core execution flow used by every _run()
    # ------------------------------------------------------------------

    def _execute_with_cache(self, params: dict) -> list[dict]:
        """
        1. Cache hit  → return immediately
        2. Budget exceeded → return mock
        3. API call with up to 3 retries (backoff: 2s, 4s, 8s)
        4. On failure → mock if use_mock_on_failure, else re-raise
        """
        cached = self._get_cached(params)
        if cached is not None:
            logger.info("cache hit: %s", self.cache_namespace)
            return cached

        if self._budget_exceeded():
            logger.warning(
                "daily SerpApi budget reached — returning mock for %s",
                self.cache_namespace,
            )
            return self._mock_data(**params)

        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(3):
            try:
                t0 = time.perf_counter()
                self._increment_budget()
                result = self._fetch(**params)
                elapsed = time.perf_counter() - t0
                logger.info(
                    "%s: %d results in %.2fs (attempt %d)",
                    self.cache_namespace,
                    len(result),
                    elapsed,
                    attempt + 1,
                )
                self._set_cached(params, result)
                return result

            except (APITimeoutError, APIRateLimitError) as exc:
                last_exc = exc
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "%s retryable error (attempt %d), waiting %ds: %s",
                    self.cache_namespace,
                    attempt + 1,
                    wait,
                    exc,
                )
                time.sleep(wait)

            except Exception as exc:
                last_exc = exc
                logger.error("%s non-retryable error: %s", self.cache_namespace, exc)
                break

        if self.use_mock_on_failure:
            logger.warning(
                "%s all attempts failed — returning mock. Last error: %s",
                self.cache_namespace,
                last_exc,
            )
            return self._mock_data(**params)

        raise last_exc

    # ------------------------------------------------------------------
    # Async — delegates to sync for now (Week 2 scope)
    # ------------------------------------------------------------------

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        return self._run(*args, **kwargs)
