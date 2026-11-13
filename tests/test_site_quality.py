# -*- coding: utf-8 -*-
"""Site quality (2026-11-08): skip link, compressed CSS/JS, gift-ideas views counted."""
import gzip
import os
import sqlite3


def test_every_page_has_a_skip_link_to_main(client):
    for url in ("/?lang=en", "/catalog?lang=he", "/gift-ideas", "/setup-cost", "/setup-cost?lang=he",
                "/gifts/kitchen", "/gifts/shabbos-table?lang=he"):
        html = client.get(url).get_data(as_text=True)
        assert 'class="skip-link" href="#main"' in html and '<main id="main"' in html
    assert "דילוג לתוכן" in client.get("/?lang=he").get_data(as_text=True)


def test_item_pages_have_skip_link_and_canonical(client, app_module):
    with app_module.app.app_context():
        row = app_module.get_db().execute("SELECT * FROM catalog_items WHERE active=1 ORDER BY id").fetchone()
        slug = app_module.catalog_slug(row)
    for lang in ("en", "he"):
        html = client.get(f"/catalog/{slug}?lang={lang}").get_data(as_text=True)
        assert 'class="skip-link" href="#main"' in html and '<main id="main"' in html
        assert 'rel="canonical"' in html


def test_css_and_js_go_out_compressed(client):
    for path in ("/static/style.css", "/static/app.js"):
        r = client.get(path, headers={"Accept-Encoding": "gzip, br"})
        assert r.headers.get("Content-Encoding") == "gzip"
        assert "Accept-Encoding" in r.headers.get("Vary", "")
        body = gzip.decompress(r.data)
        assert len(r.data) < len(body) / 3
        with open(os.path.join(client.application.static_folder, path.rsplit("/", 1)[1]), "rb") as fh:
            assert body == fh.read()
    plain = client.get("/static/style.css")  # no Accept-Encoding: the file as is
    assert "Content-Encoding" not in plain.headers and b"--paper" in plain.data


def test_gift_ideas_pages_are_counted(client):
    client.get("/gift-ideas/under-200")
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    assert db.execute("SELECT SUM(n) FROM funnel_events WHERE name='view:gift_ideas'").fetchone()[0] == 1


def test_registry_on_phones_puts_gifts_first(client):
    """The rates footnote sits under the list, and the apartment drawing has a fold-away button
    (shown on phones only, by CSS) that controls it."""
    page = client.get("/sample?lang=en").get_data(as_text=True)
    assert page.index('class="gift-grid"') < page.index("rates-note-foot")
    assert 'class="reg-plan-toggle" aria-expanded="false" aria-controls="reg-plan-body"' in page
    assert 'id="reg-plan-body"' in page
    assert "לראות את הבית שלהם" in client.get("/sample?lang=he").get_data(as_text=True)


def test_share_previews_say_whose_list_and_whats_open(client):
    """WhatsApp/Facebook read og:*: a registry link names the couple, the date, what's still open, and shows
    the registry card in the reader's language; other pages show the homepage card."""
    import re
    for lang in ("en", "he"):
        for name in ("og-home", "og-registry"):
            assert os.path.getsize(os.path.join(client.application.static_folder, f"{name}-{lang}.png")) > 20000
    page = client.get("/sample?lang=en").get_data(as_text=True)
    title = re.search(r'property="og:title" content="([^"]*)"', page).group(1)
    desc = re.search(r'property="og:description" content="([^"]*)"', page).group(1)
    assert title == "Chana &amp; Moshe: our gift list"
    assert "Wedding · " in desc and "still open" in desc
    assert "og-registry-en.png" in page
    he = client.get("/sample?lang=he").get_data(as_text=True)
    assert "og-registry-he.png" in he and "רשימת המתנות שלנו" in he
    assert "og-home-en.png" in client.get("/catalog?lang=en").get_data(as_text=True)
