# -*- coding: utf-8 -*-
"""/setup-cost: the public itemised cost calculator and its "turn this into a registry" POST."""
import json
import re

import i18n

from conftest import get_csrf, signup, create_registry

GROUPS = ("first_week", "kitchen", "shabbos", "bedbath", "appliances")
PRESET_GROUPS = {
    "minimum": ("first_week",),
    "home": ("first_week", "kitchen", "shabbos", "bedbath"),
    "everything": GROUPS,
}


def _sum(app_module, groups):
    with app_module.app.app_context():
        db = app_module.get_db()
        return sum(db.execute(
            "SELECT COALESCE(SUM(price_nis),0) FROM catalog_items WHERE active=1 AND starter_group=?"
            " AND COALESCE(seed_key,'') NOT IN ('pots-pans-premium-10-piece-set','chef-s-knife-professional')",
            (g,)).fetchone()[0] for g in groups)


def _starter_ids(app_module, limit=None):
    with app_module.app.app_context():
        rows = app_module.get_db().execute(
            "SELECT id FROM catalog_items WHERE active=1 AND starter_group != '' ORDER BY id").fetchall()
    ids = [r[0] for r in rows]
    return ids[:limit] if limit else ids


def _tally(html):
    m = re.search(r'id="starter-tally"[^>]*>([^<]*)<', html)
    return m.group(1) if m else ""


def _post(client, ids, **extra):
    client.get("/setup-cost")
    with client.session_transaction() as s:
        tok = s.get("_csrf")
    data = {f"add_{i}": "1" for i in ids}
    data.update(csrf_token=tok, **extra)
    return client.post("/setup-cost/start", data=data)


def test_page_renders_in_both_languages(client):
    for url in ("/setup-cost", "/setup-cost?lang=he"):
        r = client.get(url)
        assert r.status_code == 200
    assert "What it costs to set up an apartment in Israel" in client.get("/setup-cost?lang=en").get_data(as_text=True)
    assert "כמה עולה להקים דירה בישראל" in client.get("/setup-cost?lang=he").get_data(as_text=True)


def test_default_preset_is_working_home_and_bogus_falls_back(client, app_module):
    expect = f"₪{_sum(app_module, PRESET_GROUPS['home']):,}"
    for url in ("/setup-cost", "/setup-cost?start=bogus"):
        html = client.get(url).get_data(as_text=True)
        assert expect in _tally(html)
        assert re.search(r'aria-checked="true"[^>]*\s+data-setup-preset data-groups="first_week kitchen shabbos bedbath"', html)


def test_each_preset_total_matches_database(client, app_module):
    for key, groups in PRESET_GROUPS.items():
        html = client.get(f"/setup-cost?start={key}").get_data(as_text=True)
        assert f"₪{_sum(app_module, groups):,}" in _tally(html), key
        # the ticked boxes are exactly the preset's groups
        ticked = len(re.findall(r'type="checkbox"[^>]*\bchecked\b', html))
        with app_module.app.app_context():
            n = sum(app_module.get_db().execute(
                "SELECT COUNT(*) FROM catalog_items WHERE active=1 AND starter_group=?"
                " AND COALESCE(seed_key,'') NOT IN ('pots-pans-premium-10-piece-set','chef-s-knife-professional')", (g,)).fetchone()[0]
                for g in groups)
        assert ticked == n, key


def test_noindex_and_canonical(client):
    plain = client.get("/setup-cost").get_data(as_text=True)
    assert 'content="noindex' not in plain
    assert re.search(r'rel="canonical" href="[^"]*/setup-cost"', plain)
    q = client.get("/setup-cost?start=minimum").get_data(as_text=True)
    assert 'content="noindex' in q


def test_in_sitemap(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/setup-cost</loc>" in xml
    assert "/setup-cost?lang=he</loc>" in xml


def test_faq_jsonld_parses(client):
    html = client.get("/setup-cost").get_data(as_text=True)
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    data = [json.loads(b) for b in blocks]
    faq = [d for d in data if d.get("@type") == "FAQPage"][0]
    assert len(faq["mainEntity"]) == 4


def test_packages_listed_with_prices(client, app_module):
    html = client.get("/setup-cost").get_data(as_text=True)
    with app_module.app.app_context():
        bundles = app_module.get_db().execute("SELECT slug, price_from FROM bundles WHERE active=1").fetchall()
    assert bundles
    for b in bundles:
        assert f"₪{b['price_from']:,}" in html
        assert f"#pkg-{b['slug']}" in html


def test_item_names_link_to_catalog_pages(client):
    html = client.get("/setup-cost").get_data(as_text=True)
    assert len(re.findall(r'<a href="/catalog/[^"]+">', html)) >= 40


def test_logged_out_post_queues_then_applies_after_signup(client, app_module):
    ids = _starter_ids(app_module, 3)
    r = _post(client, ids)
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")
    with client.session_transaction() as s:
        assert s["pending_add"] == ids
    signup(client, email="setup@example.com")
    create_registry(client, couple="Setup Couple")
    with app_module.app.app_context():
        got = {r[0] for r in app_module.get_db().execute("SELECT catalog_id FROM registry_items")}
    assert set(ids) <= got


def test_logged_in_post_adds_without_duplicates(client, app_module):
    signup(client, email="li@example.com")
    create_registry(client)
    ids = _starter_ids(app_module, 4)
    r = _post(client, ids[:2])
    assert r.status_code == 302 and "/registry/items" in r.headers["Location"]
    r = _post(client, ids)
    assert r.status_code == 302
    with app_module.app.app_context():
        rows = app_module.get_db().execute(
            "SELECT catalog_id, COUNT(*) FROM registry_items WHERE catalog_id IS NOT NULL GROUP BY catalog_id").fetchall()
    assert sorted(r[0] for r in rows) == sorted(ids)
    assert all(r[1] == 1 for r in rows)


def test_invalid_ids_ignored(client, app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        gone = db.execute("SELECT id FROM catalog_items WHERE active=1 AND starter_group != '' LIMIT 1").fetchone()[0]
        db.execute("UPDATE catalog_items SET active=0 WHERE id=?", (gone,))
        db.commit()
    good = [i for i in _starter_ids(app_module, 2)]
    client.get("/setup-cost")
    with client.session_transaction() as s:
        tok = s.get("_csrf")
    data = {f"add_{gone}": "1", "add_abc": "1", "add_-5": "1", "add_": "1", "add_999999": "1", "csrf_token": tok}
    data.update({f"add_{i}": "1" for i in good})
    r = client.post("/setup-cost/start", data=data)
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert s["pending_add"] == good


def test_pending_cap_respected(client, app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        for i in range(60):
            db.execute("INSERT INTO catalog_items (name, name_he, category, price_nis, active, starter_group)"
                       " VALUES (?,?,?,?,1,'kitchen')", (f"Cap {i}", f"קאפ {i}", "kitchen", 10))
        db.commit()
    ids = _starter_ids(app_module)
    assert len(ids) > 50
    _post(client, ids)
    with client.session_transaction() as s:
        assert len(s["pending_add"]) == 50


def test_csrf_enforced(client, app_module):
    client.get("/setup-cost")
    r = client.post("/setup-cost/start", data={f"add_{_starter_ids(app_module, 1)[0]}": "1", "csrf_token": "nope"})
    assert r.status_code == 400
    with client.session_transaction() as s:
        assert not s.get("pending_add")


def test_honeypot_and_empty_selection_store_nothing(client, app_module):
    ids = _starter_ids(app_module, 2)
    _post(client, ids, website="http://spam.example")
    _post(client, [])
    with client.session_transaction() as s:
        assert not s.get("pending_add")


def test_no_banned_words_in_new_en_strings():
    banned = re.compile(r"shabbat|\bsafe|secure|cheapest|cheaper|best value|saving", re.I)
    for key, val in i18n.T_EN.items():
        if key.startswith("setup_"):
            assert not banned.search(val), key
    assert set(k for k in i18n.T_EN if k.startswith("setup_")) == set(k for k in i18n.T_HE if k.startswith("setup_"))
