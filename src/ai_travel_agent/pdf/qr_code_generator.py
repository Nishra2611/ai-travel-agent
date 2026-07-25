"""
ai_travel_agent/pdf/qr_code_generator.py — Week 14

Generates a QR code image linking to the interactive HTML map (Week 13)
for the PDF to embed. Same safe-fallback contract as everything else in
this project: generate_qr_code_safe never raises, returns None if the
`qrcode` package isn't installed or encoding fails.

Known limitation, documented rather than hidden: a QR code is only useful
if the URL it encodes is actually reachable by whoever scans it. This
project generates the interactive map as a local HTML file
(outputs/maps/travel_map.html, see Week 13's generate_map node) -- there's
no public URL for that file yet. Until a hosting/sharing endpoint exists
(a reasonable Week 15/16 addition -- e.g. a FastAPI static route or an
upload-to-S3 step), pass a placeholder or a locally-reachable URL
(http://localhost:8000/... during a live demo) rather than a bare file://
path, since most phone QR scanners refuse to open file:// links.

Drop this file at: ai_travel_agent/pdf/qr_code_generator.py
"""

from __future__ import annotations

from pathlib import Path

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)


def generate_qr_code_safe(data: str, output_path: str | Path) -> Path | None:
    """
    Encodes `data` (expected to be a URL) as a QR code PNG at output_path.
    Returns None on any failure, including qrcode not being installed.
    """
    if not data:
        logger.warning("no data provided for QR code, skipping")
        return None

    try:
        return _generate(data, Path(output_path))
    except ImportError:
        logger.warning(
            "qrcode package not installed, skipping QR code (pip install qrcode[pil])"
        )
        return None
    except Exception as exc:  # noqa: BLE001 -- a missing QR code must not block the PDF
        logger.warning(
            "QR code generation failed, continuing without it",
            extra={"error": str(exc)},
        )
        return None


def _generate(data: str, output_path: Path) -> Path:
    import qrcode

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(data)
    img.save(str(output_path))
    logger.info(
        "QR code generated", extra={"output_path": str(output_path), "data": data}
    )
    return output_path
