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
- `ob_search.py` — `search_clause(q)` for the catalog and the couple's add-gifts list: every typed
  word must match name/name_he/brand in some spelling (plural folding EN/HE, `SYNONYMS` such as
  shabbat→shabbos, plata→platta, refrigerator→fridge, פלטה→פלטת) or the model line as typed;
  LIKE wildcards escaped, ≤8 words. `rank_expr(q)` orders /catalog results (default sort only):
  name starts with the word → name contains it or a synonym → the rest. Add new everyday words to `SYNONYMS` when a search comes up empty.
- `ob_security.py` — `env_bool`, `safe_next` (open-redirect guard for login `next`),
  `same_origin_referrer` (for `/lang`, `/currency`), `validate_url`, `classify_pay_url` (exact-host
  allowlist for PayPal/Stripe/Bit/PayBox, raises `ValueError('pay_url_bad...')`), token helpers,
  `rate_limited(db, bucket, key, limit, per)` backed by `rate_events`.
- `ob_mail.py` — `mail_outbox` table; `enqueue()` always queues, fires a best-effort background
  send only if SMTP env vars are set; `attempt()` handles backoff/failure; `flush()` is what
  `manage.py send-mail` calls. Never logs a message body. `enqueue()` drops any recipient that
  isn't exactly one address (`ob_security.valid_email`, also used by signup/guest/shana forms) and
  flattens the subject to one line; `attempt()` first takes a 10-minute lease on the row
  (`next_attempt_at`), so the background thread and a scheduled flush never both send it.
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
- `i18n.py` — `T_EN`/`T_HE` dicts, `t(key, lang)` (falls back EN → key), `CATEGORIES` (slug → icon/EN/HE), `EVENT_TYPES`,
  `format_date(iso, lang)`, and `t_count(key, n, lang)`: a string with `{n}` can have `<key>_one` (n == 1) and
  `<key>_two` (n == 2, Hebrew dual) forms per language; `tf(key, lang, n=…)` picks them automatically.
- `seed_catalog.json` — ~117 curated catalog items incl. quality/size variants (Israel-specific: platta, meicham, Shabbos lamp, sponja set, Shas set, sukkah…) + 3 shana bundles. **Seed-sync**: on every start, items whose `name` isn't in the DB are inserted (existing rows untouched — retire seed items by marking inactive in admin, not deleting). Seed items with `"active": false` are inserted retired (retire on a live DB via `seed-sync --fields active`). Bundles: inserted by slug; a text field on an existing bundle is refreshed only while it still equals one of the seed's `replaces` values (the seed's own earlier wording), so admin edits survive.
- `templates/` — base.html has the inline SVG icon sprite (nav icons + 6 category + 27 item illustrations), nav, footer. `_cards.html` holds the shared gift-card macros. Public pages use `t()`; admin pages are English-only.
- `static/style.css` — "wedding invitation" aesthetic: parchment `#faf6ec`, navy `#223354`, gold `#a5762a`/`#c9a24a`; hairline borders + `3px double` gold frames on highlight panels; Bellefair (display serif) + Assistant (body) from Google Fonts (both cover Hebrew). RTL via `dir=rtl` on `<html>` + CSS logical properties. Homepage hero: gold line-art Jerusalem skyline + chuppah SVG with twinkling lights (`.tw` animation). Phones (<=560px): `.gift-card` switches to a compact row (92px thumb beside the text) and filter chips scroll in one line; `.reveal` sections are only hidden under `html.js` (set by app.js).

## Data model (schema v3, see ob_db.py MIGRATIONS + SPEC_V3.md)
`users` (couples, `session_ver` for logout-everywhere, `lang` [m22] — stamped at signup/login and
whenever they pass `?lang=`; `notify_owner()` sends every gift email to the couple in it, with the
registry title/item name in that language and a dashboard link; `claims.lang` [m23] is the guest's
language at reservation — `notify_guest()` emails them when the couple confirms receipt or releases
the reservation, and `remind-claims` uses it; '' (older claims) → both languages) → `registries` (1 per user, unique `slug`,
bilingual fields `*_he`, `paypal_url`/`stripe_url`/`bit_url`, `visibility` draft|unlisted|public,
`display_currency`, `delivery_note*`) → `registry_items` (copied from `catalog_items` or custom;
`qty_wanted`, `priority`, `archived` — set instead of deleted once an item has claims) → `claims`
(guest reservations; full lifecycle — see below — plus `amount_minor`/`currency` in integer minor
units, `token_hash` for the guest's recovery link, `idempotency_key` for one-claim-per-form-key,
`legacy=1` on rows migrated from the pre-v3 free-text `amount` field). `claim_events` is the audit
trail (event/actor/note per status change). Also: `catalog_items`, `bundles`, `shana_requests`
(leads), `messages`, `ads`, `admins` (`session_ver` too), `password_resets`, `rate_events`,
`mail_outbox`, `funnel_events` (no-PII daily counters), `schema_migrations`, `registry_members` /
`registry_invites` [m26] (co-managers, see "Managing it together").

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
- Guest gifting: `/r/<slug>` → "Gift this" opens `<dialog>` → POST claim → redirected to `/g/<token>`, a no-login guest manage page with status, payment buttons (provider-labelled via `classify_pay_url`), the store link, and a "save this link" copyable URL. From there: report (bought/sent it, with an optional `report_note` [m25] for the couple — quoted in their email and on the dashboard) or cancel. The /g/ page leads with the next action (pay block or store button); `POST /g/<token>/email` mails the link to guests who skipped the email field (only shown when SMTP is configured).
- Cash gift: general cash modal takes a numeric amount + currency select (not free text) → claim kind='cash', status='reported' (a self-report, never phrased as "sent you money" or "payment verified").
- Language: `current_lang()` = `?lang=` (stored) → `session['lang']` → browser `Accept-Language` (he/iw → Hebrew; not stored; HTML responses send `Vary: Accept-Language`) → English. `/lang/<code>` and `/currency/<code>` redirect to `ob_security.same_origin_referrer()` (never the raw `Referer`), and `/lang/<code>` rewrites a `lang=` param in that URL to the chosen language; `pick(row, field)` prefers `field_he` in Hebrew.
- i18n rule: **write "Shabbos" not "Shabbat"** in English content (same audience convention as BashertBench).

## Compression (2026-10-22)
`gzip_response` after_request: text mimetypes, GET 2xx only, and only when every query key is in
`GZIP_SAFE_ARGS` (`lang`, `preview`) — the BREACH guard, since search/filter pages echo input next to
the CSRF token. Keep it the first-registered after_request hook (Flask runs hooks in reverse).

## Auth & admin
- Couples: email+password (werkzeug hashes), session `uid` + `sv` (must match `users.session_ver`
  or the session is treated as logged out — bumped by password reset/change and by any payment-link
  edit). One registry per user. Password reset: `password_resets` table, single-use token (hash
  stored), 2h expiry, invalidates sibling tokens, bumps `session_ver`. Without SMTP configured,
  `/forgot` explains that and points to `/contact`.
- Anti-spam: hidden `website` honeypot field on all public forms; `is_spam()` silently redirects bots. Registry `views` counter increments on guest (non-owner) page loads.
- Admin: `/admin/login` — **no default admin anymore**; create one with `python manage.py Admin sessions expire after 12 h (`ADMIN_SESSION_HOURS`).
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
  `ourbayis.db`. (The old user-level `ourbayis` entry that ran app.py on the real DB was deleted 2026-09-22.)
  The repo's own `.claude/launch.json` entry is `ourbayis-dev` (same run_dev.py). Static URLs carry
  `?v=<mtime>` (`static_cache_bust`) and are cached immutable; icons come from `tools/make_icons.py`.
- Env vars: `OB_SECRET_KEY` (required if `OB_SECURE_COOKIES`/`OB_ENV=production`; otherwise a dev
  key persists in gitignored `instance/dev_secret.txt`), `OB_SECURE_COOKIES=1` (prod),
  `OB_TRUST_PROXY=1` (enables ProxyFix — only set this behind a real proxy), `OB_BASE_URL` (used
  for every external link — emails, sitemap, robots, share links — via `ext_url()`),
  `OB_ALLOWED_HOSTS` (comma list; other Host headers get 400), `OB_DB_PATH` (mainly for tests),
  `OB_RATES`/`OB_RATES_DATE` (optional JSON override, e.g. `{"USD":3.7,"GBP":4.75}`). Normal source is
  `instance/rates.json`, written by `manage.py fetch-rates` (ECB reference rates via frankfurter.app,
  ILS per unit, USD/GBP/EUR/CAD/AUD/ZAR) and hot-reloaded by `ob_money.ensure_fresh()` in a
  `before_request` hook when the file's mtime changes; fallback is `{"USD": 3.1}` (ECB, Oct 2026) with no date. Rates
  drive the header currency toggle, the short `estimate_label()` "≈ $59" on cards and the one-per-page
  `estimate_note()` footnote — ILS is always the reference; `OB_ILS_PER_USD`/`usd()` are legacy), `OB_WHATSAPP`; email (optional): `OB_SMTP_HOST/PORT/USER/PASS`
  + `OB_NOTIFY_EMAIL` (+ optional `OB_MAIL_FROM_NAME`; port 465 = implicit TLS, else STARTTLS) —
  without SMTP, mail still queues in `mail_outbox` (visible via `manage.py stats`) but nothing
  sends. **Settings file:** `instance/ob.env` (KEY=VALUE, gitignored; template `ob.env.example`) is
  loaded by both app.py and manage.py via `ob_security.load_env_file()` and never overrides a real
  env var — so scheduled tasks get the same SMTP/base URL as the site. `OB_ENV_FILE` points
  elsewhere (tests point it at a missing file). `manage.py test-mail <to>` sends one mail now.
- `manage.py`: `create-admin`, `backup`, `send-mail` (flush the outbox — run on a schedule),
  `expire-claims` (run daily), `check` (integrity + config sanity, exit 1 on problems), `stats`.
- Deploy target: PythonAnywhere like BashertBench. See [DEPLOY_AI.md](DEPLOY_AI.md) for the full walkthrough — `passenger_wsgi.py` is the ready-to-paste WSGI file (fix `project_home`, real `OB_SECRET_KEY`, `OB_BASE_URL` before using). Static mapping `/static/` → project static dir. Importing `app.py` runs migrations + catalog seed-sync automatically on first load; you still need `manage.py create-admin` once.

## Catalog rules (v3 phase 3)
- `seed_catalog.json` items carry a stable `seed_key` (slugified name), `kind` ('product' when a
  real brand is known, 'idea' for generic items), `featured` (promotional placement — homepage +
  `/registry/items/starter`'s old one-click no longer uses this), `starter_group`
  ('first_week'|'kitchen'|'shabbos'|'bedbath'|'appliances', used by the grouped starter-pack
  picker), and `price_status`/`price_checked_at`/`price_source` ('verified' for 100 of the 120 active items,
  each confirmed against a real Israeli store listing — see the 2026-10-19/20 CHANGELOG_AI.md entries; 'estimate' otherwise).
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
  whenever the couple manually changes a normally-inherited field, price included). Price follows
  only when the refresh swaps the item's `url` (the old product sold out and the catalog row points at
  a new one) and `price_nis` isn't overridden — then price_nis/price_status/price_checked_at come too;
  a price move on the same product keeps the couple's snapshot. Never touches name/qty/priority/note
  or any claim. Dry run by default. Same-product price moves are offered to the couple instead:
  `_catalog_price_news()` drives a "Store price now ₪… / Use it" line on /registry/items.

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
  from `catalog_items.starter_group`. The submit sits in a sticky `.starter-bar`; app.js (`#starter-form`)
  fills `#starter-tally` from each checkbox's `data-price` × its `qty_<id>` and drives the per-group
  `[data-starter-all]` Select all / Clear buttons (rendered `hidden`, shown by JS).
- `/registry/new` GET passes `form={"couple_names": users.name}` so the signup name is prefilled.
- **Item edit** (`/registry/items/<id>/edit`): full field edit; changing a normally-inherited field
  (url/image/store/brand/name) records it in `registry_items.overrides` so `refresh-registry-links`
  never clobbers it later.
- **Dashboard checklist**: computed live from registry state each request (details filled / ≥5
  usable gifts / a payment link if any gift has no store url / a delivery note unless every gift is
  cash-only (guest page shows it in a "Where to send it" box, or a fallback asking them to check with
  the couple) / visibility reviewed [stamped in
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
- **Shana offer on the dashboard** (`_shana_offer`): shown while `preferences_json.arrival_date` is in the
  future, `furnished` isn't "furnished", and no `shana_requests` row has the couple's email; the request
  form is prefilled for signed-in couples (`_shana_prefill`).
- **Concierge admin** (`/admin/lead/<id>`): prefilled first reply (WhatsApp `?text=` / mailto) in the
  lead's language (`shana_requests.lang`, m24; `_lead_first_reply`); [RUSH] lead emails and "(in N days)"
  on /admin when arrival is inside the package lead time; internal notes, next action + date, a dedup hint (other
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

## Design system v4 (2026-10-26, site-wide)
The last two blocks of style.css ("Design system v4", "v4 pages") override the earlier layers. Pages built
from the homepage components wrap in `<div class="home">` (shana.html, how.html) to get `.sec-inner`,
`.route`, `.faq-cols`, `.board*`, `.closing`, `.link-arrow`, `.kicker`. Registry hero = `.invite` /
`.invite-card` (keeps `<h1 dir="auto">`, `.reg-couple bdi`, `.reg-message` for tests); stamps =
`.stamp.stamp-<state>` (`.stamp-inline` for static use); gift numbers = `gift_card(n=)` + `lot_no`.

- Dashboard v4: `dashboard.html` wraps in `.home.dash-page`; floor plan via `_plan.html` with
  `room_fills` from `_room_fills()` (`ROOM_FOR_CATEGORY`). Items page wraps in `.items-page`.
- Forms ("paperwork"): `.home.sheet-page` > `.sheet-grid` (`.sheet-solo`, `.sheet-wide`) > `.sheet`
  (kicker, `.sheet-title`, `.sheet-stub`). Used by login/signup/forgot/reset/contact/account/item_edit;
  registry_form adds `.form-rail` + `.rform-sec`; items_starter = one `.sheet` per group; error.html
  includes `_lost_room.html`. Fields inside `.sheet` are filled underlines (scoped, so admin forms are
  untouched).
- Reading pages: about (`.about-grid`, letter on `.about-letter`), guides (`.guide-toc`, scoped so the
  guide article's own guide list is untouched), advertise (`.adv-*`), privacy/terms (`.legal-*`, reuse
  `.form-rail` + `.rform-h`; any page can use the rail by marking links `data-rail-link` and sections
  `data-rail-sec`).
- Guide article (`guide.html`) uses the same rail + `.legal-sec`; reading time computed in the template.
  Catalog head is `.catalog-head`; the affiliate note must stay visible (only the rate/drawing notes fold).

## Their home + thank-you studio (2026-10-30)
- Registry page: `room_fills_for(items, committed)` (shared with the dashboard) → `plan_svg(fills=)` plus
  `.room-hits` buttons; cards carry `data-room`; app.js `setRoom()` / `roomFilter` and `#reg-price`
  (data-lo/hi from `CATALOG_PRICE_BANDS`) join the existing chips/available/sort filter.
- `/dashboard/thanks` (`dashboard_thanks`, `_thanks_note(reg, gift, lang)`) and `/dashboard/keepsake`;
  `claim_thanked` honours `back=thanks`. Notes are drafted server-side in both languages, edited and
  sent client-side only (copy / wa.me / mailto) — nothing is sent or stored by the site.

## Managing it together (2026-10-30)
- `registries.user_id` is still the single **owner**; `registry_members` (UNIQUE user_id: one registry per
  account) adds **helpers**. Always get the registry through `user_registry()` (owned, else helped) and
  gate owner-only actions with `is_reg_owner(reg)`: payment links (form disables them, `_save_registry`
  ignores them), inviting/cancelling/removing, handing over (`people_make_owner`, password re-auth),
  and deleting the registry with the account. `can_manage(reg)` is for slug-based pages (`/r/<slug>`).
- Invites: `/registry/people` (owner + helper views), `/join/<token>` (states bad|signin|already|own|other|ok,
  `_join_state`); token hashed like guest links, single-use, 7 days, max 4 helpers + open invites;
  `session["pending_join"]` survives signup/login (`_fresh_session(..., "pending_join")`). Owner is emailed
  on every join. Gift notifications still go to the owner only.

## Homepage v4 (2026-10-26) — see CHANGELOG for the section list
templates/index.html + the "Homepage v4" block at the end of style.css, all scoped to `.home` (`--ed` =
Fraunces / Frank Ruhl Libre, loaded via `{% block head_extra %}` on the homepage only). The floor plan is
inline SVG (viewBox 620×470); pins are positioned in % of `.plan-drawing`; the gift schedule is the
accessible list. Room tabs: `[data-rooms]` in app.js. Not yet rolled out to other pages (owner review).

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
`.bdi`/`<bdi>` for Hebrew. Text people type (registry title/message/city, item names, guest names and
messages, delivery note, lead notes) is either `dir="auto"` (whole block, quotes included) or `<bdi>`
(inline), so an English line on a Hebrew page — or the reverse — keeps its own punctuation order. Header shows a currency toggle only when `OB_RATES` configures a second currency.

## Shared gift presentation (review pass 2026-09-17)
- `templates/_cards.html` — the only place a gift card / price line / facts block / status label is
  defined; import `with context`. Used by index (mode `link`), catalog (`catalog`), registry
  (`registry`), `/sample` (`sample`), the claim dialog, guest page and items page.
- `item_claim_breakdown(reg_id)` → `{item_id: {reserved, reported, received, committed}}` (expired
  reservations excluded); `item_claim_counts()` is a wrapper. `gift_status(item, breakdown)` returns
  `state` ∈ open|partial|reserved|reported|received and `left`. Templates never compute status themselves.
- Registry items carry `model`/`availability`/`notes*` copied from the catalog (migration 18).
  `refresh-registry-links` refreshes url/image/store/brand/model/notes unless overridden, and
  `availability` always; price only when it swaps the product (see above). Never qty/priority/note or any claim amount.
- `model_he` (migration 20) is the Hebrew description line, shown via `pick(item, 'model')`.
  Keep brand/model names in Latin and translate only the descriptors/caveats. It's an
  `_ADOPT_FIELDS` field, so the startup seed-sync fills it on a live DB where it's still empty;
  `refresh-registry-links --apply` then copies it to registry items. A test requires every
  active seed item with a `model` to have `model_he`.
- `featured_items(db, limit)` orders unavailable and url-less items last. `sample_registry(db)` builds
  the one sample fixture from it (synthetic states, no pay links, negative ids); `/sample` renders
  `registry.html` with `is_sample=True`; the homepage preview uses the same fixture.
- `registry_items.variant` is the couple's colour/size/model request, shown to guests as "They'd like:"
  by `gift_facts` (only when the row has `registry_id`). `note`/`note_he` stay private to the couple.
- `illustration_for(item)` picks an `ill-*` symbol from `_ILLUSTRATION_RULES` (keyword on name/seed_key)
  or the category drawing. No catalog row has a photo today.
- Catalog: `CATALOG_PRICE_BANDS`, `CATALOG_SORTS`, `CATALOG_PAGE_SIZE=24`; filters live in the URL.
- Shana packages: `PACKAGE_TIERS` in app.py (per tier delivery/setup/appliances/lead weeks) + i18n
  `pkg_*`/`shana_term_*`; goods lists stay in `bundles.items_text` (admin-editable, insert-only sync).
- `fmt_date(iso)` Jinja global for human dates (EN/HE); stored dates stay ISO.
- Tooling: `tools/screenshots.py` (headless Chrome; needs ≥520px windows, phone checks in the Browser
  pane), `tools/render_private.py` (logged-in pages on a temp DB), `tools/export_static.py` (docs/).

## Guides (2026-09-22)
- `guides.py` — `GUIDES` list, `BY_SLUG`, `pick(obj, field, lang)`. Each guide: slug, icon (a symbol
  already in base.html's sprite), updated, title/summary (+`_he`), `sections` of
  `{h, p[], list[]}` (+`_he` twins, same lengths — enforced by a test), and a `cta` key into
  `guides._CTAS`. Routes `/guides` and `/guides/<slug>`; Jinja globals `gpick` and `guide_cta`.
  Add an article by appending to `GUIDES` — the index, sitemap, static export and screenshots tool
  pick it up automatically. Content must stay claim-free (see the test's `banned` list).
- Header nav collapses to the hamburger at **≤1200px** (not 900): six links plus the CTA no longer fit
  beside the currency/language toggles. Check both languages before adding a seventh nav item.
- Optional Hebrew inputs live in `<details class="he-fields">` (registry form, item edit), `open` when
  a Hebrew value exists. Field names and server handling are unchanged.

## Batch 2026-09-22
- `manage.py remind-claims` (daily, after `expire-claims`): see CHANGELOG; `claims.reminded_at`.
- `count_page_views` after_request → `funnel_events` rows named `view:<endpoint>` for
  `PUBLIC_VIEW_ENDPOINTS`; `g.registry_owner_uid` is set by the registry route so owner self-views are skipped.
  `is_bot()` (User-Agent regex; empty UA counts as a bot) makes `track()` and the `/go/` click
  increments skip crawlers, link-preview fetchers and scripts; robots.txt disallows `/go/`.
- `/advertise` page (`advertise.html`, i18n `adv_*`); empty-ad "Your ad here" band in base.html.
- Registry browse controls (`#reg-controls`, `#only-available`, `#reg-sort`) handled in app.js
  `applyRegistryView()`; cards expose `data-cat`/`data-price`/`data-available`.
- `affiliate_note` i18n key: the only affiliate disclosure text — reuse it, don't write another.

## Terms of use (2026-10-22)
`/terms` → templates/terms.html, keys `terms_<section>_t/_b` (sections listed in the template). Draft
until `i18n.TERMS_REVIEWED` is True (page notice + `manage.py check` warning); `i18n.TERMS_UPDATED` is
the "Last updated" date. Keep its statements in step with the code (hold days, money flow, ads label).

## SEO / privacy facts (current)
`canonical_url`/`alt_urls`/`noindex` come from the context processor: canonical = path only (+`?lang=he`
for the Hebrew variant), hreflang en/he/x-default, `noindex` for admin/dashboard/account/edit/`/g/` pages,
non-public registries, and any page with filter/search params. JSON-LD: Organization+WebSite (home),
FAQPage (how-it-works). `static/og.png` generated by `tools/make_og.py`. robots.txt disallows
/admin, /dashboard, /g/ — never /r/. Sitemap: public pages (+`?lang=he`) and `visibility='public'`
registries only. Guest names/emails/messages never appear in public HTML; the public registry page
shows only counts.
