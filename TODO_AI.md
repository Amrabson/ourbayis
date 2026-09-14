# TODO

Rules (from CLAUDE.md): all public text in BOTH `T_EN`/`T_HE`; "Shabbos" never "Shabbat"; no new
pip deps beyond `segno`; site never touches money; keep PROJECT_KNOWLEDGE/CHANGELOG/TODO updated.

## v3 — done 2026-09-14 (phases 1–3 + integration pass; see CHANGELOG_AI.md)
P0: gift lifecycle (reserved → reported → received / cancelled / expired) with atomic reservations,
idempotent POSTs, guest recovery links, audit trail; session versioning, single-use reset tokens,
no default admin, safe redirects, DB-backed rate limits, CSP without inline scripts, mail outbox,
consistent backups, versioned migrations. P1: catalog metadata + honest card rules + `/go/`,
onboarding form + starter picker + item editing, state-driven dashboard, concierge pipeline,
admin queues/CSV/outbox, draft/unlisted/public, canonical/hreflang/JSON-LD/og image, glass-and-
parchment redesign, currency estimates with a rate note. 47 automated tests.

## Still open (code)
- [ ] Guest reminder email / "did you get a chance to order X?" scheduled task (needs a `reminded`
  column + `manage.py remind-claims`; bounded, never twice).
- [ ] `/advertise` page (inbound ad sales) and a "your ad here" line in the ad band.
- [ ] Viral CTA on the public registry page ("Create your own registry") — small, bilingual.
- [ ] Affiliate disclosure line near store buttons on registry/catalog (Amazon ToS) — one muted line.
- [ ] `/guides` bilingual content section (SEO) — 4 launch articles specced in the July roadmap.
- [ ] Registry page browsing polish for big registries: category anchor pills already exist;
  add an "available only" toggle and "most wanted first" sort.
- [ ] Per-path page-view counter (privacy-safe) to feed /advertise numbers; funnel_events only
  counts named events today.
- [ ] Hebrew registry-form fields could collapse into an "Add Hebrew" `<details>` (spec) — they are
  inline-but-optional today.
- [ ] Group gifting / chip-in toward big-ticket items — deliberately deferred (SPEC_V3 "Defer").
- [ ] Multiple registries per account, co-owners, live inventory — deferred.

## Owner launch checklist (do these before going live)
- [ ] **Real store links.** The 8 featured items have verified links in `seed_catalog.json`
  (2026-09-14, see CHANGELOG) — on the live DB run the `seed-sync --fields … --apply` command from
  the changelog, then `refresh-registry-links --apply`. The other ~109 items still have no URL: use
  `/admin/catalog` (filter "missing store link") or extend `seed_catalog.json` the same way. Sign up for Amazon Associates (works from Israel/SA) and any
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
- [ ] **Pricing verification** — 55 of 117 catalog items are marked `price_status='verified'` (dated
  2026-07-03/05, see CHANGELOG_AI.md) — the July notes only claim 31 branded + 8 big-ticket items, so
  spot-check the mapping in `/admin/catalog?price_status=verified` and downgrade anything doubtful.
  Verified dates are ~10 weeks old; recheck big-ticket prices before launch. The remaining ~62 are estimates; spot-check the highest-
  value ones (fridge, mixer, appliances) before launch. Filter `/admin/catalog?price_status=estimate`.
- [ ] **Legal review of privacy/terms** — `privacy.html` carries `[owner/legal review]` markers
  (backup retention period, affiliate wording). Deletion copy now describes the self-service Account page.
  There is no separate terms page yet — decide whether one is needed before launch.
- [ ] **PythonAnywhere scheduled tasks** — see DEPLOY_AI.md "Scheduled tasks" for the exact
  commands (`send-mail`, `expire-claims`, `backup`, `seed-sync --apply` after a `seed_catalog.json`
  edit).
- [ ] Create the production admin with `manage.py create-admin` (strong password; there is no default account any more) (via
  the form at the bottom of `/admin`), and set `OB_SECRET_KEY` + `OB_SECURE_COOKIES=1` in prod.
- [ ] Pick + buy a domain, follow DEPLOY_AI.md to deploy, add the custom domain.
