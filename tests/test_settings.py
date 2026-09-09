"""Tests for persisted user settings.

Every test redirects SETTINGS_PATH into tmp_path, so the developer's real
settings file is never read or written.
"""

import json
from pathlib import Path

import pytest

from salary_app import settings


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS_PATH", path)
    return path


# --- round trip -----------------------------------------------------------

def test_set_and_read_back(settings_file, tmp_path):
    target = tmp_path / "payslips"
    target.mkdir()
    assert settings.set_output_folder(target) == target
    assert settings.output_folder() == target


def test_creates_the_config_directory(settings_file, tmp_path):
    """The folder holding settings.json may not exist on first run."""
    assert not settings_file.parent.exists()
    settings.set_output_folder(tmp_path)
    assert settings_file.exists()


def test_default_when_nothing_saved(settings_file):
    assert settings.output_folder() == settings.default_output_folder()


def test_default_is_under_documents(settings_file):
    assert settings.default_output_folder().parent.name == "Documents"


# --- resilience -----------------------------------------------------------

def test_corrupt_file_falls_back_to_defaults(settings_file):
    """A truncated or hand-edited file must not stop the app starting."""
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text("{ this is not json", encoding="utf-8")
    assert settings.load() == {}
    assert settings.output_folder() == settings.default_output_folder()


def test_non_object_json_is_ignored(settings_file):
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text('["a", "list"]', encoding="utf-8")
    assert settings.load() == {}


def test_blank_stored_folder_falls_back(settings_file):
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text(json.dumps({"output_folder": ""}), encoding="utf-8")
    assert settings.output_folder() == settings.default_output_folder()


def test_vanished_folder_falls_back(settings_file, tmp_path):
    """A folder on a disconnected drive must not block exporting."""
    gone = tmp_path / "removable" / "slips"
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text(json.dumps({"output_folder": str(gone)}),
                             encoding="utf-8")
    assert settings.output_folder() == settings.default_output_folder()


def test_folder_not_yet_created_but_parent_exists_is_kept(settings_file, tmp_path):
    """The user may pick a folder we have not written into yet."""
    chosen = tmp_path / "not-created-yet"
    settings_file.parent.mkdir(parents=True)
    settings_file.write_text(json.dumps({"output_folder": str(chosen)}),
                             encoding="utf-8")
    assert settings.output_folder() == chosen


def test_save_reports_failure_instead_of_raising(settings_file, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("read-only volume")
    monkeypatch.setattr(Path, "mkdir", boom)
    assert settings.save({"output_folder": "x"}) is False


def test_other_settings_are_preserved(settings_file, tmp_path):
    settings.save({"something_else": 42})
    settings.set_output_folder(tmp_path)
    assert settings.load()["something_else"] == 42
