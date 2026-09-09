"""Tests for money coercion and display formatting."""

from decimal import Decimal

import pytest

from salary_app.money import format_money, money_or_zero, to_money


# --- coercion -------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (80000, Decimal("80000")),
    (80000.5, Decimal("80000.5")),
    ("80000", Decimal("80000")),
    ("80,000.00", Decimal("80000.00")),      # Excel thousands separator
    ("  1234.56  ", Decimal("1234.56")),     # stray whitespace
    ("LKR 6,400.00", Decimal("6400.00")),    # currency prefix
    ("Rs. 500", Decimal("500")),
    (Decimal("42"), Decimal("42")),
])
def test_to_money_accepts_real_world_shapes(raw, expected):
    assert to_money(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "-"])
def test_blank_inputs_become_none(raw):
    """A dash is how the sheet and the slip both write "nothing here"."""
    assert to_money(raw) is None


def test_parentheses_read_as_negative():
    """Accounting notation: (6,400.00) means -6400."""
    assert to_money("(6,400.00)") == Decimal("-6400.00")


def test_float_noise_does_not_survive_coercion():
    """Decimal(0.07) would be 0.070000000000000006...; str() coercion avoids it."""
    assert to_money(0.07) == Decimal("0.07")


def test_bool_is_rejected():
    """bool subclasses int, so True would silently become 1. Never intended."""
    with pytest.raises(TypeError):
        to_money(True)


def test_garbage_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        to_money("eighty thousand")


# --- formatting -----------------------------------------------------------

def test_blank_and_zero_are_different():
    """The core display rule: absent line vs nil line."""
    assert format_money(None) == ""
    assert format_money(Decimal("0")) == "-"


def test_thousands_and_two_decimals():
    assert format_money(Decimal("130000")) == "130,000.00"
    assert format_money(Decimal("1408100.5")) == "1,408,100.50"


def test_deductions_use_accounting_brackets():
    """Stored as a positive magnitude, printed bracketed."""
    assert format_money(Decimal("6400"), parenthesise=True) == "(6,400.00)"


def test_negative_without_brackets_uses_minus():
    assert format_money(Decimal("-500")) == "-500.00"


def test_zero_ignores_parenthesise():
    """Nil is a dash whether or not the column is a deduction column."""
    assert format_money(Decimal("0"), parenthesise=True) == "-"


def test_blank_placeholder_is_overridable():
    assert format_money(None, blank="n/a") == "n/a"


def test_money_or_zero():
    assert money_or_zero(None) == Decimal("0")
    assert money_or_zero(Decimal("5")) == Decimal("5")
