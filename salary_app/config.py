"""Paths and company details -- the things you edit without touching logic.

Why a module instead of constants scattered around: when the company moves
office or the logo changes, exactly one file needs editing, and the PDF layout
code stays untouched.

The path handling here matters more than it looks. When PyInstaller freezes the
app into a single .exe, it unpacks the bundled data files into a temporary
folder at run time and points `sys._MEIPASS` at it. So "where is the logo?" has
two different answers depending on whether we are running from source or from
the built binary. `resource_path()` hides that difference, and every other
module asks it rather than building paths itself.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path


def _base_dir() -> Path:
    """Root folder for bundled read-only resources (assets, web UI).

    Frozen (.exe)  -> the temp folder PyInstaller unpacked into.
    From source    -> the repository root.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Absolute path to a bundled resource, e.g. resource_path('assets', 'x.png')."""
    return _base_dir().joinpath(*parts)


IS_FROZEN: bool = getattr(sys, "frozen", False)

ASSETS_DIR: Path = resource_path("assets")
WEB_DIR: Path = resource_path("web")
LOGO_PATH: Path = ASSETS_DIR / "logo-sm-01.png"


def output_dir() -> Path:
    """Where generated payslips are written.

    Deliberately NOT inside the app folder: a frozen app may live in
    Program Files, which is not writable by a normal user. Documents always is.
    """
    return Path.home() / "Documents" / "Salary Slips"


@dataclass(frozen=True)
class Company:
    """Printed on every payslip. Edit here, not in the layout code."""

    name: str = "Softvil Technologies (Private) Limited"
    phone: str = "(+94) 113 491 400"
    website: str = "www.softvilmedia.com"
    offices: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Corporate Office", (
            "Level 35, West Tower, World Trade Center",
            "Colombo 01, Sri Lanka.",
        )),
        ("Development Center", (
            "No: 423/2C, Old Road, Moraketiya",
            "Pannipitiya, Sri Lanka.",
        )),
    )


COMPANY = Company()

#: Printed under the net salary, e.g. "... Rupees Only".
CURRENCY_NAME = "Rupees"
CURRENCY_CODE = "LKR"
