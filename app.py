# -*- coding: utf-8 -*-
"""OurBayis — gift registries for building a home in Israel.

Single-file Flask app (same architecture as BashertBench):
server-rendered Jinja2, SQLite next to the app, no build step.
Run:  python app.py   →  http://127.0.0.1:5001

Phase 1 (v3 P0): see SPEC_V3.md. Database, security, mail and money live in
the small ob_*.py helper modules; this file stays the routes file.
"""
import csv
import io
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import urlencode
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import guides as ob_guides
import ob_db
import ob_mail
import ob_money
import ob_security
from i18n import CATEGORIES, EVENT_TYPES, T_EN, cat_label, t as _t

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("OB_DB_PATH") or (BASE / "ourbayis.db"))

BRAND = "OurBayis"
BRAND_HE = "OurBayis"
ILS_PER_USD = float(os.environ.get("OB_ILS_PER_USD", "3.7"))
CONTACT_WHATSAPP = os.environ.get("OB_WHATSAPP", "")  # e.g. 972501234567
BASE_URL = os.environ.get("OB_BASE_URL", "").rstrip("/")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("OB_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Optional SMTP — leave unset and the site works fine, mail just stays queued.
SMTP_HOST = os.environ.get("OB_SMTP_HOST", "")
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
}

# SPEC_V3 "Privacy / SEO": private/account/admin pages are never indexed.
# `registry` overrides this per-request based on `visibility` (see the route).
NOINDEX_ENDPOINTS = {
    "dashboard", "dashboard_qr", "dashboard_print", "dashboard_shared",
    "dashboard_claims_csv", "registry_new", "registry_edit", "items_manage",
    "items_add", "items_starter", "item_edit", "guest_manage", "account",
    "account_export", "account_delete", "admin_home", "admin_login",
    "reset_password", "forgot", "signup", "login",
}


# ---------------------------------------------------------------- security
PUBLIC_VIEW_ENDPOINTS = {"index", "catalog_page", "registry", "sample", "shana", "how", "about",
                         "find", "advertise", "privacy", "contact", "guides", "guide"}


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
    return resp


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
            abort(400)


def rate_limited(bucket, limit=20, per=600):
    return ob_security.rate_limited(get_db(), bucket, request.remote_addr, limit, per)


def send_mail(to, subject, body):
    return ob_mail.enqueue(get_db(), to, subject, body, db_path=DB_PATH)


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
def current_lang():
    lang = request.args.get("lang")
    if lang in ("en", "he"):
        session["lang"] = lang
        return lang
    return session.get("lang", "en")


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


def ext_url(endpoint, **kw):
    """External URL for emails/sitemap/robots/share links — uses OB_BASE_URL
    when set (so it's correct behind a proxy without OB_TRUST_PROXY), else
    falls back to Flask's own _external=True."""
    if BASE_URL:
        return BASE_URL + url_for(endpoint, **kw)
    return url_for(endpoint, _external=True, **kw)


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


def current_admin():
    name = session.get("admin")
    if not name:
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
    uid = session.get("uid")
    if not uid or not current_user():
        return None
    return get_db().execute(
        "SELECT * FROM registries WHERE user_id=? ORDER BY id LIMIT 1", (uid,)).fetchone()


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


def go_url(item):
    """/go/ handoff-click URL for a catalog or registry item. Jinja global —
    see PROJECT_KNOWLEDGE.md "Click tracking" for the return-key contract."""
    if "clicks" not in item.keys():
        return item["url"] if "url" in item.keys() else ""
    if "category" in item.keys() and "registry_id" not in item.keys() and "sort" in item.keys():
        return url_for("go_catalog", catalog_id=item["id"])
    return url_for("go_item", item_id=item["id"])


_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
_MONTHS_HE = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט",
              "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]


def fmt_date(iso, lang=None):
    """Human-readable date for display ("15 December 2026" / "15 בדצמבר 2026")
    from a stored ISO date or datetime string. The stored value is never
    changed; anything unparsable is returned as-is."""
    lang = lang or current_lang()
    try:
        d = date.fromisoformat((iso or "")[:10])
    except (ValueError, TypeError):
        return iso or ""
    if lang == "he":
        return f"{d.day} ב{_MONTHS_HE[d.month - 1]} {d.year}"
    return f"{d.day} {_MONTHS_EN[d.month - 1]} {d.year}"


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
    date = "⁨" + ob_money.RATES_DATE + "⁩" if ob_money.RATES_DATE else ""
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
        " model, availability, notes, notes_he)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (reg_id, c["id"], c["name"], c["name_he"], c["brand"], c["category"],
         c["price_nis"], c["store"], c["url"], c["image"], _c("kind", "product"),
         _c("price_status", "estimate"), _c("price_checked_at"),
         _c("model"), _c("availability", "unknown"), _c("notes"), _c("notes_he")))


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


def item_claim_breakdown(registry_id):
    """Per-item committed quantity split by lifecycle status:
    {item_id: {'reserved': n, 'reported': n, 'received': n, 'committed': n}}.
    Expired reservations (status still 'reserved' but past expires_at) are not
    counted — they free the quantity again even before `manage.py
    expire-claims` runs. The public registry page uses this to label a card
    Reserved / Reported / Received instead of a blanket "Gifted"."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = get_db().execute(
        "SELECT item_id, status, COALESCE(SUM(qty),0) AS n FROM claims"
        " WHERE registry_id=? AND item_id IS NOT NULL"
        " AND status IN ('reserved','reported','received')"
        " AND (expires_at IS NULL OR expires_at > ? OR status != 'reserved')"
        " GROUP BY item_id, status", (registry_id, now)).fetchall()
    out = {}
    for r in rows:
        d = out.setdefault(r["item_id"], dict(reserved=0, reported=0, received=0, committed=0))
        d[r["status"]] += r["n"]
        d["committed"] += r["n"]
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
    Nothing here implies payment verification; 'reported' is the guest's own
    word and 'received' is the couple's confirmation."""
    qty = item["qty_wanted"] if "qty_wanted" in item.keys() else 1
    b = (breakdown or {}).get(item["id"]) or dict(reserved=0, reported=0, received=0, committed=0)
    left = max(qty - b["committed"], 0)
    if left > 0:
        state = "partial" if b["committed"] else "open"
    elif b["received"] >= qty:
        state = "received"
    elif b["reported"]:
        state = "reported"
    else:
        state = "reserved"
    return dict(state=state, left=left, qty=qty, **b)


# keyword -> item-specific line illustration (<symbol id="ill-*"> in base.html).
# Only used when an item has no photo; falls back to the category drawing.
_ILLUSTRATION_RULES = (
    (("hot plate", "platta", "פלטה"), "platta"),
    (("urn", "meicham", "מיחם"), "urn"),
    (("kettle", "קומקום"), "kettle"),
    (("stand mixer", "hand mixer", "מיקסר"), "mixer"),
    (("slow cooker", "crock", "cholent", "בישול איטי"), "slowcooker"),
    (("towel", "bathrobe", "מגבת", "מגבות", "חלוק"), "towel"),
    (("candlestick", "פמוט"), "candlesticks"),
    (("kiddush", "קידוש"), "kiddush"),
    (("challah", "חלה"), "challah"),
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


def track(name, owner_uid=None):
    """No-PII daily funnel counters. Skipped for admins and for the registry
    owner viewing their own registry (so self-visits don't inflate funnels)."""
    if session.get("admin"):
        return
    if owner_uid is not None and session.get("uid") == owner_uid:
        return
    day = datetime.utcnow().strftime("%Y-%m-%d")
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
        tf=lambda key, **kw: _t(key, lang).format(**kw),
        pick=lambda row, field: pick(row, field, lang),
        cat_label=lambda slug: cat_label(slug, lang),
        categories=CATEGORIES,
        event_types=EVENT_TYPES,
        usd=usd,
        fmt_money=lambda minor, cur: ob_money.fmt_minor(minor, cur, lang),
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
        go_url=go_url,
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
]


def sample_registry(db, limit=6):
    lang = current_lang()
    items, breakdown = [], {}
    picks = featured_items(db, limit=limit)
    for i, c in enumerate(picks):
        qty, res, rep, rec = _SAMPLE_STATES[i % len(_SAMPLE_STATES)]
        row = dict(c)
        row.update(id=-(i + 1), registry_id=0, catalog_id=c["id"], qty_wanted=qty,
                   priority=1 if i == 0 else 0, archived=0, note="", note_he="", clicks=0)
        items.append(row)
        if res or rep or rec:
            breakdown[row["id"]] = dict(reserved=res, reported=rep, received=rec,
                                        committed=res + rep + rec)
    reg = dict(id=0, slug="sample", title=_t("sample_reg_title", "en"),
               title_he=_t("sample_reg_title", "he"), couple_names=_t("sample_reg_couple", "en"),
               couple_names_he=_t("sample_reg_couple", "he"), event_type="wedding",
               event_date="", city=_t("sample_reg_city", lang), message=_t("sample_reg_message", "en"),
               message_he=_t("sample_reg_message", "he"), visibility="public",
               display_currency="ILS", delivery_note="", delivery_note_he="",
               paypal_url="", stripe_url="", bit_url="", views=0, user_id=0)
    return reg, items, breakdown


@app.route("/")
def index():
    db = get_db()
    featured = featured_items(db, limit=8)
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    sample_reg, sample_items, sample_breakdown = sample_registry(db, limit=4)
    return render_template("index.html", featured=featured, bundles=bundles,
                           sample_reg=sample_reg, sample_items=sample_items,
                           sample_breakdown=sample_breakdown)


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
                           is_sample=True)


@app.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "he"):
        session["lang"] = code
    return redirect(ob_security.same_origin_referrer() or url_for("index"))


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
        sql += " AND (name LIKE ? OR name_he LIKE ? OR brand LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
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
    items = db.execute(sql + f" ORDER BY {order} LIMIT ? OFFSET ?",
                       params + [CATALOG_PAGE_SIZE, (page - 1) * CATALOG_PAGE_SIZE]).fetchall()
    have = set()
    reg = user_registry()
    if reg:
        have = {r["catalog_id"] for r in db.execute(
            "SELECT catalog_id FROM registry_items WHERE registry_id=?"
            " AND catalog_id IS NOT NULL", (reg["id"],))}
    filters = dict(cat=cat or None, q=q or None, price=price or None, kind=kind or None,
                   sort=sort or None)
    return render_template("catalog.html", items=items, cat=cat, q=q, price=price, kind=kind,
                           sort=sort, page=page, pages=pages, total=total, filters=filters,
                           price_bands=CATALOG_PRICE_BANDS, have=have, has_reg=bool(reg))


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


@app.route("/go/c/<int:catalog_id>")
def go_catalog(catalog_id):
    """Click-through to a catalog item's store link. The destination is
    always read from the DB, never from the query string (no open redirect),
    and is re-validated even though it was validated on save."""
    db = get_db()
    row = db.execute("SELECT * FROM catalog_items WHERE id=?", (catalog_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    db.execute("UPDATE catalog_items SET clicks = clicks + 1 WHERE id=?", (catalog_id,))
    track("handoff_click")
    return redirect(row["url"], code=302)


@app.route("/go/i/<int:item_id>")
def go_item(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM registry_items WHERE id=?", (item_id,)).fetchone()
    if not row or not valid_http_url(row["url"]):
        abort(404)
    db.execute("UPDATE registry_items SET clicks = clicks + 1 WHERE id=?", (item_id,))
    reg = db.execute("SELECT user_id FROM registries WHERE id=?", (row["registry_id"],)).fetchone()
    track("handoff_click", owner_uid=reg["user_id"] if reg else None)
    return redirect(row["url"], code=302)


@app.route("/find")
def find():
    q = (request.args.get("q") or "").strip()
    results = None
    if q:
        like = f"%{q}%"
        results = get_db().execute(
            "SELECT * FROM registries WHERE visibility='public' AND"
            " (couple_names LIKE ? OR couple_names_he LIKE ? OR title LIKE ? OR title_he LIKE ?)"
            " ORDER BY created_at DESC LIMIT 40",
            (like, like, like, like)).fetchall()
    return render_template("find.html", q=q, results=results)


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
                f"{body[:4000]}\n\nAdmin: {ext_url('admin_home')}")
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
    is_owner = session.get("uid") == reg["user_id"]
    g.registry_owner_uid = reg["user_id"]
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
            prefs["previewed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.execute("UPDATE registries SET preferences_json=? WHERE id=?",
                      (json.dumps(prefs), reg["id"]))
    days_to_go = None
    try:
        days_to_go = (date.fromisoformat(reg["event_date"]) - date.today()).days
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
                           pay_links=reg_pay_links(reg), days_to_go=days_to_go,
                           is_owner=is_owner, is_preview=is_preview,
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
        flash(_t("form_error", lang), "err")
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
            committed = item_claim_counts(reg["id"]).get(item_id, 0)
            left = max(item["qty_wanted"] - committed, 0)
            if left <= 0:
                flash(_t("gifted", lang), "err")
                raise _Abort()
            try:
                qty = int(request.form.get("qty", 1))
            except ValueError:
                qty = 1
            qty = max(1, min(qty, left))
            pay_links = reg_pay_links(reg)
            routes = item_routes(item, pay_links)
            if not routes["store"] and not routes["cash"]:
                # an "idea" with nowhere to buy and no payment link — never reservable
                flash(_t("claim_no_route", lang), "err")
                raise _Abort()
            # server-side card rules: the only valid routes are the ones the item has
            give_cash = (request.form.get("give") == "cash" and routes["cash"]) or not routes["store"]
            price_minor = int(item["price_nis"]) * 100
            amount_minor = price_minor * qty if give_cash else None
            currency = "ILS" if give_cash else None
            expires_at = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
            token = ob_security.new_token()
            token_hash = ob_security.hash_token(token)
            try:
                cur = db.execute(
                    "INSERT INTO claims (registry_id, item_id, guest_name, guest_email, message,"
                    " qty, kind, status, amount_minor, currency, price_snapshot_minor,"
                    " price_snapshot_currency, token_hash, token_created_at, idempotency_key,"
                    " expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (reg["id"], item_id, name,
                     (request.form.get("guest_email") or "").strip()[:200],
                     (request.form.get("message") or "").strip()[:1000], qty,
                     "cash" if give_cash else "item", "reserved", amount_minor, currency,
                     price_minor, "ILS", token_hash, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                     form_key or None, expires_at))
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
            result.update(reg=dict(reg), item=dict(item), token=token, qty=qty,
                          give_cash=give_cash, name=name)
    except _Abort as ab:
        return ab.response or redirect(url_for("registry", slug=slug))

    _remember_claim_token(form_key, result["token"])
    reg, item = result["reg"], result["item"]
    owner = db.execute("SELECT email FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    if owner and owner["email"]:
        kind_txt = "mail_reserved_cash" if result["give_cash"] else "mail_reserved_item"
        send_mail(owner["email"], _t(kind_txt + "_subj", lang).format(title=reg["title"]),
                  _t(kind_txt + "_body", lang).format(name=result["name"], item=item["name"],
                                                       qty=result["qty"]))
    if request.form.get("guest_email"):
        send_mail((request.form.get("guest_email") or "").strip(),
                  _t("mail_guest_manage_subj", lang),
                  _t("mail_guest_manage_body", lang).format(
                      link=ext_url("guest_manage", token=result["token"])))
    track("reservation", owner_uid=reg["user_id"])
    return redirect(url_for("guest_manage", token=result["token"]))


class _Abort(Exception):
    """Internal control-flow signal to bail out of a write_txn block cleanly
    (rolls back the transaction) while keeping the flash message set above.
    Optionally carries a specific response to return (e.g. straight to the
    guest's own /g/<token> on a remembered duplicate form_key)."""
    def __init__(self, response=None):
        super().__init__()
        self.response = response


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
    name = (request.form.get("guest_name") or "").strip()[:120]
    currency = (request.form.get("currency") or "ILS").upper()
    if currency not in ob_money.CURRENCIES:
        currency = "ILS"
    if not name:
        flash(_t("form_error", lang), "err")
        return redirect(url_for("registry", slug=slug))
    try:
        amount_minor = ob_money.to_minor(request.form.get("amount") or "0", currency)
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
                    " idempotency_key) VALUES (?, NULL, ?, ?, ?, 1, 'cash', 'reported', ?, ?, ?, ?, ?)",
                    (reg["id"], name, (request.form.get("guest_email") or "").strip()[:200],
                     (request.form.get("message") or "").strip()[:1000], amount_minor, currency,
                     ob_security.hash_token(token), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                     form_key or None))
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
    owner = db.execute("SELECT email FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    if owner and owner["email"]:
        send_mail(owner["email"], _t("mail_cash_subj", lang).format(title=reg["title"]),
                  _t("mail_cash_body", lang).format(
                      name=name, amount=ob_money.fmt_minor(amount_minor, currency, lang)))
    if request.form.get("guest_email"):
        send_mail((request.form.get("guest_email") or "").strip(),
                  _t("mail_guest_manage_subj", lang),
                  _t("mail_guest_manage_body", lang).format(link=ext_url("guest_manage", token=token)))
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
    return render_template("guest_manage.html", claim=claim, reg=reg, item=item,
                           token=token, pay_links=reg_pay_links(reg))


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
        db.execute("UPDATE claims SET status='reported', reported_at=?, late=? WHERE id=?",
                   (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), late, claim["id"]))
        _log_claim_event(db, claim["id"], "reported", "guest", "late" if late else "")
        reg = db.execute("SELECT * FROM registries WHERE id=?", (claim["registry_id"],)).fetchone()
    owner = db.execute("SELECT email FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    if owner and owner["email"]:
        send_mail(owner["email"], _t("mail_reported_subj", lang).format(name=claim["guest_name"]),
                  _t("mail_reported_body", lang).format(name=claim["guest_name"]))
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
                   (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), claim["id"]))
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
        pw2 = request.form.get("password2") or ""
        if not name or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
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
                pending_add = session.get("pending_add")  # survives session.clear() below
                session.clear()
                session["uid"] = cur.lastrowid
                session["sv"] = 1
                if pending_add:
                    session["pending_add"] = pending_add
                track("signup")
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
            session.clear()
            session["uid"] = row["id"]
            session["sv"] = row["session_ver"]
            return redirect(nxt or url_for("dashboard"))
        flash(_t("login_error", current_lang()), "err")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
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
        if not SMTP_HOST:
            flash(_t("forgot_noemail", lang), "err")
            return redirect(url_for("contact"))
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = ob_security.new_token()
            expires_at = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
            with ob_db.write_txn(db):
                db.execute("UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL",
                          (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
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
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
            with ob_db.write_txn(db):
                db.execute(
                    "UPDATE users SET pw_hash=?, session_ver=session_ver+1 WHERE id=?",
                    (generate_password_hash(pw), row["user_id"]))
                db.execute("UPDATE password_resets SET used_at=? WHERE user_id=? AND used_at IS NULL",
                          (now, row["user_id"]))
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
        ("visibility", bool(prefs.get("visibility_reviewed_at"))),
        ("previewed", bool(prefs.get("previewed_at"))),
        ("shared", (reg["views"] or 0) > 0 or bool(prefs.get("shared_at"))),
    ]


@app.route("/dashboard")
@login_required
def dashboard():
    reg = user_registry()
    gifts = stats = totals = checklist = queues = None
    if reg:
        db = get_db()
        gifts = db.execute(
            "SELECT c.*, ri.name AS item_name, ri.name_he AS item_name_he,"
            " ri.url AS item_url, ri.store AS item_store, ri.availability AS item_availability"
            " FROM claims c"
            " LEFT JOIN registry_items ri ON ri.id = c.item_id"
            " WHERE c.registry_id=? ORDER BY c.created_at DESC", (reg["id"],)).fetchall()
        n_items = db.execute("SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0",
                             (reg["id"],)).fetchone()[0]
        n_usable = db.execute(
            "SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0"
            " AND (url != '' OR ?)", (reg["id"], 1 if reg_pay_links(reg) else 0)).fetchone()[0]
        n_claimed = db.execute(
            "SELECT COUNT(DISTINCT item_id) FROM claims WHERE registry_id=? AND item_id IS NOT NULL"
            " AND status IN ('reserved','reported','received')", (reg["id"],)).fetchone()[0]
        n_cash = db.execute(
            "SELECT COUNT(*) FROM claims WHERE registry_id=? AND kind='cash'"
            " AND status IN ('reserved','reported','received')", (reg["id"],)).fetchone()[0]
        stats = dict(items=n_items, claimed=n_claimed, cash=n_cash,
                     views=reg["views"] if "views" in reg.keys() else 0)
        totals = {}
        for gft in gifts:
            if gft["amount_minor"] is not None and gft["status"] == "received":
                cur = gft["currency"] or "ILS"
                totals[cur] = totals.get(cur, 0) + gft["amount_minor"]
        checklist = _dashboard_checklist(db, reg, n_items, n_usable, gifts)
        queues = dict(
            awaiting_confirm=[g for g in gifts if g["status"] == "reported"],
            waiting=[g for g in gifts if g["status"] == "reserved"],
            unthanked=[g for g in gifts if g["status"] == "received" and not g["thanked"]],
        )
    return render_template("dashboard.html", reg=reg, gifts=gifts, stats=stats, totals=totals,
                           checklist=checklist, queues=queues)


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
            prefs["shared_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            with ob_db.write_txn(db):
                db.execute("UPDATE registries SET preferences_json=? WHERE id=?",
                          (json.dumps(prefs), reg["id"]))
        track("share_click")
    return ("", 204)


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
    qr = segno.make(ext_url("registry", slug=reg["slug"]), error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=6, border=2, dark="#223354")
    resp = app.response_class(buf.getvalue(), mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/registry/new", methods=["GET", "POST"])
@login_required
def registry_new():
    if user_registry():
        return redirect(url_for("registry_edit"))
    if request.method == "POST":
        return _save_registry(None)
    return render_template("registry_form.html", reg=None, prefs={})


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
    prefs["visibility_reviewed_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if not title or not couple:
        flash(_t("form_error", lang), "err")
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
            cur_pw = f.get("current_password") or ""
            user = db.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
            if not cur_pw or not check_password_hash(user["pw_hash"], cur_pw):
                flash(_t("reauth_required", lang), "err")
                return render_template("registry_form.html", reg=reg, form=f, prefs=prefs, show_reauth=True)
    fields = (title, (f.get("title_he") or "").strip()[:160],
              couple, (f.get("couple_names_he") or "").strip()[:160],
              event_type, (f.get("event_date") or "").strip()[:40],
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
        flash(_t("r_saved", lang), "ok")
        return redirect(url_for("dashboard"))
    slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    while db.execute("SELECT 1 FROM registries WHERE slug=?", (slug,)).fetchone():
        slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    with ob_db.write_txn(db):
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
    return redirect(url_for("items_manage"))


@app.route("/registry/items")
@login_required
def items_manage():
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    db = get_db()
    cat = request.args.get("cat", "")
    q = (request.args.get("q") or "").strip()
    sql = "SELECT * FROM catalog_items WHERE active=1"
    params = []
    if cat in CATEGORIES:
        sql += " AND category=?"
        params.append(cat)
    if q:
        sql += " AND (name LIKE ? OR name_he LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
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
    return render_template("items.html", reg=reg, catalog=catalog, mine=mine, archived=archived,
                           archived_claim_counts=archived_claim_counts,
                           have=have_catalog_ids, claimed=claimed, breakdown=breakdown, cat=cat, q=q,
                           n_committed=n_committed, n_needs_link=n_needs_link)


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
        if not valid_http_url(url):
            url = ""
        try:
            price = max(0, int(f.get("price_nis") or 0))
        except ValueError:
            price = 0
        if name:
            db.execute(
                "INSERT INTO registry_items (registry_id, name, name_he, category,"
                " price_nis, store, url, kind) VALUES (?,?,?,?,?,?,?,?)",
                (reg["id"], name, (f.get("name_he") or "").strip()[:200],
                 f.get("category") if f.get("category") in CATEGORIES else "home",
                 price, (f.get("store") or "").strip()[:120], url,
                 "product" if url else "idea"))
            _maybe_track_first_gifts(db, reg["id"])
        else:
            flash(_t("form_error", current_lang()), "err")
    if request.args.get("back") == "catalog":
        keep = {k: request.args.get(k) for k in ("cat", "q", "price", "kind", "sort", "page")
                if request.args.get(k)}
        return redirect(url_for("catalog_page", **keep) + (f"#c-{cat_id}" if cat_id else ""))
    return redirect(url_for("items_manage", cat=request.args.get("cat", ""),
                            q=request.args.get("q", "")) + ("#add-more" if cat_id else "#mine"))


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
        flash(_t("starter_added", current_lang()).format(n=added), "ok")
        return redirect(url_for("items_manage") + "#mine")
    groups = {g: db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND starter_group=? ORDER BY sort", (g,)).fetchall()
        for g in STARTER_GROUPS_ORDER}
    return render_template("items_starter.html", reg=reg, groups=groups,
                           group_order=STARTER_GROUPS_ORDER, have=have_catalog_ids)


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
    if request.form.get("delete"):
        has_claims = db.execute("SELECT 1 FROM claims WHERE item_id=? LIMIT 1", (item_id,)).fetchone()
        if has_claims:
            db.execute("UPDATE registry_items SET archived=1 WHERE id=?", (item_id,))
        else:
            db.execute("DELETE FROM registry_items WHERE id=?", (item_id,))
    else:
        try:
            qty = max(1, min(int(request.form.get("qty_wanted", 1)), 99))
        except ValueError:
            qty = 1
        committed = item_claim_counts(reg["id"]).get(item_id, 0)
        if qty < committed:
            flash(_t("qty_below_committed", lang).format(n=committed), "err")
            return redirect(url_for("items_manage"))
        db.execute("UPDATE registry_items SET qty_wanted=?, priority=? WHERE id=?",
                   (qty, 1 if request.form.get("priority") else 0, item_id))
    return redirect(url_for("items_manage"))


_OVERRIDABLE_FIELDS = ("url", "image", "store", "brand", "name")


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
    if request.method == "POST":
        f = request.form
        name = (f.get("name") or "").strip()[:200]
        if not name:
            flash(_t("form_error", lang), "err")
            return render_template("item_edit.html", reg=reg, item=item)
        url = (f.get("url") or "").strip()[:500]
        if url and not url.startswith("http"):
            url = "https://" + url
        url_ok = (not url) or valid_http_url(url)
        if url and not url_ok:
            flash(_t("bad_url", lang), "err")
            return render_template("item_edit.html", reg=reg, item=item)
        try:
            price = max(0, int(f.get("price_nis") or 0))
        except ValueError:
            price = 0
        try:
            qty = max(1, min(int(f.get("qty_wanted", 1)), 99))
        except ValueError:
            qty = 1
        committed = item_claim_counts(reg["id"]).get(item_id, 0)
        if qty < committed:
            flash(_t("qty_below_committed", lang).format(n=committed), "err")
            return render_template("item_edit.html", reg=reg, item=item)
        store = (f.get("store") or "").strip()[:120]
        brand = (f.get("brand") or "").strip()[:80]
        new_vals = dict(name=name, url=url, store=store, brand=brand,
                        image=(f.get("image") or item["image"] or ""))
        overrides = set(x for x in (item["overrides"] or "").split(",") if x)
        for field in _OVERRIDABLE_FIELDS:
            old = item[field] if field in item.keys() else ""
            if new_vals.get(field, old) != old:
                overrides.add(field)
        db.execute(
            "UPDATE registry_items SET name=?, name_he=?, brand=?, price_nis=?, url=?, store=?,"
            " qty_wanted=?, priority=?, note=?, note_he=?, variant=?,"
            " kind=?, overrides=? WHERE id=?",
            (name, (f.get("name_he") or "").strip()[:200], brand, price, url, store, qty,
             1 if f.get("priority") else 0, (f.get("note") or "").strip()[:1000],
             (f.get("note_he") or "").strip()[:1000], (f.get("variant") or "").strip()[:120],
             f.get("kind") if f.get("kind") in ("product", "idea", "cash_need") else item["kind"],
             ",".join(sorted(overrides)), item_id))
        flash(_t("item_updated", lang), "ok")
        return redirect(url_for("items_manage"))
    return render_template("item_edit.html", reg=reg, item=item)


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
        if c["status"] in ("reported", "reserved"):
            db.execute("UPDATE claims SET status='received', confirmed_at=? WHERE id=?",
                      (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), claim_id))
            _log_claim_event(db, claim_id, "received", "owner")
            track("receipt_confirmed")
    return redirect(url_for("dashboard"))


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
        db.execute("UPDATE claims SET status='cancelled', cancelled_by='owner', cancelled_at=? WHERE id=?",
                  (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), claim_id))
        _log_claim_event(db, claim_id, "cancelled", "owner")
    return redirect(url_for("dashboard"))


@app.route("/claim/<int:claim_id>/thanked", methods=["POST"])
@login_required
def claim_thanked(claim_id):
    db = get_db()
    c = _owned_claim(claim_id)
    if not c:
        abort(404)
    db.execute("UPDATE claims SET thanked=? WHERE id=?", (0 if c["thanked"] else 1, claim_id))
    return redirect(url_for("dashboard"))


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
                   csv_safe(r["item_name"]), csv_safe(r["qty"]), csv_safe(r["kind"]),
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
    return render_template("account.html", reg=user_registry())


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
    if reg:
        data["registry"] = {k: reg[k] for k in reg.keys() if k not in ("id", "user_id")}
        data["items"] = [dict(r) for r in db.execute(
            "SELECT * FROM registry_items WHERE registry_id=?", (reg["id"],))]
        data["claims"] = [
            {k: v for k, v in dict(r).items() if k not in ("token_hash",)}
            for r in db.execute("SELECT * FROM claims WHERE registry_id=?", (reg["id"],))]
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
    session.clear()
    flash(_t("account_deleted", lang), "ok")
    return redirect(url_for("index"))


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
        has_contact = (email and _EMAIL_RE.match(email)) or len(whatsapp_digits) >= 8
        if not name or not has_contact:
            flash(_t("shana_contact_required", lang) if name else _t("form_error", lang), "err")
        else:
            db.execute(
                "INSERT INTO shana_requests (name, email, whatsapp, arrival, city, neighborhood,"
                " furnishing, budget, bundle_slug, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (name, email, (f.get("whatsapp") or "").strip()[:40],
                 (f.get("arrival") or "").strip()[:40],
                 (f.get("city") or "").strip()[:120],
                 (f.get("neighborhood") or "").strip()[:120],
                 f.get("furnishing") if f.get("furnishing") in
                     ("unknown", "empty", "partly", "furnished") else "unknown",
                 (f.get("budget") or "").strip()[:40],
                 (f.get("bundle") or "custom")[:60],
                 (f.get("notes") or "").strip()[:2000]))
            send_mail(
                NOTIFY_EMAIL,
                f"New shana rishonah lead: {name} ({f.get('bundle', 'custom')})",
                f"Name: {name}\nWhatsApp: {f.get('whatsapp', '')}\nEmail: {email}\n"
                f"Arrival: {f.get('arrival', '')}\nCity: {f.get('city', '')}\n"
                f"Neighborhood: {f.get('neighborhood', '')}\nFurnishing: {f.get('furnishing', '')}\n"
                f"Budget: {f.get('budget', '')}\nBundle: {f.get('bundle', '')}\n"
                f"Notes: {f.get('notes', '')}\n\nAdmin: {ext_url('admin_home')}")
            track("concierge_inquiry")
            flash(_t("sr_done_t", lang) + " " + _t("sr_done_b", lang), "ok")
            return redirect(url_for("shana"))
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    return render_template("shana.html", bundles=bundles, package_tiers=PACKAGE_TIERS)


# Shana Rishonah package definition, per tier (review 2026-09-15). The goods
# list lives in `bundles.items_text` (admin-editable); these are the service
# terms that differ between tiers and must stay consistent between the cards,
# the shared terms panel and the lead-time guidance. Values map to i18n keys
# pkg_delivery_<delivery>, pkg_setup_yes/no, pkg_appliances_<appliances>,
# pkg_lead_weeks. OWNER DECISION still open (see TODO_AI.md): whether Full
# Nest's price includes appliance installation or it is quoted separately —
# until decided, every tier says installation is confirmed in the quote.
PACKAGE_TIERS = {
    "basic": dict(delivery="before", setup=False, appliances="none", lead_weeks=3),
    "standard": dict(delivery="before", setup=False, appliances="ask", lead_weeks=3),
    "premium": dict(delivery="received", setup=True, appliances="included", lead_weeks=6),
}


# ---------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    db = get_db()
    n_admins = db.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    if request.method == "POST":
        if rate_limited("admin_login", limit=10, per=600):
            abort(429)
        row = db.execute("SELECT * FROM admins WHERE username=?",
                         ((request.form.get("username") or "").strip(),)).fetchone()
        if row and check_password_hash(row["pw_hash"], request.form.get("password") or ""):
            session.clear()
            session["admin"] = row["username"]
            session["admin_sv"] = row["session_ver"]
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
    leads = db.execute("SELECT * FROM shana_requests ORDER BY status='new' DESC, created_at DESC"
                       " LIMIT 50").fetchall()
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
    recent = db.execute("SELECT * FROM registries ORDER BY created_at DESC LIMIT 15").fetchall()
    mail_stats = ob_mail.outbox_counts(db)
    since = (date.today() - timedelta(days=30)).isoformat()
    funnel = db.execute(
        "SELECT name, SUM(n) AS n FROM funnel_events WHERE day>=? GROUP BY name ORDER BY n DESC",
        (since,)).fetchall()
    return render_template("admin.html", leads=leads, msgs=msgs, stats=stats, recent=recent,
                           mail_stats=mail_stats, funnel=funnel)


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


@app.route("/admin/lead/<int:lead_id>/status", methods=["POST"])
@admin_required
def admin_lead_status(lead_id):
    status = request.form.get("status", "new")
    if status in LEAD_STATUSES:
        get_db().execute("UPDATE shana_requests SET status=? WHERE id=?", (status, lead_id))
    return redirect(request.referrer or url_for("admin_home"))


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
    return render_template("admin_lead.html", lead=lead, dupes=dupes, quote=quote,
                           statuses=LEAD_STATUSES)


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
    if price_status in ("verified", "estimate", "unknown"):
        sql += " AND price_status=?"
        params.append(price_status)
    rows = db.execute(sql + " ORDER BY category, sort", params).fetchall()
    queue_counts = dict(
        missing_url=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND url=''").fetchone()[0],
        missing_image=db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND image=''").fetchone()[0],
        unverified=db.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE active=1 AND price_status!='verified'").fetchone()[0],
    )
    return render_template("admin_catalog.html", rows=rows, q=q, cat=cat, price_status=price_status,
                           missing_url=missing_url, missing_image=missing_image,
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
            f.get("starter_group") or "")
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
                " notes=?, notes_he=?, starter_group=?, updated_at=? WHERE id=?",
                vals + (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), item_id))
            if n_registry_refs:
                flash("Changes here don't rewrite gifts already copied to registries — "
                      "run `manage.py refresh-registry-links` to push url/image/store/brand out.", "ok")
            return redirect(url_for("admin_catalog"))
        else:
            db.execute(
                "INSERT INTO catalog_items (name, name_he, brand, category, price_nis, store, url,"
                " image, active, featured, sort, kind, model, variant, image_credit, price_status,"
                " price_checked_at, price_source, availability, notes, notes_he, starter_group, seed_key)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals + (None,))
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
        if title:
            db.execute("INSERT INTO ads (title, body, image, link_url) VALUES (?,?,?,?)",
                       (title, (request.form.get("body") or "").strip()[:500],
                        (request.form.get("image") or "").strip()[:500],
                        (request.form.get("link_url") or "").strip()[:500]))
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


@app.route("/admin/password", methods=["POST"])
@admin_required
def admin_password():
    admin_row = current_admin()
    cur_pw = request.form.get("current_password") or ""
    pw = request.form.get("password") or ""
    if not check_password_hash(admin_row["pw_hash"], cur_pw):
        flash("Current password is wrong", "err")
    elif len(pw) < 10:
        flash("Password must be at least 10 characters", "err")
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
@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nDisallow: /admin\nDisallow: /dashboard\nDisallow: /g/\n"
        f"Sitemap: {ext_url('sitemap')}\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    pages = [ext_url(p) for p in
             ("index", "how", "find", "catalog_page", "sample", "shana", "about", "contact", "privacy",
              "advertise", "guides")]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in pages:
        xml.append(f"<url><loc>{u}</loc></url>")
        xml.append(f"<url><loc>{u}{'&' if '?' in u else '?'}lang=he</loc></url>")
    for g in ob_guides.GUIDES:
        u = ext_url("guide", slug=g["slug"])
        xml.append(f"<url><loc>{u}</loc><lastmod>{g['updated']}</lastmod></url>")
        xml.append(f"<url><loc>{u}?lang=he</loc><lastmod>{g['updated']}</lastmod></url>")
    for r in get_db().execute("SELECT slug FROM registries WHERE visibility='public'"):
        xml.append(f"<url><loc>{ext_url('registry', slug=r['slug'])}</loc></url>")
    xml.append("</urlset>")
    return app.response_class("\n".join(xml), mimetype="application/xml")


# ---------------------------------------------------------------- error handlers
def _error_page(code):
    return app.make_response(render_template("error.html", code=code)), code


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
