# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Softvil Salary Slips app.

Build:
    .venv\\Scripts\\pyinstaller.exe packaging\\salary_app.spec --noconfirm

Produces dist/SoftvilSalarySlips.exe -- one file, no installer, no Python
needed on the target machine.

Three things this spec exists to get right:

**The web UI must be bundled as data.** index.html, the CSS, the JS and the
logo are read from disk at runtime. `config.resource_path()` resolves them via
`sys._MEIPASS` when frozen, so they must land at the same relative paths.

**pywebview's WebView2 interop is not discovered automatically.** The
edgechromium backend loads .NET assemblies (Microsoft.Web.WebView2.Core.dll and
friends) that PyInstaller's import analysis cannot see, because they are loaded
through pythonnet at runtime rather than imported. Missing them means the window
never opens, with no useful error.

**Console stays off.** A console window flashing behind a desktop app looks
broken. Set `console=True` temporarily if you need to see a traceback.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = Path(SPECPATH)
ROOT = SPEC_DIR.parent

# A windowed build swallows startup errors: the process exits with no window
# and no message. Building with SALARY_APP_CONSOLE=1 produces a console
# variant under a different name, so a failing launch prints its traceback.
#
#   $env:SALARY_APP_CONSOLE=1; .venv\Scripts\pyinstaller.exe build\salary_app.spec
DEBUG_CONSOLE = os.environ.get("SALARY_APP_CONSOLE") == "1"
EXE_NAME = "SoftvilSalarySlips-console" if DEBUG_CONSOLE else "SoftvilSalarySlips"

datas = [
    # (source, destination inside the bundle)
    (str(ROOT / "web"), "web"),
]

# pywebview ships the WebView2 interop DLLs as package data; collect them all
# rather than naming files that move between releases.
datas += collect_data_files("webview")

hiddenimports = [
    "clr_loader",
    "pythonnet",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
]
hiddenimports += collect_submodules("pypdfium2")

a = Analysis(
    # run_app.py, not salary_app/__main__.py: PyInstaller runs its entry script
    # as a top-level `__main__` with no package context, so that module's
    # relative imports fail with "attempted relative import with no known
    # parent package".
    [str(ROOT / "run_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Dev-only. PyMuPDF especially: it is AGPL-3.0 and must never end up
        # inside a distributed binary. pypdfium2 does the runtime rendering.
        "fitz", "pymupdf", "pytest", "_pytest",
        "tkinter", "matplotlib", "numpy", "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX-packed .exe files trip antivirus heuristics
    runtime_tmpdir=None,
    console=DEBUG_CONSOLE,   # SALARY_APP_CONSOLE=1 to see startup tracebacks
    disable_windowed_traceback=False,
    icon=str(SPEC_DIR / "app.ico"),
)
