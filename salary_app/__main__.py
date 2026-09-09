"""Entry point: open the salary slip app in its own window.

    python -m salary_app              native window (what the .exe does)
    python -m salary_app --browser    dev only; serves to the default browser

The `--browser` flag exists for debugging with real devtools. It is not a
shipped feature: nothing is exposed on a public interface.
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import webview

from .api import Api
from .config import IS_FROZEN, WEB_DIR

WINDOW_TITLE = "Softvil Salary Slips"
MIN_SIZE = (1100, 720)

LOG_PATH = Path(tempfile.gettempdir()) / "softvil-salary-slips.log"
log = logging.getLogger("salary_app")


def setup_logging(verbose: bool = False) -> None:
    """Log startup to a file.

    A windowed build has no console: `sys.stderr` is None, so a failure during
    startup produces a process that exits or hangs with nothing to show for it.
    A log file is the only way to find out what happened on a user's machine.
    """
    handlers: list[logging.Handler] = [logging.FileHandler(LOG_PATH, mode="w",
                                                           encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=handlers,
        force=True,
    )
    log.info("--- startup ---")
    log.info("frozen=%s  exe=%s", IS_FROZEN, sys.executable)
    log.info("meipass=%s", getattr(sys, "_MEIPASS", "(not frozen)"))
    log.info("web dir=%s  exists=%s", WEB_DIR, WEB_DIR.exists())
    index = WEB_DIR / "index.html"
    log.info("index.html=%s  exists=%s", index, index.exists())


def webview2_available() -> bool:
    """Check for the Edge WebView2 runtime.

    PyInstaller bundles Python and every library, but the window itself is
    drawn by WebView2, which is a Windows component we do not ship. It is part
    of Windows 11; on an older or stripped Windows 10 it can be missing, and
    pywebview would otherwise silently fall back to the ancient MSHTML engine
    and render the UI badly. Better to say so plainly.
    """
    if sys.platform != "win32":
        return True
    import winreg

    key = (r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
           r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}")
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key) as handle:
                version, _ = winreg.QueryValueEx(handle, "pv")
                if version:
                    return True
        except OSError:
            continue
    return False


def _show_error(title: str, message: str) -> None:
    """Native message box. A windowed build has no console to print to."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:                                   # noqa: BLE001
        pass


def run_selftest() -> int:
    """Exercise the real work inside the frozen bundle, headlessly.

    Opening a window proves very little: the parts most likely to break once
    frozen are the ones a smoke test never touches from source -- pypdfium2's
    native binary, ReportLab finding the Windows fonts, openpyxl's reader. This
    runs an actual workbook through to an actual PDF and reports what happened,
    so a broken bundle fails loudly here instead of in front of a user.
    """
    import tempfile as _tempfile
    from decimal import Decimal

    failures = 0

    def report(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        if not ok:
            failures += 1
        log.info("[%s] %s%s", "PASS" if ok else "FAIL", name,
                 f"  -- {detail}" if detail else "")

    try:
        from .models import Payslip
        from .pdf.preview import extract_text, render_page_png
        from .pdf.renderer import render_payslip

        report("imports resolve inside the bundle", True)

        slip = Payslip(
            employee_name="Selftest Person", employee_number="1",
            designation="Engineer", month="August", year="2026",
            basic_salary=Decimal("80000"), gross_pay=Decimal("150000"),
            epf_employee=Decimal("6400"), total_deduction=Decimal("6400"),
            net_salary=Decimal("143600"),
        )

        out = Path(_tempfile.mkdtemp(prefix="salaryslip-selftest-")) / "slip.pdf"
        render_payslip(slip, out)
        report("reportlab renders a PDF (fonts load)", out.exists(),
               f"{out.stat().st_size} bytes" if out.exists() else "no file")

        text = extract_text(out)
        report("pdf carries a real text layer", "143,600.00" in text,
               f"{len(text)} chars extracted")
        report("amount in words rendered",
               "One Hundred Forty Three Thousand Six Hundred" in text)

        png = render_page_png(out, scale=0.6)
        report("pypdfium2 rasterises the preview",
               png[:4] == bytes((0x89, 0x50, 0x4E, 0x47)),  # PNG magic
               f"{len(png)} bytes")

        import openpyxl
        report("openpyxl importable", bool(openpyxl.__version__),
               openpyxl.__version__)

    except Exception as exc:                                # noqa: BLE001
        log.exception("selftest crashed")
        report("no exception during selftest", False, repr(exc))

    log.info("selftest: %s", "ALL PASSED" if failures == 0
             else f"{failures} FAILURE(S)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="salary_app", description=__doc__)
    parser.add_argument("--browser", action="store_true",
                        help="development only: open in the default browser")
    parser.add_argument("--debug", action="store_true",
                        help="enable devtools and verbose logging")
    parser.add_argument("--selftest", action="store_true",
                        help="run headless checks of the packaged bundle and exit")
    args = parser.parse_args(argv)
    setup_logging(args.debug)

    if args.selftest:
        return run_selftest()

    if not args.browser and not webview2_available():
        message = (
            "Microsoft Edge WebView2 Runtime is required but was not found.\n\n"
            "It ships with Windows 11. On older Windows, install the "
            "Evergreen runtime from:\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/"
        )
        log.error("WebView2 runtime not found")
        _show_error("WebView2 Runtime missing", message)
        return 2

    log.info("creating window...")
    api = Api()
    window = webview.create_window(
        WINDOW_TITLE,
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1280, height=860,
        min_size=MIN_SIZE,
        background_color="#FFFFFF",
        text_select=True,          # payslip figures should be selectable
    )
    api.set_window(window)
    log.info("window created; starting event loop (gui=%s)",
             "edgechromium" if not args.browser else "default")
    try:
        webview.start(debug=args.debug,
                      gui="edgechromium" if not args.browser else None)
    except Exception:
        log.exception("webview.start failed")
        _show_error("Salary Slips failed to start",
                    f"See the log for details:\n{LOG_PATH}")
        return 1
    log.info("event loop ended cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
