# -*- coding: utf-8 -*-
"""Comparison pages (/compare, /compare/<group>), the picture-host preconnects and the item page's
fetchpriority. Expectations are built from the DB at test time (the seed file is edited elsewhere);
test-owned groups use the slug prefix "zzcmp"."""
import json
import os
import re
import sqlite3

import pytest

from conftest import get_csrf, signup, create_registry

TIER_RANK = {"basic": 0, "standard": 1, "premium": 2}


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _groups(db=None):
    """{group: [rows in tier-then-price order]} for groups with >= 2 active items."""
    own = db is None
    db = db or _db()
    rows = db.execute("SELECT * FROM catalog_items WHERE active=1 AND option_group != ''").fetchall()
    if own:
        db.close()
    out = {}
    for r in rows:
        out.setdefault(r["option_group"], []).append(r)
    for v in out.values():
        v.sort(key=lambda r: (TIER_RANK.get(r["tier"], 1), r["price_nis"] or 0, r["sort"] or 0, r["id"]))
    return {k: v for k, v in out.items() if len(v) > 1}


def _add(key, name, price, group="zzcmp-pillow", tier="standard", image="", active=1, cat="bedding"):
    db = _db()
    db.execute(
        "INSERT INTO catalog_items (name, name_he, category, price_nis, seed_key, kind, active, sort,"
        " option_group, tier, image) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (name, "זזק " + key, cat, price, key, "idea", active, 9000, group, tier, image))
    db.commit()
    cid = db.execute("SELECT id FROM catalog_items WHERE seed_key=?", (key,)).fetchone()[0]
    db.close()
    return cid


def _trio(image=False):
    h = ["https://ksp.co.il/a.jpg", "https://ksp.co.il/b.jpg", "https://www.heichal.co.il/c.jpg"]
    _add("zzcmp-prem", "Zzcmp Pillow Premium", 300, tier="premium", image=h[0] if image else "")
    _add("zzcmp-std", "Zzcmp Pillow Standard", 120, tier="standard", image=h[1] if image else "")
    _add("zzcmp-basic", "Zzcmp Pillow Basic", 60, tier="basic", image=h[2] if image else "")


def _jsonld(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def _preconnects(html):
    return re.findall(r'<link rel="preconnect" href="(https://[^"]+)"[^>]*>', html)


def _picture_preconnects(html):
    return [h for h in _preconnects(html) if "fonts.g" not in h]


def _table(html):
    m = re.search(r'<table class="cmp-table".*?</table>', html, re.S)
    return m.group(0) if m else ""


# ------------------------------------------------------------------ every real group
def test_every_group_renders_in_both_languages_in_order(client):
    groups = _groups()
    assert groups, "the seed should contain at least one option group"
    for slug, rows in groups.items():
        for suffix in ("", "?lang=he"):
            r = client.get("/compare/" + slug + suffix)
            assert r.status_code == 200, (slug, suffix)
            html = r.get_data(as_text=True)
            assert "<h1" in html
            table = _table(html)
            assert 'scope="col"' in table and 'scope="row"' in table
            heads = re.findall(r'<th scope="col"[^>]*><a[^>]*href="(/catalog/[^"]+)"', table)
            assert heads == ["/catalog/" + (r["seed_key"] or "item-%d" % r["id"]) for r in rows], slug


def test_index_lists_every_group_and_canonical_rules(client):
    groups = _groups()
    html = client.get("/compare").get_data(as_text=True)
    for slug in groups:
        assert 'href="/compare/%s"' % slug in html
    assert 'rel="canonical"' in html and "noindex" not in html
    g = next(iter(groups))
    h = client.get("/compare/" + g).get_data(as_text=True)
    assert '<link rel="canonical" href="http://localhost/compare/%s">' % g in h
    assert "noindex" not in h
    he = client.get("/compare/" + g + "?lang=he").get_data(as_text=True)
    assert 'rel="canonical" href="http://localhost/compare/%s?lang=he"' % g in he
    # a filtered/extra-param variant is noindex
    assert "noindex" in client.get("/compare/" + g + "?x=1").get_data(as_text=True)


def test_unknown_and_single_groups_404(client):
    assert client.get("/compare/no-such-group").status_code == 404
    _add("zzcmp-solo", "Zzcmp Solo", 50, group="zzcmp-solo")
    assert client.get("/compare/zzcmp-solo").status_code == 404
    _add("zzcmp-gone1", "Zzcmp Gone 1", 50, group="zzcmp-gone")
    _add("zzcmp-gone2", "Zzcmp Gone 2", 60, group="zzcmp-gone", active=0)
    assert client.get("/compare/zzcmp-gone").status_code == 404           # only one active item
    assert 'href="/compare/zzcmp-solo"' not in client.get("/compare").get_data(as_text=True)


def test_sitemap_has_compare_pages(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/compare</loc>" in xml and "/compare?lang=he</loc>" in xml
    for slug in _groups():
        assert "/compare/%s</loc>" % slug in xml and "/compare/%s?lang=he</loc>" % slug in xml


def test_new_group_gets_generic_name_and_intro(client):
    _trio()
    html = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    assert "Zzcmp Pillow: the options compared" in html
    assert "listed from basic to premium" in html
    he = client.get("/compare/zzcmp-pillow?lang=he").get_data(as_text=True)
    assert "האפשרויות זו לצד זו" in he
    pos = [html.index(n) for n in ("Zzcmp Pillow Basic", "Zzcmp Pillow Standard", "Zzcmp Pillow Premium")]
    assert pos == sorted(pos)
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    assert m and len(m.group(1)) <= 155 and "₪60" in m.group(1) and "₪300" in m.group(1)
    assert "compared: options and prices in Israel | OurBayis" in html


def test_every_seed_group_has_name_and_intro_strings():
    import i18n
    for slug in _groups_from_seed():
        for T in (i18n.T_EN, i18n.T_HE):
            assert "cmp_name_" + slug in T and "cmp_intro_" + slug in T, slug


def _groups_from_seed():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed_catalog.json")
    data = json.load(open(path, encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    counts = {}
    for i in items:
        if i.get("option_group") and i.get("active", True):
            counts[i["option_group"]] = counts.get(i["option_group"], 0) + 1
    return [k for k, n in counts.items() if n > 1]


def test_jsonld_parses_without_ratings_or_offers(client):
    _trio()
    html = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    docs = _jsonld(html)
    assert [d["@type"] for d in docs] == ["BreadcrumbList", "ItemList"]
    names = [e["name"] for e in docs[1]["itemListElement"]]
    assert names == ["Zzcmp Pillow Basic", "Zzcmp Pillow Standard", "Zzcmp Pillow Premium"]
    raw = json.dumps(docs).lower()
    for bad in ("rating", "review", "offers", "availability", "price"):
        assert bad not in raw
    assert all(e["url"].startswith("http://localhost/catalog/zzcmp-") for e in docs[1]["itemListElement"])


def test_no_ranking_words_in_added_english_strings():
    import i18n
    for k, v in i18n.T_EN.items():
        if k.startswith("cmp_"):
            assert not re.search(r"\b(best|top|winner|recommended)\b", v, re.I), k
            assert "₪" not in v or k in ("cmp_meta", "cmp_meta_flat", "cmp_range"), k   # no prices in prose


# ------------------------------------------------------------------ add button + back handling
def test_add_form_returns_to_compare_page(client):
    _trio()
    signup(client)
    create_registry(client)
    html = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    assert "/registry/items/add?back=compare&amp;grp=zzcmp-pillow" in html
    db = _db()
    cid = db.execute("SELECT id FROM catalog_items WHERE seed_key='zzcmp-std'").fetchone()[0]
    r = client.post("/registry/items/add?back=compare&grp=zzcmp-pillow",
                    data=dict(csrf_token=get_csrf(html), catalog_id=str(cid)))
    assert r.status_code == 302 and r.headers["Location"].endswith("/compare/zzcmp-pillow")
    again = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    assert again.count("state-added") >= 1


@pytest.mark.parametrize("grp", ["//evil.example", "https://evil.example", "no-such-group", "", "zzcmp-solo"])
def test_bogus_grp_falls_back_safely(client, grp):
    _trio()
    _add("zzcmp-solo", "Zzcmp Solo", 50, group="zzcmp-solo")
    signup(client)
    create_registry(client)
    html = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    cid = _db().execute("SELECT id FROM catalog_items WHERE seed_key='zzcmp-std'").fetchone()[0]
    r = client.post("/registry/items/add", query_string={"back": "compare", "grp": grp},
                    data=dict(csrf_token=get_csrf(html), catalog_id=str(cid)))
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "evil" not in loc and "/compare/" not in loc
    assert loc.startswith("/") or loc.startswith("http://localhost/")


# ------------------------------------------------------------------ links in
def test_item_page_links_to_compare_and_category_lists_groups(client):
    _trio()
    html = client.get("/catalog/zzcmp-std").get_data(as_text=True)
    assert 'href="/compare/zzcmp-pillow"' in html and "Compare side by side" in html
    cat = client.get("/gifts/bedding-and-bath").get_data(as_text=True)
    assert 'href="/compare/zzcmp-pillow"' in cat and "Compare options" in cat
    assert 'href="/compare"' in client.get("/catalog").get_data(as_text=True)


# ------------------------------------------------------------------ preconnect + fetchpriority
def test_preconnect_hosts_limited_ordered_and_without_crossorigin(client):
    _trio(image=True)
    for host in ("a", "b", "c", "d"):
        _add("zzcmp-x" + host, "Zzcmp X " + host, 500, group="zzcmp-many",
             image="https://cdn.%s-host.example/p.jpg" % host)
    html = client.get("/compare/zzcmp-pillow").get_data(as_text=True)
    pre = _picture_preconnects(html)
    assert pre == ["https://ksp.co.il", "https://www.heichal.co.il"]      # most frequent first
    for tag in re.findall(r'<link rel="preconnect"[^>]*>', html):
        if "fonts.gstatic" not in tag:
            assert "crossorigin" not in tag
    many = client.get("/catalog").get_data(as_text=True)
    assert len(_picture_preconnects(many)) <= 4
    assert "ksp.co.il" in many
    no_img = client.get("/compare/zzcmp-many").get_data(as_text=True)
    assert len(_picture_preconnects(no_img)) == 4


def test_item_page_main_picture_is_high_priority_others_lazy(client):
    _trio(image=True)
    html = client.get("/catalog/zzcmp-std").get_data(as_text=True)
    media = re.search(r'<div class="item-media">.*?</div>\s*</div>', html, re.S).group(0)
    img = re.search(r"<img[^>]*>", media).group(0)
    assert 'fetchpriority="high"' in img and "loading" not in img
    assert html.count('fetchpriority="high"') == 1
    assert 'loading="lazy"' in html            # option thumbnails and the rest stay lazy
    assert "fetchpriority" not in client.get("/compare/zzcmp-pillow").get_data(as_text=True)
