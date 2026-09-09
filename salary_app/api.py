"""The bridge the UI calls into.

Every method returns a plain dict shaped `{"ok": bool, ...}` with an "error"
key when something failed. Exceptions are caught and converted rather than
allowed to escape: an unhandled exception in a pywebview js_api call surfaces
in JavaScript as an opaque rejection, which is useless to a user holding a
workbook that will not open.

Money crosses this boundary as **strings**, never JavaScript numbers -- a float
round-trip would silently corrupt cents. See `models.Payslip.to_dict`.
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import traceback
from pathlib import Path

from .config import output_dir
from .excel_reader import WorkbookError, read_payslips
from .models import (
    DEDUCTION_FIELDS, EARNINGS_FIELDS, COMPANY_FIELDS, FIELD_LABELS,
    IDENTITY_FIELDS, Payslip, consistency_warnings, missing_required,
)
from .pdf.preview import render_page_data_url
from .pdf.renderer import render_payslip

#: Preview resolution. High enough that 7pt labels stay legible, low enough
#: that a re-render on every edit stays responsive.
PREVIEW_SCALE = 1.7


def _fail(message: str) -> dict:
    return {"ok": False, "error": message}


def guard(method):
    """Turn any unexpected exception into a readable `{"ok": False}` result."""
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except WorkbookError as exc:
            return _fail(str(exc))
        except Exception as exc:                      # noqa: BLE001
            traceback.print_exc()
            return _fail(f"{type(exc).__name__}: {exc}")
    wrapper.__name__ = method.__name__
    return wrapper


class Api:
    """Backend for the three screens: upload, employee list, review."""

    def __init__(self) -> None:
        self.slips: list[Payslip] = []
        self.source_path: str = ""
        self.sheet_name: str = ""
        self.window = None
        self._temp = Path(tempfile.mkdtemp(prefix="salaryslip-"))

    # -- screen 1: loading a workbook ------------------------------------

    @guard
    def browse(self) -> dict:
        """Native file dialog, then load. Returns the same shape as `load_*`."""
        if self.window is None:
            return _fail("Window not ready")
        chosen = self.window.create_file_dialog(
            10,  # webview.OPEN_DIALOG
            allow_multiple=False,
            file_types=("Excel workbook (*.xlsx;*.xlsm)", "All files (*.*)"),
        )
        if not chosen:
            return {"ok": True, "cancelled": True}
        return self.load_path(chosen[0])

    @guard
    def load_path(self, path: str) -> dict:
        """Read a workbook already on disk."""
        return self._load(Path(path))

    @guard
    def load_bytes(self, filename: str, b64: str) -> dict:
        """Read a workbook dropped onto the window.

        pywebview 6.2 exposes no file-drop event, so a dropped file's path is
        unavailable. The UI reads the bytes instead and sends them here, and we
        stage them in the session temp folder. The filename is preserved
        because the month and year are parsed from it.
        """
        safe = Path(filename).name or "dropped.xlsx"
        staged = self._temp / safe
        staged.write_bytes(base64.b64decode(b64))
        return self._load(staged)

    def _load(self, path: Path) -> dict:
        result = read_payslips(path)
        self.slips = result.slips
        self.source_path = result.source_path
        self.sheet_name = result.sheet_name
        return {
            "ok": True,
            "file": Path(result.source_path).name,
            "sheet": result.sheet_name,
            "headerRow": result.header_row,
            "unmapped": result.unmapped_headers,
            "employees": self.list_employees(),
        }

    # -- screen 2: the employee list -------------------------------------

    def list_employees(self) -> list[dict]:
        """Summary rows, including why a slip is not ready to issue."""
        rows = []
        for index, slip in enumerate(self.slips):
            missing = missing_required(slip)
            rows.append({
                "index": index,
                "name": slip.employee_name or "(no name in sheet)",
                "number": slip.employee_number,
                "designation": slip.designation,
                "net": slip.display("net_salary"),
                "period": slip.period,
                "sourceRef": slip.source_ref,
                "missing": missing,
                "ready": not missing,
                "warnings": consistency_warnings(slip),
            })
        return rows

    # -- screen 3: review ------------------------------------------------

    @guard
    def get_slip(self, index: int) -> dict:
        slip = self._slip(index)
        return {
            "ok": True,
            "slip": slip.to_dict(),
            "fields": self._field_groups(),
            "missing": missing_required(slip),
            "warnings": consistency_warnings(slip),
            "preview": self._preview(index, slip),
        }

    @guard
    def update_slip(self, index: int, data: dict) -> dict:
        """Apply edits from the form and re-render.

        The whole record is rebuilt rather than patched field by field, so
        coercion in `Payslip.__post_init__` runs over every value exactly as it
        does when reading the workbook.
        """
        slip = self._slip(index)
        merged = slip.to_dict()
        merged.update(data or {})
        updated = Payslip.from_dict(merged)
        updated.source_ref = slip.source_ref
        self.slips[index] = updated
        return {
            "ok": True,
            "slip": updated.to_dict(),
            "missing": missing_required(updated),
            "warnings": consistency_warnings(updated),
            "preview": self._preview(index, updated),
            "employees": self.list_employees(),
        }

    def _preview(self, index: int, slip: Payslip) -> str:
        pdf_path = self._temp / f"preview_{index}.pdf"
        render_payslip(slip, pdf_path)
        return render_page_data_url(pdf_path, scale=PREVIEW_SCALE)

    @staticmethod
    def _field_groups() -> list[dict]:
        """Form layout: which fields belong together and what to call them."""
        groups = (
            ("Employee", IDENTITY_FIELDS),
            ("Earnings", EARNINGS_FIELDS),
            ("Deductions", DEDUCTION_FIELDS),
            ("Company Contribution", COMPANY_FIELDS),
        )
        return [
            {
                "title": title,
                "fields": [{"name": n, "label": FIELD_LABELS.get(n, n)}
                           for n in names],
            }
            for title, names in groups
        ]

    # -- output ----------------------------------------------------------

    @guard
    def export_one(self, index: int) -> dict:
        slip = self._slip(index)
        missing = missing_required(slip)
        if missing:
            return _fail("Cannot export yet - missing: " + ", ".join(missing))
        target = output_dir() / slip.output_filename()
        render_payslip(slip, target)
        return {"ok": True, "path": str(target), "folder": str(output_dir())}

    @guard
    def export_all(self) -> dict:
        """Write every complete slip. Incomplete ones are reported, not guessed.

        A slip with no employee name would also collide on filename with every
        other unnamed slip, so skipping is the only safe behaviour.
        """
        if not self.slips:
            return _fail("No workbook loaded")

        folder = output_dir()
        written: list[str] = []
        skipped: list[dict] = []
        for index, slip in enumerate(self.slips):
            missing = missing_required(slip)
            if missing:
                skipped.append({
                    "index": index,
                    "name": slip.employee_name or slip.source_ref,
                    "missing": missing,
                })
                continue
            render_payslip(slip, folder / slip.output_filename())
            written.append(slip.output_filename())

        return {
            "ok": True,
            "written": written,
            "skipped": skipped,
            "folder": str(folder),
        }

    @guard
    def print_slip(self, index: int) -> dict:
        """Send the slip to the Windows print dialog.

        `window.print()` in the webview would print the HTML shell, not the
        PDF. Writing the real PDF and invoking the shell's print verb prints
        the actual document.
        """
        slip = self._slip(index)
        pdf_path = self._temp / f"print_{index}.pdf"
        render_payslip(slip, pdf_path)
        try:
            os.startfile(str(pdf_path), "print")            # noqa: S606
        except OSError:
            # No app registered for the print verb; open it so the user can
            # print manually rather than failing silently.
            os.startfile(str(pdf_path))                     # noqa: S606
            return {"ok": True, "opened": True, "path": str(pdf_path)}
        return {"ok": True, "printed": True, "path": str(pdf_path)}

    @guard
    def open_folder(self) -> dict:
        folder = output_dir()
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(folder)])         # noqa: S607
        return {"ok": True, "folder": str(folder)}

    # -- helpers ---------------------------------------------------------

    def _slip(self, index: int) -> Payslip:
        if not 0 <= index < len(self.slips):
            raise IndexError(f"No employee at position {index}")
        return self.slips[index]
