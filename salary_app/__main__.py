"""Entry point: open the salary slip app in its own window.

    python -m salary_app              native window (what the .exe does)
    python -m salary_app --browser    dev only; serves to the default browser

The `--browser` flag exists for debugging with real devtools. It is not a
shipped feature: nothing is exposed on a public interface.
"""

from __future__ import annotations

import argparse
import sys

import webview

from .api import Api
from .config import WEB_DIR

WINDOW_TITLE = "Softvil Salary Slips"
MIN_SIZE = (1100, 720)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="salary_app", description=__doc__)
    parser.add_argument("--browser", action="store_true",
                        help="development only: open in the default browser")
    parser.add_argument("--debug", action="store_true",
                        help="enable devtools and verbose logging")
    args = parser.parse_args(argv)

    if not args.browser and not webview2_available():
        print(
            "Microsoft Edge WebView2 Runtime is required but was not found.\n\n"
            "It ships with Windows 11. On older Windows, install the Evergreen\n"
            "runtime from:\n"
            "  https://developer.microsoft.com/microsoft-edge/webview2/\n",
            file=sys.stderr,
        )
        return 2

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
    api.window = window

    webview.start(debug=args.debug, gui="edgechromium" if not args.browser else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
