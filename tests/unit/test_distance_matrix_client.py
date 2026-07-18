"""
tests/unit/test_distance_matrix_client.py — Week 9

Tests get_distance_matrix_safe's two paths:
  1. OSRM succeeds -> parses the table response correctly
  2. OSRM fails (network error, timeout, bad response) -> falls back to
     Haversine silently, same contract as get_travel_time_safe

No real network calls -- requests.get is monkeypatched.
"""

from __future__ import annotations

import requests

from ai_travel_agent.geo.distance_matrix_client import (
    GeoPoint,
    _haversine_meters,
    get_distance_matrix_safe,
)

PARIS_POINTS = [
    GeoPoint(id="p1", name="Eiffel Tower", latitude=48.8584, longitude=2.2945),
    GeoPoint(id="p2", name="Louvre", latitude=48.8606, longitude=2.3376),
    GeoPoint(id="p3", name="Notre-Dame", latitude=48.8530, longitude=2.3499),
]


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._json


def test_osrm_success_path_parses_table_response(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        n = len(PARIS_POINTS)
        durations = [
            [0 if i == j else 300 + i * 10 + j for j in range(n)] for i in range(n)
        ]
        distances = [
            [0 if i == j else 400 + i * 10 + j for j in range(n)] for i in range(n)
        ]
        return _FakeResponse(
            {"code": "Ok", "durations": durations, "distances": distances}
        )

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    matrix = get_distance_matrix_safe(PARIS_POINTS)
    assert matrix.source == "osrm"
    assert len(matrix.entries) == len(PARIS_POINTS) * (len(PARIS_POINTS) - 1)
    duration = matrix.duration_between("p1", "p2")
    assert duration is not None and duration > 0


def test_network_error_falls_back_to_haversine(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise requests.ConnectionError("simulated network failure")

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    matrix = get_distance_matrix_safe(PARIS_POINTS)
    assert matrix.source == "haversine_fallback"
    assert len(matrix.entries) == len(PARIS_POINTS) * (len(PARIS_POINTS) - 1)


def test_osrm_non_ok_code_falls_back_to_haversine(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({"code": "NoRoute"})

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    matrix = get_distance_matrix_safe(PARIS_POINTS)
    assert matrix.source == "haversine_fallback"


def test_http_error_status_falls_back_to_haversine(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _FakeResponse({}, status_code=503)

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    matrix = get_distance_matrix_safe(PARIS_POINTS)
    assert matrix.source == "haversine_fallback"


def test_haversine_fallback_never_raises_and_covers_all_pairs(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise TimeoutError("simulated timeout")

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    matrix = get_distance_matrix_safe(PARIS_POINTS)
    for entry in matrix.entries:
        assert entry.distance_meters > 0
        assert entry.duration_seconds > 0
        assert entry.source == "haversine_fallback"


def test_haversine_distance_is_directionally_sane():
    # Eiffel Tower -> Louvre is roughly 3.9km as the crow flies.
    a, b = PARIS_POINTS[0], PARIS_POINTS[1]
    distance = _haversine_meters(a, b)
    assert 3000 < distance < 5000


def test_single_point_returns_empty_matrix():
    matrix = get_distance_matrix_safe([PARIS_POINTS[0]])
    assert matrix.entries == []


def test_too_many_points_skips_osrm_call_entirely(monkeypatch):
    called = {"count": 0}

    def fake_get(url, params=None, timeout=None):
        called["count"] += 1
        return _FakeResponse({"code": "Ok", "durations": [], "distances": []})

    monkeypatch.setattr(
        "ai_travel_agent.geo.distance_matrix_client.requests.get", fake_get
    )

    many_points = [
        GeoPoint(id=str(i), name=f"p{i}", latitude=48.85 + i * 0.001, longitude=2.35)
        for i in range(150)
    ]
    matrix = get_distance_matrix_safe(many_points)
    assert matrix.source == "haversine_fallback"
    assert called["count"] == 0
