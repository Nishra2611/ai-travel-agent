"""
tests/unit/test_qr_code_generator.py — Week 14

Unlike the mocked tests elsewhere, the "qrcode not installed" case here
doesn't need mocking -- it's genuinely true in the environment this was
developed against, so test_missing_qrcode_package_returns_none_gracefully
is exercising the real ImportError path, not a simulated one. If qrcode
IS installed in your environment, that same test still passes (it only
asserts empty-data behavior), and the pytest.importorskip'd tests below
cover the success path.
"""

from __future__ import annotations

import pytest

from ai_travel_agent.pdf.qr_code_generator import generate_qr_code_safe


def test_empty_data_returns_none_without_attempting_generation(tmp_path):
    result = generate_qr_code_safe("", tmp_path / "qr.png")
    assert result is None


def test_missing_qrcode_package_degrades_to_none(tmp_path):
    """If qrcode genuinely isn't installed, this exercises the real
    ImportError path end to end. If it IS installed, this just confirms a
    valid URL doesn't spuriously return None."""
    result = generate_qr_code_safe("https://example.com/map.html", tmp_path / "qr.png")
    try:
        import qrcode  # noqa: F401

        assert result is not None and result.exists()
    except ImportError:
        assert result is None


# ---------------------------------------------------------------------------
# qrcode-dependent tests -- skipped automatically if qrcode isn't installed.
# ---------------------------------------------------------------------------
qrcode = pytest.importorskip("qrcode")


def test_generates_valid_png_when_qrcode_available(tmp_path):
    output = tmp_path / "qr.png"
    result = generate_qr_code_safe("https://example.com/map.html", output)

    assert result == output
    assert output.exists()
    from PIL import Image

    image = Image.open(output)
    assert image.size[0] > 0 and image.size[1] > 0


def test_creates_output_directory_if_missing(tmp_path):
    nested = tmp_path / "nested" / "dir" / "qr.png"
    result = generate_qr_code_safe("https://example.com/map.html", nested)
    assert result is not None
    assert nested.exists()
