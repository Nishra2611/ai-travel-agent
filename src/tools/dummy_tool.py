from src.tools.base import BaseTravelTool


class DummyFlightTool(BaseTravelTool):

    name: str = "dummy_flight"
    description: str = "Test Tool"
    cache_namespace: str = "flights"

    def _fetch(self, **kwargs):
        return [
            {
                "airline": "IndiGo",
                "price": 5000
            }
        ]

    def _mock_data(self, **kwargs):
        return [
            {
                "airline": "Mock Airline",
                "price": 4500
            }
        ]

    def _run(self, origin, destination):
        params = {
            "origin": origin,
            "destination": destination
        }
        return self._execute_with_cache(params)
