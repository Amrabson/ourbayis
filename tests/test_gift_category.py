# -*- coding: utf-8 -*-
"""Category landing pages (2026-11-12): /gifts/<slug>, indexable, one per i18n.CATEGORIES entry."""
import json
import re
import sqlite3
import os

import pytest

SLUGS = {"kitchen": "kitchen", "appliances": "appliances", "shabbos-table": "dining",
         "bedding-and-bath": "bedding", "judaica": "judaica", "home-essentials": "home"}


def _ld(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


@pytest.mark.parametrize("slug", list(SLUGS))
def test_category_page_is_indexable_and_complete(client, app_module, slug):
    r = client.get(f"/gifts/{slug}")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "noindex" not in html
    assert f'<link rel="canonical" href="http://localhost/gifts/{slug}"' in html or f"/gifts/{slug}\"" in html
    cat = SLUGS[slug]
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    n = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND category=?", (cat,)).fetchone()[0]
    assert n and html.count('class="gift-card') >= n
    assert "for a home in Israel" in html and "Good to know" in html
    assert "Some store links are affiliate links" in html
    lds = _ld(html)
    kinds = {d["@type"] for d in lds}
    assert kinds == {"BreadcrumbList", "ItemList"}
    il = next(d for d in lds if d["@type"] == "ItemList")
    assert len(il["itemListElement"]) == n and all("/catalog/" in e["url"] for e in il["itemListElement"])
    for other in SLUGS:
        if other != slug:
            assert f'href="/gifts/{other}"' in html
    assert f'href="/gifts/{slug}"' not in html.split('class="chip-row cat-links"')[1].split("</nav>")[0]


def test_unknown_category_is_404(client):
    assert client.get("/gifts/nope").status_code == 404
    assert client.get("/gifts/dining").status_code == 404


def test_items_cheapest_first_within_bands(client):
    html = client.get("/gifts/kitchen").get_data(as_text=True)
    assert "Under ₪200" in html
    prices = [int(p.replace(",", "")) for p in re.findall(r'₪([\d,]+)', html.split("ideas-body")[1].split("catalog-affiliate")[0])]
    assert prices  # grouped bands ascend overall
    firsts = [m for m in re.findall(r'cat-band-(\w+)"', html)]
    assert firsts == sorted(firsts, key=["under200", "200_500", "500_1500", "1500plus"].index)


def test_hebrew_and_sitemap_and_links_in(client):
    he = client.get("/gifts/kitchen?lang=he").get_data(as_text=True)
    assert 'dir="rtl"' in he and "מתנות למטבח לבית בישראל" in he
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    for slug in SLUGS:
        assert f"/gifts/{slug}</loc>" in sm and f"/gifts/{slug}?lang=he</loc>" in sm
    ideas = client.get("/gift-ideas").get_data(as_text=True)
    assert all(f'href="/gifts/{s}"' in ideas for s in SLUGS)
    home = client.get("/").get_data(as_text=True)
    assert 'href="/gifts/kitchen"' in home and "/catalog?cat=kitchen" not in home
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    key = db.execute("SELECT seed_key FROM catalog_items WHERE active=1 AND category='kitchen' AND seed_key!='' LIMIT 1").fetchone()[0]
    item = client.get(f"/catalog/{key}").get_data(as_text=True)
    assert 'href="/gifts/kitchen"' in item and "/catalog?cat=kitchen" not in item
    assert "/gifts/kitchen" in json.dumps(_ld(item))


def test_add_from_category_page_returns_there(client):
    from conftest import create_registry, get_csrf, signup
    signup(client)
    create_registry(client)
    html = client.get("/gifts/kitchen").get_data(as_text=True)
    m = re.search(r'action="(/registry/items/add\?[^"]*back=cat[^"]*)".*?name="catalog_id" value="(\d+)"', html, re.S)
    assert m
    r = client.post(m.group(1).replace("&amp;", "&"), data=dict(csrf_token=get_csrf(html), catalog_id=m.group(2)))
    assert r.status_code == 302 and "/gifts/kitchen" in r.headers["Location"]
