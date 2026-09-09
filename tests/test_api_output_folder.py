"""Tests for the output-folder setting exposed to the UI."""

import pytest
from openpyxl import Workbook

from salary_app import api as api_module
from salary_app import settings
from salary_app.api import Api
from salary_app.excel_reader import TARGET_SHEET

HEADER = [
    "EMP/EPF No:", "Name", "Designation",
    "Basic Salary ", "Attendance Allowance", "Travelling Allowance",
    "Internship Allowance /        Other All.", "Over Time", "Gross Earnings",
    "EPF (12%)", "EPF(8%)", "ETF (3%)", "APIT Tax", "Salary Advance",
    "Nopay Amount", "Total Deductions", "Net Earinings/Payable",
]
COMPLETE = [70, "Nilupul Kodikara", "AI Engineer",
            80000, 35000, 35000, None, None, 150000,
            9600, 6400, 2400, 0, None, 0, 6400, 143600]


class FakeWindow:
    """Stands in for the pywebview Window's folder dialog."""

    def __init__(self, returns):
        self.returns = returns
        self.kwargs = None

    def create_file_dialog(self, dialog_type, **kwargs):
        self.kwargs = kwargs
        return self.returns


@pytest.fixture
def loaded(tmp_path, monkeypatch):
    wb = Workbook()
    ws = wb.active
    ws.title = TARGET_SHEET
    ws.append(HEADER)
    ws.append(COMPLETE)
    path = tmp_path / "Final Salary - August 2026.xlsx"
    wb.save(path)

    # Keep every test off the developer's real settings file.
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")

    api = Api()
    api.load_path(str(path))
    return api


def test_defaults_to_documents(loaded):
    result = loaded.get_output_folder()
    assert result["ok"] is True
    assert result["isDefault"] is True
    assert result["folder"] == str(settings.default_output_folder())


def test_choosing_a_folder_persists_it(loaded, tmp_path):
    chosen = tmp_path / "payslips out"
    chosen.mkdir()
    loaded.set_window(FakeWindow(str(chosen)))

    result = loaded.choose_output_folder()
    assert result["folder"] == str(chosen)
    assert result["isDefault"] is False
    # A new Api instance must see the same folder: the setting is on disk.
    assert Api().get_output_folder()["folder"] == str(chosen)


def test_choosing_accepts_a_sequence(loaded, tmp_path):
    """Backends return either a string or a one-item sequence."""
    chosen = tmp_path / "from-list"
    chosen.mkdir()
    loaded.set_window(FakeWindow([str(chosen)]))
    assert loaded.choose_output_folder()["folder"] == str(chosen)


def test_cancelling_keeps_the_previous_folder(loaded):
    before = loaded.get_output_folder()["folder"]
    loaded.set_window(FakeWindow(None))
    result = loaded.choose_output_folder()
    assert result["cancelled"] is True
    assert loaded.get_output_folder()["folder"] == before


def test_chosen_folder_is_created_if_absent(loaded, tmp_path):
    chosen = tmp_path / "does-not-exist-yet"
    loaded.set_window(FakeWindow(str(chosen)))
    loaded.choose_output_folder()
    assert chosen.exists()


def test_export_one_writes_into_the_chosen_folder(loaded, tmp_path):
    chosen = tmp_path / "chosen"
    chosen.mkdir()
    loaded.set_window(FakeWindow(str(chosen)))
    loaded.choose_output_folder()

    result = loaded.export_one(0)
    assert result["ok"] is True
    written = chosen / "Pay Slip - August 2026 - Nilupul Kodikara.pdf"
    assert written.exists()
    assert result["path"] == str(written)


def test_export_all_writes_into_the_chosen_folder(loaded, tmp_path):
    chosen = tmp_path / "batch"
    chosen.mkdir()
    loaded.set_window(FakeWindow(str(chosen)))
    loaded.choose_output_folder()

    result = loaded.export_all()
    assert result["folder"] == str(chosen)
    assert len(list(chosen.glob("*.pdf"))) == 1


def test_choose_without_a_window_reports(loaded):
    assert loaded.choose_output_folder()["ok"] is False


def test_reveal_missing_file_reports(loaded, tmp_path):
    assert loaded.reveal(str(tmp_path / "nope.pdf"))["ok"] is False
