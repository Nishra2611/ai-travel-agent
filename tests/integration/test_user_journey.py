"""
tests/integration/test_user_journey.py — Week 17

The plan calls for Playwright browser E2E tests against the React chat
UI. There's no tests/e2e/ directory in this repo (just integration,
evaluation, fixtures, unit, week15), so this lives in tests/integration/
alongside test_main_api.py and test_ws_plan.py. Unlike those two, this
one is NOT mocked — it uses Playwright's APIRequestContext to test the
same user journey the UI drives (plan → poll → export) against a LIVE
server, since that's the only honest way to test the full pipeline
together. Swap to `playwright.sync_api.sync_playwright().chromium` +
`page.goto(...)` once the React frontend is deployed; the fixtures below
already isolate "start a real server" so that swap is a small diff.

Requires the app actually running:
    uvicorn ai_travel_agent.api.main:app --port 8000 &
    pytest tests/integration/test_user_journey.py -v

Or point BASE_URL at a docker-compose instance. Keep this one out of
your default `pytest tests/unit tests/integration` CI run (see
WEEK17_18_19_GUIDE.md) since it needs a live server, not mocks.
"""

import os
import time

import pytest
from playwright.sync_api import APIRequestContext, sync_playwright

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")

# Needs a live server, unlike the mocked tests in this same directory —
# excluded from the default `pytest tests/unit tests/integration` sweep
# via this marker. Register it in pyproject.toml:
#   [tool.pytest.ini_options]
#   markers = ["live_server: needs a real running app, not mocked"]
pytestmark = pytest.mark.live_server


@pytest.fixture(scope="module")
def api() -> APIRequestContext:
    with sync_playwright() as p:
        context = p.request.new_context(base_url=BASE_URL)
        yield context
        context.dispose()


class TestFullPlanningJourney:
    def test_server_is_up(self, api: APIRequestContext):
        resp = api.get("/")
        assert resp.ok

    def test_plan_poll_export_journey(self, api: APIRequestContext):
        # 1. Start planning — mirrors the "Plan my trip" chat action
        plan_resp = api.post(
            "/plan", data={"destination": "Lisbon", "days": 4, "budget": 1800}
        )
        assert plan_resp.ok
        body = plan_resp.json()
        session_id, job_id = body["session_id"], body["job_id"]

        # 2. Poll like the frontend does, up to a real planning timeout
        status = "running"
        for _ in range(30):
            status_resp = api.get(f"/status/{job_id}")
            assert status_resp.ok
            status = status_resp.json()["status"]
            if status in ("completed", "failed"):
                break
            time.sleep(2)

        assert (
            status == "completed"
        ), f"Planning did not complete in time (last status: {status})"

        # 3. Export — mirrors the "Download PDF" button
        export_resp = api.get(
            "/export", params={"session_id": session_id, "fmt": "json"}
        )
        assert export_resp.ok
        itinerary = export_resp.json()
        assert isinstance(itinerary, dict) and len(itinerary) > 0

    def test_refine_after_plan(self, api: APIRequestContext):
        plan_resp = api.post(
            "/plan", data={"destination": "Prague", "days": 3, "budget": 1200}
        )
        session_id = plan_resp.json()["session_id"]
        job_id = plan_resp.json()["job_id"]

        for _ in range(30):
            if api.get(f"/status/{job_id}").json()["status"] in ("completed", "failed"):
                break
            time.sleep(2)

        refine_resp = api.post(
            "/refine", data={"session_id": session_id, "instruction": "less walking"}
        )
        assert refine_resp.ok
        assert refine_resp.json()["status"] == "refining"
