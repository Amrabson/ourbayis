# OurBayis v3 — implementation spec (2026-09-14)

Written by the design/review model; implemented by coding agents in phases.
Read CLAUDE.md + PROJECT_KNOWLEDGE.md first. This file is the source of truth
for v3 decisions. When code and this spec disagree after a phase lands, fix
the spec (and PROJECT_KNOWLEDGE.md) — don't leave them stale.

## Hard constraints (never break)
- Flask 3 + SQLite + Jinja2, no build step, PythonAnywhere-compatible, `app.py`
  stays the routes file (small helper modules are fine: `ob_*.py`, `manage.py`, `tests/`).
- Existing routes and `/r/<slug>` URLs keep working.
- OurBayis never processes/holds gift money. Couple-owned PayPal/Stripe/Bit links stay.
- EN + HE via `i18n.py` (`T_EN`/`T_HE`), "Shabbos" never "Shabbat", RTL correct.
- No paid SaaS, no Celery/Redis. Only new pip dep allowed: `segno` (pure-Python QR).
- Never overwrite `ourbayis.db` in the repo root during tests; tests use a temp DB via
  `OB_DB_PATH`. Never print personal records or hashes.

## Baseline classification (verified 2026-09-14 against code + snapshot DB)
| Area | State | Notes |
|---|---|---|
| Bilingual pages, RTL | working | |
| Catalog browse/filter/search | working | 117 items, **0 URLs, 0 images**; 8 featured only in DB (seed has no `featured`) → starter pack adds **nothing** on a fresh install |
| Custom items | working | no edit after creation (qty/priority only) |
| Guest reservation | incomplete | no lifecycle, non-atomic availability check, `?pc=<id>` exposes cash-claim amount to anyone with the id |
| Cash gift | incomplete | email says "sent" for a self-report; `amount` is free text |
| Thank-you tracking | working | but release **deletes** claims; item delete cascades claims |
| Password reset | incomplete | token not single-use; sessions not invalidated |
| Login `next` | broken | `startswith("/")` allows `//evil.com` |
| `/lang` | broken | redirects to raw referrer |
| Admin | working | default `admin/changeme123` auto-created; dev secret fallback |
| Email | incomplete | daemon thread, no delivery state |
| Rate limits | incomplete | per-process dict, trusts `X-Real-IP` |
| Migrations | incomplete | `try/except OperationalError: pass` hides real failures |
| Shana leads | working | statuses new/contacted/done; no notes/pipeline |
| Backups | absent | |
| Tests | absent | |
| QR | privacy leak | private registry URL sent to api.qrserver.com |

## Module layout (new)
- `ob_db.py` — `connect(path)`, versioned idempotent migrations (`schema_migrations` table),
  `has_column()`, `backup(dst)` using `sqlite3.Connection.backup` + `PRAGMA integrity_check`
  on the copy, `write_txn(db)` context manager doing `BEGIN IMMEDIATE` with bounded retry
  on `SQLITE_BUSY` (connect `timeout=10`, isolation_level=None).
- `ob_security.py` — `env_bool`, `safe_next(url)`, `same_origin_referrer()`, `validate_url()`,
  `classify_pay_url(url)` → `("paypal"|"stripe"|"bit"|"paybox", canonical_url)` or raises
  `ValueError(reason_key)`, `hash_token`, `new_token`, SQLite-backed `rate_limited()`.
- `ob_mail.py` — persistent outbox (`mail_outbox` table): `enqueue(to, subject, body)` then
  best-effort immediate attempt in a thread; `flush(limit)` for the scheduled task;
  exponential backoff, max 6 attempts, status queued/sent/failed, `last_error`.
- `ob_money.py` — `to_minor(text_or_number, currency)`, `fmt_minor(minor, currency, lang)`,
  `parse_legacy_amount(text)` → `(minor, currency) | None` (strict; never guess),
  `display_estimate(minor_ils, target_currency)` using `RATES` env (see Currency).
- `manage.py` — CLI: `create-admin`, `backup`, `send-mail`, `expire-claims`, `seed-sync [--dry-run] [--fields ...]`,
  `refresh-registry-links [--dry-run]`, `check` (integrity + config sanity), `stats`.
- `static/app.js` — all site JS (no inline scripts anywhere; CSP drops `'unsafe-inline'` for scripts).
- `tests/` — pytest, `conftest.py` sets `OB_DB_PATH` to a tmp file **before** importing `app`.

`app.py` reads `DB_PATH = Path(os.environ.get("OB_DB_PATH") or BASE/"ourbayis.db")`.

## Schema v3 (migrations 1..N, each idempotent)
```
users:        + session_ver INTEGER DEFAULT 1, + deleted_at TEXT NULL
admins:       + session_ver INTEGER DEFAULT 1
registries:   + visibility TEXT DEFAULT 'unlisted'  -- 'draft'|'unlisted'|'public'
              (migration: is_public=1 → 'public', else 'unlisted'; keep is_public in sync on write)
              + paypal_provider/stripe_provider/bit_provider TEXT DEFAULT '' (classified provider label)
              + display_currency TEXT DEFAULT 'ILS'  (couple's default suggestion; guests can switch)
              + delivery_note TEXT DEFAULT '', delivery_note_he TEXT DEFAULT ''  (private; shown only on guest manage page after reservation, never public)
              + preferences_json TEXT DEFAULT '{}'  (bed size, milchig/fleishig colours, etc.)
registry_items: + archived INTEGER DEFAULT 0, + note TEXT DEFAULT '', + note_he TEXT DEFAULT '',
              + variant TEXT DEFAULT '', + overrides TEXT DEFAULT '' (comma list of inherited fields the couple edited: url,image,store,brand,name)
              + kind TEXT DEFAULT 'product'  ('product'|'idea'|'cash_need')
claims:       + status TEXT DEFAULT 'reserved'  -- reserved|reported|received|cancelled|expired
              + amount_minor INTEGER NULL, + currency TEXT NULL
              + price_snapshot_minor INTEGER NULL, + price_snapshot_currency TEXT NULL
              + token_hash TEXT NULL (sha256 hex of guest recovery token), + token_created_at TEXT
              + idempotency_key TEXT NULL  (UNIQUE partial index WHERE NOT NULL)
              + expires_at TEXT NULL, reported_at, confirmed_at, cancelled_at TEXT NULL
              + cancelled_by TEXT DEFAULT '' ('guest'|'owner'|'system'), + late INTEGER DEFAULT 0
              + legacy INTEGER DEFAULT 0
              Migration: kind='item' → status 'reserved', legacy=1, expires_at NULL (never auto-expire legacy);
                         kind='cash' → status 'reported' (self-report, NOT received), legacy=1;
                         amount text preserved; amount_minor/currency filled ONLY when parse_legacy_amount is unambiguous
                         ("₪180" → 18000 ILS; "$180" → 18000 USD; anything else → NULL, flagged for review).
claim_events: (id, claim_id, event TEXT, actor TEXT, note TEXT, created_at)   -- audit trail
password_resets: (id, user_id, token_hash, expires_at, used_at, created_at)
rate_events:  (bucket, key, ts REAL)  + index; pruned on write
mail_outbox:  (id, to_addr, subject, body, status, attempts, last_error, next_attempt_at, created_at, sent_at)
funnel_events:(day TEXT, name TEXT, n INTEGER, PRIMARY KEY(day,name))  -- no PII ever
catalog_items:+ seed_key TEXT UNIQUE NULL, + kind TEXT DEFAULT 'product', + model TEXT DEFAULT '',
              + variant TEXT DEFAULT '', + image_credit TEXT DEFAULT '', + price_status TEXT DEFAULT 'estimate'
              ('verified'|'estimate'|'unknown'), + price_checked_at TEXT DEFAULT '', + price_source TEXT DEFAULT '',
              + availability TEXT DEFAULT 'unknown', + notes TEXT DEFAULT '', + notes_he TEXT DEFAULT '',
              + starter_group TEXT DEFAULT '' ('first_week'|'kitchen'|'shabbos'|'bedbath'|'appliances'),
              + clicks INTEGER DEFAULT 0, + updated_at TEXT
shana_requests: + neighborhood, furnishing ('unknown'|'empty'|'partly'|'furnished'), budget TEXT,
              + notes_internal TEXT, next_action TEXT, next_action_date TEXT, quote_json TEXT DEFAULT '{}'
              status set: new|contacted|quoted|accepted|arranging|completed|cancelled (migration: 'done' → 'completed')
Indexes: claims(registry_id,item_id,status); claims(token_hash); registry_items(registry_id,archived);
         rate_events(bucket,key,ts); mail_outbox(status,next_attempt_at); catalog_items(active,category,sort)
```
No WAL (OneDrive/PA filesystem). `PRAGMA foreign_keys=ON`, `busy_timeout=10000`.

## Gift lifecycle (P0)
Committed quantity for an item = `SUM(qty)` of claims with `status IN ('reserved','reported','received')`
AND (`expires_at IS NULL OR expires_at > now` OR status != 'reserved'). Expired/cancelled never count.

Routes:
- `POST /r/<slug>/claim/<int:item_id>` — inside `write_txn`: re-read item, recompute committed,
  validate qty 1..left, insert claim with `idempotency_key` (hidden `form_key` field, random per render),
  snapshot price (`price_snapshot_minor = price_nis*100`, `ILS`), for cash-for-item
  `amount_minor = price*qty*100, currency='ILS'`, `expires_at = now+14d`, generate recovery token
  (`secrets.token_urlsafe(32)`, store sha256). On `IntegrityError` (duplicate form_key) → look up the
  existing claim by key and redirect to its manage page (no duplicate). Emails go AFTER commit.
  Redirect → `/g/<token>` (guest manage page). **Remove** the `?pc=<id>` lookup.
- `POST /r/<slug>/cash` — general cash gift: fields name, email, amount (number), currency (select of
  configured currencies), message. Creates claim kind='cash', item_id NULL, status='reported'
  (guest is reporting they sent/will send), expires_at NULL. Redirect → `/g/<token>`.
- `GET /g/<token>` — guest manage page (no account). Shows: gift, status card, next step, payment
  destination buttons (provider-labelled: "Send with PayPal → paypal.me/…"), amount, store link,
  couple's delivery note if any, and the saveable link itself. `Cache-Control: no-store`, `noindex`.
  GET never mutates.
- `POST /g/<token>/report` — status reserved→reported (also allowed from expired → reported with `late=1`,
  re-committing the same claim; never creates a second claim). Records event, notifies couple
  ("<name> reports having sent/bought …" — never "payment verified").
- `POST /g/<token>/cancel` — only from reserved/expired; status→cancelled, cancelled_by='guest'.
- Owner (login): `POST /claim/<id>/confirm` (reported|reserved → received), `POST /claim/<id>/cancel`
  (→ cancelled, cancelled_by='owner'; keep `/claim/<id>/release` as an alias route to the same handler),
  `POST /claim/<id>/thanked` (toggle). All log `claim_events`. Cancel copy never implies refund.
- Expiry: lazy in availability query + `manage.py expire-claims` flips rows to 'expired' and logs event.
  Policy text (i18n): "Reservations are held for 14 days. Tell us when you've bought/sent it and it's yours."
- Item delete (`items_update` with delete): if the item has any claims → `archived=1` (not deleted);
  else real delete. Archived items don't show publicly; claims history stays on the dashboard.
- Reducing `qty_wanted` below committed qty → reject with flash explaining committed count.

Status labels (i18n, EN/HE): reserved="Reserved — purchase not complete", reported="Guest reports sending/buying",
received="Received (confirmed by the couple)", cancelled="Cancelled", expired="Reservation expired".

Emails (all through `ob_mail.enqueue`, bilingual by session lang, via i18n `mail_*` keys):
guest confirmation with manage link (if email given); couple notification for reserved / reported / general cash;
never include other guests' data. Manage link is also shown on-screen (no-email case is not a dead end).

## Security (P0)
- `SECRET_KEY`: `OB_SECRET_KEY` env. If unset and (`env_bool("OB_SECURE_COOKIES")` or `OB_ENV=production`)
  → `RuntimeError` at import with a clear message. Dev: persist a random key in `instance/dev_secret.txt` (gitignored).
- No default admin. `python manage.py create-admin <username>` (password prompt or `OB_ADMIN_PASSWORD` env,
  min 12 chars). `/admin/login` with zero admins shows a hint pointing to that command.
- Sessions carry `sv` (session_ver); `login_required`/`admin_required` compare to DB; password reset,
  password change, and payment-link change (needs current password → "reauth") bump `session_ver`.
  Use `session.clear()` + regenerate CSRF on login/logout.
- Password reset: `password_resets` rows, token = `secrets.token_urlsafe(32)` (hash stored), 2h expiry,
  single use, all outstanding tokens for the user invalidated on success. Generic response always.
  Rate limit per-IP and per-email (bucket `forgot:<email hash>`).
- `safe_next()`: must start with single `/`, not `//` or `/\`, no scheme/netloc after `urlparse` and after
  `unquote`, no control chars, ≤ 500 chars. Used by login `next`; `/lang/<code>` and `/currency/<code>`
  redirect to `same_origin_referrer()` else index.
- Proxy: `ProxyFix(x_for=1, x_proto=1, x_host=1)` ONLY if `env_bool("OB_TRUST_PROXY")` (set in passenger_wsgi).
  Rate-limit key = `request.remote_addr` only. External URLs: `OB_BASE_URL` (e.g. https://ourbayis.com) when set →
  `ext_url(endpoint, **kw)` helper; else `url_for(_external=True)`. If `OB_ALLOWED_HOSTS` set, reject other Hosts with 400.
- `validate_url(u)`: http/https, netloc present, no userinfo, host not IP literal/localhost, ≤ 500 chars.
  Retailer links: any valid URL (non-affiliate is fine). Payment links: `classify_pay_url` host allowlist:
  paypal → {paypal.me, www.paypal.me, paypal.com, www.paypal.com (path startswith /paypalme/)};
  stripe → {buy.stripe.com, donate.stripe.com}; bit → {bitpay.co.il, www.bitpay.co.il};
  paybox → {payboxapp.com, www.payboxapp.com, link.payboxapp.com}. Anything else → error
  "That doesn't look like a <provider> link". Lookalikes (paypal.me.evil.com) rejected by exact host match.
  NOTE (docs): Bit/PayBox link *paths* are not publicly documented — we verify host only.
- CSP: `script-src 'self'` (no unsafe-inline); JSON-LD is fine. Move every `onclick/onchange/onsubmit`
  to `data-*` handled in app.js (`data-autosubmit`, `data-confirm`, `data-print`, `data-modal`, `data-copy`).
- Logout (user + admin) = POST. Destructive actions POST + `data-confirm`.
- Error handlers 400/403/404/413/429/500 → `error.html` bilingual; 429 sets `Retry-After`.
  Sensitive pages (dashboard, guest manage, admin, edit forms) send `Cache-Control: no-store`.
- Guest data never in public HTML: registry page shows only counts; no guest names/emails/messages.

## Currency
`OB_RATES='{"USD":3.7,"GBP":4.75}'` + `OB_RATES_DATE='2026-09-01'`. ILS is the reference. Display currency
= session `cur` (default: registry's `display_currency` for guests, else ILS). Estimates labelled
"≈ $49 (approx., rate as of 2026-09-01)". Never sum across currencies: dashboard shows totals per currency.

## Catalog (P0/P1)
- `seed_catalog.json` items get a stable `seed_key` (slug of name, made unique), `kind`, `featured`,
  `starter_group`, `price_status` ('estimate' unless CHANGELOG says verified, then 'verified' + `price_checked_at`
  = the date in the changelog + `price_source`). Seed-sync inserts by `seed_key` only; a legacy row matched by
  exact `name` with NULL seed_key gets its `seed_key` set (one-time adoption) and is otherwise untouched.
  Inactive rows are never re-inserted. `manage.py seed-sync --fields price_nis,url --dry-run` is the only way seed
  values overwrite DB values (explicit, reviewed).
- Card rules: has url → "Reserve and buy from the store"; no url but couple has pay link → "Send money for this gift";
  neither → shown as an idea ("The couple will share where to buy") with no button; dashboard flags it.
  Price 0 → "price not set" never "free". Price status shown: "checked 2026-07-05" vs "estimate".
- Images: none exist. Use category SVG illustrations (aspect-ratio 4/3 reserved box) as the default; `<img>`
  only when `image` set, with `loading=lazy`, `onerror`-free fallback via CSS `object-fit` + `alt=""` (decorative)
  or alt=name when it's a real product photo. No hotlinking guesses.
- `manage.py refresh-registry-links`: for registry_items with catalog_id, copy url/image/store/brand from catalog
  where that field is not in `overrides`; never touch name/price/qty/priority/note or any claim. Dry-run default.

## Onboarding & dashboard (P1)
- Registry form as a 4-section single page with a step header (Details → Israel preferences → Payment (optional)
  → Visibility). Hebrew fields optional (collapsed "Add Hebrew" details). Errors re-render with values preserved.
- Catalog "Add" while logged out → store catalog ids in `session['pending_add']`, apply after registry creation.
- Dashboard checklist computed from state: details, ≥5 usable gifts (url or pay link), payment method (if any
  cash_need/idea items), visibility reviewed, previewed (flag set when owner opens /r/<slug>?preview=1), shared
  (views>0 or copy/whatsapp click posts `/dashboard/shared`).
- Action queues: "Guest reports — confirm receipt", "Reserved, waiting", "Thank-yous outstanding".
- Item edit (`/registry/items/<id>/edit`): name, name_he, price, url, store, qty, priority, note, variant, kind.
- Exports: `/dashboard/claims.csv` (CSV-injection safe: prefix `'` on cells starting with `= + - @ \t \r`).
- Print insert `/dashboard/print` and local QR `/dashboard/qr.svg` via segno.
- Starter groups: preview page `/registry/items/starter` GET (checkbox list grouped) → POST adds selected.

## Concierge (P1)
Public form: name, at least one of whatsapp/email (server-validated), arrival, city, neighborhood (optional),
furnishing status, package/budget, notes. Address NOT collected on the public form (asked later).
Admin: pipeline statuses above, `/admin/lead/<id>` detail with internal notes, next action + date, cost breakdown
editor (goods, delivery, assembly, labour, contingency, quoted price) → margin computed server-side; dedup hint
(same email/whatsapp). Lead status never implies payment.

## Privacy / SEO
- visibility: draft (owner-only 404 for others... actually 403-styled "not published" page for non-owner),
  unlisted (link works, `noindex`, not in sitemap/find), public (find + sitemap). Copy: "Unlisted means anyone with the link can open it."
- Canonical/hreflang: `?lang=he` variant is canonical for HE; other `lang` values stripped. `og:image` = `static/og.png`
  (generated by `tools/make_og.py` with Pillow, committed). JSON-LD: Organization+WebSite (home), FAQPage (how), Service (shana).
- robots.txt: Disallow /admin, /dashboard, /g/ ; no Disallow on /r/.
- Funnel counters (no PII): signup, registry_created, first_gifts, share_click, reservation, handoff_click, guest_report,
  receipt_confirmed, concierge_inquiry. Skip when session has admin or when the viewer is the owner.

## Visual direction (Phase 2)
Keep parchment/navy/gold + Bellefair/Assistant. Add: frosted-glass panels (`backdrop-filter`, translucent card
surface, hairline border, soft inner highlight) over a slow-moving gold/ivory light field in the hero (CSS only,
`prefers-reduced-motion` disables), glass sticky header, refined card system with reserved image ratios, real
product focus, 44px controls, visible focus rings, logical properties, `unicode-bidi: isolate` on prices/URLs/emails.
No low-contrast gold body text, no emoji art, no fake testimonials/badges.

## Definition of done per phase
Tests pass (`python -m pytest -q`), `python manage.py check` passes on a fresh temp DB and on a copy of the snapshot DB,
all routes smoke-render in EN and HE, docs updated.
