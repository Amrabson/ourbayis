# -*- coding: utf-8 -*-
"""Affiliate tagging, applied at redirect time in /go/c/<id> and /go/i/<id>.

Pure functions (no Flask, no DB). Stored store URLs are never modified: the
owner pastes each program's ID once in /admin/affiliates and every matching
outbound click is tagged on the way out.

A rule is a dict/Row with: id, host, kind ('param' | 'wrap'), param, value, active.
  param: set query parameter `param` to `value` (e.g. amazon.com, tag=ourbayis-20)
  wrap:  `value` is an https template containing "{url}" (network deep links);
         "{url}" is replaced by the fully percent-encoded original URL.
"""
import re
from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

_HOST_RE = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}")
_PARAM_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")
_BAD_VALUE_RE = re.compile(r"[\s\x00-\x1f\x7f]")


def _get(rule, key):
    try:
        return rule[key]
    except (KeyError, IndexError):
        return None


def _hostname(url):
    """Lowercase hostname of an http(s) URL, or None."""
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            return None
        return (p.hostname or "").lower().rstrip(".") or None
    except ValueError:
        return None


def host_matches(hostname, rule_host):
    """Dot-boundary match: `hostname` equals rule_host or is a subdomain of it."""
    h = (hostname or "").lower().rstrip(".")
    r = (rule_host or "").lower().strip().rstrip(".")
    if not h or not r:
        return False
    return h == r or h.endswith("." + r)


def _template_ok(tpl):
    if not isinstance(tpl, str) or "{url}" not in tpl or _BAD_VALUE_RE.search(tpl):
        return False
    probe = tpl.replace("{url}", "x")
    try:
        p = urlsplit(probe)
    except ValueError:
        return False
    if p.scheme != "https" or "@" in p.netloc:
        return False
    host = (p.hostname or "").lower()
    return bool(_HOST_RE.fullmatch(host))


def _set_param(url, param, value):
    """Replace/add `param` in the raw query string; other params, path and
    fragment stay byte-for-byte as they were."""
    p = urlsplit(url)
    pieces = p.query.split("&") if p.query else []
    out, done = [], False
    new = f"{quote(param, safe='')}={quote(value, safe='')}"
    for piece in pieces:
        if not piece:
            continue
        key = unquote_plus(piece.split("=", 1)[0])
        if key == param:
            if not done:
                out.append(new)
                done = True
            continue
        out.append(piece)
    if not done:
        out.append(new)
    return urlunsplit((p.scheme, p.netloc, p.path, "&".join(out), p.fragment))


def tag_url(url, rules):
    """-> (final_url, rule_id_or_None). On anything unexpected, (url, None)."""
    try:
        host = _hostname(url)
        if not host:
            return url, None
        cands = [r for r in (rules or []) if _get(r, "active") and host_matches(host, _get(r, "host"))]
        cands.sort(key=lambda r: len((_get(r, "host") or "").strip()), reverse=True)
        for r in cands:
            kind, value = _get(r, "kind"), _get(r, "value") or ""
            if kind == "param":
                param = _get(r, "param") or ""
                if not _PARAM_RE.fullmatch(param) or not value or _BAD_VALUE_RE.search(value):
                    continue
                return _set_param(url, param, value), _get(r, "id")
            if kind == "wrap":
                if not _template_ok(value):
                    continue
                return value.replace("{url}", quote(url, safe="")), _get(r, "id")
        return url, None
    except Exception:
        return url, None


def validate_rule(host, kind, param, value):
    """Check admin-form input. Returns (host, kind, param, value) normalised;
    raises ValueError with a short message."""
    host = (host or "").strip().lower()
    if not _HOST_RE.fullmatch(host) or len(host) > 120:
        raise ValueError("Host must be a bare hostname like amazon.com (no https://, no path)")
    if kind not in ("param", "wrap"):
        raise ValueError("Type must be param or wrap")
    param = (param or "").strip()
    value = (value or "").strip()
    if not value or len(value) > 300 or _BAD_VALUE_RE.search(value):
        raise ValueError("Value is required, up to 300 characters, no spaces")
    if kind == "param":
        if not _PARAM_RE.fullmatch(param):
            raise ValueError("Parameter name: letters, digits, _ or -, up to 40 characters")
    else:
        param = ""
        if not _template_ok(value):
            raise ValueError("Wrap template must be an https URL containing {url}")
    return host, kind, param, value
