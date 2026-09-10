"""Generate web/tokens.css from the palette in salary_app/pdf/theme.py.

    .venv\\Scripts\\python.exe tools\\make_tokens.py

The app chrome and the payslip are two renderers of one brand. Keeping the
colours in two hand-maintained lists is what let `--rule` become #E2E8ED in the
stylesheet while the PDF drew #D8DEE4 -- the same role, two values, and nothing
to notice. `theme.PALETTE` is now the only place a colour is decided, and
`tests/test_design_tokens.py` fails if this file is out of date.

Radii and the font stack live here too, so the two surfaces cannot disagree
about a control's corner either.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from salary_app.pdf.theme import PALETTE          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "web" / "tokens.css"

#: Radii, as roles rather than the seven ad-hoc values the stylesheet grew
#: (5, 6, 8, 10, 14, 20, 22 -- only one of them tokenised).
RADII: dict[str, str] = {
    "radius-control": "6px",     # buttons, inputs, the path field
    "radius-container": "8px",   # rows, notes, alerts, errors
    "radius-large": "12px",      # the dropzone
    "radius-pill": "999px",      # badges, toasts, the preview chip
}

EXTRAS: dict[str, str] = {
    "font": '"Segoe UI", system-ui, -apple-system, sans-serif',
    #: The toast scrim. Kept as rgba because it sits over live content.
    "scrim": "rgba(35, 35, 35, .82)",
}

HEADER = """/* GENERATED FILE -- DO NOT EDIT.
 *
 * Written by tools/make_tokens.py from the palette in
 * salary_app/pdf/theme.py, which is the single source of truth for colour
 * across the app chrome and the payslip PDF.
 *
 * To change a colour, edit theme.PALETTE and re-run:
 *     .venv\\Scripts\\python.exe tools\\make_tokens.py
 */
"""


def render() -> str:
    lines = [HEADER, ":root {"]

    lines.append("  /* palette -- from salary_app/pdf/theme.py */")
    width = max(len(name) for name in PALETTE)
    for name, value in PALETTE.items():
        lines.append(f"  --{name}:{' ' * (width - len(name))} {value};")

    lines.append("")
    lines.append("  /* radii */")
    width = max(len(name) for name in RADII)
    for name, value in RADII.items():
        lines.append(f"  --{name}:{' ' * (width - len(name))} {value};")

    lines.append("")
    for name, value in EXTRAS.items():
        lines.append(f"  --{name}: {value};")

    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> int:
    css = render()
    current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
    if current == css:
        print(f"{TARGET.name} already up to date ({len(PALETTE)} colours)")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(css, encoding="utf-8")
    print(f"wrote {TARGET}  ({len(PALETTE)} colours, {len(RADII)} radii)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
