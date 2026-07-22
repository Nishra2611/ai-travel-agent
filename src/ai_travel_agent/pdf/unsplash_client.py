"""
ai_travel_agent/pdf/unsplash_client.py — Week 14

Fetches a free high-quality destination photo for the PDF cover page via
the Unsplash API. Same safe-fallback contract as get_travel_time_safe /
get_distance_matrix_safe / render_thumbnail_safe: get_destination_photo_safe
never raises. No UNSPLASH_ACCESS_KEY, no network, rate-limited, or no
results all degrade to None -- the PDF cover page (Week 14 templates.py)
is designed to render fine with cover_photo_path=None, just without a
photo, rather than blocking the whole PDF over a missing/expired API key.

Setup: requires UNSPLASH_ACCESS_KEY in the environment. Unsplash's free
tier is rate-limited (50 requests/hour as of this writing) -- fine for a
portfolio project, but worth caching results per destination if this ever
sees real traffic (not implemented here; add a cache.get/set pair around
_fetch the same way distance_matrix_client caches OSRM pairs if needed).

Drop this file at: ai_travel_agent/pdf/unsplash_client.py
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
REQUEST_TIMEOUT_SECONDS = 8
DOWNLOAD_TIMEOUT_SECONDS = 15


def get_destination_photo_safe(query: str, output_path: str | Path) -> Path | None:
    """
    Searches Unsplash for `query` (e.g. "Paris skyline"), downloads the
    top result to output_path, and returns that path. Returns None on any
    failure -- missing API key, network error, no results, bad response,
    download failure.
    """
    api_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not api_key:
        logger.warning("UNSPLASH_ACCESS_KEY not set, skipping cover photo")
        return None

    try:
        image_url = _search(query, api_key)
        if not image_url:
            logger.warning("no Unsplash results for query", extra={"query": query})
            return None
        return _download(image_url, Path(output_path))
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- a missing cover photo must not block the PDF
        logger.warning(
            "unsplash photo fetch failed, continuing without cover photo",
            extra={"error": str(exc)},
        )
        return None


def _search(query: str, api_key: str) -> str | None:
    response = requests.get(
        UNSPLASH_SEARCH_URL,
        params={"query": query, "per_page": "1", "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {api_key}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results") or []
    if not results:
        return None
    url = results[0]["urls"]["regular"]
    return str(url) if url else None


def _download(image_url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(image_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    logger.info("cover photo downloaded", extra={"output_path": str(output_path)})
    return output_path
