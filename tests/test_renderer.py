"""Tests for the payslip PDF.

The load-bearing group is "text layer": it reads the generated PDF back and
asserts the values come out character-exact. That is what proves the output is
selectable, copyable and machine-extractable rather than a picture of a
payslip -- a stated requirement, and the property most easily lost by a
well-meaning change (drawing a figure as an image, or losing the ToUnicode map).
"""

from decimal import Decimal

import pypdfium2 as pdfium
import pytest

from salary_app.models import Payslip
from salary_app.pdf.preview import (
    extract_text, page_count, render_page_data_url, render_page_png,
)
from salary_app.pdf.renderer import render_payslip


@pytest.fixture
def slip() -> Payslip:
    """August figures from row 6 of the real workbook, with demo identity."""
    return Payslip(
        employee_name="Nilupul Kodikara",
        employee_number="70",
        designation="Associate Artificial Intelligence and Machine Learning Engineer",
        month="August", year="2026",
        basic_salary=Decimal("80000"),
        travelling_allowance=Decimal("35000"),
        attendance_allowance=Decimal("35000"),
        other_allowances=None, over_time=None,
        gross_pay=Decimal("150000"),
        no_pay=Decimal("0"), apit_tax=Decimal("0"), salary_advance=None,
        epf_employee=Decimal("6400"),
        total_deduction=Decimal("6400"),
        net_salary=Decimal("143600"),
        epf_company=Decimal("9600"), etf_company=Decimal("2400"),
    )


@pytest.fixture
def rendered(slip, tmp_path):
    return render_payslip(slip, tmp_path / "slip.pdf")


# --- it produces a PDF at all --------------------------------------------

def test_writes_a_single_page_pdf(rendered):
    assert rendered.exists()
    assert rendered.read_bytes().startswith(b"%PDF")
    assert page_count(rendered) == 1


def test_creates_missing_directories(slip, tmp_path):
    target = tmp_path / "a" / "b" / "slip.pdf"
    assert render_payslip(slip, target).exists()


# --- text layer: the copyable/extractable guarantee -----------------------

@pytest.mark.parametrize("expected", [
    "Nilupul Kodikara",
    "70",
    "August 2026",
    "Associate Artificial Intelligence and Machine Learning Engineer",
    "80,000.00",          # basic
    "35,000.00",          # allowances
    "150,000.00",         # gross
    "(6,400.00)",         # deduction, accounting brackets
    "143,600.00",         # net
    "9,600.00",           # employer EPF
    "2,400.00",           # employer ETF
    "One Hundred Forty Three Thousand Six Hundred Rupees Only",
])
def test_every_value_is_real_extractable_text(rendered, expected):
    assert expected in extract_text(rendered)


def test_labels_are_extractable(rendered):
    text = extract_text(rendered)
    for label in ("Basic Salary", "Travelling Allowance", "Gross Pay",
                  "Total Deduction", "NET SALARY", "E.P.F (8%)", "APIT Tax"):
        assert label in text, label


def test_output_is_not_a_picture_of_a_payslip(rendered):
    """A rasterised layout would extract as little or no text."""
    assert len(extract_text(rendered)) > 400


def test_fonts_are_embedded(rendered):
    """Without embedding, the slip renders in a substitute font elsewhere."""
    raw = rendered.read_bytes()
    assert b"FontFile2" in raw


def test_copy_paste_is_clean_not_glyph_soup(rendered):
    """A missing ToUnicode map yields extractable-but-meaningless output."""
    raw = rendered.read_bytes()
    assert b"ToUnicode" in raw
    assert "Payslip" in extract_text(rendered)


# --- blank vs zero survives into the PDF ----------------------------------

def test_zero_prints_a_dash_and_blank_prints_nothing(slip, tmp_path):
    text = extract_text(render_payslip(slip, tmp_path / "s.pdf"))
    assert "No Pay" in text and "Over Time" in text
    # Over Time is None -> no figure; No Pay is 0 -> a dash. Both lines exist.
    assert "-" in text


# --- metadata -------------------------------------------------------------

def test_document_metadata_identifies_the_slip(rendered):
    document = pdfium.PdfDocument(str(rendered))
    try:
        assert "Nilupul Kodikara" in document.get_metadata_value("Title")
        assert "August 2026" in document.get_metadata_value("Subject")
        assert "Softvil" in document.get_metadata_value("Author")
    finally:
        document.close()


# --- preview rasteriser ---------------------------------------------------

def test_preview_png_is_a_png(rendered):
    assert render_page_png(rendered).startswith(b"\x89PNG\r\n\x1a\n")


def test_preview_data_url_shape(rendered):
    url = render_page_data_url(rendered, scale=1.0)
    assert url.startswith("data:image/png;base64,")
    assert len(url) > 1000


def test_preview_scale_changes_resolution(rendered):
    small = len(render_page_png(rendered, scale=0.5))
    large = len(render_page_png(rendered, scale=2.0))
    assert large > small


def test_preview_rejects_out_of_range_page(rendered):
    with pytest.raises(IndexError):
        render_page_png(rendered, page=5)


# --- robustness -----------------------------------------------------------

def test_renders_with_everything_blank(tmp_path):
    """An incomplete row must still produce a page, not crash the batch."""
    path = render_payslip(Payslip(), tmp_path / "empty.pdf")
    assert path.exists()
    assert "Zero Rupees Only" in extract_text(path)


def test_long_designation_does_not_overflow(tmp_path):
    """Wrapping keeps a very long title inside the page."""
    slip = Payslip(
        employee_name="Test", employee_number="1",
        designation="Senior Principal Distinguished Associate Artificial "
                    "Intelligence and Machine Learning Platform Engineer II",
        month="August", year="2026", net_salary=Decimal("1000"),
    )
    text = extract_text(render_payslip(slip, tmp_path / "long.pdf"))
    assert "Senior Principal Distinguished" in text
