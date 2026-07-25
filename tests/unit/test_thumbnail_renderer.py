"""
tests/unit/test_thumbnail_renderer.py — Week 13

Unlike most of this project's tests, these actually launch a real headless
Chromium via Playwright rather than mocking -- rendering IS the thing being
tested, and Playwright's API surface is small enough that mocking it would
mostly just test the mocks. Requires `playwright install chromium` to have
been run once. If that hasn't happened, these are skipped rather than
failing the suite (see the availability check below), consistent with the
project's "missing optional dependency degrades what gets tested" stance
established in test_travel_map_generator.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_travel_agent.maps.thumbnail_renderer import render_thumbnail_safe


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


requires_chromium = pytest.mark.skipif(
    not _chromium_available(), reason="playwright chromium binary not installed"
)


def test_missing_html_file_returns_none_without_raising(tmp_path):
    result = render_thumbnail_safe(
        tmp_path / "does_not_exist.html", tmp_path / "out.png"
    )
    assert result is None


@requires_chromium
def test_renders_valid_png_at_requested_viewport(tmp_path):
    html_path = tmp_path / "test_map.html"
    html_path.write_text(
        '<html><body style="margin:0">'
        '<div style="width:1000px;height:700px;background:#3388ff"></div>'
        "</body></html>"
    )
    output_path = tmp_path / "thumb.png"

    result = render_thumbnail_safe(html_path, output_path)

    assert result is not None
    assert result.exists()
    from PIL import Image

    image = Image.open(result)
    assert image.size == (1000, 700)


@requires_chromium
def test_respects_custom_viewport(tmp_path):
    html_path = tmp_path / "test_map.html"
    html_path.write_text('<html><body style="margin:0;background:#fff"></body></html>')
    output_path = tmp_path / "thumb.png"

    result = render_thumbnail_safe(
        html_path, output_path, viewport={"width": 400, "height": 300}
    )

    from PIL import Image

    image = Image.open(result)
    assert image.size == (400, 300)


@requires_chromium
def test_creates_output_directory_if_missing(tmp_path):
    html_path = tmp_path / "test_map.html"
    html_path.write_text("<html><body></body></html>")
    nested_output = tmp_path / "nested" / "dir" / "thumb.png"

    result = render_thumbnail_safe(html_path, nested_output)

    assert result is not None
    assert nested_output.exists()
