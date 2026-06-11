"""Base class for all travel agent tools."""

import time
from typing import Any

from langchain.tools import BaseTool

from src.utils.cache import cache
from src.utils.logger import get_logger


class BaseTravelTool(BaseTool):
    """
    Base class for all travel agent tools.
    Provides: caching, error handling, timing, mock fallback.
    """

    cache_namespace: str = "base"
    cache_ttl: int = 3600
    use_mock_on_failure: bool = True

    def model_post_init(self, __context: Any) -> None:
        self._logger = get_logger(self.__class__.__name__)

    def _get_cached(self, params: dict[str, Any]) -> Any | None:
        return cache.get(self.cache_namespace, params)

    def _set_cached(self, params: dict[str, Any], value: Any) -> None:
        cache.set(self.cache_namespace, params, value, self.cache_ttl)

    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _mock_data(self, **kwargs: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _execute_with_cache(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        cached = self._get_cached(params)
        if cached is not None:
            self._logger.info("Serving from cache: %s", self.cache_namespace)
            return cached  # type: ignore[no-any-return]

        start = time.perf_counter()
        try:
            result = self._fetch(**params)
            elapsed = time.perf_counter() - start
            self._logger.info("%s: %d results in %.2fs", self.cache_namespace, len(result), elapsed)
            self._set_cached(params, result)
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            self._logger.error("%s failed after %.2fs: %s", self.cache_namespace, elapsed, exc)
            if self.use_mock_on_failure:
                self._logger.warning("Falling back to mock data for %s", self.cache_namespace)
                return self._mock_data(**params)
            raise

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("Subclasses must implement _run")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        return self._run(*args, **kwargs)
