"""
ai_travel_agent/maps/thumbnail_renderer.py — Week 13

Rasterizes the interactive HTML map to a static PNG, for embedding in the
Week 14 PDF (WeasyPrint can't render an interactive Leaflet map, so the PDF
needs a flat image). Uses Playwright + headless Chromium rather than
Selenium: same job, but Playwright ships its own browser binaries via
`playwright install chromium` instead of requiring a separately-managed
chromedriver version match, which is one less thing to break in CI/deploy.

Same safe-fallback contract as get_travel_time_safe / get_distance_matrix_safe
(Weeks 5-9): render_thumbnail_safe never raises. If Playwright isn't
installed, no browser binary is available, or rendering times out, it logs
a warning and returns None -- the PDF generator (Week 14) is expected to
render without a map thumbnail rather than fail outright when that happens.

Setup note: requires `playwright install chromium` to have been run once
(downloads the browser binary) in addition to `poetry add playwright`.

Drop this file at: ai_travel_agent/maps/thumbnail_renderer.py
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ViewportSize(TypedDict):
    width: int
    height: int


DEFAULT_VIEWPORT: ViewportSize = {"width": 1000, "height": 700}
RENDER_TIMEOUT_MS = 15_000
# Leaflet's tile layer loads asynchronously after the page navigates; a
# fixed wait is crude but reliable at this scale (one map, once) --
# waiting on a specific Leaflet JS event would be more precise but adds
# fragility if the map's internal structure changes.
TILE_LOAD_WAIT_MS = 2_500


def render_thumbnail_safe(
    html_path: str | Path,
    output_png_path: str | Path,
    viewport: ViewportSize | None = None,
) -> Path | None:
    """
    Screenshots a local HTML file to PNG. Returns the output path on
    success, None on any failure (missing Playwright, no browser binary,
    bad HTML path, render timeout).
    """
    html_path = Path(html_path)
    output_png_path = Path(output_png_path)

    if not html_path.exists():
        logger.warning(
            "html file not found, skipping thumbnail",
            extra={"html_path": str(html_path)},
        )
        return None

    try:
        return _render(html_path, output_png_path, viewport or DEFAULT_VIEWPORT)
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- any Playwright/browser failure must not crash the graph
        logger.warning(
            "thumbnail rendering failed, continuing without it",
            extra={"error": str(exc)},
        )
        return None


def _render(html_path: Path, output_png_path: Path, viewport: ViewportSize) -> Path:
    from playwright.sync_api import sync_playwright

    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport=viewport)
            page.goto(html_path.resolve().as_uri(), timeout=RENDER_TIMEOUT_MS)
            page.wait_for_timeout(TILE_LOAD_WAIT_MS)
            page.screenshot(path=str(output_png_path))
        finally:
            browser.close()

    logger.info("thumbnail rendered", extra={"output_path": str(output_png_path)})
    return output_png_path
