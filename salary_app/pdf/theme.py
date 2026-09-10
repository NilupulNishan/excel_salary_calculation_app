"""Fonts, colours and drawing primitives shared by every payslip design.

Kept separate from the designs so that switching layout does not mean
re-deriving the palette or re-solving logo placement.

**Fonts.** Windows-only app, so the fonts Windows always ships are used
directly -- Segoe UI in three weights, and nothing else: see `FONT_FILES`.
Nothing is bundled, which keeps the .exe smaller and sidesteps font
redistribution licensing entirely. ReportLab embeds a *subset* of the glyphs
actually used, which is what the reference June payslip already did, so this
matches the existing workflow rather than raising a new licensing question.

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

from functools import lru_cache

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..config import LOGO_PATH

# --- page -----------------------------------------------------------------

PAGE_W, PAGE_H = 595.28, 841.89          # A4 in points
MARGIN = 42.0

# --- palette --------------------------------------------------------------
#
# THE SINGLE SOURCE OF TRUTH FOR COLOUR, across the PDF *and* the app chrome.
# `tools/make_tokens.py` generates `web/tokens.css` from `PALETTE` below, and
# `tests/test_design_tokens.py` fails if the two drift apart. Before that,
# `--rule` was #E2E8ED in the CSS and #D8DEE4 here: the same role, two values,
# nothing to catch it. Add a colour here, never in the stylesheet.
#
# Every colour used for TEXT meets WCAG AA against its background (asserted in
# the tests). Brand cyan is 1.85:1 on white -- unusable as text -- so it is
# reserved for rules, bars and borders, and the tests assert it stays there.

#: token name -> hex. Names become CSS custom properties (`--brand-cyan`).
PALETTE: dict[str, str] = {
    "brand-cyan": "#00CFFF",     # straight from the logo; never text
    "brand-deep": "#0B7FA8",     # readable stand-in for the cyan (4.55:1)
    "ink": "#232323",            # the wordmark's black
    "ink-soft": "#5A5F66",       # secondary text (6.43:1 on white)
    "rule": "#D8DEE4",           # hairlines; the print-safe of the two
    "band": "#F4F7F9",           # zebra / section fill
    "band-deep": "#E8F6FC",      # tinted highlight
    "surface": "#FCFDFE",        # dropzone rest state
    "surface-sunken": "#EEF1F4", # preview pane behind the page
    "border-soft": "#C3CCD4",    # dashed dropzone border
    "danger": "#B4342B",         # 5.56:1 on danger-bg
    "danger-bg": "#FDF3F2",
    "danger-border": "#F3D3D0",
    "warn": "#9A6700",           # 4.55:1 on warn-bg
    "warn-bg": "#FDF7E6",
}

BRAND_CYAN = HexColor(PALETTE["brand-cyan"])
BRAND_DEEP = HexColor(PALETTE["brand-deep"])
INK = HexColor(PALETTE["ink"])
INK_SOFT = HexColor(PALETTE["ink-soft"])
RULE = HexColor(PALETTE["rule"])
BAND = HexColor(PALETTE["band"])
BAND_DEEP = HexColor(PALETTE["band-deep"])
NEGATIVE = HexColor(PALETTE["danger"])

# --- type scale -----------------------------------------------------------
#
# Six roles, in points. The payslip previously carried THIRTEEN sizes
# (6.4 6.5 6.8 7 7.4 8 8.4 8.6 9 10 10.5 19 30), four of which -- 6.4, 6.5,
# 6.8 and 7 -- were all doing the same job: uppercase micro-labels. Rows were
# 8.4 and their totals 8.6, a difference nobody can see, where the WEIGHT
# already carried the distinction.
#
# DISPLAY and FIGURE sit deliberately outside the text scale: a document's
# title and its one headline number are allowed to be exceptional.
#
# BODY at 8.6pt follows this document's own precedent -- the reference June
# payslip set its body at 8.76pt, and 8-9pt is normal for payslips and
# invoices. It is not the 12pt floor that governs posters read across a room.

DISPLAY = 30.0     # "Payslip"
FIGURE = 19.0      # the net salary amount
LEAD = 10.5        # company name, employee name, EMP NO, period, values
BODY = 8.6         # designation, breakdown rows, totals, labels
FINE = 7.4         # addresses, amount in words, footer, currency code
MICRO = 6.8        # EVERY uppercase label

#: Extra letter-spacing for MICRO, matching the app's `letter-spacing: .06em`.
#: Uppercase text needs tracking to stay legible at this size, and this was
#: the one place the two surfaces treated the same element differently.
MICRO_TRACKING = 0.4

# --- spacing --------------------------------------------------------------
# Named rather than a strict baseline grid: forcing one would rewrite the
# layout for little gain, but named steps make the rhythm inspectable.

SPACE_SM = 8.0
SPACE_MD = 14.0
SPACE_LG = 22.0
SPACE_XL = 38.0

#: Inner padding for banded blocks (employee strip, net salary) and for the
#: denser breakdown rows. Two deliberate values replaced three accidental
#: ones (8, 14 and 16).
BAND_PAD = 14.0
ROW_PAD = 8.0

#: Corner radius for filled bands on the page.
BAND_RADIUS = 4.0

# --- fonts ----------------------------------------------------------------

_WINDOWS_FONTS = "C:/Windows/Fonts"

#: name used in code -> file on disk.
#:
#: Only the faces the design actually draws. Serif (Palatino) and Slab
#: (Georgia) were registered here for two rejected design candidates and never
#: drawn again -- which meant a machine without Georgia crashed at startup on
#: a font the payslip does not use.
FONT_FILES: dict[str, str] = {
    "Sans": "segoeui.ttf",
    "Sans-Bold": "segoeuib.ttf",
    "Sans-Light": "segoeuisl.ttf",
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
             align="left", leading=None, tracking=0.0):
        """Draw a string. `align` is one of left / right / center.

        `tracking` adds letter-spacing in points -- used for uppercase
        micro-labels, which need it to stay legible at 6.8pt.

        It is passed to ReportLab's own draw methods rather than applied by
        hand. Character spacing (`Tc`) is PDF graphics state and is not reset
        by ending a text object, so a hand-rolled version leaks tracking into
        every later string on the page -- which it did: the footer note ended
        up 19.6pt past the right margin. ReportLab's methods set `Tc` and put
        it back to 0, and compute the aligned width as `(len - 1) * charSpace`
        (tracking sits BETWEEN characters, not after the last one).
        """
        if string is None or string == "":
            return
        string = str(string)
        y = self.y(top)
        self.c.setFont(font, size)
        self.c.setFillColor(color)
        if align == "right":
            self.c.drawRightString(x, y, string, charSpace=tracking)
        elif align == "center":
            self.c.drawCentredString(x, y, string, charSpace=tracking)
        else:
            self.c.drawString(x, y, string, charSpace=tracking)

    def micro(self, x, top, string, color=INK_SOFT, align="left"):
        """An uppercase micro-label: one size, one weight, one tracking.

        A helper rather than a convention, because the four sizes this
        replaces (6.4, 6.5, 6.8, 7) drifted apart precisely because each call
        site chose its own.
        """
        self.text(x, top, string, "Sans-Bold", MICRO, color,
                  align=align, tracking=MICRO_TRACKING)

    @staticmethod
    def wrap_lines(string, width, font="Sans", size=9.0) -> list[str]:
        """Break `string` into lines that fit `width`, without drawing.

        Separate from `wrapped` so a caller can size a filled band BEFORE
        drawing the text on top of it. The band is painted first, so its height
        has to be known first -- otherwise a value that wraps to a second line
        spills below the band, which is exactly what used to happen to a long
        job title.
        """
        if not string:
            return []
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
        return lines

    def wrapped(self, x, top, string, width, font="Sans", size=9.0,
                color=INK, leading=12.0) -> float:
        """Draw text wrapped to `width`. Returns the new top offset."""
        lines = self.wrap_lines(string, width, font, size)
        for offset, text in enumerate(lines):
            self.text(x, top + offset * leading, text, font, size, color)
        return top + len(lines) * leading

    # -- shapes
    def rule(self, x0, top, x1, color=RULE, width=0.6):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        y = self.y(top)
        self.c.line(x0, y, x1, y)

    def vrule(self, x, top0, top1, color=RULE, width=0.6):
        """Vertical hairline between two top-down offsets.

        Drawn as a real stroked line rather than a 0.6pt filled box: a box that
        thin lands between device pixels and prints as a smear or vanishes,
        whereas a stroke is snapped by the renderer.
        """
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        self.c.line(x, self.y(top0), x, self.y(top1))

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


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.x contrast ratio between two hex colours.

    Here rather than only in the tests so a colour decision can be checked at
    the point it is made. AA wants 4.5:1 for normal text, 3:1 for large.
    """
    def luminance(hex_colour: str) -> float:
        value = hex_colour.lstrip("#")
        channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                  for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)),
                         reverse=True)
    return (light + 0.05) / (dark + 0.05)
