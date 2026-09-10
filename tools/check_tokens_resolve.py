"""Confirm every CSS token actually resolves in the real window.

A `var()` naming a token that does not exist resolves to nothing: the element
renders transparent or unstyled, no error is raised, and every functional test
still passes. This opens the app and reads the *computed* styles back, which is
the only way to catch that.

    .venv\\Scripts\\python.exe tools\\check_tokens_resolve.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import webview

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salary_app.api import Api                        # noqa: E402
from salary_app.config import WEB_DIR                 # noqa: E402
from salary_app.pdf.theme import PALETTE              # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


def drive(window) -> None:
    try:
        time.sleep(1.5)

        # 1. every palette token has a non-empty computed value
        names = json.dumps([f"--{n}" for n in PALETTE])
        missing = window.evaluate_js(f"""
            (() => {{
              const s = getComputedStyle(document.documentElement);
              return {names}.filter(n => !s.getPropertyValue(n).trim());
            }})()
        """)
        # `not missing` is also true when evaluate_js returns None -- a page
        # that never loaded, or JS that threw. That would print PASS for
        # exactly the failure this tool exists to catch.
        check("all palette tokens resolve",
              isinstance(missing, list) and not missing,
              f"missing: {missing!r}")

        # 2. radius tokens resolve
        radii = ["--radius-control", "--radius-container",
                 "--radius-large", "--radius-pill"]
        missing = window.evaluate_js(f"""
            (() => {{
              const s = getComputedStyle(document.documentElement);
              return {json.dumps(radii)}.filter(n => !s.getPropertyValue(n).trim());
            }})()
        """)
        check("all radius tokens resolve",
              isinstance(missing, list) and not missing,
              f"missing: {missing!r}")

        # 3. no element ends up with a transparent background where one was set
        probe = window.evaluate_js("""
            (() => {
              const el = document.querySelector('.dropzone');
              const s = getComputedStyle(el);
              return { bg: s.backgroundColor, radius: s.borderRadius,
                       border: s.borderTopColor };
            })()
        """)
        check("dropzone paints from tokens",
              probe["bg"] not in ("", "rgba(0, 0, 0, 0)", "transparent"),
              json.dumps(probe))

        # 4. the cyan alias chain (--cyan -> --brand-cyan) still resolves
        cyan = window.evaluate_js("""
            getComputedStyle(document.documentElement)
              .getPropertyValue('--cyan').trim()
        """)
        check("--cyan alias resolves", bool(cyan), f"value={cyan!r}")

        # 5. body font comes from the token, not a browser default
        font = window.evaluate_js("getComputedStyle(document.body).fontFamily")
        check("body font from token", "Segoe UI" in font, font)

    except Exception as exc:                            # noqa: BLE001
        check("no exception", False, repr(exc))
    finally:
        time.sleep(0.3)
        window.destroy()


def main() -> int:
    api = Api()
    window = webview.create_window(
        "Softvil Salary Slips", url=str(WEB_DIR / "index.html"),
        js_api=api, width=1280, height=860)
    api.set_window(window)

    print("checking tokens in the real window...")
    threading.Thread(target=drive, args=(window,), daemon=True).start()
    webview.start(gui="edgechromium")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
