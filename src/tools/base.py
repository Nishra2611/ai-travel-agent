"""Base class for all travel agent tools."""

import time
from typing import Any, Optional
from langchain.tools import BaseTool
from src.utils.cache import cache
from src.utils.logger import get_logger


class BaseTravelTool(BaseTool):
    """
    Base class for all travel agent tools.
    Provides: caching, error handling, timing, mock fallback.

    Subclasses must implement:
        _fetch(self, **kwargs) -> list[dict]
        _mock_data(self, **kwargs) -> list[dict]

    Subclasses should set:
        name: str
        description: str
        cache_namespace: str
        cache_ttl: int
    """

    cache_namespace: str = "base"
    cache_ttl: int = 3600
    use_mock_on_failure: bool = True

    def model_post_init(self, __context: Any) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def _get_cached(self, params: dict) -> Optional[Any]:
        return cache.get(self.cache_namespace, params)

    def _set_cached(self, params: dict, value: Any) -> None:
        cache.set(self.cache_namespace, params, value, self.cache_ttl)

    def _fetch(self, **kwargs: Any) -> list[dict]:
        """Override in subclass: call the real API."""
        raise NotImplementedError

    def _mock_data(self, **kwargs: Any) -> list[dict]:
        """Override in subclass: return realistic fake data."""
        raise NotImplementedError

    def _execute_with_cache(self, params: dict) -> list[dict]:
        """
        Core execution flow:
        1. Check cache
        2. Call real API
        3. On failure -> fallback to mock
        4. Store result in cache
        """
        cached = self._get_cached(params)
        if cached is not None:
            self._logger.info("Serving from cache: %s", self.cache_namespace)
            return cached

        start = time.perf_counter()
        try:
            result = self._fetch(**params)
            elapsed = time.perf_counter() - start
            self._logger.info(
                "%s: %d results in %.2fs", self.cache_namespace, len(result), elapsed
            )
            self._set_cached(params, result)
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            self._logger.error(
                "%s failed after %.2fs: %s", self.cache_namespace, elapsed, exc
            )
            if self.use_mock_on_failure:
                self._logger.warning("Falling back to mock data for %s", self.cache_namespace)
                return self._mock_data(**params)
            raise

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Subclasses must implement _run")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        return self._run(*args, **kwargs)
