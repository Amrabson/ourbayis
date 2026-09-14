# TODO

Rules (from CLAUDE.md): all public text in BOTH `T_EN`/`T_HE`; "Shabbos" never "Shabbat"; no new
pip deps beyond `segno`; site never touches money; keep PROJECT_KNOWLEDGE/CHANGELOG/TODO updated.

## v3 phase 3 — done 2026-09-14
Catalog data model (seed_key/kind/featured/starter_group/price_status, seed-sync/refresh-
registry-links, admin CSV import/export, /go/ click tracking), onboarding (4-section registry
form, pending_add for logged-out catalog adds, starter-pack picker), items management (edit page,
archived section, needs-link flag), dashboard (checklist, action queues, print insert, account
export/delete), concierge (email-or-whatsapp requirement, neighborhood/furnishing/budget, admin
lead detail + cost-breakdown/margin editor), admin (outbox, backup download, funnel table),
privacy/SEO (draft/unlisted/public visibility, canonical/hreflang globals, noindex). See
CHANGELOG_AI.md "2026-09-14 — v3 phase 3" for the full breakdown and decisions.

Everything below the roadmap items marked `[x]` was superseded or built by phase 3; items still
`[ ]` are genuinely open.

### P1 — Revenue plumbing
- [x] Outbound click tracking `/go/` — built as `/go/c/<catalog_id>` and `/go/i/<item_id>`,
  `clicks` column, `handoff_click` funnel event. Registry/catalog/items templates should route
  their store links through `go_url(item)` (Jinja global) rather than the raw `item['url']` —
  **verify the design agent's templates actually call it** (registry.html/catalog.html are theirs).
- [ ] Guest claim-confirmation email (purchase recovery) — not built this phase. Add to the claim
  route: when `guest_email` present and the item has a store URL, send a reminder with the `/go/`
  link a few days after reservation if not yet reported.
- [ ] Unfinished-claim reminder scheduled task (`manage.py` subcommand or standalone script) —
  not built. Needs a `reminded` column on `claims` and a daily PythonAnywhere task.
- [ ] `/advertise` page (inbound ad sales) — not built.
- [ ] Viral + cross-sell CTAs on registry.html/dashboard — design-agent territory (their template
  ownership); flag to them if not already covered by the redesign.
- [x] Amazon Associates disclosure — admin catalog UI now correctly calls a missing link "missing
  store link" (not "missing affiliate") since not every store link is an affiliate link; the
  guest-facing disclosure line is still the design agent's to add near link buttons.
- [ ] v2 — Group gifting for big-ticket items (chip-in cash claims) — not built.

### P1 — SEO
- [x] Canonical + hreflang + noindex context — `canonical_url`, `alt_urls`, `noindex` Jinja
  globals now computed server-side in app.py (GET-only, lang stripped/overridden). **base.html
  still needs to actually render them** (`<link rel="canonical">`, hreflang alternates gated on
  these vars, `<meta name="robots" content="noindex">` when `noindex` is true) — base.html is
  DO NOT TOUCH for this agent; hand off to the design agent.
- [ ] JSON-LD structured data (Organization/WebSite/FAQPage/Service) — not built, design-agent
  territory (base.html/index.html/how.html/shana.html markup).
- [ ] `/guides` content section — not built.
- [ ] Title/meta pass — mostly the design agent's territory; my new pages (`item_edit`,
  `items_starter`, `account`, `dashboard_print`) have basic `{% block title %}`s only.
- [ ] `og:image`/`static/og.png` — not built this phase (no Pillow script run); base.html already
  references `static/og.png` — confirm the file actually exists before launch.

### P2 — UX/UI
- [x] Dashboard onboarding checklist — built (details/≥5 gifts/payment/visibility reviewed/
  previewed/shared), disappears once every step is done.
- [x] Thank-you export CSV — already existed from phase 1 (`/dashboard/claims.csv`).
- [x] Printable invitation insert — built (`/dashboard/print`, 2-per-A4 `@media print`).
- [ ] Registry page browsing polish (category anchor pills, claimed/available filter) —
  design-agent territory (registry.html).
- [ ] Empty/edge states pass — partially covered; not audited this phase.

### P2 — Function/ops
- [ ] Privacy-friendly server-side page-view analytics — not built (funnel_events covers
  named events but not a per-path view log).
- [x] SQLite backup — `manage.py backup` already existed (phase 1); this phase added an
  admin-UI download button (`/admin/backup.db`).
- [ ] 404 upsell (find-a-registry box on 404.html) — design-agent territory.

## Owner launch checklist (do these before going live)
- [ ] **Real store links.** Catalog has 0 real URLs by design (seed never invents links). Use
  `/admin/catalog` (filter "missing store link") or `manage.py seed-sync --fields url --apply`
  after editing `seed_catalog.json`. Sign up for Amazon Associates (works from Israel/SA) and any
  other affiliate programs; paste links per item.
- [ ] **Images** — only add a product photo URL you have the right to use (the store's own listing
  image, or one you purchased/shot). `image_credit` field exists in the catalog admin form for
  attribution if needed. Until then the category SVG placeholder is used.
- [ ] **Payment provider setup** — couples paste their own PayPal.me/Stripe Payment Link/Bit/
  PayBox URLs; nothing to configure server-side. **Verify Bit and PayBox link formats** —
  `ob_security._PAY_HOSTS` allowlists `bitpay.co.il`/`payboxapp.com` by host only (their exact
  link *paths* aren't publicly documented); test with a real Bit/PayBox account before launch and
  tighten the allowlist if you learn the real path pattern.
- [ ] **SMTP sender** — set `OB_SMTP_HOST/PORT/USER/PASS` + `OB_NOTIFY_EMAIL` (Gmail app password
  or Zoho work fine). Without it, mail queues in `mail_outbox` but never sends — `/forgot` and
  guest confirmation emails silently no-op.
- [ ] **Rates config** — set `OB_RATES` (e.g. `{"USD":3.7,"GBP":4.75}`) and `OB_RATES_DATE` so
  `estimate_label()` shows "≈ $49 (approx., rate as of ...)" instead of nothing. Update
  periodically — nothing auto-refreshes exchange rates.
- [ ] **Pricing verification** — 55 of 117 catalog items are `price_status='verified'` (dated
  2026-07-03/05, see CHANGELOG_AI.md). The remaining ~62 are estimates; spot-check the highest-
  value ones (fridge, mixer, appliances) before launch. Filter `/admin/catalog?price_status=estimate`.
- [ ] **Legal review of privacy/terms** — `privacy.html` still has `[owner/legal review]` markers
  (e.g. `privacy_delete_b` describes manual deletion by request — now partially superseded by the
  self-service `/account/delete`; reconcile that copy). Not touched this phase (privacy.html is
  the design agent's file).
- [ ] **PythonAnywhere scheduled tasks** — see DEPLOY_AI.md "Scheduled tasks" for the exact
  commands (`send-mail`, `expire-claims`, `backup`, `seed-sync --apply` after a `seed_catalog.json`
  edit).
- [ ] Change the admin password from whatever `manage.py create-admin` was seeded with (via
  the form at the bottom of `/admin`), and set `OB_SECRET_KEY` + `OB_SECURE_COOKIES=1` in prod.
- [ ] Pick + buy a domain, follow DEPLOY_AI.md to deploy, add the custom domain.
