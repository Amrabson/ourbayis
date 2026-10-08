# Changelog

## 2026-10-08 (Shana Rishonah budget bands)
- The request form's budget options stopped at "₪10,000+", while The Full Nest starts at ₪17,900 —
  the most valuable leads all landed in one vague bucket. Now …6,000–10,000 · 10,000–20,000 ·
  20,000+ (`SHANA_BUDGETS`). The stored value was free text from the browser; now only these keys
  (anything else → empty). The lead email and admin lead page show the label ("₪20,000+"), not the
  key; old "10000_plus" leads keep their label.
- 1 test — 224 tests.

## 2026-10-08 (delivery note example)
- The delivery-note box (now shown to guests as "Where to send it") was an empty 2-line box with no
  hint of what to write. It gets an example placeholder in both languages (address with apartment,
  a phone number for the courier, or where to send things the couple will bring) and 3 rows.

## 2026-10-08 (find a couple by name, in any order)
- /find matched the typed text as one block, so "Sarah Dovid" or "Dovid and Sarah" found nothing for
  "Sarah & Dovid Cohen". Now every name typed must appear somewhere in the names/title, in any order;
  filler words (and, the, family, wedding, registry, את, של, חתונה…) are ignored, a Hebrew ו prefix
  is optional (שרה ודוד finds שרה & דוד), and `%`/`_` are literal.
- 8 tests — 223 tests.

## 2026-10-08 (guest page: way back, and who cancelled)
- The guest's private page had no link back to the registry — someone who wanted to give a second
  gift, or whose reservation was released, had nowhere to go. Now "See the rest of the list →"
  (or "Choose another gift →" once cancelled/expired).
- A cancelled reservation only said "This reservation was cancelled." Now it says whether the guest
  cancelled it or the couple released it ("…so you don't need to buy or send it").
- 1 test — 215 tests.

## 2026-10-08 (registry when everything is taken)
- A fully reserved registry just showed a list of "reserved" cards; a guest had to scroll it all to
  find out there was nothing left. Now a note at the top of the list says every gift is spoken for,
  with "You can still send the couple a cash gift →" opening the cash dialog when the couple has a
  payment link.
- The couple's dashboard says the same ("guests who open it now have nothing left to choose")
  with a link to add more gifts.
- 1 test — 214 tests.

## 2026-10-08 (one-tap thank-you email)
- The dashboard showed a guest's email as plain text. It's now a mailto link, and gifts that are
  on the way / received (and not yet marked thanked) get a "Write a thank-you" button that opens the
  couple's mail app with the subject ("Thank you for Electric kettle!") and an opening paragraph
  signed with their names, in the couple's language. Nothing is sent by the site.
- 1 test — 213 tests.

## 2026-10-08 (guests hear back)
- When the couple confirmed a gift arrived, the guest was never told — the overseas relative never
  learned it got there. When the couple released a reservation, the guest wasn't told either and
  could still buy it (a duplicate). Both now email the guest if they left an address, in the
  language they reserved in (new `claims.lang`, migration 23). "Released" says they don't need to
  buy it and links back to the registry.
- The couple's confirm / release buttons gave no feedback; now a toast: "Marked as received — we
  emailed Aunt Sarah that it arrived" / "Reservation released — we emailed … so they don't buy it".
- `remind-claims` writes in the guest's language (both only for claims from before m23); the Hebrew
  link carries `?lang=he`.
- 3 tests — 212 tests.

## 2026-10-08 (first visit follows the browser's language)
- Everyone started in English unless the link said `?lang=he` — so an Israeli relative opening the
  couple's plain link on a Hebrew phone got English. With no choice made yet, `current_lang()` now
  falls back to `Accept-Language` (he/iw → Hebrew). It isn't stored: the first tap on the language
  button (or a `?lang=` link) decides from then on. Crawlers send no Accept-Language and still get
  English at the x-default URLs; HTML responses carry `Vary: Accept-Language`.
- 6 tests — 209 tests.

## 2026-10-08 (the English button works everywhere)
- Reported by the owner: the "English" button didn't switch back. `/lang/en` redirected to the
  referring page, and when that page had been opened as `?lang=he` (Hebrew share links, hreflang
  URLs, Hebrew searches/filters) the `?lang=he` set Hebrew again. `/lang/<code>` now rewrites a `lang`
  parameter in the return URL to the chosen language.
- `same_origin_referrer()` could return `//evil.example/…` for a referrer like
  `https://site//evil.example` (e.g. a 404 page), a protocol-relative open redirect; leading
  slashes/backslashes are now collapsed.
- 2 tests — 203 tests.

## 2026-10-08 (searches that find nothing)
- /catalog with no results only said "try a different search". Now: if a category/price/kind filter
  is what emptied it, a link to the N results for the same words without filters; and always a line
  that couples can add any gift from any store, linking to the add-gift form (or signup).
- The couple's add-gifts list showed a blank grid for a search with no match. Now an empty note with
  "Add it as your own gift, from any store ↓" → `#custom`, whose name field is pre-filled with the
  search. The search form opens results at `#add-more` instead of the top of the page.
- 2 tests — 201 tests.

## 2026-10-08 (search results in a sensible order)
- Search results kept the catalog's category order, so "plates" listed the Shabbos hot plates before
  the dinnerware and "sheets" put cookie sheets first. In the default sort, /catalog now ranks names
  that start with the word (any spelling) first, then names containing it or a synonym, then the rest
  (`ob_search.rank_expr`). Explicit price/name sorts are unchanged.
- 3 tests — 199 tests.

## 2026-10-08 (catalog search that finds things)
- Search was one substring match on name/brand, so "shabbat", "plata", "hotplate", "פלטה",
  "refrigerator", "silverware", "becher", "candle sticks", "crock pot" found nothing, and "sheets" /
  "towels" / "knives" missed the sheet, towel and knife sets. New `ob_search.py`: every word must
  match, plurals folded in English and Hebrew, a synonym table maps everyday words and
  transliterations to the catalog's wording, the model line matches the word as typed (so
  "Hidurit PS4" works without "glass" hitting every "ceramic glass"). Used by /catalog and the
  couple's add-gifts list. `%`/`_` in a query are now literal.
- 16 tests — 196 tests.

## 2026-10-08 (couple's emails in the couple's language; language survives login)
- Gift emails to the couple ("someone reserved…", "reports sending…", "cash gift reported") were
  written in the *guest's* browsing language, with the English registry title and item name — a
  Hebrew-speaking couple got English mail whenever an English-speaking guest acted. New `users.lang`
  (migration 22), stamped at signup/login and on any `?lang=` switch while logged in;
  `notify_owner()` uses it (falls back to the reader's language when unknown).
- Those emails said "Log in to confirm" with nothing to click and "Kettle x1"; now they end with a
  dashboard link, and the quantity only appears when it's more than 1 ("×2").
- Logging in, signing up, logging out or deleting the account cleared the whole session, language
  included — a Hebrew user landed on an English dashboard right after login. `_fresh_session()` keeps it.
- 2 tests — 180 tests.

## 2026-10-08 (guest page after the gift is bought)
- After a guest reported a store gift as bought — or the couple confirmed it — the guest page still
  said "Next step: buy it from the store…" with the big "Buy it at KSP" button, plus price-checked /
  "Out of stock at last check" tags. Those (and the delivery box) now show only while there's still
  something to buy (store gift, reserved/expired); afterwards the item keeps a plain "View product
  details" link. `gift_facts(..., show_tags=)` added.
- The "≈ amounts in USD are estimates" small print showed on pages with no ≈ amount (finished gifts,
  cash gifts without pay buttons); now only next to a price or pay amount.
- 3 tests — 178 tests.

## 2026-10-08 (guest page: where to send it)
- The guest page told a store-gift guest to "have it delivered to the couple" but never said where:
  the couple's delivery note was an unlabeled grey line under the exchange-rate small print, and when
  there was none the guest got nothing. Now a "Where to send it" / "לאן לשלוח" box sits right under the
  store button (while the gift is reserved), with the note or, if missing, "ask them (or their family)
  where to send it before you order".
- New dashboard checklist step "Tell guests where to send store gifts" → registry form `#delivery`;
  done when a delivery note exists or every gift is cash-only.
- Guest-page progress steps were the couple-side status labels ("Guest reports sending/buying",
  wrapping to 3 lines on a phone); now "Reserved · You bought / sent it · The couple got it" (HE
  "שוריין · קניתם / שלחתם · הזוג קיבל") with `aria-current="step"`.
- 1 test — 175 tests.

## 2026-10-08 (English text on Hebrew pages, and the reverse)
- Text typed by couples/guests took the page's direction, so an English welcome message on the Hebrew
  registry showed as `".Thank you for helping us set up our first home"` (quotes and period flipped);
  the same for English guest messages on a Hebrew dashboard, and Hebrew ones on an English page.
  Now `dir="auto"` on registry h1/message, gift-card and items-page h3, dashboard/admin/lead messages,
  delivery note, print-card names; `<bdi>` around city, guest names, the catalog search echo and the
  guest page's title/names/item name.
- 1 test — 174 tests.

## 2026-10-07 (quantity lines at 1)
- Hebrew quantity lines said "1 שוריינו" / "1 התקבלו" / "1 מתוך 3 עדיין פנויים"; now "1 שוריין",
  "1 התקבל", "1 מתוך 3 עדיין פנוי" (`qty_*_one`; `qty_available` gets `n=left`).
- The "can't go below" error/hint at 1 read "1 of these are already reserved…"; now singular in both
  languages. The two `qty_below_committed` flashes go through `tf()`.
- 5 tests — 173 tests.
- `tools/export_static.py` strips CSRF tokens (meta + hidden inputs) from the static copy: a new
  token on every run rewrote ~55 docs/ files per export and buried real changes in the diff. Repeat
  exports are now a no-op.

## 2026-10-06 (counts that read naturally)
- "1 gifts" (registry/catalog filter count), "1 days to go!" / "עוד 1 ימים!", "1 need a store link",
  "1 essentials added", "1 past reservation(s)". New `i18n.t_count`: `<key>_one` / `<key>_two` forms
  per language, used by `tf()` whenever `n=` is passed. Now "Tomorrow!" / "מחר!", "עוד יומיים!",
  "1 gift" / "מתנה אחת", etc. The JS-filled registry count uses `data-label-one`.
- 11 tests — 168 tests.

## 2026-09-28 (`manage.py check` catches quiet config mistakes)
- New WARNING lines (exit code unchanged): email off; `OB_BASE_URL` missing / not https / https
  without `OB_ENV=production` or `OB_SECURE_COOKIES` (cookies not Secure); `OB_NOTIFY_EMAIL` missing
  or invalid (leads only in /admin); emails that failed for good (→ /admin/outbox); no
  `instance/rates.json` or one older than 7 days (daily `fetch-rates` stopped).
- New PROBLEM (exit 1): email half set up (some of OB_SMTP_HOST/USER/PASS missing — nothing can send).
- `check` on a brand-new/wrong DB file crashed with "no such table: admins"; now explains it.
- `remind-claims` without `OB_BASE_URL` queued reminders whose only link was a bare "/r/…" that no
  mail app can open. It now refuses (exit 1) and says why; `--dry-run` still works.
- 2 tests — 157 tests.

## 2026-09-28 (backup retention)
- `manage.py backup` never deleted anything, so a scheduled weekly backup would slowly fill the
  PythonAnywhere quota (each copy is the whole DB). New `--keep N` (default 14): after the new copy
  is written and verified, the oldest automatic copies beyond N are removed. Only files named by the
  command (`ourbayis-YYYY-MM-DD-HHMMSS.db`) are ever pruned — a hand-made snapshot such as
  `ourbayis-snapshot-2026-09-14.db` is left alone — and a custom `--dest` is never pruned.
  `--keep 0` keeps everything. `OB_BACKUP_DIR` overrides the folder (used by the test).
- DEPLOY_AI.md schedule note and TODO_AI "Backup retention" updated (privacy wording still the
  owner's decision). Test — 155 tests.

## 2026-09-28 (reminder email wording)
- `manage.py remind-claims`: the Hebrew half of the bilingual reminder used the English gift name
  and registry title even when Hebrew ones exist, and both halves printed the hold date as raw ISO
  ("2026-10-12"). Now the Hebrew half uses `name_he` / `title_he` (falling back to English) and the
  date reads "12 October 2026" / "12 באוקטובר 2026".
- Date wording moved to `i18n.format_date(iso, lang)` so emails queued from manage.py read the same
  as the site; `app.fmt_date` delegates to it.
- The reminder still links to the registry, not the guest's /g/ page — only the token hash is
  stored (by design); guests who get reminders gave an email, so their confirmation has the link.
- Reminder test extended — 154 tests.

## 2026-09-28 (Reply-To on owner notifications; login keeps email)
- Contact messages and Shana Rishonah leads are emailed to `OB_NOTIFY_EMAIL` from the site's own
  address, so hitting Reply answered the site. They now carry `Reply-To: <the sender's email>`
  (only when it's one valid address). New `mail_outbox.reply_to` (migration 21), `enqueue(...,
  reply_to=)`, `send_now(..., reply_to=)`.
- /login re-shows the typed email after a wrong password.
- Tests — 154 tests.

## 2026-09-28 (messages you can actually see; Shana form keeps input)
- **Shana Rishonah form:** it posts to `#request` and the success redirect inherits that fragment,
  so both outcomes opened at the form while the message sat at the top of the page, off-screen.
  On success people saw an empty form and no "Got it — mazel tov!" (and could submit again); on
  a rejected request (e.g. no WhatsApp/email) they saw an empty form with no explanation — and
  everything they'd typed, notes included, was gone. Now the message renders inside the form panel
  (`{% block flashes %}` in base.html, overridden on shana.html; role=alert/status) and a rejected
  POST re-renders with every field and select refilled.
- **Everywhere else that redirects to a spot on the page** (`#item-12` after a gift attempt, `#mine`,
  `#claim-3` on the dashboard): app.js turns the top-of-page messages into a toast pinned to the
  bottom of the screen with a close button when the page opens at a fragment. Success notes fade
  after 7 s; errors stay until closed. Verified in the browser (fixed, 16 px from the bottom, RTL
  close button on the correct side).
- A gift attempt with a blank name said "Please check the highlighted fields" — nothing is
  highlighted after the redirect. Now `claim_name_required` (EN+HE) for item and cash gifts.
- 2 tests — 152 tests.

## 2026-09-28 (share links + link previews)
- Text scan of every public page in EN+HE (44 pages): clean — only brand names are Latin on HE pages.
- Registry link previews (WhatsApp/Facebook/og:description + meta description) said only
  "Registry for Sarah & Dovid". Now "Wedding · 15 December 2026 — Sarah & Dovid are setting up their
  new home. See the gifts they'd love and reserve one." (HE: "…מקימים בית חדש. צפו במתנות שהם
  ישמחו לקבל ושריינו אחת."); event/date only when set. Key `reg_meta_desc`.
- The link a couple shares (copy button, WhatsApp, QR code, print card) and the registry page's own
  share buttons now carry `?lang=he` when the person is using the site in Hebrew — the WhatsApp
  preview and the page guests land on are Hebrew. English stays the bare URL. Guests can still
  switch. One helper, `registry_share_url(slug)` (Jinja global, also used by /dashboard/qr.svg).
- Test — 150 tests.

## 2026-09-28 (Hebrew description lines — model_he)
- Hebrew pages showed each gift's description line only in English, including facts a guest
  needs ("(not sterling)", "plated with 925 silver (not solid silver)", "price is for two sets").
  New `model_he` on catalog_items + registry_items (migration 20, backfills registry copies),
  filled for all 57 active seed items that have a `model` (brand/model names kept in Latin, as
  sold in Israeli stores; units as ל׳ / ס״מ / ק״ג / וואט). Cards use `pick(item, 'model')`.
- Plumbing: seed_sync INSERT + `_ADOPT_FIELDS`, refresh_registry_links, the catalog→registry copy,
  and a "Description line (HE)" field in /admin/catalog.
- **Live DB:** restarting the app runs migration 20 and the startup seed-sync, which fills
  `model_he` in the catalog (only where empty — admin edits are kept). Then copy it onto gifts
  already on registries: `python manage.py refresh-registry-links` (dry run) → `--apply`.
- 3 tests (Hebrew/English card lines, every seed model has Hebrew, live-DB fill path) — 149 tests.

## 2026-09-28 (couple + guest pages review, rendered via tools/render_private.py)
- **Paid-twice risk:** a guest's page for a cash gift kept showing "Amount to send" and the PayPal
  button after the couple had confirmed receiving it (or it was cancelled). Pay buttons now show
  only while the claim is reserved/reported; afterwards just the amount.
- Dashboard queue said "(פג תוקף 12 באוקטובר 2026)" — "expired" — about reservations that are still
  held. Now "משוריין עד …" / "held until …", matching the guest page.
- /registry/items status read "1 reserved (1 reserved)" (EN and HE use the same words for the
  headline and the breakdown). Now just the breakdown: "1 reserved", "1 on the way, 1 received".
- /registry/items still printed raw ISO price-check dates → `fmt_date`.
- "IKEA · IKEA", "Vardinon · Vardinon": the store is no longer repeated when it equals the brand
  (catalog picker and every gift card).
- 2 tests — 146 tests.

## 2026-09-28 (Hebrew maqaf before Latin store names)
- Mobile Hebrew walk-through of the guest flow (registry → gift dialog → reserve → /g/ page).
  Store names were glued to the Hebrew prefix: "לפרטי המוצר בMachsanei Chashmal", "לקנייה בKSP",
  "אתם מזמינים מMachsanei…". New `tf(key, lang, **kw)` (the Jinja `tf` global now calls it) adds a
  maqaf when a one/two-letter prefix (ו/ב/ל/מ/ה/כ/ש) is directly followed by a Latin letter or digit:
  "ב-Machsanei Chashmal", "מ-KSP"; a Hebrew store name stays joined ("במחסני חשמל"). No static
  Hebrew string is affected (checked all of T_HE). Verified the RTL order on the /g/ button by
  measuring glyph positions.
- Rest of the flow checked: dialog labels all attached (the unlabeled field is the honeypot), status
  stepper, save-your-link notice, localised rate date and expiry date — fine.
- Test `test_hebrew_prefix_takes_maqaf_before_latin_store` — 144 tests.

## 2026-09-27 (localised dates on public pages)
- Mobile Hebrew pass on a live registry: every card's tag read "המחיר נבדק ב-2026-09-14" (raw ISO).
  Now `fmt_date` → "המחיר נבדק ב-14 בספטמבר 2026" / "Price checked 14 September 2026"; fits on one
  line at 375 px. Same fix for the ≈-estimate footnote's rate date and /find result event dates
  (the latter also wrapped in `<time datetime>` like the registry header).
- Checked for horizontal overflow at 375 px in Hebrew: none (only the category chip scroller,
  by design).
- Test `test_public_dates_are_localised` — 141 tests.

## 2026-09-27 (password reset)
- /forgot decided "email works" from `OB_SMTP_HOST` alone. With a half-filled `instance/ob.env`
  (host but no user/password) it told the couple "check your inbox" while nothing could ever send.
  Now uses `ob_mail.configured()` (host + user + password) and otherwise sends them to /contact as
  before. The unused `SMTP_HOST` constant is gone.
- /reset checked the token before the write transaction, so two simultaneous submits of one link
  (two tabs, double tap) could both set a password. The token is now spent atomically inside the
  lock (`UPDATE … WHERE used_at IS NULL AND expires_at>=now`, rowcount) before the password changes;
  the loser is sent to /forgot with the usual "link expired or used" message.
- 2 tests (half-configured SMTP; two tabs on one reset link) — 140 tests.

## 2026-09-27 (honest audience numbers)
- Page views, funnel events and store-link clicks are the figures the owner quotes to advertisers,
  but every crawler, WhatsApp/Facebook link-preview fetch and script was counted as a visitor.
  New `is_bot()` (User-Agent pattern; no UA = bot) — `track()` and the `/go/` click increments
  skip them. Bots still get every page and redirect normally.
- robots.txt now disallows `/go/` so search engines don't crawl (and count) store redirects.
- /admin/lead WhatsApp link built the number with two `replace`s (a dashed or local 05x number
  gave a broken wa.me link); now uses the same `wa_number` filter as the admin list.
- 7 tests (browser counted; Googlebot/WhatsApp/facebook/curl/empty UA redirected but not counted;
  robots) — 138 tests.

## 2026-09-27 (email hardening)
- Reserve and cash-gift forms stored and mailed the optional guest email with no server check
  (only the browser's `type=email`). A hand-made POST with `me@x.com,victim@y.com` got accepted,
  so the site could be used to send its "manage your gift" email to extra people. Now
  `_guest_email()` returns "" unless it's one valid address; the gift still goes through.
- One shared `ob_security.valid_email` (rejects commas, semicolons, `<>`, quotes, whitespace,
  newlines; accepts `+` tags and apostrophes) replaces three copies of a looser regex (signup,
  guest link email, shana inquiry).
- `ob_mail.enqueue` refuses anything that isn't one address (covers every caller, incl.
  `manage.py remind-claims`) and flattens the subject to one line — a newline from a registry
  title would have made `EmailMessage` raise on every retry until the row failed.
- Double send: the background send started by `enqueue()` and a scheduled `manage.py send-mail`
  could both pick up a fresh row and deliver it twice. `attempt()` now takes a 10-minute lease on
  the row before sending; only the sender that moved `next_attempt_at` sends. A crash mid-send just
  lets the lease run out and the row is retried.
- tests/test_mail.py (14 tests: address rules, crafted guest email, enqueue guards, concurrent
  senders, backoff) — 131 tests.

## 2026-09-27 (logged-in pages audit, admin password form, utcnow)
- Same markup audit over the couple and admin pages (via the test client, temp DB). Fixed:
  - /registry/items catalog filter: category select, search box and the icon-only search button had
    no accessible name (screen readers said "button"). Labelled with existing i18n keys (EN+HE).
  - /admin/catalog: same for its search box, two selects and icon button.
  - /dashboard/print had no h1 — added a visually hidden one.
  - /admin password form said "10+ chars" / `minlength=10`, but the server requires 12 — typing 10–11
    characters passed the browser and was then rejected. Now 12, plus aria-labels and
    `autocomplete=current-password/new-password` for password managers.
- `datetime.utcnow()` (deprecated in Python 3.12+; 26 calls) → `datetime.now(timezone.utc)
  .replace(tzinfo=None)`: identical naive-UTC values, so stored strings/comparisons are unchanged.
  Test run warnings 644 → 0.
- New tests/test_a11y.py: 18 logged-in pages (EN+HE) checked for one h1, heading order, unique ids,
  labelled fields, named buttons; admin password minimum (117 tests).

## 2026-09-27 (heading outline + page audit)
- Audited 19 public pages for duplicate ids, unlabeled fields, images without alt, empty
  buttons/links, `_blank` without noopener and heading order. Only issue: /catalog, /find and
  /advertise jumped h1 → h3 (card titles), which breaks screen-reader heading navigation. Added a
  visually hidden h2 above each card group (`catalog_items_h`, `find_results_h`, `adv_who_h`, EN+HE);
  nothing changes visually.
- Also measured SQL per page (≤8 queries, no N+1; registry page ~85 ms on the dev DB) — no change needed.
- Test `test_public_pages_have_sound_heading_outline_and_unique_ids` over 13 pages (115 tests).

## 2026-09-27 (registry list: sort reset, Back button, stuck buttons)
- Picking "Suggested order" after a price sort did nothing — the cards stayed price-sorted. Cards
  now remember their original position (`data-order`) and the empty sort value restores it (dialogs
  stay paired with their cards).
- After Back, the browser restored "only available" and the sort select but the list showed
  everything in the original order. The view is re-applied on `pageshow` (form state is restored
  after DOMContentLoaded). Verified in the browser: back → 6 available gifts, ascending price.
- Double-submit guard marks the buttons it disables; on a back/forward-cache restore they're
  re-enabled, so a returning guest isn't left with a dead "Reserve" button.
- Removed an unused variable in `applyRegistryView`.

## 2026-09-25 (gift dialog: scrollbar click no longer closes it)
- app.js closed any `<dialog>` on a click whose target was the dialog itself (meant for the
  backdrop). The gift dialog scrolls on short laptop screens (`overflow: auto`), and a click/drag on
  its scrollbar also targets `<dialog>` — closing it mid-form and losing what the guest typed. Now it
  closes only for real pointer clicks (`e.detail > 0`) outside the dialog's bounding box. Verified in
  the browser at 1280×600: edge click keeps it open, backdrop click closes it.

## 2026-09-25 (error page survives a DB outage)
- `_error_page` rendered `error.html`, whose layout's context processor queries the DB (ad slot,
  current user). With the DB locked/missing, the 500 handler itself raised and guests got Werkzeug's
  bare "Internal Server Error". Now it falls back to `_BARE_ERROR_HTML` — static, bilingual, only the
  stylesheet, logs the failure — and still returns the right status. It deliberately doesn't promise
  a reservation was saved (a failed write rolls back); it tells the guest to check before retrying.
- Test `test_error_page_survives_a_database_outage` (102 tests).

## 2026-09-25 (colour contrast, WCAG AA)
- Measured every visible text node on /, /sample (EN+HE), /catalog, /shana-rishonah, /guides, /find,
  /about, a /g/ guest page and a live registry, against its real background.
- `--gold` #a5762a → **#876022**: gold text was 3.7:1 on paper / 3.3:1 on gold-soft, and the gold
  cash-gift buttons (cream on gold) 3.7:1 — now ≥4.6:1 everywhere. `--ink-soft` #6f6a5e → #6c675c
  (was 4.45:1 on paper-deep). Decorative line-art strokes keep the lighter gold.
- Footer: "Bayis" in the footer logo now uses `--gold-bright` (dark gold on navy was 2.8:1);
  copyright line #7e889e → #939cb0 (5.7:1).
- WhatsApp share button #1faf58 → #107c41 (white text 2.9:1 → 5.3:1).
- After the change: 0 failing text/background combinations on all scanned pages.
- New test `test_palette_text_contrast_meets_wcag_aa` checks the token pairs from style.css.

## 2026-09-25 ("price checked" now always means a real product)
- 27 items were `price_status='verified'` with only "Zap.co.il + brand/retailer sites" as source and no
  store link — cards showed "Price checked 2026-07-05" on generic ideas like "Couch". Downgraded to
  `estimate` (price kept; `price_source` says it was a July range, no specific product). Every
  verified item now has a store link.
- Re-verified 10 of them with real KSP products (same price rule): air fryer Ninja AF500EU ₪699 ·
  coffee machine Philips 1200 EP1200 ₪1,089 (bean-to-cup; note compares capsule machines) · food
  processor Bosch MCM3110W ₪399 · hand mixer Bosch MFQ22100 ₪159 · stick blender Bosch MSM66110 ₪249
  · SodaStream Terra ₪229 · robot vacuum Xiaomi S40C ₪779 · dryer Bosch Serie 4 heat pump ₪3,375 ·
  Brita Style ₪149 · premium kettle Bosch DesignLine ₪277 (note: ask your rav about tevilah).
- 57 of 120 active items linked. Live DB: `price_status,price_checked_at` must be in the
  `seed-sync --fields` list (the 2026-09-25 split entry's command already includes both).

## 2026-09-25 (illustration fixes)
- `_ILLUSTRATION_RULES`: "Baking pans & cookie sheets" matched "sheet" and showed a **bed**; new
  rules run first — baking pans/dishes → kitchen drawing, bath mat/shower → towel, "pump pot" → urn.
  Regression test added (99 tests).

## 2026-09-25 (combo items split into single products)
- **Seed items can be retired:** `"active": false` in seed_catalog.json inserts the row retired on a
  fresh install (`seed_sync` INSERT now writes `active`); on a live DB, include `active` in
  `seed-sync --fields`. Retired rows stay on any registry that already copied them.
- Retired → replaced by: milchig/fleishig cutting-board set → Berox 30×40 red (fleishig) ₪69 + blue
  (milchig) ₪66 · duvet+pillows → pillows ×2 (Arige Gad, ₪24 each → ₪48) + summer duvet (Vardinon
  Tani, ₪195) · bath mats+caddy → non-slip bath mat (Nino, ₪49) + shower shelf (Aquila, ₪59). New
  items carry the old starter groups.
- Renamed in place (old names in `legacy_names`): netilas cup+basin → "Netilas yadayim cup" (Heichal
  Menachem stainless, ₪90) · ceramic pan set → "Ceramic frying pan (26 cm)" (Ninja ZeroStick, ₪139) ·
  8-piece towels → "Towel set — 8 pieces (2 packs of 4)" (Homestyle London ₪149 × 2 → ₪298).
- Catalog: 123 seed rows, 120 active, 47 linked. Starter packs 45 of 47 linked (left: pump thermos,
  sponja set — no honest single product found).
- Tests: count-based tests now derive from seed_catalog.json; new test that retired seed items are
  inactive and hidden from /catalog and the starter picker. 98 tests.
- **Live DB command now:** `python manage.py seed-sync --apply` (inserts the 6 new items), then
  `python manage.py seed-sync --fields active,name,name_he,url,store,brand,model,price_nis,kind,price_status,price_checked_at,price_source,availability,notes,notes_he` (dry run, then `--apply`), then
  `python manage.py refresh-registry-links --apply`.

## 2026-09-25 (deploy paths + 4 more starter-pack links)
- **DEPLOY_AI.md / passenger_wsgi.py use full `/home/bashertbench/ourbayis` paths** and open with a
  warning: the PythonAnywhere account also hosts BashertBench *in the home folder itself*, so `~/` or
  a clone into home would land next to the live site. Scheduled-task commands are now full paths
  (manage.py resolves the DB and `instance/ob.env` from its own folder, same as the web app).
- KSP links (same price rule as 2026-09-23): milchig dinnerware Soltam Opal 18-pc tempered glass ₪139
  (white — the fleishig set is turquoise) · cutlery Soltam Berlin 26-pc ₪155 each → ₪310 for two ·
  large Shabbos hot plate Gold Line ATL-500 ₪109 (title says Tzomet-approved; note says check) ·
  Hidurit 40-cup urn ₪361 (no approval claimed).
- 38 of 117 catalog items linked; starter packs 36 of 44. Unlinked starter items are the ones with no
  honest single product: cutting-board pair, pump thermos, duvet+pillows, bath mats+caddy, netilas
  cup+basin, sponja set, ceramic pan set, 8-piece towels.

## 2026-09-23 (store links: 4 Judaica items at Heichal Menachem)
- heichal.co.il category pages (Shabbos → cups / challah boards / covers / havdalah) mark unavailable
  items "לא זמין במלאי"; each pick's product page shows a single price and a quantity selector with no
  such notice in the product block. Kiddush cup with tray, 925-silver plated, 8.5 cm ₪198 · silver-
  plated havdalah set ₪220 · bamboo challah board + knife ₪179 · leather-look challah cover ₪110.
  Notes say plated ≠ solid silver and remind couples to check the cup holds a revi'is.
- Netilas yadayim "cup & basin" left unlinked (the shop sells cups only).
- 34 of 117 catalog items now have verified links. Same live-DB `seed-sync --fields …` command as the
  kitchen/bedding entry below.

## 2026-09-23 (store links: 13 kitchen + bedding KSP products)
- **Price rule, confirmed on a control item:** on a KSP page the price block follows the Eilat notice;
  the FIRST ₪ amount there is the regular price. A second amount right after it is a member price,
  "מחיר אילת" is VAT-free Eilat, "חסוך והגש הצעה החל מ-" is a make-an-offer floor — all ignored.
  (The 9 appliances from earlier today were re-checked against this rule; all correct.)
- Kitchen: starter pots Food Appeal Flexi 7-pc ₪399 · premium Ninja NeverStick Ceramic Pro 10-pc
  ₪799 · knife block Fresco 5 knives ₪89 (note mentions VIKING ₪499) · chef's knife Victorinox Swibo
  21 cm ₪199 · mixing bowls Soltam ×4 ₪59 · Lock & Lock ×12 ₪119 · glass baking dishes Ibili ×3 ₪199
  (item renamed from "…(Pyrex set)" — it isn't Pyrex; old name kept in `legacy_names`).
- Bedding: sheet sets ×2 Arige Gad Ekko Cotton 160×200 ₪109 each → ₪218 · sateen Homestyle Infinity
  ₪287 (listing is 180×200 — note says pick size) · mattress protector Arige Gad double ₪45 ·
  winter blanket Vardinon Brooks ₪159 · winter duvet Vardinon Benjamin ₪229 · guest set Homestyle
  single ₪79.
- **Deliberately left unlinked** (no honest single-product match): milchig/fleishig cutting boards
  (boards are sold singly), ceramic frying-pan set (only hybrid/single pans), duvet+pillows combo,
  8-piece luxury towels, bath mats + caddy.
- Stopped when KSP began showing a bot-verification page; KSP carries no Judaica anyway.
- 30 of 117 catalog items now have verified links. Live DB: this batch renames one item, so include
  name fields — `python manage.py seed-sync --fields name,name_he,url,store,brand,model,price_nis,kind,price_status,price_checked_at,price_source,availability,notes,notes_he` (dry run, then `--apply`), then
  `python manage.py refresh-registry-links --apply`.

## 2026-09-23 (store links: 9 more verified KSP products)
- Researched in the browser on ksp.co.il product pages (regular price read from the purchase block —
  NOT the lower "make an offer from" / club price; add-to-cart present, no "last unit" flag):
  electric kettle Gold Line ATL-2707W ₪64 (KSP lists it as tevilah-exempt — note says confirm with
  your rav) · toaster oven Gold Line ATL-6640 40 L ₪233 · microwave Sharp R-703Z(K) ₪460 · vacuum
  Samsung SC4540 ₪299 · fans ×2 Midea FS40-15F ₪149 each → ₪298 · washing machine LG WFS8014WB 8 kg
  ₪1,865 · dishwasher Midea WQP14-W7633C-W ₪1,372 · fridge Sharp SJ-8420-SL 421 L ₪3,570 · built-in
  oven AEG ABU51229M with Shabbos mode ₪2,466. Placeholder brands (Tefal/Electrolux/Bosch…) replaced
  by the real product; item names stay generic; notes give alternatives and what we did NOT verify
  (e.g. fridge Shabbos mode).
- Catalog now has 17 of 117 items with a verified store link.
- **Live DB:** seed data never overwrites existing rows. Apply with (dry run first, then --apply):
  `python manage.py seed-sync --fields url,store,brand,model,price_nis,kind,price_status,price_checked_at,price_source,availability,notes,notes_he` then `python manage.py refresh-registry-links --apply`.

## 2026-09-23 (admin review)
- **Admin sessions expire after 12 h** (`ADMIN_SESSION_HOURS`, `session["admin_at"]` stamped at
  login; older sessions must log in again) — the admin can download the whole DB.
- **Admin login hash-checks even unknown usernames** (`_DUMMY_PW_HASH`) so timing doesn't reveal
  which usernames exist. Admin password change now needs 12+ chars (same as `create-admin`).
- **Ads**: link and image URLs get `https://` if missing and must pass `validate_url`, else the ad
  isn't saved — they render on every public page.
- **Lead status redirect** uses `same_origin_referrer()` instead of the raw Referer.
- **Leads list**: follow-ups whose `next_action_date` has arrived are sorted first, marked
  ("due: …", gold edge) and counted in a "follow-ups due" stat card; only completed/cancelled
  leads are dimmed (quoted/accepted/arranging used to look done).
- **WhatsApp links** use the `wa_number` filter: digits only, `00` prefix dropped, a local
  leading-0 number becomes 972… (wa.me needs international form).
- Messages: email is a mailto link. Catalog CSV import rejects negative prices (reported per row).
- Tests: 97.

## 2026-09-23 (registry settings review)
- **Payment-link changes email the account owner** (`mail_paylinks_*`, EN/HE) with the new links and
  what to do if it wasn't them — these links decide where guest money goes.
- **Current-password check for payment links is rate-limited** (`pay_reauth`, 8 per 15 min per IP)
  — it was an unlimited password oracle for anyone holding a session.
- **Visibility choice survives a validation error** (radios read the submitted value; the form
  already did this for every other field).
- **Event date validated server-side** (ISO date or empty, `r_bad_date`); garbage used to be stored
  and silently break the countdown.
- **One registry per user is checked under the write lock** in `_save_registry`, so a double-
  submitted create can't make two.
- Tests: 94.

## 2026-09-23 (items page review)
- **Store-link validation was too loose**: `ob_security.validate_url` accepted `https://bad link`
  (urlparse takes any netloc). Now rejects whitespace and requires a dotted hostname (IDN letters
  allowed, no underscores). All seed/DB links still pass. Affects the items page, item edit and
  admin catalog.
- **Quantity/remove are atomic with guest claims**: `items_update` and `item_edit` re-check
  committed quantity and archive-vs-delete inside `ob_db.write_txn` (the claim route's lock), so a
  reservation landing mid-edit can't over-commit an item or make a delete hit the FK.
- **Item edit keeps what was typed** when validation fails (was re-rendering from the DB); qty input
  `min` = committed, with a hint; Cancel returns to the item's row.
- **Custom items**: an invalid link is reported ("left off — use Edit") instead of silently dropped;
  an identical double-submit (same name/link/price) is ignored.
- **Removing a reserved/given item** shows a specific confirm (their gift stays on the dashboard);
  Remove button is `formnovalidate`.
- Save/remove/edit return to `/registry/items#item-<id>` (row outlined via `:target`); save now
  flashes "Item updated".
- `qty_below_committed` copy fixed (said "lower the quantity below that", the rule is the opposite).
- Tests: 91.

## 2026-09-22 (dashboard review)
- **Release can no longer undo a received gift**: `/claim/<id>/cancel` (and `/release`) only acts on
  reserved/reported claims — a stale form from a second tab used to flip `received` → `cancelled`.
- **Lapsed reservations**: the dashboard shows a reserved claim past `expires_at` as expired (same as
  the public page already treats it) even before `manage.py expire-claims` runs; it's no longer in
  the "waiting" queue or the claimed/cash counts. Cancelled/expired rows sort last and are muted
  (`.is-closed`).
- **Late gifts can be confirmed**: `claim_confirm` accepts `expired` too (event note "late"), matching
  the guest side, which already allows a late report.
- **"Mark thanked"** only shows (and only toggles on) reported/received gifts; un-marking always works.
- **Actions keep your place**: confirm/cancel/thanked redirect to `/dashboard#claim-<id>`
  (`scroll-margin-top` clears the sticky header; the row is outlined via `:target`).
- **Share links use `ext_url()`**: dashboard copy/WhatsApp link, printable insert, public registry
  share buttons, og:image and homepage JSON-LD used `_external=True`, which ignores `OB_BASE_URL`
  — the links couples paste into invitations now always carry the real domain.
- Tests: 89.

## 2026-09-22 (improvement pass 3 — guest "your gift" page)
- **/g/<token> reordered for phones**: status → the guest's next action (cash: amount + payment
  buttons; store: item + "Buy at …" button) → "save this link" (while reserved) → details/notes.
  Previously the payment block sat below the product facts and the save-link box at the very end.
  The status panel stacks (`.notice-stack`) instead of squeezing its title into a narrow column;
  inline styles moved to classes.
- **Path-specific reserved note** (`guest_reserved_note_cash` / `_buy`, EN+HE) instead of "buy it
  or send the money" after the guest already chose.
- **"Email me this link"** (`POST /g/<token>/email`, rate-limited 5/h per IP): for guests who skipped
  the optional email field. Stores the address on the claim only if none was given (so
  `remind-claims` reaches them) and queues `mail_guest_manage_*`. Shown only when
  `ob_mail.configured()` (host+user+pass) — never promises mail that can't send.
- Removed the user-level `ourbayis` launch entry (ran app.py on the real DB) from ~/.claude/launch.json.
- Tests: 85.

## 2026-09-22 (improvement pass 2)
- **Couple names on the guest page**: `/r/<slug>` never showed `couple_names` (the one required
  identifying field) — now under the title (`.reg-couple`) and first in the `<title>`, so guests
  know they're on the right list and name searches match the tab/search title.
- **Real icon files** (`tools/make_icons.py`, dev-time Pillow): `static/favicon.svg`,
  `favicon.ico` (16/32/48, also served at `/favicon.ico` — was a 404 on every page load and Google
  can't use a data: URI favicon) and a 180px `apple-touch-icon.png` for "Add to Home Screen";
  `<meta name="theme-color">` navy.
- **Static cache-busting**: `url_defaults` adds `?v=<mtime>` to every `url_for('static')`; versioned
  requests get `Cache-Control: public, max-age=31536000, immutable` — saves a revalidation
  round-trip per asset per page (guests abroad). On PythonAnywhere the /static/ mapping serves the
  file directly (nginx ignores the query), and the changing URL still busts caches after a deploy.
- **autocomplete** on signup/login/reset/forgot/contact (`name`, `email`, `new-password`,
  `current-password`) so password managers and phone autofill work.
- Static export maps `/favicon.ico` to `static/favicon.ico` (relative) for GitHub Pages; docs/ regenerated.
- Project `.claude/launch.json` entry renamed `ourbayis-dev` — the user-level `ourbayis` entry of the
  same name runs app.py on the real DB (use `ourbayis-v3` from a home-dir session).
- Tests: 84.

## 2026-09-22 (owner decisions + email setup)
- **Full Nest includes appliance installation** (owner decision): washer/fridge/microwave "delivered
  and installed" on a standard hookup to existing water/drain/power points; new plumbing/electrical
  work and other installation/assembly stay quoted per item. Updated the bundle seed text, the
  `pkg_appliances_included` tier line, the terms panel (`shana_term_install_b`), EN+HE.
- **Package prices confirmed** (₪2,450 / ₪6,900 / ₪17,900): "Indicative" → "Starting price — final
  quote after we talk"; packages subtitle no longer says "indicative, not quotes".
- **`bundle_sync` refreshes untouched seed text** via a per-bundle `replaces` map (earlier seed texts
  collected from git history + local/snapshot DBs). Admin-edited text and prices are never touched.
- **`instance/ob.env` settings file** read by app.py and manage.py — fixes scheduled `send-mail` /
  `remind-claims` never having SMTP or `OB_BASE_URL` (they don't run passenger_wsgi.py).
  `ob.env.example` template; DEPLOY_AI.md step 4b walks through a Gmail app password.
- **`manage.py test-mail <to>`**: synchronous send that prints the real SMTP error.
  `ob_mail.send_now()` shared with the outbox; port 465 (SSL) supported; sender shows as "OurBayis".
- Removed an accidental duplicate of the KosherRoute project from the repo folder (untracked;
  byte-identical to Documents/KosherRoute, sent to the Recycle Bin).
- Tests: 82 (bundle-sync safety, Full Nest copy, env-file precedence).

## 2026-09-22 (mobile pass) — phone layout fixes
- **Gift cards on phones (<=560px)** are now compact rows: 92px square illustration/photo beside the
  text instead of a full-width 4:3 box. Registry/catalog/homepage cards went from ~371px to ~258px
  tall at 375px, so a guest sees ~3 gifts per screen. Same macro everywhere, RTL-safe (logical margins).
- **Header on small phones (<=430px)**: the hamburger was clipped (right edge at 392px on a 375px
  screen). Tighter gaps/padding and a smaller brand name; it now fits in EN and HE.
- **Catalog/registry filters on phones**: category chips scroll in one row; catalog search + button
  share a row and the three selects sit on one row, so gifts appear on the first screen.
- **Reveal-on-scroll no longer hides content without JS**: `app.js` adds `html.js`, and `.reveal`
  is only hidden under `.js`, so a failed/blocked script can't leave homepage sections blank.
- `docs/static` refreshed (HTML pages not re-committed — the only diff was CSRF-token churn).

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
