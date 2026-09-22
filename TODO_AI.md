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
- [x] Guest reminder email — `manage.py remind-claims` (2026-09-22).
- [x] `/advertise` page + "your ad here" band (2026-09-22).
- [x] Viral CTA on the public registry page (2026-09-17).
- [x] Affiliate disclosure line (2026-09-22) — wording is generic; if you join Amazon Associates, add
  their required sentence to `affiliate_note` (EN+HE).
- [ ] `/guides` bilingual content section (SEO) — 4 launch articles specced in the July roadmap.
- [x] Registry "available only" toggle + price sort (2026-09-22); server order is already most-wanted-first.
- [ ] Item-specific illustrations cover ~27 shapes; extend `_ILLUSTRATION_RULES` when new seed items
  don't match (they fall back to the category drawing, never to a wrong item).
- [x] Per-page view counters (2026-09-22) — `view:<endpoint>` rows in the admin funnel table.
- [ ] Hebrew registry-form fields could collapse into an "Add Hebrew" `<details>` (spec) — they are
  inline-but-optional today.
- [ ] Group gifting / chip-in toward big-ticket items — deliberately deferred (SPEC_V3 "Defer").
- [ ] Multiple registries per account, co-owners, live inventory — deferred.

## Owner decisions from the 2026-09-17 review pass (publication blockers for the affected claims)
- [ ] **Full Nest installation.** The package now says washer/fridge/microwave are "ordered and delivery
  coordinated (installation confirmed in your quote)" and the terms panel says installation is priced
  per item. Decide: is appliance installation included in the ₪17,900 starting price or always extra?
  Then edit `PACKAGE_TIERS` / `pkg_appliances_included` and the bundle line accordingly.
- [x] **Who receives deliveries** — decided 2026-09-17: everything is delivered to the couple's
  apartment; with access (key/code/someone to open) deliveries are placed inside. Copy updated.
- [ ] **Bundle text on an existing database.** `bundle_sync` is insert-only, so a live DB keeps the old
  "most popular" / "coordinated and installed" wording. Edit the three bundles in `/admin/bundles`
  (or on a fresh install the seed is used). The static preview already shows the new text.
- [ ] **Starting prices** (₪2,450 / ₪6,900 / ₪17,900) are unchanged and labelled indicative; confirm
  or replace them.
- [ ] **Product photos.** 0 of 117 catalog items have an image; cards use item-specific line drawings
  labelled as illustrations. If you want photos for the 8 featured items, add only images you have the
  right to use via `/admin/catalog` (`image` + `image_credit`); the card, homepage strip, registry and
  dialog all pick them up automatically and fall back to the drawing on error.
- [ ] **Exchange rate.** Run `python manage.py fetch-rates` once and schedule it daily (DEPLOY_AI.md);
  it writes `instance/rates.json` (ECB reference rates via frankfurter.app, USD/GBP/EUR/CAD/AUD/ZAR)
  and the running app picks it up without a reload. Until that runs, the built-in USD 3.7 fallback
  shows with no date. `OB_RATES` env still overrides everything if you prefer a fixed rate.
- [ ] **Backup retention.** Privacy copy no longer promises a period; state one once you decide how long
  `manage.py backup` files are kept, then update `privacy_delete_b` (EN+HE).
- [ ] **Sample registry title/names** ("Our new bayis in Yerushalayim" / "A sample couple") — change
  in i18n `sample_reg_*` if you prefer different wording; keep the "Sample registry" flag.

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
- [ ] **Rates** — schedule `manage.py fetch-rates` daily (see the decisions list above); `OB_RATES`
  env is only needed if you want to pin a fixed rate.
- [ ] **Pricing verification** — 55 of 117 catalog items are marked `price_status='verified'` (dated
  2026-07-03/05, see CHANGELOG_AI.md) — the July notes only claim 31 branded + 8 big-ticket items, so
  spot-check the mapping in `/admin/catalog?price_status=verified` and downgrade anything doubtful.
  Verified dates are ~10 weeks old; recheck big-ticket prices before launch. The remaining ~62 are estimates; spot-check the highest-
  value ones (fridge, mixer, appliances) before launch. Filter `/admin/catalog?price_status=estimate`.
- [ ] **Legal review of privacy/terms** — `privacy.html` is now bilingual with no bracketed notes, but it
  is a description of current behaviour, not reviewed legal text. There is no separate terms page yet —
  decide whether one is needed before launch.
- [ ] **PythonAnywhere scheduled tasks** — see DEPLOY_AI.md "Scheduled tasks" for the exact
  commands (`send-mail`, `expire-claims`, `backup`, `seed-sync --apply` after a `seed_catalog.json`
  edit).
- [ ] Create the production admin with `manage.py create-admin` (strong password; there is no default account any more) (via
  the form at the bottom of `/admin`), and set `OB_SECRET_KEY` + `OB_SECURE_COOKIES=1` in prod.
- [ ] Pick + buy a domain, follow DEPLOY_AI.md to deploy, add the custom domain.
