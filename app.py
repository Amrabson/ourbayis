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
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

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


def estimate_label(price_nis, lang=None):
    """"≈ $49 (approx., rate as of 2026-09-01)" in the session/registry display
    currency, or '' when that currency is ILS (no estimate needed) or isn't
    configured in OB_RATES. Jinja global for public templates."""
    lang = lang or current_lang()
    cur = session.get("cur") or "ILS"
    if cur == "ILS" or not price_nis:
        return ""
    minor = int(price_nis) * 100
    est_minor = ob_money.estimate(minor, cur)
    if est_minor is None:
        return ""
    body = ob_money.fmt_minor(est_minor, cur, lang)
    if ob_money.RATES_DATE:
        return _t("estimate_label_dated", lang).format(amount=body, date=ob_money.RATES_DATE)
    return _t("estimate_label", lang).format(amount=body)


def item_claim_counts(registry_id):
    """Committed quantity per item: reserved/reported/received claims, minus
    reserved claims that have expired (those free up the quantity again)."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = get_db().execute(
        "SELECT item_id, COALESCE(SUM(qty),0) AS n FROM claims"
        " WHERE registry_id=? AND item_id IS NOT NULL"
        " AND status IN ('reserved','reported','received')"
        " AND (expires_at IS NULL OR expires_at > ? OR status != 'reserved')"
        " GROUP BY item_id", (registry_id, now)).fetchall()
    return {r["item_id"]: r["n"] for r in rows}


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


def _log_claim_event(db, claim_id, event, actor, note=""):
    db.execute(
        "INSERT INTO claim_events (claim_id, event, actor, note) VALUES (?,?,?,?)",
        (claim_id, event, actor, note))


def _canonical_and_alts():
    """canonical_url + alt_urls (en/he) for the current GET request, computed
    from the path with `lang` stripped/overridden — GET only (SPEC_V3
    "Privacy / SEO" -> Canonical/hreflang)."""
    if request.method != "GET":
        return None, {}
    args = request.args.to_dict(flat=True)
    args.pop("lang", None)
    base = request.path
    qs = "&".join(f"{k}={v}" for k, v in args.items())
    sep = "&" if qs else ""
    canonical = ext_url_path(base, args, "he" if current_lang() == "he" else None)
    alts = {
        "en": ext_url_path(base, args, None),
        "he": ext_url_path(base, args, "he"),
    }
    return canonical, alts


def ext_url_path(path, args, lang_code):
    q = dict(args)
    if lang_code:
        q["lang"] = lang_code
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    full = (BASE_URL or request.host_url.rstrip("/")) + path
    return full + (("?" + qs) if qs else "")


@app.context_processor
def inject_globals():
    lang = current_lang()
    canonical_url, alt_urls = _canonical_and_alts()
    ep = request.endpoint or ""
    default_noindex = ep.startswith("admin") or ep in NOINDEX_ENDPOINTS or request.path.startswith("/g/")
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
        display_currency=session.get("cur") or "ILS",
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
@app.route("/")
def index():
    db = get_db()
    featured = db.execute(
        "SELECT * FROM catalog_items WHERE active=1 AND featured=1 ORDER BY sort LIMIT 8").fetchall()
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    return render_template("index.html", featured=featured, bundles=bundles)


@app.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "he"):
        session["lang"] = code
    return redirect(ob_security.same_origin_referrer() or url_for("index"))


@app.route("/currency/<code>")
def set_currency(code):
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


@app.route("/catalog")
def catalog_page():
    """Public catalog — browse everything without an account."""
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
    items = db.execute(sql + " ORDER BY category, sort", params).fetchall()
    have = set()
    reg = user_registry()
    if reg:
        have = {r["catalog_id"] for r in db.execute(
            "SELECT catalog_id FROM registry_items WHERE registry_id=?"
            " AND catalog_id IS NOT NULL", (reg["id"],))}
    return render_template("catalog.html", items=items, cat=cat, q=q,
                           have=have, has_reg=bool(reg))


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
    claimed = item_claim_counts(reg["id"])
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
            give_cash = request.form.get("give") == "cash" and bool(pay_links)
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
                # duplicate form_key = a repeated POST (double-click / retry). We can't
                # recover the original guest's raw recovery token from its stored hash,
                # so send them back to the registry instead of guessing a /g/ URL —
                # documented deviation, see CHANGELOG_AI.md "Decisions".
                flash(_t("claim_already", lang), "ok")
                raise _Abort()
            _log_claim_event(db, cur.lastrowid, "reserved", "guest")
            result.update(reg=dict(reg), item=dict(item), token=token, qty=qty,
                          give_cash=give_cash, name=name)
    except _Abort:
        return redirect(url_for("registry", slug=slug))

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
    (rolls back the transaction) while keeping the flash message set above."""


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
    token = ob_security.new_token()
    with ob_db.write_txn(db):
        cur = db.execute(
            "INSERT INTO claims (registry_id, item_id, guest_name, guest_email, message, qty,"
            " kind, status, amount_minor, currency, token_hash, token_created_at)"
            " VALUES (?, NULL, ?, ?, ?, 1, 'cash', 'reported', ?, ?, ?, ?)",
            (reg["id"], name, (request.form.get("guest_email") or "").strip()[:200],
             (request.form.get("message") or "").strip()[:1000], amount_minor, currency,
             ob_security.hash_token(token), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        _log_claim_event(db, cur.lastrowid, "reported", "guest")
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
                session.clear()
                session["uid"] = cur.lastrowid
                session["sv"] = 1
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
@app.route("/dashboard")
@login_required
def dashboard():
    reg = user_registry()
    gifts = stats = totals = None
    if reg:
        db = get_db()
        gifts = db.execute(
            "SELECT c.*, ri.name AS item_name, ri.name_he AS item_name_he,"
            " ri.url AS item_url, ri.store AS item_store FROM claims c"
            " LEFT JOIN registry_items ri ON ri.id = c.item_id"
            " WHERE c.registry_id=? ORDER BY c.created_at DESC", (reg["id"],)).fetchall()
        n_items = db.execute("SELECT COUNT(*) FROM registry_items WHERE registry_id=? AND archived=0",
                             (reg["id"],)).fetchone()[0]
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
    return render_template("dashboard.html", reg=reg, gifts=gifts, stats=stats, totals=totals)


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
    return render_template("registry_form.html", reg=None)


@app.route("/registry/edit", methods=["GET", "POST"])
@login_required
def registry_edit():
    reg = user_registry()
    if not reg:
        return redirect(url_for("registry_new"))
    if request.method == "POST":
        return _save_registry(reg)
    return render_template("registry_form.html", reg=reg)


def _save_registry(reg):
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
    if not title or not couple:
        flash(_t("form_error", lang), "err")
        return render_template("registry_form.html", reg=reg)
    if pay_errors:
        for msg in pay_errors:
            flash(msg, "err")
        return render_template("registry_form.html", reg=reg)
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
                return render_template("registry_form.html", reg=reg, show_reauth=True)
    fields = (title, (f.get("title_he") or "").strip()[:160],
              couple, (f.get("couple_names_he") or "").strip()[:160],
              event_type, (f.get("event_date") or "").strip()[:40],
              (f.get("city") or "").strip()[:120],
              (f.get("message") or "").strip()[:2000],
              (f.get("message_he") or "").strip()[:2000],
              pay["paypal_url"], pay["stripe_url"], pay["bit_url"],
              1 if f.get("is_public") else 0,
              "public" if f.get("is_public") else "unlisted")
    if reg:
        with ob_db.write_txn(db):
            db.execute(
                "UPDATE registries SET title=?, title_he=?, couple_names=?, couple_names_he=?,"
                " event_type=?, event_date=?, city=?, message=?, message_he=?, paypal_url=?,"
                " stripe_url=?, bit_url=?, is_public=?, visibility=? WHERE id=?",
                fields + (reg["id"],))
            if any(pay[c] != (reg[c] if c in reg.keys() else "") for c in
                  ("paypal_url", "stripe_url", "bit_url")):
                db.execute("UPDATE users SET session_ver=session_ver+1 WHERE id=?", (session["uid"],))
                session["sv"] = db.execute("SELECT session_ver FROM users WHERE id=?",
                                           (session["uid"],)).fetchone()[0]
        return redirect(url_for("dashboard"))
    slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    while db.execute("SELECT 1 FROM registries WHERE slug=?", (slug,)).fetchone():
        slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    with ob_db.write_txn(db):
        db.execute(
            "INSERT INTO registries (user_id, slug, title, title_he, couple_names,"
            " couple_names_he, event_type, event_date, city, message, message_he,"
            " paypal_url, stripe_url, bit_url, is_public, visibility)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session["uid"], slug) + fields)
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
    have_catalog_ids = {m["catalog_id"] for m in mine if m["catalog_id"]}
    claimed = item_claim_counts(reg["id"])
    return render_template("items.html", reg=reg, catalog=catalog, mine=mine,
                           have=have_catalog_ids, claimed=claimed, cat=cat, q=q)


@app.route("/registry/items/add", methods=["POST"])
@login_required
def items_add():
    reg = user_registry()
    if not reg:
        abort(400)
    db = get_db()
    f = request.form
    cat_id = f.get("catalog_id")
    if cat_id:
        c = db.execute("SELECT * FROM catalog_items WHERE id=? AND active=1", (cat_id,)).fetchone()
        if not c:
            abort(404)
        exists = db.execute(
            "SELECT 1 FROM registry_items WHERE registry_id=? AND catalog_id=?",
            (reg["id"], c["id"])).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO registry_items (registry_id, catalog_id, name, name_he, brand,"
                " category, price_nis, store, url, image) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (reg["id"], c["id"], c["name"], c["name_he"], c["brand"], c["category"],
                 c["price_nis"], c["store"], c["url"], c["image"]))
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
                " price_nis, store, url) VALUES (?,?,?,?,?,?,?)",
                (reg["id"], name, (f.get("name_he") or "").strip()[:200],
                 f.get("category") if f.get("category") in CATEGORIES else "home",
                 price, (f.get("store") or "").strip()[:120], url))
        else:
            flash(_t("form_error", current_lang()), "err")
    if request.args.get("back") == "catalog":
        return redirect(url_for("catalog_page", cat=request.args.get("cat", ""),
                                q=request.args.get("q", "")))
    return redirect(url_for("items_manage", cat=request.args.get("cat", ""),
                            q=request.args.get("q", "")))


@app.route("/registry/items/starter", methods=["POST"])
@login_required
def items_starter():
    """One-click: add all featured catalog items the couple doesn't have yet."""
    reg = user_registry()
    if not reg:
        abort(400)
    db = get_db()
    added = 0
    with ob_db.write_txn(db):
        for c in db.execute("SELECT * FROM catalog_items WHERE active=1 AND featured=1"):
            if not db.execute("SELECT 1 FROM registry_items WHERE registry_id=? AND catalog_id=?",
                              (reg["id"], c["id"])).fetchone():
                db.execute(
                    "INSERT INTO registry_items (registry_id, catalog_id, name, name_he, brand,"
                    " category, price_nis, store, url, image) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (reg["id"], c["id"], c["name"], c["name_he"], c["brand"], c["category"],
                     c["price_nis"], c["store"], c["url"], c["image"]))
                added += 1
    flash(_t("starter_added", current_lang()).format(n=added), "ok")
    return redirect(url_for("items_manage") + "#mine")


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
        if not name:
            flash(_t("form_error", lang), "err")
        else:
            db.execute(
                "INSERT INTO shana_requests (name, email, whatsapp, arrival, city,"
                " address, bundle_slug, notes) VALUES (?,?,?,?,?,?,?,?)",
                (name, (f.get("email") or "").strip()[:200],
                 (f.get("whatsapp") or "").strip()[:40],
                 (f.get("arrival") or "").strip()[:40],
                 (f.get("city") or "").strip()[:120],
                 (f.get("address") or "").strip()[:300],
                 (f.get("bundle") or "custom")[:60],
                 (f.get("notes") or "").strip()[:2000]))
            send_mail(
                NOTIFY_EMAIL,
                f"New shana rishonah lead: {name} ({f.get('bundle', 'custom')})",
                f"Name: {name}\nWhatsApp: {f.get('whatsapp', '')}\nEmail: {f.get('email', '')}\n"
                f"Arrival: {f.get('arrival', '')}\nCity: {f.get('city', '')}\n"
                f"Address: {f.get('address', '')}\nBundle: {f.get('bundle', '')}\n"
                f"Notes: {f.get('notes', '')}\n\nAdmin: {ext_url('admin_home')}")
            flash(_t("sr_done_t", lang) + " " + _t("sr_done_b", lang), "ok")
            return redirect(url_for("shana"))
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    return render_template("shana.html", bundles=bundles)


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
        no_affiliate=db.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE active=1 AND url=''").fetchone()[0],
    )
    recent = db.execute("SELECT * FROM registries ORDER BY created_at DESC LIMIT 15").fetchall()
    mail_stats = ob_mail.outbox_counts(db)
    return render_template("admin.html", leads=leads, msgs=msgs, stats=stats, recent=recent,
                           mail_stats=mail_stats)


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


@app.route("/admin/lead/<int:lead_id>/status", methods=["POST"])
@admin_required
def admin_lead_status(lead_id):
    status = request.form.get("status", "new")
    if status in ("new", "contacted", "quoted", "accepted", "arranging", "completed", "cancelled"):
        get_db().execute("UPDATE shana_requests SET status=? WHERE id=?", (status, lead_id))
    return redirect(url_for("admin_home"))


@app.route("/admin/message/<int:msg_id>/resolve", methods=["POST"])
@admin_required
def admin_msg_resolve(msg_id):
    get_db().execute("UPDATE messages SET resolved=1 WHERE id=?", (msg_id,))
    return redirect(url_for("admin_home"))


@app.route("/admin/catalog")
@admin_required
def admin_catalog():
    rows = get_db().execute("SELECT * FROM catalog_items ORDER BY category, sort").fetchall()
    return render_template("admin_catalog.html", rows=rows)


@app.route("/admin/catalog/new", methods=["GET", "POST"])
@app.route("/admin/catalog/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_catalog_edit(item_id=None):
    db = get_db()
    row = db.execute("SELECT * FROM catalog_items WHERE id=?", (item_id,)).fetchone() if item_id else None
    if item_id and not row:
        abort(404)
    if request.method == "POST":
        f = request.form
        try:
            price = max(0, int(f.get("price_nis") or 0))
        except ValueError:
            price = 0
        vals = ((f.get("name") or "").strip()[:200], (f.get("name_he") or "").strip()[:200],
                (f.get("brand") or "").strip()[:80],
                f.get("category") if f.get("category") in CATEGORIES else "home",
                price, (f.get("store") or "").strip()[:120],
                (f.get("url") or "").strip()[:500], (f.get("image") or "").strip()[:500],
                1 if f.get("active") else 0, 1 if f.get("featured") else 0,
                int(f.get("sort") or 0))
        if not vals[0]:
            flash("Name is required", "err")
        elif row:
            db.execute("UPDATE catalog_items SET name=?, name_he=?, brand=?, category=?,"
                       " price_nis=?, store=?, url=?, image=?, active=?, featured=?, sort=?"
                       " WHERE id=?", vals + (item_id,))
            return redirect(url_for("admin_catalog"))
        else:
            db.execute("INSERT INTO catalog_items (name, name_he, brand, category, price_nis,"
                       " store, url, image, active, featured, sort, seed_key)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vals + (None,))
            return redirect(url_for("admin_catalog"))
    return render_template("admin_catalog_form.html", row=row)


@app.route("/admin/catalog/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_catalog_delete(item_id):
    get_db().execute("DELETE FROM catalog_items WHERE id=?", (item_id,))
    return redirect(url_for("admin_catalog"))


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


# ---------------------------------------------------------------- misc
@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nDisallow: /admin\nDisallow: /dashboard\nDisallow: /g/\n"
        f"Sitemap: {ext_url('sitemap')}\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    pages = [ext_url(p) for p in
             ("index", "how", "find", "catalog_page", "shana", "about", "contact", "privacy")]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in pages:
        xml.append(f"<url><loc>{u}</loc></url>")
        xml.append(f"<url><loc>{u}{'&' if '?' in u else '?'}lang=he</loc></url>")
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
