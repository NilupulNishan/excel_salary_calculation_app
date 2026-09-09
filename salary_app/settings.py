"""User settings that persist between runs.

Currently just the output folder, but the shape is here for anything else that
should be remembered.

Stored in %APPDATA%\\SoftvilSalarySlips\\settings.json rather than beside the
executable: a frozen app may live in Program Files, which a normal user cannot
write to. Settings must never fail to save because of where the app installed.

Every read is defensive. A settings file can be hand-edited, truncated by a
crash, or written by a newer version -- none of which should stop the app
starting. A bad file falls back to defaults rather than raising.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "SoftvilSalarySlips"


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / APP_NAME


SETTINGS_PATH: Path = _config_dir() / "settings.json"


def default_output_folder() -> Path:
    """Where payslips go until the user picks somewhere else."""
    return Path.home() / "Documents" / "Salary Slips"


def load() -> dict:
    """Read the settings file. Returns {} if absent or unreadable."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        # Missing, unreadable, or corrupt -- defaults are always safe here.
        return {}


def save(data: dict) -> bool:
    """Write settings. Returns False rather than raising if it cannot."""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        return True
    except OSError:
        return False


def output_folder() -> Path:
    """The folder payslips are written to.

    Falls back to the default if the stored path is blank or has since been
    deleted -- a saved folder on a disconnected USB drive should not leave the
    user unable to export.
    """
    stored = load().get("output_folder")
    if stored:
        candidate = Path(stored)
        if candidate.exists() or candidate.parent.exists():
            return candidate
    return default_output_folder()


def set_output_folder(path: str | Path) -> Path:
    """Remember `path` as the output folder and return it."""
    folder = Path(path)
    data = load()
    data["output_folder"] = str(folder)
    save(data)
    return folder
