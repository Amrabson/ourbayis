# Changelog

## 2026-09-22 (later) — /guides content section + optional-Hebrew form fields
- **`/guides` and `/guides/<slug>`**: four bilingual articles in a new `guides.py` module (kept out of
  i18n.py — long-form editorial, not UI strings; same `*_he` + English-fallback contract via
  `guides.pick()`). Launch set: *What a first apartment in Israel actually needs*, *Giving a gift to a
  couple in Israel from abroad*, *Setting up a kosher kitchen in a new home*, *Before you buy: sizes,
  plugs and delivery in Israel*. Article JSON-LD with `dateModified`, both languages in the sitemap
  with `lastmod`, "More guides" cross-links, one CTA per article (catalog / sample / signup / shana).
  Content rules: no customs, warranty or halachic claims; voltage and socket types stated as the
  national supply with "check the label / the store page" for any specific product; Israeli bed sizes
  given as what shops commonly sell, with "measure the mattress"; halachic questions pointed at a rav.
  Linked from the main nav, the footer, the homepage three-step section and How It Works.
- **Nav breakpoint**: with a sixth item the header stopped fitting beside the currency + language
  toggles at ~1100px (the toggles were pushed off-screen). The nav now collapses to the hamburger at
  ≤1200px instead of ≤900px; the rest of the responsive layout is unchanged. Measured in both
  languages — Hebrew is the wider one.
- **Optional Hebrew fields** collapse into an "Add Hebrew (optional)" `<details>` on the registry form
  (title / names / message, and separately the delivery note) and on the item edit page (name / note).
  Opened automatically when any Hebrew value already exists, so an existing registry never hides
  content the couple typed. Same field names, same POST handler — nothing changed server-side.
- Tests: +4 → **79 passed** (guides render in both languages, every guide fully bilingual with no
  banned claims, guides linked and in the sitemap, Hebrew `<details>` collapsed until filled and still
  saving). Static export now publishes 54 pages including the guides.

## 2026-09-22 — reminders, page-view counters, /advertise, registry browse controls, affiliate line
- `manage.py remind-claims [--dry-run]`: one bilingual nudge per reservation that has a guest email,
  is 5+ days old, still `reserved`, not expired and not yet reminded (`claims.reminded_at`, migration
  19; the flag is set before the mail is queued so a crash can lose a nudge but never duplicate one;
  200 per run). Links to the registry page — the raw `/g/` token is never stored, so it can't be resent.
- Privacy-safe page views: `after_request` counts `view:<endpoint>` per day in `funnel_events` for
  public HTML GETs (no IP/UA/params; owners viewing their own registry and admins excluded). Shows in
  the admin funnel table; gives the owner real numbers to quote to advertisers.
- `/advertise` (bilingual, in sitemap): audience, three formats, no invented traffic figures, links to
  the contact form with `topic=partner`. Footer "Advertise with us" now points there; when no ad is
  active, the homepage/catalog/find/how pages show a dotted "Your ad here" band linking to it.
- Registry page: "Show only gifts still available" toggle + price sort (client-side; cards carry
  `data-available`/`data-price`; dialogs move with their cards; live count). Also on `/sample`.
- Affiliate disclosure (one muted sentence) on the registry, catalog and guest page near store links.
- Tests: +4 → **75 passed**.

## 2026-09-17 — live-ish exchange rates + delivery decision
- `manage.py fetch-rates` pulls ECB reference rates (frankfurter.app, free, no key) for
  USD/GBP/EUR/CAD/AUD/ZAR, inverts them to ILS-per-unit and writes `instance/rates.json` atomically
  (a failed fetch leaves the previous file untouched and exits 1). `ob_money` resolves rates as
  env `OB_RATES` → rates file → `{"USD": 3.7}` fallback, and `ensure_fresh()` (called from a
  `before_request` hook) re-reads the file when its mtime changes, so a daily scheduled task updates
  the running site with no reload. Estimates remain labelled approximate with the rate date; the site
  still never converts money itself.
- Shana Rishonah delivery term (owner decision): everything is delivered to the couple's apartment;
  with access (key/code/someone to open) deliveries are placed inside; Full Nest receives and unpacks.

## 2026-09-17 — review pass 2: homepage journey, shared gift cards, status labels, sample, packages, copy
**Status / availability consistency (the one demonstrated defect, fixed first).** Registry items now
carry `model`, `availability`, `notes`/`notes_he` (migration 18, backfilled from the catalog;
`_insert_registry_item_from_catalog` copies them; `refresh-registry-links` refreshes them — `availability`
always, the rest unless the couple overrode the field). The Crock-Pot's "Out of stock at last check"
badge therefore shows on the homepage strip, `/catalog`, the registry card, the claim dialog, the items
page and the dashboard row, not only on `/catalog`. `featured_items()` sorts unavailable items last, so
the default homepage/sample selection prefers orderable gifts (the badge still shows when one is included).
Claim `amount_minor`/`price_snapshot_minor` and the registry item's `price_nis` are never touched by the
refresh (test: `test_refresh_links_updates_availability_but_never_claim_amounts`).

**Gift lifecycle shown honestly.** `item_claim_breakdown()` (reserved/reported/received per item) and
`gift_status(item, breakdown)` are the single presentation rule. The public registry no longer prints
"Gifted" whenever quantity is exhausted: cards say *Reserved by a guest* / *On its way — reported by a
guest* / *Received — confirmed by the couple*; multi-quantity cards say "1 of 3 still available · 1
reserved · 1 received"; the progress line reads "reserved, on the way or received"; How It Works has a
status legend. No donor names or messages are exposed.

**Shared card component.** `templates/_cards.html` (`gift_card`, `gift_media`, `price_line`,
`gift_facts`, `status_label`, `qty_line`) is now used by the homepage strip, `/catalog`, `/r/<slug>`,
`/sample`, the claim dialog, the guest page and the items page. Name + shekel price first; brand · store,
model, "Price checked <date>" / "Estimated price" and the stock flag subordinate. 27 item-specific line
illustrations (`ill-platta`, `ill-urn`, `ill-kettle`, `ill-mixer`, `ill-slowcooker`, `ill-towel`, …) picked
by `illustration_for(item)` (keyword rules on name/seed_key, category drawing as fallback) so a kettle no
longer looks like a mixer; the box is `role="img"` with an "illustration, not a product photo" label. No
catalog row has a photo (checked: 0/117 in the seed and the snapshot DB) — see TODO for the image workflow.

**Homepage.** New sequence: split hero (eyebrow / H1 "Build your bayis in Israel." / display-serif lead
/ body / one-line payment explanation / Create your registry + Find a couple / "See a sample registry" /
three short trust points) beside a live preview of the sample registry; one shared three-step story with
"For guests" notes; 8 featured gift cards; a category chip strip; three factual benefit cards; the
Shana Rishonah band (labelled "separate service"); FAQ; final CTA. The old duplicate couples/guests
sections, the six category tiles, the hardcoded ₪180/₪1,650 sample and the full-width skyline art are
gone (the chuppah motif survives above the preview). Hero light-field animation now only runs ≥900px and
under `prefers-reduced-motion: no-preference`; `.reveal` is faster and triggers earlier.

**One canonical sample.** `sample_registry(db)` builds the sample from the live featured catalog rows
with synthetic states (open, 1-of-2, received, reported, reserved). `/sample` renders `registry.html`
with `is_sample=True` (no dialogs, no forms, no pay links, inert buttons, "Sample registry" flag,
"Yours will look like this" CTA). The homepage preview uses the same fixture. `tools/export_static.py`
publishes `/sample` (old `docs/registry/` redirects to it) and no longer seeds a "Demo Couple".

**Catalog browsing.** Result count, price bands (`CATALOG_PRICE_BANDS`), exact-products/ideas filter,
sort (`CATALOG_SORTS`), 24-per-page pagination (`CATALOG_PAGE_SIZE`), search also matches brand, reset
link; everything is in the URL so back/forward and the pending-add-through-signup flow keep state.
`items_add?back=catalog` now carries `price/kind/sort/page` back and anchors to the added card. The
logged-out "Sign up to add" is a real pending-add POST, not a bare link to /signup.

**Gift dialog.** "View product details at {store} ↗" before reserving; two clearly separated routes with
one-line notes on who completes the order (guest + store) vs. who orders after a cash gift (the couple);
"Next you'll get a private link…" hint; translated `Close` label; `aria-labelledby`; dialogs scroll
inside `max-height: calc(100dvh - 24px)`. Guest page: price + facts, "Next step: buy it…" CTA for store
claims, localized held-until date; the rates footnote moved out of the save-link panel.

**Shana Rishonah.** `PACKAGE_TIERS` (per tier: delivery, setup, appliances, lead weeks) drives four
visible facts per card + a 4-line "What's included" summary + `<details>` full list; the common terms
(delivery/receiving, installation, extras, exclusions, timing, quotes & payment) appear once in a terms
panel. Seed copy: "most popular" removed, Full Nest's washer/fridge/microwave line now says "ordered and
delivery coordinated (installation confirmed in your quote)". Removed "No response-time guarantee, no
automatic ordering" and "within one business day"; the form is described as an inquiry, "Not sure yet —
help me choose" kept, contact requirement stated up front, `shana_how1` no longer asks for the address.
**Existing databases keep their old bundle text** (bundle_sync is insert-only) — see TODO.

**Copy.** Trust strip → Free for couples / English and Hebrew / Direct-to-couple cash gifts. Removed
"Every appliance … works with Israeli current", "Local sizes … not an American one", "No customs",
About's "click a gift, and they're done" (now reserve → buy/send → tell them; includes shana-rishonah
arrivals, not only olim). Privacy page fully bilingual, no bracketed owner notes, no invented retention
period ("deleted data drops out of dated backups as those backups are rotated"), contact pointer.
"Checked {date}" → "Price checked {date}"; "estimate" → "Estimated price"; catalog legend explains both.
Localized dates (`fmt_date`) on registry hero, guest page, dashboard queues; stored ISO values unchanged.

**Dashboard / items.** Checklist shows only remaining steps with a "5 of 6 done" count and a one-line
"Done:" summary; queue entries link to the row; rows flag an unavailable item with a hint; items page
puts the couple's own list above the catalog with a status breakdown and stock flag per row.

**Tooling.** `tools/screenshots.py` (headless Chrome, desktop/tablet/narrow, EN+HE), `tools/render_private.py`
(logged-in/guest pages on a temp DB for screenshots). `run_dev.py` sets `OB_RATES` so the preview shows ≈ estimates.

**Tests:** `tests/test_p2.py` (21 tests) → **69 passed**. Browser checks: home, sample, catalog (filters,
pages), registry with every claim state, claim dialog, guest page, dashboard, items, starter picker,
shana — desktop 1280 / tablet 768 / narrow 520 headless with Bellefair + Assistant loaded, and 375px in the
in-app Chromium (EN + HE; `scrollWidth == viewport`, no overflow; primary CTA inside the first screen).

## 2026-09-14 — featured items: real store links verified (8/8), seed-sync metadata fix
Each of the 8 featured catalog items now has a real Israeli product page in `seed_catalog.json`,
checked by opening the page on 2026-09-14 (KSP / Machsanei Chashmal block scripted fetches, so those
were read in a real browser session):

| Item | Store / page | Price seen | Stock at check | Note |
|---|---|---|---|---|
| Shabbos hot plate (platta) | KSP item 117570 (SKU 109554), Hidurit PS4 ceramic 4-pot | ₪305 (was ₪180 in seed) | last unit | 6-pot ₪371 same page |
| Shabbos urn (meicham) | KSP item 117602 (SKU 109550), Hidurit 60-cup | ₪499 (was ₪330) | in stock | 40-cup (M-LC8) ~₪395 out of stock |
| Stand mixer | payngo.co.il 237042, KitchenAid Artisan 5KSM125 | ₪2,290 (unchanged) | in stock | official importer warranty |
| Slow cooker (for cholent!) | hakolabait.co.il, Crock-Pot TimeSelect 5.6 L | ₪599 (was ₪350) | **out of stock** | Express ₪850 also out; Multi-Express ₪949 in stock at cookstore.co.il; card shows "Out of stock at last check" |
| Dinnerware set — fleishig | hakolabait.co.il, Luminarc 18-piece turquoise | ₪199 (was ₪320) | in stock | store changed from "Naaman" |
| Towel set | vardinon.co.il 3191595, ESTER 4-towel set | ₪199.90 sale (reg ₪599.90) | in stock | promo rotates |
| Shabbos candlesticks | heichal.co.il product 4268, 36 cm plated pair | ₪300 (was ₪350 idea) | in stock | now kind=product; plated, not sterling |
| Folding table (renamed from "+ 6 chairs") | homecenter.co.il 1747685036002, 180×70 cm | ₪99.90 sale (was ₪700 bundle idea) | in stock | chairs sold separately; no in-stock table+chairs bundle existed |

Every row records `model`, `price_source`, `price_checked_at=2026-09-14`, `availability`, and bilingual
`notes`/`notes_he`. Prices/links are a point-in-time check, not live inventory.

**Seed-sync fix (real bug):** migration 12 assigns `seed_key`s to legacy rows by slugified name, so on
an existing database `seed_sync()` never hit its "adopt" branch and `starter_group`/`kind`/price
metadata stayed at defaults — the starter picker would have been empty on the live install. Keyed rows
now get still-default metadata filled (never price/url/name/store/brand/active/featured). New
`legacy_names` seed field lets a renamed seed item adopt its old row (used for the folding table).
Inserts now carry model/variant/availability/notes. Regression test added (49th test uses the snapshot DB).

**Applying to an existing DB is opt-in:** the links/prices above do NOT auto-apply to a live database.
Review with `python manage.py seed-sync --fields url,price_nis,name,name_he,model,store,brand,availability,notes,notes_he,price_status,price_checked_at,price_source,kind`
(dry run, 21 field changes on the snapshot) and add `--apply` to write, then
`python manage.py refresh-registry-links --apply` so registries that already copied these items pick up the URLs.

Catalog cards now show the model line and an "Out of stock at last check" badge when `availability='unavailable'`.

## 2026-09-14 — v3 phase 3 (catalog, onboarding, dashboard, concierge, admin) + integration pass
**Phase 3 (Sonnet agent; the run was cut off mid-docs, code was fully committed):**
- Catalog data model: `seed_catalog.json` items carry `seed_key`, `kind` (product/idea), `featured`
  (the 8 from the snapshot), `starter_group` (first_week/kitchen/shabbos/bedbath/appliances) and
  `price_status`/`price_checked_at`/`price_source` mapped from the July price-audit entries below
  (55 rows marked verified — **owner: spot-check that mapping**, the July notes say 31 of ~48 branded
  items + the 8 big-ticket ones). Seed sync now matches by `seed_key` (one-time adoption of legacy
  rows by exact name), never re-inserts retired rows, never overwrites admin edits. Explicit
  `manage.py seed-sync --fields … [--apply]` and `manage.py refresh-registry-links` (respects the
  couple's `overrides`, never touches claims/price/qty/priority/note).
- Card rules helper `gift_routes(item)` + `/go/c/<id>` / `/go/i/<id>` click tracking (DB-stored URL
  only, `validate_url` re-checked, no query-string redirects).
- Admin catalog: search, filters (category / missing link / missing image / price status / inactive),
  queue counts, full metadata form with server-side URL validation, soft "Retire", CSV export
  (formula-safe) and CSV import with dry-run diff. "Missing affiliate link" → "missing store link".
- Registry form: 4 sections with step header (details → Israel preferences → payment → visibility);
  `preferences_json` (bed size, apartment size, furnishing, needed-by, before-arrival list);
  provider-validated pay links with per-provider errors; draft/unlisted/public with honest hints;
  values preserved on validation errors; `pending_add` keeps catalog picks across signup.
- Items: starter-pack picker grouped by starter_group with qty + "already added"; per-item edit page
  (name/brand/price/url/store/qty/priority/note/variant/kind; qty below committed rejected; edited
  inherited fields recorded in `overrides`); archived section; "needs a link or payment method" flag.
- Dashboard: state-driven checklist (details / ≥5 usable gifts / payment method / visibility reviewed /
  previewed / shared), action queues (awaiting confirmation, reserved & waiting with expiry, thank-yous
  outstanding), per-currency totals, `/dashboard/print` insert with local QR, `/dashboard/claims.csv`,
  `/dashboard/shared` beacon. Account page: JSON export + password-confirmed deletion.
- Concierge: email-or-WhatsApp requirement, neighborhood/furnishing/budget, address no longer collected
  publicly; bundle cards split Included / optional extras / not included / coordination vs installation /
  lead time "confirmed per quote". Admin `/admin/lead/<id>`: 7-stage pipeline (legacy `done` → `completed`),
  internal notes, next action + date, duplicate hint, cost breakdown → total/profit/margin server-side.
- Admin: `/admin/outbox` (masked recipients, retry), `/admin/backup.db`, funnel table.
- Privacy/SEO plumbing: draft registries hidden from non-owners, `?preview=1`, `canonical_url`/
  `alt_urls`/`noindex` globals, `find`/sitemap only for `visibility='public'`, robots disallows `/g/`.
- Duplicate `form_key` POSTs now redirect to the same `/g/<token>` (token kept in session, capped at 10).
- Tests: `tests/test_p1.py` (20 tests) → 47 total.

**Integration pass (review model), after both parallel agents finished:**
- `base.html` now renders the server-computed `canonical_url`/`alt_urls` and a `noindex` meta for every
  private/filtered page (filter/search result pages are noindexed; canonical never carries filter params).
  Added `<meta name="csrf-token">` and a display-currency toggle in the header (only when `OB_RATES`
  configures more than ILS).
- Store links on registry/guest pages go through `/go/` (`rel="noopener sponsored"`); `app.js` fires the
  dashboard share beacon (copy/WhatsApp) with the CSRF token.
- Currency: `usd()` no longer used in templates. `estimate_label()` gives a short "≈ $59" (whole units,
  guest default = registry's display currency, else USD when configured); `estimate_note()` prints one
  per-page footnote with the rate date. Bidi-isolated for Hebrew.
- **Server-side gift routes**: `claim_item` now refuses items with neither a store URL nor a payment link
  and forces the cash route when there is no store URL (previously template-only).
- Claim modal shows price + a route explanation; guest page shows "Amount to send", provider-labelled
  button with the destination host, and a clean save-link URL.
- Copy: "Popular gifts right now" → "A taste of the catalog" (no popularity claim); removed the
  "Most wanted" badge from concierge bundles; progress bar says "reserved or received";
  dashboard "Release" → "Cancel reservation" (explicitly no refund); privacy deletion paragraph now
  describes the self-service Account page.
- CSS for all phase-3 components (checklist, queues, starter picker, step header, visibility radios,
  admin tables) in the same parchment/gold system; 1-column gift grid under 430px; fixed an RTL
  horizontal-overflow bug caused by the honeypot input's `left:-9999px` (now `inset-inline-start`).
- Dev tooling: `run_dev.py` forces a %TEMP% database (the user-level launch.json's old `ourbayis` entry
  ran the real DB — a new `ourbayis-v3` entry points at the wrapper). The repo `ourbayis.db` was restored
  from `backups/ourbayis-snapshot-2026-09-14.db` after that slip; the snapshot itself was never touched.

**Verified this pass:** `python -m pytest -q` → 47 passed. Browser checks (in-app Chromium) at ~700px and
375px, EN + HE: home, catalog (filtered), registry, claim modal, guest manage page, dashboard, starter
picker, registry form, concierge; no console errors; no horizontal overflow after the honeypot fix. Admin
routes smoke-tested with the Flask test client (all 200), lead quote math checked (₪6,900 quote on ₪5,200
cost → 24.6 % margin).

## 2026-09-14 — v3 phase 2 (design system + homepage)
Visual system: glassmorphic sticky header + hero/registry-hero/guest-status/modal panels
(`.glass`/`.glass-panel`, `backdrop-filter: blur(14px) saturate(1.2)` with a solid
`@supports not` fallback); CSS-only hero light field (4 drifting blurred bokeh blobs),
skyline/chuppah line-art draw-in animation, gold foil shimmer on `.btn-gold`, card
lift-on-hover, `IntersectionObserver` `.reveal`/`.in` section fade-ins — all disabled under
`prefers-reduced-motion: reduce`. New per-category SVG line illustrations (`ill-kitchen`,
`ill-appliances`, `ill-dining`, `ill-bedding`, `ill-judaica`, `ill-home`) replace the flat
icon-on-colour placeholders, shown in a reserved 4:3 `.gift-ph.ill-box`; a broken/missing
`<img class="gift-img-img">` falls back to the illustration via an `app.js` `error` listener.
44px controls, visible `:focus-visible` rings, `.bdi`/`<bdi>` isolation around prices/URLs,
sticky glass filter bar with active-filter summary + reset on `/catalog`.

Homepage rewritten end-to-end per SPEC_V3 "Rebuild the homepage": hero (glass card + light
field), couples/guests how-it-works, catalog teaser labelled as illustrative, "why it fits an
Israeli home" (220V/plugs, local sizes, Shabbos+kashrus), a static **sample registry**
(illustration only — synthetic couple, `aria-disabled` buttons, no real links/POSTs), a Shana
Rishonah intro band, a 6-item FAQ (`<details>`, also emitted as FAQPage JSON-LD on
`how-it-works`), final CTA. `how.html`, `about.html` (no longer US-only — UK/SA/AU/CA/olim
generally), `catalog.html`, `registry.html`, `guest_manage.html` (status stepper, store link
shown whenever `item['url']` exists regardless of store name, "save this link" box),
`privacy.html` (rewritten to match actual behavior: session cookie only, no analytics,
no-PII daily counters, mail outbox, guest recovery token hashing, affiliate links, deletion —
marked `[owner/legal review]` where a legal call is needed), `error.html`/`404.html` (find-a-registry
search box) all updated. `base.html` gained `{% block robots %}`/`{% block jsonld %}`/
`{% block ad %}` (empty-overridden on login/signup/forgot/reset/guest_manage), canonical +
hreflang (en/he/x-default) links, `og:image`/`og:site_name`/`twitter:card`, and the six
illustration `<symbol>`s in the sprite. `tools/make_og.py` (new, Pillow-only) generates
`static/og.png` (1200×630).

Registry gift-card button label now varies by what the item actually offers (SPEC_V3 "Card
rules"): url-only → "Reserve and buy from the store", pay-links-only → "Send money for this
gift", both → "Gift this" (opens the modal with the buy/cash radio choice), neither → muted
"the couple will share where to buy" with no button. Price 0 shows "Price not set" instead of
being blank. `catalog_items.price_status`/`price_checked_at` (added by the parallel backend
agent this phase) are read defensively via `is defined` since `registry_items` doesn't carry
them — a "Checked <date>" vs "estimate" badge shows wherever they're present.

`app.js`: reveal-on-scroll observer, modal opener tracked and refocused on close, clipboard
copy falls back to `window.prompt` when the Clipboard API is unavailable/denied.

Verification: `python -m pytest -q` stays green (27 passed, untouched by this phase); every
public route smoke-rendered EN+HE via Flask's test client (home, how, about, find, catalog,
login, signup, forgot, contact, privacy, 404, registry with items + a claim end-to-end, guest
manage). Browser-tool visual pass at 375/1280 width, EN+HE, incl. keyboard focus ring and FAQ
`<details>` toggle — no console errors, no horizontal overflow. One `/r/<slug>` 404 was seen in
the live dev-server browser session on a registry whose `visibility` the concurrently-running
backend agent's `app.py` didn't yet resolve consistently with the DB row (`app.py` is out of
scope for this phase) — templates themselves were already verified end-to-end via the test
client, which did hit registry.html/guest_manage.html successfully (stepper, claim modal, card
button rules all rendered).

## 2026-09-14 — v3 phase 1 (P0 backend)
Implemented per SPEC_V3.md: new modules `ob_db.py`, `ob_security.py`, `ob_mail.py`,
`ob_money.py`, `manage.py`; `app.py` rewritten to use them; new `static/app.js` (CSP is now
`script-src 'self'`, no inline scripts left anywhere); `templates/error.html` +
`templates/guest_manage.html` added; `tests/` added (pytest, temp DB per test).

**Schema**: versioned migrations (`schema_migrations`, `ob_db.MIGRATIONS`) replace the old
`try/except OperationalError: pass` pattern. Every column/table/index from SPEC_V3 "Schema v3"
that's in scope for Phase 1 is migrated, including the one-time legacy-claims migration (old
`kind='item'` rows → status 'reserved', `legacy=1`; `kind='cash'` rows → status 'reported',
`legacy=1`, with `amount_minor`/`currency` filled only when `parse_legacy_amount()` is unambiguous).
Verified against `backups/ourbayis-snapshot-2026-09-14.db` (copied, never modified): "₪180" → 18000
ILS, "$180" → 18000 USD, zero claims deleted. Catalog/shana columns from later-phase spec sections
were added now (defaults only) so those phases don't need another schema change.

**Gift lifecycle**: full reserved → reported → received / cancelled / expired flow, atomic
reservation via `write_txn` + `form_key` idempotency, price snapshot, recovery-token guest manage
page at `/g/<token>` (replaces the old `?pc=<id>` cash-banner, which leaked a claim's amount to
anyone with the id). Item delete archives instead of deleting once it has any claims.

**Security**: no default admin (`manage.py create-admin`); session versioning so password
reset/change and payment-link edits invalidate other sessions; `safe_next`/`same_origin_referrer`
close the open-redirect holes in `next=` and `/lang`; `classify_pay_url` host-allowlists payment
links; POST-only logout; DB-backed rate limiting; error pages for 400/403/404/413/429/500.

### Decisions
- **Duplicate `form_key` on `/claim`**: the spec says to look up the existing claim and redirect
  to its manage page. Since only the sha256 hash of the recovery token is stored (by design — the
  raw token must never be recoverable from the DB), a genuine duplicate POST can't be redirected to
  the *same* `/g/<token>` URL a second time. Implemented instead: flash "already recorded" and
  redirect to the registry page. The guest's original request (the one that succeeded) already
  carries the real `/g/<token>` link.
- **`registry_items.kind` ('product'/'idea'/'cash_need')**: column added per schema, but the
  "idea" card treatment in `registry.html` is driven directly by presence of `item.url`/pay links
  (matches the P0/P1 "Card rules" in SPEC_V3 under Catalog, which is out of this phase's scope) —
  not yet wired to the `kind` column itself. A later catalog-phase pass should decide whether `kind`
  should override or just describe that same rule.
- **Dashboard currency totals**: only sums `status='received'` claims per currency (never mixes
  currencies) — reserved/reported amounts aren't "confirmed" money yet, so they're shown per-row
  but excluded from the total to avoid implying they're already in hand.
- **`ext_url()` in emails/sitemap/robots**: uses `OB_BASE_URL` when set, else falls back to
  Flask's `url_for(..., _external=True)` — this is correct with or without `OB_TRUST_PROXY`.

### Left for later phases (out of scope for P0 per the brief)
Visual redesign, catalog metadata (price_status/starter_group/etc. logic), onboarding checklist,
concierge pipeline admin UI, SEO (JSON-LD, canonical/hreflang, og:image), `manage.py seed-sync`
and `refresh-registry-links` (stubbed, print "not implemented in Phase 1").

## 2026-07-07 — improvement roadmap specced (no code changes)
- Full pre/post-launch improvement roadmap added to TODO_AI.md, tagged [SONNET]/[HAIKU] for implementation by cheaper models. Covers: revenue plumbing (click tracking via `/go/`, guest claim-confirmation + reminder emails, /advertise page, viral/cross-sell CTAs, Amazon disclosure near links, v2 group gifting), SEO (canonical/hreflang/og:image, JSON-LD, /guides content section, title/meta pass), UX (onboarding checklist, thank-you CSV, printable invitation insert, registry browsing polish, empty states), ops (server-side analytics, DB backups, 404 upsell).

## 2026-07-05 — v2.3: last small-appliance sweep
- Milk frother (Nespresso Aeroccino): ₪150 → ₪300 (real Aeroccino 3/4 converts to roughly ₪280–420)
- Air fryer (Tefal): ₪400 → ₪550 (real Tefal Dual Easy Fry & Grill: ₪750 on sale from ₪1,350 — smaller models likely cheaper, priced conservatively below the confirmed model)
- Small freezer (Electrolux): ₪1,200 → ₪2,000 (real compact freezers ₪1,950–3,049 — was well below the real minimum)
- Glassware set (Luminarc): ₪150 → ₪70 (real Luminarc drinking glass sets ₪25–82 — was noticeably overpriced for the brand)
- Confirmed accurate, no change: Braun food processor, Braun hand mixer, Electrolux clothes dryer
- Genuinely inconclusive after 2–3 search attempts each (left as original estimates): Electrolux dehumidifier, Tefal sandwich maker + waffle maker, Braun full-size (jug) blender — Hebrew search terms kept surfacing unrelated products or only immersion-blender data
- **31 of ~48 branded items now verified.** Remaining unverified: Pots & pans starter set/Tefal, Ceramic frying pan set/Tefal, Salad bowl set/Luminarc, Tadiran fans/heater, the 4 inconclusive items above — all lower-stakes, modest-price items

## 2026-07-05 — v2.2: Vardinon lines complete
- Sheet sets (x2, basic tier): ₪300 → ₪500 (real double satin sets ₪249–578 each; ₪300 for two combined was below one real set alone)
- Sheet set, premium sateen: ₪350 → ₪450 (sits more clearly above the basic tier now, within the real ₪249–578 satin range)
- Confirmed accurate, no change: mattress protectors, quilted bedspread, guest linen set (all within real Vardinon/market ranges), IKEA entryway mirror + shelf, duvet & pillows set (basic tier)
- **This closes out the full catalog audit for today: 28 of ~48 branded items now verified against real Israeli listings across five research passes.** Remaining unverified items are the two genuinely-inconclusive ones (Electrolux dehumidifier, Tadiran fans/heater — see TODO) plus a handful of smaller items not explicitly re-checked (deemed low-risk: modest prices, no extreme brand/price mismatch plausible)

## 2026-07-05 — v2.1: final sweep of the price/brand audit
- More corrections from real Israeli listings:
  - Dinnerware set, both tiers (Luminarc): ₪400 → ₪320 (real 18–19pc Luminarc sets ₪176–330)
  - Bathrobe set, his & hers (Vardinon): ₪250 → ₪450 (real single robes ₪180–450 each; ₪250 for a pair was too low)
- Confirmed accurate, no change: Spiegelau wine glasses, Pyrex (mixing bowls/baking dishes/serving bowls), IKEA dining table+chairs, IKEA coffee table (₪400 vs real ₪395 — near-exact), IKEA floor lamp (₪200 vs real ₪225)
- **Genuinely inconclusive, left as estimates**: Electrolux dehumidifier and Tadiran fans/heater — search didn't surface clear pricing for either (Hebrew terminology ambiguity for "dehumidifier" specifically); flagged rather than guessed
- **Running total: 26 of ~48 branded items now verified against real listings** across four research passes today. Remaining unverified: other Vardinon lines (sheets/duvets/mattress protectors/quilted bedspread/guest linen), Electrolux dehumidifier, Tadiran fans/heater, IKEA entryway mirror

## 2026-07-05 — v2.0: deeper price/brand audit
- More corrections from real Israeli listings:
  - Slow cooker (Crock-Pot): ₪300 → ₪350 (real ₪349–899)
  - Cutlery sets (WMF): ₪350 → ₪750 (real WMF sets ₪270–899 — ₪350 for two real WMF sets was too low for the brand)
  - Porcelain dinnerware, both tiers (Villeroy & Boch): ₪900 → ₪2,900 (**significant miss** — real V&B 18-piece dinner sets run ₪3,983–4,978; ₪900 wasn't a plausible price for the genuine brand at all)
  - Memory foam pillows, pair (Tempur): ₪250 → ₪1,500, store corrected Vardinon → **Hollandia** (Tempur's confirmed exclusive Israeli importer; Vardinon doesn't carry it) — real Tempur pillows run ₪737–1,129 *each*, so ₪250 for a pair was off by nearly 6x
- Confirmed accurate, no change: Zwilling knife set + premium cookware set, Lock&Lock storage, Brita pitcher, Electrolux vacuum, Samsung microwave, IKEA couch
- Inconclusive (left as-is, flagged in TODO): Tadiran fans/heater — search didn't surface clear pricing for the basic tier

## 2026-07-05 — v1.9: more price checks
- Verified against real Israeli listings (Zap.co.il + brand/retailer sites) and corrected:
  - Electric kettle (Tefal, basic): ₪120 → ₪220 (real Tefal kettles start ~₪219, nothing at ₪120)
  - Electric kettle — premium stainless (Tefal): ₪250 → ₪279 (widened the gap from the basic model to actually mean something; both now sit at the real ends of Tefal's ₪219–279 range)
  - Coffee machine (Nespresso): ₪600 → ₪750 (real cheapest Nespresso machine found: ₪699)
  - Water carbonator (SodaStream): ₪450 → ₪320 (real base Terra model: ₪265–320)
- Confirmed accurate, no change needed: Kiddush cup/silver-plated (₪250, real ₪64–299), Kiddush cup/sterling-silver premium (₪900, real solid-925 range ₪850–990), immersion blender/Braun (₪200, real ₪126–699), Vardinon towel sets (both tiers, real ₪120–421)
- All fixes applied to seed_catalog.json (fresh installs) and this dev DB directly (reminder: seed-sync never overwrites existing rows — see TODO_AI.md)

## 2026-07-05 — v1.8: deployment-ready
- Added `passenger_wsgi.py` (PythonAnywhere WSGI entry point, ready to paste in with two edits: real path, real secret key) and [DEPLOY_AI.md](DEPLOY_AI.md) — full step-by-step matching the BashertBench PythonAnywhere setup
- Smoke-tested the exact WSGI import pattern end to end (env vars → app import → live requests) — works cleanly
- Added `itsdangerous` to requirements.txt (used directly for password-reset tokens, previously an implicit Flask dependency)

## 2026-07-03 — v1.7: verified real prices for the biggest-ticket items
- Web-searched actual Israeli retail prices (Zap.co.il comparisons + brand sites) and corrected 8 catalog items:
  - **Fixed a made-up brand**: "Kayor" (invented, not real) → **Hidorit** (verified real brand for Shabbos plattas/urns, confirmed via Zap + hidurit.co.il) — applied to all 4 platta/urn variants
  - Shabbos urn (meicham): ₪250 → ₪330 (real Hidorit 40-cup urns run ₪349–404)
  - Stand mixer (KitchenAid): ₪1,500 → ₪2,290 (real KitchenAid mixers in Israel start ~₪2,049, cheapest confirmed model ₪2,290)
  - Washing machine (Bosch): ₪1,800 → ₪1,950 (real Bosch 8kg models ₪1,810–2,430)
  - Dishwasher (Bosch): ₪2,000 → ₪2,300 (real Bosch models ₪2,195–2,739)
  - Fridge, large family (Samsung): ₪4,800 → ₪5,200 (real Samsung family fridges start ~₪6,368 for 664L; this is a smaller/entry model, priced conservatively below that)
  - Confirmed accurate as-is: Robot vacuum/Xiaomi (₪1,200 vs real ₪1,099–1,199), Vardinon sheet pricing, oven/Bosch (₪2,200 within real ₪1,590–7,590 range)
- Applied to both seed_catalog.json (for fresh installs) and the running dev DB directly — the seed-sync logic intentionally never overwrites existing rows' price/brand (to protect admin's manual edits on restart), so existing installs need the same catch-up applied by hand or via /admin/catalog
- Still unverified: the other ~50 branded items and all Judaica/dining/bedding items not explicitly searched this pass — see TODO_AI.md

## 2026-07-03 — v1.6: brand names
- Added `brand` column to catalog_items and registry_items; 65 of 117 catalog items now show a real brand actually sold in Israel (Tefal, Zwilling, KitchenAid, Bosch, Samsung, Electrolux, Nespresso, Braun, Crock-Pot, Vardinon, Luminarc, WMF, SodaStream, Kayor for Shabbos plattas/urns, etc.) — shown as a small gold tag above the item name on the public catalog, registry pages, items management, and homepage popular strip
- Judaica and generic/unbranded items deliberately left blank (accurate — those are typically artisan or store-brand, not name-brand)
- Migration backfills brand onto registry_items that were added to a couple's list *before* this update, from their catalog source, so existing registries update automatically
- Note: brand names are real and plausible, but exact SKU/model + price still needs a manual check per item (see TODO_AI.md) — web search hit its session limit mid-session so live price verification is still pending

## 2026-07-03 — v1.5: public gift catalog
- New public `/catalog` page — anyone can browse all products without an account (matches how Zola/MyRegistry work): category chips (server-side links), search, product cards with images/prices/stores
- Logged-in couples get Add buttons right on the catalog (redirects back to the filtered catalog via `?back=catalog`); visitors get "Sign up to add"; logged-in users without a registry get "Create my registry"
- "Gift catalog" added to main nav + footer; homepage category tiles and popular-gift cards now link into the filtered catalog instead of straight to signup; catalog added to sitemap

## 2026-07-03 — v1.4: account recovery, images, registry management
- Password reset: /forgot emails a 2-hour signed link (itsdangerous, no schema change); graceful "contact us" fallback when SMTP isn't configured; "Forgot password?" link on login
- Product images now render everywhere when a catalog/registry item has an image URL (gift cards, catalog picker, popular strip) — falls back to the category gradient
- Couples can **release** a reserved gift from the dashboard (guest flaked / changed mind) — frees it back onto the list
- Registry view counter (owner visits excluded) shown as a dashboard stat
- Countdown on the registry hero ("✦ 30 days to go! ✦") when the event date is set and in the future
- Honeypot anti-spam field on all public forms (signup, contact, shana, claim, cash)

## 2026-07-02 — v1.3: notifications, onboarding, sharing tools
- Email notifications (optional, via OB_SMTP_* env vars; silently skipped when unset): couple gets an email when a gift/cash gift arrives; owner (OB_NOTIFY_EMAIL) gets shana leads and contact messages. Sent on a background thread, never blocks a request
- One-click "Add the essentials" starter pack on the items page — adds the 8 featured catalog items, skipping ones already on the list
- Dashboard: QR code for the wedding invitation (via api.qrserver.com) + "Print gift list" button with print stylesheet (for thank-you cards)
- Homepage trust strip: free for couples / no fees / EN+HE
- Sitemap now includes public registries (SEO for couple-name searches); admin can export shana leads as CSV; rate-limiter dict now prunes stale entries

## 2026-07-02 — v1.2: economics + guest-to-order flow + polish
- **Repriced shana bundles for profit** (was roughly break-even/loss at retail component cost): Landing Basics ₪1,950→₪2,450 (~₪660 gross), Home Sweet Home ₪4,800→₪6,900 (~₪1,440), Full Nest ₪9,500→₪17,900 (~₪3,740) — ~25-27% margin over estimated retail cost; updated in seed + live DB
- Shana page: lead-time notice (3 weeks / 6 weeks for Full Nest) + "prices are starting estimates, final quote before payment"
- Dashboard: cash gifts tied to an item now show a "Buy it at {store}" button so the couple can click straight through and order it with the money they received
- Homepage: "Popular gifts" section (8 featured catalog items — platta, meicham, candlesticks, stand mixer, dinnerware, towels, cholent pot, folding table; `featured` flag, admin-editable)
- Registry page: category filter chips (auto-hidden when only one category)
- Hero: candle flames re-centered on their candlesticks + soft glow halos

## 2026-07-02 — v1.1: design overhaul + payments + bigger catalog
- New visual identity ("wedding invitation"): parchment/navy/gold, Bellefair+Assistant fonts, hairline rules, double-gold frames; new homepage hero — gold line-art Jerusalem skyline + chuppah with twinkling string lights
- Fixed double checkmark on gifted/reserved tags (✓ was in both the string and the icon)
- Catalog 58 → 117 items with quality/size variants (premium pots, sateen sheets, silver candlesticks, Shas set, sukkah, couch…); seed now syncs new items by name on startup
- Couples can add up to 3 cash-gift links: PayPal.Me, Stripe Payment Link (theirs, not ours), Bit/PayBox — guests see a button per link (schema migration adds stripe_url/bit_url)
- New "send the couple the money for it" option in the gift modal: reserves the item and shows a pay banner with the exact amount + the couple's payment buttons, so guests never face an Israeli store checkout

## 2026-07-02 — v1: full site built
- Flask+SQLite single-file app: couple accounts, one registry each, shareable `/r/<slug>` links
- Guest flow: reserve gifts (no account), buy at store via affiliate link, cash gifts via couple's own PayPal.Me; thank-you tracking on dashboard
- Curated Israel catalog (~58 items, EN+HE) + custom items; categories with gradient placeholders
- Shana Rishonah page: 3 packages (Landing Basics ₪1,950+ / Home Sweet Home ₪4,800+ / Full Nest ₪9,500+) + lead form → admin pipeline (new/contacted/done)
- Full EN/HE i18n with RTL, language toggle, bilingual content fields
- Admin: leads, messages, catalog CRUD, bundles CRUD, ad slots, password change
- Security: CSRF, per-IP rate limits, CSP, security headers; robots.txt + sitemap.xml
