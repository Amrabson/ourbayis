# -*- coding: utf-8 -*-
"""OurBayis — gift registries for building a home in Israel.

Single-file Flask app (same architecture as BashertBench):
server-rendered Jinja2, SQLite next to the app, no build step.
Run:  python app.py   →  http://127.0.0.1:5001

Phase 1 (v3 P0): see SPEC_V3.md. Database, security, mail and money live in
the small ob_*.py helper modules; this file stays the routes file.
"""
import csv
import gzip
import io
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import BadSignature, URLSafeSerializer
from markupsafe import Markup, escape

import guides as ob_guides
import i18n as i18n_mod
import ob_affiliate
import ob_db
import ob_hebcal
import ob_linkinfo
import ob_mail
import ob_money
import ob_search
import ob_security
from i18n import CATEGORIES, EVENT_TYPES, T_EN, cat_label, format_date, t as _t, t_count

BASE = Path(__file__).resolve().parent
ob_security.load_env_file(ob_security.env_file_path(BASE))  # instance/ob.env, before any env read
DB_PATH =Path(os.environ.get("OB_DB_PATH") or (BASE / "ourbayis.db"))

BRAND = "OurBayis"
BRAND_HE = "OurBayis"
ILS_PER_USD = float(os.environ.get("OB_ILS_PER_USD", "3.1"))
CONTACT_WHATSAPP = os.environ.get("OB_WHATSAPP", "")  # e.g. 972501234567
BASE_URL = os.environ.get("OB_BASE_URL", "").rstrip("/")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("OB_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Optional SMTP — leave unset and the site works fine, mail just stays queued.
NOTIFY_EMAIL = os.environ.get("OB_NOTIFY_EMAIL", "")  # owner: shana leads + contact msgs

app = Flask(__name__)
if ob_security.env_bool("OB_TRUST_PROXY"):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ---------------------------------------------------------------- secret key
_secret = os.environ.get("OB_SECRET_KEY")
if not _secret:
    if ob_security.env_bool("OB_SECURE_COOKIES") or os.environ.get("OB_ENV") == "production":
        raise RuntimeError(
            "OB_SECRET_KEY is required (OB_SECURE_COOKIES/OB_ENV=production is set). "
            "Set it in the environment before starting the app.")
    _instance = BASE / "instance"
    _instance.mkdir(exist_ok=True)
    _secret_file = _instance / "dev_secret.txt"
    if _secret_file.exists():
        _secret = _secret_file.read_text(encoding="utf-8").strip()
    if not _secret:
        _secret = secrets.token_hex(32)
        _secret_file.write_text(_secret, encoding="utf-8")

app.config.update(
    SECRET_KEY=_secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=ob_security.env_bool("OB_SECURE_COOKIES"),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self'; "
    "img-src 'self' https: data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)

NO_STORE_ENDPOINTS = {
    "dashboard", "registry_new", "registry_edit", "items_manage",
    "guest_manage", "admin_home", "admin_login", "reset_password", "forgot",
    "dashboard_thanks", "dashboard_keepsake", "registry_people", "join_registry", "registry_check", "digest_off",
}

# SPEC_V3 "Privacy / SEO": private/account/admin pages are never indexed.
# `registry` overrides this per-request based on `visibility` (see the route).
NOINDEX_ENDPOINTS = {
    "dashboard", "dashboard_qr", "dashboard_print", "dashboard_shared",
    "dashboard_claims_csv", "dashboard_thanks", "dashboard_keepsake", "registry_new", "registry_edit", "items_manage",
    "items_add", "items_starter", "item_edit", "guest_manage", "account",
    "account_export", "account_delete", "admin_home", "admin_login",
    "reset_password", "forgot", "signup", "login", "registry_people", "join_registry", "registry_check", "digest_off",
}


# ---------------------------------------------------------------- compression
# Registered before every other after_request hook, so Flask runs it last (hooks run in reverse).
GZIP_MIMETYPES = {"text/html", "text/css", "text/plain", "text/csv", "text/javascript",
                  "application/javascript", "application/json", "application/xml", "image/svg+xml"}
# BREACH: compressing a page that holds a secret (the CSRF token) next to text an attacker can
# choose lets them guess the secret from response sizes. Only pages whose query string carries
# nothing but these (never echoed) keys are compressed; search/filter pages (?q=, ?cat=) are not.
GZIP_SAFE_ARGS = {"lang", "preview"}


_STATIC_GZ = {}  # (path, mtime) -> gzipped bytes, so each static file is compressed once per version


def _gzip_static(resp):
    """CSS/JS/SVG from Flask's own static route: compressed from the file (the response is a
    passthrough file stream, which gzip_response leaves alone). With a PythonAnywhere static
    mapping these requests never reach Flask; see DEPLOY_AI.md for checking that path."""
    path = os.path.join(app.static_folder, request.view_args.get("filename", ""))
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return resp
    if key not in _STATIC_GZ:
        with open(path, "rb") as fh:
            _STATIC_GZ[key] = gzip.compress(fh.read(), compresslevel=9)
    resp.direct_passthrough = False
    resp.set_data(_STATIC_GZ[key])
    resp.headers["Content-Encoding"] = "gzip"
    resp.vary.add("Accept-Encoding")
    return resp


@app.after_request
def gzip_response(resp):
    """gzip text responses for browsers that accept it: the registry page carries one claim dialog
    per gift (~100 KB for 23 gifts -> ~10 KB). PythonAnywhere serves Flask output uncompressed."""
    if (request.endpoint == "static" and request.method == "GET" and resp.status_code == 200
            and resp.mimetype in ("text/css", "text/javascript", "application/javascript", "image/svg+xml")
            and "Content-Encoding" not in resp.headers and not request.range
            and "gzip" in (request.headers.get("Accept-Encoding") or "").lower()):
        return _gzip_static(resp)
    if (request.method != "GET" or not 200 <= resp.status_code < 300 or resp.direct_passthrough
            or resp.is_streamed or "Content-Encoding" in resp.headers
            or resp.mimetype not in GZIP_MIMETYPES
            or not set(request.args) <= GZIP_SAFE_ARGS
            or "gzip" not in (request.headers.get("Accept-Encoding") or "").lower()):
        return resp
    data = resp.get_data()
    if len(data) < 1024:
        return resp
    resp.set_data(gzip.compress(data, compresslevel=6))
    resp.headers["Content-Encoding"] = "gzip"
    resp.vary.add("Accept-Encoding")
    return resp


# ---------------------------------------------------------------- security
PUBLIC_VIEW_ENDPOINTS = {"index", "catalog_page", "registry", "sample", "shana", "how", "about",
                         "find", "advertise", "privacy", "terms", "contact", "guides", "guide", "gift_ideas",
                         "catalog_item", "gift_category", "setup_cost"}


@app.after_request
def count_page_views(resp):
    """Privacy-safe per-page counters (no IP, no UA, no path params): one
    funnel row per endpoint per day, for public HTML GETs only. Feeds the
    admin funnel table and the audience figures the owner can quote to
    advertisers. Owners viewing their own registry are not counted."""
    try:
        if (request.method == "GET" and resp.status_code == 200
                and request.endpoint in PUBLIC_VIEW_ENDPOINTS
                and resp.mimetype == "text/html" and not session.get("admin")):
            owner_uid = None
            if request.endpoint == "registry" and getattr(g, "registry_owner_uid", None):
                owner_uid = g.registry_owner_uid
            track("view:" + request.endpoint, owner_uid=owner_uid)
    except Exception:  # noqa: BLE001 — counting must never break a page
        pass
    return resp


@app.before_request
def refresh_rates():
    ob_money.ensure_fresh()  # picks up instance/rates.json written by `manage.py fetch-rates`


@app.before_request
def remember_owner_lang():
    """Emails to a couple go out in the language they use the site in — not the language of
    the guest whose action triggered them."""
    lang = request.args.get("lang")
    if lang in ("en", "he") and session.get("uid"):
        get_db().execute("UPDATE users SET lang=? WHERE id=? AND lang IS NOT ?", (lang, session["uid"], lang))


@app.before_request
def check_host():
    if ALLOWED_HOSTS and request.host.split(":")[0] not in ALLOWED_HOSTS:
        abort(400)


@app.after_request
def set_security_headers(resp):
    resp.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.endpoint in NO_STORE_ENDPOINTS or (request.path.startswith("/g/")):
        resp.headers["Cache-Control"] = "no-store"
    elif request.endpoint == "static" and request.args.get("v") and resp.status_code == 200:
        # versioned URL (see static_cache_bust) — a new file gets a new URL, so cache for good
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    if resp.mimetype == "text/html":
        resp.vary.add("Accept-Language")     # current_lang() falls back to it on a first visit
    return resp


@app.url_defaults
def static_cache_bust(endpoint, values):
    """Append ?v=<mtime> to every url_for('static', ...) so browsers can keep
    CSS/JS/images cached (one fewer round-trip per page for guests abroad)
    and still pick up a deploy immediately."""
    if endpoint == "static" and "v" not in values and values.get("filename"):
        try:
            mtime = os.stat(os.path.join(app.static_folder, values["filename"])).st_mtime_ns
        except (OSError, ValueError):
            return
        values["v"] = format(mtime // 1_000_000, "x")


def _ensure_csrf():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("_csrf")
        sent = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, sent):
            # almost always a page left open past a sign-out or a server restart: say that, not "something went wrong"
            abort(app.make_response((render_template("error.html", code=400, csrf_failed=True,
                                                     signed_out=not session.get("uid")), 400)))


def rate_limited(bucket, limit=20, per=600):
    return ob_security.rate_limited(get_db(), bucket, request.remote_addr, limit, per)


def send_mail(to, subject, body, reply_to=""):
    return ob_mail.enqueue(get_db(), to, subject, body, db_path=DB_PATH, reply_to=reply_to)


def notify_owner(db, reg, key, fallback_lang, item=None, qty=1, to_helpers=False, **kw):
    """`<key>_subj` / `<key>_body` to the registry owner — and, with `to_helpers` (the gift emails),
    to every helper who turned them on — each in their own language (users.lang; falls back to the
    current reader's), with the registry title / item name in that language and a dashboard link."""
    people = [db.execute("SELECT email, lang FROM users WHERE id=?", (reg["user_id"],)).fetchone()]
    if to_helpers:
        people += db.execute(
            "SELECT u.email, u.lang FROM registry_members m JOIN users u ON u.id = m.user_id"
            " WHERE m.registry_id=? AND m.notify=1 ORDER BY u.id", (reg["id"],)).fetchall()
    for person in people:
        if not person or not person["email"]:
            continue
        lang = person["lang"] if person["lang"] in ("en", "he") else fallback_lang
        he = lang == "he"
        words = dict(kw)
        words.setdefault("title", (reg["title_he"] if he and reg["title_he"] else reg["title"]))
        words["msg"] = (_t("mail_reserved_msg", lang).format(msg=kw["guest_message"])
                        if kw.get("guest_message") else "")
        if item is not None:
            name = item["name_he"] if he and item["name_he"] else item["name"]
            words["item"] = f"{name} ×{qty}" if qty > 1 else name
        body = (_t(key + "_body", lang).format(**words) + "\n\n"
                + _t("mail_owner_footer", lang).format(link=ext_url("dashboard")))
        send_mail(person["email"], _t(key + "_subj", lang).format(**words), body)


def chip_label(amount_minor, item_name, item_name_he, lang):
    """"₪180 toward Fridge" / "₪180 עבור מקרר": how a chip-in contribution reads in mails and lists."""
    name = item_name_he if lang == "he" and item_name_he else item_name
    return tf("chip_toward", lang, amount=ob_money.fmt_minor(amount_minor or 0, "ILS", lang), item=name or "")


def notify_guest(db, claim, key):
    """`<key>_subj` / `<key>_body` to the guest who made `claim`, if they left an email — in the
    language they reserved in (both languages for claims from before that was recorded).
    Returns True when a message was queued."""
    if not claim["guest_email"]:
        return False
    reg = db.execute("SELECT * FROM registries WHERE id=?", (claim["registry_id"],)).fetchone()
    item = (db.execute("SELECT name, name_he FROM registry_items WHERE id=?", (claim["item_id"],)).fetchone()
            if claim["item_id"] else None)
    langs = [claim["lang"]] if claim["lang"] in ("en", "he") else ["en", "he"]
    parts = []
    for lang in langs:
        he = lang == "he"
        kw = dict(couple=(reg["couple_names_he"] if he and reg["couple_names_he"] else reg["couple_names"]) or _t("the_couple", lang),
                  title=reg["title_he"] if he and reg["title_he"] else reg["title"],
                  item=((item["name_he"] if he and item["name_he"] else item["name"]) if item else _t("gift_cash", lang)),
                  link=ext_url("registry", slug=reg["slug"]) + ("?lang=he" if he else ""))
        if claim["kind"] == "chip" and item:
            kw["item"] = chip_label(claim["amount_minor"], item["name"], item["name_he"], lang)
        parts.append((_t(key + "_subj", lang).format(**kw), _t(key + "_body", lang).format(**kw)))
    send_mail(claim["guest_email"], parts[0][0], "\n\n— — —\n\n".join(b for _, b in parts))
    return True


def send_guest_link(db, claim_id, token, to, lang):
    """The guest's own confirmation: which gift and for whom, the next step that fits it (store, cash
    amount, or buy-anywhere), how long it's held, and the private link — their only way back to it."""
    c = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    reg = db.execute("SELECT * FROM registries WHERE id=?", (c["registry_id"],)).fetchone()
    item = (db.execute("SELECT * FROM registry_items WHERE id=?", (c["item_id"],)).fetchone()
            if c["item_id"] else None)
    he = lang == "he"
    couple = (reg["couple_names_he"] if he and reg["couple_names_he"] else reg["couple_names"]) or _t("the_couple", lang)
    if item is not None and c["kind"] == "chip":
        item_label = chip_label(c["amount_minor"], item["name"], item["name_he"], lang)
    elif item is not None:
        name = item["name_he"] if he and item["name_he"] else item["name"]
        item_label = f"{name} ×{c['qty']}" if (c["qty"] or 1) > 1 else name
    else:
        item_label = _t("gift_cash", lang)
    kw = dict(couple=couple, item=item_label, link=ext_url("guest_manage", token=token))
    if c["status"] != "reserved":  # a general cash gift is recorded as already reported
        body = _t("mail_guest_cash_body", lang).format(**kw)
    else:
        if c["kind"] in ("cash", "chip"):
            amount = (ob_money.fmt_minor(c["amount_minor"], c["currency"] or "ILS", lang)
                      if c["amount_minor"] is not None else _t("gift_cash", lang))
            nxt = _t("mail_guest_next_cash", lang).format(amount=amount)
        elif item is not None and item["url"]:
            address = ((reg["delivery_note_he"] if he and reg["delivery_note_he"] else reg["delivery_note"]) or "").strip()
            store = (item["store"] or "").strip()
            # " from KSP" / " ב-KSP" ("ב" alone before a Hebrew store name); nothing when the store isn't named
            store_part = ("" if not store else f" ב{'' if _HE_LETTER.match(store) else '-'}{store}" if he
                          else f" from {store}")
            nxt = _t("mail_guest_next_store", lang).format(
                store_part=store_part, store_link=ext_url("go_item", item_id=item["id"]),
                address=(_t("mail_guest_address", lang).format(address=address) if address
                         else _t("mail_guest_no_address", lang)))
        else:
            nxt = _t("mail_guest_next_plain", lang)
        held = (_t("mail_guest_held", lang).format(date=format_date(c["expires_at"][:10], lang))
                if c["expires_at"] else "")
        body = _t("mail_guest_manage_body", lang).format(next=nxt, held=held, **kw)
    send_mail(to, _t("mail_guest_manage_subj", lang).format(**kw), body)


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = ob_db.connect(DB_PATH)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Run migrations once at import time, then seed-sync the catalog/bundles
    (catalog seeding stays here — it's not part of the Phase 1 module split).
    See ob_db.seed_sync() for the adoption/insert rules (SPEC_V3 "Catalog")."""
    db = ob_db.connect(DB_PATH)
    try:
        ob_db.migrate(db)
        seed_path = BASE / "seed_catalog.json"
        if seed_path.exists():
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            with ob_db.write_txn(db):
                ob_db.seed_sync(db, seed.get("items", []))
                ob_db.bundle_sync(db, seed.get("bundles", []))
    finally:
        db.close()


# ---------------------------------------------------------------- helpers
def _fresh_session(*keep):
    """session.clear() for login/signup/logout (no fixation, no leftovers) — but the reader's
    language survives, or a Hebrew couple lands on an English dashboard right after logging in."""
    saved = {k: session[k] for k in ("lang",) + keep if k in session}
    session.clear()
    session.update(saved)


def current_lang():
    lang = request.args.get("lang")
    if lang in ("en", "he"):
        session["lang"] = lang
        return lang
    if "lang" in session:
        return session["lang"]
    # first visit, no choice made yet: a phone set to Hebrew (an Israeli relative opening the
    # couple's link) gets Hebrew. Not stored, so the first tap on the language button decides.
    # Crawlers send no Accept-Language and keep getting English at the x-default URL.
    best = request.accept_languages.best_match(["en", "he", "iw"])
    return "he" if best in ("he", "iw") else "en"


def slugify(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "registry"


def usd(nis):
    try:
        return int(round(float(nis) / ILS_PER_USD))
    except (TypeError, ValueError):
        return 0


def valid_http_url(u):
    return ob_security.validate_url(u)


def wa_number(raw):
    """Digits for a wa.me link. wa.me needs the international form: a number
    typed locally with a leading 0 (e.g. 050-123-4567) is taken as Israeli."""
    digits = re.sub(r"\D", "", raw or "")
    if (raw or "").strip().startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "972" + digits[1:]
    return digits


app.jinja_env.filters["wa_number"] = wa_number


def days_until(iso):
    """Whole days from today to a YYYY-MM-DD date (negative = past); None if it isn't one."""
    try:
        return (datetime.strptime((iso or "")[:10], "%Y-%m-%d").date() - date.today()).days
    except ValueError:
        return None


app.jinja_env.filters["days_until"] = days_until


def ext_url(endpoint, **kw):
    """External URL for emails/sitemap/robots/share links — uses OB_BASE_URL
    when set (so it's correct behind a proxy without OB_TRUST_PROXY), else
    falls back to Flask's own _external=True."""
    if BASE_URL:
        return BASE_URL + url_for(endpoint, **kw)
    return url_for(endpoint, _external=True, **kw)


def registry_share_url(slug):
    """The registry link a couple (or a guest) shares — in the language they're using, so a
    Hebrew-speaking couple's WhatsApp preview, QR code and landing page are Hebrew too
    (guests can still switch). Jinja global."""
    return ext_url("registry", slug=slug, **({"lang": "he"} if current_lang() == "he" else {}))


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    row = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not row or row["session_ver"] != session.get("sv"):
        return None
    return row


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


ADMIN_SESSION_HOURS = 12  # admin can download the whole DB — don't keep that open for days


def current_admin():
    name = session.get("admin")
    if not name:
        return None
    try:
        started = datetime.fromisoformat(session.get("admin_at") or "")
    except ValueError:
        return None  # sessions from before admin_at existed have to log in again
    if datetime.now(timezone.utc).replace(tzinfo=None) - started > timedelta(hours=ADMIN_SESSION_HOURS):
        return None
    row = get_db().execute("SELECT * FROM admins WHERE username=?", (name,)).fetchone()
    if not row or row["session_ver"] != session.get("admin_sv"):
        return None
    return row


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not current_admin():
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrapper


def user_registry():
    """The registry this account manages: its own, or the one it was invited to help with."""
    uid = session.get("uid")
    if not uid or not current_user():
        return None
    db = get_db()
    return (db.execute("SELECT * FROM registries WHERE user_id=? ORDER BY id LIMIT 1", (uid,)).fetchone()
            or db.execute("SELECT r.* FROM registries r JOIN registry_members m ON m.registry_id = r.id"
                          " WHERE m.user_id=?", (uid,)).fetchone())


def is_reg_owner(reg):
    """The account that made the registry (or was handed it). Only the owner changes the payment
    links, decides who else can help, and deletes the registry along with their account."""
    return bool(reg) and session.get("uid") == reg["user_id"]


def registry_owner_name(reg):
    row = get_db().execute("SELECT name FROM users WHERE id=?", (reg["user_id"],)).fetchone() if reg else None
    return row["name"] if row else ""


def can_manage(reg):
    """Owner or helper — used where a page is looked up by slug rather than through user_registry()."""
    uid = session.get("uid")
    if not reg or not uid:
        return False
    return uid == reg["user_id"] or get_db().execute(
        "SELECT 1 FROM registry_members WHERE registry_id=? AND user_id=?", (reg["id"], uid)).fetchone() is not None


def pick(row, field, lang):
    """Bilingual column: prefer the *_he variant in Hebrew, fall back to EN."""
    if lang == "he":
        he = row[field + "_he"] if (field + "_he") in row.keys() else ""
        if he:
            return he
    return row[field]


def is_spam():
    """Honeypot: the hidden 'website' field is invisible to humans; bots fill it."""
    return bool(request.form.get("website"))


def _remember_claim_token(form_key, token):
    """After a successful reservation/cash-gift, remember form_key -> raw
    token in the session (capped at 10) so a retried/double-click POST with
    the same form_key can be sent straight to /g/<token> instead of a dead
    "already recorded" flash — the raw token only ever lives in the
    requesting guest's own session, never in the DB (see CHANGELOG_AI.md
    "Decisions": only the sha256 hash is stored server-side)."""
    if not form_key:
        return
    tokens = session.get("claim_tokens") or {}
    tokens[form_key] = token
    if len(tokens) > 10:
        for k in list(tokens)[:len(tokens) - 10]:
            del tokens[k]
    session["claim_tokens"] = tokens


def _prefs(reg):
    """Parse registries.preferences_json -> dict, never raising."""
    try:
        return json.loads(reg["preferences_json"] or "{}")
    except (ValueError, TypeError):
        return {}


def reg_pay_links(reg):
    """[(t-key, url), ...] for whichever cash-gift links the couple added and
    that still classify to a known provider."""
    links = []
    for col, key in (("paypal_url", "pay_paypal"), ("stripe_url", "pay_stripe"),
                     ("bit_url", "pay_bit")):
        u = reg[col] if col in reg.keys() else ""
        if u:
            try:
                _provider, canon = ob_security.classify_pay_url(u)
                links.append((key, canon))
            except ValueError:
                continue
    return links


def item_routes(item, pay_links):
    """Card-rule plumbing (SPEC_V3 "Catalog" -> "Card rules"): what can a
    guest actually do with this gift?
      store — a valid store link exists -> "Reserve and buy from the store"
      cash  — the couple has at least one working pay link -> "Send money
              for this gift" (allowed even for a kind='idea' row: an idea
              still needs money, it just has no store link to click through)
    Neither -> shown as an idea with no button; the dashboard flags it."""
    has_url = bool(item["url"]) if "url" in item.keys() else False
    return dict(store=has_url, cash=bool(pay_links))


def _active_affiliate_rules():
    """Active affiliate rules, read once per request (go_url runs per card)."""
    if "aff_rules" not in g:
        g.aff_rules = get_db().execute("SELECT * FROM affiliate_rules WHERE active=1").fetchall()
    return g.aff_rules


def _direct_destination(item):
    """The tagged store URL when the active rule matching this item's URL is a 'param' rule marked
    `direct` (Amazon: its rules disfavour a redirect that hides the referring page); else None."""
    url = item["url"] if "url" in item.keys() else ""
    if not url:
        return None
    rules = _active_affiliate_rules()
    if not rules:
        return None
    final, rule_id = ob_affiliate.tag_url(url, rules)
    if rule_id is None or not valid_http_url(final):
        return None
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if rule is None or rule["kind"] != "param" or not rule["direct"]:
        return None
    return final


def _go_path(item):
    if "category" in item.keys() and "registry_id" not in item.keys() and "sort" in item.keys():
        return url_for("go_catalog", catalog_id=item["id"])
    return url_for("go_item", item_id=item["id"])


def go_url(item):
    """/go/ handoff-click URL for a catalog or registry item. Jinja global —
    see PROJECT_KNOWLEDGE.md "Click tracking" for the return-key contract.
    A 'direct' affiliate rule links the tagged store URL itself (see go_attrs for the click ping)."""
    if "clicks" not in item.keys():
        return item["url"] if "url" in item.keys() else ""
    direct = _direct_destination(item)
    return direct if direct else _go_path(item)


def go_attrs(item):
    """Extra attributes for a link built with go_url(): for a direct link, `data-go-ping` names the
    POST endpoint app.js beacons so the click is still counted. Empty otherwise. Jinja global."""
    if "clicks" not in item.keys() or not _direct_destination(item):
        return ""
    return Markup(' data-go-ping="%s"' % escape(_go_path(item) + "/ping"))


def fmt_date(iso, lang=None):
    """Human-readable date for display ("15 December 2026" / "15 בדצמבר 2026")
    from a stored ISO date or datetime string (i18n.format_date). The stored
    value is never changed; anything unparsable is returned as-is."""
    return format_date(iso, lang or current_lang())


def estimate_label(price_nis, lang=None):
    """"≈ $49 (approx., rate as of 2026-09-01)" in the session/registry display
    currency, or '' when that currency is ILS (no estimate needed) or isn't
    configured in OB_RATES. Jinja global for public templates."""
    lang = lang or current_lang()
    cur = (session.get("cur") or getattr(g, "display_currency", None)
           or ("USD" if "USD" in ob_money.CURRENCIES else "ILS"))
    if cur == "ILS" or not price_nis:
        return ""
    minor = int(price_nis) * 100
    est_minor = ob_money.estimate(minor, cur)
    if est_minor is None:
        return ""
    est_minor = int(round(est_minor / 100.0)) * 100  # approximate → whole units
    body = ob_money.fmt_minor(est_minor, cur, lang)
    return _t("estimate_label", lang).format(amount=body)


def estimate_note(lang=None):
    """One-per-page footnote explaining the ≈ estimates (currency, rate date).
    Empty when the display currency is ILS, so pages show nothing extra."""
    lang = lang or current_lang()
    cur = (session.get("cur") or getattr(g, "display_currency", None)
           or ("USD" if "USD" in ob_money.CURRENCIES else "ILS"))
    if cur == "ILS" or cur not in ob_money.CURRENCIES:
        return ""
    date = "⁨" + fmt_date(ob_money.RATES_DATE, lang) + "⁩" if ob_money.RATES_DATE else ""
    key = "estimate_note_dated" if ob_money.RATES_DATE else "estimate_note"
    return _t(key, lang).format(cur=cur, date=date)


def _insert_registry_item_from_catalog(db, reg_id, c):
    """Copy a catalog_items row onto a registry (used by items_add, items_starter,
    and pending_add-after-signup). Carries kind/price_status/price_checked_at
    forward per SPEC_V3 "Card rules"."""
    def _c(field, default=""):
        return c[field] if field in c.keys() and c[field] is not None else default
    db.execute(
        "INSERT INTO registry_items (registry_id, catalog_id, name, name_he, brand,"
        " category, price_nis, store, url, image, kind, price_status, price_checked_at,"
        " model, model_he, availability, notes, notes_he)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (reg_id, c["id"], c["name"], c["name_he"], c["brand"], c["category"],
         c["price_nis"], c["store"], c["url"], c["image"], _c("kind", "product"),
         _c("price_status", "estimate"), _c("price_checked_at"),
         _c("model"), _c("model_he"), _c("availability", "unknown"), _c("notes"), _c("notes_he")))


def _apply_pending_add(db, reg_id, catalog_ids):
    """Apply session['pending_add'] catalog ids (queued while the guest was
    logged out) onto a freshly-created registry. Skips inactive/missing ids
    and ones already on the registry. Returns how many were added."""
    added = 0
    for cid in catalog_ids:
        c = db.execute("SELECT * FROM catalog_items WHERE id=? AND active=1", (cid,)).fetchone()
        if not c:
            continue
        exists = db.execute("SELECT 1 FROM registry_items WHERE registry_id=? AND catalog_id=?",
                            (reg_id, c["id"])).fetchone()
        if not exists:
            _insert_registry_item_from_catalog(db, reg_id, c)
            added += 1
    return added


def _blank_breakdown():
    return dict(reserved=0, reported=0, received=0, committed=0, chip_minor=0, chip_reserved_minor=0,
                chip_reported_minor=0, chip_received_minor=0, chip_count=0)


def _chip_state(price_nis, b):
    """(fully_funded, state) for a chip-in item from its chip sums `b` (see item_claim_breakdown) and
    price. state = 'received' when every active chip was confirmed, 'reported' when none is merely
    reserved, else 'reserved'. (False, None) while the goal (price in agorot) isn't met."""
    goal = int(price_nis or 0) * 100
    funded = b.get("chip_minor", 0)
    if not b.get("chip_count") or goal <= 0 or funded < goal:
        return False, None
    if b.get("chip_received_minor", 0) >= funded:
        return True, "received"
    if b.get("chip_reserved_minor", 0) == 0:
        return True, "reported"
    return True, "reserved"


def item_claim_breakdown(registry_id):
    """Per-item committed quantity split by lifecycle status:
    {item_id: {'reserved': n, 'reported': n, 'received': n, 'committed': n, chip_*...}}.
    Expired reservations (status still 'reserved' but past expires_at) are not
    counted — they free the quantity again even before `manage.py
    expire-claims` runs. The public registry page uses this to label a card
    Reserved / Reported / Received instead of a blanket "Gifted".
    Chip-in contributions (kind='chip', qty=0) add to the chip_* sums: chip_minor (active total),
    chip_reserved_minor / chip_reported_minor / chip_received_minor, chip_count (active rows).
    A FULLY funded chip-in item also counts as one committed unit (in the bucket its chips
    imply), so every caller that counts taken gifts from `committed` treats it as taken, and a
    partly funded one as still open."""
    now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    rows = db.execute(
        "SELECT item_id, status, COALESCE(SUM(qty),0) AS n,"
        " COALESCE(SUM(CASE WHEN kind='chip' THEN amount_minor END),0) AS chip_minor,"
        " COALESCE(SUM(kind='chip'),0) AS chip_n FROM claims"
        " WHERE registry_id=? AND item_id IS NOT NULL"
        " AND status IN ('reserved','reported','received')"
        " AND (expires_at IS NULL OR expires_at > ? OR status != 'reserved')"
        " GROUP BY item_id, status", (registry_id, now)).fetchall()
    out = {}
    for r in rows:
        d = out.setdefault(r["item_id"], _blank_breakdown())
        d[r["status"]] += r["n"]
        d["committed"] += r["n"]
        d["chip_minor"] += r["chip_minor"]
        d["chip_" + r["status"] + "_minor"] += r["chip_minor"]
        d["chip_count"] += r["chip_n"]
    chip_ids = [i for i, d in out.items() if d["chip_count"]]
    if chip_ids:
        prices = {r["id"]: r["price_nis"] for r in db.execute(
            "SELECT id, price_nis FROM registry_items WHERE registry_id=? AND id IN (%s)"
            % ",".join("?" * len(chip_ids)), [registry_id] + chip_ids)}
        for i in chip_ids:
            d = out[i]
            if d["committed"]:
                continue  # a whole-item claim holds it (chip-in and whole claims never coexist)
            full, state = _chip_state(prices.get(i), d)
            if full:
                d[state] += 1
                d["committed"] += 1
                d["chip_full"] = True
    return out


def item_claim_counts(registry_id):
    """Committed quantity per item (reserved + reported + received, minus
    expired reservations). Thin wrapper over item_claim_breakdown()."""
    return {k: v["committed"] for k, v in item_claim_breakdown(registry_id).items()}


def gift_status(item, breakdown):
    """Shared presentation rule for a registry item's gift state (used by the
    public registry, the sample, the items page and tests):
      state  — 'open' (nothing committed), 'partial' (some units still
               available), or, when nothing is left: 'received' (every
               committed unit confirmed by the couple), 'reported' (a guest
               says it's bought/sent, not yet confirmed) or 'reserved'.
      left   — units a guest can still take (never negative)
      chip   — for a chip-in item: dict(funded_minor, goal_minor, remaining_minor, pct, count), else None.
               Funded < goal -> state 'partial', left 1; funded >= goal -> left 0 and state by the chips.
    Nothing here implies payment verification; 'reported' is the guest's own
    word and 'received' is the couple's confirmation."""
    qty = item["qty_wanted"] if "qty_wanted" in item.keys() else 1
    b = dict(_blank_breakdown(), **((breakdown or {}).get(item["id"]) or {}))
    keys = item.keys()
    chip = None
    if (b["chip_count"] or ("chip_in" in keys and item["chip_in"])) and (not b["committed"] or b.get("chip_full")):
        # chips are the only claims on this item: take the unit buckets from them (the breakdown may
        # already carry the "fully funded" unit, so reset rather than add it twice)
        b.update(reserved=0, reported=0, received=0, committed=0)
        goal = int(item["price_nis"] or 0) * 100 if "price_nis" in keys else 0
        funded = b["chip_minor"]
        full, state = _chip_state(item["price_nis"] if "price_nis" in keys else 0, b)
        if full:
            b[state] = 1
            b["committed"] = 1
        chip = dict(funded_minor=funded, goal_minor=goal, remaining_minor=max(goal - funded, 0),
                    pct=min(100, funded * 100 // goal) if goal else 0, count=b["chip_count"])
    left = max(qty - b["committed"], 0)
    if left > 0:
        state = "partial" if (b["committed"] or b["chip_count"]) else "open"
    elif b["received"] >= qty:
        state = "received"
    elif b["reported"]:
        state = "reported"
    else:
        state = "reserved"
    return dict(state=state, left=left, qty=qty, chip=chip, **b)


# keyword -> item-specific line illustration (<symbol id="ill-*"> in base.html).
# Only used when an item has no photo; falls back to the category drawing.
_ILLUSTRATION_RULES = (
    # cash funds ("Sefarim fund", "קרן ספרים"): the money-box drawing, ahead of every keyword rule
    (("fund ", "קרן "), "boxes"),
    # checked before the broad rules below: "cookie sheets" must not hit "sheet" (bedding)
    (("cookie sheet", "baking pan", "baking dish", "kugel pan", "loaf", "תבנית"), "bakeware"),
    # 2026-10-25 additions, checked first: the more specific names before the broad rules below
    (("cutting board", "קרש חיתוך"), "board"),
    (("cake stand", "מעמד עוגה"), "cakestand"),
    (("measuring", "מדידה"), "measure"),
    (("spice", "salt", "תבלינים", "מלחייה"), "spices"),
    (("rolling pin", "pastry", "מערוך"), "rolling"),
    (("garlic", "peeler", "מכבש שום", "קולפן"), "cutlery"),
    (("hamper", "laundry basket", "סל כביסה"), "hamper"),
    (("drying rack", "dish rack", "מתקן ייבוש"), "dishrack"),
    (("havdalah", "הבדלה"), "havdalah"),
    (("netilas", "washing cup", "mayim achronim", "נטלה", "נטילת ידיים", "מים אחרונים"), "netilas"),
    (("seder", "קערת ליל הסדר", "קערת סדר"), "seder"),
    (("ironing", "steam iron", "מגהץ"), "iron"),
    (("hanger", "קולב"), "hanger"),
    (("storage box", "container", "organizer", "קופסאות אחסון", "מארגנ", "tzedakah", "tallit bag", "tallis bag", "קופסת צדקה", "תיק טלית"), "boxes"),
    (("step stool", "stool", "שרפרף"), "stool"),
    (("tool kit", "toolbox", "first aid", "ארגז כלים", "עזרה ראשונה"), "toolbox"),
    (("sandwich", "waffle", "panini", "טוסטר לחיצה", "וופל"), "press"),
    (("carbonator", "soda", "סודה"), "soda"),
    (("guest bed", "folding bed", "מיטה מתקפלת", "מיטות מתקפלות"), "bedding"),
    (("bowl", "colander", "strainer", "honey dish", "קערה", "קערות", "מסננת", "קערית דבש"), "bowls"),
    (("bath mat", "shower", "מקלחת", "אמבטיה"), "towel"),
    (("hot plate", "platta", "פלטה"), "platta"),
    (("urn", "meicham", "pump pot", "מיחם"), "urn"),
    (("kettle", "קומקום"), "kettle"),
    (("stand mixer", "hand mixer", "מיקסר"), "mixer"),
    (("slow cooker", "crock", "cholent", "בישול איטי"), "slowcooker"),
    (("towel", "bathrobe", "מגבת", "מגבות", "חלוק"), "towel"),
    (("candlestick", "פמוט"), "candlesticks"),
    (("kiddush", "קידוש"), "kiddush"),
    (("challah", "matzah", "חלה", "מצות"), "challah"),
    (("menorah", "chanukah", "חנוכייה"), "menorah"),
    (("mezuzah", "מזוזה"), "mezuzah"),
    (("dinnerware", "plates", "porcelain", "צלחות", "כלי אוכל"), "dinnerware"),
    (("cutlery", "knife", "knives", "סכו", "סכין"), "cutlery"),
    (("glassware", "wine", "pitcher", "carafe", "כוסות", "יין"), "glassware"),
    (("pots", "frying pan", "סירים", "מחבת"), "pots"),
    (("table", "chairs", "שולחן", "כיסא"), "table"),
    (("sheet", "duvet", "blanket", "pillow", "bedspread", "mattress", "linen", "מצעים", "שמיכ", "כרית"), "bedding"),
    (("fridge", "freezer", "מקרר", "מקפיא"), "fridge"),
    (("washing", "washer", "dryer", "dishwasher", "מכונת כביסה", "מדיח", "מייבש"), "washer"),
    (("oven", "microwave", "toaster", "air fryer", "תנור", "מיקרוגל", "טוסטר"), "oven"),
    (("blender", "food processor", "בלנדר", "מעבד מזון"), "blender"),
    (("coffee", "frother", "קפה"), "coffee"),
    (("vacuum", "sponja", "broom", "שואב", "ספונג"), "cleaning"),
    (("bookcase", "sefarim", "shas", "chumash", "siddur", "machzor", "bentcher", "ספרי", "ספרייה"), "books"),
    (("sukkah", "esrog", "סוכה", "אתרוג"), "sukkah"),
    (("lamp", "מנורה"), "lamp"),
    (("fan", "heater", "dehumidifier", "מאוורר", "חימום", "לחות"), "fan"),
    (("couch", "sofa", "rug", "curtain", "mirror", "ספה", "שטיח", "וילון", "מראה"), "sofa"),
)


def illustration_for(item):
    """Symbol id (without the 'ill-' prefix) for an item without a photo:
    item-specific when a keyword matches, otherwise the category drawing."""
    name = ((item["name"] if "name" in item.keys() else "") or "").lower()
    key = ((item["seed_key"] if "seed_key" in item.keys() else "") or "").lower().replace("-", " ")
    hay = name + " " + key
    for words, symbol in _ILLUSTRATION_RULES:
        if any(w in hay for w in words):
            return symbol
    cat = item["category"] if "category" in item.keys() else "home"
    return cat if cat in CATEGORIES else "home"


def csv_safe(cell):
    """CSV-injection guard: prefix a leading apostrophe if the cell could be
    interpreted as a formula by Excel/Sheets."""
    text = "" if cell is None else str(cell)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


_BOT_UA_RE = re.compile(
    r"bot|crawl|spider|slurp|preview|fetch|scan|monitor|curl|wget|python-|httpx|go-http|java/|"
    r"headless|lighthouse|facebookexternalhit|whatsapp|telegram|discord|skype", re.I)


def is_bot():
    """Crawlers, link-preview fetchers and scripts: they still get every page and
    redirect, but aren't counted — the funnel and click numbers are what the owner
    quotes to advertisers, so they must be people."""
    ua = request.headers.get("User-Agent") or ""
    return not ua or bool(_BOT_UA_RE.search(ua))


def track(name, owner_uid=None):
    """No-PII daily funnel counters. Skipped for admins, for bots (is_bot), and for
    the registry owner viewing their own registry (so self-visits don't inflate funnels)."""
    if session.get("admin") or is_bot():
        return
    if owner_uid is not None and session.get("uid") == owner_uid:
        return
    day = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    db = get_db()
    with ob_db.write_txn(db):
        db.execute(
            "INSERT INTO funnel_events (day, name, n) VALUES (?, ?, 1)"
            " ON CONFLICT(day, name) DO UPDATE SET n = n + 1", (day, name))


def _maybe_track_first_gifts(db, registry_id):
    """Fire the `first_gifts` funnel event the moment a registry reaches 5
    usable items — SPEC_V3 "Privacy / SEO" funnel counters list. Cheap COUNT
    each call; fine at this scale (idempotent day+name PK on funnel_events,
    but we still only want to fire once per registry: gate on ==5 exactly)."""
    n = db.execute("SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0",
                   (registry_id,)).fetchone()[0]
    if n == 5:
        track("first_gifts")


def _log_claim_event(db, claim_id, event, actor, note=""):
    db.execute(
        "INSERT INTO claim_events (claim_id, event, actor, note) VALUES (?,?,?,?)",
        (claim_id, event, actor, note))


def _canonical_and_alts():
    """canonical_url + alt_urls (en/he) for the current GET request. Filter/
    search params are dropped on purpose (SPEC_V3 "Privacy / SEO": don't index
    search-result/filter combinations); only the `lang=he` variant survives."""
    if request.method != "GET":
        return None, {}
    canonical = ext_url_path(request.path, {}, "he" if current_lang() == "he" else None)
    alts = {"en": ext_url_path(request.path, {}, None),
            "he": ext_url_path(request.path, {}, "he")}
    return canonical, alts


def ext_url_path(path, args, lang_code):
    q = dict(args)
    if lang_code:
        q["lang"] = lang_code
    qs = urlencode(q)
    full = (BASE_URL or request.host_url.rstrip("/")) + path
    return full + (("?" + qs) if qs else "")


# Hebrew one-letter prefixes (ב/מ/ל/ה/ו/כ/ש, up to two) take a maqaf before a Latin word or a
# number: "ב-KSP", "מ-Machsanei Chashmal" — but "במחסני חשמל" when the store name is Hebrew.
_HE_PREFIX_BEFORE_LATIN = re.compile(r"(?<![\w-])([ובלמהכש]{1,2})(?=[A-Za-z0-9])")


def tf(key, lang, **kw):
    """Translated string with values filled in (the `tf` Jinja global)."""
    s = (t_count(key, kw["n"], lang) if isinstance(kw.get("n"), int) else _t(key, lang)).format(**kw)
    return _HE_PREFIX_BEFORE_LATIN.sub(r"\1-", s) if lang == "he" else s


def amazon_associate_active():
    """True when an active affiliate rule targets an Amazon host (so the
    Associates disclosure sentence must be shown). Cached per request."""
    if not hasattr(g, "_amazon_assoc"):
        g._amazon_assoc = bool(get_db().execute(
            "SELECT 1 FROM affiliate_rules WHERE active=1 AND host LIKE '%amazon%' LIMIT 1").fetchone())
    return g._amazon_assoc


@app.context_processor
def inject_globals():
    lang = current_lang()
    canonical_url, alt_urls = _canonical_and_alts()
    ep = request.endpoint or ""
    filtered = any(k != "lang" for k in request.args)  # ?q=/?cat= result pages
    default_noindex = (ep.startswith("admin") or ep in NOINDEX_ENDPOINTS
                       or request.path.startswith("/g/") or filtered)
    return dict(
        brand=BRAND,
        lang=lang,
        rtl=(lang == "he"),
        t=lambda key: _t(key, lang),
        tf=lambda key, **kw: tf(key, lang, **kw),
        registry_share_url=registry_share_url,
        pick=lambda row, field: pick(row, field, lang),
        cat_label=lambda slug: cat_label(slug, lang),
        categories=CATEGORIES,
        event_types=EVENT_TYPES,
        usd=usd,
        fmt_money=lambda minor, cur: ob_money.fmt_minor(minor, cur, lang),
        fmt_hdate=lambda iso: ob_hebcal.format_hebrew(iso, lang),
        estimate_label=lambda price_nis: estimate_label(price_nis, lang),
        rates_date=ob_money.RATES_DATE,
        display_currency=(session.get("cur") or getattr(g, "display_currency", None)
                          or ("USD" if "USD" in ob_money.CURRENCIES else "ILS")),
        currencies=ob_money.CURRENCIES,
        csrf_token=_ensure_csrf(),
        user=current_user(),
        my_registry=user_registry(),
        site_ad=get_db().execute(
            "SELECT * FROM ads WHERE active=1 ORDER BY RANDOM() LIMIT 1").fetchone(),
        whatsapp_contact=CONTACT_WHATSAPP,
        now_year=datetime.now().year,
        classify_pay_url=ob_security.classify_pay_url,
        form_key=secrets.token_urlsafe(16),
        gift_routes=lambda item: item_routes(item, reg_pay_links_for_item(item)),
        item_url=item_url,
        gift_category_url=gift_category_url,
        go_url=go_url,
        go_attrs=go_attrs,
        amazon_associate=amazon_associate_active(),
        ext_url=ext_url,
        estimate_note=lambda: estimate_note(lang),
        gpick=lambda obj, field: ob_guides.pick(obj, field, lang),
        guide_cta=guide_cta,
        gift_status=gift_status,
        illustration_for=illustration_for,
        fmt_date=lambda iso: fmt_date(iso, lang),
        canonical_url=canonical_url,
        alt_urls=alt_urls,
        noindex=default_noindex,
    )


def reg_pay_links_for_item(item):
    """gift_routes(item) needs the owning registry's pay links; item rows
    (registry_items / claims joins) don't carry them, so look the registry
    up. Cheap: one indexed lookup, only called from templates that already
    have `pay_links` in scope most of the time — kept for the documented
    Jinja `gift_routes()` contract in PROJECT_KNOWLEDGE.md."""
    if "registry_id" not in item.keys():
        return []
    reg = get_db().execute("SELECT * FROM registries WHERE id=?", (item["registry_id"],)).fetchone()
    return reg_pay_links(reg) if reg else []


# ---------------------------------------------------------------- public pages
def featured_items(db, limit=8):
    """Featured catalog items for promotional placement. Items flagged out of
    stock at the last check sort last so the default strip prefers things a
    guest can actually order today (the badge still shows if one is included)."""
    return db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND featured=1"
        " ORDER BY (availability='unavailable'), (url=''), sort LIMIT ?", (limit,)).fetchall()


# The one canonical sample registry (review 2026-09-15). Built from the live
# catalog so it stays in step with real prices/links, with synthetic gift
# states so visitors can see Reserved / Reported / Received and a multi-qty
# card. Never a real couple, never a real payment destination — the sample
# has no pay links and its buttons are inert (`is_sample`).
_SAMPLE_STATES = [  # (qty_wanted, reserved, reported, received)
    (1, 0, 0, 0), (2, 1, 0, 0), (1, 0, 0, 1), (1, 0, 1, 0), (1, 0, 0, 0), (1, 1, 0, 0),
    (1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 1), (1, 0, 0, 0), (2, 0, 0, 0), (1, 1, 0, 0),
    (1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 1),
]  # ten weeks out most of a real list is still open


def _sample_date():
    """The sample couple's wedding: a Tuesday about ten weeks out (never Yom Tov or Chol
    Hamoed), so the sample shows a date with its Hebrew date and never goes stale."""
    d = date.today() + timedelta(days=70)
    d += timedelta(days=(1 - d.weekday()) % 7)
    while ob_hebcal.day_note(d):
        d += timedelta(days=7)
    return d.isoformat()


def sample_registry(db, limit=16):
    """The featured strip's items first, then two linked, orderable items from each category,
    so the sample reads like a real first-apartment list rather than a handful of cards."""
    lang = current_lang()
    items, breakdown = [], {}
    picks = list(featured_items(db, limit=min(limit, 8)))
    seen, per_cat = {c["id"] for c in picks}, {}
    for c in db.execute("SELECT * FROM catalog_items WHERE active=1 AND url != ''"
                        " AND COALESCE(availability, '') != 'unavailable' ORDER BY category, sort"):
        if len(picks) >= limit:
            break
        if c["id"] not in seen and per_cat.get(c["category"], 0) < 2:
            picks.append(c)
            per_cat[c["category"]] = per_cat.get(c["category"], 0) + 1
    # one big-ticket appliance is open to chip-in, about 60% given by four (synthetic) guests
    big = db.execute("SELECT * FROM catalog_items WHERE active=1 AND category='appliances' AND price_nis >= 1500"
                     " AND url != '' AND COALESCE(availability, '') != 'unavailable' ORDER BY price_nis, id").fetchone()
    if big and big["id"] not in {c["id"] for c in picks}:
        if len(picks) >= limit:
            picks.pop()
        picks.insert(min(len(picks), len(featured_items(db, limit=min(limit, 8)))), big)
    chip_cid = big["id"] if big else None
    for i, c in enumerate(picks):
        qty, res, rep, rec = _SAMPLE_STATES[i % len(_SAMPLE_STATES)]
        row = dict(c)
        row.update(id=-(i + 1), registry_id=0, catalog_id=c["id"], qty_wanted=qty,
                   priority=1 if i == 0 else 0, archived=0, note="", note_he="", clicks=0)
        items.append(row)
        if c["id"] == chip_cid:
            row.update(qty_wanted=1, chip_in=1)
            shares = [round(row["price_nis"] * f) for f in (0.25, 0.15, 0.1, 0.1)]
            b = _blank_breakdown()
            b.update(chip_minor=sum(shares) * 100, chip_count=len(shares),
                     chip_received_minor=(shares[0] + shares[1]) * 100,
                     chip_reported_minor=shares[2] * 100, chip_reserved_minor=shares[3] * 100)
            breakdown[row["id"]] = b
        elif res or rep or rec:
            breakdown[row["id"]] = dict(reserved=res, reported=rep, received=rec,
                                        committed=res + rep + rec)
    reg = dict(id=0, slug="sample", title=_t("sample_reg_title", "en"),
               title_he=_t("sample_reg_title", "he"), couple_names=_t("sample_reg_couple", "en"),
               couple_names_he=_t("sample_reg_couple", "he"), event_type="wedding",
               event_date=_sample_date(), city=_t("sample_reg_city", lang), message=_t("sample_reg_message", "en"),
               message_he=_t("sample_reg_message", "he"), visibility="public",
               display_currency="ILS", delivery_note="", delivery_note_he="",
               paypal_url="", stripe_url="", bit_url="", views=0, user_id=0, closed_at=None)
    return reg, items, breakdown


# The homepage floor plan: each sample gift pinned where it lives in the apartment (x, y in the
# drawing's 620x470 viewBox), with a synthetic state like the /sample fixture's. Owner, 2026-10-26:
# the meicham is in the kitchen, leichter on the dining-room sideboard, challah board at the head
# of the table; 2026-10-27: the slow cooker on the kitchen counter, not by the door. `origin` n -> plan_from_<n> ("from London" ...), None for an open gift.
PLAN_PINS = (
    ("shabbos-urn-meicham", 563, 112, "received", 1),
    ("shabbos-hot-plate-platta", 563, 168, "open", None),
    ("stand-mixer", 376, 57, "reserved", 3),
    ("shabbos-candlesticks", 284, 49, "received", 2),
    ("challah-board-knife", 98, 130, "open", None),
    ("slow-cooker-for-cholent", 526, 57, "reported", 4),  # on the counter beside the hob
    ("towel-set", 68, 338, "received", 5),
    ("sheet-sets-x2", 497, 352, "reserved", 4),
)


def plan_pins(db):
    pins = []
    for key, x, y, state, origin in PLAN_PINS:
        row = db.execute("SELECT * FROM catalog_items WHERE seed_key=? AND active=1", (key,)).fetchone()
        if row:
            pins.append(dict(item=row, x=f"{x / 620 * 100:.1f}%", y=f"{y / 470 * 100:.1f}%",
                             state=state, origin=f"plan_from_{origin}" if origin else None))
    return pins


@app.route("/")
def index():
    db = get_db()
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    # "Room by room": per category, its best four (featured first, in stock, with a store link)
    rooms = []
    for slug in CATEGORIES:
        rows = db.execute(
            "SELECT * FROM catalog_items WHERE active=1 AND category=?"
            " ORDER BY featured DESC, (availability='unavailable'), (url=''), sort LIMIT 4", (slug,)).fetchall()
        n = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND category=?", (slug,)).fetchone()[0]
        if rows:
            rooms.append({"slug": slug, "items": rows, "count": n})
    return render_template("index.html", bundles=bundles, rooms=rooms, plan_pins=plan_pins(db))


@app.route("/sample")
def sample():
    """Read-only sample registry: the public registry template rendered on the
    synthetic fixture. No claims can be made here (no dialogs, no POST routes
    for slug 'sample'); `is_sample` disables every button."""
    db = get_db()
    reg, items, breakdown = sample_registry(db)
    total = sum(i["qty_wanted"] for i in items)
    done = sum(min(breakdown.get(i["id"], {}).get("committed", 0), i["qty_wanted"]) for i in items)
    return render_template("registry.html", reg=reg, items=items, claimed={},
                           breakdown=breakdown, total=total, done=done, bought_item=None,
                           pay_links=[], days_to_go=None, is_owner=False, is_preview=False,
                           is_sample=True, price_bands=CATALOG_PRICE_BANDS,
                           room_fills=room_fills_for(items, {k: v["committed"] for k, v in breakdown.items()}))


@app.route("/lang/<code>")
def set_lang(code):
    back = ob_security.same_origin_referrer() or url_for("index")
    if code in ("en", "he"):
        session["lang"] = code
        # a page reached as ?lang=he (Hebrew share links, hreflang URLs, Hebrew searches) would
        # switch straight back to Hebrew on return — so the button seemed to do nothing
        parts = urlsplit(back)
        query = parse_qsl(parts.query, keep_blank_values=True)
        if any(k == "lang" for k, _ in query):
            back = urlunsplit(("", "", parts.path,
                               urlencode([(k, code if k == "lang" else v) for k, v in query]), ""))
    return redirect(back)


@app.route("/currency", defaults={"code": None})
@app.route("/currency/<code>")
def set_currency(code):
    code = (code or request.args.get("code") or "").upper()
    if code in ob_money.CURRENCIES:
        session["cur"] = code
    return redirect(ob_security.same_origin_referrer() or url_for("index"))


@app.route("/how-it-works")
def how():
    return render_template("how.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html", terms_updated=i18n_mod.TERMS_UPDATED,
                           terms_reviewed=i18n_mod.TERMS_REVIEWED)


# ---------------------------------------------------------------- gift ideas by budget
IDEAS_BANDS = {"under-200": "under200", "200-500": "200_500", "500-1500": "500_1500", "1500-plus": "1500plus"}


def _band_items(db, key):
    """Active catalog items in one CATALOG_PRICE_BANDS band, featured first, then cheapest."""
    lo, hi = CATALOG_PRICE_BANDS[key]
    sql, params = "SELECT * FROM catalog_items WHERE active=1 AND price_nis >= ?", [lo]
    if hi is not None:
        sql += " AND price_nis < ?"
        params.append(hi)
    return db.execute(sql + " ORDER BY featured DESC, price_nis, sort", params).fetchall()


@app.route("/gift-ideas", defaults={"band": None})
@app.route("/gift-ideas/<band>")
def gift_ideas(band):
    """Gift ideas by budget: public, indexable landing pages built from the catalog. The index
    shows the four price bands (who each suits, a few examples); a band page lists its catalog
    items by category, with the catalog's own cards (so a couple can add from here too)."""
    if band is not None and band not in IDEAS_BANDS:
        abort(404)
    db = get_db()
    lang = current_lang()
    key = IDEAS_BANDS.get(band)
    bands = []
    for slug, k in IDEAS_BANDS.items():
        items = _band_items(db, k)
        bands.append(dict(slug=slug, key=k, n=len(items),
                          examples=[pick(i, "name", lang) for i in items[:3]]))
    groups, have = [], set()
    reg = user_registry()
    if key:
        items = _band_items(db, key)
        groups = [(cat, [i for i in items if i["category"] == cat]) for cat in CATEGORIES]
        groups = [(cat, its) for cat, its in groups if its]
        if reg:
            have = {r["catalog_id"] for r in db.execute(
                "SELECT catalog_id FROM registry_items WHERE registry_id=? AND catalog_id IS NOT NULL",
                (reg["id"],))}
    return render_template("gift_ideas.html", band=key, bands=bands, groups=groups,
                           have=have, has_reg=bool(reg), cat_links=GIFT_CATS)


# ---------------------------------------------------------------- category landing pages
# Indexable /gifts/<slug>, one per i18n.CATEGORIES entry (the filtered /catalog?cat= view stays noindex).
GIFT_CATS = {  # URL slug -> internal category slug
    "kitchen": "kitchen",
    "appliances": "appliances",
    "shabbos-table": "dining",
    "bedding-and-bath": "bedding",
    "judaica": "judaica",
    "home-essentials": "home",
}
GIFT_CAT_SLUG = {v: k for k, v in GIFT_CATS.items()}


def gift_category_url(cat):
    """Path of a category's landing page (Jinja global); falls back to the catalog filter."""
    slug = GIFT_CAT_SLUG.get(cat)
    return url_for("gift_category", cat_slug=slug) if slug else url_for("catalog_page", cat=cat)


@app.route("/gifts/<cat_slug>")
def gift_category(cat_slug):
    """All active catalog items of one category, grouped by price band, cheapest first."""
    cat = GIFT_CATS.get(cat_slug)
    if not cat:
        abort(404)
    db = get_db()
    rows = db.execute("SELECT * FROM catalog_items WHERE active=1 AND category=?"
                      " ORDER BY price_nis, sort, id", (cat,)).fetchall()
    groups = []
    for key, (lo, hi) in CATALOG_PRICE_BANDS.items():
        its = [r for r in rows if (r["price_nis"] or 0) >= lo and (hi is None or (r["price_nis"] or 0) < hi)]
        if its:
            groups.append((key, its))
    reg = user_registry()
    have = set()
    if reg:
        have = {r["catalog_id"] for r in db.execute(
            "SELECT catalog_id FROM registry_items WHERE registry_id=? AND catalog_id IS NOT NULL",
            (reg["id"],))}
    return render_template("gift_category.html", cat=cat, cat_slug=cat_slug, groups=groups, items=rows,
                           have=have, has_reg=bool(reg), cat_links=GIFT_CATS,
                           guide_obj=ob_guides.BY_SLUG.get(ITEM_GUIDES.get(cat, "")))


@app.route("/guides")
def guides():
    return render_template("guides.html", guides=ob_guides.GUIDES)


@app.route("/guides/<slug>")
def guide(slug):
    g = ob_guides.BY_SLUG.get(slug)
    if not g:
        abort(404)
    others = [x for x in ob_guides.GUIDES if x["slug"] != slug][:3]
    return render_template("guide.html", guide=g, others=others)


def guide_cta(g):
    """(url, i18n key) for the button at the end of a guide."""
    endpoint, key = ob_guides._CTAS.get(g.get("cta", "start"), ("signup", "cta_start"))
    return url_for(endpoint), key


@app.route("/advertise")
def advertise():
    """Inbound ad / partnership page. Deliberately carries no audience numbers
    (nothing to cite yet) — the admin funnel has the real page-view counts."""
    return render_template("advertise.html")


@app.route("/catalog")
def catalog_page():
    """Public catalog — browse everything without an account."""
    db = get_db()
    cat = request.args.get("cat", "")
    q = (request.args.get("q") or "").strip()
    price = request.args.get("price", "")
    kind = request.args.get("kind", "")
    sort = request.args.get("sort", "")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    sql = "SELECT * FROM catalog_items WHERE active=1"
    params = []
    if cat in CATEGORIES:
        sql += " AND category=?"
        params.append(cat)
    if q:
        clause, qparams = ob_search.search_clause(q)
        sql += clause
        params += qparams
    if price in CATALOG_PRICE_BANDS:
        lo, hi = CATALOG_PRICE_BANDS[price]
        sql += " AND price_nis >= ?"
        params.append(lo)
        if hi is not None:
            sql += " AND price_nis < ?"
            params.append(hi)
    else:
        price = ""
    if kind in ("product", "idea"):
        sql += " AND kind=?"
        params.append(kind)
    else:
        kind = ""
    order = CATALOG_SORTS.get(sort)
    if order is None:
        sort, order = "", CATALOG_SORTS[""]
    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    pages = max(1, (total + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
    page = min(page, pages)
    # a search in the default order puts direct name matches first ("plates" → dinnerware, then hot plates)
    rank, rank_params = ob_search.rank_expr(q) if q and not sort else ("", [])
    items = db.execute(sql + f" ORDER BY {rank + ', ' if rank else ''}{order} LIMIT ? OFFSET ?",
                       params + rank_params + [CATALOG_PAGE_SIZE, (page - 1) * CATALOG_PAGE_SIZE]).fetchall()
    have = set()
    reg = user_registry()
    if reg:
        have = {r["catalog_id"] for r in db.execute(
            "SELECT catalog_id FROM registry_items WHERE registry_id=?"
            " AND catalog_id IS NOT NULL", (reg["id"],))}
    filters = dict(cat=cat or None, q=q or None, price=price or None, kind=kind or None,
                   sort=sort or None)
    # nothing found because of a filter on top of the search: offer the matches without it
    unfiltered = 0
    if q and not total and (cat or price or kind):
        clause, qparams = ob_search.search_clause(q)
        unfiltered = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1" + clause,
                                qparams).fetchone()[0]
    return render_template("catalog.html", items=items, cat=cat, q=q, price=price, kind=kind,
                           unfiltered=unfiltered,
                           sort=sort, page=page, pages=pages, total=total, filters=filters,
                           price_bands=CATALOG_PRICE_BANDS, have=have, has_reg=bool(reg))


# ---------------------------------------------------------------- catalog item pages
# One indexable page per active catalog item: /catalog/<slug>. slug = seed_key, or item-<id>
# for admin-added rows that have none. No other route lives under /catalog/.
ITEM_GUIDES = {  # category -> guides.py slug (skipped quietly if the guide is gone)
    "kitchen": "kosher-kitchen-basics",
    "appliances": "appliances-from-abroad-or-buy-in-israel",
    "dining": "shabbos-kitchen-equipment-buying-guide",
    "bedding": "israeli-bed-mattress-and-linen-sizes",
    "judaica": "first-yom-tov-year-in-a-new-home",
    "home": "first-apartment-checklist",
}
ITEM_DESC_MAX = 155


def catalog_slug(row):
    """URL segment of a catalog row: its seed_key, else item-<id>."""
    seed_key = row["seed_key"] if "seed_key" in row.keys() else None
    return seed_key or "item-%d" % row["id"]


def item_url(row):
    """Path of a catalog item's page, or None when `row` isn't (or can't be traced to) a catalog
    row: registry items and sample rows without a seed_key. Jinja global."""
    try:
        keys = row.keys()
        if "name" not in keys or "category" not in keys:
            return None
        seed_key = row["seed_key"] if "seed_key" in keys else None
        if not seed_key and ("registry_id" in keys or not row["id"] or row["id"] <= 0):
            return None
        return url_for("catalog_item", slug=catalog_slug(row))
    except (AttributeError, KeyError, TypeError):
        return None


def _catalog_by_slug(db, slug):
    """The active catalog row a /catalog/<slug> URL names, else None."""
    row = db.execute("SELECT * FROM catalog_items WHERE seed_key=? AND active=1", (slug,)).fetchone()
    if row:
        return row
    m = re.fullmatch(r"item-(\d{1,9})", slug)
    if m:
        return db.execute("SELECT * FROM catalog_items WHERE id=? AND active=1"
                          " AND (seed_key IS NULL OR seed_key='')", (int(m.group(1)),)).fetchone()
    return None


def _item_description(item, lang):
    """Meta description from name, brand/model, price and store, at most ITEM_DESC_MAX characters."""
    name = pick(item, "name", lang)
    detail = (pick(item, "model", lang) or item["brand"] or "").strip()
    price = ("₪{:,}".format(item["price_nis"])) if item["price_nis"] else ""
    store = (item["store"] or "").strip()
    tail = _t("item_desc_tail", lang)

    def build(detail_txt, with_tail):
        s = name + (" (%s)" % detail_txt if detail_txt else "")
        facts = " ".join(x for x in (price, tf("item_desc_at", lang, store=store) if store else "") if x)
        if facts:
            s += ": " + facts
        s += "."
        return s + (" " + tail if with_tail else "")

    out = build(detail, True)
    if len(out) > ITEM_DESC_MAX:
        out = build(detail, False)
    if len(out) > ITEM_DESC_MAX and detail:
        room = ITEM_DESC_MAX - len(build("", False)) - 3
        out = build(detail[:room].rstrip(" ,;—-") + "…", False) if room >= 12 else build("", False)
    return out[:ITEM_DESC_MAX]


@app.route("/catalog/<slug>")
def catalog_item(slug):
    db = get_db()
    lang = current_lang()
    item = _catalog_by_slug(db, slug)
    if not item:
        abort(404)
    cat = item["category"] if item["category"] in CATEGORIES else "home"
    price = item["price_nis"] or 0
    band_key = _band_of(price) if price else None
    band_slug = next((s for s, k in IDEAS_BANDS.items() if k == band_key), None)
    guide_obj = ob_guides.BY_SLUG.get(ITEM_GUIDES.get(cat, ""))
    more = db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND category=? AND id != ?"
        " ORDER BY ABS(price_nis - ?), sort, id LIMIT 4", (item["category"], item["id"], price)).fetchall()
    reg = user_registry()
    have = set()
    if reg:
        have = {r["catalog_id"] for r in db.execute(
            "SELECT catalog_id FROM registry_items WHERE registry_id=? AND catalog_id IS NOT NULL",
            (reg["id"],))}
    return render_template(
        "catalog_item.html", item=item, slug=catalog_slug(item), cat=cat, band_key=band_key,
        band_slug=band_slug, guide_obj=guide_obj, more=more, have=have, has_reg=bool(reg),
        meta_desc=_item_description(item, lang),
        offer_ok=(item["price_status"] == "verified" and bool(item["url"]) and price > 0))


# Public catalog browsing controls (all server-side, URL-addressable so the
# browser back button and the pending-add-through-signup redirect keep state).
CATALOG_PAGE_SIZE = 24
CATALOG_PRICE_BANDS = {  # key -> (min inclusive, max exclusive) in NIS
    "under200": (0, 200),
    "200_500": (200, 500),
    "500_1500": (500, 1500),
    "1500plus": (1500, None),
}
CATALOG_SORTS = {
    "": "category, sort",
    "price_asc": "price_nis, sort",
    "price_desc": "price_nis DESC, sort",
    "name": "name COLLATE NOCASE",
}


def _affiliate_destination(db, url, owner_uid=None):
    """Tag `url` with the first matching active affiliate rule. When a rule
    applied (and this is a real visitor) count the click on the rule and fire
    `handoff_click_tagged`. A tagged URL that no longer validates falls back
    to the untagged one. The stored URL is never modified."""
    rules = db.execute("SELECT * FROM affiliate_rules WHERE active=1").fetchall()
    if not rules:
        return url
    final, rule_id = ob_affiliate.tag_url(url, rules)
    if rule_id is None or not valid_http_url(final):
        return url
    if not is_bot():
        db.execute("UPDATE affiliate_rules SET clicks = clicks + 1 WHERE id=?", (rule_id,))
    track("handoff_click_tagged", owner_uid=owner_uid)
    return final


@app.route("/go/c/<int:catalog_id>")
def go_catalog(catalog_id):
    """Click-through to a catalog item's store link. The destination is
    always read from the DB, never from the query string (no open redirect),
    and is re-validated even though it was validated on save."""
    db = get_db()
    row = db.execute("SELECT * FROM catalog_items WHERE id=?", (catalog_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    if not is_bot():
        db.execute("UPDATE catalog_items SET clicks = clicks + 1 WHERE id=?", (catalog_id,))
    track("handoff_click")
    return redirect(_affiliate_destination(db, row["url"]), code=302)


@app.route("/go/i/<int:item_id>")
def go_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM registry_items WHERE id=?", (item_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    if not is_bot():
        db.execute("UPDATE registry_items SET clicks = clicks + 1 WHERE id=?", (item_id,))
    reg = db.execute("SELECT user_id FROM registries WHERE id=?", (row["registry_id"],)).fetchone()
    owner_uid = reg["user_id"] if reg else None
    track("handoff_click", owner_uid=owner_uid)
    return redirect(_affiliate_destination(db, row["url"], owner_uid=owner_uid), code=302)


# A "direct" affiliate link goes straight to the store (no /go/ redirect), so app.js beacons one of
# these on click instead. Same counting as the GET routes; the CSRF token rides in the beacon body.
@app.route("/go/c/<int:catalog_id>/ping", methods=["POST"])
def go_catalog_ping(catalog_id):
    if rate_limited("go_ping", limit=60, per=600):
        abort(429)
    db = get_db()
    row = db.execute("SELECT * FROM catalog_items WHERE id=?", (catalog_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    if not is_bot():
        db.execute("UPDATE catalog_items SET clicks = clicks + 1 WHERE id=?", (catalog_id,))
    track("handoff_click")
    _affiliate_destination(db, row["url"])
    return "", 204


@app.route("/go/i/<int:item_id>/ping", methods=["POST"])
def go_item_ping(item_id):
    if rate_limited("go_ping", limit=60, per=600):
        abort(429)
    db = get_db()
    row = db.execute("SELECT * FROM registry_items WHERE id=?", (item_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    if not is_bot():
        db.execute("UPDATE registry_items SET clicks = clicks + 1 WHERE id=?", (item_id,))
    reg = db.execute("SELECT user_id FROM registries WHERE id=?", (row["registry_id"],)).fetchone()
    owner_uid = reg["user_id"] if reg else None
    track("handoff_click", owner_uid=owner_uid)
    _affiliate_destination(db, row["url"], owner_uid=owner_uid)
    return "", 204


_FIND_SKIP_WORDS = {"and", "the", "family", "wedding", "registry", "mr", "mrs", "ms", "את", "של", "חתונה"}
_HE_LETTER = re.compile(r"[א-ת]")
# English spellings of the same Jewish name vary (Cohen / Kohen / Kahn, Levi / Levy, Chaya / Haya,
# Dovid / David, Yossi / Yosi): `name_sound` reduces a Latin word to its consonants after folding the
# usual alternatives, so those meet. Used only when the exact search finds nothing.
_SOUND_FOLDS = (("sch", "sh"), ("tz", "z"), ("ts", "z"), ("ch", "h"), ("kh", "h"), ("ck", "k"),
                ("ph", "f"), ("c", "k"), ("q", "k"), ("w", "v"), ("j", "y"))


def name_sound(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return ""
    for a, b in _SOUND_FOLDS:
        w = w.replace(a, b)
    w = re.sub(r"(?<=[aeiouy])h$", "", w)      # Sarah = Sara, Rivkah = Rivka
    w = re.sub(r"y$", "i", w)                     # Levy = Levi, Gurary = Gurari
    skeleton = w[0] + re.sub(r"[aeiou]", "", w[1:])
    return re.sub(r"(.)\1+", r"\1", skeleton)  # Yossi = Yosi, Mendl = Mendel


def _find_by_sound(words):
    """Public registries whose names contain, for every Latin word typed, a word that sounds the same
    (same `name_sound`, at least two letters). Hebrew words still have to appear as typed."""
    wanted = [(w, name_sound(w)) for w in words]
    if not any(_HE_LETTER.search(w) is None and len(s) >= 2 for w, s in wanted):
        return []
    found = []
    for r in get_db().execute("SELECT * FROM registries WHERE visibility='public' ORDER BY created_at DESC"):
        text = " ".join(filter(None, (r["couple_names"], r["couple_names_he"], r["title"], r["title_he"])))
        sounds = {name_sound(t) for t in re.split(r"[\s,&+/.'-]+", text) if t}
        ok = True
        for w, s in wanted:
            if _HE_LETTER.search(w):
                ok = w in text or (w[0] == "ו" and w[1:] in text)
            else:
                ok = len(s) >= 2 and s in sounds  # whole names only: Moshe must not find Mushka
            if not ok:
                break
        if ok:
            found.append(r)
            if len(found) >= 40:
                break
    return found


@app.route("/find")
def find():
    q = (request.args.get("q") or "").strip()
    results, close = None, False
    if q:
        # every name typed must appear, in any order: "Sarah Dovid" finds "Sarah & Dovid",
        # "Dovid and Sarah" too, and "שרה ודוד" finds "שרה ודוד" or "שרה & דוד"
        words = [w for w in re.split(r"[\s,&+/]+", q) if w.lower() not in _FIND_SKIP_WORDS and len(w) > 1]
        sql, params = "SELECT * FROM registries WHERE visibility='public'", []
        for w in (words or [q])[:6]:
            alts = [w] + ([w[1:]] if len(w) > 2 and w[0] == "ו" and _HE_LETTER.match(w[1]) else [])
            ors = []
            for a in alts:
                for f in ("couple_names", "couple_names_he", "title", "title_he"):
                    ors.append(f"{f} LIKE ? ESCAPE '\\'")
                    params.append("%" + a.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
            sql += " AND (" + " OR ".join(ors) + ")"
        results = get_db().execute(sql + " ORDER BY created_at DESC LIMIT 40", params).fetchall()
        if not results and words:
            results = _find_by_sound(words[:6])
            close = bool(results)
    return render_template("find.html", q=q, results=results, close=close)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        if rate_limited("contact", limit=5, per=600):
            abort(429)
        if is_spam():
            return redirect(url_for("contact"))
        body = (request.form.get("body") or "").strip()
        if body:
            get_db().execute(
                "INSERT INTO messages (name, email, topic, body) VALUES (?,?,?,?)",
                ((request.form.get("name") or "").strip()[:120],
                 (request.form.get("email") or "").strip()[:200],
                 (request.form.get("topic") or "general")[:40], body[:4000]))
            send_mail(
                NOTIFY_EMAIL,
                f"OurBayis contact: {(request.form.get('topic') or 'general')}",
                f"From: {request.form.get('name', '')} <{request.form.get('email', '')}>\n\n"
                f"{body[:4000]}\n\nAdmin: {ext_url('admin_home')}",
                reply_to=(request.form.get("email") or "").strip())
            flash(_t("contact_done", current_lang()), "ok")
            return redirect(url_for("contact"))
    return render_template("contact.html")


# ---------------------------------------------------------------- registry (guest view)
@app.route("/r/<slug>")
def registry(slug):
    db = get_db()
    reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
    if not reg:
        abort(404)
    is_owner = can_manage(reg)  # the owner or someone helping them
    g.registry_owner_uid = session.get("uid") if is_owner else reg["user_id"]  # don't count their own views
    if reg["display_currency"] in ob_money.CURRENCIES and reg["display_currency"] != "ILS":
        g.display_currency = reg["display_currency"]  # couple's suggested guest currency
    if reg["visibility"] == "draft" and not is_owner and not session.get("admin"):
        resp = app.make_response(
            render_template("error.html", code=404, draft_not_published=True))
        resp.status_code = 404
        return resp
    if not is_owner:
        db.execute("UPDATE registries SET views = views + 1 WHERE id=?", (reg["id"],))
    is_preview = is_owner and request.args.get("preview") == "1"
    if is_preview:
        prefs = _prefs(reg)
        if not prefs.get("previewed_at"):
            prefs["previewed_at"] = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
            db.execute("UPDATE registries SET preferences_json=? WHERE id=?",
                      (json.dumps(prefs), reg["id"]))
    days_to_go = after_days = None
    try:
        days_to_go = (date.fromisoformat(reg["event_date"]) - date.today()).days
        if days_to_go < 0:
            after_days = -days_to_go
        if days_to_go <= 0:
            days_to_go = None
    except (ValueError, TypeError):
        pass
    items = db.execute(
        "SELECT * FROM registry_items WHERE registry_id=? AND archived=0"
        " ORDER BY priority DESC, category, id", (reg["id"],)).fetchall()
    breakdown = item_claim_breakdown(reg["id"])
    claimed = {k: v["committed"] for k, v in breakdown.items()}
    total = sum(i["qty_wanted"] for i in items)
    done = sum(min(claimed.get(i["id"], 0), i["qty_wanted"]) for i in items)
    bought_item = None
    if request.args.get("bought"):
        try:
            bought_item = db.execute(
                "SELECT * FROM registry_items WHERE id=? AND registry_id=?",
                (int(request.args["bought"]), reg["id"])).fetchone()
        except ValueError:
            pass
    return render_template("registry.html", reg=reg, items=items, claimed=claimed,
                           breakdown=breakdown, is_sample=False,
                           total=total, done=done, bought_item=bought_item,
                           pay_links=reg_pay_links(reg), days_to_go=days_to_go, after_days=after_days,
                           is_owner=is_owner, is_preview=is_preview,
                           bracha_sent=request.args.get("bracha") == "sent",
                           price_bands=CATALOG_PRICE_BANDS, room_fills=room_fills_for(items, claimed),
                           noindex=(reg["visibility"] != "public"))


@app.route("/r/<slug>/claim/<int:item_id>", methods=["POST"])
def claim_item(slug, item_id):
    if rate_limited("claim", limit=15, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("registry", slug=slug))
    lang = current_lang()
    form_key = (request.form.get("form_key") or "").strip()[:80]
    db = get_db()
    name = (request.form.get("guest_name") or "").strip()[:120]
    if not name:
        flash(_t("claim_name_required", lang), "err")
        return redirect(url_for("registry", slug=slug) + f"#item-{item_id}")

    result = {}
    try:
        with ob_db.write_txn(db):
            reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
            item = db.execute(
                "SELECT * FROM registry_items WHERE id=? AND registry_id=? AND archived=0",
                (item_id, reg["id"] if reg else -1)).fetchone()
            if not reg or not item:
                abort(404)
            if reg["closed_at"]:
                flash(_t("reg_closed_flash", lang), "err")
                raise _Abort()
            br = item_claim_breakdown(reg["id"]).get(item_id) or _blank_breakdown()
            committed = br["committed"]
            left = max(item["qty_wanted"] - committed, 0)
            if left <= 0:
                flash(_t("gifted", lang), "err")
                raise _Abort()
            pay_links = reg_pay_links(reg)
            chip_minor = None
            # the chip dialog also offers "I'll buy the whole gift at the store" while nobody has chipped in
            whole_instead = (request.form.get("chip_preset") == "store"
                             and not (request.form.get("chip_amount") or "").strip())
            if request.form.get("give") == "chip" and not whole_instead:
                chip_minor = _chip_amount_minor(item, br, pay_links, lang)  # flashes + raises _Abort when refused
            elif br["chip_count"]:
                # guests are already chipping in: the only way forward is to chip in too
                flash(_t("chip_only", lang), "err")
                raise _Abort()
            try:
                qty = int(request.form.get("qty", 1))
            except ValueError:
                qty = 1
            qty = 0 if chip_minor else max(1, min(qty, left))
            routes = item_routes(item, pay_links)
            if not routes["store"] and not routes["cash"]:
                # an "idea" with nowhere to buy and no payment link — never reservable
                flash(_t("claim_no_route", lang), "err")
                raise _Abort()
            # server-side card rules: the only valid routes are the ones the item has
            give_cash = (request.form.get("give") == "cash" and routes["cash"]) or not routes["store"]
            price_minor = int(item["price_nis"]) * 100
            if chip_minor:
                give_cash, amount_minor, currency = False, chip_minor, "ILS"
            else:
                amount_minor = price_minor * qty if give_cash else None
                currency = "ILS" if give_cash else None
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
            token = ob_security.new_token()
            token_hash = ob_security.hash_token(token)
            try:
                cur = db.execute(
                    "INSERT INTO claims (registry_id, item_id, guest_name, guest_email, message,"
                    " qty, kind, status, amount_minor, currency, price_snapshot_minor,"
                    " price_snapshot_currency, token_hash, token_created_at, idempotency_key,"
                    " expires_at, lang) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (reg["id"], item_id, name,
                     _guest_email(),
                     (request.form.get("message") or "").strip()[:1000], qty,
                     "chip" if chip_minor else "cash" if give_cash else "item", "reserved", amount_minor, currency,
                     price_minor, "ILS", token_hash, datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),
                     form_key or None, expires_at, lang))
            except sqlite3.IntegrityError:
                # duplicate form_key = a repeated POST (double-click/retry). If
                # this session made the original request, it remembered the raw
                # token (see _remember_claim_token) and can go straight there.
                remembered = (session.get("claim_tokens") or {}).get(form_key) if form_key else None
                if remembered:
                    raise _Abort(redirect(url_for("guest_manage", token=remembered)))
                flash(_t("claim_already", lang), "ok")
                raise _Abort()
            _log_claim_event(db, cur.lastrowid, "reserved", "guest")
            result.update(claim_id=cur.lastrowid, reg=dict(reg), item=dict(item), token=token, qty=qty,
                          give_cash=give_cash, name=name, chip_minor=chip_minor)
    except _Abort as ab:
        if request.form.get("give") == "chip":  # back to the item the guest was chipping in on
            return ab.response or redirect(url_for("registry", slug=slug) + f"#item-{item_id}")
        return ab.response or redirect(url_for("registry", slug=slug))

    _remember_claim_token(form_key, result["token"])
    reg, item = result["reg"], result["item"]
    extra = {}
    if result["chip_minor"]:
        owner = db.execute("SELECT lang FROM users WHERE id=?", (reg["user_id"],)).fetchone()
        extra["amount"] = ob_money.fmt_minor(result["chip_minor"], "ILS",
                                             owner["lang"] if owner and owner["lang"] in ("en", "he") else lang)
    notify_owner(db, reg, "mail_reserved_chip" if result["chip_minor"]
                 else "mail_reserved_cash" if result["give_cash"] else "mail_reserved_item", lang, to_helpers=True,
                 item=item, qty=max(result["qty"], 1), name=result["name"],
                 guest_message=(request.form.get("message") or "").strip()[:1000], **extra)
    if _guest_email():
        send_guest_link(db, result["claim_id"], result["token"], _guest_email(), lang)
    track("reservation", owner_uid=reg["user_id"])
    return redirect(url_for("guest_manage", token=result["token"]))


CHIP_SUGGEST_FROM = 1500  # shekels: the list check suggests chip-in for an open gift priced at least this
CHIP_MIN = 20  # shekels: the smallest chip-in (or whatever is left, when less)


def _chip_amount_minor(item, br, pay_links, lang):
    """Validate a guest's chip-in against the item and what's already given (`br` is the item's
    item_claim_breakdown row, read inside the caller's write transaction so two guests can't
    over-fund). Returns the amount in agorot; otherwise flashes why and raises _Abort."""
    price = int(item["price_nis"] or 0)
    if (not item["chip_in"] or not pay_links or item["qty_wanted"] != 1 or price <= 0
            or (br["committed"] and not br.get("chip_full"))):
        flash(_t("chip_closed", lang), "err")
        raise _Abort()
    remaining = price - br["chip_minor"] // 100
    if remaining <= 0:
        flash(_t("gifted", lang), "err")
        raise _Abort()
    raw = (request.form.get("chip_amount") or "").strip()
    if not raw:
        preset = (request.form.get("chip_preset") or "").strip()
        raw = str(remaining) if preset == "rest" else preset
    if not re.fullmatch(r"[0-9]{1,7}", raw) or int(raw) <= 0:
        flash(_t("chip_bad_amount", lang), "err")
        raise _Abort()
    amount = int(raw)
    if amount > remaining:
        flash(tf("chip_over", lang, amount=ob_money.fmt_minor(remaining * 100, "ILS", lang)), "err")
        raise _Abort()
    if amount < min(CHIP_MIN, remaining):
        flash(tf("chip_under", lang, amount=ob_money.fmt_minor(min(CHIP_MIN, remaining) * 100, "ILS", lang)), "err")
        raise _Abort()
    return amount * 100


def _guest_email():
    """The optional guest email from a reserve/cash form, or "" when it isn't one valid address."""
    email = (request.form.get("guest_email") or "").strip()
    return email if ob_security.valid_email(email) else ""


class _Abort(Exception):
    """Internal control-flow signal to bail out of a write_txn block cleanly
    (rolls back the transaction) while keeping the flash message set above.
    Optionally carries a specific response to return (e.g. straight to the
    guest's own /g/<token> on a remembered duplicate form_key)."""
    def __init__(self, response=None):
        super().__init__()
        self.response = response


@app.route("/r/<slug>/bracha", methods=["POST"])
def bracha_add(slug):
    """A guest's bracha without a gift: name + message, read only by the couple."""
    if rate_limited("bracha", limit=6, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("registry", slug=slug))
    lang = current_lang()
    db = get_db()
    reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
    if not reg or reg["visibility"] == "draft":
        abort(404)
    name = (request.form.get("guest_name") or "").strip()[:120]
    message = (request.form.get("message") or "").strip()[:1000]
    if not name or not message:
        flash(_t("bracha_required", lang), "err")
        return redirect(url_for("registry", slug=slug, _anchor="bracha"))
    form_key = (request.form.get("form_key") or "").strip()[:80] or None
    try:
        db.execute("INSERT INTO brachos (registry_id, guest_name, message, lang, form_key) VALUES (?,?,?,?,?)",
                   (reg["id"], name, message, lang, form_key))
    except sqlite3.IntegrityError:  # the same form sent twice: already saved
        return redirect(url_for("registry", slug=slug, bracha="sent", _anchor="bracha"))
    notify_owner(db, reg, "mail_bracha", lang, to_helpers=True, name=name, message=message)
    track("bracha", owner_uid=reg["user_id"])
    return redirect(url_for("registry", slug=slug, bracha="sent", _anchor="bracha"))


@app.route("/r/<slug>/cash", methods=["POST"])
def cash_gift(slug):
    if rate_limited("cash", limit=15, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("registry", slug=slug))
    lang = current_lang()
    db = get_db()
    reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
    if not reg:
        abort(404)
    if reg["closed_at"]:
        flash(_t("reg_closed_flash", lang), "err")
        return redirect(url_for("registry", slug=slug))
    name = (request.form.get("guest_name") or "").strip()[:120]
    currency = (request.form.get("currency") or "ILS").upper()
    if currency not in ob_money.CURRENCIES:
        currency = "ILS"
    if not name:
        flash(_t("claim_name_required", lang), "err")
        return redirect(url_for("registry", slug=slug))
    try:
        # optional: blank (or 0) stores no amount, so the couple never sees "₪0"
        amount_minor = ob_money.to_minor(request.form.get("amount") or "0", currency) or None
    except ValueError:
        flash(_t("form_error", lang), "err")
        return redirect(url_for("registry", slug=slug))
    form_key = (request.form.get("form_key") or "").strip()[:80]
    token = ob_security.new_token()
    try:
        with ob_db.write_txn(db):
            try:
                cur = db.execute(
                    "INSERT INTO claims (registry_id, item_id, guest_name, guest_email, message,"
                    " qty, kind, status, amount_minor, currency, token_hash, token_created_at,"
                    " idempotency_key, lang) VALUES (?, NULL, ?, ?, ?, 1, 'cash', 'reported', ?, ?, ?, ?, ?, ?)",
                    (reg["id"], name, _guest_email(),
                     (request.form.get("message") or "").strip()[:1000], amount_minor, currency,
                     ob_security.hash_token(token), datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),
                     form_key or None, lang))
            except sqlite3.IntegrityError:
                remembered = (session.get("claim_tokens") or {}).get(form_key) if form_key else None
                if remembered:
                    raise _Abort(redirect(url_for("guest_manage", token=remembered)))
                flash(_t("claim_already", lang), "ok")
                raise _Abort()
            _log_claim_event(db, cur.lastrowid, "reported", "guest")
    except _Abort as ab:
        return ab.response or redirect(url_for("registry", slug=slug))
    _remember_claim_token(form_key, token)
    _owner_lang = db.execute("SELECT lang FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    _ol = _owner_lang["lang"] if _owner_lang and _owner_lang["lang"] in ("en", "he") else lang
    notify_owner(db, reg, "mail_cash", lang, to_helpers=True, name=name,
                 guest_message=(request.form.get("message") or "").strip()[:1000],
                 amount=(ob_money.fmt_minor(amount_minor, currency, _ol) if amount_minor is not None
                         else _t("mail_cash_no_amount", _ol)))
    if _guest_email():
        send_guest_link(db, cur.lastrowid, token, _guest_email(), lang)
    track("guest_report", owner_uid=reg["user_id"])
    return redirect(url_for("guest_manage", token=token))


# ---------------------------------------------------------------- guest manage
@app.route("/g/<token>")
def guest_manage(token):
    db = get_db()
    claim = db.execute("SELECT * FROM claims WHERE token_hash=?",
                       (ob_security.hash_token(token),)).fetchone()
    if not claim:
        abort(404)
    reg = db.execute("SELECT * FROM registries WHERE id=?", (claim["registry_id"],)).fetchone()
    item = None
    if claim["item_id"]:
        item = db.execute("SELECT * FROM registry_items WHERE id=?", (claim["item_id"],)).fetchone()
    days_to_simcha = None
    if reg["event_date"]:
        try:
            days_to_simcha = (date.fromisoformat(reg["event_date"][:10]) - date.today()).days
        except ValueError:
            pass
    return render_template("guest_manage.html", claim=claim, reg=reg, item=item, days_to_simcha=days_to_simcha,
                           token=token, pay_links=reg_pay_links(reg), can_email=ob_mail.configured())


@app.route("/g/<token>/email", methods=["POST"])
def guest_email_link(token):
    """Email the guest their private /g/ link — for guests who skipped the
    optional email field and would otherwise lose the gift with the tab. The
    address is kept on the claim (only if none was given) so the reminder
    reaches them too."""
    lang = current_lang()
    db = get_db()
    if rate_limited("guest_link_mail", limit=5, per=3600):
        abort(429)
    email = (request.form.get("email") or "").strip()[:200]
    if not ob_security.valid_email(email):
        flash(_t("guest_email_link_bad", lang), "err")
        return redirect(url_for("guest_manage", token=token))
    with ob_db.write_txn(db):
        claim = db.execute("SELECT id, guest_email FROM claims WHERE token_hash=?",
                           (ob_security.hash_token(token),)).fetchone()
        if not claim:
            abort(404)
        if not claim["guest_email"]:
            db.execute("UPDATE claims SET guest_email=? WHERE id=?", (email, claim["id"]))
    send_guest_link(db, claim["id"], token, email, lang)
    flash(_t("guest_email_link_sent", lang), "ok")
    return redirect(url_for("guest_manage", token=token))


@app.route("/g/<token>/report", methods=["POST"])
def guest_report(token):
    lang = current_lang()
    db = get_db()
    with ob_db.write_txn(db):
        claim = db.execute("SELECT * FROM claims WHERE token_hash=?",
                           (ob_security.hash_token(token),)).fetchone()
        if not claim:
            abort(404)
        if claim["status"] not in ("reserved", "expired"):
            flash(_t("guest_action_invalid", lang), "err")
            return redirect(url_for("guest_manage", token=token))
        late = 1 if claim["status"] == "expired" else 0
        note = " ".join((request.form.get("report_note") or "").split())[:500]
        db.execute("UPDATE claims SET status='reported', reported_at=?, late=?, report_note=? WHERE id=?",
                   (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), late, note,
                    claim["id"]))
        _log_claim_event(db, claim["id"], "reported", "guest", "late" if late else "")
        reg = db.execute("SELECT * FROM registries WHERE id=?", (claim["registry_id"],)).fetchone()
        item = (db.execute("SELECT * FROM registry_items WHERE id=?", (claim["item_id"],)).fetchone()
                if claim["item_id"] else None)
    owner_lang = (db.execute("SELECT lang FROM users WHERE id=?", (reg["user_id"],)).fetchone() or {"lang": ""})["lang"]
    owner_lang = owner_lang if owner_lang in ("en", "he") else lang
    extra = {} if item else {"item": _t("gift_cash", owner_lang)}
    if item and claim["kind"] == "chip":
        extra = {"item": chip_label(claim["amount_minor"], item["name"], item["name_he"], owner_lang)}
        item = None
    notify_owner(db, reg, "mail_reported", lang, to_helpers=True, item=item, qty=claim["qty"] or 1, name=claim["guest_name"],
                 note=_t("mail_reported_note", owner_lang).format(note=note) if note else "", **extra)
    track("guest_report", owner_uid=reg["user_id"])
    flash(_t("guest_report_done", lang), "ok")
    return redirect(url_for("guest_manage", token=token))


@app.route("/g/<token>/cancel", methods=["POST"])
def guest_cancel(token):
    lang = current_lang()
    db = get_db()
    with ob_db.write_txn(db):
        claim = db.execute("SELECT * FROM claims WHERE token_hash=?",
                           (ob_security.hash_token(token),)).fetchone()
        if not claim:
            abort(404)
        if claim["status"] not in ("reserved", "expired"):
            flash(_t("guest_action_invalid", lang), "err")
            return redirect(url_for("guest_manage", token=token))
        db.execute("UPDATE claims SET status='cancelled', cancelled_by='guest', cancelled_at=? WHERE id=?",
                   (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), claim["id"]))
        _log_claim_event(db, claim["id"], "cancelled", "guest")
    flash(_t("guest_cancel_done", lang), "ok")
    return redirect(url_for("guest_manage", token=token))


# ---------------------------------------------------------------- auth
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if rate_limited("signup", limit=8, per=3600):
            abort(429)
        if is_spam():
            return redirect(url_for("signup"))
        lang = current_lang()
        name = (request.form.get("name") or "").strip()[:120]
        email = (request.form.get("email") or "").strip().lower()[:200]
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2", pw)  # the form has one field + "show password"; older forms sent two
        if not name or not ob_security.valid_email(email):
            flash(_t("form_error", lang), "err")
        elif len(pw) < 8:
            flash(_t("pw_short", lang), "err")
        elif pw != pw2:
            flash(_t("pw_mismatch", lang), "err")
        else:
            db = get_db()
            try:
                cur = db.execute(
                    "INSERT INTO users (email, pw_hash, name) VALUES (?,?,?)",
                    (email, generate_password_hash(pw), name))
                _fresh_session("pending_add", "pending_join")
                session["uid"] = cur.lastrowid
                session["sv"] = 1
                db.execute("UPDATE users SET lang=? WHERE id=?", (current_lang(), cur.lastrowid))
                track("signup")
                if session.get("pending_join"):  # came from an invite: back to it, not a registry of their own
                    return redirect(url_for("join_registry", token=session["pending_join"]))
                return redirect(url_for("registry_new"))
            except sqlite3.IntegrityError:
                flash(_t("email_taken", lang), "err")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if rate_limited("login", limit=10, per=600):
            abort(429)
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        row = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row and check_password_hash(row["pw_hash"], pw):
            nxt = ob_security.safe_next(request.form.get("next") or request.args.get("next", ""))
            _fresh_session("pending_join")
            session["uid"] = row["id"]
            session["sv"] = row["session_ver"]
            get_db().execute("UPDATE users SET lang=? WHERE id=?", (current_lang(), row["id"]))
            if not nxt and session.get("pending_join"):
                nxt = url_for("join_registry", token=session["pending_join"])
            return redirect(nxt or url_for("dashboard"))
        flash(_t("login_error", current_lang()), "err")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout", methods=["POST"])
def logout():
    _fresh_session()
    return redirect(url_for("index"))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        if rate_limited("forgot", limit=5, per=3600):
            abort(429)
        lang = current_lang()
        email = (request.form.get("email") or "").strip().lower()
        if rate_limited(f"forgot_email:{email}", limit=5, per=3600):
            abort(429)
        if not ob_mail.configured():  # host AND user AND password — a half-set ob.env sends nothing
            flash(_t("forgot_noemail", lang), "err")
            return redirect(url_for("contact"))
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = ob_security.new_token()
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            with ob_db.write_txn(db):
                db.execute("UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL",
                          (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
                db.execute(
                    "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?,?,?)",
                    (user["id"], ob_security.hash_token(token), expires_at))
            send_mail(email, _t("mail_reset_subj", lang),
                      _t("mail_reset_body", lang).format(link=ext_url("reset_password", token=token)))
        # same message either way, so the form can't be used to probe for accounts
        flash(_t("forgot_sent", lang), "ok")
        return redirect(url_for("login"))
    return render_template("forgot.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    lang = current_lang()
    db = get_db()
    row = db.execute(
        "SELECT * FROM password_resets WHERE token_hash=? AND used_at IS NULL",
        (ob_security.hash_token(token),)).fetchone()
    now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    if not row or row["expires_at"] < now:
        flash(_t("reset_invalid", lang), "err")
        return redirect(url_for("forgot"))
    if request.method == "POST":
        pw = request.form.get("password") or ""
        pw2 = request.form.get("password2") or ""
        if len(pw) < 8:
            flash(_t("pw_short", lang), "err")
        elif pw != pw2:
            flash(_t("pw_mismatch", lang), "err")
        else:
            pw_hash = generate_password_hash(pw)
            with ob_db.write_txn(db):
                # spend this token first, under the lock: of two simultaneous submits only one
                # gets rowcount 1 — a reset link sets the password exactly once
                spent = db.execute(
                    "UPDATE password_resets SET used_at=? WHERE id=? AND used_at IS NULL AND expires_at>=?",
                    (now, row["id"], now)).rowcount
                if spent:
                    db.execute(
                        "UPDATE users SET pw_hash=?, session_ver=session_ver+1 WHERE id=?",
                        (pw_hash, row["user_id"]))
                    db.execute("UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL",
                              (now, row["user_id"]))
            if not spent:
                flash(_t("reset_invalid", lang), "err")
                return redirect(url_for("forgot"))
            flash(_t("reset_done", lang), "ok")
            return redirect(url_for("login"))
    return render_template("reset.html", token=token)


# ---------------------------------------------------------------- couple dashboard
def _dashboard_checklist(db, reg, n_items, n_usable, gifts):
    """Onboarding checklist items, each (key, done: bool). Disappears from the
    dashboard once every item is done (SPEC_V3 "Onboarding & dashboard")."""
    prefs = _prefs(reg)
    # a cash-only gift = a registry_items row with no store url at all
    n_cash_only = db.execute(
        "SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0 AND url=''",
        (reg["id"],)).fetchone()[0]
    has_pay_link = bool(reg_pay_links(reg))
    return [
        ("details", bool(reg["title"] and reg["couple_names"])),
        ("gifts", n_usable >= 5),
        ("payment", has_pay_link or n_cash_only == 0),
        # guests who buy from a store are told to "have it delivered" — they need an address
        ("delivery", bool(reg["delivery_note"] or reg["delivery_note_he"])
                     or (n_items > 0 and n_items == n_cash_only)),
        ("visibility", bool(prefs.get("visibility_reviewed_at"))),
        ("previewed", bool(prefs.get("previewed_at"))),
        ("shared", (reg["views"] or 0) > 0 or bool(prefs.get("shared_at"))),
    ]


@app.route("/dashboard")
@login_required
def dashboard():
    reg = user_registry()
    gifts = stats = totals = checklist = queues = room_fills = None
    if reg:
        db = get_db()
        now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        gifts = []
        for row in db.execute(
                "SELECT c.*, ri.name AS item_name, ri.name_he AS item_name_he,"
                " ri.url AS item_url, ri.store AS item_store, ri.availability AS item_availability"
                " FROM claims c"
                " LEFT JOIN registry_items ri ON ri.id = c.item_id"
                " WHERE c.registry_id=? ORDER BY c.created_at DESC", (reg["id"],)):
            gft = dict(row)
            if gft["kind"] == "chip":
                gft["chip_label"] = chip_label(gft["amount_minor"], gft["item_name"], gft["item_name_he"], current_lang())
                gft["chip_gift"] = _thank_item(gft, current_lang())
            # a reservation past its hold is already free on the public page; show it the
            # same way here even before `manage.py expire-claims` flips the stored status
            if gft["status"] == "reserved" and gft["expires_at"] and gft["expires_at"] <= now:
                gft["status"] = "expired"
            gifts.append(gft)
        # open gifts first, cancelled/expired ones last (still newest-first within each group)
        gifts.sort(key=lambda gft: gft["status"] in ("cancelled", "expired"))
        n_items = db.execute("SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0",
                             (reg["id"],)).fetchone()[0]
        n_usable = db.execute(
            "SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0"
            " AND (url != '' OR ?)", (reg["id"], 1 if reg_pay_links(reg) else 0)).fetchone()[0]
        live = [gft for gft in gifts if gft["status"] in ("reserved", "reported", "received")]
        committed = item_claim_counts(reg["id"])
        # an item chipped in on counts as reserved only once it is fully funded (committed counts it then)
        n_claimed = len({gft["item_id"] for gft in live if gft["item_id"] is not None
                         and (gft["kind"] != "chip" or committed.get(gft["item_id"], 0) > 0)})
        n_cash = sum(1 for gft in live if gft["kind"] in ("cash", "chip"))
        all_taken = n_items > 0 and all(
            committed.get(r["id"], 0) >= r["qty_wanted"] for r in db.execute(
                "SELECT id, qty_wanted FROM registry_items WHERE registry_id=? AND archived=0", (reg["id"],)))
        stats = dict(items=n_items, claimed=n_claimed, cash=n_cash, all_taken=all_taken,
                     brachos=db.execute("SELECT COUNT(*) FROM brachos WHERE registry_id=?", (reg["id"],)).fetchone()[0],
                     views=reg["views"] if "views" in reg.keys() else 0)
        totals = {}
        for gft in gifts:
            if gft["amount_minor"] is not None and gft["status"] == "received":
                cur = gft["currency"] or "ILS"
                totals[cur] = totals.get(cur, 0) + gft["amount_minor"]
        checklist = _dashboard_checklist(db, reg, n_items, n_usable, gifts)
        room_fills = _room_fills(db, reg, committed)
        queues = dict(
            awaiting_confirm=[g for g in gifts if g["status"] == "reported"],
            waiting=[g for g in gifts if g["status"] == "reserved"],
            unthanked=[g for g in gifts if g["status"] == "received" and not g["thanked"]],
        )
    after_days = to_thank = None
    if reg:
        try:
            after_days = (date.today() - date.fromisoformat(reg["event_date"])).days
        except (ValueError, TypeError):
            pass
        if not after_days or after_days < 1:
            after_days = None
        else:
            to_thank = (sum(1 for gft in gifts if gft["status"] in ("reported", "received") and not gft["thanked"])
                        + get_db().execute("SELECT COUNT(*) FROM outside_gifts WHERE registry_id=? AND thanked=0",
                                           (reg["id"],)).fetchone()[0])
    return render_template("dashboard.html", reg=reg, gifts=gifts, stats=stats, totals=totals,
                           after_days=after_days, to_thank=to_thank,
                           checklist=checklist, queues=queues, room_fills=room_fills,
                           helping_owner=(_people(reg)[0] if reg and not is_reg_owner(reg) else None),
                           shana_arrival=_shana_offer(get_db(), current_user(), reg) if reg else None)


# which room of the dashboard's floor plan each category's gifts live in
ROOM_FOR_CATEGORY = {"kitchen": "kitchen", "appliances": "kitchen", "dining": "salon", "judaica": "salon",
                     "bedding": "bedroom", "home": "entry"}


def room_of(category):
    """The room of the apartment drawing a gift of this category lives in."""
    return ROOM_FOR_CATEGORY.get(category, "entry")


def room_fills_for(items, committed):
    """{room: {done, total, pct}} in gift units (qty) over registry item rows: how much of each
    room's list is already spoken for (reserved, on the way or received). Shared by the couple's
    dashboard and the guests' view of the registry ("their home, filling up")."""
    fills = {room: {"done": 0, "total": 0, "pct": 0.0} for room in set(ROOM_FOR_CATEGORY.values())}
    for r in items:
        f = fills[room_of(r["category"])]
        f["total"] += r["qty_wanted"]
        f["done"] += min(committed.get(r["id"], 0), r["qty_wanted"])
    for f in fills.values():
        f["pct"] = round(f["done"] / f["total"], 3) if f["total"] else 0.0
    return fills


def _room_fills(db, reg, committed):
    return room_fills_for(db.execute(
        "SELECT id, category, qty_wanted FROM registry_items WHERE registry_id=? AND archived=0",
        (reg["id"],)).fetchall(), committed)


def _shana_offer(db, user, reg):
    """The couple's arrival date (ISO) when it is still ahead, the apartment isn't marked fully
    furnished and they haven't sent a Shana Rishonah request yet — the dashboard then mentions the
    setup service once, quietly. None otherwise."""
    prefs = _prefs(reg)
    if prefs.get("furnished") == "furnished":
        return None
    try:
        arrival = date.fromisoformat((prefs.get("arrival_date") or "")[:10])
    except ValueError:
        return None
    if arrival < datetime.now(timezone.utc).date():
        return None
    if user and user["email"] and db.execute(
            "SELECT 1 FROM shana_requests WHERE lower(email)=lower(?) LIMIT 1", (user["email"],)).fetchone():
        return None
    return arrival.isoformat()


def _shana_prefill():
    """A signed-in couple's request form starts with what their registry already knows."""
    user = current_user()
    reg = user_registry() if user else None
    if not reg:
        return {}
    prefs = _prefs(reg)
    furnishing = prefs.get("furnished")
    return {"name": user["name"] or reg["couple_names"], "email": user["email"],
            "arrival": (prefs.get("arrival_date") or "")[:10], "city": reg["city"] or "",
            "furnishing": furnishing if furnishing in ("empty", "partly", "furnished") else ""}


@app.route("/dashboard/shared", methods=["POST"])
@login_required
def dashboard_shared():
    """Beacon the design agent's app.js fires on a copy-link/WhatsApp-share
    click (data-share-beacon). Records the share so the dashboard checklist's
    "shared" step can complete even before a guest visits. No body needed."""
    reg = user_registry()
    if reg:
        db = get_db()
        prefs = _prefs(reg)
        if not prefs.get("shared_at"):
            prefs["shared_at"] = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
            with ob_db.write_txn(db):
                db.execute("UPDATE registries SET preferences_json=? WHERE id=?",
                          (json.dumps(prefs), reg["id"]))
        track("share_click")
    return ("", 204)


@app.route("/registry/close", methods=["POST"])
@login_required
def registry_close():
    """Close the gift list (owner or helper): guests see a thank-you instead of the gifts and can
    still leave a bracha; reservations already made stay as they are. `/registry/reopen` undoes it."""
    return _set_closed(True)


@app.route("/registry/reopen", methods=["POST"])
@login_required
def registry_reopen():
    return _set_closed(False)


def _set_closed(closed):
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    db = get_db()
    with ob_db.write_txn(db):
        db.execute("UPDATE registries SET closed_at=? WHERE id=?",
                   (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
                    if closed else None, reg["id"]))
    track("registry_closed" if closed else "registry_reopened")
    flash(_t("list_closed_flash" if closed else "list_reopened_flash", current_lang()), "ok")
    return redirect(url_for("registry_edit", _anchor="rf-close") if request.form.get("back") == "edit"
                    else url_for("dashboard"))


@app.route("/dashboard/print")
@login_required
def dashboard_print():
    reg = user_registry()
    if not reg:
        abort(404)
    return render_template("dashboard_print.html", reg=reg)


@app.route("/dashboard/qr.svg")
@login_required
def dashboard_qr():
    reg = user_registry()
    if not reg:
        abort(404)
    import segno
    qr = segno.make(registry_share_url(reg["slug"]), error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=6, border=2, dark="#223354")
    resp = app.response_class(buf.getvalue(), mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- share kit
SHARE_KINDS = ("family", "friends", "abroad", "invite", "reminder")


def share_messages(reg, msg_lang):
    """Ready-to-send messages in `msg_lang`, each linking to the registry page in that language
    (a Hebrew message opens the Hebrew page whatever language the couple uses). The abroad
    message mentions the cash option only when the couple has a payment link; the reminder
    only shows while the date is 3+ days away."""
    link = ext_url("registry", slug=reg["slug"], **({"lang": "he"} if msg_lang == "he" else {}))
    cash = _t("share_msg_abroad_cash", msg_lang) if reg_pay_links(reg) else ""
    try:
        days = (date.fromisoformat(reg["event_date"]) - date.today()).days
    except (ValueError, TypeError):
        days = 0
    out = []
    for kind in SHARE_KINDS:
        if kind == "reminder" and days < 3:
            continue
        text = _t("share_msg_" + kind, msg_lang).format(
            link=link, names=pick(reg, "couple_names", msg_lang), cash=cash, n=days)
        out.append(dict(kind=kind, text=text, subject=_t("share_mail_subj", msg_lang)))
    return out


@app.route("/registry/share")
@login_required
def registry_share():
    """Share kit: the messages in the couple's language first, the other language folded below,
    each with WhatsApp / email / copy (an edited message sends as edited: app.js), plus the QR
    code and the printable insert."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    lang = current_lang()
    groups = [(code, share_messages(reg, code)) for code in (lang, "he" if lang == "en" else "en")]
    return render_template("share.html", reg=reg, groups=groups)


@app.route("/registry/new", methods=["GET", "POST"])
@login_required
def registry_new():
    if user_registry():
        return redirect(url_for("registry_edit"))
    if request.method == "POST":
        return _save_registry(None)
    # the name they gave at signup is almost always who the registry is for —
    # start "Your names" with it rather than asking twice
    user = current_user()
    start = {"couple_names": user["name"]} if user and user["name"] else None
    return render_template("registry_form.html", reg=None, form=start, prefs={})


@app.route("/registry/edit", methods=["GET", "POST"])
@login_required
def registry_edit():
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    if request.method == "POST":
        return _save_registry(reg)
    return render_template("registry_form.html", reg=reg, prefs=_prefs(reg))


PREFERENCE_FIELDS = ("bed_size", "colors", "apartment_size", "furnished",
                     "arrival_date", "items_needed")
VISIBILITY_VALUES = ("draft", "unlisted", "public")


def _form_event_date(f, lang):
    """The simcha date from the registry form as ISO ('' for none); ValueError with the
    message to show. The Hebrew picker (hd_day / hd_month / hd_year) wins only when the
    couple changed it: `hdate_was` carries what the page showed, so on a form prefilled
    from the saved date, editing just the calendar date still works."""
    picked = tuple((f.get(k) or "").strip() for k in ("hd_day", "hd_month", "hd_year"))
    if any(picked) and "|".join(picked) != (f.get("hdate_was") or ""):
        if not all(picked):
            raise ValueError(_t("r_hdate_incomplete", lang))
        try:
            day, year = int(picked[0]), int(picked[2])
        except ValueError:
            raise ValueError(_t("r_bad_date", lang))
        month = ob_hebcal.resolve_month(picked[1], year)
        if month is None or not 5600 <= year <= 6000:
            raise ValueError(_t("r_bad_date", lang))
        try:
            return ob_hebcal.from_hebrew(year, month, day).isoformat()
        except ValueError:
            raise ValueError(_t("r_hdate_no_day", lang).format(
                month=ob_hebcal.month_name(year, month, lang),
                year=ob_hebcal.numeral(year) if lang == "he" else year,
                days=ob_hebcal.month_days(month, year)))
    raw = (f.get("event_date") or "").strip()
    if not raw:
        return ""
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise ValueError(_t("r_bad_date", lang))


def _flash_date_note(event_type, event_date, old_date, lang):
    """A newly set wedding date on Shabbos, Yom Tov, Chol Hamoed or Tisha B'Av gets one
    gentle "check the date" note (motzei Shabbos weddings are real, so it never blocks).
    Other simchas skip it: a bar mitzvah or a bris on Shabbos is ordinary."""
    if event_type != "wedding" or not event_date or event_date == (old_date or ""):
        return
    note = ob_hebcal.day_note(date.fromisoformat(event_date))
    if not note:
        return
    kind, holiday = note
    when = f"{format_date(event_date, lang)} ({ob_hebcal.format_hebrew(event_date, lang)})"
    flash(_t("r_date_note_" + kind, lang).format(
        date=when, holiday=_t("hol_" + holiday, lang) if holiday else ""), "warn")


def hdate_form(form, reg, lang):
    """What the registry form's Hebrew-date picker shows: the submitted values when the
    form came back with an error, else the saved date's Hebrew date; plus the year list
    (last year to three years on, and the shown year if it's outside that)."""
    if form is not None and "hdate_was" in form:
        shown = tuple((form.get(k) or "") for k in ("hd_day", "hd_month", "hd_year"))
        was = form.get("hdate_was") or ""
    else:
        iso = (form or {}).get("event_date") or (reg["event_date"] if reg else "") or ""
        try:
            y, m, d = ob_hebcal.to_hebrew(date.fromisoformat(iso[:10]))
            shown = (str(d), ob_hebcal.month_choice(y, m), str(y))
        except ValueError:
            shown = ("", "", "")
        was = "|".join(shown) if any(shown) else ""
    this_year = ob_hebcal.to_hebrew(date.today())[0]
    years = list(range(this_year - 1, this_year + 4))
    if shown[2].isdigit() and int(shown[2]) not in years:
        years.append(int(shown[2]))
        years.sort()
    return dict(day=shown[0], month=shown[1], year=shown[2], was=was,
                open=any(shown) and "|".join(shown) != was,
                days=range(1, 31), years=[(y, ob_hebcal.numeral(y) if lang == "he" else str(y)) for y in years],
                months=[(c, ob_hebcal.choice_label(c, lang)) for c in ob_hebcal.MONTH_CHOICES])


def _save_registry(reg):
    """4-section form: Details -> Israel preferences -> Payment (optional) ->
    Visibility. On any validation error, re-render with `request.form` so the
    couple never loses what they typed (SPEC_V3 "Onboarding & dashboard")."""
    lang = current_lang()
    f = request.form
    title = (f.get("title") or "").strip()[:160]
    couple = (f.get("couple_names") or "").strip()[:160]
    pay = {}
    pay_errors = []
    for col in ("paypal_url", "stripe_url", "bit_url"):
        u = (f.get(col) or "").strip()[:300]
        if not u:
            pay[col] = ""
            continue
        try:
            _provider, canon = ob_security.classify_pay_url(u)
            pay[col] = canon
        except ValueError as e:
            pay[col] = u  # keep what they typed so they can fix it
            pay_errors.append(_t(str(e), lang))
    if reg and not is_reg_owner(reg):
        # a helper edits everything else; where guests' money goes stays the owner's decision
        pay = {c: (reg[c] or "") for c in ("paypal_url", "stripe_url", "bit_url")}
        pay_errors = []
    event_type = f.get("event_type") if f.get("event_type") in EVENT_TYPES else "wedding"
    visibility = f.get("visibility") if f.get("visibility") in VISIBILITY_VALUES else (
        reg["visibility"] if reg else "unlisted")
    prefs = _prefs(reg) if reg else {}
    for pf in PREFERENCE_FIELDS:
        val = (f.get(pf) or "").strip()[:300]
        if val:
            prefs[pf] = val
        else:
            prefs.pop(pf, None)
    if "visibility" in f:
        prefs["visibility_reviewed_at"] = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    if not reg and not title:  # first-time setup: the title can wait ("Our new home" until they change it)
        title = _t("r_default_title", "en")
    if not title or not couple:
        flash(_t("form_error", lang), "err")
        return render_template("registry_form.html", reg=reg, form=f, prefs=prefs)
    try:
        event_date = _form_event_date(f, lang)
    except ValueError as e:
        flash(str(e), "err")
        return render_template("registry_form.html", reg=reg, form=f, prefs=prefs)
    if pay_errors:
        for msg in pay_errors:
            flash(msg, "err")
        return render_template("registry_form.html", reg=reg, form=f, prefs=prefs)
    db = get_db()
    # payment-link changes are security-sensitive (they redirect guest money) —
    # require the couple to re-enter their current password whenever any pay
    # field actually changes, per SPEC_V3 "Security".
    if reg:
        changed_pay = any(pay[c] != (reg[c] if c in reg.keys() else "") for c in
                          ("paypal_url", "stripe_url", "bit_url"))
        if changed_pay:
            if rate_limited("pay_reauth", limit=8, per=900):
                abort(429)
            cur_pw = f.get("current_password") or ""
            user = db.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
            if not cur_pw or not check_password_hash(user["pw_hash"], cur_pw):
                flash(_t("reauth_required", lang), "err")
                return render_template("registry_form.html", reg=reg, form=f, prefs=prefs, show_reauth=True)
    title_he = (f.get("title_he") or "").strip()[:160]
    if not reg and not title_he and title == _t("r_default_title", "en"):
        title_he = _t("r_default_title", "he")
    fields = (title, title_he,
              couple, (f.get("couple_names_he") or "").strip()[:160],
              event_type, event_date,
              (f.get("city") or "").strip()[:120],
              (f.get("message") or "").strip()[:2000],
              (f.get("message_he") or "").strip()[:2000],
              pay["paypal_url"], pay["stripe_url"], pay["bit_url"],
              1 if visibility == "public" else 0, visibility,
              (f.get("delivery_note") or "").strip()[:1000],
              (f.get("delivery_note_he") or "").strip()[:1000],
              json.dumps(prefs))
    if reg:
        with ob_db.write_txn(db):
            db.execute(
                "UPDATE registries SET title=?, title_he=?, couple_names=?, couple_names_he=?,"
                " event_type=?, event_date=?, city=?, message=?, message_he=?, paypal_url=?,"
                " stripe_url=?, bit_url=?, is_public=?, visibility=?, delivery_note=?,"
                " delivery_note_he=?, preferences_json=? WHERE id=?",
                fields + (reg["id"],))
            if any(pay[c] != (reg[c] if c in reg.keys() else "") for c in
                  ("paypal_url", "stripe_url", "bit_url")):
                db.execute("UPDATE users SET session_ver=session_ver+1 WHERE id=?", (session["uid"],))
                session["sv"] = db.execute("SELECT session_ver FROM users WHERE id=?",
                                           (session["uid"],)).fetchone()[0]
                pay_changed = True
            else:
                pay_changed = False
        if pay_changed:
            # these links decide where guests' money goes: always tell the account owner
            owner = db.execute("SELECT email FROM users WHERE id=?", (session["uid"],)).fetchone()
            if owner and owner["email"]:
                links = ("\n".join(u for u in (pay["paypal_url"], pay["stripe_url"], pay["bit_url"]) if u)
                         or _t("mail_paylinks_none", lang))
                send_mail(owner["email"], _t("mail_paylinks_subj", lang),
                          _t("mail_paylinks_body", lang).format(links=links,
                                                                 contact=ext_url("contact")))
        flash(_t("r_saved", lang), "ok")
        _flash_date_note(event_type, event_date, reg["event_date"], lang)
        return redirect(url_for("dashboard"))
    slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    while db.execute("SELECT 1 FROM registries WHERE slug=?", (slug,)).fetchone():
        slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    with ob_db.write_txn(db):
        if (db.execute("SELECT 1 FROM registries WHERE user_id=?", (session["uid"],)).fetchone()
                or db.execute("SELECT 1 FROM registry_members WHERE user_id=?", (session["uid"],)).fetchone()):
            return redirect(url_for("registry_edit"))  # a double-submitted create form, or already helping
        cur = db.execute(
            "INSERT INTO registries (user_id, slug, title, title_he, couple_names,"
            " couple_names_he, event_type, event_date, city, message, message_he,"
            " paypal_url, stripe_url, bit_url, is_public, visibility, delivery_note,"
            " delivery_note_he, preferences_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session["uid"], slug) + fields)
        reg_id = cur.lastrowid
        pending = session.pop("pending_add", None) or []
        if pending:
            _apply_pending_add(db, reg_id, pending)
    track("registry_created")
    flash(_t("r_created", lang), "ok")
    _flash_date_note(event_type, event_date, "", lang)
    return redirect(url_for("items_manage"))


@app.route("/registry/items")
@login_required
def items_manage():
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    db = get_db()
    prefill = session.pop("link_prefill", None) or {}   # set by items_lookup; gone after one view
    lookup_note = prefill.get("status", "")
    cat = request.args.get("cat", "")
    q = (request.args.get("q") or "").strip()
    sql = "SELECT * FROM catalog_items WHERE active=1"
    params = []
    if cat in CATEGORIES:
        sql += " AND category=?"
        params.append(cat)
    if q:
        clause, qparams = ob_search.search_clause(q)
        sql += clause
        params += qparams
    catalog = db.execute(sql + " ORDER BY category, sort", params).fetchall()
    mine = db.execute(
        "SELECT * FROM registry_items WHERE registry_id=? AND archived=0"
        " ORDER BY priority DESC, category, id", (reg["id"],)).fetchall()
    archived = db.execute(
        "SELECT * FROM registry_items WHERE registry_id=? AND archived=1"
        " ORDER BY category, id", (reg["id"],)).fetchall()
    archived_claim_counts = {a["id"]: db.execute(
        "SELECT COUNT(*) FROM claims WHERE item_id=?", (a["id"],)).fetchone()[0] for a in archived}
    have_catalog_ids = {m["catalog_id"] for m in mine if m["catalog_id"]}
    breakdown = item_claim_breakdown(reg["id"])
    claimed = {k: v["committed"] for k, v in breakdown.items()}
    n_committed = sum(1 for m in mine if claimed.get(m["id"]))
    n_needs_link = sum(1 for m in mine if not m["url"] and not reg_pay_links(reg))
    price_news = _catalog_price_news(db, mine)
    return render_template("items.html", reg=reg, catalog=catalog, mine=mine, archived=archived,
                           archived_claim_counts=archived_claim_counts,
                           have=have_catalog_ids, claimed=claimed, breakdown=breakdown, cat=cat, q=q,
                           n_committed=n_committed, n_needs_link=n_needs_link, price_news=price_news,
                           prefill=prefill, lookup_note=lookup_note, has_pay=bool(reg_pay_links(reg)))


# ------------------------------------------------- paste a link from any store
# Friendly store names for hosts the catalog already uses (matched on a dot boundary).
STORE_NAMES = {
    "ksp.co.il": "KSP",
    "judaicawebstore.com": "Judaica WebStore",
    "homecenter.co.il": "Home Center",
    "payngo.co.il": "Machsanei Chashmal",
    "heichal.co.il": "Heichal Menachem",
    "vardinon.co.il": "Vardinon",
    "ikea.com": "IKEA",
    "ikea.co.il": "IKEA",
    "zarahome.com": "Zara Home",
    "foxhome.co.il": "Fox Home",
    "golfco.co.il": "Golf & Co",
    "naaman.co.il": "Naaman",
    "hakolabait.co.il": "Hakol LaBait",
}
_HEBREW_RE = re.compile(r"[֐-׿]")
LOOKUP_LIMIT = 20          # pasted-link lookups per couple per LOOKUP_PER seconds
LOOKUP_PER = 600


def _link_host(url):
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def store_name_for(host, site_name=""):
    """A friendly store name: the known-store table, else the page's own site name, else the
    host's main label capitalised ("shop.example.co.il" -> "Example")."""
    host = (host or "").lower()
    for dom, label in STORE_NAMES.items():
        if host == dom or host.endswith("." + dom):
            return label
    parts = host.split(".")
    if "amazon" in parts[-3:-1]:
        return "Amazon"
    site_name = " ".join((site_name or "").split())[:120]
    if site_name:
        return site_name
    labels = [p for p in parts[:-1] if p]
    while len(labels) > 1 and labels[-1] in ("co", "com", "org", "net", "gov", "ac"):
        labels.pop()
    return labels[-1].capitalize() if labels else ""


def clean_image_url(raw):
    """A picture link we keep: https only, the app's URL check, at most 500 chars; else ''."""
    raw = (raw or "").strip()
    return raw if raw.startswith("https://") and len(raw) <= 500 and valid_http_url(raw) else ""


def _lookup_price(info):
    """(whole shekels or None, original price text or ''): ILS as is, another currency only
    when ob_money has a rate for it (then the text is shown so the couple checks it)."""
    try:
        price = Decimal(str(info.get("price")).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None, ""
    cur = (info.get("currency") or "").upper()
    cur = "ILS" if cur == "NIS" else cur
    if not price.is_finite() or price <= 0:
        return None, ""
    original = ""
    if cur == "ILS":
        ils = price
    elif cur and ob_money.RATES.get(cur):
        ils = price * Decimal(str(ob_money.RATES[cur]))
        try:
            original = ob_money.fmt_minor(ob_money.to_minor(price, cur), cur)
        except ValueError:
            return None, ""
    else:
        return None, ""
    whole = int(ils.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return (whole, original) if 0 < whole <= 99999 else (None, "")


def link_prefill(link, info):
    """Turn a lookup() result into the custom-form prefill dict (+ a `status` for the note).
    status: ok | unread (we kept what we could) | bad (nothing usable at all)."""
    if info.get("error") in ("bad_url", "blocked_host"):
        return {"status": "bad"}
    url = ""
    pasted = link.strip()
    if pasted and not pasted.startswith("http"):
        pasted = "https://" + pasted
    for cand in (info.get("url"), pasted):
        if cand and valid_http_url(cand):
            url = cand
            break
    host = _link_host(url) or _link_host(info.get("url") or "") or (info.get("host") or "")
    out = {"status": "ok" if info.get("ok") and url else "unread", "url": url, "host": host,
           "store": store_name_for(host, info.get("site_name") if info.get("ok") else "") if host else ""}
    if out["status"] == "unread" and not url:
        out["store"] = ""
    if info.get("ok"):
        name = " ".join((info.get("name") or "").split())[:200]
        out["name"] = name
        out["name_he"] = name if _HEBREW_RE.search(name) else ""
        out["image"] = clean_image_url(info.get("image"))
        price, original = _lookup_price(info)
        if price:
            out["price_nis"] = price
            out["converted_from"] = original
    return out


@app.route("/registry/items/lookup", methods=["POST"])
@login_required
def items_lookup():
    """Fetch the pasted store link once, stash the prefill in the session and redirect, so a
    refresh of the items page never fetches again. Nothing is saved until the couple presses Add."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    link = (request.form.get("link") or "").strip()[:2000]
    if ob_security.rate_limited(get_db(), "lookup", f"u{session.get('uid')}", LOOKUP_LIMIT, LOOKUP_PER):
        session["link_prefill"] = {"status": "limited"}
    elif not link:
        session["link_prefill"] = {"status": "bad"}
    else:
        session["link_prefill"] = link_prefill(link, ob_linkinfo.lookup(link))
    return redirect(url_for("items_manage", _anchor="custom"))


def _catalog_price_news(db, items):
    """{registry_item_id: catalog row} for items whose catalog product (same link) has a newer
    checked price than the one on the couple's list. The registry price is the couple's
    snapshot and refresh-registry-links leaves it alone, so the items page offers it instead.
    Skipped when the couple typed their own price (`price_nis` in overrides)."""
    news = {}
    for m in items:
        if not m["catalog_id"] or "price_nis" in (m["overrides"] or "").split(","):
            continue
        c = db.execute("SELECT id, url, price_nis, price_status, price_checked_at FROM catalog_items"
                       " WHERE id=? AND active=1", (m["catalog_id"],)).fetchone()
        if (c and c["price_status"] == "verified" and c["price_nis"] and c["url"]
                and c["url"] == m["url"] and c["price_nis"] != m["price_nis"]
                and (c["price_checked_at"] or "") > (m["price_checked_at"] or "")):
            news[m["id"]] = c
    return news


@app.route("/registry/items/add", methods=["POST"])
def items_add():
    """Logged in: add straight away. Logged out (catalog "Add" button before
    signup): queue the catalog_id in session['pending_add'] and send them to
    signup — applied to the registry once they create one (SPEC_V3
    "Onboarding" -> pending_add). Not @login_required: it handles the
    anonymous case itself instead of bouncing through login."""
    user = current_user()
    f = request.form
    cat_id = f.get("catalog_id")
    if not user:
        if cat_id:
            try:
                cat_id_int = int(cat_id)
            except ValueError:
                cat_id_int = None
            if cat_id_int:
                pending = session.get("pending_add") or []
                if cat_id_int not in pending:
                    pending.append(cat_id_int)
                session["pending_add"] = pending[-50:]
        flash(_t("pending_add_signup", current_lang()), "ok")
        return redirect(url_for("signup"))
    reg = user_registry()
    if not reg:
        abort(400)
    db = get_db()
    if cat_id:
        c = db.execute("SELECT * FROM catalog_items WHERE id=? AND active=1", (cat_id,)).fetchone()
        if not c:
            abort(404)
        exists = db.execute(
            "SELECT 1 FROM registry_items WHERE registry_id=? AND catalog_id=?",
            (reg["id"], c["id"])).fetchone()
        if not exists:
            _insert_registry_item_from_catalog(db, reg["id"], c)
            _maybe_track_first_gifts(db, reg["id"])
    else:
        name = (f.get("name") or "").strip()[:200]
        url = (f.get("url") or "").strip()[:500]
        if url and not url.startswith("http"):
            url = "https://" + url
        url_dropped = bool(url) and not valid_http_url(url)
        if url_dropped:
            url = ""
        try:
            price = max(0, int(f.get("price_nis") or 0))
        except ValueError:
            price = 0
        duplicate = name and db.execute(
            "SELECT 1 FROM registry_items WHERE registry_id=? AND archived=0 AND catalog_id IS NULL"
            " AND name=? AND url=? AND price_nis=?", (reg["id"], name, url, price)).fetchone()
        if url_dropped:
            flash(_t("custom_url_dropped", current_lang()), "err")
        if name and not duplicate:
            db.execute(
                "INSERT INTO registry_items (registry_id, name, name_he, category,"
                " price_nis, store, url, kind, image) VALUES (?,?,?,?,?,?,?,?,?)",
                (reg["id"], name, (f.get("name_he") or "").strip()[:200],
                 f.get("category") if f.get("category") in CATEGORIES else "home",
                 price, (f.get("store") or "").strip()[:120], url,
                 "product" if url else "idea", clean_image_url(f.get("image"))))
            _maybe_track_first_gifts(db, reg["id"])
        elif not name:
            flash(_t("form_error", current_lang()), "err")
    if request.args.get("back") == "check":
        return redirect(url_for("registry_check") + "#" + (request.args.get("sec") or "budgets")[:20])
    if request.args.get("back") == "item":
        # back to a catalog item page; the slug is looked up, never used as a redirect target
        here = _catalog_by_slug(db, request.args.get("slug") or "")
        if here:
            return redirect(url_for("catalog_item", slug=catalog_slug(here)))
    if request.args.get("back") == "cat" and request.args.get("cat_slug") in GIFT_CATS:
        return redirect(url_for("gift_category", cat_slug=request.args["cat_slug"])
                        + (f"#c-{cat_id}" if cat_id else ""))
    if request.args.get("back") == "catalog":
        keep ={k: request.args.get(k) for k in ("cat", "q", "price", "kind", "sort", "page")
                if request.args.get(k)}
        return redirect(url_for("catalog_page", **keep) + (f"#c-{cat_id}" if cat_id else ""))
    return redirect(url_for("items_manage", cat=request.args.get("cat", ""),
                            q=request.args.get("q", "")) + ("#add-more" if cat_id else "#mine"))


FUND_MIN, FUND_MAX = 100, 99999  # shekels: the goal of a cash fund


@app.route("/registry/items/fund", methods=["POST"])
@login_required
def items_fund():
    """A cash fund ("Sefarim fund"): a custom registry item with no store link that guests chip in
    toward (chip_in=1, qty 1, price = the goal). It needs a working payment link, as every chip-in does.
    The note is stored in `variant`, the field guests see as the couple's request."""
    lang = current_lang()
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    if not reg_pay_links(reg):
        flash(_t("fund_need_pay", lang), "err")
        return redirect(url_for("registry_edit", _anchor="rf-payment"))
    f = request.form
    name = " ".join((f.get("name") or "").split())[:200]
    raw = (f.get("goal") or "").strip()
    if not name:
        flash(_t("fund_need_name", lang), "err")
        return redirect(url_for("items_manage", _anchor="fund"))
    if not re.fullmatch(r"[0-9]{1,6}", raw) or not FUND_MIN <= int(raw) <= FUND_MAX:
        flash(tf("fund_bad_goal", lang, lo="{:,}".format(FUND_MIN), hi="{:,}".format(FUND_MAX)), "err")
        return redirect(url_for("items_manage", _anchor="fund"))
    db = get_db()
    with ob_db.write_txn(db):
        dup = db.execute("SELECT 1 FROM registry_items WHERE registry_id=? AND archived=0 AND chip_in=1"
                         " AND catalog_id IS NULL AND name=? AND price_nis=?",
                         (reg["id"], name, int(raw))).fetchone()
        if not dup:
            db.execute(
                "INSERT INTO registry_items (registry_id, name, name_he, category, price_nis, store, url,"
                " kind, image, qty_wanted, chip_in, variant, price_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (reg["id"], name, name if re.search("[֐-׿]", name) else "", "home", int(raw),
                 "", "", "idea", "", 1, 1, (f.get("note") or "").strip()[:120], ""))
            _maybe_track_first_gifts(db, reg["id"])
    flash(_t("fund_added", lang), "ok")
    return redirect(url_for("items_manage") + "#mine")


# ---------------------------------------------------------------- list check
CHECK_ROOMS = ("kitchen", "salon", "bedroom", "entry")   # rooms a category can put a gift in
CHECK_FEW = 3       # fewer open gifts than this in a guest budget = "only a few left"
CHECK_SUGGEST = 3   # catalog suggestions per gap


def _band_of(price):
    for key, (lo, hi) in CATALOG_PRICE_BANDS.items():
        if price >= lo and (hi is None or price < hi):
            return key
    return None


def _check_suggestions(db, have, band=None, room=None):
    """Catalog gifts not on the list yet for one gap: starter-pack staples first, then featured."""
    sql = "SELECT * FROM catalog_items WHERE active=1 AND price_nis > 0"
    params = []
    if band:
        lo, hi = CATALOG_PRICE_BANDS[band]
        sql += " AND price_nis >= ?" + (" AND price_nis < ?" if hi is not None else "")
        params += [lo] + ([hi] if hi is not None else [])
    if room:
        cats = [c for c, r in ROOM_FOR_CATEGORY.items() if r == room]
        sql += " AND category IN (%s)" % ",".join("?" * len(cats))
        params += cats
    if have:
        sql += " AND id NOT IN (%s)" % ",".join("?" * len(have))
        params += sorted(have)
    sql += " ORDER BY (starter_group != '') DESC, featured DESC, sort, id LIMIT ?"
    return db.execute(sql, params + [CHECK_SUGGEST]).fetchall()


def list_check(db, reg):
    """What a guest finds on the list right now, gap by gap. Counts are open gift units
    (qty still wanted minus what's reserved, on its way or received)."""
    items = db.execute("SELECT * FROM registry_items WHERE registry_id=? AND archived=0"
                       " ORDER BY priority DESC, price_nis, id", (reg["id"],)).fetchall()
    committed = {k: v["committed"] for k, v in item_claim_breakdown(reg["id"]).items()}
    have = {r["catalog_id"] for r in items if r["catalog_id"]}
    pay = bool(reg_pay_links(reg))
    bands = {k: {"open": 0, "total": 0, "names": []} for k in CATALOG_PRICE_BANDS}
    rooms = {k: {"open": 0, "total": 0} for k in CHECK_ROOMS}
    no_price, cant_give, chip_suggest = [], [], None
    for r in items:
        left = max(r["qty_wanted"] - committed.get(r["id"], 0), 0)
        if (chip_suggest is None and pay and left and r["qty_wanted"] == 1 and not r["chip_in"]
                and (r["price_nis"] or 0) >= CHIP_SUGGEST_FROM):
            chip_suggest = r  # a big open gift guests could share
        room = rooms[room_of(r["category"])]
        room["total"] += r["qty_wanted"]
        room["open"] += left
        if not r["url"] and not pay:
            cant_give.append(r)
        if not r["price_nis"]:
            no_price.append(r)
            continue
        b = bands[_band_of(r["price_nis"])]
        b["total"] += r["qty_wanted"]
        b["open"] += left
        if left and len(b["names"]) < 3:
            b["names"].append(r)
    for key, b in bands.items():
        # the top band can be empty on purpose; the three guest budgets shouldn't be
        b["status"] = ("good" if b["open"] >= CHECK_FEW else "few" if b["open"] else
                       "none" if key != "1500plus" else "quiet")
        b["suggest"] = _check_suggestions(db, have, band=key) if b["status"] in ("few", "none") else []
    for key, rm in rooms.items():
        rm["status"] = "listed" if rm["total"] else "empty"
        rm["suggest"] = _check_suggestions(db, have, room=key) if not rm["total"] else []
    budget_keys = [k for k in CATALOG_PRICE_BANDS if k != "1500plus"]
    return dict(
        items=len(items), open=sum(b["open"] for b in bands.values()),
        bands=bands, rooms=rooms, no_price=no_price, cant_give=cant_give, pay=pay, chip_suggest=chip_suggest,
        fund_suggest=pay and not any(r["chip_in"] for r in items),
        budgets_ok=sum(1 for k in budget_keys if bands[k]["status"] == "good"), budgets_n=len(budget_keys),
        rooms_ok=sum(1 for rm in rooms.values() if rm["status"] == "listed"), rooms_n=len(rooms),
    )


@app.route("/registry/check")
@login_required
def registry_check():
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    return render_template("list_check.html", reg=reg, check=list_check(get_db(), reg))


STARTER_GROUPS_ORDER = ["first_week", "kitchen", "shabbos", "bedbath", "appliances"]


@app.route("/registry/items/starter", methods=["GET", "POST"])
@login_required
def items_starter():
    """Grouped starter-pack picker (First Week / Kitchen Basics / Shabbos
    Hosting / Bedding & Bath / Appliances) — replaces the old one-click
    "add all featured" (featured is promotional catalog/home-page placement,
    not a curated starter list; see CHANGELOG_AI.md "Decisions"). GET shows
    a checkbox preview per group with already-added items pre-unchecked and
    labelled; POST adds whichever boxes were checked, at the chosen qty."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    db = get_db()
    have_catalog_ids = {r["catalog_id"] for r in db.execute(
        "SELECT catalog_id FROM registry_items WHERE registry_id=? AND catalog_id IS NOT NULL",
        (reg["id"],))}
    if request.method == "POST":
        added = 0
        with ob_db.write_txn(db):
            for key, val in request.form.items():
                if not key.startswith("add_"):
                    continue
                try:
                    cid = int(key[len("add_"):])
                except ValueError:
                    continue
                c = db.execute("SELECT * FROM catalog_items WHERE id=? AND active=1", (cid,)).fetchone()
                if not c or cid in have_catalog_ids:
                    continue
                try:
                    qty = max(1, min(int(request.form.get(f"qty_{cid}", 1)), 99))
                except ValueError:
                    qty = 1
                _insert_registry_item_from_catalog(db, reg["id"], c)
                if qty > 1:
                    db.execute("UPDATE registry_items SET qty_wanted=? WHERE registry_id=? AND catalog_id=?",
                              (qty, reg["id"], cid))
                added += 1
            if added:
                _maybe_track_first_gifts(db, reg["id"])
        flash(tf("starter_added", current_lang(), n=added), "ok")
        return redirect(url_for("items_manage") + "#mine")
    groups = starter_groups(db)
    return render_template("items_starter.html", reg=reg, groups=groups,
                           group_order=STARTER_GROUPS_ORDER, have=have_catalog_ids)


def starter_groups(db):
    """{group: [catalog rows]} for every starter group, in STARTER_GROUPS_ORDER (shared by the
    starter picker and the /setup-cost calculator)."""
    return {g: db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND starter_group=? ORDER BY sort", (g,)).fetchall()
        for g in STARTER_GROUPS_ORDER}


# ---------------------------------------------------------------- setup-cost calculator
SETUP_PRESETS = {  # ?start=<key> -> starter groups ticked by default
    "minimum": ("first_week",),
    "home": ("first_week", "kitchen", "shabbos", "bedbath"),
    "everything": tuple(STARTER_GROUPS_ORDER),
}
SETUP_DEFAULT_PRESET = "home"
# Starter-picker options that are a second, pricier version of something already in the list (the
# first-week pots set, the knife block): fine to offer a couple, but in a cost total they count twice.
SETUP_SKIP = ("pots-pans-premium-10-piece-set", "chef-s-knife-professional")


@app.route("/setup-cost")
def setup_cost():
    """Public, itemised cost of a first apartment from the starter-group catalog items. The preset
    only decides which boxes are ticked and the server-rendered total; app.js (#starter-form)
    keeps the tally live."""
    db = get_db()
    preset = request.args.get("start")
    if preset not in SETUP_PRESETS:
        preset = SETUP_DEFAULT_PRESET
    groups = {grp: [r for r in rows if r["seed_key"] not in SETUP_SKIP]
              for grp, rows in starter_groups(db).items()}
    checked_groups = SETUP_PRESETS[preset]
    group_totals = {g: sum(r["price_nis"] or 0 for r in rows) for g, rows in groups.items()}
    total = sum(group_totals[g] for g in checked_groups)
    n_items = sum(len(groups[g]) for g in checked_groups)
    checked_dates = [r["price_checked_at"] for rows in groups.values() for r in rows if r["price_checked_at"]]
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    appliances_guide = any(g["slug"] == "appliances-from-abroad-or-buy-in-israel" for g in ob_guides.GUIDES)
    cur = (session.get("cur") or getattr(g, "display_currency", None)
           or ("USD" if "USD" in ob_money.CURRENCIES else "ILS"))
    est_rate = ob_money.RATES.get(cur) if cur != "ILS" else None
    return render_template(
        "setup_cost.html", groups=groups, group_order=STARTER_GROUPS_ORDER, presets=SETUP_PRESETS,
        preset=preset, checked_groups=checked_groups, group_totals=group_totals, total=total,
        n_items=n_items, last_checked=max(checked_dates) if checked_dates else "", bundles=bundles,
        appliances_guide=appliances_guide, est_rate=est_rate,
        est_sym=ob_money.CURRENCY_SYMBOLS.get(cur, cur + " ") if est_rate else "")


def _setup_ticked_ids(db, cap):
    """Ids of the ACTIVE catalog items ticked on the /setup-cost form (ascii-digit `add_<id>` keys
    only), in form order, at most `cap`."""
    wanted = []
    for key in request.form:
        if key.startswith("add_") and key[4:].isascii() and key[4:].isdigit() and int(key[4:]) not in wanted:
            wanted.append(int(key[4:]))
            if len(wanted) >= 200:  # far more than the page offers; bounds the query below
                break
    if not wanted:
        return []
    ok = {r[0] for r in db.execute(
        "SELECT id FROM catalog_items WHERE active=1 AND id IN (%s)" % ",".join("?" * len(wanted)),
        wanted)}
    return [i for i in wanted if i in ok][:cap]


@app.route("/setup-cost/request", methods=["POST"])
def setup_cost_request():
    """"Have it done for you": carry the ticked list (ids only, max 60) in the session to the Shana
    Rishonah request form, which attaches it to the lead if the visitor sends it."""
    if rate_limited("setup_request", limit=20, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("setup_cost"))
    ids = _setup_ticked_ids(get_db(), 60)
    if ids:
        session["shana_list"] = ids
        track("setup_cost_request")
    return redirect(url_for("shana") + "#request")


@app.route("/shana-rishonah/list/remove", methods=["POST"])
def shana_list_remove():
    session.pop("shana_list", None)
    return redirect(url_for("shana") + "#request")


def _shana_list_items(db):
    """Active catalog rows for the session's carried list, in saved order (prices read fresh)."""
    ids = [i for i in (session.get("shana_list") or []) if isinstance(i, int)][:60]
    if not ids:
        return []
    rows = {r["id"]: r for r in db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND id IN (%s)" % ",".join("?" * len(ids)), ids)}
    return [rows[i] for i in ids if i in rows]


@app.route("/setup-cost/start", methods=["POST"])
def setup_cost_start():
    """Turn the ticked setup-cost items into a registry: straight onto the list for a couple with
    one (no duplicates), else queued in session['pending_add'] (cap 50, as items_add) until they
    sign up and create a registry."""
    if rate_limited("setup_start", limit=20, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("setup_cost"))
    lang = current_lang()
    db = get_db()
    ids = _setup_ticked_ids(db, 50)
    if not ids:
        flash(_t("setup_none_selected", lang), "err")
        return redirect(url_for("setup_cost"))
    track("setup_cost_start")
    reg = user_registry() if current_user() else None
    if reg:
        with ob_db.write_txn(db):
            added = _apply_pending_add(db, reg["id"], ids)
            if added:
                _maybe_track_first_gifts(db, reg["id"])
        flash(tf("starter_added", lang, n=added) if added else _t("setup_nothing_new", lang), "ok")
        return redirect(url_for("items_manage") + "#mine")
    pending = [i for i in (session.get("pending_add") or []) if i not in ids] + ids
    session["pending_add"] = pending[-50:]
    flash(_t("pending_add_signup", lang), "ok")
    return redirect(url_for("registry_new") if current_user() else url_for("signup"))


@app.route("/registry/items/<int:item_id>/update", methods=["POST"])
@login_required
def items_update(item_id):
    reg = user_registry()
    db = get_db()
    item = db.execute("SELECT * FROM registry_items WHERE id=? AND registry_id=?",
                      (item_id, reg["id"] if reg else -1)).fetchone()
    if not item:
        abort(404)
    lang = current_lang()
    here = url_for("items_manage", _anchor=f"item-{item_id}")
    # same write lock as the guest claim route, so a reservation landing at this
    # moment can't slip past the quantity check or collide with the delete
    with ob_db.write_txn(db):
        if request.form.get("use_catalog_price"):
            # the price is re-read from the catalog here, never taken from the form
            c = _catalog_price_news(db, [item]).get(item_id)
            funded = (item_claim_breakdown(reg["id"]).get(item_id) or _blank_breakdown())["chip_minor"]
            if c and (c["price_nis"] or 0) * 100 < funded:
                flash(tf("chip_price_locked", lang, amount=ob_money.fmt_minor(funded, "ILS", lang)), "err")
            elif c:
                db.execute("UPDATE registry_items SET price_nis=?, price_status=?, price_checked_at=?"
                           " WHERE id=?", (c["price_nis"], c["price_status"], c["price_checked_at"], item_id))
                flash(_t("price_news_done", lang), "ok")
            return redirect(here)
        if request.form.get("delete"):
            has_claims = db.execute("SELECT 1 FROM claims WHERE item_id=? LIMIT 1", (item_id,)).fetchone()
            if has_claims:
                db.execute("UPDATE registry_items SET archived=1 WHERE id=?", (item_id,))
            else:
                db.execute("DELETE FROM registry_items WHERE id=?", (item_id,))
            return redirect(url_for("items_manage", _anchor="mine"))
        try:
            qty = max(1, min(int(request.form.get("qty_wanted", 1)), 99))
        except ValueError:
            qty = 1
        committed = item_claim_counts(reg["id"]).get(item_id, 0)
        if qty < committed:
            flash(tf("qty_below_committed", lang, n=committed), "err")
            return redirect(here)
        if qty > 1 and item["chip_in"]:
            flash(_t("chip_qty_locked", lang), "err")
            return redirect(here)
        db.execute("UPDATE registry_items SET qty_wanted=?, priority=? WHERE id=?",
                   (qty, 1 if request.form.get("priority") else 0, item_id))
    flash(_t("item_updated", lang), "ok")
    return redirect(here)


_OVERRIDABLE_FIELDS = ("url", "image", "store", "brand", "name", "price_nis")


@app.route("/registry/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def item_edit(item_id):
    """Full edit of one registry item (SPEC_V3 "Items management"). Editing a
    field that's normally inherited from the catalog (url/image/store/brand/
    name) records it in `overrides` so a later `refresh-registry-links` never
    clobbers the couple's own edit."""
    reg = user_registry()
    db = get_db()
    item = db.execute("SELECT * FROM registry_items WHERE id=? AND registry_id=?",
                      (item_id, reg["id"] if reg else -1)).fetchone()
    if not item:
        abort(404)
    lang = current_lang()
    committed = item_claim_counts(reg["id"]).get(item_id, 0)

    def _again():
        # re-show the form with what the couple typed, not the stored values
        typed = dict(item)
        typed.update({k: v for k, v in request.form.items() if k in typed and k != "id"})
        typed["priority"] = 1 if request.form.get("priority") else 0
        typed["chip_in"] = 1 if request.form.get("chip_in") or item["chip_in"] else 0
        return render_template("item_edit.html", reg=reg, item=typed, committed=committed,
                               chip=_chip_edit_state(reg, item))

    if request.method == "POST":
        f = request.form
        name = (f.get("name") or "").strip()[:200]
        if not name:
            flash(_t("form_error", lang), "err")
            return _again()
        url = (f.get("url") or "").strip()[:500]
        if url and not url.startswith("http"):
            url = "https://" + url
        url_ok = (not url) or valid_http_url(url)
        if url and not url_ok:
            flash(_t("bad_url", lang), "err")
            return _again()
        try:
            price = max(0, int(f.get("price_nis") or 0))
        except ValueError:
            price = 0
        try:
            qty = max(1, min(int(f.get("qty_wanted", 1)), 99))
        except ValueError:
            qty = 1
        store = (f.get("store") or "").strip()[:120]
        brand = (f.get("brand") or "").strip()[:80]
        image = item["image"] or ""
        if "image" in f and (f.get("image") or "").strip() != image:
            image = clean_image_url(f.get("image"))     # https only; anything else is dropped
        new_vals = dict(name=name, url=url, store=store, brand=brand, price_nis=price, image=image)
        overrides = set(x for x in (item["overrides"] or "").split(",") if x)
        for field in _OVERRIDABLE_FIELDS:
            old = item[field] if field in item.keys() else ""
            if new_vals.get(field, old) != old:
                overrides.add(field)
        with ob_db.write_txn(db):
            committed = item_claim_counts(reg["id"]).get(item_id, 0)
            if qty < committed:
                flash(tf("qty_below_committed", lang, n=committed), "err")
                return _again()
            chip_in = _chip_in_for_save(reg, item, price, qty, bool(f.get("chip_in")), lang)
            if chip_in is None:
                return _again()
            db.execute(
                "UPDATE registry_items SET name=?, name_he=?, brand=?, price_nis=?, url=?, store=?,"
                " qty_wanted=?, priority=?, note=?, note_he=?, variant=?,"
                " kind=?, overrides=?, chip_in=?, image=? WHERE id=?",
                (name, (f.get("name_he") or "").strip()[:200], brand, price, url, store, qty,
                 1 if f.get("priority") else 0, (f.get("note") or "").strip()[:1000],
                 # note_he left the form (the note is private); keep whatever an older form saved
                 ((f.get("note_he") if "note_he" in f else item["note_he"]) or "").strip()[:1000],
                 (f.get("variant") or "").strip()[:120],
                 f.get("kind") if f.get("kind") in ("product", "idea", "cash_need") else item["kind"],
                 ",".join(sorted(overrides)), chip_in, image, item_id))
        flash(_t("item_updated", lang), "ok")
        return redirect(url_for("items_manage", _anchor=f"item-{item_id}"))
    return render_template("item_edit.html", reg=reg, item=item, committed=committed,
                           chip=_chip_edit_state(reg, item))


def _chip_edit_state(reg, item):
    """What the item edit page shows for the "let guests chip in" box: can it be ticked, why not,
    and whether guests already chipped in (then it stays on)."""
    br = item_claim_breakdown(reg["id"]).get(item["id"]) or _blank_breakdown()
    reason = ""
    if br["chip_count"]:
        reason = "locked"
    elif not reg_pay_links(reg):
        reason = "paylink"
    elif not int(item["price_nis"] or 0) > 0:
        reason = "price"
    elif item["qty_wanted"] != 1:
        reason = "qty"
    return dict(can=not reason, reason=reason, count=br["chip_count"], funded_minor=br["chip_minor"])


def _chip_in_for_save(reg, item, price, qty, want, lang):
    """The chip_in value to store when the couple saves the item form (inside the write txn, so a
    contribution landing now is counted), or None after flashing why the save is refused: chip-in
    needs a payment link, a price and a quantity of 1; it can't be switched off, nor the price
    dropped below what's given, nor the quantity raised, while guests have chipped in."""
    br = item_claim_breakdown(reg["id"]).get(item["id"]) or _blank_breakdown()
    if br["chip_count"]:
        if qty != 1:
            flash(_t("chip_qty_locked", lang), "err")
            return None
        if price * 100 < br["chip_minor"]:
            flash(tf("chip_price_locked", lang, amount=ob_money.fmt_minor(br["chip_minor"], "ILS", lang)), "err")
            return None
        return 1
    if not want:
        return 0
    if not reg_pay_links(reg) or price <= 0 or qty != 1:
        flash(_t("chip_cant", lang), "err")
        return None
    return 1


def _owned_claim(claim_id):
    reg = user_registry()
    return get_db().execute("SELECT * FROM claims WHERE id=? AND registry_id=?",
                            (claim_id, reg["id"] if reg else -1)).fetchone()


@app.route("/claim/<int:claim_id>/confirm", methods=["POST"])
@login_required
def claim_confirm(claim_id):
    db = get_db()
    with ob_db.write_txn(db):
        c = _owned_claim(claim_id)
        if not c:
            abort(404)
        # 'expired' too: the gift can still arrive after the hold lapsed (guests can report late)
        if c["status"] in ("reported", "reserved", "expired"):
            db.execute("UPDATE claims SET status='received', confirmed_at=? WHERE id=?",
                      (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), claim_id))
            _log_claim_event(db, claim_id, "received", "owner",
                             "late" if c["status"] == "expired" else "")
            track("receipt_confirmed")
            told = notify_guest(db, c, "mail_guest_received")
            lang = current_lang()
            flash(tf("claim_confirmed_told", lang, name=c["guest_name"]) if told
                  else _t("claim_confirmed_ok", lang), "ok")
    return redirect(url_for("dashboard", _anchor=f"claim-{claim_id}"))


@app.route("/claim/<int:claim_id>/release", methods=["POST"])
@app.route("/claim/<int:claim_id>/cancel", methods=["POST"])
@login_required
def claim_cancel(claim_id):
    """Owner cancels/frees a claim (guest changed their mind / never bought it).
    /release is kept as an alias to this same handler."""
    db = get_db()
    with ob_db.write_txn(db):
        c = _owned_claim(claim_id)
        if not c:
            abort(404)
        # only open claims — a stale form (second tab) must never undo a received gift
        if c["status"] in ("reserved", "reported"):
            db.execute("UPDATE claims SET status='cancelled', cancelled_by='owner', cancelled_at=? WHERE id=?",
                      (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), claim_id))
            _log_claim_event(db, claim_id, "cancelled", "owner")
            # without this a guest who still meant to buy it would — and the couple gets two
            told = notify_guest(db, c, "mail_guest_released")
            lang = current_lang()
            flash(tf("claim_released_told", lang, name=c["guest_name"]) if told
                  else _t("claim_released_ok", lang), "ok")
    return redirect(url_for("dashboard", _anchor=f"claim-{claim_id}"))


@app.route("/claim/<int:claim_id>/thanked", methods=["POST"])
@login_required
def claim_thanked(claim_id):
    db = get_db()
    c = _owned_claim(claim_id)
    if not c:
        abort(404)
    if c["thanked"] or c["status"] in ("reported", "received"):
        db.execute("UPDATE claims SET thanked=? WHERE id=?", (0 if c["thanked"] else 1, claim_id))
    if request.form.get("back") == "thanks":
        return redirect(url_for("dashboard_thanks", _anchor=f"thanks-{claim_id}"))
    return redirect(url_for("dashboard", _anchor=f"claim-{claim_id}"))


# words that stay capitalised mid-sentence in an English note
_KEEP_CAPS = ("Shabbos", "Kiddush", "Havdalah", "Pesach", "Chanukah", "Sukkos", "Shavuos", "Yom Tov", "Seder",
              "Netilas", "Challah")


def _thank_item(gift, lang):
    """What a thank-you note thanks a chip-in guest for: "chipping in toward the fridge"."""
    name = (gift["item_name_he"] if lang == "he" and gift["item_name_he"] else gift["item_name"]) or ""
    if lang == "en":
        keep = name[1:2].isupper() or name.startswith(_KEEP_CAPS)
        name = "the " + (name if keep else name[:1].lower() + name[1:])
    return tf("dash_thank_item_chip", lang, item=name)


def _thanks_note(reg, gift, lang):
    """A thank-you note already started for one gift, in `lang`: {subject, body}. The couple edits
    it and sends it themselves (copy / WhatsApp / their own mail app) — the site never sends it."""
    name = (gift["item_name_he"] if lang == "he" and gift["item_name_he"] else gift["item_name"]) or ""
    if gift["kind"] == "cash" or not name:
        item = _t("dash_thank_item_cash", lang)
    elif gift["kind"] == "chip":
        item = _thank_item(gift, lang)
    elif lang == "he":
        item = name
    elif gift["kind"] == "outside" and re.match(r"(a|an|the|your|our|some)\s", name, re.I):
        item = name[:1].lower() + name[1:]
    else:  # "Thank you so much for the electric kettle" (keep "KitchenAid" / "LED" / "Shabbos" as written)
        keep = name[1:2].isupper() or name.startswith(_KEEP_CAPS)
        item = "the " + (name if keep else name[:1].lower() + name[1:])
    who = gift["guest_name"] or ""
    if lang == "en" and who[:4].lower() == "the " and len(who) > 4:
        who = who[4:]  # "Dear Friedman family", not "Dear The Friedman family"
    return dict(subject=tf("dash_thank_mail_subj", lang, item=item),
                body=tf("dash_thank_mail_body", lang, name=who, item=item,
                        couple=pick(reg, "couple_names", lang) or ""))


@app.route("/dashboard/thanks")
@login_required
def dashboard_thanks():
    """Thank-you studio: everyone who reported or delivered a gift — and the gifts the couple noted
    from outside the list — with their message and a note already started in their language."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("dashboard"))
    ui = current_lang()
    db = get_db()
    gifts = []
    for row in db.execute(
            "SELECT c.*, ri.name AS item_name, ri.name_he AS item_name_he FROM claims c"
            " LEFT JOIN registry_items ri ON ri.id = c.item_id"
            " WHERE c.registry_id=? AND c.status IN ('reported', 'received')", (reg["id"],)):
        gft = dict(row, anchor=str(row["id"]), toggle_url=url_for("claim_thanked", claim_id=row["id"]))
        gft["amount_label"] = (ob_money.fmt_minor(gft["amount_minor"], gft["currency"] or "ILS", ui)
                               if gft["amount_minor"] is not None and gft["kind"] == "cash" else "")
        if gft["kind"] == "chip":
            gft["chip_label"] = chip_label(gft["amount_minor"], gft["item_name"], gft["item_name_he"], ui)
        gifts.append(gft)
    for row in db.execute("SELECT * FROM outside_gifts WHERE registry_id=?", (reg["id"],)):
        gifts.append(dict(row, kind="outside", status="outside", guest_name=row["giver_name"],
                          guest_email=row["email"], item_name=row["gift"], item_name_he=None, report_note="",
                          qty=1, amount_label="", anchor=f"o{row['id']}",
                          toggle_url=url_for("outside_thanked", gift_id=row["id"])))
    for gft in gifts:
        gft["note_lang"] = gft["lang"] if gft["lang"] in ("en", "he") else ui
        gft["notes"] = {lang: _thanks_note(reg, gft, lang) for lang in ("en", "he")}
    gifts.sort(key=lambda gft: (gft["created_at"] or "", gft["anchor"]), reverse=True)
    brachos = db.execute("SELECT * FROM brachos WHERE registry_id=? ORDER BY created_at DESC, id DESC",
                         (reg["id"],)).fetchall()
    return render_template("thanks.html", reg=reg, outside_max=OUTSIDE_MAX, brachos=brachos,
                           to_thank=[g for g in gifts if not g["thanked"]],
                           thanked=[g for g in gifts if g["thanked"]])


# gifts from outside the list: noted by the couple, seen only on their thank-you page and keepsake
OUTSIDE_MAX = 600         # per registry: a big wedding's envelopes, with room to spare
OUTSIDE_PASTE_MAX = 200   # lines per paste
_HEBREW = re.compile("[א-ת]")
_OUTSIDE_SEPS = ("\t", " — ", " – ", " - ", ",", "،")


def _outside_split(line):
    """'Cohen family - salad bowl' -> ('Cohen family', 'salad bowl'); a bare name -> (name, '')."""
    for sep in _OUTSIDE_SEPS:
        if sep in line:
            name, gift = line.split(sep, 1)
            return name.strip(), gift.strip()
    return line.strip(), ""


def _owned_outside(gift_id):
    reg = user_registry()
    row = get_db().execute("SELECT * FROM outside_gifts WHERE id=?", (gift_id,)).fetchone()
    if not reg or not row or row["registry_id"] != reg["id"]:
        abort(404)
    return row


@app.route("/dashboard/thanks/outside", methods=["POST"])
@login_required
def outside_add():
    """One gift from the form, or a pasted list (one 'name - gift' per line)."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("dashboard"))
    ui = current_lang()
    if rate_limited("outside_add", limit=60, per=600):
        abort(429)
    db = get_db()
    room = OUTSIDE_MAX - db.execute("SELECT COUNT(*) FROM outside_gifts WHERE registry_id=?",
                                    (reg["id"],)).fetchone()[0]
    f = request.form
    if "lines" in f:
        rows = [_outside_split(ln) for ln in f.get("lines", "").splitlines() if ln.strip()]
        rows = [(n[:80], gft[:120]) for n, gft in rows if n]
        if not rows:
            flash(_t("outside_err_paste", ui), "err")
            return redirect(url_for("dashboard_thanks", _anchor="outside-add"))
        cut = len(rows) > min(OUTSIDE_PASTE_MAX, room)
        rows = rows[:max(0, min(OUTSIDE_PASTE_MAX, room))]
        if not rows:
            flash(tf("outside_err_full", ui, n=OUTSIDE_MAX), "err")
            return redirect(url_for("dashboard_thanks"))
        with ob_db.write_txn(db):
            for n, gft in rows:  # a line written in Hebrew starts its note in Hebrew, and vice versa
                note_lang = "he" if _HEBREW.search(n + gft) else "en" if re.search(r"[A-Za-z]", n + gft) else ui
                db.execute("INSERT INTO outside_gifts (registry_id, giver_name, gift, lang, created_by)"
                           " VALUES (?,?,?,?,?)", (reg["id"], n, gft, note_lang, session["uid"]))
        flash(tf("outside_added_n", ui, n=len(rows)) + (" " + tf("outside_paste_cut", ui, n=len(rows)) if cut else ""),
              "ok")
        return redirect(url_for("dashboard_thanks"))
    name = (f.get("giver_name") or "").strip()[:80]
    email = (f.get("email") or "").strip()
    lang = f.get("lang") if f.get("lang") in ("en", "he") else ui
    if not name:
        flash(_t("outside_err_name", ui), "err")
        return redirect(url_for("dashboard_thanks", _anchor="outside-add"))
    if email and not ob_security.valid_email(email):
        flash(_t("outside_err_email", ui), "err")
        return redirect(url_for("dashboard_thanks", _anchor="outside-add"))
    if room <= 0:
        flash(tf("outside_err_full", ui, n=OUTSIDE_MAX), "err")
        return redirect(url_for("dashboard_thanks"))
    cur = db.execute(
        "INSERT INTO outside_gifts (registry_id, giver_name, gift, message, email, lang, created_by)"
        " VALUES (?,?,?,?,?,?,?)", (reg["id"], name, (f.get("gift") or "").strip()[:120],
                                    (f.get("message") or "").strip()[:1000], email, lang, session["uid"]))
    flash(tf("outside_added", ui, name=name), "ok")
    return redirect(url_for("dashboard_thanks", _anchor=f"thanks-o{cur.lastrowid}"))


@app.route("/dashboard/thanks/outside/<int:gift_id>/thanked", methods=["POST"])
@login_required
def outside_thanked(gift_id):
    row = _owned_outside(gift_id)
    get_db().execute("UPDATE outside_gifts SET thanked=? WHERE id=?", (0 if row["thanked"] else 1, gift_id))
    return redirect(url_for("dashboard_thanks", _anchor=f"thanks-o{gift_id}"))


@app.route("/dashboard/brachos/<int:bracha_id>/delete", methods=["POST"])
@login_required
def bracha_delete(bracha_id):
    reg = user_registry()
    row = get_db().execute("SELECT registry_id FROM brachos WHERE id=?", (bracha_id,)).fetchone()
    if not reg or not row or row["registry_id"] != reg["id"]:
        abort(404)
    get_db().execute("DELETE FROM brachos WHERE id=?", (bracha_id,))
    flash(_t("brachos_removed", current_lang()), "ok")
    return redirect(url_for("dashboard_thanks", _anchor="brachos"))


@app.route("/dashboard/thanks/outside/<int:gift_id>/delete", methods=["POST"])
@login_required
def outside_delete(gift_id):
    _owned_outside(gift_id)
    get_db().execute("DELETE FROM outside_gifts WHERE id=?", (gift_id,))
    flash(_t("outside_removed", current_lang()), "ok")
    return redirect(url_for("dashboard_thanks"))


@app.route("/dashboard/keepsake")
@login_required
def dashboard_keepsake():
    """Every message guests left with their gifts, set as a printable keepsake."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("dashboard"))
    notes = get_db().execute(
        "SELECT c.guest_name, c.message, c.kind, c.created_at, ri.name AS item_name, ri.name_he AS item_name_he"
        " FROM claims c LEFT JOIN registry_items ri ON ri.id = c.item_id"
        " WHERE c.registry_id=? AND c.status IN ('reserved', 'reported', 'received') AND TRIM(c.message) != ''"
        " UNION ALL SELECT giver_name, message, 'outside', created_at, gift, NULL FROM outside_gifts"
        " WHERE registry_id=? AND TRIM(message) != ''"
        " UNION ALL SELECT guest_name, message, 'bracha', created_at, NULL, NULL FROM brachos WHERE registry_id=?"
        " ORDER BY 4", (reg["id"], reg["id"], reg["id"])).fetchall()
    return render_template("keepsake.html", reg=reg, notes=notes)


# ---------------------------------------------------------------- managing it together
MAX_HELPERS = 4      # people besides the owner: helpers plus invites still open
INVITE_DAYS = 7


def _utc_stamp(delta=None):
    t = datetime.now(timezone.utc).replace(tzinfo=None)
    return (t + delta if delta else t).strftime("%Y-%m-%d %H:%M:%S")


def _people(reg):
    """(owner, helpers) — users rows; helpers in the order they joined."""
    db = get_db()
    owner = db.execute("SELECT id, name, email, created_at FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    helpers = db.execute(
        "SELECT u.id, u.name, u.email, m.added_at, m.notify FROM registry_members m JOIN users u ON u.id = m.user_id"
        " WHERE m.registry_id=? ORDER BY m.added_at, u.id", (reg["id"],)).fetchall()
    return owner, helpers


def _open_invites(reg):
    return get_db().execute(
        "SELECT * FROM registry_invites WHERE registry_id=? AND used_at IS NULL AND revoked_at IS NULL"
        " AND expires_at > ? ORDER BY id", (reg["id"], _utc_stamp())).fetchall()


def _owned_registry_or_403():
    reg = user_registry()
    if not reg or not is_reg_owner(reg):
        abort(403)
    return reg


@app.route("/registry/people")
@login_required
def registry_people():
    """Who manages this registry: the owner, helpers, open invites — and a fresh invite link,
    shown once right after it's made (only its hash is stored)."""
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    owner, helpers = _people(reg)
    invites = _open_invites(reg) if is_reg_owner(reg) else []
    new = session.pop("new_invite", None)
    new_link = None
    if new and is_reg_owner(reg):
        made = [i for i in invites if i["id"] == new.get("id")]
        if made:
            new_link = dict(id=made[0]["id"], label=made[0]["label"],
                            url=ext_url("join_registry", token=new.get("token", "")))
    return render_template("people.html", reg=reg, owner=owner, helpers=helpers, invites=invites,
                           new_link=new_link, max_helpers=MAX_HELPERS,
                           room_left=MAX_HELPERS - len(helpers) - len(invites))


@app.route("/registry/people/invite", methods=["POST"])
@login_required
def people_invite():
    reg = _owned_registry_or_403()
    if rate_limited("invite", limit=10, per=3600):
        abort(429)
    lang = current_lang()
    db = get_db()
    token = ob_security.new_token()
    with ob_db.write_txn(db):
        _owner, helpers = _people(reg)
        if len(helpers) + len(_open_invites(reg)) >= MAX_HELPERS:
            flash(tf("people_invite_full", lang, n=MAX_HELPERS), "err")
            return redirect(url_for("registry_people"))
        cur = db.execute(
            "INSERT INTO registry_invites (registry_id, token_hash, label, created_by, expires_at)"
            " VALUES (?,?,?,?,?)",
            (reg["id"], ob_security.hash_token(token), (request.form.get("label") or "").strip()[:60],
             session["uid"], _utc_stamp(timedelta(days=INVITE_DAYS))))
    session["new_invite"] = {"id": cur.lastrowid, "token": token}
    track("helper_invited")
    flash(_t("people_invite_made", lang), "ok")
    return redirect(url_for("registry_people", _anchor="new-invite"))


@app.route("/registry/people/invite/<int:invite_id>/revoke", methods=["POST"])
@login_required
def people_invite_revoke(invite_id):
    reg = _owned_registry_or_403()
    get_db().execute(
        "UPDATE registry_invites SET revoked_at=? WHERE id=? AND registry_id=? AND used_at IS NULL"
        " AND revoked_at IS NULL", (_utc_stamp(), invite_id, reg["id"]))
    flash(_t("people_revoked", current_lang()), "ok")
    return redirect(url_for("registry_people"))


@app.route("/registry/people/<int:user_id>/remove", methods=["POST"])
@login_required
def people_remove(user_id):
    reg = _owned_registry_or_403()
    db = get_db()
    row = db.execute("SELECT u.name FROM registry_members m JOIN users u ON u.id = m.user_id"
                     " WHERE m.registry_id=? AND m.user_id=?", (reg["id"], user_id)).fetchone()
    if not row:
        abort(404)
    db.execute("DELETE FROM registry_members WHERE registry_id=? AND user_id=?", (reg["id"], user_id))
    flash(tf("people_removed", current_lang(), name=row["name"]), "ok")
    return redirect(url_for("registry_people"))


@app.route("/registry/people/<int:user_id>/owner", methods=["POST"])
@login_required
def people_make_owner(user_id):
    """Hand the registry to a helper (they take over the payment links; the old owner stays on as a
    helper) — so one of them can delete their account without deleting the registry."""
    reg = _owned_registry_or_403()
    if rate_limited("pay_reauth", limit=8, per=900):
        abort(429)
    lang = current_lang()
    me = current_user()
    if not check_password_hash(me["pw_hash"], request.form.get("current_password") or ""):
        flash(_t("reauth_required", lang), "err")
        return redirect(url_for("registry_people", _anchor=f"person-{user_id}"))
    db = get_db()
    with ob_db.write_txn(db):
        row = db.execute("SELECT u.name FROM registry_members m JOIN users u ON u.id = m.user_id"
                         " WHERE m.registry_id=? AND m.user_id=?", (reg["id"], user_id)).fetchone()
        if not row:
            abort(404)
        db.execute("DELETE FROM registry_members WHERE user_id=?", (user_id,))
        db.execute("UPDATE registries SET user_id=? WHERE id=?", (user_id, reg["id"]))
        db.execute("INSERT INTO registry_members (registry_id, user_id, added_at) VALUES (?,?,?)",
                   (reg["id"], me["id"], _utc_stamp()))
        notify_owner(db, dict(reg, user_id=user_id), "mail_owner_moved", lang, name=me["name"])
    flash(tf("people_owner_moved", lang, name=row["name"]), "ok")
    return redirect(url_for("registry_people"))


@app.route("/registry/people/leave", methods=["POST"])
@login_required
def people_leave():
    reg = user_registry()
    if not reg or is_reg_owner(reg):
        abort(403)  # the owner hands it over or deletes their account instead
    get_db().execute("DELETE FROM registry_members WHERE registry_id=? AND user_id=?",
                     (reg["id"], session["uid"]))
    flash(_t("people_left", current_lang()), "ok")
    return redirect(url_for("dashboard"))


@app.route("/registry/people/notify", methods=["POST"])
@login_required
def people_notify():
    """A helper turns the gift emails on or off for themselves (never for anyone else)."""
    reg = user_registry()
    if not reg or is_reg_owner(reg):
        abort(403)  # the owner always gets them
    on = request.form.get("notify") == "1"
    get_db().execute("UPDATE registry_members SET notify=? WHERE registry_id=? AND user_id=?",
                     (1 if on else 0, reg["id"], session["uid"]))
    flash(_t("people_notify_saved_on" if on else "people_notify_saved_off", current_lang()), "ok")
    return redirect(url_for("registry_people", _anchor="gift-emails"))


def _live_invite(db, token):
    if not token or len(token) > 100:
        return None
    return db.execute(
        "SELECT i.*, r.title, r.title_he, r.user_id AS owner_id, u.name AS inviter"
        " FROM registry_invites i JOIN registries r ON r.id = i.registry_id JOIN users u ON u.id = r.user_id"
        " WHERE i.token_hash=? AND i.used_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > ?",
        (ob_security.hash_token(token), _utc_stamp())).fetchone()


def _join_state(db, inv, user):
    """bad | signin | already | own (has a registry of their own) | other (helps elsewhere) | ok"""
    if not inv:
        return "bad"
    if not user:
        return "signin"
    if user["id"] == inv["owner_id"] or db.execute(
            "SELECT 1 FROM registry_members WHERE registry_id=? AND user_id=?",
            (inv["registry_id"], user["id"])).fetchone():
        return "already"
    if db.execute("SELECT 1 FROM registries WHERE user_id=?", (user["id"],)).fetchone():
        return "own"
    if db.execute("SELECT 1 FROM registry_members WHERE user_id=?", (user["id"],)).fetchone():
        return "other"
    return "ok"


@app.route("/join/<token>", methods=["GET", "POST"])
def join_registry(token):
    """An invite to help manage a registry. Logged out: the token waits in the session through
    signup/login, which bring them back here to accept explicitly."""
    db = get_db()
    lang = current_lang()
    user = current_user()
    if request.method == "POST":
        if not user:
            return redirect(url_for("login"))
        if rate_limited("join", limit=20, per=600):
            abort(429)
        with ob_db.write_txn(db):
            inv = _live_invite(db, token)
            state = _join_state(db, inv, user)
            if state == "ok":
                db.execute("INSERT INTO registry_members (registry_id, user_id, added_at) VALUES (?,?,?)",
                           (inv["registry_id"], user["id"], _utc_stamp()))
                db.execute("UPDATE registry_invites SET used_at=?, used_by=? WHERE id=?",
                           (_utc_stamp(), user["id"], inv["id"]))
                reg = db.execute("SELECT * FROM registries WHERE id=?", (inv["registry_id"],)).fetchone()
                # tells the owner straight away — if they didn't send this link, they'll want to know
                notify_owner(db, reg, "mail_member_joined", lang, name=user["name"], email=user["email"])
        if state == "ok":
            session.pop("pending_join", None)
            track("helper_joined")
            flash(tf("join_done", lang, title=pick(inv, "title", lang), name=inv["inviter"]), "ok")
            return redirect(url_for("dashboard"))
    else:
        inv = _live_invite(db, token)
        state = _join_state(db, inv, user)
    if state == "signin":
        session["pending_join"] = token
    elif state != "ok":
        session.pop("pending_join", None)
    return render_template("join.html", state=state, inv=inv, user=user, token=token)


@app.route("/dashboard/claims.csv")
@login_required
def dashboard_claims_csv():
    reg = user_registry()
    if not reg:
        abort(404)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "guest_name", "guest_email", "item", "qty", "kind", "status",
               "amount", "currency", "created_at"])
    for r in get_db().execute(
            "SELECT c.*, ri.name AS item_name FROM claims c"
            " LEFT JOIN registry_items ri ON ri.id=c.item_id"
            " WHERE c.registry_id=? ORDER BY c.created_at DESC", (reg["id"],)):
        w.writerow([csv_safe(r["id"]), csv_safe(r["guest_name"]), csv_safe(r["guest_email"]),
                   csv_safe(r["item_name"]), csv_safe("" if r["kind"] == "chip" else r["qty"]), csv_safe(r["kind"]),
                   csv_safe(r["status"]), csv_safe(r["amount_minor"]), csv_safe(r["currency"]),
                   csv_safe(r["created_at"])])
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=gifts.csv"
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- account (data export/deletion)
@app.route("/account")
@login_required
def account():
    reg = user_registry()
    owner, helpers = _people(reg) if reg else (None, [])
    return render_template("account.html", reg=reg, reg_owner=owner, helpers=helpers, me=current_user())


# ---------------------------------------------------------------- the weekly summary
DIGEST_EVERY = timedelta(days=7) - timedelta(hours=12)  # a daily job lands on the same weekday
DIGEST_SOON_DAYS = 60   # list gaps are worth an email of their own only this close to the event


def _digest_signer():
    return URLSafeSerializer(app.secret_key, salt="digest-off")


def digest_lines(db, reg, lang, since):
    """The weekly summary's bullet lines for one registry, in `lang` — [] when there's nothing to say.
    New gifts and brachos since `since`; gifts to confirm and to thank; and, close to the event, guest
    budgets with nothing left to choose (from the list check)."""
    rid = reg["id"]
    one = lambda sql: db.execute(sql, (rid,)).fetchone()[0]  # noqa: E731
    new_gifts = db.execute("SELECT COUNT(*) FROM claims WHERE registry_id=? AND created_at > ?"
                           " AND status IN ('reserved', 'reported', 'received')", (rid, since)).fetchone()[0]
    new_brachos = db.execute("SELECT COUNT(*) FROM brachos WHERE registry_id=? AND created_at > ?",
                             (rid, since)).fetchone()[0]
    confirm = one("SELECT COUNT(*) FROM claims WHERE registry_id=? AND status='reported'")
    thank = (one("SELECT COUNT(*) FROM claims WHERE registry_id=? AND status IN ('reported', 'received')"
                 " AND thanked=0") + one("SELECT COUNT(*) FROM outside_gifts WHERE registry_id=? AND thanked=0"))
    lines = []
    for key, n in (("digest_new_gifts", new_gifts), ("digest_brachos", new_brachos),
                   ("digest_confirm", confirm), ("digest_thank", thank)):
        if n:
            lines.append(_t(key + "_one", lang) if n == 1 else tf(key, lang, n=n))
    try:
        days = (date.fromisoformat(reg["event_date"]) - date.today()).days
    except (TypeError, ValueError):
        days = None
    if days is not None and 0 < days <= DIGEST_SOON_DAYS:
        check = list_check(db, reg)
        empty = [_t("price_band_" + k, lang) for k, b in check["bands"].items() if b["status"] == "none"]
        if check["items"] and empty:
            bands = empty[0] if len(empty) == 1 else ", ".join(empty[:-1]) + _t("digest_or", lang) + empty[-1]
            lines.append(tf("digest_gap", lang, bands=bands,
                            link=ext_url("registry_check") + ("?lang=he" if lang == "he" else "")))
    if not lines:
        return [], days
    return lines, days


def digest_mail(db, user, reg, now):
    """(subject, body) of one person's weekly summary, or None when there's nothing to say."""
    lang = user["lang"] if user["lang"] in ("en", "he") else "en"
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    since = max(user["digest_at"] or week_ago, week_ago)
    lines, days = digest_lines(db, reg, lang, since)
    if not lines:
        return None
    title = reg["title_he"] if lang == "he" and reg["title_he"] else reg["title"]
    q = "?lang=he" if lang == "he" else ""
    head = _t("digest_intro", lang)
    if days is not None and 0 < days <= DIGEST_SOON_DAYS:
        head += " " + (_t("digest_days_one", lang) if days == 1 else tf("digest_days", lang, n=days))
    body = "\n".join([head, ""] + ["• " + ln for ln in lines] + [
        "", tf("digest_links", lang, dashboard=ext_url("dashboard") + q, thanks=ext_url("dashboard_thanks") + q),
        "", tf("digest_off", lang, link=ext_url("digest_off", token=_digest_signer().dumps(user["id"])) + q)])
    return tf("digest_subj", lang, title=title), body


def send_digests(db, now=None):
    """Queue the weekly summary for everyone who is due one and has something to read: each owner, and
    each helper who turned on the gift emails, unless they turned the summary off. Returns the count."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    due = (now - DIGEST_EVERY).strftime("%Y-%m-%d %H:%M:%S")
    people = db.execute(
        "SELECT u.*, r.id AS reg_id FROM users u JOIN registries r ON r.user_id = u.id"
        " WHERE u.digest=1 AND (u.digest_at IS NULL OR u.digest_at <= ?)"
        " UNION ALL SELECT u.*, m.registry_id FROM users u JOIN registry_members m ON m.user_id = u.id"
        " WHERE m.notify=1 AND u.digest=1 AND (u.digest_at IS NULL OR u.digest_at <= ?)",
        (due, due)).fetchall()
    sent = 0
    for person in people:
        reg = db.execute("SELECT * FROM registries WHERE id=?", (person["reg_id"],)).fetchone()
        mail = digest_mail(db, person, reg, now) if reg and person["email"] else None
        if not mail:
            continue
        with ob_db.write_txn(db):  # mark first, then queue: a crash loses one summary, never repeats it
            db.execute("UPDATE users SET digest_at=? WHERE id=?", (now.strftime("%Y-%m-%d %H:%M:%S"), person["id"]))
            ob_mail.enqueue(db, person["email"], *mail)
        sent += 1
    return sent


@app.route("/account/digest", methods=["POST"])
@login_required
def account_digest():
    on = request.form.get("digest") == "1"
    get_db().execute("UPDATE users SET digest=? WHERE id=?", (1 if on else 0, session["uid"]))
    flash(_t("digest_saved_on" if on else "digest_saved_off", current_lang()), "ok")
    return redirect(url_for("account", _anchor="weekly-summary"))


@app.route("/digest/off/<token>", methods=["GET", "POST"])
def digest_off(token):
    """The email's own link: a page with one button (mail scanners open links; only a POST changes
    anything), no login needed — the signed token names the account."""
    try:
        uid = int(_digest_signer().loads(token))
    except (BadSignature, ValueError, TypeError):
        abort(404)
    db = get_db()
    user = db.execute("SELECT id, digest FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        abort(404)
    if request.method == "POST":
        db.execute("UPDATE users SET digest=0 WHERE id=?", (uid,))
        return render_template("digest_off.html", done=True)
    return render_template("digest_off.html", done=not user["digest"])


@app.route("/account/export.json")
@login_required
def account_export():
    """Own data only, no password hash / claim tokens — SPEC_V3 "Data export/deletion"."""
    db = get_db()
    user = current_user()
    reg = user_registry()
    data = dict(
        user=dict(email=user["email"], name=user["name"], created_at=user["created_at"]),
        registry=None, items=[], claims=[],
    )
    if reg and not is_reg_owner(reg):
        # a helper's own data is their account and which registry they help with, not the couple's guests
        data["helping_with"] = dict(title=reg["title"], slug=reg["slug"])
        reg = None
    if reg:
        data["registry"] = {k: reg[k] for k in reg.keys() if k not in ("id", "user_id")}
        data["items"] = [dict(r) for r in db.execute(
            "SELECT * FROM registry_items WHERE registry_id=?", (reg["id"],))]
        data["claims"] = [
            {k: v for k, v in dict(r).items() if k not in ("token_hash",)}
            for r in db.execute("SELECT * FROM claims WHERE registry_id=?", (reg["id"],))]
        data["outside_gifts"] = [
            {k: v for k, v in dict(r).items() if k not in ("id", "registry_id", "created_by")}
            for r in db.execute("SELECT * FROM outside_gifts WHERE registry_id=?", (reg["id"],))]
        data["brachos"] = [
            {k: r[k] for k in ("guest_name", "message", "lang", "created_at")}
            for r in db.execute("SELECT * FROM brachos WHERE registry_id=?", (reg["id"],))]
    resp = app.response_class(json.dumps(data, indent=2, default=str), mimetype="application/json")
    resp.headers["Content-Disposition"] = "attachment; filename=ourbayis-data.json"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/account/delete", methods=["POST"])
@login_required
def account_delete():
    """Deletes the registry (+ items + claims, via ON DELETE CASCADE) and the
    user row. Retention decision (documented in PROJECT_KNOWLEDGE.md): mail_outbox
    rows for this address are purged; funnel_events are aggregate, no PII, kept."""
    lang = current_lang()
    user = current_user()
    pw = request.form.get("current_password") or ""
    if not check_password_hash(user["pw_hash"], pw):
        flash(_t("reauth_required", lang), "err")
        return redirect(url_for("account"))
    db = get_db()
    with ob_db.write_txn(db):
        db.execute("DELETE FROM mail_outbox WHERE to_addr=?", (user["email"],))
        db.execute("DELETE FROM users WHERE id=?", (user["id"],))
    _fresh_session()
    flash(_t("account_deleted", lang), "ok")
    return redirect(url_for("index"))




# ---------------------------------------------------------------- shana rishonah
@app.route("/shana-rishonah", methods=["GET", "POST"])
def shana():
    db = get_db()
    if request.method == "POST":
        if rate_limited("shana", limit=5, per=3600):
            abort(429)
        if is_spam():
            return redirect(url_for("shana"))
        lang = current_lang()
        f = request.form
        name = (f.get("name") or "").strip()[:120]
        email = (f.get("email") or "").strip()[:200]
        whatsapp_digits = re.sub(r"\D", "", f.get("whatsapp") or "")
        has_contact = ob_security.valid_email(email) or len(whatsapp_digits) >= 8
        if not name or not has_contact:
            flash(_t("shana_contact_required", lang) if name else _t("form_error", lang), "err")
        else:
            bundle = db.execute("SELECT slug, tier FROM bundles WHERE slug=? AND active=1",
                                (f.get("bundle") or "",)).fetchone()
            bundle_slug = bundle["slug"] if bundle else "custom"
            lead_weeks = PACKAGE_TIERS.get(bundle["tier"] if bundle else "basic", PACKAGE_TIERS["basic"])["lead_weeks"]
            try:
                arrival = datetime.strptime((f.get("arrival") or "").strip(), "%Y-%m-%d").date()
                days_left = (arrival - datetime.now(timezone.utc).date()).days
            except ValueError:
                days_left = None
            # sooner than the package's planning lead time (a past date may just mean "already here")
            rush = days_left is not None and 0 <= days_left < lead_weeks * 7
            wanted_list = ""
            if f.get("with_list"):
                # prices and names are re-read from the catalog now; the owner reads English
                items = _shana_list_items(db)
                if items:
                    wanted_list = "\n".join(
                        f"{r['name']} — ₪{r['price_nis'] or 0:,} ({r['store'] or 'store'})" for r in items
                    ) + f"\nTotal at store prices: ₪{sum(r['price_nis'] or 0 for r in items):,}" \
                        f"\nItems: {len(items)}"
            db.execute(
                "INSERT INTO shana_requests (name, email, whatsapp, arrival, city, neighborhood,"
                " furnishing, budget, bundle_slug, notes, lang, wanted_list) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, email, (f.get("whatsapp") or "").strip()[:40],
                 (f.get("arrival") or "").strip()[:40],
                 (f.get("city") or "").strip()[:120],
                 (f.get("neighborhood") or "").strip()[:120],
                 f.get("furnishing") if f.get("furnishing") in
                     ("unknown", "empty", "partly", "furnished") else "unknown",
                 f.get("budget") if f.get("budget") in SHANA_BUDGETS else "",
                 bundle_slug,
                 (f.get("notes") or "").strip()[:2000], lang, wanted_list))
            send_mail(
                NOTIFY_EMAIL,
                f"{'[RUSH] ' if rush else ''}New shana rishonah lead: {name} ({bundle_slug})",
                f"Name: {name}\nWhatsApp: {f.get('whatsapp', '')}\nEmail: {email}\n"
                f"Arrival: {f.get('arrival', '')}"
                + (f" — {days_left} days away (package lead time {lead_weeks} weeks)" if rush else "")
                + f"\nCity: {f.get('city', '')}\n"
                f"Neighborhood: {f.get('neighborhood', '')}\nFurnishing: {f.get('furnishing', '')}\n"
                f"Budget: {budget_label(f.get('budget'))}\nBundle: {bundle_slug}\n"
                f"Notes: {f.get('notes', '')}\n"
                + (f"\nList from the cost calculator:\n{wanted_list}\n" if wanted_list else "")
                + f"\nAdmin: {ext_url('admin_home')}",
                reply_to=email)
            if f.get("with_list"):
                session.pop("shana_list", None)
            track("concierge_inquiry")
            flash(_t("sr_done_t", lang) + " " + _t("sr_done_b", lang), "ok")
            if rush:
                flash(tf("sr_rush_note_today" if days_left == 0 else "sr_rush_note", lang,
                         n=days_left, weeks=lead_weeks), "ok")
            return redirect(url_for("shana"))
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    # a rejected POST re-renders with what was typed (up to 2000 chars of notes) instead of blanking it
    list_items = _shana_list_items(db)
    return render_template("shana.html", bundles=bundles, package_tiers=PACKAGE_TIERS,
                           shana_budgets=SHANA_BUDGETS, list_items=list_items,
                           list_total=sum(r["price_nis"] or 0 for r in list_items),
                           form=request.form if request.method == "POST" else _shana_prefill())


# Shana Rishonah package definition, per tier (review 2026-09-15). The goods
# list lives in `bundles.items_text` (admin-editable); these are the service
# terms that differ between tiers and must stay consistent between the cards,
# the shared terms panel and the lead-time guidance. Values map to i18n keys
# pkg_delivery_<delivery>, pkg_setup_yes/no, pkg_appliances_<appliances>,
# Shana Rishonah budget bands, in order. Bands reach past the top package's starting price
# (The Full Nest, from ₪17,900) so those leads don't all land in one "10,000+" bucket.
# "10000_plus" is the pre-2026-10 top band: no longer offered, still labelled for old leads.
SHANA_BUDGETS = ("under_3000", "3000_6000", "6000_10000", "10000_20000", "20000_plus", "not_sure")


def budget_label(key):
    """English label for a stored budget key (admin + lead email); the raw value if unknown."""
    return _t("budget_" + key, "en") if key in SHANA_BUDGETS + ("10000_plus",) else (key or "—")


def bundle_label(slug):
    """A lead's package by its English name (admin); "custom" = the "not sure yet" choice."""
    row = get_db().execute("SELECT name FROM bundles WHERE slug=?", (slug or "",)).fetchone()
    return row["name"] if row else "Custom / not sure"


app.jinja_env.globals.update(budget_label=budget_label, bundle_label=bundle_label, room_of=room_of,
                             hdate_form=hdate_form, hnumeral=ob_hebcal.numeral,
                             is_reg_owner=is_reg_owner, registry_owner_name=registry_owner_name)


# pkg_lead_weeks. Owner decision 2026-09-22: Full Nest's price includes standard
# installation of the washer/fridge/microwave (existing hookups); other
# installation, and new plumbing/electrical work, is quoted per item.
PACKAGE_TIERS = {
    "basic": dict(delivery="before", setup=False, appliances="none", lead_weeks=3),
    "standard": dict(delivery="before", setup=False, appliances="ask", lead_weeks=3),
    "premium": dict(delivery="received", setup=True, appliances="included", lead_weeks=6),
}


# ---------------------------------------------------------------- admin
_DUMMY_PW_HASH = generate_password_hash("not-a-real-admin-password")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    db = get_db()
    n_admins = db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if request.method == "POST":
        if rate_limited("admin_login", limit=10, per=600):
            abort(429)
        row = db.execute("SELECT * FROM admins WHERE username=?",
                         ((request.form.get("username") or "").strip(),)).fetchone()
        # hash-check even for an unknown username so response time doesn't reveal which exist
        ok = check_password_hash(row["pw_hash"] if row else _DUMMY_PW_HASH,
                                 request.form.get("password") or "")
        if row and ok:
            session.clear()
            session["admin"] = row["username"]
            session["admin_sv"] = row["session_ver"]
            session["admin_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
            return redirect(url_for("admin_home"))
        flash("Wrong credentials", "err")
    return render_template("admin_login.html", no_admins=(n_admins == 0))


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_home():
    db = get_db()
    today = date.today().isoformat()
    # due follow-ups first, then new leads, then everything else still open, closed ones last
    leads = sorted(
        db.execute("SELECT * FROM shana_requests ORDER BY created_at DESC LIMIT 200").fetchall(),
        key=lambda l: (not _lead_due(l, today), l["status"] != "new",
                       l["status"] in LEAD_CLOSED))[:50]
    msgs = db.execute("SELECT * FROM messages ORDER BY resolved, created_at DESC LIMIT 50").fetchall()
    stats = dict(
        registries=db.execute("SELECT COUNT(*) FROM registries").fetchone()[0],
        users=db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        claims=db.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        leads_new=db.execute("SELECT COUNT(*) FROM shana_requests WHERE status='new'").fetchone()[0],
        catalog=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1").fetchone()[0],
        missing_store_link=db.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE active=1 AND url=''").fetchone()[0],
    )
    today = date.today().isoformat()
    stats["followups_due"] = sum(1 for l in leads if _lead_due(l, today))
    recent = db.execute("SELECT * FROM registries ORDER BY created_at DESC LIMIT 15").fetchall()
    mail_stats = ob_mail.outbox_counts(db)
    since = (date.today() - timedelta(days=30)).isoformat()
    funnel = db.execute(
        "SELECT name, SUM(n) AS n FROM funnel_events WHERE day>=? GROUP BY name ORDER BY n DESC",
        (since,)).fetchall()
    return render_template("admin.html", leads=leads, msgs=msgs, stats=stats, recent=recent,
                           mail_stats=mail_stats, funnel=funnel, today=today,
                           lead_closed=LEAD_CLOSED, lead_statuses=LEAD_STATUSES)


def _lead_due(lead, today):
    """Open lead whose next-action date has arrived (ISO dates compare as strings)."""
    return bool(lead["next_action_date"]) and lead["next_action_date"][:10] <= today \
        and lead["status"] not in LEAD_CLOSED


@app.route("/admin/leads.csv")
@admin_required
def admin_leads_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "whatsapp", "arrival", "city", "address",
               "bundle", "notes", "status", "created_at"])
    for r in get_db().execute("SELECT * FROM shana_requests ORDER BY created_at DESC"):
        w.writerow([csv_safe(r["id"]), csv_safe(r["name"]), csv_safe(r["email"]),
                   csv_safe(r["whatsapp"]), csv_safe(r["arrival"]), csv_safe(r["city"]),
                   csv_safe(r["address"]), csv_safe(r["bundle_slug"]), csv_safe(r["notes"]),
                   csv_safe(r["status"]), csv_safe(r["created_at"])])
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=shana-leads.csv"
    resp.headers["Cache-Control"] = "no-store"
    return resp


LEAD_STATUSES = ("new", "contacted", "quoted", "accepted", "arranging", "completed", "cancelled")
LEAD_CLOSED = ("completed", "cancelled")


@app.route("/admin/lead/<int:lead_id>/status", methods=["POST"])
@admin_required
def admin_lead_status(lead_id):
    status = request.form.get("status", "new")
    if status in LEAD_STATUSES:
        get_db().execute("UPDATE shana_requests SET status=? WHERE id=?", (status, lead_id))
    return redirect(ob_security.same_origin_referrer() or url_for("admin_home"))


@app.route("/admin/lead/<int:lead_id>")
@admin_required
def admin_lead(lead_id):
    db = get_db()
    lead = db.execute("SELECT * FROM shana_requests WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        abort(404)
    dupes = []
    if lead["email"] or lead["whatsapp"]:
        clauses, params = [], []
        if lead["email"]:
            clauses.append("email=?")
            params.append(lead["email"])
        if lead["whatsapp"]:
            clauses.append("whatsapp=?")
            params.append(lead["whatsapp"])
        dupes = db.execute(
            f"SELECT * FROM shana_requests WHERE id!=? AND ({' OR '.join(clauses)})"
            " ORDER BY created_at DESC", [lead_id] + params).fetchall()
    try:
        quote = json.loads(lead["quote_json"] or "{}")
    except (ValueError, TypeError):
        quote = {}
    return render_template("admin_lead.html", lead=lead, dupes=dupes, quote=quote, budget_label=budget_label,
                           statuses=LEAD_STATUSES, reply=_lead_first_reply(db, lead))


def _lead_first_reply(db, lead):
    """(subject, text) for the owner's first message to a lead — in the language they wrote in,
    naming their package, arrival date and city so it doesn't read like a form letter."""
    lang = lead["lang"] if lead["lang"] in ("en", "he") else "en"
    b = db.execute("SELECT name, name_he FROM bundles WHERE slug=?", (lead["bundle_slug"] or "",)).fetchone()
    details = [(b["name_he"] if lang == "he" and b["name_he"] else b["name"]) if b else _t("lead_reply_custom", lang)]
    if lead["arrival"]:
        details.append(tf("lead_reply_arrival", lang, date=format_date(lead["arrival"], lang)))
    if lead["city"]:
        details.append(lead["city"])
    text = tf("lead_reply_body", lang, name=(lead["name"] or "").split(" ")[0] or lead["name"],
              details=", ".join(details))
    return _t("lead_reply_subj", lang), text


@app.route("/admin/lead/<int:lead_id>/update", methods=["POST"])
@admin_required
def admin_lead_update(lead_id):
    """Internal notes, next action + date, and the cost-breakdown editor
    (goods/delivery/assembly/labour/contingency/quoted_price -> total cost,
    profit, margin % computed server-side and stored in quote_json)."""
    db = get_db()
    lead = db.execute("SELECT * FROM shana_requests WHERE id=?", (lead_id,)).fetchone()
    if not lead:
        abort(404)
    f = request.form
    cost_fields = ("goods", "delivery", "assembly", "labour", "contingency", "quoted_price")

    def _num(key):
        try:
            return max(0.0, float(f.get(key) or 0))
        except ValueError:
            return 0.0
    quote = {k: _num(k) for k in cost_fields}
    total_cost = quote["goods"] + quote["delivery"] + quote["assembly"] + quote["labour"] + quote["contingency"]
    quote["total_cost"] = round(total_cost, 2)
    quote["profit"] = round(quote["quoted_price"] - total_cost, 2)
    quote["margin_pct"] = round((quote["profit"] / quote["quoted_price"]) * 100, 1) if quote["quoted_price"] else 0
    quote["needs_reconfirmation"] = request.form.getlist("needs_reconfirmation")
    status = f.get("status", lead["status"])
    if status not in LEAD_STATUSES:
        status = lead["status"]
    db.execute(
        "UPDATE shana_requests SET status=?, notes_internal=?, next_action=?, next_action_date=?,"
        " quote_json=? WHERE id=?",
        (status, (f.get("notes_internal") or "").strip()[:4000],
         (f.get("next_action") or "").strip()[:200], (f.get("next_action_date") or "").strip()[:20],
         json.dumps(quote), lead_id))
    flash("Lead updated", "ok")
    return redirect(url_for("admin_lead", lead_id=lead_id))


@app.route("/admin/message/<int:msg_id>/resolve", methods=["POST"])
@admin_required
def admin_msg_resolve(msg_id):
    get_db().execute("UPDATE messages SET resolved=1 WHERE id=?", (msg_id,))
    return redirect(url_for("admin_home"))


# a "Price checked <date>" tag older than this is due for a re-check (admin queue + manage.py check)
PRICE_RECHECK_DAYS = 30
STALE_PRICE_SQL = ("price_status='verified' AND (price_checked_at IS NULL OR price_checked_at=''"
                   f" OR date(substr(price_checked_at, 1, 10)) < date('now', '-{PRICE_RECHECK_DAYS} days'))")


@app.route("/admin/catalog")
@admin_required
def admin_catalog():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    cat = request.args.get("cat", "")
    missing_url = request.args.get("missing_url")
    missing_image = request.args.get("missing_image")
    price_status = request.args.get("price_status", "")
    show_inactive = request.args.get("inactive")
    stale = request.args.get("stale")
    sql = "SELECT * FROM catalog_items WHERE 1=1"
    params = []
    if not show_inactive:
        sql += " AND active=1"
    if q:
        sql += " AND (name LIKE ? OR name_he LIKE ? OR seed_key LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if cat in CATEGORIES:
        sql += " AND category=?"
        params.append(cat)
    if missing_url:
        sql += " AND url=''"
    if missing_image:
        sql += " AND image=''"
    if stale:
        sql += " AND " + STALE_PRICE_SQL
    if price_status in ("verified", "estimate", "unknown"):
        sql += " AND price_status=?"
        params.append(price_status)
    rows = db.execute(sql + " ORDER BY category, sort", params).fetchall()
    queue_counts = dict(
        missing_url=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND url=''").fetchone()[0],
        missing_image=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND image=''").fetchone()[0],
        unverified=db.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE active=1 AND price_status!='verified'").fetchone()[0],
        stale=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND " + STALE_PRICE_SQL).fetchone()[0],
    )
    return render_template("admin_catalog.html", rows=rows, q=q, cat=cat, price_status=price_status,
                           missing_url=missing_url, missing_image=missing_image, stale=stale,
                           recheck_days=PRICE_RECHECK_DAYS,
                           show_inactive=show_inactive, queue_counts=queue_counts)


CATALOG_PRICE_STATUSES = ("verified", "estimate", "unknown")
CATALOG_KINDS = ("product", "idea")
CATALOG_AVAILABILITY = ("unknown", "in_stock", "backorder", "discontinued")


def _catalog_form_values(f):
    """Shared parse+validate for the catalog admin add/edit form. Returns
    (values_tuple, errors_list)."""
    errors = []
    try:
        price = max(0, int(f.get("price_nis") or 0))
    except ValueError:
        price = 0
        errors.append("Price must be a number")
    url = (f.get("url") or "").strip()[:500]
    if url and not url.startswith("http"):
        url = "https://" + url
    if url and not valid_http_url(url):
        errors.append("That store link doesn't look like a valid http(s) URL")
    image = (f.get("image") or "").strip()[:500]
    if image and not image.startswith("http"):
        image = "https://" + image
    if image and not valid_http_url(image):
        errors.append("That image link doesn't look like a valid http(s) URL")
    vals = ((f.get("name") or "").strip()[:200], (f.get("name_he") or "").strip()[:200],
            (f.get("brand") or "").strip()[:80],
            f.get("category") if f.get("category") in CATEGORIES else "home",
            price, (f.get("store") or "").strip()[:120], url, image,
            1 if f.get("active") else 0, 1 if f.get("featured") else 0,
            int(f.get("sort") or 0),
            f.get("kind") if f.get("kind") in CATALOG_KINDS else "product",
            (f.get("model") or "").strip()[:120], (f.get("variant") or "").strip()[:120],
            (f.get("image_credit") or "").strip()[:200],
            f.get("price_status") if f.get("price_status") in CATALOG_PRICE_STATUSES else "estimate",
            (f.get("price_checked_at") or "").strip()[:20], (f.get("price_source") or "").strip()[:200],
            f.get("availability") if f.get("availability") in CATALOG_AVAILABILITY else "unknown",
            (f.get("notes") or "").strip()[:1000], (f.get("notes_he") or "").strip()[:1000],
            f.get("starter_group") or "", (f.get("model_he") or "").strip()[:160])
    if not vals[0]:
        errors.append("Name is required")
    return vals, errors


@app.route("/admin/catalog/new", methods=["GET", "POST"])
@app.route("/admin/catalog/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_catalog_edit(item_id=None):
    db = get_db()
    row = db.execute("SELECT * FROM catalog_items WHERE id=?", (item_id,)).fetchone() if item_id else None
    if item_id and not row:
        abort(404)
    n_registry_refs = db.execute(
        "SELECT COUNT(*) FROM registry_items WHERE catalog_id=?", (item_id or -1,)).fetchone()[0]
    if request.method == "POST":
        vals, errors = _catalog_form_values(request.form)
        for e in errors:
            flash(e, "err")
        if errors:
            pass
        elif row:
            db.execute(
                "UPDATE catalog_items SET name=?, name_he=?, brand=?, category=?, price_nis=?,"
                " store=?, url=?, image=?, active=?, featured=?, sort=?, kind=?, model=?, variant=?,"
                " image_credit=?, price_status=?, price_checked_at=?, price_source=?, availability=?,"
                " notes=?, notes_he=?, starter_group=?, model_he=?, updated_at=? WHERE id=?",
                vals + (datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"), item_id))
            if n_registry_refs:
                flash("Changes here don't rewrite gifts already copied to registries — "
                      "run `manage.py refresh-registry-links` to push url/image/store/brand out.", "ok")
            return redirect(url_for("admin_catalog"))
        else:
            db.execute(
                "INSERT INTO catalog_items (name, name_he, brand, category, price_nis, store, url,"
                " image, active, featured, sort, kind, model, variant, image_credit, price_status,"
                " price_checked_at, price_source, availability, notes, notes_he, starter_group, model_he, seed_key)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals + (None,))
            return redirect(url_for("admin_catalog"))
    return render_template("admin_catalog_form.html", row=row, n_registry_refs=n_registry_refs)


@app.route("/admin/catalog/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_catalog_delete(item_id):
    """"Retire" — soft-delete (active=0) unless nothing references it, in
    which case a hard delete is safe."""
    db = get_db()
    n_refs = db.execute("SELECT COUNT(*) FROM registry_items WHERE catalog_id=?", (item_id,)).fetchone()[0]
    if n_refs:
        db.execute("UPDATE catalog_items SET active=0 WHERE id=?", (item_id,))
    else:
        db.execute("DELETE FROM catalog_items WHERE id=?", (item_id,))
    return redirect(url_for("admin_catalog"))


@app.route("/admin/catalog.csv")
@admin_required
def admin_catalog_csv():
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ("seed_key", "id", "name", "name_he", "brand", "category", "price_nis", "store", "url",
           "image", "kind", "active", "featured", "sort", "price_status", "price_checked_at",
           "price_source", "starter_group")
    w.writerow(cols)
    for r in get_db().execute("SELECT * FROM catalog_items ORDER BY category, sort"):
        w.writerow([csv_safe(r[c]) for c in cols])
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=catalog.csv"
    resp.headers["Cache-Control"] = "no-store"
    return resp


_CSV_IMPORT_FIELDS = ("name", "name_he", "brand", "category", "price_nis", "store", "url", "image",
                      "kind", "active", "featured", "sort", "price_status", "price_checked_at",
                      "price_source", "starter_group")


@app.route("/admin/catalog/import", methods=["GET", "POST"])
@admin_required
def admin_catalog_import():
    """CSV import matched by seed_key (falls back to id). Always shows a
    dry-run diff first; only writes on a second POST with mode=apply and the
    same re-uploaded file (nothing is trusted from a hidden/session payload)."""
    if request.method != "POST":
        return render_template("admin_catalog_import.html", diffs=None)
    db = get_db()
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a CSV file", "err")
        return render_template("admin_catalog_import.html", diffs=None)
    mode = request.form.get("mode", "preview")
    text = file.stream.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    diffs, errors = _catalog_csv_diff(db, reader, write=(mode == "apply"))
    if mode == "apply":
        flash(f"Applied {len(diffs)} field change(s).", "ok")
        return redirect(url_for("admin_catalog"))
    return render_template("admin_catalog_import.html", diffs=diffs, errors=errors,
                           filename=file.filename)


def _catalog_csv_diff(db, reader, write):
    """Parse+validate a catalog CSV against the DB by seed_key (falls back to
    id). Always computes the full diff; only writes when `write` is True —
    keeps the dry-run path free of any transaction/rollback trickery."""
    diffs, errors = [], []

    def _apply(rows):
        for i, row, existing, sets, params in rows:
            if sets:
                db.execute(f"UPDATE catalog_items SET {', '.join(sets)} WHERE id=?",
                          params + [existing["id"]])

    pending = []
    for i, row in enumerate(reader, start=2):
        key = (row.get("seed_key") or "").strip()
        rid = (row.get("id") or "").strip()
        existing = None
        if key:
            existing = db.execute("SELECT * FROM catalog_items WHERE seed_key=?", (key,)).fetchone()
        elif rid:
            existing = db.execute("SELECT * FROM catalog_items WHERE id=?", (rid,)).fetchone()
        if not existing:
            errors.append(f"Row {i}: no match for seed_key={key!r} id={rid!r}")
            continue
        url = (row.get("url") or "").strip()
        if url and not valid_http_url(url):
            errors.append(f"Row {i} ({existing['name']}): invalid url {url!r}")
            continue
        sets, params = [], []
        for field in _CSV_IMPORT_FIELDS:
            if field not in row:
                continue
            new_val = row[field]
            if field in ("price_nis", "sort"):
                try:
                    new_val = int(new_val or 0)
                except ValueError:
                    continue
                if field == "price_nis" and new_val < 0:
                    errors.append(f"Row {i} ({existing['name']}): negative price {new_val} skipped")
                    continue
            elif field in ("active", "featured"):
                new_val = 1 if str(new_val).strip() in ("1", "true", "True") else 0
            old_val = existing[field] if field in existing.keys() else None
            if old_val != new_val:
                diffs.append((existing["id"], existing["name"], field, old_val, new_val))
                sets.append(f"{field}=?")
                params.append(new_val)
        pending.append((i, row, existing, sets, params))
    if write:
        with ob_db.write_txn(db):
            _apply(pending)
    return diffs, errors


@app.route("/admin/bundles")
@admin_required
def admin_bundles():
    rows = get_db().execute("SELECT * FROM bundles ORDER BY sort").fetchall()
    return render_template("admin_bundles.html", rows=rows)


@app.route("/admin/bundles/new", methods=["GET", "POST"])
@app.route("/admin/bundles/<int:bundle_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_bundle_edit(bundle_id=None):
    db = get_db()
    row = db.execute("SELECT * FROM bundles WHERE id=?", (bundle_id,)).fetchone() if bundle_id else None
    if bundle_id and not row:
        abort(404)
    if request.method == "POST":
        f = request.form
        try:
            price = max(0, int(f.get("price_from") or 0))
        except ValueError:
            price = 0
        vals = ((f.get("name") or "").strip()[:160], (f.get("name_he") or "").strip()[:160],
                (f.get("tier") or "basic")[:20], price,
                (f.get("description") or "").strip()[:2000],
                (f.get("description_he") or "").strip()[:2000],
                (f.get("items_text") or "").strip()[:4000],
                (f.get("items_text_he") or "").strip()[:4000],
                1 if f.get("active") else 0, int(f.get("sort") or 0))
        if not vals[0]:
            flash("Name is required", "err")
        elif row:
            db.execute("UPDATE bundles SET name=?, name_he=?, tier=?, price_from=?,"
                       " description=?, description_he=?, items_text=?, items_text_he=?,"
                       " active=?, sort=? WHERE id=?", vals + (bundle_id,))
            return redirect(url_for("admin_bundles"))
        else:
            slug = slugify(vals[0])
            db.execute("INSERT INTO bundles (slug, name, name_he, tier, price_from, description,"
                       " description_he, items_text, items_text_he, active, sort)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?,?)", (slug,) + vals)
            return redirect(url_for("admin_bundles"))
    return render_template("admin_bundle_form.html", row=row)


@app.route("/admin/ads", methods=["GET", "POST"])
@admin_required
def admin_ads():
    db = get_db()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()[:200]
        urls = {}
        for field in ("link_url", "image"):
            u = (request.form.get(field) or "").strip()[:500]
            if u and not u.startswith(("http://", "https://")):
                u = "https://" + u  # "example.com" would otherwise be a link into our own site
            if u and not valid_http_url(u):
                flash(f"That {'link' if field == 'link_url' else 'image'} URL doesn't look valid"
                      " — the ad was not saved.", "err")
                return redirect(url_for("admin_ads"))
            urls[field] = u
        if title:
            db.execute("INSERT INTO ads (title, body, image, link_url) VALUES (?,?,?,?)",
                       (title, (request.form.get("body") or "").strip()[:500],
                        urls["image"], urls["link_url"]))
        return redirect(url_for("admin_ads"))
    rows = db.execute("SELECT * FROM ads ORDER BY created_at DESC").fetchall()
    return render_template("admin_ads.html", rows=rows)


@app.route("/admin/ads/<int:ad_id>/toggle", methods=["POST"])
@admin_required
def admin_ad_toggle(ad_id):
    get_db().execute("UPDATE ads SET active = 1 - active WHERE id=?", (ad_id,))
    return redirect(url_for("admin_ads"))


@app.route("/admin/ads/<int:ad_id>/delete", methods=["POST"])
@admin_required
def admin_ad_delete(ad_id):
    get_db().execute("DELETE FROM ads WHERE id=?", (ad_id,))
    return redirect(url_for("admin_ads"))


def _outbound_click_hosts(db):
    """Outbound store clicks grouped by destination hostname (catalog + registry
    items), each with the affiliate rule that covers it, if any."""
    rules = db.execute("SELECT * FROM affiliate_rules ORDER BY active DESC, id").fetchall()
    totals = {}
    for table in ("catalog_items", "registry_items"):
        for r in db.execute(f"SELECT url, clicks FROM {table} WHERE url != '' AND clicks > 0"):
            try:
                host = (urlsplit(r["url"]).hostname or "").lower()
            except ValueError:
                continue
            if host.startswith("www."):
                host = host[4:]
            if host:
                totals[host] = totals.get(host, 0) + (r["clicks"] or 0)
    out = []
    for host, n in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        rule = next((x for x in rules if ob_affiliate.host_matches(host, x["host"])), None)
        out.append(dict(host=host, clicks=n, rule=rule))
    return out


def _render_affiliates(test_url="", test_result=None):
    db = get_db()
    rows = db.execute("SELECT * FROM affiliate_rules ORDER BY active DESC, host").fetchall()
    return render_template("admin_affiliates.html", rows=rows, hosts=_outbound_click_hosts(db),
                           test_url=test_url, test_result=test_result)


def _affiliate_direct(kind):
    """The "Link directly" checkbox; only a 'param' rule can be linked directly."""
    return 1 if kind == "param" and request.form.get("direct") else 0


def _affiliate_form_values():
    return ob_affiliate.validate_rule(request.form.get("host"), request.form.get("kind"),
                                      request.form.get("param"), request.form.get("value"))


@app.route("/admin/affiliates", methods=["GET", "POST"])
@admin_required
def admin_affiliates():
    if request.method == "POST":
        db = get_db()
        try:
            host, kind, param, value = _affiliate_form_values()
        except ValueError as e:
            flash(f"Rule not saved: {e}", "err")
            return redirect(url_for("admin_affiliates"))
        label = (request.form.get("label") or "").strip()[:80]
        if db.execute("SELECT 1 FROM affiliate_rules WHERE host=?", (host,)).fetchone():
            flash(f"There is already a rule for {host}: edit it instead.", "err")
        else:
            db.execute("INSERT INTO affiliate_rules (host, kind, param, value, label, direct) VALUES (?,?,?,?,?,?)",
                       (host, kind, param, value, label, _affiliate_direct(kind)))
            flash("Rule added.", "ok")
        return redirect(url_for("admin_affiliates"))
    return _render_affiliates()


@app.route("/admin/affiliates/test", methods=["POST"])
@admin_required
def admin_affiliates_test():
    u = (request.form.get("test_url") or "").strip()[:500]
    if u and not u.startswith(("http://", "https://")):
        u = "https://" + u
    result = None
    if u:
        if not valid_http_url(u):
            result = dict(error="That doesn't look like a valid store URL.")
        else:
            rules = get_db().execute("SELECT * FROM affiliate_rules WHERE active=1").fetchall()
            final, rule_id = ob_affiliate.tag_url(u, rules)
            if rule_id is not None and not valid_http_url(final):
                result = dict(error="The tagged URL would be invalid, so visitors get the plain link.")
            else:
                rule = next((r for r in rules if r["id"] == rule_id), None)
                result = dict(final=final, rule=rule)
    return _render_affiliates(test_url=u, test_result=result)


@app.route("/admin/affiliates/<int:rule_id>/edit", methods=["POST"])
@admin_required
def admin_affiliate_edit(rule_id):
    db = get_db()
    try:
        host, kind, param, value = _affiliate_form_values()
    except ValueError as e:
        flash(f"Rule not saved: {e}", "err")
        return redirect(url_for("admin_affiliates"))
    if db.execute("SELECT 1 FROM affiliate_rules WHERE host=? AND id!=?", (host, rule_id)).fetchone():
        flash(f"There is already a rule for {host}.", "err")
        return redirect(url_for("admin_affiliates"))
    db.execute("UPDATE affiliate_rules SET host=?, kind=?, param=?, value=?, label=?, direct=? WHERE id=?",
               (host, kind, param, value, (request.form.get("label") or "").strip()[:80],
                _affiliate_direct(kind), rule_id))
    flash("Rule saved.", "ok")
    return redirect(url_for("admin_affiliates"))


@app.route("/admin/affiliates/<int:rule_id>/toggle", methods=["POST"])
@admin_required
def admin_affiliate_toggle(rule_id):
    get_db().execute("UPDATE affiliate_rules SET active = 1 - active WHERE id=?", (rule_id,))
    return redirect(url_for("admin_affiliates"))


@app.route("/admin/affiliates/<int:rule_id>/delete", methods=["POST"])
@admin_required
def admin_affiliate_delete(rule_id):
    get_db().execute("DELETE FROM affiliate_rules WHERE id=?", (rule_id,))
    return redirect(url_for("admin_affiliates"))


# ---------------------------------------------------------------- admin insights (read-only business view)
INSIGHT_ENDPOINT_NAMES = {
    "index": "Home", "catalog_page": "Catalog", "registry": "Registry pages (guest view)",
    "sample": "Sample registry", "shana": "Shana Rishonah", "how": "How it works", "about": "About",
    "find": "Find a registry", "advertise": "Advertise", "privacy": "Privacy", "terms": "Terms",
    "contact": "Contact", "guides": "Guides index", "guide": "Guide articles",
    "gift_ideas": "Gift ideas", "catalog_item": "Item pages", "gift_category": "Category pages",
    "setup_cost": "Setup cost calculator",
}


def insights_days(raw):
    """?days= value -> 7, 30, 90 or None (all time); anything else is 30."""
    raw = (raw or "").strip().lower()
    if raw == "all":
        return None
    return int(raw) if raw in ("7", "30", "90") else 30


def _pct(part, whole):
    """Whole-number percentage, or None when there is nothing to divide by."""
    return round(part * 100 / whole) if whole else None


def insights_data(db, days=30, today=None):
    """Everything the /admin/insights page and `manage.py insights` show. Needs only a DB handle
    (no request). days=None means all time (no previous-period figures). Daily funnel_events
    are compared with the equally long period before; table counts use created_at."""
    today = today or datetime.now(timezone.utc).date()
    since = (today - timedelta(days=days - 1)).isoformat() if days else ""
    prev_since = (today - timedelta(days=2 * days - 1)).isoformat() if days else None
    d = dict(days=days, since=since, today=today.isoformat())

    def ev(names, lo, hi=None):
        sql = f"SELECT COALESCE(SUM(n),0) FROM funnel_events WHERE name IN ({','.join('?' * len(names))})"
        args = list(names)
        if lo:
            sql += " AND day>=?"
            args.append(lo)
        if hi:
            sql += " AND day<?"
            args.append(hi)
        return db.execute(sql, args).fetchone()[0]

    def pair(*names):
        """(this period, previous period or None)"""
        return ev(names, since), (ev(names, prev_since, since) if days else None)

    def views(lo, hi=None):
        sql = "SELECT name, SUM(n) AS n FROM funnel_events WHERE name LIKE 'view:%'"
        args = []
        if lo:
            sql += " AND day>=?"
            args.append(lo)
        if hi:
            sql += " AND day<?"
            args.append(hi)
        return {r["name"][5:]: r["n"] for r in db.execute(sql + " GROUP BY name", args)}

    def made(table, extra=""):
        sql = f"SELECT COUNT(*) FROM {table} WHERE substr(created_at,1,10)>=?{extra}"
        return db.execute(sql, (since,)).fetchone()[0]

    # 1. visitors and pages
    cur_v = views(since)
    prev_v = views(prev_since, since) if days else {}
    d["views_total"] = sum(cur_v.values())
    d["views_prev"] = sum(prev_v.values()) if days else None
    d["top_pages"] = [dict(name=INSIGHT_ENDPOINT_NAMES.get(k, k), n=n, prev=(prev_v.get(k, 0) if days else None))
                      for k, n in sorted(cur_v.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]
    d["key_pages"] = [dict(name=INSIGHT_ENDPOINT_NAMES[k], n=cur_v.get(k, 0), prev=(prev_v.get(k, 0) if days else None))
                      for k in ("setup_cost", "gift_ideas", "guides", "guide", "catalog_item", "gift_category")]

    # 2. couples funnel (cohorts by created_at, each step a subset of the one before)
    regs = db.execute(
        "SELECT r.id, (r.views>0 OR COALESCE(r.preferences_json,'') LIKE '%\"shared_at\"%') AS shared,"
        " (SELECT COUNT(*) FROM registry_items i WHERE i.registry_id=r.id AND i.archived=0) AS n_items,"
        " EXISTS(SELECT 1 FROM claims c WHERE c.registry_id=r.id AND c.status!='cancelled') AS has_claim"
        " FROM registries r WHERE substr(r.created_at,1,10)>=?", (since,)).fetchall()
    five = [r for r in regs if r["n_items"] >= 5]
    shared = [r for r in five if r["shared"]]
    reserved = [r for r in shared if r["has_claim"]]
    steps = [("Signed up", made("users"), pair("signup")),
             ("Created a registry", len(regs), pair("registry_created")),
             ("Has 5+ gifts", len(five), pair("first_gifts")),
             ("Shared it", len(shared), pair("share_click")),
             ("Got a first reservation", len(reserved), pair("reservation"))]
    d["funnel"] = [dict(label=label, n=n, pct=(_pct(n, steps[i - 1][1]) if i else None), ev=e[0], ev_prev=e[1])
                   for i, (label, n, e) in enumerate(steps)]

    # 3. guests
    live = "status IN ('reserved','reported','received')"
    cl = {}
    for kind in ("item", "cash", "chip"):
        row = db.execute(
            f"SELECT COUNT(*) AS n,"
            f" COALESCE(SUM(CASE WHEN status='reserved' THEN amount_minor END),0) AS pledged,"
            f" COALESCE(SUM(CASE WHEN status='reported' THEN amount_minor END),0) AS reported,"
            f" COALESCE(SUM(CASE WHEN status='received' THEN amount_minor END),0) AS received"
            f" FROM claims WHERE kind=? AND {live} AND substr(created_at,1,10)>=?"
            f" AND COALESCE(currency,'ILS')='ILS'", (kind, since)).fetchone()
        cl[kind] = dict(n=row["n"], pledged=row["pledged"] // 100, reported=row["reported"] // 100,
                        received=row["received"] // 100)
    active_regs = db.execute(
        f"SELECT COUNT(DISTINCT registry_id) FROM claims WHERE kind='item' AND {live}"
        " AND substr(created_at,1,10)>=?", (since,)).fetchone()[0]
    d["guests"] = dict(
        reservations=cl["item"]["n"], cash=cl["cash"], chip=cl["chip"], brachos=made("brachos"),
        active_registries=active_regs,
        avg_per_registry=round(cl["item"]["n"] / active_regs, 1) if active_regs else 0)

    # 4. store clicks
    hosts = _outbound_click_hosts(db)
    total_c = sum(h["clicks"] for h in hosts)
    covered = sum(h["clicks"] for h in hosts if h["rule"] is not None and h["rule"]["active"])
    top_items = db.execute(
        "SELECT id, name, clicks FROM catalog_items WHERE clicks>0 ORDER BY clicks DESC, name LIMIT 10").fetchall()
    d["clicks"] = dict(
        period=pair("handoff_click"), tagged=pair("handoff_click_tagged"),
        hosts=hosts[:10], lifetime=total_c, covered=covered, covered_pct=_pct(covered, total_c),
        top_items=[dict(id=r["id"], name=r["name"], clicks=r["clicks"]) for r in top_items])

    # 5. Shana Rishonah leads
    tiers = {r["slug"]: r["tier"] for r in db.execute("SELECT slug, tier FROM bundles")}
    leads = db.execute("SELECT * FROM shana_requests WHERE substr(created_at,1,10)>=?", (since,)).fetchall()
    by_status = {}
    rush = 0
    q_n = q_price = q_cost = q_profit = 0
    margins = []
    for l in leads:
        by_status[l["status"]] = by_status.get(l["status"], 0) + 1
        try:
            left = (datetime.strptime((l["arrival"] or "")[:10], "%Y-%m-%d").date()
                    - datetime.strptime(l["created_at"][:10], "%Y-%m-%d").date()).days
            weeks = PACKAGE_TIERS.get(tiers.get(l["bundle_slug"], "basic"), PACKAGE_TIERS["basic"])["lead_weeks"]
            rush += 1 if 0 <= left < weeks * 7 else 0
        except (ValueError, TypeError):
            pass
        try:
            q = json.loads(l["quote_json"] or "{}")
            price = float(q.get("quoted_price") or 0)
        except (ValueError, TypeError, AttributeError):
            continue
        if price > 0:
            q_n += 1
            q_price += price
            q_cost += float(q.get("total_cost") or 0)
            q_profit += float(q.get("profit") or 0)
            margins.append(float(q.get("margin_pct") or 0))
    overdue = db.execute(
        "SELECT id, name, next_action, next_action_date FROM shana_requests"
        " WHERE next_action_date!='' AND substr(next_action_date,1,10)<? AND status NOT IN ('completed','cancelled')"
        " ORDER BY next_action_date", (today.isoformat(),)).fetchall()
    d["leads"] = dict(
        total=len(leads), by_status=[(s, by_status[s]) for s in LEAD_STATUSES if s in by_status],
        rush=rush, quotes=q_n, price=round(q_price), cost=round(q_cost), profit=round(q_profit),
        avg_margin=round(sum(margins) / len(margins), 1) if margins else None,
        overdue=[dict(id=r["id"], name=r["name"], next_action=r["next_action"], date=r["next_action_date"][:10])
                 for r in overdue])

    # 6. catalog health
    def n(where):
        return db.execute(f"SELECT COUNT(*) FROM catalog_items WHERE active=1{where}").fetchone()[0]
    rules = db.execute("SELECT host FROM affiliate_rules WHERE active=1").fetchall()
    bare = set()
    for r in db.execute("SELECT url FROM catalog_items WHERE active=1 AND url!=''"):
        try:
            host = (urlsplit(r["url"]).hostname or "").lower()
        except ValueError:
            continue
        host = host[4:] if host.startswith("www.") else host
        if host and not any(ob_affiliate.host_matches(host, x["host"]) for x in rules):
            bare.add(host)
    d["catalog"] = dict(
        active=n(""), with_link=n(" AND url!=''"), verified=n(" AND price_status='verified'"),
        stale=n(" AND " + STALE_PRICE_SQL), zero_clicks=n(" AND COALESCE(clicks,0)=0"),
        hosts_without_rule=len(bare))

    # 7. mail
    counts = ob_mail.outbox_counts(db)
    d["mail"] = dict(queued=counts.get("queued", 0), failed=counts.get("failed", 0),
                     smtp=ob_mail.configured())
    return d


@app.route("/admin/insights")
@admin_required
def admin_insights():
    days = insights_days(request.args.get("days"))
    return render_template("admin_insights.html", d=insights_data(get_db(), days),
                           choice=("all" if days is None else str(days)))


@app.route("/admin/password", methods=["POST"])
@admin_required
def admin_password():
    admin_row = current_admin()
    cur_pw = request.form.get("current_password") or ""
    pw = request.form.get("password") or ""
    if not check_password_hash(admin_row["pw_hash"], cur_pw):
        flash("Current password is wrong", "err")
    elif len(pw) < 12:
        flash("Password must be at least 12 characters", "err")
    else:
        db = get_db()
        with ob_db.write_txn(db):
            db.execute("UPDATE admins SET pw_hash=?, session_ver=session_ver+1 WHERE username=?",
                      (generate_password_hash(pw), admin_row["username"]))
            session["admin_sv"] = db.execute("SELECT session_ver FROM admins WHERE username=?",
                                             (admin_row["username"],)).fetchone()[0]
        flash("Password updated", "ok")
    return redirect(url_for("admin_home"))


@app.route("/admin/outbox")
@admin_required
def admin_outbox():
    db = get_db()
    rows = db.execute("SELECT * FROM mail_outbox ORDER BY created_at DESC LIMIT 50").fetchall()
    masked = [dict(r, to_addr=_mask_email(r["to_addr"])) for r in rows]
    return render_template("admin_outbox.html", rows=masked, mail_stats=ob_mail.outbox_counts(db))


def _mask_email(addr):
    """a***@x.com — admin_outbox never shows a full address (see PROJECT_KNOWLEDGE.md)."""
    if not addr or "@" not in addr:
        return "***"
    local, _, domain = addr.partition("@")
    return (local[:1] or "*") + "***@" + domain


@app.route("/admin/outbox/<int:mail_id>/retry", methods=["POST"])
@admin_required
def admin_outbox_retry(mail_id):
    db = get_db()
    with ob_db.write_txn(db):
        db.execute(
            "UPDATE mail_outbox SET status='queued', next_attempt_at=datetime('now') WHERE id=? AND status='failed'",
            (mail_id,))
    return redirect(url_for("admin_outbox"))


@app.route("/admin/backup.db")
@admin_required
def admin_backup_download():
    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        ob_db.backup(DB_PATH, tmp_path)
        return app.response_class(
            Path(tmp_path).read_bytes(), mimetype="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=ourbayis-backup.db",
                    "Cache-Control": "no-store"})
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------- misc
@app.route("/favicon.ico")
def favicon():
    # browsers and search crawlers ask for /favicon.ico at the root regardless of <link rel=icon>
    resp = app.send_static_file("favicon.ico")
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp


@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nDisallow: /admin\nDisallow: /dashboard\nDisallow: /g/\nDisallow: /go/\n"
        f"Sitemap: {ext_url('sitemap')}\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    pages = [ext_url(p) for p in
             ("index", "how", "find", "catalog_page", "sample", "shana", "about", "contact", "privacy", "terms",
              "advertise", "guides", "gift_ideas", "setup_cost")]
    pages += [ext_url("gift_ideas", band=slug) for slug in IDEAS_BANDS]
    pages += [ext_url("gift_category", cat_slug=slug) for slug in GIFT_CATS]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in pages:
        xml.append(f"<url><loc>{u}</loc></url>")
        xml.append(f"<url><loc>{u}{'&' if '?' in u else '?'}lang=he</loc></url>")
    for g in ob_guides.GUIDES:
        u = ext_url("guide", slug=g["slug"])
        xml.append(f"<url><loc>{u}</loc><lastmod>{g['updated']}</lastmod></url>")
        xml.append(f"<url><loc>{u}?lang=he</loc><lastmod>{g['updated']}</lastmod></url>")
    for c in get_db().execute("SELECT id, seed_key FROM catalog_items WHERE active=1 ORDER BY category, sort, id"):
        u = ext_url("catalog_item", slug=catalog_slug(c))
        xml.append(f"<url><loc>{u}</loc></url>")
        xml.append(f"<url><loc>{u}?lang=he</loc></url>")
    for r in get_db().execute("SELECT slug FROM registries WHERE visibility='public' AND closed_at IS NULL"):
        xml.append(f"<url><loc>{ext_url('registry', slug=r['slug'])}</loc></url>")
    xml.append("</urlset>")
    return app.response_class("\n".join(xml), mimetype="application/xml")


# ---------------------------------------------------------------- error handlers
def _error_page(code):
    try:
        return app.make_response(render_template("error.html", code=code)), code
    except Exception:  # noqa: BLE001 — the layout needs the DB; if that's what broke, don't 500 again
        app.logger.exception("error page itself failed to render (code %s)", code)
        return app.make_response(_BARE_ERROR_HTML), code


# Last-resort page when the normal layout can't render (e.g. the database is locked or
# missing): no DB, no templates, no scripts — just the stylesheet and a link home, EN + HE.
_BARE_ERROR_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>OurBayis — temporarily unavailable</title>
<link rel="stylesheet" href="/static/style.css"></head>
<body><main class="wrap section narrow" style="text-align:center">
<h1 class="section-title">Something went wrong on our side</h1>
<p class="page-sub">Please try again in a minute. If you were reserving a gift, check whether it went through before trying again.</p>
<p class="page-sub" dir="rtl" lang="he">משהו השתבש אצלנו. נסו שוב בעוד דקה. אם שריינתם מתנה, בדקו אם השריון נקלט לפני שמנסים שוב.</p>
<p><a class="btn btn-primary btn-lg" href="/">OurBayis</a></p>
</main></body></html>"""


@app.errorhandler(400)
def bad_request(_e):
    return _error_page(400)


@app.errorhandler(403)
def forbidden(_e):
    return _error_page(403)


@app.errorhandler(404)
def not_found(_e):
    return _error_page(404)


@app.errorhandler(413)
def too_large(_e):
    return _error_page(413)


@app.errorhandler(429)
def too_many(_e):
    resp, code = _error_page(429)
    resp.headers["Retry-After"] = "120"
    return resp, code


@app.errorhandler(500)
def server_error(_e):
    return _error_page(500)


init_db()

if __name__ == "__main__":
    app.run(debug=bool(os.environ.get("OB_DEBUG")), port=5001)
