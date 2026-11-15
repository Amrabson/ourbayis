# -*- coding: utf-8 -*-
"""Options and quality tiers in the catalog (2026-11-15): catalog_items.option_group / tier,
the "Other options" block on item pages, tier tags + "1 of N options" on cards, the /catalog
Quality filter, the admin form. Every test creates its own rows (slug prefix "zzopt"), so none of
it depends on which option groups the seed file happens to contain."""
import io
import os
import re
import sqlite3

import ob_db

from conftest import get_csrf, signup, create_registry
from test_p1 import admin_login


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _add(key, name=None, price=100, group="zzopt-pillow", tier="standard", active=1, cat="home", model=""):
    db = _db()
    db.execute(
        "INSERT INTO catalog_items (name, name_he, category, price_nis, seed_key, kind, active, sort,"
        " option_group, tier, model) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (name or "Zzopt " + key, "זזופט " + key, cat, price, key, "idea", active, 9000, group, tier, model))
    db.commit()
    cid = db.execute("SELECT id FROM catalog_items WHERE seed_key=?", (key,)).fetchone()[0]
    db.close()
    return cid


def _trio():
    """A basic / standard / premium pillow trio, inserted out of tier order and price order."""
    _add("zzopt-prem", "Zzopt Pillow Premium", 300, tier="premium", model="Zzmodel P")
    _add("zzopt-std", "Zzopt Pillow Standard", 120, tier="standard")
    _add("zzopt-basic", "Zzopt Pillow Basic", 60, tier="basic")


def _options_html(html):
    m = re.search(r'<section class="item-options".*?</section>', html, re.S)
    return m.group(0) if m else ""


def _card(html, cid):
    m = re.search(r'<article class="gift-card[^>]*id="c-%d".*?</article>' % cid, html, re.S)
    assert m, cid
    return m.group(0)


# ------------------------------------------------------------------ schema + sync
def test_migration_adds_columns_with_defaults(client):
    db = _db()
    cols = {r["name"]: r["dflt_value"] for r in db.execute("PRAGMA table_info(catalog_items)")}
    assert "option_group" in cols and "tier" in cols
    db.execute("INSERT INTO catalog_items (name, category, price_nis, seed_key) VALUES ('Zzopt plain','home',5,'zzopt-plain')")
    row = db.execute("SELECT option_group, tier FROM catalog_items WHERE seed_key='zzopt-plain'").fetchone()
    assert (row["option_group"], row["tier"]) == ("", "standard")
    assert len(ob_db.MIGRATIONS) >= 36
    # idempotent: running it again is harmless
    ob_db._m036_catalog_options(db)


def test_seed_sync_adopts_defaults_never_overwrites(client):
    db = _db()
    _add("zzopt-def", group="", tier="standard")           # still at the defaults
    _add("zzopt-set", group="mine", tier="basic")          # an admin's own values
    seed = [dict(seed_key="zzopt-def", name="Zzopt zzopt-def", option_group="shabbos-zz", tier="premium"),
            dict(seed_key="zzopt-set", name="Zzopt zzopt-set", option_group="other", tier="premium")]
    ob_db.seed_sync(db, seed)
    db.commit()
    a = db.execute("SELECT option_group, tier FROM catalog_items WHERE seed_key='zzopt-def'").fetchone()
    b = db.execute("SELECT option_group, tier FROM catalog_items WHERE seed_key='zzopt-set'").fetchone()
    assert (a["option_group"], a["tier"]) == ("shabbos-zz", "premium")
    assert (b["option_group"], b["tier"]) == ("mine", "basic")


def test_seed_sync_insert_sets_fields_and_bad_tier_is_standard(client):
    db = _db()
    ob_db.seed_sync(db, [
        dict(seed_key="zzopt-new1", name="Zzopt new one", option_group="pots-zz", tier="premium"),
        dict(seed_key="zzopt-new2", name="Zzopt new two", option_group="pots-zz", tier="luxurious"),
        dict(seed_key="zzopt-new3", name="Zzopt new three")])
    db.commit()
    got = {r["seed_key"]: (r["option_group"], r["tier"]) for r in
           db.execute("SELECT * FROM catalog_items WHERE seed_key LIKE 'zzopt-new%'")}
    assert got == {"zzopt-new1": ("pots-zz", "premium"), "zzopt-new2": ("pots-zz", "standard"),
                   "zzopt-new3": ("", "standard")}
    # a bad tier is never adopted onto an existing default row either
    ob_db.seed_sync(db, [dict(seed_key="zzopt-new3", name="Zzopt new three", tier="bogus")])
    db.commit()
    assert db.execute("SELECT tier FROM catalog_items WHERE seed_key='zzopt-new3'").fetchone()[0] == "standard"


# ------------------------------------------------------------------ item page
def test_item_page_options_block_order_and_current_marker(client):
    _trio()
    html = client.get("/catalog/zzopt-std").get_data(as_text=True)
    block = _options_html(html)
    assert 'id="options"' in block and "Other options" in block
    pos = [block.index(n) for n in ("Zzopt Pillow Basic", "Zzopt Pillow Standard", "Zzopt Pillow Premium")]
    assert pos == sorted(pos)                                   # basic -> standard -> premium
    assert block.count('class="opt-row') == 3
    assert "This one" in block and block.count("This one") == 1
    # the current item is not a link, the others are
    assert 'href="/catalog/zzopt-std"' not in block
    assert 'href="/catalog/zzopt-basic"' in block and 'href="/catalog/zzopt-prem"' in block
    assert "Zzmodel P" in block and "Premium" in block and "₪300" in block
    assert 'name="catalog_id"' in block and "back=item" in block and "slug=zzopt-std" in block


def test_same_tier_orders_by_price(client):
    _add("zzopt-s2", "Zzopt Std Dear", 200, tier="standard")
    _add("zzopt-s1", "Zzopt Std Cheap", 80, tier="standard")
    block = _options_html(client.get("/catalog/zzopt-s1").get_data(as_text=True))
    assert block.index("Zzopt Std Cheap") < block.index("Zzopt Std Dear")


def test_no_block_for_group_of_one_or_inactive_others(client):
    _add("zzopt-solo", group="zzopt-alone")
    assert 'id="options"' not in client.get("/catalog/zzopt-solo").get_data(as_text=True)
    _add("zzopt-a", group="zzopt-pair", price=90)
    _add("zzopt-b", group="zzopt-pair", price=95, active=0)
    assert 'id="options"' not in client.get("/catalog/zzopt-a").get_data(as_text=True)
    _add("zzopt-c", group="", price=95)                         # no group at all
    assert 'id="options"' not in client.get("/catalog/zzopt-c").get_data(as_text=True)


def test_more_in_category_skips_option_block_items(client):
    _trio()
    html = client.get("/catalog/zzopt-std").get_data(as_text=True)
    m = re.search(r'<section class="sec-inner item-more".*?</section>', html, re.S)
    more = m.group(0) if m else ""
    assert "Zzopt Pillow" not in more
    assert "Zzopt Pillow" in _options_html(html)


def test_options_block_signup_and_registry_paths(client):
    _trio()
    assert "Sign up to add" in client.get("/catalog/zzopt-std").get_data(as_text=True)
    signup(client)
    create_registry(client)
    cid = _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-prem'").fetchone()[0]
    html = client.get("/catalog/zzopt-std").get_data(as_text=True)
    r = client.post("/registry/items/add?back=item&slug=zzopt-std",
                    data=dict(csrf_token=get_csrf(html), catalog_id=str(cid)))
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalog/zzopt-std")
    again = _options_html(client.get("/catalog/zzopt-std").get_data(as_text=True))
    assert "state-added" in again


def test_options_render_in_hebrew(client):
    _trio()
    html = client.get("/catalog/zzopt-std?lang=he").get_data(as_text=True)
    block = _options_html(html)
    assert "אפשרויות נוספות" in block and "פרימיום" in block and "בסיסי" in block
    assert "זו שאתם רואים" in block
    assert 'dir="rtl"' in html


# ------------------------------------------------------------------ cards
def test_cards_show_tier_tag_and_option_count(client):
    _trio()
    html = client.get("/catalog?q=zzopt").get_data(as_text=True)
    prem = _card(html, _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-prem'").fetchone()[0])
    basic = _card(html, _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-basic'").fetchone()[0])
    std = _card(html, _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-std'").fetchone()[0])
    assert "tier-tag" in prem and ">Premium<" in prem
    assert "tier-tag" in basic and ">Basic<" in basic
    assert "tier-tag" not in std
    for c in (prem, basic, std):
        assert "1 of 3 options" in c and "/catalog/zzopt-" in c and "#options" in c
    he = client.get("/catalog?q=zzopt&lang=he").get_data(as_text=True)
    assert "פרימיום" in he and "אחת מתוך 3 אפשרויות" in he


def test_no_options_line_without_alternatives(client):
    _add("zzopt-solo", group="zzopt-alone")
    cid = _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-solo'").fetchone()[0]
    card = _card(client.get("/catalog?q=zzopt").get_data(as_text=True), cid)
    assert "options" not in card.split("</h3>")[1]


def test_registry_cards_carry_no_tier_or_options(client):
    _trio()
    signup(client)
    create_registry(client)
    db = _db()
    cid = db.execute("SELECT id FROM catalog_items WHERE seed_key='zzopt-prem'").fetchone()[0]
    html = client.get("/registry/items").get_data(as_text=True)
    client.post("/registry/items/add", data=dict(csrf_token=get_csrf(html), catalog_id=str(cid)))
    slug = db.execute("SELECT slug FROM registries").fetchone()[0]
    page = client.get(f"/r/{slug}").get_data(as_text=True)
    assert "Zzopt Pillow Premium" in page
    assert "tier-tag" not in page and "options</" not in page and "#options" not in page


def test_category_page_and_gift_ideas_render_with_tags(client):
    _trio()
    r = client.get("/gifts/home-essentials")
    assert r.status_code == 200 and "tier-tag" in r.get_data(as_text=True)
    r = client.get("/gift-ideas/under-200")
    assert r.status_code == 200 and "Zzopt Pillow Basic" in r.get_data(as_text=True)


# ------------------------------------------------------------------ catalog filter
def test_tier_filter_lists_only_that_tier_and_combines(client):
    _trio()
    _add("zzopt-kit", "Zzopt Kitchen Premium", 500, group="", tier="premium", cat="kitchen")
    html = client.get("/catalog?tier=premium&q=zzopt").get_data(as_text=True)
    assert "Zzopt Pillow Premium" in html and "Zzopt Kitchen Premium" in html
    assert "Zzopt Pillow Basic" not in html and "Zzopt Pillow Standard" not in html
    both = client.get("/catalog?tier=premium&cat=home&q=zzopt").get_data(as_text=True)
    assert "Zzopt Pillow Premium" in both and "Zzopt Kitchen Premium" not in both
    assert 'name="tier"' in html and 'option value="premium" selected' in html


def test_tier_filter_pagination_keeps_tier(client):
    for i in range(30):
        _add("zzopt-m%02d" % i, "Zzopt Many %02d" % i, 50 + i, group="", tier="premium")
    _add("zzopt-lo", "Zzopt Many Low", 40, group="", tier="basic")
    html = client.get("/catalog?tier=premium&q=zzopt").get_data(as_text=True)
    m = re.search(r'<a class="btn btn-ghost btn-sm" href="([^"]+)" rel="next"', html)
    assert m and "tier=premium" in m.group(1) and "page=2" in m.group(1)
    page2 = client.get(m.group(1).replace("&amp;", "&")).get_data(as_text=True)
    assert "Zzopt Many Low" not in page2 and "Zzopt Many Low" not in html
    assert re.search(r"Zzopt Many \d\d", page2) and "tier=premium" in page2


def test_bogus_tier_is_ignored_and_filtered_page_is_noindex(client):
    _trio()
    html = client.get("/catalog?tier=bogus&q=zzopt").get_data(as_text=True)
    assert all(n in html for n in ("Zzopt Pillow Basic", "Zzopt Pillow Standard", "Zzopt Pillow Premium"))
    assert 'option value="premium" selected' not in html and 'option value="basic" selected' not in html
    ok = client.get("/catalog?tier=premium").get_data(as_text=True)
    assert 'content="noindex' in ok
    assert 'content="noindex' not in client.get("/catalog").get_data(as_text=True)


def test_tier_filter_hebrew(client):
    _trio()
    html = client.get("/catalog?tier=basic&q=zzopt&lang=he").get_data(as_text=True)
    assert "רמת איכות" in html and "כל הרמות" in html and "בסיסי" in html


# ------------------------------------------------------------------ admin
def test_admin_form_saves_option_group_and_tier(client):
    admin_login(client)
    page = client.get("/admin/catalog/new").get_data(as_text=True)
    assert 'name="option_group"' in page and 'name="tier"' in page
    r = client.post("/admin/catalog/new", data=dict(
        csrf_token=get_csrf(page), name="Zzopt Admin Made", category="home", price_nis="150",
        option_group=" Zz Group! ", tier="premium", active="on", kind="idea", sort="0"))
    assert r.status_code == 302
    row = _db().execute("SELECT * FROM catalog_items WHERE name='Zzopt Admin Made'").fetchone()
    assert (row["option_group"], row["tier"]) == ("zz-group", "premium")
    edit = client.get("/admin/catalog/%d/edit" % row["id"]).get_data(as_text=True)
    assert 'value="zz-group"' in edit and re.search(r'<option value="premium" selected', edit)
    client.post("/admin/catalog/%d/edit" % row["id"], data=dict(
        csrf_token=get_csrf(edit), name="Zzopt Admin Made", category="home", price_nis="150",
        option_group="zz-group", tier="nonsense", active="on", kind="idea", sort="0"))
    assert _db().execute("SELECT tier FROM catalog_items WHERE id=?", (row["id"],)).fetchone()[0] == "standard"
    csv_text = client.get("/admin/catalog.csv").get_data(as_text=True)
    assert csv_text.splitlines()[0].endswith("option_group,tier") and "zz-group" in csv_text


def test_csv_import_sets_option_group_and_tier(client):
    admin_login(client)
    _add("zzopt-imp", group="")
    text = "seed_key,option_group,tier\nzzopt-imp,Zz Imp,PREMIUM\n"
    tok = get_csrf(client.get("/admin/catalog/import").get_data(as_text=True))
    client.post("/admin/catalog/import", data=dict(
        csrf_token=tok, mode="apply", file=(io.BytesIO(text.encode()), "x.csv")),
        content_type="multipart/form-data")
    row = _db().execute("SELECT option_group, tier FROM catalog_items WHERE seed_key='zzopt-imp'").fetchone()
    assert (row["option_group"], row["tier"]) == ("zz-imp", "premium")


# ------------------------------------------------------------------ setup cost
def test_setup_cost_unchanged_by_tiers(client):
    before = client.get("/setup-cost").get_data(as_text=True)
    m = re.search(r'id="starter-tally"[^>]*>([^<]*)<', before)
    db = _db()
    ids = [r[0] for r in db.execute(
        "SELECT id FROM catalog_items WHERE active=1 AND starter_group != '' ORDER BY id LIMIT 6")]
    for n, i in enumerate(ids):
        db.execute("UPDATE catalog_items SET option_group='zzopt-setup', tier=? WHERE id=?",
                   (("premium", "basic", "standard")[n % 3], i))
    db.commit()
    db.close()
    after = client.get("/setup-cost").get_data(as_text=True)
    m2 = re.search(r'id="starter-tally"[^>]*>([^<]*)<', after)
    assert (m.group(1) if m else "") == (m2.group(1) if m2 else "")
    # same items (the tier tags/option lines don't change what is listed or priced)
    assert re.findall(r'data-price="(\d+)"', before) == re.findall(r'data-price="(\d+)"', after)
