# OurBayis — Project Knowledge

**Read this first instead of re-scanning the repo.** Keep this file, CHANGELOG_AI.md, and TODO_AI.md updated when making changes.

## What it is
Gift registry site for couples building a home in Israel (main crowd: Americans and American-Israelis, chassanim/kallahs, olim). Fully bilingual EN/HE with RTL. Plus a **Shana Rishonah setup service**: newlyweds landing in Israel request a package (basics ordered/delivered/set up before arrival) — this is a concierge/lead-gen business, coordinated manually over WhatsApp.

## Money model (owner is South African — NO Stripe **for the site itself**)
- **The site never touches guest money.** Store gifts: guests buy directly at the store via (affiliate) links. Cash gifts: go to the couple's **own** payment links — `paypal_url`, `stripe_url` (their Stripe Payment Link — allowed, it's the couple's account not ours), `bit_url` (Bit/PayBox for Israeli guests). `reg_pay_links()` builds the button list.
- **Cash-for-item flow:** in the gift modal guests choose "buy myself at the store" or "send the couple the money for it" (radio `give=cash`). The cash path creates a claim (kind='cash', item_id set, amount=price×qty) and shows a pay banner (`?pc=<claim_id>`) with the couple's payment buttons — so guests never have to face an Israeli store checkout.
- Revenue: (1) affiliate links on catalog items (Amazon Associates etc. — admin pastes URLs), (2) ad slots (`ads` table, one random active ad in a band above the footer, sold manually), (3) Shana Rishonah concierge margin — client pays owner by PayPal or Israeli (Leumi) bank transfer, owner orders the goods.

## Stack & layout (v3 phase 1)
Flask 3 + SQLite, server-rendered Jinja2, no build step. Same architecture as BashertBench.
- `app.py` — routes, admin, CSRF (session token + form field), context processor. DB `ourbayis.db`
  (or `OB_DB_PATH` if set) lives next to app.py, auto-migrated + seeded on first run via `init_db()`.
- `ob_db.py` — `connect(path)` (Row factory, `isolation_level=None`/autocommit, FK on, 10s busy
  timeout), `MIGRATIONS` list + `migrate(db)` (tracked in `schema_migrations`, each migration
  idempotent via `has_column`/`IF NOT EXISTS`), `write_txn(db)` (BEGIN IMMEDIATE + bounded retry
  on SQLITE_BUSY, reentrant-safe so a route can call `track()` from inside its own txn), `backup()`.
- `ob_security.py` — `env_bool`, `safe_next` (open-redirect guard for login `next`),
  `same_origin_referrer` (for `/lang`, `/currency`), `validate_url`, `classify_pay_url` (exact-host
  allowlist for PayPal/Stripe/Bit/PayBox, raises `ValueError('pay_url_bad...')`), token helpers,
  `rate_limited(db, bucket, key, limit, per)` backed by `rate_events`.
- `ob_mail.py` — `mail_outbox` table; `enqueue()` always queues, fires a best-effort background
  send only if SMTP env vars are set; `attempt()` handles backoff/failure; `flush()` is what
  `manage.py send-mail` calls. Never logs a message body.
- `ob_money.py` — everything in integer minor units (agorot/cents). `to_minor`, `fmt_minor`,
  `parse_legacy_amount` (strict — used only for the one-time migration of old free-text amounts),
  `RATES`/`CURRENCIES` from `OB_RATES` env, `estimate()`.
- `manage.py` — CLI: `create-admin`, `backup`, `send-mail`, `expire-claims`, `check`, `stats`
  (seed-sync / refresh-registry-links are Phase 3 stubs).
- `static/app.js` — every bit of site JS (CSP is `script-src 'self'`, no inline scripts anywhere):
  modal open/close, copy-link, hamburger nav, chip filter, `data-autosubmit`, `data-confirm`
  (on a button — only that submitter needs confirming — or a whole `<form>`), `data-print`.
- `tests/` — pytest; `conftest.py` points `OB_DB_PATH` at a tmp file and re-imports `app` fresh
  per test, so the real `ourbayis.db` is never touched by the suite.
- `i18n.py` — `T_EN`/`T_HE` dicts, `t(key, lang)` (falls back EN → key), `CATEGORIES` (slug → icon/EN/HE), `EVENT_TYPES`.
- `seed_catalog.json` — ~117 curated catalog items incl. quality/size variants (Israel-specific: platta, meicham, Shabbos lamp, sponja set, Shas set, sukkah…) + 3 shana bundles. **Seed-sync**: on every start, items whose `name` isn't in the DB are inserted (existing rows untouched — retire seed items by marking inactive in admin, not deleting).
- `templates/` — base.html has inline SVG icon sprite, nav, footer, modal/copy/hamburger JS. Public pages use `t()`; admin pages are English-only.
- `static/style.css` — "wedding invitation" aesthetic: parchment `#faf6ec`, navy `#223354`, gold `#a5762a`/`#c9a24a`; hairline borders + `3px double` gold frames on highlight panels; Bellefair (display serif) + Assistant (body) from Google Fonts (both cover Hebrew). RTL via `dir=rtl` on `<html>` + CSS logical properties. Homepage hero: gold line-art Jerusalem skyline + chuppah SVG with twinkling lights (`.tw` animation).

## Data model (schema v3, see ob_db.py MIGRATIONS + SPEC_V3.md)
`users` (couples, `session_ver` for logout-everywhere) → `registries` (1 per user, unique `slug`,
bilingual fields `*_he`, `paypal_url`/`stripe_url`/`bit_url`, `visibility` draft|unlisted|public,
`display_currency`, `delivery_note*`) → `registry_items` (copied from `catalog_items` or custom;
`qty_wanted`, `priority`, `archived` — set instead of deleted once an item has claims) → `claims`
(guest reservations; full lifecycle — see below — plus `amount_minor`/`currency` in integer minor
units, `token_hash` for the guest's recovery link, `idempotency_key` for one-claim-per-form-key,
`legacy=1` on rows migrated from the pre-v3 free-text `amount` field). `claim_events` is the audit
trail (event/actor/note per status change). Also: `catalog_items`, `bundles`, `shana_requests`
(leads), `messages`, `ads`, `admins` (`session_ver` too), `password_resets`, `rate_events`,
`mail_outbox`, `funnel_events` (no-PII daily counters), `schema_migrations`.

## Gift lifecycle (see SPEC_V3.md "Gift lifecycle" for the full spec)
`claims.status`: reserved → reported → received, or → cancelled/expired. Committed quantity for
an item = `SUM(qty)` of claims in (reserved, reported, received), excluding reserved claims whose
`expires_at` has passed (those free the quantity back up — `manage.py expire-claims` flips them to
'expired' for the dashboard, but availability is also computed lazily so nothing over-commits even
before that runs). `POST /r/<slug>/claim/<item_id>` runs inside `ob_db.write_txn` — re-reads the
item, recomputes committed qty, validates, snapshots the price, generates a recovery token (only
the sha256 hash is stored), and redirects to `/g/<token>` (no account needed). A repeated POST with
the same `form_key` hits the unique partial index on `claims.idempotency_key` and is treated as
"already recorded" rather than creating a second claim (see CHANGELOG_AI.md "Decisions" for why it
doesn't try to recover the original token). Owner actions live under `/claim/<id>/...` (confirm,
cancel — `/release` is kept as an alias route to the same handler, thanked).

## Key flows
- Public catalog: `/catalog` (no login) — browse/filter/search all active catalog items; logged-in couples add directly (`items_add?back=catalog`), visitors see signup CTA. Global catalog is edited ONLY in `/admin/catalog`.
- Guest gifting: `/r/<slug>` → "Gift this" opens `<dialog>` → POST claim → redirected to `/g/<token>`, a no-login guest manage page with status, payment buttons (provider-labelled via `classify_pay_url`), the store link, and a "save this link" copyable URL. From there: report (bought/sent it) or cancel.
- Cash gift: general cash modal takes a numeric amount + currency select (not free text) → claim kind='cash', status='reported' (a self-report, never phrased as "sent you money" or "payment verified").
- Language: `/lang/<code>` and `/currency/<code>` redirect to `ob_security.same_origin_referrer()` (never the raw `Referer`); `pick(row, field)` prefers `field_he` in Hebrew.
- i18n rule: **write "Shabbos" not "Shabbat"** in English content (same audience convention as BashertBench).

## Auth & admin
- Couples: email+password (werkzeug hashes), session `uid` + `sv` (must match `users.session_ver`
  or the session is treated as logged out — bumped by password reset/change and by any payment-link
  edit). One registry per user. Password reset: `password_resets` table, single-use token (hash
  stored), 2h expiry, invalidates sibling tokens, bumps `session_ver`. Without SMTP configured,
  `/forgot` explains that and points to `/contact`.
- Anti-spam: hidden `website` honeypot field on all public forms; `is_spam()` silently redirects bots. Registry `views` counter increments on guest (non-owner) page loads.
- Admin: `/admin/login` — **no default admin anymore**; create one with `python manage.py
  create-admin <username>` (12+ char password). The login page shows that command when the
  `admins` table is empty. Session `admin` + `admin_sv`. Admin password change requires the current
  password. Manages: shana leads, messages, catalog CRUD (`/admin/catalog`), bundles, ads, mail
  outbox counts.
- Payment-link edits (`paypal_url`/`stripe_url`/`bit_url` on the registry form) require the
  couple's current password whenever any of the three actually changes — this is where guest
  money gets redirected, so it's treated like a security-sensitive change.
- CSRF: session token + hidden form field, checked on every POST. Logout (both couple and admin)
  is POST-only.

## Running / deploying
- Local: `python app.py` → port **5001** (BashertBench uses 5000). Debug via `OB_DEBUG=1`.
- Env vars: `OB_SECRET_KEY` (required if `OB_SECURE_COOKIES`/`OB_ENV=production`; otherwise a dev
  key persists in gitignored `instance/dev_secret.txt`), `OB_SECURE_COOKIES=1` (prod),
  `OB_TRUST_PROXY=1` (enables ProxyFix — only set this behind a real proxy), `OB_BASE_URL` (used
  for every external link — emails, sitemap, robots, share links — via `ext_url()`),
  `OB_ALLOWED_HOSTS` (comma list; other Host headers get 400), `OB_DB_PATH` (mainly for tests),
  `OB_RATES`/`OB_RATES_DATE` (JSON rates for non-ILS cash-gift estimates), `OB_ILS_PER_USD`
  (legacy ~$ display on catalog cards), `OB_WHATSAPP`; email (optional): `OB_SMTP_HOST/PORT/USER/PASS`
  + `OB_NOTIFY_EMAIL` — without SMTP, mail still queues in `mail_outbox` (visible via
  `manage.py stats`) but nothing sends.
- `manage.py`: `create-admin`, `backup`, `send-mail` (flush the outbox — run on a schedule),
  `expire-claims` (run daily), `check` (integrity + config sanity, exit 1 on problems), `stats`.
- Deploy target: PythonAnywhere like BashertBench. See [DEPLOY_AI.md](DEPLOY_AI.md) for the full walkthrough — `passenger_wsgi.py` is the ready-to-paste WSGI file (fix `project_home`, real `OB_SECRET_KEY`, `OB_BASE_URL` before using). Static mapping `/static/` → project static dir. Importing `app.py` runs migrations + catalog seed-sync automatically on first load; you still need `manage.py create-admin` once.
