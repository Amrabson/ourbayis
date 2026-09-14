# -*- coding: utf-8 -*-
"""OurBayis money helpers — everything stored as integer minor units (agorot /
cents), never floats. See SPEC_V3.md "Currency"."""
import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CURRENCY_SYMBOLS = {"ILS": "₪", "USD": "$", "EUR": "€", "GBP": "£"}
CURRENCY_CODES = {"ILS", "NIS", "USD", "EUR", "GBP"}
_SYMBOL_TO_CODE = {"₪": "ILS", "$": "USD", "€": "EUR", "£": "GBP", "NIS": "ILS"}

MAX_MINOR = 10 ** 9 * 100  # reject absurd/garbage amounts (spec: reject > 10^9)


def to_minor(value, currency="ILS"):
    """Decimal-safe conversion of a user-entered amount to integer minor units.
    Rejects negative, NaN, or values over 10^9 major units. Raises ValueError."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError("bad amount")
    if not d.is_finite():
        raise ValueError("bad amount")
    if d < 0:
        raise ValueError("negative amount")
    if d > 10 ** 9:
        raise ValueError("amount too large")
    minor = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return minor


def fmt_minor(minor, currency, lang="en"):
    """₪1,234 (no decimals when the ILS amount is a whole shekel) / $1,234.50."""
    if minor is None:
        return ""
    currency = (currency or "ILS").upper()
    sym = CURRENCY_SYMBOLS.get(currency, currency + " ")
    major = Decimal(minor) / 100
    if currency == "ILS" and major == major.to_integral_value():
        body = f"{int(major):,}"
    else:
        body = f"{major:,.2f}"
    return f"{sym}{body}"


_LEGACY_RE = re.compile(
    r"^\s*(?P<sym>₪|\$|€|£|ILS|NIS|USD|EUR|GBP)?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"\s*(?P<sym2>₪|\$|€|£|ILS|NIS|USD|EUR|GBP)?\s*$"
)


def parse_legacy_amount(text):
    """Strict parse of the old free-text `claims.amount` field. Returns
    (minor, currency_code) or None — never guesses. Accepts an optional
    symbol/code before or after a number with optional thousands commas and
    at most 2 decimal places; nothing else (no words, no ranges, no 'ish')."""
    if not text:
        return None
    m = _LEGACY_RE.match(text)
    if not m:
        return None
    sym = m.group("sym") or m.group("sym2")
    if not sym:
        return None  # ambiguous — no currency marker at all
    code = _SYMBOL_TO_CODE.get(sym, sym if sym in CURRENCY_CODES else None)
    if not code:
        return None
    if code == "NIS":
        code = "ILS"
    num = m.group("num").replace(",", "")
    try:
        minor = to_minor(num, code)
    except ValueError:
        return None
    return minor, code


def _rates():
    try:
        raw = json.loads(os.environ.get("OB_RATES", "") or '{"USD": 3.7}')
    except (ValueError, TypeError):
        raw = {"USD": 3.7}
    return {str(k).upper(): float(v) for k, v in raw.items()}


RATES = _rates()
RATES_DATE = os.environ.get("OB_RATES_DATE", "")
CURRENCIES = ["ILS"] + [c for c in RATES if c != "ILS"]


def estimate(minor_ils, code):
    """Convert an ILS minor amount to another configured currency's minor
    units, or None if that currency isn't configured (never guess a rate)."""
    code = (code or "").upper()
    if code == "ILS":
        return minor_ils
    rate = RATES.get(code)
    if not rate or minor_ils is None:
        return None
    return int(round(minor_ils / rate))
