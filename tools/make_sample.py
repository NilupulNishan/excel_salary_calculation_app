"""Render a sample payslip so the layout can be eyeballed after a change.

    .venv\\Scripts\\python.exe tools\\make_sample.py            demo data
    .venv\\Scripts\\python.exe tools\\make_sample.py <file.xlsx> first employee

Writes out/sample.pdf plus colour and grayscale PNGs. The grayscale pass is not
decoration: it is how we check the layout still reads on a mono printer, which
is a stated requirement.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salary_app.models import Payslip                      # noqa: E402
from salary_app.pdf.preview import render_page_png         # noqa: E402
from salary_app.pdf.renderer import render_payslip         # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "out"


def demo_slip() -> Payslip:
    """Real August figures (row 6 of Payment Summary) with demo identity.

    Columns B-M of the supplied workbook are empty, so name, number and
    designation are placeholders taken from the June reference PDF.
    """
    return Payslip(
        employee_name="Nilupul Kodikara",
        employee_number="70",
        designation="Associate Artificial Intelligence and Machine Learning Engineer",
        month="August", year="2026",
        basic_salary=Decimal("80000"),
        travelling_allowance=Decimal("35000"),
        attendance_allowance=Decimal("35000"),
        other_allowances=None,
        over_time=None,
        gross_pay=Decimal("150000"),
        no_pay=Decimal("0"),
        apit_tax=Decimal("0"),
        salary_advance=None,
        epf_employee=Decimal("6400"),
        total_deduction=Decimal("6400"),
        net_salary=Decimal("143600"),
        epf_company=Decimal("9600"),
        etf_company=Decimal("2400"),
    )


def main(argv: list[str]) -> int:
    if argv:
        from salary_app.excel_reader import read_payslips
        result = read_payslips(argv[0])
        slip = result.slips[0]
        print(f"read {len(result)} employees from {result.sheet_name}; "
              f"rendering {slip.source_ref}")
    else:
        slip = demo_slip()
        print("rendering demo data")

    OUT.mkdir(parents=True, exist_ok=True)
    pdf_path = render_payslip(slip, OUT / "sample.pdf")

    png = render_page_png(pdf_path)
    (OUT / "sample.png").write_bytes(png)

    from io import BytesIO
    gray = Image.open(BytesIO(png)).convert("L").convert("RGB")
    gray.save(OUT / "sample_gray.png")

    print(f"  {pdf_path}  ({pdf_path.stat().st_size / 1024:.0f} KB)")
    print(f"  {OUT / 'sample.png'}")
    print(f"  {OUT / 'sample_gray.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
