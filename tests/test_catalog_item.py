# -*- coding: utf-8 -*-
"""Public page per catalog item (/catalog/<slug>, 2026-11-11): slug rules, 404s, SEO tags, JSON-LD,
the store handoff, the add-to-registry flow through signup, card links, and the category guidance."""
import json
import os
import re
import sqlite3

import pytest

from conftest import get_csrf, signup, create_registry
from test_p2 import _couple_with_catalog_items


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _item(where):
    db = _db()
    row = db.execute(f"SELECT * FROM catalog_items WHERE active=1 AND {where} ORDER BY id LIMIT 1").fetchone()
    db.close()
    assert row is not None, where
    return row


def _ld(html, kind):
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        data = json.loads(blob)
        if data.get("@type") == kind:
            return data
    raise AssertionError(f"no {kind} JSON-LD")


def _h1(html):
    return re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S).group(1)


def test_page_renders_in_english_and_hebrew_with_the_name_in_the_h1(client):
    item = _item("seed_key='towel-set'")
    en = client.get(f"/catalog/{item['seed_key']}?lang=en")
    assert en.status_code == 200 and item["name"] in _h1(en.get_data(as_text=True))
    he_html = client.get(f"/catalog/{item['seed_key']}?lang=he").get_data(as_text=True)
    assert item["name_he"] in _h1(he_html)
    assert 'dir="rtl"' in he_html and "טוב לדעת" in he_html
    assert "price in Israel" in en.get_data(as_text=True) and "מחיר בישראל" in he_html


def test_unknown_slug_and_inactive_item_are_404(client):
    assert client.get("/catalog/no-such-thing").status_code == 404
    assert client.get("/catalog/item-999999").status_code == 404
    item = _item("seed_key IS NOT NULL")
    assert client.get(f"/catalog/{item['seed_key']}").status_code == 200
    db = _db()
    db.execute("UPDATE catalog_items SET active=0 WHERE id=?", (item["id"],))
    db.commit(); db.close()
    assert client.get(f"/catalog/{item['seed_key']}").status_code == 404


def test_filtered_catalog_route_still_works(client):
    assert client.get("/catalog?cat=kitchen&sort=price_asc").status_code == 200
    assert "Towel set" in client.get("/catalog?q=towel").get_data(as_text=True)


def _insert_unseeded(name="Admin added kettle stand", price=123, price_status="estimate", url=""):
    db = _db()
    cur = db.execute(
        "INSERT INTO catalog_items (name, name_he, category, price_nis, store, url, price_status, active, seed_key)"
        " VALUES (?,?,?,?,?,?,?,1,NULL)", (name, "מעמד לקומקום", "kitchen", price, "KSP", url, price_status))
    db.commit()
    cid = cur.lastrowid
    db.close()
    return cid


def test_item_without_seed_key_lives_at_item_dash_id(client, app_module):
    cid = _insert_unseeded()
    r = client.get(f"/catalog/item-{cid}")
    assert r.status_code == 200 and "Admin added kettle stand" in _h1(r.get_data(as_text=True))
    with app_module.app.test_request_context("/"):
        row = app_module.get_db().execute("SELECT * FROM catalog_items WHERE id=?", (cid,)).fetchone()
        assert app_module.catalog_slug(row) == f"item-{cid}"
        assert app_module.item_url(row) == f"/catalog/item-{cid}"
        assert app_module.item_url({"name": "x", "category": "home", "id": -3, "registry_id": 0}) is None
    # a seeded row is not also reachable under item-<id>
    seeded = _item("seed_key IS NOT NULL")
    assert client.get(f"/catalog/item-{seeded['id']}").status_code == 404


def test_canonical_is_the_path_and_page_is_indexable(client):
    item = _item("seed_key='towel-set'")
    path = f"/catalog/{item['seed_key']}"
    en = client.get(path).get_data(as_text=True)
    assert re.search(rf'<link rel="canonical" href="[^"]*{re.escape(path)}">', en)
    assert 'name="robots"' not in en
    he = client.get(path + "?lang=he").get_data(as_text=True)
    assert re.search(rf'<link rel="canonical" href="[^"]*{re.escape(path)}\?lang=he">', he)
    assert 'name="robots"' not in he and 'hreflang="x-default"' in he
    assert 'content="noindex' in client.get(path + "?utm=x").get_data(as_text=True)


def test_title_and_meta_description(client):
    item = _item("seed_key='towel-set'")
    html = client.get(f"/catalog/{item['seed_key']}").get_data(as_text=True)
    assert f"<title>{item['name']} — price in Israel | OurBayis</title>" in html
    for lang in ("en", "he"):
        h = client.get(f"/catalog/{item['seed_key']}?lang={lang}").get_data(as_text=True)
        desc = re.search(r'<meta name="description" content="([^"]*)"', h).group(1)
        assert 0 < len(desc) <= 155 and "₪" in desc


def test_every_description_fits_the_limit(client, app_module):
    db = _db()
    rows = db.execute("SELECT * FROM catalog_items WHERE active=1").fetchall()
    db.close()
    with app_module.app.test_request_context("/"):
        for row in rows:
            for lang in ("en", "he"):
                assert len(app_module._item_description(row, lang)) <= 155, (row["seed_key"], lang)


def test_sitemap_lists_item_pages_and_views_are_counted(client):
    item = _item("seed_key='towel-set'")
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert f"/catalog/{item['seed_key']}</loc>" in xml and f"/catalog/{item['seed_key']}?lang=he</loc>" in xml
    cid = _insert_unseeded()
    assert f"/catalog/item-{cid}</loc>" in client.get("/sitemap.xml").get_data(as_text=True)
    client.get(f"/catalog/{item['seed_key']}")
    db = _db()
    assert db.execute("SELECT SUM(n) FROM funnel_events WHERE name='view:catalog_item'").fetchone()[0] == 1


def test_product_json_ld_offers_only_for_a_verified_item_with_a_url(client):
    verified = _item("price_status='verified' AND url != '' AND price_nis > 0")
    html = client.get(f"/catalog/{verified['seed_key']}").get_data(as_text=True)
    prod = _ld(html, "Product")
    assert prod["name"] == verified["name"] and "image" not in prod
    offer = prod["offers"]
    assert offer["price"] == verified["price_nis"] and offer["priceCurrency"] == "ILS"
    assert offer["url"].endswith(f"/catalog/{verified['seed_key']}")
    assert offer["seller"]["name"] == verified["store"]
    assert "aggregateRating" not in prod and "review" not in prod and "availability" not in offer
    crumbs = _ld(html, "BreadcrumbList")["itemListElement"]
    assert [c["position"] for c in crumbs] == [1, 2, 3]
    # estimate -> no offers; verified without a store link -> no offers
    est = _item("price_status='estimate'")
    assert "offers" not in _ld(client.get(f"/catalog/{est['seed_key']}").get_data(as_text=True), "Product")
    db = _db()
    db.execute("UPDATE catalog_items SET url='' WHERE id=?", (verified["id"],))
    db.commit(); db.close()
    assert "offers" not in _ld(client.get(f"/catalog/{verified['seed_key']}").get_data(as_text=True), "Product")


def test_store_link_goes_through_go_and_is_marked_sponsored(client):
    item = _item("url LIKE '%ksp.co.il%'")
    html = client.get(f"/catalog/{item['seed_key']}").get_data(as_text=True)
    m = re.search(r'<a class="btn btn-ghost btn-lg bdi" href="([^"]+)"[^>]*rel="([^"]+)"', html)
    assert m and m.group(1) == f"/go/c/{item['id']}"
    assert m.group(2) == "nofollow sponsored noopener" and 'target="_blank"' in html
    assert item["url"] not in html
    db = _db()
    db.execute("UPDATE catalog_items SET url='' WHERE id=?", (item["id"],))
    db.commit(); db.close()
    assert "/go/c/" not in client.get(f"/catalog/{item['seed_key']}").get_data(as_text=True)


def test_add_to_registry_logged_out_goes_through_signup_then_adds(client):
    item = _item("seed_key='towel-set'")
    slug = item["seed_key"]
    html = client.get(f"/catalog/{slug}").get_data(as_text=True)
    assert "Add to your registry" in html
    assert f'action="/registry/items/add?back=item&amp;slug={slug}"' in html
    r = client.post(f"/registry/items/add?back=item&slug={slug}",
                    data=dict(csrf_token=get_csrf(html), catalog_id=str(item["id"])))
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")
    signup(client, email="itempage@example.com")
    create_registry(client)
    db = _db()
    assert db.execute("SELECT COUNT(*) FROM registry_items WHERE catalog_id=?", (item["id"],)).fetchone()[0] == 1
    db.close()
    # logged in: the button is replaced by "Added", and a "more" card add returns to this page
    page = client.get(f"/catalog/{slug}").get_data(as_text=True)
    assert "Add to your registry" not in page
    other = _item(f"category='{item['category']}' AND id != {item['id']}")
    r = client.post(f"/registry/items/add?back=item&slug={slug}",
                    data=dict(csrf_token=get_csrf(page), catalog_id=str(other["id"])))
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/catalog/{slug}")
    # a bad slug never becomes a redirect target
    r = client.post("/registry/items/add?back=item&slug=//evil.example",
                    data=dict(csrf_token=get_csrf(page), catalog_id=str(other["id"])))
    assert "evil" not in r.headers["Location"]


def test_catalog_cards_link_to_the_item_page_but_registry_cards_do_not(client, app_module):
    item = _item("seed_key='towel-set'")
    cat = client.get("/catalog?cat=bedding").get_data(as_text=True)
    assert f'<a class="gift-name-link" href="/catalog/{item["seed_key"]}">' in cat
    ideas = client.get("/gift-ideas/under-200").get_data(as_text=True)
    assert 'class="gift-name-link" href="/catalog/' in ideas
    home = client.get("/").get_data(as_text=True)
    assert re.search(r'<a class="gift-card[^"]*gift-card-link"\s+href="/catalog/', home)
    sample = client.get("/sample").get_data(as_text=True)
    assert 'href="/catalog/' not in sample
    reg, _items = _couple_with_catalog_items(client, app_module, ["towel-set"])
    page = client.get(f"/r/{reg['slug']}").get_data(as_text=True)
    assert 'href="/catalog/' not in page and "gift-name-link" not in page


def test_more_in_category_shows_up_to_four_other_items_of_that_category(client):
    item = _item("seed_key='towel-set'")
    html = client.get(f"/catalog/{item['seed_key']}").get_data(as_text=True)
    more = html.split('id="item-more-h"')[1]
    cards = re.findall(r'<article class="gift-card', more)
    assert 1 <= len(cards) <= 4
    assert f'href="/catalog/{item["seed_key"]}"' not in more
    assert "/gift-ideas/" in html and "/guides/" in html


def test_every_category_has_three_notes_in_both_languages():
    from i18n import CATEGORIES, T_EN, T_HE
    for cat in CATEGORIES:
        for n in (1, 2, 3):
            key = f"item_know_{cat}_{n}"
            assert T_EN.get(key) and T_HE.get(key), key
            low = T_EN[key].lower()
            assert "shabbat" not in low and "safe" not in low and "secure" not in low, key
            assert "₪" not in T_EN[key] and "%" not in T_EN[key], key


def test_item_title_keys_exist_in_both_languages():
    from i18n import T_EN, T_HE
    for key in ("item_title", "item_desc_at", "item_desc_tail", "item_add_registry", "item_view_at",
                "item_know_h", "item_more_band", "item_more_h", "item_next_h", "item_crumbs"):
        assert T_EN.get(key) and T_HE.get(key), key


def test_every_active_catalog_item_page_renders(client):
    db = _db()
    slugs = [r["seed_key"] for r in db.execute("SELECT seed_key FROM catalog_items WHERE active=1")]
    db.close()
    assert len(slugs) > 100
    for slug in slugs:
        r = client.get(f"/catalog/{slug}")
        assert r.status_code == 200, slug
        assert "<h1" in r.get_data(as_text=True)
    for slug in slugs[::10]:
        assert client.get(f"/catalog/{slug}?lang=he").status_code == 200
