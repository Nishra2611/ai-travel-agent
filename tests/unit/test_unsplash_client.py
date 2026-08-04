"""
tests/unit/test_unsplash_client.py — Week 14

Tests get_destination_photo_safe's failure modes -- same pattern as
test_distance_matrix_client.py (Week 9): requests.get is monkeypatched, no
real network call. Every one of these was run for real against the actual
function during development, including the "no API key" path, which is
the default state of this sandbox (no UNSPLASH_ACCESS_KEY set).
"""

from __future__ import annotations

import pytest
import requests

from ai_travel_agent.pdf import unsplash_client


class _FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200):
        self._json = json_data
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)


def test_missing_api_key_returns_none_without_network_call(monkeypatch, tmp_path):
    called = {"n": 0}

    def fake_get(*args, **kwargs):
        called["n"] += 1
        return _FakeResponse()

    monkeypatch.setattr(unsplash_client.requests, "get", fake_get)
    result = unsplash_client.get_destination_photo_safe(
        "Paris skyline", tmp_path / "cover.jpg"
    )

    assert result is None
    assert called["n"] == 0  # no network call attempted at all without a key


def test_success_path_downloads_and_saves_image(monkeypatch, tmp_path):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "fake-key")

    def fake_get(url, params=None, headers=None, timeout=None):
        if "search" in url:
            return _FakeResponse(
                json_data={
                    "results": [
                        {"urls": {"regular": "https://images.unsplash.com/fake.jpg"}}
                    ]
                }
            )
        return _FakeResponse(content=b"FAKEJPEGBYTES")

    monkeypatch.setattr(unsplash_client.requests, "get", fake_get)
    output = tmp_path / "cover.jpg"
    result = unsplash_client.get_destination_photo_safe("Paris skyline", output)

    assert result == output
    assert output.read_bytes() == b"FAKEJPEGBYTES"


def test_no_search_results_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "fake-key")
    monkeypatch.setattr(
        unsplash_client.requests,
        "get",
        lambda *a, **kw: _FakeResponse(json_data={"results": []}),
    )

    result = unsplash_client.get_destination_photo_safe(
        "Nowhereville", tmp_path / "cover.jpg"
    )
    assert result is None


def test_network_failure_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "fake-key")

    def fake_get(*args, **kwargs):
        raise requests.ConnectionError("simulated failure")

    monkeypatch.setattr(unsplash_client.requests, "get", fake_get)
    result = unsplash_client.get_destination_photo_safe("Paris", tmp_path / "cover.jpg")
    assert result is None


def test_http_error_status_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "fake-key")
    monkeypatch.setattr(
        unsplash_client.requests, "get", lambda *a, **kw: _FakeResponse(status_code=429)
    )

    result = unsplash_client.get_destination_photo_safe("Paris", tmp_path / "cover.jpg")
    assert result is None
