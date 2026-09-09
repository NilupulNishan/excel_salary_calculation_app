"""End-to-end smoke test of the real window.

Starts the app, drives it through JavaScript exactly as a user would, and
reports what the DOM actually contains. This catches the class of failure unit
tests cannot see: a broken asset path, a JS exception on load, a handler that
never fires.

    .venv\\Scripts\\python.exe tools\\smoke_ui.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import webview

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salary_app.api import Api          # noqa: E402
from salary_app.config import WEB_DIR   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "Final Salary - August 2026 - Copy.xlsx"

checks: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    checks.append((name, bool(passed), detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
          + (f"  -- {detail}" if detail else ""))


def drive(window) -> None:
    """Run the scripted interaction once the page has loaded."""
    try:
        time.sleep(1.5)   # let pywebviewready fire and handlers bind

        # 1. the page loaded at all
        title = window.evaluate_js("document.title")
        check("page loaded", title == "Softvil Salary Slips", f"title={title!r}")

        # 2. the bridge is present
        ready = window.evaluate_js("typeof window.pywebview?.api?.load_path")
        check("api bridge exposed", ready == "function", f"typeof={ready}")

        # 3. no JS exception broke the handlers
        bound = window.evaluate_js(
            "!!document.getElementById('dropzone') && "
            "document.querySelectorAll('.screen').length === 3")
        check("three screens present", bound is True)

        # 4. the logo actually resolved (naturalWidth is 0 for a broken image)
        logo_w = window.evaluate_js(
            "document.querySelector('.upload-logo').naturalWidth")
        check("logo image resolves", bool(logo_w), f"naturalWidth={logo_w}")

        # 5. load the real workbook through the same call the UI makes
        if WORKBOOK.exists():
            window.evaluate_js(
                "window.pywebview.api.load_path("
                f"{json.dumps(str(WORKBOOK))}).then(onLoaded)")
            time.sleep(2.0)

            visible = window.evaluate_js(
                "document.querySelector('.screen.is-active').id")
            check("advanced to list screen", visible == "screen-list",
                  f"active={visible}")

            rows = window.evaluate_js(
                "document.querySelectorAll('#employee-rows .row').length")
            check("six employee rows rendered", rows == 6, f"rows={rows}")

            note = window.evaluate_js(
                "document.getElementById('list-note').hidden === false")
            check("incomplete-rows note shown", note is True)

            # 6. open review for one employee -> preview image must appear
            window.evaluate_js("openReview(2)")
            time.sleep(2.5)

            visible = window.evaluate_js(
                "document.querySelector('.screen.is-active').id")
            check("advanced to review screen", visible == "screen-review",
                  f"active={visible}")

            preview = window.evaluate_js(
                "document.getElementById('preview-img').naturalWidth")
            check("pdf preview rendered", bool(preview),
                  f"naturalWidth={preview}")

            fields = window.evaluate_js(
                "document.querySelectorAll('#slip-form input').length")
            check("form fields built", fields == 19, f"inputs={fields}")

            disabled = window.evaluate_js(
                "document.getElementById('btn-download').disabled")
            check("download blocked while incomplete", disabled is True)

            # 7. fill the missing identity, download should unblock
            window.evaluate_js("""
                document.getElementById('f-employee_name').value = 'Test Person';
                document.getElementById('f-employee_number').value = '70';
                document.getElementById('f-designation').value = 'Engineer';
                saveNow();
            """)
            time.sleep(2.5)

            disabled = window.evaluate_js(
                "document.getElementById('btn-download').disabled")
            check("download unblocked after filling", disabled is False)
        else:
            check("workbook present", False, f"missing {WORKBOOK.name}")

    except Exception as exc:                    # noqa: BLE001
        check("no exception during drive", False, repr(exc))
    finally:
        time.sleep(0.4)
        window.destroy()


def main() -> int:
    api = Api()
    window = webview.create_window(
        "Softvil Salary Slips",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=1280, height=860,
    )
    api.window = window

    print("driving the real window...")
    threading.Thread(target=drive, args=(window,), daemon=True).start()
    webview.start(gui="edgechromium")

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
