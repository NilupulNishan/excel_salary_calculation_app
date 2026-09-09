"""Fonts, colours and drawing primitives shared by every payslip design.

Kept separate from the designs so that switching layout does not mean
re-deriving the palette or re-solving logo placement.

**Fonts.** Windows-only app, so the fonts Windows always ships are used
directly (Segoe UI, Calibri, Palatino Linotype, Georgia). Nothing is bundled,
which keeps the .exe smaller and sidesteps font redistribution licensing
entirely. ReportLab embeds a *subset* of the glyphs actually used into the PDF,
which is exactly what the existing June payslip already does -- it carries
`BCDEEE+PalatinoLinotype-Roman`. So this matches the current workflow rather
than introducing a new licensing question.

**Colours.** Sampled from the supplied logo, not invented: the mark's cyan is
#00CFFF and the wordmark is #232323. Cyan that bright is unreadable as text on
white, so a deepened variant is used for anything that carries meaning and the
pure cyan is reserved for rules and accents.

**The logo needs trimming.** `logo-sm-01.png` is a 2084x2084 canvas holding
only 1339x829 of actual artwork -- roughly 60% is transparent padding. Placed
untrimmed it renders small and visibly off-centre, so `logo_image()` crops to
the real bounding box and caches the result.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..config import LOGO_PATH

# --- page -----------------------------------------------------------------

PAGE_W, PAGE_H = 595.28, 841.89          # A4 in points
MARGIN = 42.0

# --- palette --------------------------------------------------------------

BRAND_CYAN = HexColor("#00CFFF")         # straight from the logo
BRAND_DEEP = HexColor("#0B7FA8")         # readable stand-in for the cyan
INK = HexColor("#232323")                # the wordmark's black
INK_SOFT = HexColor("#5A5F66")           # secondary text
RULE = HexColor("#D8DEE4")               # hairlines
BAND = HexColor("#F4F7F9")               # zebra / section fill
BAND_DEEP = HexColor("#E8F6FC")          # tinted highlight
WHITE = HexColor("#FFFFFF")
POSITIVE = HexColor("#1B7F4B")
NEGATIVE = HexColor("#B4342B")

# --- fonts ----------------------------------------------------------------

_WINDOWS_FONTS = "C:/Windows/Fonts"

#: name used in code -> file on disk
FONT_FILES: dict[str, str] = {
    "Sans": "segoeui.ttf",
    "Sans-Bold": "segoeuib.ttf",
    "Sans-Light": "segoeuisl.ttf",
    "Serif": "pala.ttf",
    "Serif-Bold": "palab.ttf",
    "Slab": "georgia.ttf",
    "Slab-Bold": "georgiab.ttf",
}

_registered = False


def register_fonts() -> None:
    """Register the system fonts once per process. Safe to call repeatedly."""
    global _registered
    if _registered:
        return
    for name, filename in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, f"{_WINDOWS_FONTS}/{filename}"))
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold")
    pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-Bold")
    _registered = True


# --- logo -----------------------------------------------------------------

@lru_cache(maxsize=4)
def logo_image(path: str | None = None) -> ImageReader | None:
    """The logo cropped to its artwork, ready to draw. None if unavailable.

    Cropping matters: the source PNG is ~60% transparent padding, so an
    untrimmed placement looks small and sits visibly high in its box.
    """
    from PIL import Image

    source = path or str(LOGO_PATH)
    try:
        image = Image.open(source).convert("RGBA")
    except (OSError, ValueError):
        return None
    box = image.getbbox()          # alpha-aware: ignores transparent padding
    if box:
        image = image.crop(box)
    return ImageReader(image)


@lru_cache(maxsize=4)
def logo_image_white(path: str | None = None) -> ImageReader | None:
    """Knockout version: the artwork silhouette in white, alpha preserved.

    The logo's wordmark is #232323. Dropped onto a dark header band it becomes
    invisible -- which is exactly what happened on the first render of the
    `statement` design. Recolouring to a white silhouette is the standard fix
    for reversed-out branding and keeps the mark legible on any dark fill.
    """
    from PIL import Image

    source = path or str(LOGO_PATH)
    try:
        image = Image.open(source).convert("RGBA")
    except (OSError, ValueError):
        return None
    box = image.getbbox()
    if box:
        image = image.crop(box)
    white = Image.new("RGBA", image.size, (255, 255, 255, 0))
    white.putalpha(image.getchannel("A"))
    return ImageReader(white)


def logo_aspect(path: str | None = None) -> float:
    """Width / height of the trimmed artwork, for proportional placement."""
    reader = logo_image(path)
    if reader is None:
        return 1.615               # measured fallback
    width, height = reader.getSize()
    return width / height


# --- drawing primitives ---------------------------------------------------

class Canvas:
    """Thin wrapper over ReportLab's canvas.

    Two conveniences that remove most of the noise from layout code: a
    top-down y-axis (`y()`), because designs are easier to reason about
    measured from the top of the page, and text helpers that set font and
    colour in one call.
    """

    def __init__(self, canvas):
        self.c = canvas

    # -- coordinates
    @staticmethod
    def y(top_down: float) -> float:
        """Convert a distance from the page top into ReportLab's y."""
        return PAGE_H - top_down

    # -- text
    def text(self, x, top, string, font="Sans", size=9.0, color=INK,
             align="left", leading=None):
        """Draw a string. `align` is one of left / right / center."""
        if string is None or string == "":
            return
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        y = self.y(top)
        if align == "right":
            self.c.drawRightString(x, y, str(string))
        elif align == "center":
            self.c.drawCentredString(x, y, str(string))
        else:
            self.c.drawString(x, y, str(string))

    def wrapped(self, x, top, string, width, font="Sans", size=9.0,
                color=INK, leading=12.0) -> float:
        """Draw text wrapped to `width`. Returns the new top offset."""
        if not string:
            return top
        words, line, lines = str(string).split(), "", []
        for word in words:
            trial = f"{line} {word}".strip()
            if pdfmetrics.stringWidth(trial, font, size) <= width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for offset, text in enumerate(lines):
            self.text(x, top + offset * leading, text, font, size, color)
        return top + len(lines) * leading

    # -- shapes
    def rule(self, x0, top, x1, color=RULE, width=0.6):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        y = self.y(top)
        self.c.line(x0, y, x1, y)

    def box(self, x, top, width, height, fill=None, stroke=None,
            line_width=0.6, radius=None):
        if fill:
            self.c.setFillColor(fill)
        if stroke:
            self.c.setStrokeColor(stroke)
            self.c.setLineWidth(line_width)
        y = self.y(top + height)
        args = dict(stroke=1 if stroke else 0, fill=1 if fill else 0)
        if radius:
            self.c.roundRect(x, y, width, height, radius, **args)
        else:
            self.c.rect(x, y, width, height, **args)

    def logo(self, x, top, height, path=None, white=False):
        """Place the trimmed logo, scaled from its height.

        `white=True` draws the knockout silhouette, for dark backgrounds.
        """
        reader = logo_image_white(path) if white else logo_image(path)
        if reader is None:
            return
        width = height * logo_aspect(path)
        self.c.drawImage(reader, x, self.y(top + height), width, height,
                         mask="auto")
        return width


def money_color(value: Decimal | None, negative_is_red: bool = False) -> Color:
    if negative_is_red and value is not None and value < 0:
        return NEGATIVE
    return INK
