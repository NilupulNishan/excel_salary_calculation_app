"""Tests for the shared design system.

These exist because the app chrome and the payslip are two renderers of one
brand, and they had already drifted: `--rule` was #E2E8ED in the stylesheet
while the PDF drew #D8DEE4. Nothing caught it, because nothing was checking.
"""

import re
from pathlib import Path

import pytest

from salary_app.pdf import renderer, theme
from salary_app.pdf.theme import PALETTE, contrast_ratio

ROOT = Path(__file__).resolve().parent.parent
TOKENS_CSS = ROOT / "web" / "tokens.css"
STYLES_CSS = ROOT / "web" / "styles.css"


# --- the generated stylesheet stays in step with the palette ---------------

def test_tokens_css_is_up_to_date():
    """Regenerate with `python tools/make_tokens.py` if this fails."""
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.make_tokens import render

    assert TOKENS_CSS.exists(), "run tools/make_tokens.py"
    assert TOKENS_CSS.read_text(encoding="utf-8") == render(), (
        "web/tokens.css is stale -- run tools/make_tokens.py")


def test_every_palette_colour_reaches_the_css():
    css = TOKENS_CSS.read_text(encoding="utf-8")
    for name, value in PALETTE.items():
        assert f"--{name}:" in css, name
        assert value in css, f"{name} = {value}"


def test_stylesheet_declares_no_brand_colours_of_its_own():
    """Colours belong in theme.PALETTE, not here.

    Plain #fff / #000 are allowed: they are not brand colours, and pinning
    them to a token would only add indirection.
    """
    css = STYLES_CSS.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)      # strip comments
    stray = [hex_value for hex_value in re.findall(r"#[0-9a-fA-F]{3,6}\b", css)
             if hex_value.lower() not in ("#fff", "#000", "#ffffff", "#000000")]
    assert stray == [], f"untokenised colours in styles.css: {stray}"


def test_stylesheet_uses_radius_tokens_only():
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert re.search(r"border-radius:\s*\d", css) is None, (
        "hard-coded radius in styles.css -- use a --radius-* token")


# --- contrast -------------------------------------------------------------

#: (foreground, background, minimum). 4.5 is WCAG AA for normal text.
TEXT_PAIRS = [
    ("ink", "#FFFFFF", 4.5),
    ("ink", "band", 4.5),
    ("ink-soft", "#FFFFFF", 4.5),
    ("ink-soft", "band", 4.5),
    ("brand-deep", "#FFFFFF", 4.5),
    ("danger", "danger-bg", 4.5),
    ("warn", "warn-bg", 4.5),
]


@pytest.mark.parametrize("fg,bg,minimum", TEXT_PAIRS)
def test_text_colours_meet_wcag_aa(fg, bg, minimum):
    foreground = PALETTE.get(fg, fg)
    background = PALETTE.get(bg, bg)
    ratio = contrast_ratio(foreground, background)
    assert ratio >= minimum, f"{fg} on {bg} is {ratio:.2f}:1, needs {minimum}"


def _calls(source: str, name: str) -> list[str]:
    """Every `name(...)` call in `source`, with balanced parentheses.

    A regex like `g\\.text\\([^)]*\\)` stops at the FIRST `)`, so any call
    containing `slip.display(field)` was truncated before its colour and size
    arguments -- silently exempting four of the seven call sites from the two
    checks below. Scanning for the matching paren is the only way to see the
    whole call.
    """
    found, needle = [], f"{name}("
    index = source.find(needle)
    while index != -1:
        depth, cursor = 0, index + len(needle) - 1
        while cursor < len(source):
            if source[cursor] == "(":
                depth += 1
            elif source[cursor] == ")":
                depth -= 1
                if depth == 0:
                    found.append(source[index:cursor + 1])
                    break
            cursor += 1
        index = source.find(needle, index + 1)
    return found


def _split_args(call: str) -> list[str]:
    """Top-level comma-separated arguments of a call, nested calls intact."""
    inner = call[call.index("(") + 1:-1]
    args, depth, current = [], 0, ""
    for char in inner:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        args.append(current.strip())
    return args


def test_the_call_scanner_sees_whole_calls():
    """Guards the guard: the previous regex truncated at the first ')'."""
    sample = 'g.text(x, y, slip.display(f), "Sans", BODY, INK, align="right")'
    calls = _calls(sample, "g.text")
    assert len(calls) == 1 and calls[0] == sample
    assert _split_args(calls[0])[4] == "BODY"


def test_brand_cyan_is_unusable_as_text_and_is_never_used_as_text():
    """The reason cyan is confined to rules and bars, asserted rather than
    left as a comment someone can quietly break."""
    assert contrast_ratio(PALETTE["brand-cyan"], "#FFFFFF") < 3.0

    code = _code_only(ROOT / "salary_app" / "pdf" / "renderer.py")
    calls = _calls(code, "g.text") + _calls(code, "g.micro")
    assert len(calls) >= 7, f"only found {len(calls)} text calls -- scanner broken"
    for call in calls:
        assert "BRAND_CYAN" not in call, f"cyan used as text: {call[:70]}"


# --- the type scale -------------------------------------------------------

def test_type_scale_has_one_size_per_role():
    sizes = [theme.DISPLAY, theme.FIGURE, theme.LEAD,
             theme.BODY, theme.FINE, theme.MICRO]
    assert len(set(sizes)) == len(sizes), "two roles share a size"
    assert sizes == sorted(sizes, reverse=True), "scale is out of order"


def test_renderer_carries_no_raw_font_sizes():
    """Every size comes from the scale; the page used to hold thirteen."""
    code = _code_only(ROOT / "salary_app" / "pdf" / "renderer.py")
    roles = {"DISPLAY", "FIGURE", "LEAD", "BODY", "FINE", "MICRO"}
    checked = 0
    for call in _calls(code, "g.text"):
        args = _split_args(call)
        assert len(args) >= 5, f"g.text call with no explicit size: {call[:70]}"
        assert args[4] in roles, f"raw size {args[4]!r} in {call[:70]}"
        checked += 1
    assert checked >= 7, f"only checked {checked} calls -- scanner broken"


# --- the grid -------------------------------------------------------------

def test_employee_strip_sits_on_the_column_pitch():
    """Its second field was at MARGIN + 300 -- 33.36pt off the page grid."""
    assert renderer.COL_PITCH == pytest.approx(
        renderer.COL_W + renderer.GUTTER)
    col_one = renderer.MARGIN + theme.BAND_PAD
    col_two = col_one + renderer.COL_PITCH
    assert col_two - col_one == pytest.approx(renderer.COL_PITCH)
    assert col_two != pytest.approx(342.0), "back on the old arbitrary offset"


def _code_only(path: Path) -> str:
    """Source with docstrings and comments removed.

    Needed because these files explain the values they replaced, so a plain
    substring search finds the history in the prose and fails on it.
    """
    source = path.read_text(encoding="utf-8")
    source = re.sub(r'"""(?:.|\n)*?"""', "", source)
    source = re.sub(r"#.*", "", source)
    return source


def test_only_two_inner_paddings_exist():
    """Banded blocks used 8, 14 and 16 before; now two named values."""
    assert theme.BAND_PAD != theme.ROW_PAD
    code = _code_only(ROOT / "salary_app" / "pdf" / "renderer.py")
    assert "MARGIN + 300" not in code, "the off-grid offset is back"
    assert "BAND_PAD" in code and "ROW_PAD" in code


# --- fonts ----------------------------------------------------------------

def test_only_the_faces_the_design_draws_are_registered():
    """Georgia and Palatino were registered for rejected candidates and never
    drawn -- a machine without them crashed on a font the payslip never uses."""
    assert set(theme.FONT_FILES) == {"Sans", "Sans-Bold", "Sans-Light"}

    source = (ROOT / "salary_app" / "pdf" / "renderer.py").read_text(
        encoding="utf-8")
    for face in re.findall(r'"(Sans[\w-]*)"', source):
        assert face in theme.FONT_FILES, f"{face} is drawn but not registered"
