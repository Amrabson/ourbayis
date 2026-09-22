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
    html = client.get("/catalog").get_data(as_text=True)
    assert "117 gifts" in html and "Page 1 of 5" in html and 'rel="next"' in html
    html = client.get("/catalog?price=1500plus&kind=product&sort=price_desc").get_data(as_text=True)
    prices = [int(p.replace(",", "")) for p in re.findall(r"<strong>₪([\d,]+)</strong>", html)]
    assert prices and prices == sorted(prices, reverse=True) and min(prices) >= 1500
    assert "Reset filters" in html
    assert client.get("/catalog?page=99").status_code == 200  # clamps, never 500
    assert client.get("/catalog?page=abc&sort=evil&price=x").status_code == 200
    assert "Nothing matches" in client.get("/catalog?q=zzzzzz").get_data(as_text=True)
    he = client.get("/catalog?lang=he").get_data(as_text=True)
    assert "117 מתנות" in he


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
