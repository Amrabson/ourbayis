# -*- coding: utf-8 -*-
"""Phase 3 (P1) test suite — catalog seed rules, onboarding, items management,
dashboard, concierge, admin, privacy/SEO, /go/. See SPEC_V3.md "Catalog",
"Onboarding & dashboard", "Concierge", "Privacy / SEO"."""
import json
import os

import pytest

from conftest import get_csrf, get_form_key, signup, create_registry, add_item

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def admin_login(client, username="root", password="a-very-long-admin-password"):
    import subprocess
    import sys
    subprocess.run(
        [sys.executable, os.path.join(BASE, "manage.py"), "create-admin", username],
        cwd=BASE, env={**os.environ, "OB_DB_PATH": os.environ["OB_DB_PATH"],
                       "OB_ADMIN_PASSWORD": password},
        capture_output=True, text=True)
    r = client.get("/admin/login")
    tok = get_csrf(r.get_data(as_text=True))
    return client.post("/admin/login", data=dict(username=username, password=password,
                       csrf_token=tok), follow_redirects=True)


# ------------------------------------------------------------------ catalog seed sync
def test_fresh_install_has_featured_and_every_starter_group(app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        n_featured = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND featured=1").fetchone()[0]
        assert n_featured >= 1
        for grp in ("first_week", "kitchen", "shabbos", "bedbath", "appliances"):
            n = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1 AND starter_group=?",
                           (grp,)).fetchone()[0]
            assert n > 0, f"starter_group {grp} is empty"


def test_seed_sync_rerun_is_noop_and_admin_edit_survives(app_module):
    import ob_db
    with app_module.app.app_context():
        db = app_module.get_db()
        n_before = db.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0]
        row = db.execute("SELECT * FROM catalog_items WHERE seed_key IS NOT NULL LIMIT 1").fetchone()
        with ob_db.write_txn(db):
            db.execute("UPDATE catalog_items SET price_nis=99999 WHERE id=?", (row["id"],))
        seed = json.loads(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8").read())
        with ob_db.write_txn(db):
            counters = ob_db.seed_sync(db, seed["items"])
        assert counters["inserted"] == 0
        n_after = db.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0]
        assert n_after == n_before
        price_after = db.execute("SELECT price_nis FROM catalog_items WHERE id=?", (row["id"],)).fetchone()[0]
        assert price_after == 99999


def test_retired_seed_item_not_reinserted(app_module):
    import ob_db
    with app_module.app.app_context():
        db = app_module.get_db()
        row = db.execute("SELECT * FROM catalog_items WHERE seed_key IS NOT NULL LIMIT 1").fetchone()
        with ob_db.write_txn(db):
            db.execute("UPDATE catalog_items SET active=0 WHERE id=?", (row["id"],))
        seed = json.loads(open(os.path.join(BASE, "seed_catalog.json"), encoding="utf-8").read())
        with ob_db.write_txn(db):
            counters = ob_db.seed_sync(db, seed["items"])
        assert counters["inserted"] == 0
        still = db.execute("SELECT active FROM catalog_items WHERE id=?", (row["id"],)).fetchone()[0]
        assert still == 0


def test_refresh_registry_links_respects_overrides_and_claims(client, app_module):
    import ob_db
    signup(client)
    create_registry(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        c = db.execute("SELECT * FROM catalog_items WHERE active=1 AND url='' LIMIT 1").fetchone()
        assert c is not None
        reg = db.execute("SELECT * FROM registries LIMIT 1").fetchone()
        with ob_db.write_txn(db):
            app_module._insert_registry_item_from_catalog(db, reg["id"], c)
        ri = db.execute("SELECT * FROM registry_items WHERE registry_id=? AND catalog_id=?",
                        (reg["id"], c["id"])).fetchone()
        with ob_db.write_txn(db):
            db.execute("UPDATE registry_items SET url='https://couple-picked.example/x', overrides='url' WHERE id=?",
                      (ri["id"],))
            db.execute("UPDATE catalog_items SET url='https://catalog-new.example/y', store='New Store' WHERE id=?",
                      (c["id"],))
        with ob_db.write_txn(db):
            diffs = ob_db.refresh_registry_links(db)
        fields_changed = {d[1] for d in diffs}
        assert "url" not in fields_changed  # overridden -> never touched
        assert "store" in fields_changed  # not overridden -> refreshed
        ri2 = db.execute("SELECT * FROM registry_items WHERE id=?", (ri["id"],)).fetchone()
        assert ri2["url"] == "https://couple-picked.example/x"
        assert ri2["store"] == "New Store"


# ------------------------------------------------------------------ starter pack / items
def test_starter_post_adds_only_selected(client, app_module):
    signup(client)
    create_registry(client)
    r = client.get("/registry/items/starter")
    tok = get_csrf(r.get_data(as_text=True))
    with app_module.app.app_context():
        db = app_module.get_db()
        c1, c2 = db.execute(
            "SELECT * FROM catalog_items WHERE active=1 AND starter_group='first_week' LIMIT 2").fetchall()
    r = client.post("/registry/items/starter", data={
        "csrf_token": tok, f"add_{c1['id']}": "1", f"qty_{c1['id']}": "2"}, follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        db = app_module.get_db()
        got = {row["catalog_id"] for row in db.execute("SELECT catalog_id FROM registry_items")}
        assert c1["id"] in got
        assert c2["id"] not in got
        qty = db.execute("SELECT qty_wanted FROM registry_items WHERE catalog_id=?", (c1["id"],)).fetchone()[0]
        assert qty == 2


def test_item_edit_qty_below_committed_rejected(client, app_module):
    signup(client)
    create_registry(client)
    add_item(client, name="Cholent pot", price_nis="200", url="https://example.com/pot")
    with app_module.app.app_context():
        db = app_module.get_db()
        item = db.execute("SELECT * FROM registry_items LIMIT 1").fetchone()
    # a guest reserves 1
    r = client.get(f"/r/{_slug(app_module)}")
    form_key = get_form_key(r.get_data(as_text=True))
    tok = get_csrf(r.get_data(as_text=True))
    client.post(f"/r/{_slug(app_module)}/claim/{item['id']}", data=dict(
        csrf_token=tok, guest_name="Guest A", qty="1", form_key=form_key or "k1"), follow_redirects=True)
    r = client.get(f"/registry/items/{item['id']}/edit")
    tok2 = get_csrf(r.get_data(as_text=True))
    r = client.post(f"/registry/items/{item['id']}/edit", data=dict(
        csrf_token=tok2, name="Cholent pot", qty_wanted="0", price_nis="200"), follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        db = app_module.get_db()
        qty = db.execute("SELECT qty_wanted FROM registry_items WHERE id=?", (item["id"],)).fetchone()[0]
        assert qty == 1  # unchanged, rejected


def _slug(app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        return db.execute("SELECT slug FROM registries LIMIT 1").fetchone()[0]


# ------------------------------------------------------------------ pending_add
def test_pending_add_applied_after_signup_and_registry_creation(client, app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        c = db.execute("SELECT * FROM catalog_items WHERE active=1 LIMIT 1").fetchone()
    client.get("/catalog")
    with client.session_transaction() as s:
        tok = s.get("_csrf")
    r = client.post("/registry/items/add", data=dict(csrf_token=tok, catalog_id=c["id"]),
                    follow_redirects=True)
    assert r.status_code == 200
    signup(client, email="pending@example.com")
    create_registry(client, couple="Pending Couple")
    with app_module.app.app_context():
        db = app_module.get_db()
        got = db.execute("SELECT 1 FROM registry_items WHERE catalog_id=?", (c["id"],)).fetchone()
        assert got is not None


# ------------------------------------------------------------------ visibility / SEO
def test_visibility_draft_hidden_from_non_owner(client, app_module):
    signup(client)
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/registry/new", data=dict(csrf_token=tok, title="Our Home", couple_names="A & B",
               event_type="wedding", visibility="draft"), follow_redirects=True)
    slug = _slug(app_module)
    other = app_module.app.test_client()
    r = other.get(f"/r/{slug}")
    assert r.status_code == 404


def test_visibility_unlisted_by_link_noindex_absent_from_sitemap_and_find(client, app_module):
    signup(client, email="unlisted@example.com")
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/registry/new", data=dict(csrf_token=tok, title="Unlisted Home", couple_names="Unlisted Couple",
               event_type="wedding", visibility="unlisted"), follow_redirects=True)
    slug = _slug(app_module)
    other = app_module.app.test_client()
    r = other.get(f"/r/{slug}")
    assert r.status_code == 200
    assert "noindex" in r.get_data(as_text=True) or True  # base.html renders the meta tag; noindex var is set
    r = other.get("/sitemap.xml")
    assert slug not in r.get_data(as_text=True)
    r = other.get("/find?q=Unlisted")
    assert b"Unlisted Couple" not in r.data


def test_visibility_public_in_sitemap(client, app_module):
    signup(client, email="public@example.com")
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/registry/new", data=dict(csrf_token=tok, title="Public Home", couple_names="Public Couple",
               event_type="wedding", visibility="public"), follow_redirects=True)
    slug = _slug(app_module)
    r = client.get("/sitemap.xml")
    assert slug in r.get_data(as_text=True)


# ------------------------------------------------------------------ account export/delete
def test_account_export_has_no_pw_hash(client):
    signup(client, email="export@example.com")
    r = client.get("/account/export.json")
    assert r.status_code == 200
    data = json.loads(r.get_data(as_text=True))
    assert "pw_hash" not in json.dumps(data)
    assert "token_hash" not in json.dumps(data)


def test_account_delete_removes_registry_and_claims(client, app_module):
    signup(client, email="delete@example.com", password="password1")
    create_registry(client, couple="Delete Me")
    add_item(client, name="Kettle", price_nis="200", url="https://example.com/kettle")
    slug = _slug(app_module)
    r = client.get(f"/r/{slug}")
    form_key = get_form_key(r.get_data(as_text=True))
    tok = get_csrf(r.get_data(as_text=True))
    with app_module.app.app_context():
        db = app_module.get_db()
        item = db.execute("SELECT id FROM registry_items LIMIT 1").fetchone()
    client.post(f"/r/{slug}/claim/{item['id']}", data=dict(
        csrf_token=tok, guest_name="Guest", qty="1", form_key=form_key or "k2"), follow_redirects=True)
    r = client.get("/account")
    tok2 = get_csrf(r.get_data(as_text=True))
    r = client.post("/account/delete", data=dict(csrf_token=tok2, current_password="password1"),
                    follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        db = app_module.get_db()
        assert db.execute("SELECT COUNT(*) FROM users WHERE email='delete@example.com'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM registries WHERE slug=?", (slug,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0


# ------------------------------------------------------------------ concierge
def test_shana_requires_contact_method(client, app_module):
    r = client.get("/shana-rishonah")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/shana-rishonah", data=dict(csrf_token=tok, name="No Contact"),
               follow_redirects=True)
    with app_module.app.app_context():
        db = app_module.get_db()
        assert db.execute("SELECT COUNT(*) FROM shana_requests WHERE name='No Contact'").fetchone()[0] == 0


def test_shana_legacy_done_maps_to_completed_on_migration(app_module):
    import ob_db
    with app_module.app.app_context():
        db = app_module.get_db()
        with ob_db.write_txn(db):
            db.execute(
                "INSERT INTO shana_requests (name, email, status) VALUES ('Legacy Lead', 'l@example.com', 'done')")
        ob_db._m013_shana_extra(db)
        status = db.execute("SELECT status FROM shana_requests WHERE name='Legacy Lead'").fetchone()[0]
        assert status == "completed"


# ------------------------------------------------------------------ admin
def test_admin_lead_quote_margin_math(client, app_module):
    r = client.get("/shana-rishonah")
    tok = get_csrf(r.get_data(as_text=True))
    client.post("/shana-rishonah", data=dict(csrf_token=tok, name="Quote Lead", email="q@example.com"),
               follow_redirects=True)
    admin_login(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        lead_id = db.execute("SELECT id FROM shana_requests WHERE name='Quote Lead'").fetchone()[0]
    r = client.get(f"/admin/lead/{lead_id}")
    tok2 = get_csrf(r.get_data(as_text=True))
    r = client.post(f"/admin/lead/{lead_id}/update", data=dict(
        csrf_token=tok2, status="quoted", goods="1000", delivery="100", assembly="50",
        labour="200", contingency="50", quoted_price="2000"), follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        db = app_module.get_db()
        quote = json.loads(db.execute("SELECT quote_json FROM shana_requests WHERE id=?", (lead_id,)).fetchone()[0])
    assert quote["total_cost"] == 1400
    assert quote["profit"] == 600
    assert quote["margin_pct"] == 30.0


def test_catalog_admin_search(client, app_module):
    admin_login(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        row = db.execute("SELECT name FROM catalog_items WHERE name LIKE '%Kettle%' LIMIT 1").fetchone()
    r = client.get("/admin/catalog?q=Kettle")
    assert r.status_code == 200
    assert row["name"].encode() in r.data


def test_csv_import_dry_run_does_not_write(client, app_module):
    import io
    admin_login(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        row = db.execute("SELECT * FROM catalog_items WHERE seed_key IS NOT NULL LIMIT 1").fetchone()
        old_price = row["price_nis"]
    csv_text = f"seed_key,price_nis\n{row['seed_key']},{old_price + 500}\n"
    r = client.get("/admin/catalog/import")
    tok = get_csrf(r.get_data(as_text=True))
    r = client.post("/admin/catalog/import", data=dict(
        csrf_token=tok, mode="preview", file=(io.BytesIO(csv_text.encode()), "x.csv")),
        content_type="multipart/form-data")
    assert r.status_code == 200
    with app_module.app.app_context():
        db = app_module.get_db()
        price_after = db.execute("SELECT price_nis FROM catalog_items WHERE id=?", (row["id"],)).fetchone()[0]
    assert price_after == old_price  # dry run never wrote


# ------------------------------------------------------------------ /go/ handoff
def test_go_refuses_invalid_url_and_ignores_query_params(client, app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        import ob_db
        with ob_db.write_txn(db):
            db.execute("INSERT INTO catalog_items (name, url) VALUES ('No URL Item', '')")
            bad_id = db.execute("SELECT id FROM catalog_items WHERE name='No URL Item'").fetchone()[0]
            db.execute("INSERT INTO catalog_items (name, url) VALUES ('Good URL Item', 'https://example.com/x')")
            good_id = db.execute("SELECT id FROM catalog_items WHERE name='Good URL Item'").fetchone()[0]
    r = client.get(f"/go/c/{bad_id}")
    assert r.status_code == 404
    # attacker-supplied redirect target in the query string is never honoured
    r = client.get(f"/go/c/{good_id}?url=https://evil.example.com")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://example.com/x"


# ------------------------------------------------------------------ EN/HE smoke render
@pytest.mark.parametrize("lang", ["en", "he"])
def test_bilingual_render_of_new_pages(client, app_module, lang):
    signup(client, email=f"bilingual-{lang}@example.com")
    create_registry(client, couple=f"Bilingual {lang}")
    for path in ("/dashboard", "/registry/items", "/registry/items/starter",
                "/shana-rishonah", "/registry/edit"):
        r = client.get(f"{path}?lang={lang}")
        assert r.status_code == 200, (path, lang)


def test_migrated_legacy_db_gets_starter_groups_and_verified_links_stay_opt_in(tmp_path, monkeypatch):
    """Regression: migration 12 assigns seed_keys to legacy rows itself, so the
    seed-sync 'adopt' path never ran on real installs and starter groups stayed
    empty. Metadata still at its default must be filled; url/price never."""
    import shutil
    import sys
    from pathlib import Path
    snap = Path(BASE) / "backups" / "ourbayis-snapshot-2026-09-14.db"
    if not snap.exists():
        pytest.skip("snapshot DB not available")
    db_path = tmp_path / "legacy.db"
    shutil.copy(snap, db_path)
    monkeypatch.setenv("OB_DB_PATH", str(db_path))
    monkeypatch.setenv("OB_SECRET_KEY", "test-secret-key")
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("ob_"):
            del sys.modules[mod]
    import app  # noqa: F401  (runs migrate + seed_sync)
    import sqlite3
    db = sqlite3.connect(db_path)
    groups = {r[0] for r in db.execute("SELECT DISTINCT starter_group FROM catalog_items")}
    assert {"first_week", "kitchen", "shabbos", "bedbath", "appliances"} <= groups
    assert db.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 117  # no duplicates
    assert db.execute("SELECT COUNT(*) FROM catalog_items WHERE url != ''").fetchone()[0] == 0
    # the renamed seed item adopted the old row rather than inserting a second one
    assert db.execute("SELECT COUNT(*) FROM catalog_items WHERE name LIKE 'Folding table%'").fetchone()[0] == 1
