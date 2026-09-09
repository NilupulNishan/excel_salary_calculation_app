"""Tests for the amount-to-words converter.

The single most important test here is `test_matches_june_reference_payslip`:
it asserts the exact string printed on the real June 2026 payslip. If that
ever fails, generated slips no longer match the document they replace.
"""

from decimal import Decimal

import pytest

from salary_app.numwords import amount_to_words, int_to_words


# --- the load-bearing test ------------------------------------------------

def test_matches_june_reference_payslip():
    """Character-exact string extracted from the reference PDF."""
    assert amount_to_words(123600) == (
        "One Hundred Twenty Three Thousand Six Hundred Rupees Only"
    )


# --- integer wording ------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (0, "Zero"),
    (7, "Seven"),
    (13, "Thirteen"),          # irregular teen, not "Ten Three"
    (20, "Twenty"),            # no trailing unit
    (23, "Twenty Three"),      # no hyphen
    (100, "One Hundred"),
    (105, "One Hundred Five"), # no "and"
    (999, "Nine Hundred Ninety Nine"),
    (1_000, "One Thousand"),
    (80_000, "Eighty Thousand"),
    (143_600, "One Hundred Forty Three Thousand Six Hundred"),
    (1_408_100, "One Million Four Hundred Eight Thousand One Hundred"),
])
def test_int_to_words(value, expected):
    assert int_to_words(value) == expected


def test_short_scale_not_indian_numbering():
    """100000 is 'One Hundred Thousand', never 'One Lakh'."""
    words = int_to_words(100_000)
    assert words == "One Hundred Thousand"
    assert "Lakh" not in words and "Crore" not in words


# --- money formatting -----------------------------------------------------

def test_whole_amount_omits_cents_clause():
    result = amount_to_words(80_000)
    assert result == "Eighty Thousand Rupees Only"
    assert "Cents" not in result


def test_cents_are_spelled_out():
    assert amount_to_words("267900.50") == (
        "Two Hundred Sixty Seven Thousand Nine Hundred Rupees "
        "and Fifty Cents Only"
    )


def test_zero_amount():
    assert amount_to_words(0) == "Zero Rupees Only"


@pytest.mark.parametrize("value", [123600, "123600", 123600.0, Decimal("123600.00")])
def test_accepts_int_str_float_and_decimal(value):
    """The reader may hand us any of these; all must agree."""
    assert amount_to_words(value) == (
        "One Hundred Twenty Three Thousand Six Hundred Rupees Only"
    )


def test_float_noise_does_not_leak_through():
    """Decimal(0.07) is 0.07000000000000000666...; str() coercion avoids it."""
    assert amount_to_words(1234.07) == (
        "One Thousand Two Hundred Thirty Four Rupees and Seven Cents Only"
    )


def test_rounds_half_up():
    """Money convention: 0.005 rounds away from zero, not to even."""
    assert amount_to_words("10.005") == "Ten Rupees and One Cents Only"
    assert amount_to_words("10.004") == "Ten Rupees Only"


def test_negative_renders_rather_than_raising():
    """A negative net is a data problem, but it must not abort Export All."""
    assert amount_to_words(-500) == "Minus Five Hundred Rupees Only"


def test_currency_words_are_overridable():
    assert amount_to_words(5, currency="Dollars", fraction="Cents") == (
        "Five Dollars Only"
    )
    assert amount_to_words(5, suffix="") == "Five Rupees"
