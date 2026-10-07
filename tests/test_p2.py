# -*- coding: utf-8 -*-
"""Review pass 2026-09-15 — shared gift status labels, stock warnings across
surfaces, protected historical amounts, one canonical sample, package
definitions, translated labels, catalog filters, and the unaffected real flows.
Every test runs against the temp DB from conftest (never ourbayis.db)."""
import os
import re
import sqlite3

import pytest

from conftest import get_csrf, get_form_key, signup, create_registry, add_item

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _couple_with_catalog_items(client, app_module, keys, pay=False):
    """Signed-up couple with a public registry holding the given seed items."""
    signup(client)
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    data = dict(csrf_token=tok, title="Our Home", couple_names="Sarah & Dovid",
                event_type="wedding", visibility="public")
    if pay:
        data["paypal_url"] = "https://paypal.me/sarahdovid"
    client.post("/registry/new", data=data, follow_redirects=True)
    db = _db()
    for key in keys:
        cid = db.execute("SELECT id FROM catalog_items WHERE seed_key=?", (key,)).fetchone()[0]
        r = client.get("/registry/items")
        tok = get_csrf(r.get_data(as_text=True))
        client.post("/registry/items/add", data=dict(csrf_token=tok, catalog_id=str(cid)))
    reg = db.execute("SELECT * FROM registries").fetchone()
    items = {r["catalog_id"]: r for r in db.execute("SELECT * FROM registry_items")}
    db.close()
    return reg, items


def _claim(app_module, slug, item_id, name="Guest", **extra):
    guest = app_module.app.test_client()
    html = guest.get(f"/r/{slug}").get_data(as_text=True)
    data = dict(csrf_token=get_csrf(html), form_key=get_form_key(html), guest_name=name, give="buy")
    data.update(extra)
    r = guest.post(f"/r/{slug}/claim/{item_id}", data=data)
    assert r.status_code == 302 and "/g/" in r.headers["Location"]
    return r.headers["Location"].rsplit("/", 1)[-1]


# ------------------------------------------------------------------ status labels
def test_gift_status_states(app_module):
    gs = app_module.gift_status
    item = {"id": 1, "qty_wanted": 2}
    assert gs(item, {})["state"] == "open"
    assert gs(item, {1: dict(reserved=1, reported=0, received=0, committed=1)})["state"] == "partial"
    assert gs(item, {1: dict(reserved=2, reported=0, received=0, committed=2)})["state"] == "reserved"
    assert gs(item, {1: dict(reserved=1, reported=1, received=0, committed=2)})["state"] == "reported"
    assert gs(item, {1: dict(reserved=0, reported=0, received=2, committed=2)})["state"] == "received"
    st = gs(item, {1: dict(reserved=0, reported=1, received=1, committed=2)})
    assert st["state"] == "reported" and st["left"] == 0  # not "received" until every unit is confirmed
    # committed beyond qty never yields a negative "left"
    assert gs({"id": 1, "qty_wanted": 1}, {1: dict(reserved=3, reported=0, received=0, committed=3)})["left"] == 0


def test_public_registry_distinguishes_reserved_reported_received(client, app_module):
    """A fully reserved item is unavailable but must not be labelled received."""
    reg, items = _couple_with_catalog_items(
        client, app_module, ["shabbos-hot-plate-platta", "stand-mixer", "towel-set"])
    ids = list(items)
    _claim(app_module, reg["slug"], items[ids[0]]["id"])
    t1 = _claim(app_module, reg["slug"], items[ids[1]]["id"])
    t2 = _claim(app_module, reg["slug"], items[ids[2]]["id"])
    g = app_module.app.test_client()
    html = g.get(f"/g/{t1}").get_data(as_text=True)
    g.post(f"/g/{t1}/report", data=dict(csrf_token=get_csrf(html)))
    with app_module.app.app_context():
        db = app_module.get_db()
        cid = db.execute("SELECT id FROM claims WHERE item_id=?", (items[ids[2]]["id"],)).fetchone()[0]
    html = client.get("/dashboard").get_data(as_text=True)
    client.post(f"/claim/{cid}/confirm", data=dict(csrf_token=get_csrf(html)))

    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert "Reserved by a guest" in page
    assert "On its way" in page
    assert "Received — confirmed by the couple" in page
    assert page.count("Gift this") == 0  # nothing left to reserve
    assert "3 of 3 gifts reserved, on the way or received" in page
    # the old blanket label is gone from the public page
    assert ">Gifted<" not in page


def test_partial_quantity_breakdown(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["towel-set"])
    item = list(items.values())[0]
    with app_module.app.app_context():
        app_module.get_db().execute("UPDATE registry_items SET qty_wanted=3 WHERE id=?", (item["id"],))
    _claim(app_module, reg["slug"], item["id"], qty="1")
    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert "2 of 3 still available" in page and "1 reserved" in page
    assert "Reserve and buy from the store" in page  # still reservable (store-only route)
    # the dialog only offers the remaining units
    assert re.search(r'<select name="qty"><option>1</option><option>2</option></select>', page)
    he = client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    assert "2 מתוך 3 עדיין פנויים" in he


# ------------------------------------------------------------------ stock warning across surfaces
def test_stock_warning_follows_item_to_every_surface(client, app_module):
    """The catalog flags the Crock-Pot as out of stock at last check; the
    homepage strip, the registry card, the claim dialog and the sample must say
    the same thing instead of silently dropping it."""
    tag = "Out of stock at last check"
    assert tag in client.get("/catalog?cat=appliances").get_data(as_text=True)
    home = client.get("/").get_data(as_text=True)
    assert tag in home
    reg, items = _couple_with_catalog_items(client, app_module, ["slow-cooker-for-cholent"])
    item = list(items.values())[0]
    assert item["availability"] == "unavailable" and item["model"].startswith("Crock-Pot")
    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert page.count(tag) >= 2  # card + dialog
    assert "View product details at Hakol LaBait" in page  # pre-reservation link reads as viewing
    assert 'aria-label="Close"' not in client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    assert 'aria-label="סגירה"' in client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    items_page = client.get("/registry/items?lang=en").get_data(as_text=True)
    assert tag in items_page


def test_featured_strip_prefers_available_items(client, app_module):
    with app_module.app.app_context():
        rows = app_module.featured_items(app_module.get_db(), limit=8)
    avail = [r["availability"] for r in rows]
    assert "unavailable" in avail and avail.index("unavailable") == len(avail) - 1


# ------------------------------------------------------------------ protected historical amounts
def test_refresh_links_updates_availability_but_never_claim_amounts(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"], pay=True)
    item = list(items.values())[0]
    _claim(app_module, reg["slug"], item["id"], give="cash")
    with app_module.app.app_context():
        db = app_module.get_db()
        before = db.execute("SELECT amount_minor, price_snapshot_minor FROM claims").fetchone()
        assert before["amount_minor"] == 2290 * 100
        # the store changes: price up, item now unavailable, couple overrode the url
        db.execute("UPDATE catalog_items SET price_nis=2590, availability='unavailable',"
                   " url='https://example.com/new' WHERE id=?", (item["catalog_id"],))
        db.execute("UPDATE registry_items SET overrides='url', url='https://example.com/mine'"
                   " WHERE id=?", (item["id"],))
        diffs = app_module.ob_db.refresh_registry_links(db)
        after_item = db.execute("SELECT * FROM registry_items WHERE id=?", (item["id"],)).fetchone()
        after_claim = db.execute("SELECT amount_minor, price_snapshot_minor FROM claims").fetchone()
    fields = {d[1] for d in diffs}
    assert "availability" in fields and "url" not in fields  # override respected
    assert after_item["availability"] == "unavailable"
    assert after_item["url"] == "https://example.com/mine"
    assert after_item["price_nis"] == 2290  # registry price is the couple's snapshot
    assert tuple(after_claim) == tuple(before)  # the guest's committed amount is untouched


def test_migration_18_backfills_snapshot_registry_items(tmp_path, monkeypatch):
    import shutil
    import sys
    snap = os.path.join(BASE, "backups", "ourbayis-snapshot-2026-09-14.db")
    if not os.path.exists(snap):
        pytest.skip("snapshot DB not available")
    db_path = tmp_path / "legacy.db"
    shutil.copy(snap, db_path)
    monkeypatch.setenv("OB_DB_PATH", str(db_path))
    monkeypatch.setenv("OB_SECRET_KEY", "test-secret-key")
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("ob_"):
            del sys.modules[mod]
    import app  # noqa: F401
    db = sqlite3.connect(db_path)
    cols = {r[1] for r in db.execute("PRAGMA table_info(registry_items)")}
    assert {"model", "availability", "notes", "notes_he"} <= cols
    assert 18 in {r[0] for r in db.execute("SELECT version FROM schema_migrations")}
    n = db.execute("SELECT COUNT(*) FROM registry_items WHERE catalog_id IS NOT NULL"
                   " AND availability IS NULL").fetchone()[0]
    assert n == 0


# ------------------------------------------------------------------ one canonical sample
def test_sample_registry_is_consistent_and_inert(client, app_module):
    home = client.get("/").get_data(as_text=True)
    sample = client.get("/sample").get_data(as_text=True)
    assert "Sample registry" in home and "Sample registry" in sample
    assert 'href="/sample"' in home
    with app_module.app.test_request_context("/sample"):
        db = app_module.get_db()
        reg, items, breakdown = app_module.sample_registry(db)
        featured = {r["id"] for r in app_module.featured_items(db, limit=8)}
    assert {i["catalog_id"] for i in items} <= featured  # same source as the featured strip
    assert all(not reg[k] for k in ("paypal_url", "stripe_url", "bit_url"))
    for it in items[:4]:
        assert it["name"] in home and it["name"] in sample
    assert "<dialog" not in sample and "<form" not in sample.split("<footer")[0].split("</header>")[1]
    assert "sample-btn-disabled" in sample
    # every state is on show, no real people, and nothing can be posted against it
    assert "Received — confirmed by the couple" in sample and "1 of 2 still available" in sample
    assert client.post("/r/sample/claim/-1", data={}).status_code in (400, 404)
    he = client.get("/sample?lang=he").get_data(as_text=True)
    assert "רשימה לדוגמה" in he


# ------------------------------------------------------------------ package definitions
def test_package_tiers_cover_every_bundle_and_copy_is_consistent(client, app_module):
    with app_module.app.app_context():
        tiers = {r["tier"] for r in app_module.get_db().execute("SELECT tier FROM bundles WHERE active=1")}
    assert tiers <= set(app_module.PACKAGE_TIERS)
    page = client.get("/shana-rishonah").get_data(as_text=True)
    for bad in ("Most popular", "most popular", "No response-time guarantee", "within one business day",
                "coordinated and installed"):
        assert bad not in page
    assert page.count("How every package works") == 1
    assert "Ask at least 6 weeks before arrival" in page and "Ask at least 3 weeks before arrival" in page
    assert "confirm your package and price in writing before any payment" in page
    assert "Not sure yet" in page
    he = client.get("/shana-rishonah?lang=he").get_data(as_text=True)
    assert "איך כל חבילה עובדת" in he


def test_shana_inquiry_form_still_works(client, app_module):
    r = client.get("/shana-rishonah")
    tok = get_csrf(r.get_data(as_text=True))
    r = client.post("/shana-rishonah", data=dict(csrf_token=tok, name="Test", whatsapp="+972501234567",
                                                 bundle="custom", city="Yerushalayim"),
                    follow_redirects=True)
    assert "send a quote" in r.get_data(as_text=True)
    with app_module.app.app_context():
        row = app_module.get_db().execute("SELECT bundle_slug FROM shana_requests").fetchone()
    assert row["bundle_slug"] == "custom"


# ------------------------------------------------------------------ translations
def test_every_template_key_exists_in_both_languages():
    import glob
    import i18n
    used = set()
    for f in glob.glob(os.path.join(BASE, "templates", "*.html")):
        s = open(f, encoding="utf-8").read()
        used |= set(re.findall(r"\bt\('([a-z0-9_]+)'\)", s))
        used |= set(re.findall(r"\btf\('([a-z0-9_]+)'", s))
    missing_en = sorted(k for k in used if k not in i18n.T_EN)
    missing_he = sorted(k for k in i18n.T_EN if k not in i18n.T_HE)
    assert not missing_en, missing_en
    assert not missing_he, missing_he
    for k, v in i18n.T_EN.items():
        assert "Shabbat" not in v, k
        assert "[owner" not in v and "legal review]" not in v, k


@pytest.mark.parametrize("path", ["/", "/sample", "/catalog", "/shana-rishonah", "/privacy", "/about"])
def test_public_copy_has_no_internal_notes_or_unsupported_claims(client, path):
    for lang in ("en", "he"):
        html = client.get(f"{path}?lang={lang}").get_data(as_text=True)
        assert "[owner" not in html and "legal review" not in html
        assert "Every appliance on OurBayis works" not in html
        assert "No customs" not in html
        assert "click a gift, and they're done" not in html
        assert "Shabbat" not in html


# ------------------------------------------------------------------ catalog browsing
def test_catalog_filters_sort_and_pagination(client, app_module):
    import json
    seed = json.loads(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8").read())["items"]
    n_active = sum(1 for it in seed if it.get("active") is not False)
    html = client.get("/catalog").get_data(as_text=True)
    assert f"{n_active} gifts" in html and "Page 1 of " in html and 'rel="next"' in html
    html = client.get("/catalog?price=1500plus&kind=product&sort=price_desc").get_data(as_text=True)
    prices = [int(p.replace(",", "")) for p in re.findall(r"<strong>₪([\d,]+)</strong>", html)]
    assert prices and prices == sorted(prices, reverse=True) and min(prices) >= 1500
    assert "Reset filters" in html
    assert client.get("/catalog?page=99").status_code == 200  # clamps, never 500
    assert client.get("/catalog?page=abc&sort=evil&price=x").status_code == 200
    assert "Nothing matches" in client.get("/catalog?q=zzzzzz").get_data(as_text=True)
    he = client.get("/catalog?lang=he").get_data(as_text=True)
    assert f"{n_active} מתנות" in he


def test_catalog_add_keeps_filter_state_and_pending_add_flow(client, app_module):
    """Logged out: 'Sign up to add' posts through pending_add (not a dead link).
    Logged in: adding from a filtered page returns to the same filtered page."""
    with app_module.app.app_context():
        cid = app_module.get_db().execute(
            "SELECT id FROM catalog_items WHERE seed_key='towel-set'").fetchone()[0]
    html = client.get("/catalog?cat=bedding").get_data(as_text=True)
    assert f'<input type="hidden" name="catalog_id" value="{cid}">' in html
    r = client.post(f"/registry/items/add?back=catalog&cat=bedding&sort=price_asc&page=1",
                    data=dict(csrf_token=get_csrf(html), catalog_id=str(cid)))
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")
    signup(client, email="p@example.com")
    create_registry(client)
    with app_module.app.app_context():
        assert app_module.get_db().execute(
            "SELECT COUNT(*) FROM registry_items WHERE catalog_id=?", (cid,)).fetchone()[0] == 1
    html = client.get("/catalog?cat=kitchen&sort=price_asc").get_data(as_text=True)
    m = re.search(r'name="catalog_id" value="(\d+)"', html)
    r = client.post("/registry/items/add?back=catalog&cat=kitchen&sort=price_asc",
                    data=dict(csrf_token=get_csrf(html), catalog_id=m.group(1)))
    loc = r.headers["Location"]
    assert "cat=kitchen" in loc and "sort=price_asc" in loc and f"#c-{m.group(1)}" in loc


# ------------------------------------------------------------------ real flows unaffected
def test_claim_dialog_routes_and_guest_flow_unchanged(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"], pay=True)
    item = list(items.values())[0]
    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert "buy it from the store" in page and "send the couple the money for it" in page
    token = _claim(app_module, reg["slug"], item["id"], give="cash")
    g = app_module.app.test_client()
    html = g.get(f"/g/{token}").get_data(as_text=True)
    assert "Amount to send" in html and "paypal.me" in html
    assert "Next step: buy it" not in html  # cash route: no store CTA
    r = g.post(f"/g/{token}/report", data=dict(csrf_token=get_csrf(html)), follow_redirects=True)
    assert "Guest reports" in r.get_data(as_text=True)


def test_dates_are_localised_but_stored_unchanged(client, app_module):
    signup(client)
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/registry/new", data=dict(csrf_token=tok, title="T", couple_names="C",
                                           event_type="wedding", event_date="2026-12-15",
                                           visibility="public"), follow_redirects=True)
    with app_module.app.app_context():
        reg = app_module.get_db().execute("SELECT * FROM registries").fetchone()
    assert reg["event_date"] == "2026-12-15"
    en = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    he = client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    assert '<time datetime="2026-12-15">15 December 2026</time>' in en
    assert "15 בדצמבר 2026" in he


# ------------------------------------------------------------------ exchange rates
def test_rates_file_is_hot_reloaded_and_env_wins(tmp_path, monkeypatch):
    import importlib
    import json as _json
    import sys
    monkeypatch.delenv("OB_RATES", raising=False)
    for mod in list(sys.modules):
        if mod == "ob_money":
            del sys.modules[mod]
    import ob_money
    monkeypatch.setattr(ob_money, "RATES_FILE", str(tmp_path / "rates.json"))
    monkeypatch.setattr(ob_money, "_rates_mtime", object())  # force a re-read from the new path
    ob_money.ensure_fresh()
    assert ob_money.RATES == {"USD": 3.7} and ob_money.RATES_DATE == ""
    (tmp_path / "rates.json").write_text(_json.dumps(
        {"rates": {"USD": 3.1, "GBP": 4.1}, "date": "2026-09-17", "source": "test"}), encoding="utf-8")
    ob_money.ensure_fresh()
    assert ob_money.RATES["GBP"] == 4.1 and ob_money.RATES_DATE == "2026-09-17"
    assert ob_money.CURRENCIES == ["ILS", "USD", "GBP"]
    assert ob_money.estimate(31000, "USD") == 10000
    # a corrupt file never wipes the previous good rates
    (tmp_path / "rates.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(ob_money, "_rates_mtime", object())  # mtime can tie within the same second
    ob_money.ensure_fresh()
    assert ob_money.RATES == {"USD": 3.7}  # falls back to the default, never crashes
    monkeypatch.setenv("OB_RATES", '{"USD": 9.9}')
    importlib.reload(ob_money)
    assert ob_money.RATES == {"USD": 9.9}


def test_currency_select_and_query_route(client, app_module):
    app_module.ob_money._apply({"USD": 3.7, "GBP": 4.7, "EUR": 4.0}, "2026-09-17", "test")
    html = client.get("/").get_data(as_text=True)
    assert '<form class="cur-form"' in html and '<option value="GBP"' in html
    r = client.get("/currency?code=gbp", headers={"Referer": "http://localhost/catalog"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalog")
    assert "≈ £" in client.get("/catalog").get_data(as_text=True)
    assert client.get("/currency?code=XXX").status_code == 302  # ignored, no 500


# ------------------------------------------------------------------ batch 3: reminders, views, advertise, browse controls
def test_remind_claims_is_bounded_and_idempotent(client, app_module, tmp_path):
    import subprocess
    import sys
    reg, items = _couple_with_catalog_items(client, app_module, ["towel-set", "stand-mixer"], pay=True)
    ids = list(items)
    _claim(app_module, reg["slug"], items[ids[0]]["id"], guest_email="g1@example.com")
    _claim(app_module, reg["slug"], items[ids[1]]["id"])  # no email → never reminded
    env = {**os.environ, "OB_DB_PATH": os.environ["OB_DB_PATH"], "OB_BASE_URL": "https://ourbayis.example",
           "PYTHONIOENCODING": "utf-8"}
    run = lambda *a: subprocess.run([sys.executable, os.path.join(BASE, "manage.py"), "remind-claims", *a],
                                    cwd=BASE, env=env, capture_output=True, text=True)
    assert "0 reminder(s) would be queued" in run("--dry-run").stdout  # too fresh
    with app_module.app.app_context():
        app_module.get_db().execute("UPDATE claims SET created_at = datetime('now', '-6 days')")
    assert "Queued 1 reminder(s)" in run().stdout
    assert "Queued 0 reminder(s)" in run().stdout  # never twice
    with app_module.app.app_context():
        db = app_module.get_db()
        mail = db.execute("SELECT to_addr, subject, body FROM mail_outbox WHERE subject LIKE '%reminder%'").fetchall()
        assert len(mail) == 1 and mail[0]["to_addr"] == "g1@example.com"
        assert "Towel set" in mail[0]["subject"] and "https://ourbayis.example/r/" in mail[0]["body"]
        assert "שלום" in mail[0]["body"]  # bilingual body
        assert "״סט מגבות״" in mail[0]["body"]  # Hebrew half names the gift in Hebrew
        assert not re.search(r"\d{4}-\d\d-\d\d", mail[0]["body"])  # "12 October 2026", not ISO
        assert re.search(r"\d{1,2} ב[א-ת]+ \d{4}", mail[0]["body"])
        assert db.execute("SELECT COUNT(*) FROM claims WHERE reminded_at IS NOT NULL").fetchone()[0] == 1


def test_page_views_are_counted_without_pii_and_skip_owner(client, app_module):
    app_module.app.test_client().get("/")
    app_module.app.test_client().get("/catalog?cat=kitchen")
    reg, _ = _couple_with_catalog_items(client, app_module, ["towel-set"])
    client.get(f"/r/{reg['slug']}")  # the owner's own visit
    app_module.app.test_client().get(f"/r/{reg['slug']}")  # a guest
    with app_module.app.app_context():
        rows = {r["name"]: r["n"] for r in app_module.get_db().execute("SELECT name, n FROM funnel_events")}
    assert rows["view:index"] == 1 and rows["view:catalog_page"] == 1
    assert rows["view:registry"] == 1
    assert not any(k.startswith("view:") and ("kitchen" in k or reg["slug"] in k) for k in rows)


def test_advertise_page_and_empty_ad_band(client):
    for lang in ("en", "he"):
        html = client.get(f"/advertise?lang={lang}").get_data(as_text=True)
        assert "topic=partner" in html and "ad-band" not in html  # no ad band on the ad page itself
    home = client.get("/").get_data(as_text=True)
    assert 'class="ad-band ad-band-empty"' in home and 'href="/advertise"' in home
    assert "affiliate links" in client.get("/catalog?lang=en").get_data(as_text=True)


def test_registry_browse_controls_expose_availability(client, app_module):
    reg, items = _couple_with_catalog_items(
        client, app_module, ["towel-set", "stand-mixer", "shabbos-urn-meicham", "electric-kettle"])
    ids = list(items)
    _claim(app_module, reg["slug"], items[ids[0]]["id"])
    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert 'id="only-available"' in page and 'id="reg-sort"' in page
    assert page.count('data-available="0"') == 1 and page.count('data-available="1"') == 3
    assert 'data-price="2290"' in page
    assert "affiliate links" in page


# ------------------------------------------------------------------ guides + optional Hebrew fields
def test_guides_index_and_articles_render_in_both_languages(client, app_module):
    import guides as ob_guides
    from markupsafe import escape  # Jinja escapes apostrophes/quotes in the copy
    for lang in ("en", "he"):
        index = client.get(f"/guides?lang={lang}").get_data(as_text=True)
        for g in ob_guides.GUIDES:
            assert f'/guides/{g["slug"]}' in index
            page = client.get(f"/guides/{g['slug']}?lang={lang}").get_data(as_text=True)
            assert str(escape(ob_guides.pick(g, "title", lang))) in page
            assert '"@type": "Article"' in page
            for s in g["sections"]:
                assert str(escape(ob_guides.pick(s, "h", lang))) in page
                for para in ob_guides.pick(s, "p", lang):
                    assert str(escape(para))[:40] in page
    assert client.get("/guides/not-a-guide").status_code == 404


def test_every_guide_is_fully_bilingual_and_makes_no_banned_claims():
    import guides as ob_guides
    slugs = [g["slug"] for g in ob_guides.GUIDES]
    assert len(slugs) == len(set(slugs))
    banned = ("no customs", "guaranteed", "halachically permitted", "works with any", "we ship")
    for g in ob_guides.GUIDES:
        for field in ("title", "summary"):
            assert g.get(field) and g.get(field + "_he"), (g["slug"], field)
        for s in g["sections"]:
            assert s.get("h") and s.get("h_he")
            assert len(s["p"]) == len(s["p_he"])
            if s.get("list"):
                assert len(s["list"]) == len(s["list_he"])
        blob = " ".join([g["title"], g["summary"]] +
                        [x for s in g["sections"] for x in [s["h"]] + s["p"] + s.get("list", [])])
        low = blob.lower()
        assert "shabbat" not in low
        for phrase in banned:
            assert phrase not in low, (g["slug"], phrase)


def test_guides_are_linked_and_in_the_sitemap(client):
    import guides as ob_guides
    home = client.get("/").get_data(as_text=True)
    assert '/guides"' in home
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    for g in ob_guides.GUIDES:
        assert f"/guides/{g['slug']}</loc>" in sitemap
        assert f"<lastmod>{g['updated']}</lastmod>" in sitemap
    assert "/guides</loc>" in sitemap


def test_hebrew_fields_are_collapsed_until_filled(client, app_module):
    signup(client)
    html = client.get("/registry/new").get_data(as_text=True)
    assert 'class="he-fields"' in html and "Add Hebrew (optional)" in html
    assert 'class="he-fields" open' not in html  # collapsed on a fresh form
    tok = get_csrf(html)
    client.post("/registry/new", data=dict(csrf_token=tok, title="Our Home", couple_names="S & D",
                                           title_he="הבית שלנו", event_type="wedding",
                                           visibility="unlisted"), follow_redirects=True)
    html = client.get("/registry/edit").get_data(as_text=True)
    assert 'class="he-fields" open' in html  # re-opened because a Hebrew value exists
    with app_module.app.app_context():
        reg = app_module.get_db().execute("SELECT * FROM registries").fetchone()
    assert reg["title_he"] == "הבית שלנו"  # still saved by the same form post
    page = client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    assert "הבית שלנו" in page


def test_bundle_sync_refreshes_only_untouched_seed_text(app_module):
    import ob_db
    seed = [dict(slug="full-nest", name="The Full Nest", tier="premium", price_from=17900,
                 items_text="new list", description="new desc",
                 replaces={"items_text": ["old list"], "description": ["old desc"],
                           "price_from": [1]})]
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("UPDATE bundles SET items_text='old list', description='edited in admin',"
                   " price_from=17900 WHERE slug='full-nest'")
        ob_db.bundle_sync(db, seed)
        row = db.execute("SELECT * FROM bundles WHERE slug='full-nest'").fetchone()
    assert row["items_text"] == "new list"            # still the old seed text -> refreshed
    assert row["description"] == "edited in admin"    # admin edit -> never overwritten
    assert row["price_from"] == 17900                 # only text fields are ever synced


def test_full_nest_says_appliances_are_installed(client):
    html = client.get("/shana-rishonah").get_data(as_text=True)
    assert "delivered and installed" in html
    assert "installation confirmed in your quote" not in html


def test_env_file_fills_unset_vars_only(tmp_path, monkeypatch):
    import ob_security
    f = tmp_path / "ob.env"
    f.write_text('# comment\nexport OB_T_A="one two"\nOB_T_B=from-file\n\nnot a setting\n',
                 encoding="utf-8")
    monkeypatch.delenv("OB_T_A", raising=False)
    monkeypatch.setenv("OB_T_B", "from-env")
    assert ob_security.load_env_file(f) == 1
    assert os.environ["OB_T_A"] == "one two"      # quotes and `export` stripped
    assert os.environ["OB_T_B"] == "from-env"     # a real env var always wins
    monkeypatch.delenv("OB_T_A")
    assert ob_security.load_env_file(tmp_path / "missing.env") == 0


def test_static_urls_are_versioned_and_cached(client):
    html = client.get("/").get_data(as_text=True)
    m = re.search(r'href="(/static/style\.css\?v=[0-9a-f]+)"', html)
    assert m, "style.css should carry a ?v= version"
    r = client.get(m.group(1))
    assert r.status_code == 200 and "immutable" in r.headers["Cache-Control"]
    assert "immutable" not in client.get("/static/style.css").headers.get("Cache-Control", "")
    fav = client.get("/favicon.ico")
    assert fav.status_code == 200 and fav.mimetype in ("image/x-icon", "image/vnd.microsoft.icon")
    assert 'rel="apple-touch-icon"' in html


def test_registry_page_shows_couple_names(client):
    signup(client)
    create_registry(client, couple="Rivka & Yossi")
    tok = get_csrf(client.get("/registry/edit").get_data(as_text=True))
    html = client.get("/dashboard").get_data(as_text=True)
    slug = re.search(r"/r/([a-z0-9-]+)", html).group(1)
    client.post("/logout", data=dict(csrf_token=tok))
    page = client.get(f"/r/{slug}").get_data(as_text=True)
    assert 'class="reg-couple bdi">Rivka &amp; Yossi<' in page
    assert "<title>Rivka &amp; Yossi · " in page


def test_guest_can_email_themselves_the_manage_link(client, app_module, monkeypatch):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    token = _claim(app_module, reg["slug"], list(items.values())[0]["id"])
    guest = app_module.app.test_client()
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert "Email me this link" not in html          # hidden while SMTP isn't configured
    monkeypatch.setattr(app_module.ob_mail, "configured", lambda: True)
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert "Email me this link" in html
    tok = get_csrf(html)
    r = guest.post(f"/g/{token}/email", data=dict(csrf_token=tok, email="not-an-email"),
                   follow_redirects=True)
    assert "look right" in r.get_data(as_text=True)
    r = guest.post(f"/g/{token}/email", data=dict(csrf_token=tok, email="aunt@example.com"),
                   follow_redirects=True)
    assert "check your inbox" in r.get_data(as_text=True)
    db = _db()
    assert db.execute("SELECT guest_email FROM claims").fetchone()[0] == "aunt@example.com"
    mail = db.execute("SELECT to_addr, body FROM mail_outbox WHERE to_addr='aunt@example.com'").fetchone()
    assert mail and f"/g/{token}" in mail["body"]
    assert guest.post("/g/not-a-real-token/email",
                      data=dict(csrf_token=tok, email="a@b.co")).status_code == 404


def test_dashboard_treats_lapsed_reservation_as_expired(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer", "towel-set"])
    ids = [i["id"] for i in items.values()]
    _claim(app_module, reg["slug"], ids[0], name="Lapsed Guest")
    _claim(app_module, reg["slug"], ids[1], name="Active Guest")
    db = _db()
    db.execute("UPDATE claims SET expires_at='2000-01-01 00:00:00' WHERE guest_name='Lapsed Guest'")
    db.commit()
    html = client.get("/dashboard").get_data(as_text=True)
    assert html.index("Active Guest") < html.rindex("Lapsed Guest")      # closed rows sort last
    assert re.search(r'class="gift-row\s+is-closed"[^>]*>\s*<div>\s*<strong>Lapsed Guest', html)
    assert re.search(r'<strong>1</strong><span>[^<]*</span></div>\s*<div class="stat-card"><strong>0', html)
    # a late arrival can still be confirmed as received
    cid = db.execute("SELECT id FROM claims WHERE guest_name='Lapsed Guest'").fetchone()[0]
    r = client.post(f"/claim/{cid}/confirm", data=dict(csrf_token=get_csrf(html)))
    assert r.headers["Location"].endswith(f"/dashboard#claim-{cid}")
    assert _db().execute("SELECT status FROM claims WHERE id=?", (cid,)).fetchone()[0] == "received"


def test_stale_release_never_undoes_a_received_gift(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    _claim(app_module, reg["slug"], list(items.values())[0]["id"])
    cid = _db().execute("SELECT id FROM claims").fetchone()[0]
    tok = get_csrf(client.get("/dashboard").get_data(as_text=True))
    client.post(f"/claim/{cid}/confirm", data=dict(csrf_token=tok))
    client.post(f"/claim/{cid}/cancel", data=dict(csrf_token=tok))      # e.g. from a second tab
    assert _db().execute("SELECT status FROM claims WHERE id=?", (cid,)).fetchone()[0] == "received"


def test_thanked_only_for_gifts_actually_given(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    _claim(app_module, reg["slug"], list(items.values())[0]["id"])
    cid = _db().execute("SELECT id FROM claims").fetchone()[0]
    html = client.get("/dashboard").get_data(as_text=True)
    assert f"/claim/{cid}/thanked" not in html                           # still only reserved
    client.post(f"/claim/{cid}/thanked", data=dict(csrf_token=get_csrf(html)))
    assert _db().execute("SELECT thanked FROM claims WHERE id=?", (cid,)).fetchone()[0] == 0


def test_share_links_use_base_url(client, app_module, monkeypatch):
    reg, _ = _couple_with_catalog_items(client, app_module, [])
    monkeypatch.setattr(app_module, "BASE_URL", "https://www.ourbayis.example")
    html = client.get("/dashboard").get_data(as_text=True)
    assert f'data-copy="https://www.ourbayis.example/r/{reg["slug"]}"' in html
    assert "https%3A//www.ourbayis.example/r/" in html or "https%3A%2F%2Fwww.ourbayis.example" in html


def test_custom_item_bad_link_is_reported_and_double_submit_ignored(client, app_module):
    signup(client)
    create_registry(client)
    tok = get_csrf(client.get("/registry/items").get_data(as_text=True))
    data = dict(csrf_token=tok, name="Hand-made mezuzah case", price_nis="250", url="not a url at all")
    r = client.post("/registry/items/add", data=data, follow_redirects=True)
    assert "left off" in r.get_data(as_text=True)
    client.post("/registry/items/add", data=data)                        # the double click
    rows = _db().execute("SELECT url FROM registry_items WHERE name='Hand-made mezuzah case'").fetchall()
    assert len(rows) == 1 and rows[0]["url"] == ""


def test_item_edit_keeps_typed_values_on_error_and_guards_qty(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["towel-set"])
    item = list(items.values())[0]
    _claim(app_module, reg["slug"], item["id"])
    html = client.get(f"/registry/items/{item['id']}/edit").get_data(as_text=True)
    assert 'min="1"' in html and "can&#39;t go below 1" in html
    tok = get_csrf(html)
    r = client.post(f"/registry/items/{item['id']}/edit",
                    data=dict(csrf_token=tok, name="My renamed towels", url="bad link", qty_wanted="1"))
    page = r.get_data(as_text=True)
    assert "valid link" in page and 'value="My renamed towels"' in page   # typed value survives
    r = client.post(f"/registry/items/{item['id']}/update", data=dict(csrf_token=tok, qty_wanted="3"))
    assert r.headers["Location"].endswith(f"/registry/items#item-{item['id']}")
    items_html = client.get("/registry/items").get_data(as_text=True)
    assert f'id="item-{item["id"]}"' in items_html and "A guest has already reserved" in items_html


def test_registry_form_keeps_visibility_and_rejects_bad_date(client, app_module):
    signup(client)
    create_registry(client)
    html = client.get("/registry/edit").get_data(as_text=True)
    r = client.post("/registry/edit", data=dict(
        csrf_token=get_csrf(html), title="Our Home", couple_names="S & D", event_type="wedding",
        event_date="next spring", visibility="public"))
    page = r.get_data(as_text=True)
    assert "pick the date from the calendar" in page
    assert re.search(r'value="public"\s+checked', page)       # the couple's choice survives the error
    assert _db().execute("SELECT event_date FROM registries").fetchone()[0] in ("", None)


def test_payment_link_change_notifies_owner_and_reauth_is_rate_limited(client, app_module):
    signup(client, email="owner@example.com")
    create_registry(client)
    tok = get_csrf(client.get("/registry/edit").get_data(as_text=True))
    base = dict(csrf_token=tok, title="Our Home", couple_names="S & D", event_type="wedding",
                visibility="unlisted", paypal_url="https://paypal.me/newlink")
    client.post("/registry/edit", data=dict(base, current_password="password1"))
    mail = _db().execute("SELECT body FROM mail_outbox WHERE to_addr='owner@example.com'"
                         " AND subject LIKE '%payment links%'").fetchone()
    assert mail and "paypal.me/newlink" in mail["body"]
    tok = get_csrf(client.get("/registry/edit").get_data(as_text=True))  # session_ver was bumped
    codes = [client.post("/registry/edit", data=dict(base, csrf_token=tok, paypal_url="https://paypal.me/other",
                                                     current_password="wrong")).status_code
             for _ in range(10)]
    assert codes[0] == 200 and 429 in codes


def test_double_submitted_create_makes_one_registry(client, app_module):
    signup(client)
    tok = get_csrf(client.get("/registry/new").get_data(as_text=True))
    data = dict(csrf_token=tok, title="Our Home", couple_names="S & D", event_type="wedding",
                visibility="unlisted")
    client.post("/registry/new", data=data)
    # the second POST of the same form (e.g. a double click) must not create another
    r = client.post("/registry/new", data=data)
    assert r.status_code == 302
    assert _db().execute("SELECT COUNT(*) FROM registries").fetchone()[0] == 1


def test_retired_seed_items_are_inactive_and_hidden(client, app_module):
    """Seed items marked "active": false (combos split into single products) are inserted
    retired on a fresh install: not in /catalog, not in the starter picker."""
    import json
    seed = json.loads(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8").read())["items"]
    retired = [it for it in seed if it.get("active") is False]
    assert retired, "expected at least one retired seed item"
    db = _db()
    for it in retired:
        row = db.execute("SELECT active FROM catalog_items WHERE seed_key=?", (it["seed_key"],)).fetchone()
        assert row is not None and row["active"] == 0, it["seed_key"]
    signup(client)
    create_registry(client)
    starter = client.get("/registry/items/starter").get_data(as_text=True)
    catalog = client.get("/catalog?q=Duvet").get_data(as_text=True)
    for it in retired:
        assert it["name"] not in starter and it["name"] not in catalog
    assert "Summer duvet (double)" in starter  # its replacement is offered instead


def test_illustrations_do_not_mislabel_kitchen_and_bath_items(app_module):
    ill = app_module.illustration_for
    item = lambda name, cat: {"name": name, "seed_key": "", "category": cat}  # noqa: E731
    assert ill(item("Baking pans & cookie sheets", "kitchen")) == "kitchen"   # not a bed
    assert ill(item("Non-slip bath mat", "bedding")) == "towel"
    assert ill(item("Shower shelf", "bedding")) == "towel"
    assert ill(item("Hot water pump pot (for Shabbos)", "dining")) == "urn"
    assert ill(item("Sheet sets (x2)", "bedding")) == "bedding"               # still a bed


def test_verified_prices_always_point_at_a_real_product():
    """A "Price checked <date>" tag is only honest if there is a product page behind it."""
    import json
    seed = json.loads(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8").read())["items"]
    bad = [it["seed_key"] for it in seed
           if it.get("active") is not False and it.get("price_status") == "verified"
           and not (it.get("url") and it.get("price_checked_at"))]
    assert not bad, f"verified without a store link/date: {bad}"


def test_palette_text_contrast_meets_wcag_aa():
    """Text colours from style.css's :root tokens against the backgrounds they sit on
    (WCAG AA, 4.5:1 for normal text). Guards the 2026-09-25 contrast pass."""
    css = open(os.path.join(BASE, "static", "style.css"), encoding="utf-8").read()
    tok = dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", css))

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def ratio(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    light = ["paper", "paper-deep", "card", "gold-soft"]
    for fg in ("ink", "ink-soft", "gold", "navy", "green", "danger"):
        for bg in light:
            assert ratio(tok[fg], tok[bg]) >= 4.5, (fg, bg, round(ratio(tok[fg], tok[bg]), 2))
    assert ratio(tok["paper"], tok["gold"]) >= 4.5       # .btn-gold text (cash-gift buttons)
    assert ratio(tok["gold-bright"], tok["navy-deep"]) >= 4.5   # gold text on the dark hero/footer
    wa = re.search(r"\.btn-wa \{ background: (#[0-9a-fA-F]{6})", css).group(1)
    assert ratio("#ffffff", wa) >= 4.5                   # WhatsApp share button


def test_error_page_survives_a_database_outage(app_module, monkeypatch):
    """The normal error page uses the layout, which queries the DB; if the DB is what broke,
    guests must still get a friendly (bilingual) page, not a bare server error."""
    import logging
    import sqlite3

    def boom():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(app_module, "get_db", boom)
    app_module.app.config["PROPAGATE_EXCEPTIONS"] = False
    app_module.app.config["TESTING"] = False
    logging.disable(logging.CRITICAL)
    try:
        r = app_module.app.test_client().get("/")
    finally:
        logging.disable(logging.NOTSET)
    html = r.get_data(as_text=True)
    assert r.status_code == 500
    assert "went wrong on our side" in html and "משהו השתבש" in html


@pytest.mark.parametrize("path", ["/", "/catalog", "/catalog?cat=kitchen", "/sample", "/sample?lang=he",
                                  "/shana-rishonah", "/guides", "/find?q=a", "/advertise", "/about",
                                  "/how-it-works", "/login", "/signup"])
def test_public_pages_have_sound_heading_outline_and_unique_ids(client, path):
    """One h1, no skipped heading levels (screen-reader navigation), no duplicate ids."""
    html = client.get(path).get_data(as_text=True)
    levels = [int(h) for h in re.findall(r"<h([1-6])[\s>]", html)]
    assert levels.count(1) == 1, (path, levels)
    assert not [(a, b) for a, b in zip(levels, levels[1:]) if b > a + 1], (path, levels)
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids)), (path, sorted({i for i in ids if ids.count(i) > 1}))


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


@pytest.mark.parametrize("ua,counted", [
    (BROWSER_UA, True),
    ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", False),
    ("WhatsApp/2.23.20.0", False),
    ("facebookexternalhit/1.1", False),
    ("curl/8.4.0", False),
    ("", False),
])
def test_bots_get_redirected_but_are_not_counted(client, app_module, ua, counted):
    """Click and view numbers are what the owner quotes to advertisers — people only."""
    reg, items = _couple_with_catalog_items(client, app_module, ["towel-set"])
    item = next(iter(items.values()))
    visitor = app_module.app.test_client()
    r = visitor.get(f"/go/i/{item['id']}", headers={"User-Agent": ua})
    assert r.status_code == 302 and r.headers["Location"] == item["url"]
    visitor.get(f"/r/{reg['slug']}", headers={"User-Agent": ua})
    db = _db()
    clicks = db.execute("SELECT clicks FROM registry_items WHERE id=?", (item["id"],)).fetchone()[0]
    views = db.execute("SELECT COALESCE(SUM(n), 0) FROM funnel_events WHERE name='view:registry'").fetchone()[0]
    assert (clicks, views) == ((1, 1) if counted else (0, 0))


def test_robots_keeps_crawlers_off_click_redirects(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /go/" in body


def test_public_dates_are_localised(client):
    """Price-checked tags showed a raw ISO date ("המחיר נבדק ב-2026-09-14")."""
    he = client.get("/catalog?lang=he").get_data(as_text=True)
    assert "המחיר נבדק ב-" in he
    assert not re.search(r"נבדק ב-\d{4}-\d\d-\d\d", he)
    en = client.get("/catalog?lang=en").get_data(as_text=True)
    assert re.search(r"Price checked \d{1,2} [A-Z][a-z]+ \d{4}", en)


@pytest.mark.parametrize("store,expect", [
    ("KSP", "לפרטי המוצר ב-KSP"),
    ("Machsanei Chashmal", "לפרטי המוצר ב-Machsanei Chashmal"),
    ("מחסני חשמל", "לפרטי המוצר במחסני חשמל"),
])
def test_hebrew_prefix_takes_maqaf_before_latin_store(app_module, store, expect):
    """"בMachsanei" is wrong Hebrew typography; a Hebrew store name stays joined."""
    assert app_module.tf("view_at_store", "he", store=store) == expect
    assert app_module.tf("view_at_store", "en", store="KSP").endswith("at KSP")


def test_confirmed_cash_gift_no_longer_offers_to_pay(client, app_module):
    """After the couple confirms a cash gift, the guest's page must not keep showing
    "amount to send" + the PayPal button — a returning guest could pay twice."""
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"], pay=True)
    item = next(iter(items.values()))
    token = _claim(app_module, reg["slug"], item["id"], give="cash")
    g = app_module.app.test_client()
    assert "paypal.me/sarahdovid" in g.get(f"/g/{token}").get_data(as_text=True)
    with app_module.app.app_context():
        cid = app_module.get_db().execute("SELECT id FROM claims").fetchone()[0]
    html = client.get("/dashboard").get_data(as_text=True)
    client.post(f"/claim/{cid}/confirm", data=dict(csrf_token=get_csrf(html)))
    page = g.get(f"/g/{token}").get_data(as_text=True)
    assert "paypal.me/sarahdovid" not in page and "Amount to send" not in page


def test_items_page_status_line_does_not_repeat_itself(client, app_module):
    """Was "1 reserved (1 reserved)"; also no raw ISO dates, no "IKEA · IKEA"."""
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    _claim(app_module, reg["slug"], next(iter(items.values()))["id"])
    page = client.get("/registry/items").get_data(as_text=True)
    note = re.search(r'<em class="claimed-note">(.*?)</em>', page, re.S).group(1)
    assert " ".join(note.split()) == "1 reserved"
    text = re.sub(r"<[^>]+>", " ", page)
    assert not re.search(r"checked \d{4}-\d\d-\d\d", text)
    assert "IKEA · IKEA" not in text and "Vardinon · Vardinon" not in text


def test_hebrew_description_line_on_cards(client, app_module):
    """The model line carries facts like "not sterling" — Hebrew pages show it in Hebrew."""
    reg, items = _couple_with_catalog_items(client, app_module, ["shabbos-candlesticks"])
    item = next(iter(items.values()))
    assert "לא כסף סטרלינג" in item["model_he"]           # copied onto the registry item
    he = client.get(f"/r/{reg['slug']}?lang=he").get_data(as_text=True)
    en = client.get(f"/r/{reg['slug']}?lang=en").get_data(as_text=True)
    assert "לא כסף סטרלינג" in he and "(not sterling)" not in he
    assert "(not sterling)" in en


def test_every_seed_description_line_has_hebrew():
    import json
    items = json.load(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8"))["items"]
    missing = [it["seed_key"] for it in items
               if it.get("model") and it.get("active", True) is not False and not it.get("model_he")]
    assert not missing, missing


def test_live_db_gets_model_he_from_ordinary_seed_sync(client, app_module):
    """On an existing install model_he starts empty; the usual `seed-sync` + `refresh-registry-links`
    fill it (catalog, then registry copies) without any forced overwrite."""
    import json
    import ob_db
    seed = json.load(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8"))["items"]
    _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    with app_module.app.app_context():
        db = app_module.get_db()
        cid = db.execute("SELECT id FROM catalog_items WHERE seed_key='stand-mixer'").fetchone()[0]
        db.execute("UPDATE catalog_items SET model_he='' WHERE id=?", (cid,))
        db.execute("UPDATE registry_items SET model_he='' WHERE catalog_id=?", (cid,))
        ob_db.seed_sync(db, seed)
        assert "קערת נירוסטה" in db.execute("SELECT model_he FROM catalog_items WHERE id=?", (cid,)).fetchone()[0]
        ob_db.refresh_registry_links(db)
        assert "קערת נירוסטה" in db.execute("SELECT model_he FROM registry_items").fetchone()[0]


def test_share_link_and_preview_follow_the_couples_language(client, app_module):
    """A couple using the site in Hebrew shares a Hebrew link (WhatsApp, copy, QR); the
    link preview says what the page is for instead of just "Registry for …"."""
    reg, _ = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    slug = reg["slug"]
    en = client.get("/dashboard?lang=en").get_data(as_text=True)
    assert f'data-copy="http://localhost/r/{slug}"' in en
    he = client.get("/dashboard?lang=he").get_data(as_text=True)
    assert f'data-copy="http://localhost/r/{slug}?lang=he"' in he
    assert f"/r/{slug}%3Flang%3Dhe" in he                       # WhatsApp share text
    with app_module.app.test_request_context("/?lang=he"):                  # what the QR encodes
        assert app_module.registry_share_url(slug).endswith(f"/r/{slug}?lang=he")
    page = app_module.app.test_client().get(f"/r/{slug}?lang=he").get_data(as_text=True)
    desc = re.search(r'<meta property="og:description" content="([^"]*)"', page).group(1)
    assert "מקימים בית חדש" in desc and "Sarah &amp; Dovid" in desc
    page = app_module.app.test_client().get(f"/r/{slug}?lang=en").get_data(as_text=True)
    assert "See the gifts they&#39;d love and reserve one." in page


def test_shana_form_keeps_what_was_typed_and_shows_messages_at_the_form(client):
    """The form posts to #request, so the page opens at the form: the message must be there
    (not at the top, off-screen), and a rejected request must not blank 2000 chars of notes."""
    html = client.get("/shana-rishonah").get_data(as_text=True)
    r = client.post("/shana-rishonah", data=dict(
        csrf_token=get_csrf(html), name="Test Lead", city="Yerushalayim", bundle="custom",
        furnishing="partly", budget="3000_6000", notes="Arriving after Sukkos, two rooms."))
    page = r.get_data(as_text=True)
    panel = page[page.index('id="request"'):]
    assert "Please add a WhatsApp number or email" in panel
    assert page.count("Please add a WhatsApp number or email") == 1      # not also at the top
    assert 'value="Test Lead"' in panel and 'value="Yerushalayim"' in panel
    assert ">Arriving after Sukkos, two rooms.</textarea>" in panel
    assert 'value="partly" selected' in panel and 'value="3000_6000" selected' in panel
    r = client.post("/shana-rishonah", data=dict(
        csrf_token=get_csrf(html), name="Test Lead", whatsapp="+972 50 123 4567"), follow_redirects=True)
    page = r.get_data(as_text=True)
    assert "Got it — mazel tov!" in page[page.index('id="request"'):]


def test_blank_guest_name_gets_a_specific_message(client, app_module):
    reg, items = _couple_with_catalog_items(client, app_module, ["stand-mixer"])
    item = next(iter(items.values()))
    g = app_module.app.test_client()
    html = g.get(f"/r/{reg['slug']}").get_data(as_text=True)
    r = g.post(f"/r/{reg['slug']}/claim/{item['id']}", data=dict(
        csrf_token=get_csrf(html), form_key=get_form_key(html), guest_name="   ", give="buy"))
    assert r.headers["Location"].endswith(f"#item-{item['id']}")
    page = g.get(r.headers["Location"]).get_data(as_text=True)
    assert "Please add your name so the couple knows who the gift is from" in page
    assert 'class="wrap flash-stack"' in page                      # app.js turns it into a toast


def test_failed_login_keeps_the_email(client):
    html = client.get("/login").get_data(as_text=True)
    page = client.post("/login", data=dict(csrf_token=get_csrf(html), email="dovid@example.com",
                                           password="wrong-password")).get_data(as_text=True)
    assert 'value="dovid@example.com"' in page


def test_backup_keeps_newest_n_and_never_touches_hand_made_snapshots(app_module, tmp_path):
    """A weekly scheduled backup must not slowly fill the hosting quota."""
    import subprocess
    import sys
    folder = tmp_path / "backups"
    folder.mkdir()
    for day in range(1, 17):                                   # 16 older automatic backups
        (folder / f"ourbayis-2026-01-{day:02d}-120000.db").write_bytes(b"x")
    (folder / "ourbayis-snapshot-2026-09-14.db").write_bytes(b"keep me")
    env = {**os.environ, "OB_DB_PATH": os.environ["OB_DB_PATH"], "OB_BACKUP_DIR": str(folder)}
    r = subprocess.run([sys.executable, os.path.join(BASE, "manage.py"), "backup"],
                       cwd=BASE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    names = sorted(p.name for p in folder.iterdir())
    auto = [n for n in names if n != "ourbayis-snapshot-2026-09-14.db"]
    assert "ourbayis-snapshot-2026-09-14.db" in names
    assert len(auto) == 14                                     # the new one + the 13 newest old ones
    assert "ourbayis-2026-01-01-120000.db" not in names and "ourbayis-2026-01-16-120000.db" in names
    assert "Removed 3 older backup(s)" in r.stdout
    r = subprocess.run([sys.executable, os.path.join(BASE, "manage.py"), "backup", "--keep", "0"],
                       cwd=BASE, env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "Removed" not in r.stdout    # --keep 0: nothing removed
    assert "ourbayis-2026-01-04-120000.db" in {p.name for p in folder.iterdir()}


@pytest.mark.parametrize("lang,key,n,expect", [
    ("en", "result_count", 1, "1 gift"), ("en", "result_count", 3, "3 gifts"),
    ("he", "result_count", 1, "מתנה אחת"), ("he", "result_count", 3, "3 מתנות"),
    ("en", "reg_countdown", 1, "Tomorrow!"), ("en", "reg_countdown", 2, "2 days to go!"),
    ("he", "reg_countdown", 1, "מחר!"), ("he", "reg_countdown", 2, "עוד יומיים!"),
    ("he", "reg_countdown", 9, "עוד 9 ימים!"),
    ("en", "items_needs_link", 1, "1 needs a store link or payment method"),
    ("he", "qty_reserved", 1, "1 שוריין"), ("he", "qty_reserved", 2, "2 שוריינו"),
    ("he", "qty_received", 1, "1 התקבל"),
    ("en", "item_edit_committed_hint", 1, "1 already reserved or confirmed by a guest — the quantity can't go below 1."),
])
def test_counts_read_naturally_at_one_and_two(app_module, lang, key, n, expect):
    """Was "1 gifts", "1 days to go!", "עוד 1 ימים!"."""
    assert app_module.tf(key, lang, n=n) == expect


def test_every_singular_form_has_a_base_key():
    import i18n
    for table in (i18n.T_EN, i18n.T_HE):
        for k in table:
            if k.endswith(("_one", "_two")) and k[:-4] in i18n.T_EN:
                assert "{n}" in i18n.T_EN[k[:-4]] or "{left}" in i18n.T_EN[k[:-4]], k


def test_one_gift_left_reads_singular_in_hebrew(app_module):
    assert app_module.tf("qty_available", "he", left=1, qty=3, n=1) == "1 מתוך 3 עדיין פנוי"
    assert app_module.tf("qty_available", "he", left=2, qty=3, n=2) == "2 מתוך 3 עדיין פנויים"
    assert app_module.tf("qty_available", "en", left=1, qty=3, n=1) == "1 of 3 still available"
