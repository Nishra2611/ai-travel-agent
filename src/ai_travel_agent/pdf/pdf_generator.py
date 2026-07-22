"""
ai_travel_agent/pdf/pdf_generator.py — Week 14

Thin wrapper: render_itinerary_html (templates.py, already unit-tested
without WeasyPrint) -> WeasyPrint HTML-to-PDF. This is the one line in the
whole PDF pipeline that actually needs WeasyPrint installed, which is
deliberate -- WeasyPrint has real system-level dependencies (Cairo, Pango,
GDK-Pixbuf) that are a common source of "works on my machine, breaks in
Docker" failures, so keeping the WeasyPrint touchpoint to a single
function means that failure mode is isolated and easy to reason about,
rather than scattered through the templating logic.

Note: this assumes ai_travel_agent/utils/exceptions.py already defines
TravelAgentError (it does, per your Week 2 setup -- exceptions.py was one
of the original six files). Nothing new needed there.

Drop this file at: ai_travel_agent/pdf/pdf_generator.py
"""

from __future__ import annotations

from pathlib import Path

from ai_travel_agent.pdf.templates import PDFContext, render_itinerary_html
from ai_travel_agent.utils.exceptions import TravelAgentError
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)


class PDFGenerationError(TravelAgentError):
    """Raised when WeasyPrint fails to render the HTML to PDF (missing
    system libs, malformed HTML, disk/permission issues)."""


class _PDFGenerator:
    """Deliberately thin -- see module docstring for why the WeasyPrint
    call is isolated to one method rather than spread through this class."""

    def build(self, context: PDFContext, output_path: str | Path) -> Path:
        html = render_itinerary_html(context)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._render_pdf(html, output_path)
        except ImportError as exc:
            raise PDFGenerationError(
                "WeasyPrint is not installed (pip install weasyprint) or its "
                "system dependencies (Cairo/Pango/GDK-Pixbuf) are missing"
            ) from exc
        except (
            Exception
        ) as exc:  # noqa: BLE001 -- surface as our own exception type, not weasyprint's
            raise PDFGenerationError(f"PDF rendering failed: {exc}") from exc

        logger.info(
            "PDF generated",
            extra={"output_path": str(output_path), "num_days": context.num_days},
        )
        return output_path

    @staticmethod
    def _render_pdf(html: str, output_path: Path) -> None:
        from weasyprint import HTML

        HTML(string=html, base_url=str(output_path.parent)).write_pdf(str(output_path))
