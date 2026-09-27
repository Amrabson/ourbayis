# -*- coding: utf-8 -*-
"""OurBayis security helpers: env parsing, open-redirect guards, payment-link
allowlisting, tokens, and a DB-backed rate limiter. See SPEC_V3.md "Security"."""
import hashlib
import re
import secrets
import time
from urllib.parse import urlparse, unquote

from flask import request


def load_env_file(path):
    """Read KEY=VALUE lines from a private settings file (default
    instance/ob.env, gitignored) into os.environ without overriding anything
    already set. Both the web app and manage.py call this, so scheduled tasks
    (send-mail, remind-claims) see the same SMTP/base-URL settings as the site.
    Blank lines and # comments are skipped; surrounding quotes are stripped."""
    import os
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return 0
    n = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip().removeprefix("export ").strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val
            n += 1
    return n


def env_file_path(base):
    import os
    return os.environ.get("OB_ENV_FILE") or os.path.join(base, "instance", "ob.env")


def env_bool(name, default=False):
    import os
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def safe_next(url):
    """Only ever allow a same-site, single-leading-slash relative path. Rejects
    protocol-relative (`//evil.com`), backslash tricks (`/\\evil.com`), absolute
    URLs, encoded slashes, javascript: etc. Returns None if unsafe."""
    if not url or len(url) > 500:
        return None
    if any(ord(c) < 0x20 for c in url):
        return None
    decoded = unquote(url)
    for candidate in (url, decoded):
        if not candidate.startswith("/"):
            return None
        if candidate.startswith("//") or candidate.startswith("/\\"):
            return None
        parsed = urlparse(candidate)
        if parsed.scheme or parsed.netloc:
            return None
    return url


def same_origin_referrer():
    """Return the referrer's path+query if it's same-origin (host match),
    else None. Used by /lang and /currency so they never redirect off-site."""
    ref = request.referrer
    if not ref:
        return None
    try:
        parsed = urlparse(ref)
    except ValueError:
        return None
    if parsed.netloc != request.host:
        return None
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return path


_PRIVATE_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


# one address, no list/display-name syntax: a comma, semicolon, angle bracket, quote or
# whitespace could turn one "email" field into several recipients or break the header
_EMAIL_RE = re.compile(r"[^@\s,;<>()\[\]\"\\:]+@[^@\s,;<>()\[\]\"\\:']+\.[^@\s,;<>()\[\]\"\\:']+")


def valid_email(s):
    return bool(s) and len(s) <= 200 and bool(_EMAIL_RE.fullmatch(s))


def validate_url(u):
    """General external-URL sanity check (store/affiliate links): http(s),
    has a host, no embedded userinfo, not a bare IP/localhost, reasonable length."""
    if not u or len(u) > 500 or re.search(r"\s", u):
        return False
    try:
        p = urlparse(u)
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    if not p.netloc or "@" in p.netloc:
        return False
    host = p.hostname or ""
    # a real dotted hostname (labels of letters/digits/hyphens, IDN letters allowed) —
    # rejects "https://bad link" style input that urlparse happily accepts
    if not re.fullmatch(r"(?:[\w-]+\.)+[\w-]{2,}", host) or "_" in host:
        return False
    if host.lower() in _PRIVATE_HOSTS:
        return False
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        return False
    return True


# provider -> allowed exact hostnames (lowercase, no trailing dot)
_PAY_HOSTS = {
    "paypal": {"paypal.me", "www.paypal.me", "paypal.com", "www.paypal.com"},
    "stripe": {"buy.stripe.com", "donate.stripe.com"},
    "bit": {"bitpay.co.il", "www.bitpay.co.il"},
    "paybox": {"payboxapp.com", "www.payboxapp.com", "link.payboxapp.com"},
}


def classify_pay_url(u):
    """Classify a couple-entered payment link into a known provider by exact
    host match (never substring — blocks paypal.me.evil.com / evil.com/paypal.me).
    Returns (provider, url). Raises ValueError('pay_url_bad_<provider-guess>')
    with an i18n key the caller can show, defaulting to a generic key."""
    if not u or len(u) > 300:
        raise ValueError("pay_url_bad")
    candidate = u if "://" in u else "https://" + u
    try:
        p = urlparse(candidate)
    except ValueError:
        raise ValueError("pay_url_bad")
    if p.scheme not in ("http", "https"):
        raise ValueError("pay_url_bad")
    host = (p.hostname or "").lower().rstrip(".")
    for provider, hosts in _PAY_HOSTS.items():
        if host in hosts:
            if provider == "paypal" and host in ("paypal.com", "www.paypal.com"):
                if not p.path.lower().startswith("/paypalme/"):
                    continue
            return provider, candidate
    # best-effort guess for a friendlier error key
    for provider, hosts in _PAY_HOSTS.items():
        if any(host.endswith("." + h) or provider in host for h in hosts):
            raise ValueError(f"pay_url_bad_{provider}")
    raise ValueError("pay_url_bad")


def new_token():
    return secrets.token_urlsafe(32)


def hash_token(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


_rate_call_count = 0


def rate_limited(db, bucket, key, limit, per):
    """SQLite-backed rate limiter: True if `key` already made `limit` calls to
    `bucket` in the last `per` seconds. Records this call either way. Prunes
    rows older than 1h roughly every 100 calls so the table can't grow forever."""
    global _rate_call_count
    now = time.time()
    cutoff = now - per
    n = db.execute(
        "SELECT COUNT(*) FROM rate_events WHERE bucket=? AND key=? AND ts>?",
        (bucket, key, cutoff)).fetchone()[0]
    over = n >= limit
    if not over:
        db.execute("INSERT INTO rate_events (bucket, key, ts) VALUES (?,?,?)",
                   (bucket, key, now))
    _rate_call_count += 1
    if _rate_call_count % 100 == 0:
        db.execute("DELETE FROM rate_events WHERE ts < ?", (now - 3600,))
    return over
