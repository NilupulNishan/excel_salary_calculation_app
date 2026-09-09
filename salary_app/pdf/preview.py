"""Rasterise a generated PDF for on-screen preview.

The point of this module is that the preview shown in the app is a picture of
**the real PDF**, not an HTML lookalike. There is one layout implementation, so
the preview cannot drift from what prints -- which is the whole reason the
review screen is a form beside a rendered page rather than an editable replica.

Rendering uses pypdfium2 (Apache-2.0/BSD), deliberately not PyMuPDF, which is
AGPL-3.0 and must not ship inside a distributed binary.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium

#: 2.0 ~= 144 DPI. Enough that 7pt labels stay readable when the preview is
#: shown at roughly page width, without making every keystroke expensive.
DEFAULT_SCALE = 2.0


def render_page_png(pdf_path: Path | str, page: int = 0,
                    scale: float = DEFAULT_SCALE) -> bytes:
    """Return one page of `pdf_path` as PNG bytes."""
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        if not 0 <= page < len(document):
            raise IndexError(
                f"page {page} out of range; document has {len(document)}")
        image = document[page].render(scale=scale).to_pil().convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    finally:
        document.close()


def render_page_data_url(pdf_path: Path | str, page: int = 0,
                         scale: float = DEFAULT_SCALE) -> str:
    """Return one page as a `data:image/png;base64,...` URL.

    A data URL rather than a temp file served over HTTP: the window has no
    server to serve from, and it sidesteps the browser caching a stale preview
    at the same path after a re-render.
    """
    encoded = base64.b64encode(render_page_png(pdf_path, page, scale)).decode()
    return f"data:image/png;base64,{encoded}"


def page_count(pdf_path: Path | str) -> int:
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(document)
    finally:
        document.close()


def extract_text(pdf_path: Path | str, page: int = 0) -> str:
    """Pull the text layer back out of a generated PDF.

    Used by the tests to prove the output is real text rather than a picture
    of text, and available at runtime for anything that needs to verify a slip.
    """
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        return document[page].get_textpage().get_text_range()
    finally:
        document.close()
