from typing import Any

from src.tools.base import BaseTravelTool


class DummyFlightTool(BaseTravelTool):

    name: str = "dummy_flight"
    description: str = "Test Tool"
    cache_namespace: str = "flights"

    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"airline": "IndiGo", "price": 5000}]

    def _mock_data(self, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"airline": "Mock Airline", "price": 4500}]

    def _run(self, origin: str, destination: str) -> list[dict[str, Any]]:
        params = {"origin": origin, "destination": destination}
        return self._execute_with_cache(params)
