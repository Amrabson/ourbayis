# -*- coding: utf-8 -*-
"""OurBayis money helpers — everything stored as integer minor units (agorot /
cents), never floats. See SPEC_V3.md "Currency"."""
import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CURRENCY_SYMBOLS = {"ILS": "₪", "USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$", "ZAR": "R"}
CURRENCY_CODES = {"ILS", "NIS", "USD", "EUR", "GBP", "CAD", "AUD", "ZAR"}
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
    if major == major.to_integral_value():  # whole amounts read cleaner in every currency
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


# Exchange rates: ILS per one unit of each currency. Resolution order:
#   1. OB_RATES / OB_RATES_DATE env (explicit, wins)
#   2. instance/rates.json written by `manage.py fetch-rates` (daily scheduled task)
#   3. built-in fallback {"USD": 3.7} with no date (the rate note then says "approx." only)
# The file is re-read whenever its mtime changes (see ensure_fresh), so a running
# web app picks up a fresh fetch without a reload. Estimates stay labelled as
# approximate — what a guest pays is always the store's / provider's own rate.
RATES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "rates.json")
RATES_SOURCE = ""
_DEFAULT_RATES = {"USD": 3.7}
_rates_mtime = None


def _read_rates_file():
    try:
        with open(RATES_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        rates = {str(k).upper(): float(v) for k, v in (data.get("rates") or {}).items()}
        return rates, str(data.get("date") or ""), str(data.get("source") or "")
    except (OSError, ValueError, TypeError, AttributeError):
        return None, "", ""


def _rates():
    """(rates, date, source) — see the resolution order above."""
    env = os.environ.get("OB_RATES", "")
    if env:
        try:
            raw = json.loads(env)
            return ({str(k).upper(): float(v) for k, v in raw.items()},
                    os.environ.get("OB_RATES_DATE", ""), "env")
        except (ValueError, TypeError, AttributeError):
            pass
    rates, date, source = _read_rates_file()
    if rates:
        return rates, date, source
    return dict(_DEFAULT_RATES), os.environ.get("OB_RATES_DATE", ""), ""


def _apply(rates, date, source):
    global RATES_DATE, RATES_SOURCE
    RATES.clear()
    RATES.update(rates)
    RATES_DATE = date
    RATES_SOURCE = source
    CURRENCIES[:] = ["ILS"] + [c for c in RATES if c != "ILS"]


RATES = {}
CURRENCIES = []
RATES_DATE = ""
_apply(*_rates())


def ensure_fresh():
    """Cheap per-request check: re-read instance/rates.json if it changed on
    disk (a scheduled `manage.py fetch-rates` ran). No-op when OB_RATES is set."""
    global _rates_mtime
    if os.environ.get("OB_RATES"):
        return
    try:
        mtime = os.stat(RATES_FILE).st_mtime
    except OSError:
        mtime = None
    if mtime != _rates_mtime:
        _rates_mtime = mtime
        _apply(*_rates())


FETCH_CURRENCIES = ("USD", "GBP", "EUR", "CAD", "AUD", "ZAR")
FETCH_URL = "https://api.frankfurter.app/latest?from=ILS&to={to}"


def fetch_rates(codes=FETCH_CURRENCIES, timeout=15):
    """Fetch reference rates (frankfurter.app — European Central Bank data, free,
    no key, updated on ECB business days) and write instance/rates.json.
    Returns (rates, date). Raises on network/parse errors so the scheduled task
    exits non-zero and the previous file stays in place (never writes garbage)."""
    import datetime
    import urllib.request
    url = FETCH_URL.format(to=",".join(codes))
    req = urllib.request.Request(url, headers={"User-Agent": "OurBayis rates fetch"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    per_ils = data.get("rates") or {}
    rates = {}
    for code in codes:
        v = per_ils.get(code)
        if v and float(v) > 0:
            rates[code] = round(1.0 / float(v), 4)  # ILS per one unit of `code`
    if not rates:
        raise ValueError("no usable rates in response")
    date = str(data.get("date") or datetime.date.today().isoformat())
    os.makedirs(os.path.dirname(RATES_FILE), exist_ok=True)
    tmp = RATES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"rates": rates, "date": date, "source": "frankfurter.app (ECB)",
                   "fetched_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}, fh, indent=1)
    os.replace(tmp, RATES_FILE)
    ensure_fresh()
    return rates, date


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
