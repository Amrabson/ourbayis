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
- `templates/` — base.html has the inline SVG icon sprite (nav icons + 6 category + 27 item illustrations), nav, footer. `_cards.html` holds the shared gift-card macros. Public pages use `t()`; admin pages are English-only.
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
  For the Claude Browser preview use `run_dev.py` (launch config **`ourbayis-v3`** in the user-level
  `~/.claude/launch.json`) — it forces a throwaway DB in %TEMP% so the preview can't migrate the repo's
  `ourbayis.db`. The old `ourbayis` launch entry runs `app.py` on the real DB: don't use it.
- Env vars: `OB_SECRET_KEY` (required if `OB_SECURE_COOKIES`/`OB_ENV=production`; otherwise a dev
  key persists in gitignored `instance/dev_secret.txt`), `OB_SECURE_COOKIES=1` (prod),
  `OB_TRUST_PROXY=1` (enables ProxyFix — only set this behind a real proxy), `OB_BASE_URL` (used
  for every external link — emails, sitemap, robots, share links — via `ext_url()`),
  `OB_ALLOWED_HOSTS` (comma list; other Host headers get 400), `OB_DB_PATH` (mainly for tests),
  `OB_RATES`/`OB_RATES_DATE` (JSON rates, e.g. `{"USD":3.7,"GBP":4.75}`; drives the header currency
  toggle, the short `estimate_label()` "≈ $59" on cards and the one-per-page `estimate_note()` footnote —
  ILS is always the reference; `OB_ILS_PER_USD`/`usd()` are legacy and no longer used by templates), `OB_WHATSAPP`; email (optional): `OB_SMTP_HOST/PORT/USER/PASS`
  + `OB_NOTIFY_EMAIL` — without SMTP, mail still queues in `mail_outbox` (visible via
  `manage.py stats`) but nothing sends.
- `manage.py`: `create-admin`, `backup`, `send-mail` (flush the outbox — run on a schedule),
  `expire-claims` (run daily), `check` (integrity + config sanity, exit 1 on problems), `stats`.
- Deploy target: PythonAnywhere like BashertBench. See [DEPLOY_AI.md](DEPLOY_AI.md) for the full walkthrough — `passenger_wsgi.py` is the ready-to-paste WSGI file (fix `project_home`, real `OB_SECRET_KEY`, `OB_BASE_URL` before using). Static mapping `/static/` → project static dir. Importing `app.py` runs migrations + catalog seed-sync automatically on first load; you still need `manage.py create-admin` once.

## Catalog rules (v3 phase 3)
- `seed_catalog.json` items carry a stable `seed_key` (slugified name), `kind` ('product' when a
  real brand is known, 'idea' for generic items), `featured` (promotional placement — homepage +
  `/registry/items/starter`'s old one-click no longer uses this), `starter_group`
  ('first_week'|'kitchen'|'shabbos'|'bedbath'|'appliances', used by the grouped starter-pack
  picker), and `price_status`/`price_checked_at`/`price_source` ('verified' for the 55 items
  CHANGELOG_AI.md's v1.7–v2.3 entries confirmed against real Israeli listings; 'estimate' otherwise).
- **Seed sync** (`ob_db.seed_sync()`, called automatically on every app import, and via
  `manage.py seed-sync`): matches by `seed_key`. A DB row with that `seed_key` is left untouched.
  A legacy row (no `seed_key`, `NULL`) matched by exact `name` gets its `seed_key` set and ONLY
  its still-default metadata fields (`kind`/`starter_group`/`price_status`/`price_checked_at`/
  `price_source`) filled — never name/price/url/store/brand/active/featured. A `seed_key` with no
  DB match at all is inserted fresh (including `featured`/`starter_group`, so a brand-new install
  gets a working starter pack and homepage strip immediately). Inactive (retired) rows are matched
  by `seed_key` like any other row, so they're never re-inserted after being retired in
  `/admin/catalog`.
- **Explicit overwrite** (`manage.py seed-sync --fields price_nis,url,... --apply`) is the *only*
  way a seed value overwrites an existing DB value — always a dry run (prints a diff table) unless
  `--apply` is passed.
- **Card rules** (`item_routes(item, pay_links)` in app.py, exposed as the Jinja global
  `gift_routes(item)`): `store` is true iff the item has a `url`; `cash` is true iff the couple has
  at least one working pay link — this is true even for `kind='idea'` rows (an idea still needs
  money, it just has no store link to click through). Neither → the design agent's templates show
  it as an idea with no button.
- **`/go/c/<catalog_id>`** and **`/go/i/<item_id>`**: the only sanctioned click-through routes.
  Redirect to the DB-stored `url` (re-validated with `validate_url`, never trusts a query string —
  no open redirect), increments `clicks`, logs the `handoff_click` funnel event. `go_url(item)` is
  the Jinja global that builds these URLs — templates should never link `item['url']` directly.
- **`manage.py refresh-registry-links`**: for `registry_items` with a `catalog_id`, copies
  url/image/store/brand from the current catalog row onto the registry item, for whichever of
  those fields is NOT in the item's `overrides` (comma list, set by `/registry/items/<id>/edit`
  whenever the couple manually changes a normally-inherited field). Never touches name/price/qty/
  priority/note or any claim. Dry run by default.

## Key flows added in v3 phase 3
- **Pending add while logged out**: `/registry/items/add` is no longer `@login_required` — if
  there's no `uid`, it stashes `catalog_id` in `session['pending_add']` (capped at 50) and sends
  the visitor to `/signup` with a flash. `signup()` must carry `pending_add` across its
  `session.clear()` (it rotates the session on account creation) — this was a real bug fixed
  during phase 3 testing (see CHANGELOG_AI.md). `_save_registry()`'s insert branch applies the
  queued ids via `_apply_pending_add()` once the new registry exists, then clears the session key.
- **Starter pack picker** (`/registry/items/starter`, GET shows groups + checkboxes, POST adds only
  what was checked, at the chosen qty): replaces the old "add all 8 featured items" one-click —
  `featured` is promotional homepage placement, not a curated starter list. Groups come straight
  from `catalog_items.starter_group`.
- **Item edit** (`/registry/items/<id>/edit`): full field edit; changing a normally-inherited field
  (url/image/store/brand/name) records it in `registry_items.overrides` so `refresh-registry-links`
  never clobbers it later.
- **Dashboard checklist**: computed live from registry state each request (details filled / ≥5
  usable gifts / a payment link if any gift has no store url / visibility reviewed [stamped in
  `preferences_json.visibility_reviewed_at` whenever the registry form is saved] / previewed
  [`?preview=1` by the owner stamps `previewed_at`] / shared [`views>0` or a
  `POST /dashboard/shared` beacon the share buttons fire, stamping `shared_at`]). Disappears once
  every step is done.
- **Visibility** (`registries.visibility`: draft|unlisted|public): draft renders `error.html` (404)
  with `draft_not_published=True` for non-owners; owner still sees it with `is_owner`/`is_preview`
  context. `find`/`sitemap.xml` only ever include `visibility='public'` rows. `noindex` is computed
  server-side per request (admin/dashboard/account/auth endpoints always; registries by
  `visibility != 'public'`) and passed as a context var — **base.html itself doesn't render a
  `<meta name="robots">` tag yet**, that's the design agent's to add (base.html is out of this
  agent's file ownership).
- **Account** (`/account`, `/account/export.json`, `/account/delete`): self-service data export
  (own data only, no `pw_hash`/`token_hash`) and account deletion (current-password confirm,
  cascades registry→items→claims via `ON DELETE CASCADE`, purges the user's `mail_outbox` rows,
  leaves `funnel_events` alone since those carry no PII).
- **Concierge admin** (`/admin/lead/<id>`): internal notes, next action + date, a dedup hint (other
  leads sharing the same email/whatsapp), and a cost-breakdown editor
  (goods/delivery/assembly/labour/contingency/quoted_price) stored in `shana_requests.quote_json`
  with `total_cost`/`profit`/`margin_pct` computed server-side on every save.
- **Admin catalog**: search/category/price-status/missing-url/missing-image filters, queue counts,
  CSV export (`/admin/catalog.csv`) and import (`/admin/catalog/import` — always shows a dry-run
  diff first; a second POST with the *same re-uploaded file* and `mode=apply` writes; nothing is
  ever trusted from a session-stored payload). "Delete" is really "Retire" (`active=0`) whenever
  any `registry_items` row still references the catalog item; otherwise a real `DELETE`.
- **Admin outbox** (`/admin/outbox`): masked addresses (`a***@x.com`) — the body is never shown.
  Failed rows get a one-click "Retry" that resets them to `status='queued'`.

## Visual system (v3 phase 2 + integration)
Parchment/navy/gold + Bellefair/Assistant kept. Glass surfaces (`.glass`, `.glass-panel`: translucent
card + `backdrop-filter`, solid `@supports not` fallback) on the sticky header, hero card, registry hero,
guest status card, modals. CSS-only motion: drifting hero light field, skyline draw-in, gold foil shimmer
on `.btn-gold`, `.reveal` section fade-ins — all off under `prefers-reduced-motion`. Category SVG
illustrations (`#ill-*` symbols in base.html) fill the reserved 4:3 `.gift-ph` box when an item has no
image; `<img>` errors fall back to the illustration via app.js. All JS lives in `static/app.js`
(CSP `script-src 'self'`): modal open/close/focus-return, `data-copy` with prompt fallback,
`data-autosubmit`, `data-confirm`, `data-print`, `data-share-beacon`, category chip filter.
Gift grid: auto-fill ≥240px, 2 columns ≤520px, 1 column ≤430px. Prices/URLs/emails wrapped in
`.bdi`/`<bdi>` for Hebrew. Header shows a currency toggle only when `OB_RATES` configures a second currency.

## Shared gift presentation (review pass 2026-09-17)
- `templates/_cards.html` — the only place a gift card / price line / facts block / status label is
  defined; import `with context`. Used by index (mode `link`), catalog (`catalog`), registry
  (`registry`), `/sample` (`sample`), the claim dialog, guest page and items page.
- `item_claim_breakdown(reg_id)` → `{item_id: {reserved, reported, received, committed}}` (expired
  reservations excluded); `item_claim_counts()` is a wrapper. `gift_status(item, breakdown)` returns
  `state` ∈ open|partial|reserved|reported|received and `left`. Templates never compute status themselves.
- Registry items carry `model`/`availability`/`notes*` copied from the catalog (migration 18).
  `refresh-registry-links` refreshes url/image/store/brand/model/notes unless overridden, and
  `availability` always. It never touches price/qty/priority/note or any claim amount.
- `featured_items(db, limit)` orders unavailable and url-less items last. `sample_registry(db)` builds
  the one sample fixture from it (synthetic states, no pay links, negative ids); `/sample` renders
  `registry.html` with `is_sample=True`; the homepage preview uses the same fixture.
- `illustration_for(item)` picks an `ill-*` symbol from `_ILLUSTRATION_RULES` (keyword on name/seed_key)
  or the category drawing. No catalog row has a photo today.
- Catalog: `CATALOG_PRICE_BANDS`, `CATALOG_SORTS`, `CATALOG_PAGE_SIZE=24`; filters live in the URL.
- Shana packages: `PACKAGE_TIERS` in app.py (per tier delivery/setup/appliances/lead weeks) + i18n
  `pkg_*`/`shana_term_*`; goods lists stay in `bundles.items_text` (admin-editable, insert-only sync).
- `fmt_date(iso)` Jinja global for human dates (EN/HE); stored dates stay ISO.
- Tooling: `tools/screenshots.py` (headless Chrome; needs ≥520px windows, phone checks in the Browser
  pane), `tools/render_private.py` (logged-in pages on a temp DB), `tools/export_static.py` (docs/).

## SEO / privacy facts (current)
`canonical_url`/`alt_urls`/`noindex` come from the context processor: canonical = path only (+`?lang=he`
for the Hebrew variant), hreflang en/he/x-default, `noindex` for admin/dashboard/account/edit/`/g/` pages,
non-public registries, and any page with filter/search params. JSON-LD: Organization+WebSite (home),
FAQPage (how-it-works). `static/og.png` generated by `tools/make_og.py`. robots.txt disallows
/admin, /dashboard, /g/ — never /r/. Sitemap: public pages (+`?lang=he`) and `visibility='public'`
registries only. Guest names/emails/messages never appear in public HTML; the public registry page
shows only counts.
