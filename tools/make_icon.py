"""Build the Windows app icon from the logo.

    .venv\\Scripts\\python.exe tools\\make_icon.py

Two things matter for an icon that does not look broken in the taskbar:

**Trim, then pad to square.** The source PNG is a 2084x2084 canvas holding only
1339x829 of artwork. Squashing that rectangle into a square icon distorts the
mark; padding it into a square canvas keeps the proportions and centres it.

**Ship every size.** Windows picks a bitmap from the .ico by context -- 16px in
the title bar, 32px in the taskbar, 256px in large-icon views. Letting Windows
downscale a single 256px bitmap to 16px produces a smudge, so each size is
resampled with Lanczos and stored.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "web" / "logo-sm-01.png"
TARGET = ROOT / "build" / "app.ico"

SIZES = (16, 24, 32, 48, 64, 128, 256)

#: Fraction of the canvas the artwork occupies. A little breathing room stops
#: the mark touching the edges at small sizes.
INSET = 0.86


def build_icon(source: Path = SOURCE, target: Path = TARGET) -> Path:
    image = Image.open(source).convert("RGBA")

    box = image.getbbox()          # alpha-aware: drops transparent padding
    if box:
        image = image.crop(box)

    side = int(max(image.size) / INSET)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))

    frames = [canvas.resize((s, s), Image.LANCZOS) for s in SIZES]

    target.parent.mkdir(parents=True, exist_ok=True)
    frames[-1].save(target, format="ICO",
                    sizes=[(s, s) for s in SIZES], append_images=frames[:-1])
    return target


def main() -> int:
    if not SOURCE.exists():
        print(f"logo not found: {SOURCE}", file=sys.stderr)
        return 1
    path = build_icon()
    print(f"wrote {path}  ({path.stat().st_size / 1024:.1f} KB, "
          f"sizes {', '.join(str(s) for s in SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
