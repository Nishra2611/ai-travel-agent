"""
locustfile.py — Week 17 load testing

Run against a REAL running instance (docker-compose up, or uvicorn
locally) — this hits actual endpoints, not mocks, so start Ollama +
Redis first or expect /plan to fall back to mock data via
use_mock_on_failure in BaseTravelTool.

Usage:
    locust -f locustfile.py --host=http://localhost:8000
    # then open http://localhost:8089 and set 10 users / 2 spawn rate
    # to match the plan's "10 concurrent planning sessions" target

Headless CI run:
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 10 --spawn-rate 2 --run-time 2m --headless \
        --csv=locust_report
"""
import random
import time

from locust import HttpUser, between, task

DESTINATIONS = ["Paris", "Tokyo", "Rome", "Bali", "New York", "Barcelona", "Kyoto"]


class TravelPlannerUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    @task(3)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(5)
    def plan_and_poll(self):
        payload = {
            "destination": random.choice(DESTINATIONS),
            "days": random.randint(3, 7),
            "budget": random.choice([1000, 1500, 2500, 4000]),
        }
        with self.client.post("/plan", json=payload, name="/plan", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"plan failed: {resp.status_code}")
                return
            job_id = resp.json().get("job_id")

        if not job_id:
            return

        # poll status a few times — mirrors real frontend polling behavior
        for _ in range(5):
            with self.client.get(f"/status/{job_id}", name="/status/[job_id]", catch_response=True) as r:
                if r.status_code != 200:
                    r.failure(f"status check failed: {r.status_code}")
                    return
                if r.json().get("status") in ("completed", "failed"):
                    return
            time.sleep(2)

    @task(1)
    def get_attractions(self):
        self.client.get("/api/trip/attractions", params={"city": random.choice(DESTINATIONS)},
                        name="/api/trip/attractions")

    @task(1)
    def get_weather(self):
        self.client.get("/api/trip/weather", params={"city": random.choice(DESTINATIONS)},
                        name="/api/trip/weather")
