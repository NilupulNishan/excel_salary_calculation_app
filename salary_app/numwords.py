"""Spell a money amount out in English words, for the line under Net Salary.

The exact wording is not a style choice -- it is copied from the reference
payslip, which prints:

    123600.00  ->  "One Hundred Twenty Three Thousand Six Hundred Rupees Only"

Three things are pinned by that one line of evidence:

  * **Short scale.** "One Hundred Twenty Three Thousand", not the Indian
    "One Lakh Twenty Three Thousand". Sri Lankan formal English uses the
    international scale, and the reference confirms it.
  * **No "and".** Not "One Hundred and Twenty Three Thousand".
  * **No hyphens, Title Case.** "Twenty Three", not "twenty-three".

This module is deliberately pure: no I/O, no config imports, no dependencies.
That makes it trivially testable, which matters because a wrong word here is
the kind of bug that reaches an employee's payslip without anyone noticing.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Index == value, so _UNITS[7] == "Seven". Covers the irregular teens, which
# is why this runs to 19 rather than stopping at 9.
_UNITS: tuple[str, ...] = (
    "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
    "Sixteen", "Seventeen", "Eighteen", "Nineteen",
)

# Index == tens digit, so _TENS[3] == "Thirty". Slots 0 and 1 are unused:
# anything below 20 is handled by _UNITS above.
_TENS: tuple[str, ...] = (
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
    "Eighty", "Ninety",
)

# Largest first: the algorithm peels off each group in turn.
_SCALES: tuple[tuple[int, str], ...] = (
    (1_000_000_000_000, "Trillion"),
    (1_000_000_000, "Billion"),
    (1_000_000, "Million"),
    (1_000, "Thousand"),
)


def _words_under_hundred(n: int) -> list[str]:
    """0-99 as words. Assumes the caller has already handled the sign."""
    if n < 20:
        return [_UNITS[n]]
    tens, ones = divmod(n, 10)
    # "Forty" alone when ones == 0, otherwise "Forty Two".
    return [_TENS[tens]] + ([_UNITS[ones]] if ones else [])


def _words_under_thousand(n: int) -> list[str]:
    """1-999 as words, e.g. 605 -> ['Six', 'Hundred', 'Five']."""
    hundreds, rest = divmod(n, 100)
    words: list[str] = []
    if hundreds:
        words += [_UNITS[hundreds], "Hundred"]
    if rest:
        words += _words_under_hundred(rest)
    return words


def int_to_words(n: int) -> str:
    """Render a whole number in Title Case English words.

    Negatives are prefixed "Minus" rather than rejected. A negative net salary
    means something is wrong upstream, but raising here would abort an entire
    Export All run -- better to render it visibly and let validation flag it.
    """
    if n < 0:
        return "Minus " + int_to_words(-n)
    if n == 0:
        return "Zero"

    words: list[str] = []
    for value, name in _SCALES:
        group, n = divmod(n, value)
        if group:
            words += _words_under_thousand(group) + [name]
    if n:  # trailing 0-999
        words += _words_under_thousand(n)
    return " ".join(words)


def amount_to_words(
    amount,
    currency: str = "Rupees",
    fraction: str = "Cents",
    suffix: str = "Only",
) -> str:
    """Spell out a money amount the way the payslip prints it.

    Whole amounts omit the fractional clause entirely -- the reference slip
    says "... Six Hundred Rupees Only", never "... and Zero Cents".

        >>> amount_to_words(123600)
        'One Hundred Twenty Three Thousand Six Hundred Rupees Only'
        >>> amount_to_words("267900.50")
        'Two Hundred Sixty Seven Thousand Nine Hundred Rupees and Fifty Cents Only'

    `amount` is coerced via str() before Decimal so that floats do not smuggle
    in binary-representation noise (Decimal(0.07) is 0.0700000000000000006...).
    """
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    negative = value < 0
    value = abs(value)
    whole = int(value)
    cents = int((value - whole) * 100)

    parts: list[str] = []
    if negative:
        parts.append("Minus")
    parts += [int_to_words(whole), currency]
    if cents:
        parts += ["and", int_to_words(cents), fraction]
    if suffix:
        parts.append(suffix)
    return " ".join(parts)
