"""
tests/integration/test_main_api.py — Week 17

Integration tests for the FastAPI app. Every external tool call is
mocked (SerpApi, OpenWeatherMap, Places, the LangGraph itself) so this
suite runs offline and fast — the "mocked API responses" requirement
from the Week 17 plan, matching your existing patch-based style from
test_itinerary_builder.py's `patch_osrm` fixture.

Run: pytest tests/integration/test_main_api.py -v --cov=ai_travel_agent.api.main
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_travel_agent.api.main import app

client = TestClient(app)


# ── health ────────────────────────────────────────────────────────────────

class TestHealth:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "AI Travel Agent" in r.json()["message"]

    def test_health_ok_when_cache_healthy(self):
        with patch("ai_travel_agent.api.main.cache.is_healthy", return_value=True):
            r = client.get("/health")
            assert r.json()["status"] == "ok"

    def test_health_degraded_when_cache_down(self):
        with patch("ai_travel_agent.api.main.cache.is_healthy", return_value=False):
            r = client.get("/health")
            assert r.json()["status"] == "degraded"

    def test_cache_health_endpoint(self):
        with patch("ai_travel_agent.api.main.cache.is_healthy", return_value=True):
            r = client.get("/cache/health")
            assert r.json() == {"healthy": True}


# ── /plan + /status ──────────────────────────────────────────────────────

FAKE_GRAPH_RESULT = {
    "final_output": {
        "destination": "Paris",
        "itinerary": {
            "days": [
                {"day_number": 1, "activities": [
                    {"name": "Eiffel Tower", "time_slot": "evening", "cost": 0}
                ]}
            ]
        },
        "flights": [], "hotels": [], "weather": [], "budget": {},
    }
}


class TestPlanAndStatus:
    def test_plan_returns_session_and_job_id(self):
        with patch("ai_travel_agent.api.main._graph.invoke", return_value=FAKE_GRAPH_RESULT):
            r = client.post("/plan", json={"destination": "Paris", "days": 5, "budget": 1500})
            assert r.status_code == 200
            body = r.json()
            assert "session_id" in body and "job_id" in body
            assert body["status"] == "planning"

    def test_status_completed_after_background_task(self):
        with patch("ai_travel_agent.api.main._graph.invoke", return_value=FAKE_GRAPH_RESULT):
            r = client.post("/plan", json={"destination": "Tokyo", "days": 3, "budget": 2000})
            job_id = r.json()["job_id"]
            # TestClient runs BackgroundTasks synchronously before returning control here
            status = client.get(f"/status/{job_id}")
            assert status.status_code == 200
            assert status.json()["status"] == "completed"

    def test_status_unknown_job_404(self):
        r = client.get("/status/does-not-exist")
        assert r.status_code == 404

    def test_plan_graph_failure_marks_job_failed(self):
        with patch("ai_travel_agent.api.main._graph.invoke", side_effect=RuntimeError("boom")):
            r = client.post("/plan", json={"destination": "Nowhere", "days": 1, "budget": 100})
            job_id = r.json()["job_id"]
            status = client.get(f"/status/{job_id}")
            assert status.json()["status"] == "failed"
            assert "boom" in status.json()["error"]


# ── /refine ───────────────────────────────────────────────────────────────

class TestRefine:
    def test_refine_unknown_session_404(self):
        r = client.post("/refine", json={"session_id": "nope", "instruction": "less walking"})
        assert r.status_code == 404

    def test_refine_known_session_ok(self):
        with patch("ai_travel_agent.api.main._graph.invoke", return_value=FAKE_GRAPH_RESULT):
            plan = client.post("/plan", json={"destination": "Rome", "days": 4, "budget": 1800})
            session_id = plan.json()["session_id"]
            r = client.post("/refine", json={"session_id": session_id, "instruction": "add museums"})
            assert r.status_code == 200
            assert r.json()["status"] == "refining"


# ── /export ───────────────────────────────────────────────────────────────

class TestExport:
    def _planned_session(self) -> str:
        with patch("ai_travel_agent.api.main._graph.invoke", return_value=FAKE_GRAPH_RESULT):
            plan = client.post("/plan", json={"destination": "Kyoto", "days": 3, "budget": 1200})
            return plan.json()["session_id"]

    def test_export_unknown_session_404(self):
        r = client.get("/export", params={"session_id": "nope", "fmt": "json"})
        assert r.status_code == 404

    def test_export_json_placeholder_when_no_itinerary_yet(self):
        session_id = self._planned_session()
        r = client.get("/export", params={"session_id": session_id, "fmt": "json"})
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_export_markdown(self):
        session_id = self._planned_session()
        r = client.get("/export", params={"session_id": session_id, "fmt": "markdown"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/markdown")

    def test_export_invalid_format_422(self):
        session_id = self._planned_session()
        r = client.get("/export", params={"session_id": session_id, "fmt": "xml"})
        assert r.status_code == 422


# ── tool-backed endpoints (all external calls mocked) ───────────────────────

class TestFlights:
    def test_search_flights_mocked(self):
        with patch("ai_travel_agent.api.main.flight_tool._run",
                   return_value=[{"airline": "Mock Air", "price": 400}]):
            r = client.get("/flights", params={"origin": "BOM", "destination": "CDG"})
            assert r.status_code == 200
            assert r.json()["results"][0]["airline"] == "Mock Air"


class TestHotels:
    def test_search_hotels_mocked(self):
        with patch("ai_travel_agent.api.main.hotel_tool._run", return_value=[{"name": "Mock Hotel"}]):
            r = client.get("/api/hotels", params={
                "city": "Paris", "check_in": "2026-08-01", "check_out": "2026-08-05",
            })
            assert r.status_code == 200
            assert r.json()["count"] == 1


class TestAttractions:
    def test_attractions_mocked(self):
        with patch("ai_travel_agent.api.main._attraction_tool._run",
                   return_value=[{"name": "Mock Museum"}]):
            r = client.get("/api/trip/attractions", params={"city": "Paris"})
            assert r.status_code == 200
            assert r.json()[0]["name"] == "Mock Museum"

    def test_attractions_upstream_failure_returns_502(self):
        with patch("ai_travel_agent.api.main._attraction_tool._run", side_effect=Exception("overpass down")):
            r = client.get("/api/trip/attractions", params={"city": "Paris"})
            assert r.status_code == 502


class TestRestaurants:
    def test_restaurants_mocked(self):
        with patch("ai_travel_agent.api.main._restaurant_tool._run",
                   return_value=[{"name": "Mock Bistro"}]):
            r = client.get("/api/trip/restaurants", params={"city": "Paris"})
            assert r.status_code == 200
            assert r.json()[0]["name"] == "Mock Bistro"


class TestWeather:
    def test_weather_mocked(self):
        with patch("ai_travel_agent.api.main._weather_tool._run",
                   return_value=[{"date": "2026-08-01", "condition": "Clear"}]):
            r = client.get("/api/trip/weather", params={"city": "Paris"})
            assert r.status_code == 200
            assert r.json()[0]["condition"] == "Clear"


class TestBudget:
    def test_update_budget_mocked(self):
        with patch("ai_travel_agent.api.main._budget_tool._run",
                   return_value={"status": "budget_set", "total_budget": 2000.0}):
            r = client.post("/api/trip/budget", json={
                "trip_id": "paris-2026", "action": "set_budget", "total_budget": 2000.0,
            })
            assert r.status_code == 200
            assert r.json()["status"] == "budget_set"

    def test_get_budget_summary_mocked(self):
        with patch("ai_travel_agent.api.main._budget_tool._run",
                   return_value={"spent_total": 0, "by_category": {}}):
            r = client.get("/api/trip/budget/paris-2026")
            assert r.status_code == 200


# ── legacy endpoints ──────────────────────────────────────────────────────

class TestLegacyEndpoints:
    def test_legacy_plan_missing_request_422(self):
        r = client.post("/api/trip/plan", json={})
        assert r.status_code == 422

    def test_legacy_plan_success(self):
        with patch("ai_travel_agent.api.main._run_graph", return_value=FAKE_GRAPH_RESULT):
            r = client.post("/api/trip/plan", json={"request": "Paris 5 days $3000"})
            assert r.status_code == 200
            assert "thread_id" in r.json()

    def test_legacy_evaluate(self):
        with patch("ai_travel_agent.api.main.evaluate_itinerary", return_value={"score": 8.5}):
            r = client.post("/api/trip/evaluate", json={"itinerary": {}, "request": "test"})
            assert r.status_code == 200
            assert r.json()["score"] == 8.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
