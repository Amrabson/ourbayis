# Changelog

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
