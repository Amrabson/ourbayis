# -*- coding: utf-8 -*-
"""Gift ideas by budget (2026-11-07): public, indexable pages built from the catalog."""
import os
import sqlite3


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def test_index_lists_the_four_budgets(client):
    page = client.get("/gift-ideas?lang=en").get_data(as_text=True)
    assert "Gift ideas by budget" in page
    for slug in ("under-200", "200-500", "500-1500", "1500-plus"):
        assert f'href="/gift-ideas/{slug}"' in page
    assert "noindex" not in page
    he = client.get("/gift-ideas?lang=he").get_data(as_text=True)
    assert "רעיונות למתנות לפי תקציב" in he


def test_band_page_shows_only_that_price_range_grouped_by_category(client):
    db = _db()
    inside = db.execute("SELECT name FROM catalog_items WHERE active=1 AND price_nis >= 200 AND price_nis < 500"
                        " ORDER BY price_nis LIMIT 1").fetchone()["name"]
    outside = db.execute("SELECT name FROM catalog_items WHERE active=1 AND price_nis >= 1500"
                         " ORDER BY price_nis DESC LIMIT 1").fetchone()["name"]
    page = client.get("/gift-ideas/200-500?lang=en").get_data(as_text=True)
    assert "Gift ideas from ₪200 to ₪500" in page
    assert inside.replace("&", "&amp;") in page
    assert outside.replace("&", "&amp;") not in page
    assert 'aria-current="page"' in page
    assert client.get("/gift-ideas/cheap").status_code == 404


def test_gift_ideas_are_in_the_sitemap_and_footer(client):
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/gift-ideas</loc>" in sm and "/gift-ideas/1500-plus</loc>" in sm
    assert 'href="/gift-ideas"' in client.get("/about").get_data(as_text=True)
