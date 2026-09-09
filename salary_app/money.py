"""Money coercion and display formatting.

Split out from `models` because both the PDF renderer and the on-screen form
need the same rules. If formatting lived in one of them, the other would
eventually grow a near-copy that drifts.

Two rules drive everything here.

**Decimal, never float.** Payroll money must not go through binary floating
point. `0.1 + 0.2 != 0.3` in float, and a cent of drift on a salary document
is indefensible. Every amount becomes a `Decimal`, coerced via `str()` so
float noise never enters in the first place.

**Blank and zero are different things.** On the reference payslip, "No Pay"
and "APIT Tax" print a dash (the line applies, the amount is nil) while
"Other Allowances" and "Over Time" print nothing at all (the line does not
apply to this employee). Both are 0 in the spreadsheet. Collapsing them would
lose real meaning, so:

    None -> ""      the line does not apply; print nothing
    0    -> "-"     the line applies and is nil
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

#: A money value that may legitimately be absent. See the blank/zero note above.
Money = Decimal | None


def to_money(value) -> Money:
    """Coerce a spreadsheet cell or form input to Decimal, preserving blanks.

    Returns None for anything genuinely empty. Accepts the shapes openpyxl and
    the JS bridge actually hand us: int, float, str, Decimal, None.

    Strings are cleaned of the decoration humans and Excel add -- thousands
    separators, currency codes, whitespace -- and accounting-style parentheses
    are read as negative, since "(6,400.00)" means -6400 on a payslip.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool is a subclass of int; treating True as 1 here is never intended.
        raise TypeError("bool is not a money value")
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value).strip()
    if not text or text == "-":
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace("_", "").strip()
    for token in ("LKR", "Rs.", "Rs", "rs"):
        if text.startswith(token):
            text = text[len(token):].strip()
    if not text:
        return None

    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a money value: {value!r}") from exc
    return -amount if negative else amount


def format_money(value: Money, parenthesise: bool = False, blank: str = "") -> str:
    """Render an amount for display. See the blank/zero rule above.

    `parenthesise` wraps the figure in brackets, the accounting convention for
    deductions. It applies to the magnitude, so a deduction stored as a
    positive 6400 still prints as "(6,400.00)".
    """
    if value is None:
        return blank
    if value == 0:
        return "-"
    text = f"{abs(value):,.2f}"
    if parenthesise:
        return f"({text})"
    return f"-{text}" if value < 0 else text


def money_or_zero(value: Money) -> Decimal:
    """Treat a blank as nil. For arithmetic that must not crash on None.

    Note this is for *display and comparison* helpers only -- it is never used
    to derive a payslip figure. See the no-calculation rule in the package
    docstring.
    """
    return Decimal("0") if value is None else value
