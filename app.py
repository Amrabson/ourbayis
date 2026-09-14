# -*- coding: utf-8 -*-
"""OurBayis — gift registries for building a home in Israel.

Single-file Flask app (same architecture as BashertBench):
server-rendered Jinja2, SQLite next to the app, no build step.
Run:  python app.py   →  http://127.0.0.1:5001
"""
import json
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
import unicodedata
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from i18n import CATEGORIES, EVENT_TYPES, T_EN, cat_label, t as _t

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "ourbayis.db"

BRAND = "OurBayis"
BRAND_HE = "OurBayis"
ILS_PER_USD = float(os.environ.get("OB_ILS_PER_USD", "3.7"))
CONTACT_WHATSAPP = os.environ.get("OB_WHATSAPP", "")  # e.g. 972501234567

# Optional SMTP — leave unset and the site works fine, just without emails.
SMTP_HOST = os.environ.get("OB_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("OB_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("OB_SMTP_USER", "")
SMTP_PASS = os.environ.get("OB_SMTP_PASS", "")
NOTIFY_EMAIL = os.environ.get("OB_NOTIFY_EMAIL", "")  # owner: shana leads + contact msgs

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    SECRET_KEY=os.environ.get("OB_SECRET_KEY", "dev-key-change-in-prod"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("OB_SECURE_COOKIES")),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' https: data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


# ---------------------------------------------------------------- security
@app.after_request
def set_security_headers(resp):
    resp.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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


_RATE: dict = {}


def rate_limited(bucket, limit=20, per=600):
    """True if this IP already made `limit` calls in `per` seconds."""
    now = time.time()
    if len(_RATE) > 2000:  # prune stale entries so the dict can't grow forever
        for k in [k for k, v in _RATE.items() if not v or now - v[-1] > 3600]:
            _RATE.pop(k, None)
    key = (bucket, request.headers.get("X-Real-IP", request.remote_addr))
    hits = [ts for ts in _RATE.get(key, []) if now - ts < per]
    if len(hits) >= limit:
        _RATE[key] = hits
        return True
    hits.append(now)
    _RATE[key] = hits
    return False


def send_email(to, subject, body):
    """Fire-and-forget email in a background thread; no-op without SMTP config."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and to):
        return

    def _send():
        try:
            msg = EmailMessage()
            msg["From"] = SMTP_USER
            msg["To"] = to
            msg["Subject"] = subject
            msg.set_content(body)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
        except Exception:
            app.logger.exception("email send failed (to=%s subject=%s)", to, subject)

    threading.Thread(target=_send, daemon=True).start()


# ---------------------------------------------------------------- database
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL,
  name TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS registries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  title_he TEXT DEFAULT '',
  couple_names TEXT NOT NULL,
  couple_names_he TEXT DEFAULT '',
  event_type TEXT DEFAULT 'wedding',
  event_date TEXT DEFAULT '',
  city TEXT DEFAULT '',
  message TEXT DEFAULT '',
  message_he TEXT DEFAULT '',
  paypal_url TEXT DEFAULT '',
  stripe_url TEXT DEFAULT '',
  bit_url TEXT DEFAULT '',
  is_public INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS registry_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  registry_id INTEGER NOT NULL REFERENCES registries(id) ON DELETE CASCADE,
  catalog_id INTEGER,
  name TEXT NOT NULL,
  name_he TEXT DEFAULT '',
  brand TEXT DEFAULT '',
  category TEXT DEFAULT 'home',
  price_nis INTEGER DEFAULT 0,
  store TEXT DEFAULT '',
  url TEXT DEFAULT '',
  image TEXT DEFAULT '',
  qty_wanted INTEGER DEFAULT 1,
  priority INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  registry_id INTEGER NOT NULL REFERENCES registries(id) ON DELETE CASCADE,
  item_id INTEGER REFERENCES registry_items(id) ON DELETE CASCADE,
  guest_name TEXT NOT NULL,
  guest_email TEXT DEFAULT '',
  message TEXT DEFAULT '',
  qty INTEGER DEFAULT 1,
  kind TEXT DEFAULT 'item',
  amount TEXT DEFAULT '',
  thanked INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS catalog_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  name_he TEXT DEFAULT '',
  brand TEXT DEFAULT '',
  category TEXT DEFAULT 'home',
  price_nis INTEGER DEFAULT 0,
  store TEXT DEFAULT '',
  url TEXT DEFAULT '',
  image TEXT DEFAULT '',
  active INTEGER DEFAULT 1,
  featured INTEGER DEFAULT 0,
  sort INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS bundles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  name_he TEXT DEFAULT '',
  tier TEXT DEFAULT 'basic',
  price_from INTEGER DEFAULT 0,
  description TEXT DEFAULT '',
  description_he TEXT DEFAULT '',
  items_text TEXT DEFAULT '',
  items_text_he TEXT DEFAULT '',
  active INTEGER DEFAULT 1,
  sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS shana_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT DEFAULT '',
  whatsapp TEXT DEFAULT '',
  arrival TEXT DEFAULT '',
  city TEXT DEFAULT '',
  address TEXT DEFAULT '',
  bundle_slug TEXT DEFAULT '',
  notes TEXT DEFAULT '',
  status TEXT DEFAULT 'new',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT DEFAULT '',
  email TEXT DEFAULT '',
  topic TEXT DEFAULT '',
  body TEXT NOT NULL,
  resolved INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  body TEXT DEFAULT '',
  image TEXT DEFAULT '',
  link_url TEXT DEFAULT '',
  active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS admins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    # lightweight migrations for columns added after v1
    for col in ("stripe_url TEXT DEFAULT ''", "bit_url TEXT DEFAULT ''",
                "views INTEGER DEFAULT 0"):
        try:
            db.execute(f"ALTER TABLE registries ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # column already exists
    try:
        db.execute("ALTER TABLE catalog_items ADD COLUMN brand TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE registry_items ADD COLUMN brand TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    for it in json.loads((BASE / "seed_catalog.json").read_text(encoding="utf-8"))["items"]:
        if it.get("brand"):
            db.execute("UPDATE catalog_items SET brand=? WHERE name=? AND brand=''",
                       (it["brand"], it["name"]))
    # items already copied onto a registry before the brand column existed:
    # backfill from their catalog source so existing registries pick it up too
    db.execute("""
        UPDATE registry_items SET brand = (
            SELECT brand FROM catalog_items WHERE catalog_items.id = registry_items.catalog_id
        )
        WHERE (brand IS NULL OR brand = '') AND catalog_id IS NOT NULL
    """)
    # default admin (change the password after first login!)
    cur = db.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        db.execute("INSERT INTO admins (username, pw_hash) VALUES (?, ?)",
                   ("admin", generate_password_hash("changeme123")))
    # sync seed catalog + bundles: insert anything not present yet (matched by
    # name/slug), so new seed items appear without touching existing rows.
    # To retire a seed item, mark it inactive in admin rather than deleting it.
    seed = json.loads((BASE / "seed_catalog.json").read_text(encoding="utf-8"))
    have = {r[0] for r in db.execute("SELECT name FROM catalog_items")}
    for i, it in enumerate(seed["items"]):
        if it["name"] not in have:
            db.execute(
                "INSERT INTO catalog_items (name, name_he, brand, category, price_nis, store,"
                " url, sort) VALUES (?,?,?,?,?,?,?,?)",
                (it["name"], it.get("name_he", ""), it.get("brand", ""),
                 it.get("category", "home"), it.get("price_nis", 0), it.get("store", ""),
                 it.get("url", ""), i))
    for i, b in enumerate(seed.get("bundles", [])):
        db.execute(
            "INSERT OR IGNORE INTO bundles (slug, name, name_he, tier, price_from,"
            " description, description_he, items_text, items_text_he, sort)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (b["slug"], b["name"], b.get("name_he", ""), b.get("tier", "basic"),
             b.get("price_from", 0), b.get("description", ""), b.get("description_he", ""),
             b.get("items_text", ""), b.get("items_text_he", ""), i))
    db.commit()
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
    return bool(re.match(r"^https?://[^\s]+$", u or ""))


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("uid"):
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*a, **kw)
    return wrapper


def user_registry():
    uid = session.get("uid")
    if not uid:
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


def _reset_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="pw-reset")


def reg_pay_links(reg):
    """[(t-key, url), ...] for whichever cash-gift links the couple added."""
    links = []
    for col, key in (("paypal_url", "pay_paypal"), ("stripe_url", "pay_stripe"),
                     ("bit_url", "pay_bit")):
        if col in reg.keys() and reg[col]:
            links.append((key, reg[col]))
    return links


def item_claim_counts(registry_id):
    rows = get_db().execute(
        "SELECT item_id, COALESCE(SUM(qty),1) AS n FROM claims"
        " WHERE registry_id=? AND item_id IS NOT NULL GROUP BY item_id",
        (registry_id,)).fetchall()
    return {r["item_id"]: r["n"] for r in rows}


@app.context_processor
def inject_globals():
    lang = current_lang()
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
        csrf_token=_ensure_csrf(),
        user=current_user(),
        my_registry=user_registry(),
        site_ad=get_db().execute(
            "SELECT * FROM ads WHERE active=1 ORDER BY RANDOM() LIMIT 1").fetchone(),
        whatsapp_contact=CONTACT_WHATSAPP,
        now_year=datetime.now().year,
    )


# ---------------------------------------------------------------- public pages
@app.route("/")
def index():
    db = get_db()
    featured = db.execute(
        "SELECT * FROM catalog_items WHERE active=1 ORDER BY featured DESC, sort LIMIT 8").fetchall()
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    return render_template("index.html", featured=featured, bundles=bundles)


@app.route("/lang/<code>")
def set_lang(code):
    if code in ("en", "he"):
        session["lang"] = code
    return redirect(request.referrer or url_for("index"))


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


@app.route("/find")
def find():
    q = (request.args.get("q") or "").strip()
    results = None
    if q:
        like = f"%{q}%"
        results = get_db().execute(
            "SELECT * FROM registries WHERE is_public=1 AND"
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
            get_db().commit()
            send_email(
                NOTIFY_EMAIL,
                f"OurBayis contact: {(request.form.get('topic') or 'general')}",
                f"From: {request.form.get('name', '')} <{request.form.get('email', '')}>\n\n"
                f"{body[:4000]}\n\nAdmin: {url_for('admin_home', _external=True)}")
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
    if session.get("uid") != reg["user_id"]:
        db.execute("UPDATE registries SET views = views + 1 WHERE id=?", (reg["id"],))
        db.commit()
    days_to_go = None
    try:
        days_to_go = (date.fromisoformat(reg["event_date"]) - date.today()).days
        if days_to_go <= 0:
            days_to_go = None
    except (ValueError, TypeError):
        pass
    items = db.execute(
        "SELECT * FROM registry_items WHERE registry_id=?"
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
    pay_claim = None  # guest chose "send the money" — show the pay-now banner
    if request.args.get("pc"):
        try:
            pay_claim = db.execute(
                "SELECT * FROM claims WHERE id=? AND registry_id=? AND kind='cash'",
                (int(request.args["pc"]), reg["id"])).fetchone()
        except ValueError:
            pass
    return render_template("registry.html", reg=reg, items=items, claimed=claimed,
                           total=total, done=done, bought_item=bought_item,
                           pay_claim=pay_claim, pay_links=reg_pay_links(reg),
                           days_to_go=days_to_go)


@app.route("/r/<slug>/claim/<int:item_id>", methods=["POST"])
def claim_item(slug, item_id):
    if rate_limited("claim", limit=15, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("registry", slug=slug))
    db = get_db()
    reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
    item = db.execute(
        "SELECT * FROM registry_items WHERE id=? AND registry_id=?",
        (item_id, reg["id"] if reg else -1)).fetchone()
    if not reg or not item:
        abort(404)
    name = (request.form.get("guest_name") or "").strip()[:120]
    if not name:
        flash(_t("form_error", current_lang()), "err")
        return redirect(url_for("registry", slug=slug) + f"#item-{item_id}")
    already = item_claim_counts(reg["id"]).get(item_id, 0)
    left = max(item["qty_wanted"] - already, 0)
    try:
        qty = max(1, min(int(request.form.get("qty", 1)), max(left, 1)))
    except ValueError:
        qty = 1
    if left <= 0:
        flash(_t("gifted", current_lang()), "err")
        return redirect(url_for("registry", slug=slug))
    give_cash = request.form.get("give") == "cash" and reg_pay_links(reg)
    amount = f"₪{item['price_nis'] * qty:,}" if (give_cash and item["price_nis"]) else ""
    cur = db.execute(
        "INSERT INTO claims (registry_id, item_id, guest_name, guest_email, message, qty,"
        " kind, amount) VALUES (?,?,?,?,?,?,?,?)",
        (reg["id"], item_id, name,
         (request.form.get("guest_email") or "").strip()[:200],
         (request.form.get("message") or "").strip()[:1000], qty,
         "cash" if give_cash else "item", amount))
    db.commit()
    owner = db.execute("SELECT email FROM users WHERE id=?", (reg["user_id"],)).fetchone()
    if owner:
        kind_txt = f"is sending you the money ({amount})" if give_cash else "reserved"
        send_email(
            owner["email"],
            f"Mazel tov! {name} {'sent a gift' if give_cash else 'reserved a gift'} — {reg['title']}",
            f"{name} {kind_txt}: {item['name']} x{qty}\n"
            f"Message: {(request.form.get('message') or '').strip()[:1000] or '—'}\n\n"
            f"See all your gifts: {url_for('dashboard', _external=True)}")
    if give_cash:
        return redirect(url_for("registry", slug=slug, pc=cur.lastrowid))
    flash(_t("claim_done_t", current_lang()) + " " + _t("claim_done_b", current_lang()), "ok")
    if item["url"]:
        return redirect(url_for("registry", slug=slug, bought=item_id))
    return redirect(url_for("registry", slug=slug))


@app.route("/r/<slug>/cash", methods=["POST"])
def cash_gift(slug):
    if rate_limited("cash", limit=15, per=600):
        abort(429)
    if is_spam():
        return redirect(url_for("registry", slug=slug))
    db = get_db()
    reg = db.execute("SELECT * FROM registries WHERE slug=?", (slug,)).fetchone()
    if not reg:
        abort(404)
    name = (request.form.get("guest_name") or "").strip()[:120]
    if name:
        db.execute(
            "INSERT INTO claims (registry_id, item_id, guest_name, message, qty, kind, amount)"
            " VALUES (?, NULL, ?, ?, 1, 'cash', ?)",
            (reg["id"], name,
             (request.form.get("message") or "").strip()[:1000],
             (request.form.get("amount") or "").strip()[:40]))
        db.commit()
        owner = db.execute("SELECT email FROM users WHERE id=?", (reg["user_id"],)).fetchone()
        if owner:
            send_email(
                owner["email"],
                f"Mazel tov! {name} sent you a cash gift — {reg['title']}",
                f"{name} sent a cash gift"
                f"{' (' + request.form.get('amount', '').strip() + ')' if request.form.get('amount') else ''}.\n"
                f"Message: {(request.form.get('message') or '').strip()[:1000] or '—'}\n\n"
                f"See all your gifts: {url_for('dashboard', _external=True)}")
        flash(_t("reg_cash_recorded", current_lang()), "ok")
    return redirect(url_for("registry", slug=slug))


# ---------------------------------------------------------------- auth
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("uid"):
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
                db.commit()
                session["uid"] = cur.lastrowid
                return redirect(url_for("registry_new"))
            except sqlite3.IntegrityError:
                flash(_t("email_taken", lang), "err")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("uid"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if rate_limited("login", limit=10, per=600):
            abort(429)
        email = (request.form.get("email") or "").strip().lower()
        pw = request.form.get("password") or ""
        row = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row and check_password_hash(row["pw_hash"], pw):
            session["uid"] = row["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") else url_for("dashboard"))
        flash(_t("login_error", current_lang()), "err")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("uid", None)
    return redirect(url_for("index"))


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        if rate_limited("forgot", limit=5, per=3600):
            abort(429)
        lang = current_lang()
        if not SMTP_HOST:
            flash(_t("forgot_noemail", lang), "err")
            return redirect(url_for("contact"))
        email = (request.form.get("email") or "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user:
            token = _reset_serializer().dumps(user["id"])
            send_email(
                email, f"{BRAND} — reset your password",
                "Someone (hopefully you) asked to reset your OurBayis password.\n\n"
                f"Reset it here (link valid for 2 hours):\n"
                f"{url_for('reset_password', token=token, _external=True)}\n\n"
                "If this wasn't you, ignore this email — nothing changes.")
        # same message either way, so the form can't be used to probe for accounts
        flash(_t("forgot_sent", lang), "ok")
        return redirect(url_for("login"))
    return render_template("forgot.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    lang = current_lang()
    try:
        uid = _reset_serializer().loads(token, max_age=7200)
    except (BadSignature, SignatureExpired):
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
            db = get_db()
            db.execute("UPDATE users SET pw_hash=? WHERE id=?",
                       (generate_password_hash(pw), uid))
            db.commit()
            flash(_t("reset_done", lang), "ok")
            return redirect(url_for("login"))
    return render_template("reset.html", token=token)


# ---------------------------------------------------------------- couple dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    reg = user_registry()
    gifts = stats = None
    if reg:
        db = get_db()
        gifts = db.execute(
            "SELECT c.*, ri.name AS item_name, ri.name_he AS item_name_he,"
            " ri.url AS item_url, ri.store AS item_store FROM claims c"
            " LEFT JOIN registry_items ri ON ri.id = c.item_id"
            " WHERE c.registry_id=? ORDER BY c.created_at DESC", (reg["id"],)).fetchall()
        n_items = db.execute("SELECT COUNT(*) FROM registry_items WHERE registry_id=?",
                             (reg["id"],)).fetchone()[0]
        n_claimed = db.execute(
            "SELECT COUNT(DISTINCT item_id) FROM claims WHERE registry_id=? AND item_id IS NOT NULL",
            (reg["id"],)).fetchone()[0]
        n_cash = db.execute("SELECT COUNT(*) FROM claims WHERE registry_id=? AND kind='cash'",
                            (reg["id"],)).fetchone()[0]
        stats = dict(items=n_items, claimed=n_claimed, cash=n_cash,
                     views=reg["views"] if "views" in reg.keys() else 0)
    return render_template("dashboard.html", reg=reg, gifts=gifts, stats=stats)


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
    for col in ("paypal_url", "stripe_url", "bit_url"):
        u = (f.get(col) or "").strip()[:300]
        if u and not u.startswith("http"):
            u = "https://" + u
        pay[col] = u if valid_http_url(u) else ""
    event_type = f.get("event_type") if f.get("event_type") in EVENT_TYPES else "wedding"
    if not title or not couple:
        flash(_t("form_error", lang), "err")
        return render_template("registry_form.html", reg=reg)
    db = get_db()
    fields = (title, (f.get("title_he") or "").strip()[:160],
              couple, (f.get("couple_names_he") or "").strip()[:160],
              event_type, (f.get("event_date") or "").strip()[:40],
              (f.get("city") or "").strip()[:120],
              (f.get("message") or "").strip()[:2000],
              (f.get("message_he") or "").strip()[:2000],
              pay["paypal_url"], pay["stripe_url"], pay["bit_url"],
              1 if f.get("is_public") else 0)
    if reg:
        db.execute(
            "UPDATE registries SET title=?, title_he=?, couple_names=?, couple_names_he=?,"
            " event_type=?, event_date=?, city=?, message=?, message_he=?, paypal_url=?,"
            " stripe_url=?, bit_url=?, is_public=? WHERE id=?", fields + (reg["id"],))
        db.commit()
        return redirect(url_for("dashboard"))
    slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    while db.execute("SELECT 1 FROM registries WHERE slug=?", (slug,)).fetchone():
        slug = slugify(couple)[:40] + "-" + secrets.token_hex(2)
    db.execute(
        "INSERT INTO registries (user_id, slug, title, title_he, couple_names,"
        " couple_names_he, event_type, event_date, city, message, message_he,"
        " paypal_url, stripe_url, bit_url, is_public) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (session["uid"], slug) + fields)
    db.commit()
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
        "SELECT * FROM registry_items WHERE registry_id=? ORDER BY priority DESC, category, id",
        (reg["id"],)).fetchall()
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
            db.commit()
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
            db.commit()
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
    for c in db.execute("SELECT * FROM catalog_items WHERE active=1 AND featured=1"):
        if not db.execute("SELECT 1 FROM registry_items WHERE registry_id=? AND catalog_id=?",
                          (reg["id"], c["id"])).fetchone():
            db.execute(
                "INSERT INTO registry_items (registry_id, catalog_id, name, name_he, brand,"
                " category, price_nis, store, url, image) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (reg["id"], c["id"], c["name"], c["name_he"], c["brand"], c["category"],
                 c["price_nis"], c["store"], c["url"], c["image"]))
            added += 1
    db.commit()
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
    if request.form.get("delete"):
        db.execute("DELETE FROM registry_items WHERE id=?", (item_id,))
    else:
        try:
            qty = max(1, min(int(request.form.get("qty_wanted", 1)), 99))
        except ValueError:
            qty = 1
        db.execute("UPDATE registry_items SET qty_wanted=?, priority=? WHERE id=?",
                   (qty, 1 if request.form.get("priority") else 0, item_id))
    db.commit()
    return redirect(url_for("items_manage"))


@app.route("/claim/<int:claim_id>/release", methods=["POST"])
@login_required
def claim_release(claim_id):
    """Owner frees a reserved gift (guest changed their mind / never bought it)."""
    reg = user_registry()
    db = get_db()
    c = db.execute("SELECT * FROM claims WHERE id=? AND registry_id=?",
                   (claim_id, reg["id"] if reg else -1)).fetchone()
    if not c:
        abort(404)
    db.execute("DELETE FROM claims WHERE id=?", (claim_id,))
    db.commit()
    return redirect(url_for("dashboard"))


@app.route("/claim/<int:claim_id>/thanked", methods=["POST"])
@login_required
def claim_thanked(claim_id):
    reg = user_registry()
    db = get_db()
    c = db.execute("SELECT * FROM claims WHERE id=? AND registry_id=?",
                   (claim_id, reg["id"] if reg else -1)).fetchone()
    if not c:
        abort(404)
    db.execute("UPDATE claims SET thanked=? WHERE id=?", (0 if c["thanked"] else 1, claim_id))
    db.commit()
    return redirect(url_for("dashboard"))


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
            db.commit()
            send_email(
                NOTIFY_EMAIL,
                f"New shana rishonah lead: {name} ({f.get('bundle', 'custom')})",
                f"Name: {name}\nWhatsApp: {f.get('whatsapp', '')}\nEmail: {f.get('email', '')}\n"
                f"Arrival: {f.get('arrival', '')}\nCity: {f.get('city', '')}\n"
                f"Address: {f.get('address', '')}\nBundle: {f.get('bundle', '')}\n"
                f"Notes: {f.get('notes', '')}\n\nAdmin: {url_for('admin_home', _external=True)}")
            flash(_t("sr_done_t", lang) + " " + _t("sr_done_b", lang), "ok")
            return redirect(url_for("shana"))
    bundles = db.execute("SELECT * FROM bundles WHERE active=1 ORDER BY sort").fetchall()
    return render_template("shana.html", bundles=bundles)


# ---------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if rate_limited("admin_login", limit=10, per=600):
            abort(429)
        row = get_db().execute("SELECT * FROM admins WHERE username=?",
                               ((request.form.get("username") or "").strip(),)).fetchone()
        if row and check_password_hash(row["pw_hash"], request.form.get("password") or ""):
            session["admin"] = row["username"]
            return redirect(url_for("admin_home"))
        flash("Wrong credentials", "err")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
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
    return render_template("admin.html", leads=leads, msgs=msgs, stats=stats, recent=recent)


@app.route("/admin/leads.csv")
@admin_required
def admin_leads_csv():
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "whatsapp", "arrival", "city", "address",
                "bundle", "notes", "status", "created_at"])
    for r in get_db().execute("SELECT * FROM shana_requests ORDER BY created_at DESC"):
        w.writerow([r["id"], r["name"], r["email"], r["whatsapp"], r["arrival"],
                    r["city"], r["address"], r["bundle_slug"], r["notes"],
                    r["status"], r["created_at"]])
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=shana-leads.csv"
    return resp


@app.route("/admin/lead/<int:lead_id>/status", methods=["POST"])
@admin_required
def admin_lead_status(lead_id):
    status = request.form.get("status", "new")
    if status in ("new", "contacted", "done"):
        get_db().execute("UPDATE shana_requests SET status=? WHERE id=?", (status, lead_id))
        get_db().commit()
    return redirect(url_for("admin_home"))


@app.route("/admin/message/<int:msg_id>/resolve", methods=["POST"])
@admin_required
def admin_msg_resolve(msg_id):
    get_db().execute("UPDATE messages SET resolved=1 WHERE id=?", (msg_id,))
    get_db().commit()
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
            db.commit()
            return redirect(url_for("admin_catalog"))
        else:
            db.execute("INSERT INTO catalog_items (name, name_he, brand, category, price_nis,"
                       " store, url, image, active, featured, sort)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?,?)", vals)
            db.commit()
            return redirect(url_for("admin_catalog"))
    return render_template("admin_catalog_form.html", row=row)


@app.route("/admin/catalog/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_catalog_delete(item_id):
    get_db().execute("DELETE FROM catalog_items WHERE id=?", (item_id,))
    get_db().commit()
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
            db.commit()
            return redirect(url_for("admin_bundles"))
        else:
            slug = slugify(vals[0])
            db.execute("INSERT INTO bundles (slug, name, name_he, tier, price_from, description,"
                       " description_he, items_text, items_text_he, active, sort)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?,?)", (slug,) + vals)
            db.commit()
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
            db.commit()
        return redirect(url_for("admin_ads"))
    rows = db.execute("SELECT * FROM ads ORDER BY created_at DESC").fetchall()
    return render_template("admin_ads.html", rows=rows)


@app.route("/admin/ads/<int:ad_id>/toggle", methods=["POST"])
@admin_required
def admin_ad_toggle(ad_id):
    get_db().execute("UPDATE ads SET active = 1 - active WHERE id=?", (ad_id,))
    get_db().commit()
    return redirect(url_for("admin_ads"))


@app.route("/admin/ads/<int:ad_id>/delete", methods=["POST"])
@admin_required
def admin_ad_delete(ad_id):
    get_db().execute("DELETE FROM ads WHERE id=?", (ad_id,))
    get_db().commit()
    return redirect(url_for("admin_ads"))


@app.route("/admin/password", methods=["POST"])
@admin_required
def admin_password():
    pw = request.form.get("password") or ""
    if len(pw) >= 10:
        get_db().execute("UPDATE admins SET pw_hash=? WHERE username=?",
                         (generate_password_hash(pw), session["admin"]))
        get_db().commit()
        flash("Password updated", "ok")
    else:
        flash("Password must be at least 10 characters", "err")
    return redirect(url_for("admin_home"))


# ---------------------------------------------------------------- misc
@app.route("/robots.txt")
def robots():
    return app.response_class(
        "User-agent: *\nDisallow: /admin\nDisallow: /dashboard\n"
        f"Sitemap: {url_for('sitemap', _external=True)}\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    pages = [url_for(p, _external=True) for p in
             ("index", "how", "find", "catalog_page", "shana", "about", "contact",
              "privacy", "signup")]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in pages:
        xml.append(f"<url><loc>{u}</loc></url>")
        xml.append(f"<url><loc>{u}{'&' if '?' in u else '?'}lang=he</loc></url>")
    for r in get_db().execute("SELECT slug FROM registries WHERE is_public=1"):
        xml.append(f"<url><loc>{url_for('registry', slug=r['slug'], _external=True)}</loc></url>")
    xml.append("</urlset>")
    return app.response_class("\n".join(xml), mimetype="application/xml")


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


@app.errorhandler(429)
def too_many(_e):
    return "Slow down a little — try again in a few minutes.", 429


init_db()

if __name__ == "__main__":
    app.run(debug=bool(os.environ.get("OB_DEBUG")), port=5001)
