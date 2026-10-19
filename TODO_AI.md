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
- [x] `/guides` bilingual content section — 4 launch articles (2026-09-22). Next articles go in
  `guides.py`; keep them claim-free (the test enforces a banned-phrase list).
- [x] Registry "available only" toggle + price sort (2026-09-22); server order is already most-wanted-first.
- [ ] Item-specific illustrations cover ~27 shapes; extend `_ILLUSTRATION_RULES` when new seed items
  don't match (they fall back to the category drawing, never to a wrong item).
- [x] Per-page view counters (2026-09-22) — `view:<endpoint>` rows in the admin funnel table.
- [x] Hebrew registry-form fields collapse into an "Add Hebrew" `<details>` (2026-09-22); same on the
  item edit page.
- [ ] Group gifting / chip-in toward big-ticket items — deliberately deferred (SPEC_V3 "Defer").
- [ ] Multiple registries per account, co-owners, live inventory — deferred.

## Owner decisions from the 2026-09-17 review pass (publication blockers for the affected claims)
- [x] **Full Nest installation** — decided 2026-09-22: included. Washer/fridge/microwave are
  "delivered and installed" on a standard hookup (existing water/drain/power points); new
  plumbing/electrical work and installing/assembling anything else is quoted per item.
- [x] **Who receives deliveries** — decided 2026-09-17: everything is delivered to the couple's
  apartment; with access (key/code/someone to open) deliveries are placed inside. Copy updated.
- [x] **Bundle text on an existing database** — fixed 2026-09-22: `bundle_sync` now also refreshes a
  text field whose value is still one of the seed's own earlier texts (`replaces` in
  seed_catalog.json); admin edits are never overwritten. When rewording a bundle in the seed, add
  the old text to its `replaces` list. Any pre-git wording not in that list: edit in `/admin/bundles`.
- [x] **Starting prices** ₪2,450 / ₪6,900 / ₪17,900 — confirmed by the owner 2026-09-22. Copy now says
  "Starting price — final quote after we talk" (no longer "indicative").
- [ ] **Product photos.** 0 of 117 catalog items have an image; cards use item-specific line drawings
  labelled as illustrations. If you want photos for the 8 featured items, add only images you have the
  right to use via `/admin/catalog` (`image` + `image_credit`); the card, homepage strip, registry and
  dialog all pick them up automatically and fall back to the drawing on error.
- [ ] **Exchange rate.** Run `python manage.py fetch-rates` once and schedule it daily (DEPLOY_AI.md);
  it writes `instance/rates.json` (ECB reference rates via frankfurter.app, USD/GBP/EUR/CAD/AUD/ZAR)
  and the running app picks it up without a reload. Until that runs, the built-in USD 3.1 fallback
  shows with no date. `OB_RATES` env still overrides everything if you prefer a fixed rate.
- [ ] **Backup retention.** Privacy copy no longer promises a period. Since 2026-09-28 `manage.py backup`
  keeps the newest 14 automatic copies in `backups/` (`--keep N` to change; hand-named snapshots are never
  pruned) — weekly backups = about 14 weeks. Once you settle N, state it in `privacy_delete_b` (EN+HE),
  and remember copies you downloaded off the server aren't covered.
- [ ] **Sample registry title/names** ("Our new bayis in Yerushalayim" / "A sample couple") — change
  in i18n `sample_reg_*` if you prefer different wording; keep the "Sample registry" flag.

## Owner launch checklist (do these before going live)
- [ ] **Re-check prices monthly.** `/admin/catalog?stale=1` lists verified prices older than 30 days;
  `manage.py check` prints the count. All 67 linked items were re-checked 2026-10-19 (next due ~2026-11-18) —
  KSP's own item feed (`/m_action/api/item/<id>`, `price` = regular price, `addToCart` 0 = "not available
  now", `isLastItem` = last unit) read from inside a browser tab on ksp.co.il is the fast way; go slowly
  (KSP starts answering with an HTML page after ~40 quick requests — stop and wait, don't push past it).
  **Live DB:** apply that re-check with the commands in the 2026-10-19 CHANGELOG entry.
- [ ] **Real store links.** 67 of 120 active items (45 of the 47 starter-pack items) have verified store links
  in `seed_catalog.json`; 3 combo items were retired and split on 2026-09-25. On the live DB run the three commands at the end
  of the 2026-09-25 "combo items split" CHANGELOG entry, then `refresh-registry-links --apply`. The other 53
  active items still have no URL: use `/admin/catalog` (filter "missing store link") or extend
  `seed_catalog.json` the same way. Sign up for Amazon Associates (works from Israel/SA) and any
  other affiliate programs; paste links per item.
- [ ] **Images** — only add a product photo URL you have the right to use (the store's own listing
  image, or one you purchased/shot). `image_credit` field exists in the catalog admin form for
  attribution if needed. Until then the category SVG placeholder is used.
- [ ] **Payment provider setup** — couples paste their own PayPal.me/Stripe Payment Link/Bit/
  PayBox URLs; nothing to configure server-side. **Verify Bit and PayBox link formats** —
  `ob_security._PAY_HOSTS` allowlists `bitpay.co.il`/`payboxapp.com` by host only (their exact
  link *paths* aren't publicly documented); test with a real Bit/PayBox account before launch and
  tighten the allowlist if you learn the real path pattern.
- [ ] **SMTP sender** — create `instance/ob.env` from `ob.env.example` (Gmail app password), then
  `python manage.py test-mail you@gmail.com`. Step-by-step in DEPLOY_AI.md 4b. Without it, mail
  queues in `mail_outbox` but never sends — `/forgot` and guest confirmation emails silently no-op.
- [ ] **Rates** — schedule `manage.py fetch-rates` daily (see the decisions list above); `OB_RATES`
  env is only needed if you want to pin a fixed rate.
- [x] **Pricing verification** — done 2026-09-25: "verified" now only on items with a store
  link checked on the product page (57). The July Zap-range items without a product were
  downgraded to estimates. Re-check prices before launch if more than ~2 months pass.
- [ ] **Legal review of privacy/terms** — `privacy.html` is now bilingual with no bracketed notes, but it
  is a description of current behaviour, not reviewed legal text. There is no separate terms page yet —
  decide whether one is needed before launch.
- [ ] **PythonAnywhere scheduled tasks** — see DEPLOY_AI.md "Scheduled tasks" for the exact
  commands (`send-mail`, `expire-claims`, `backup`, `seed-sync --apply` after a `seed_catalog.json`
  edit).
- [ ] Create the production admin with `manage.py create-admin` (strong password; there is no default account any more) (via
  the form at the bottom of `/admin`), and set `OB_SECRET_KEY` + `OB_SECURE_COOKIES=1` in prod.
- [ ] Pick + buy a domain, follow DEPLOY_AI.md to deploy, add the custom domain.
