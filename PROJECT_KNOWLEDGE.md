# OurBayis — Project Knowledge

**Read this first instead of re-scanning the repo.** Keep this file, CHANGELOG_AI.md, and TODO_AI.md updated when making changes.

## What it is
Gift registry site for couples building a home in Israel (main crowd: Americans and American-Israelis, chassanim/kallahs, olim). Fully bilingual EN/HE with RTL. Plus a **Shana Rishonah setup service**: newlyweds landing in Israel request a package (basics ordered/delivered/set up before arrival) — this is a concierge/lead-gen business, coordinated manually over WhatsApp.

## Money model (owner is South African — NO Stripe **for the site itself**)
- **The site never touches guest money.** Store gifts: guests buy directly at the store via (affiliate) links. Cash gifts: go to the couple's **own** payment links — `paypal_url`, `stripe_url` (their Stripe Payment Link — allowed, it's the couple's account not ours), `bit_url` (Bit/PayBox for Israeli guests). `reg_pay_links()` builds the button list.
- **Cash-for-item flow:** in the gift modal guests choose "buy myself at the store" or "send the couple the money for it" (radio `give=cash`). The cash path creates a claim (kind='cash', item_id set, amount=price×qty) and shows a pay banner (`?pc=<claim_id>`) with the couple's payment buttons — so guests never have to face an Israeli store checkout.
- Revenue: (1) affiliate links on catalog items (Amazon Associates etc. — admin pastes URLs), (2) ad slots (`ads` table, one random active ad in a band above the footer, sold manually), (3) Shana Rishonah concierge margin — client pays owner by PayPal or Israeli (Leumi) bank transfer, owner orders the goods.

## Stack & layout
Flask 3 + SQLite, server-rendered Jinja2, no build step. Same architecture as BashertBench.
- `app.py` — everything: schema, security (CSRF token in session + form, per-IP rate limits, CSP headers), routes, admin. DB `ourbayis.db` lives next to app.py, auto-created + seeded on first run.
- `i18n.py` — `T_EN`/`T_HE` dicts, `t(key, lang)` (falls back EN → key), `CATEGORIES` (slug → icon/EN/HE), `EVENT_TYPES`.
- `seed_catalog.json` — ~117 curated catalog items incl. quality/size variants (Israel-specific: platta, meicham, Shabbos lamp, sponja set, Shas set, sukkah…) + 3 shana bundles. **Seed-sync**: on every start, items whose `name` isn't in the DB are inserted (existing rows untouched — retire seed items by marking inactive in admin, not deleting).
- `templates/` — base.html has inline SVG icon sprite, nav, footer, modal/copy/hamburger JS. Public pages use `t()`; admin pages are English-only.
- `static/style.css` — "wedding invitation" aesthetic: parchment `#faf6ec`, navy `#223354`, gold `#a5762a`/`#c9a24a`; hairline borders + `3px double` gold frames on highlight panels; Bellefair (display serif) + Assistant (body) from Google Fonts (both cover Hebrew). RTL via `dir=rtl` on `<html>` + CSS logical properties. Homepage hero: gold line-art Jerusalem skyline + chuppah SVG with twinkling lights (`.tw` animation).

## Data model (all in app.py SCHEMA)
`users` (couples) → `registries` (1 per user, unique `slug`, bilingual fields `*_he`, `paypal_url`, `is_public`) → `registry_items` (copied from `catalog_items` or custom; `qty_wanted`, `priority`) → `claims` (guest reservations; `kind='item'|'cash'`, `thanked` flag for thank-you tracking). Separate: `catalog_items`, `bundles`, `shana_requests` (leads, status new/contacted/done), `messages`, `ads`, `admins`.

## Key flows
- Public catalog: `/catalog` (no login) — browse/filter/search all active catalog items; logged-in couples add directly (`items_add?back=catalog`), visitors see signup CTA. Global catalog is edited ONLY in `/admin/catalog`.
- Guest gifting: `/r/<slug>` → "Gift this" opens `<dialog>` → POST claim (name/email/message/qty) → redirected back with a "now buy it at the store" banner if the item has a URL. Claim = reservation only; purchase happens at the store.
- Cash gift: modal → couple's PayPal link (new tab) + optional "let them know" form → claim kind='cash'.
- Language: `/lang/<code>` sets session; `pick(row, field)` prefers `field_he` in Hebrew.
- i18n rule: **write "Shabbos" not "Shabbat"** in English content (same audience convention as BashertBench).

## Auth & admin
- Couples: email+password (werkzeug hashes), session `uid`. One registry per user. Password reset at `/forgot` — itsdangerous signed token (salt `pw-reset`, 2h expiry) emailed via `send_email()`; without SMTP it redirects to contact with an explanation.
- Anti-spam: hidden `website` honeypot field on all public forms; `is_spam()` silently redirects bots. Registry `views` counter increments on guest (non-owner) page loads.
- Admin: `/admin/login`, default **admin / changeme123 — MUST change after first login** (form on admin dashboard). Session `admin`. Manages: shana leads (status dropdown), messages, catalog CRUD (`/admin/catalog`), bundles, ads.

## Running / deploying
- Local: `python app.py` → port **5001** (BashertBench uses 5000). Debug via `OB_DEBUG=1`.
- Env vars: `OB_SECRET_KEY` (required in prod), `OB_SECURE_COOKIES=1` (prod), `OB_ILS_PER_USD` (default 3.7, used for ~$ estimates), `OB_WHATSAPP`; email (optional): `OB_SMTP_HOST/PORT/USER/PASS` + `OB_NOTIFY_EMAIL` (owner inbox for leads/messages) — `send_email()` no-ops without them and runs in a daemon thread when set.
- Deploy target: PythonAnywhere like BashertBench. See [DEPLOY_AI.md](DEPLOY_AI.md) for the full walkthrough — `passenger_wsgi.py` is the ready-to-paste WSGI file (fix `project_home` + real `OB_SECRET_KEY` before using). Static mapping `/static/` → project static dir. `init_db()` runs at import, safe — creates the DB + seeds the catalog automatically on first load.
