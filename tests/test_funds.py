# -*- coding: utf-8 -*-
"""Cash funds (2026-11-12): "Sefarim fund" is a custom chip-in item with no store link, made in one step."""
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from conftest import create_registry, get_csrf, get_form_key, signup  # noqa: E402
from test_people import _invite, _join  # noqa: E402


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _couple(client, pay=True, public=True):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    db = _db()
    if pay:
        db.execute("UPDATE registries SET paypal_url='https://paypal.me/dinayossi'")
    if public:
        db.execute("UPDATE registries SET visibility='public'")
    db.commit()
    return db.execute("SELECT slug FROM registries").fetchone()["slug"]


def _fund(client, name="Sefarim fund", goal="3000", note="For our first shelf", lang=None):
    page = client.get("/registry/items" + (f"?lang={lang}" if lang else "")).get_data(as_text=True)
    return client.post("/registry/items/fund", data=dict(
        csrf_token=get_csrf(page), name=name, goal=goal, note=note))


def _items():
    return _db().execute("SELECT * FROM registry_items").fetchall()


def test_fund_creates_a_chip_in_item(client):
    _couple(client)
    r = _fund(client)
    assert r.status_code == 302
    (it,) = _items()
    assert (it["name"], it["price_nis"], it["chip_in"], it["qty_wanted"], it["url"], it["kind"]) == \
        ("Sefarim fund", 3000, 1, 1, "", "idea")
    assert it["category"] == "home" and it["variant"] == "For our first shelf" and not it["note"]


def test_fund_form_and_chips_on_the_items_page(client):
    _couple(client)
    page = client.get("/registry/items").get_data(as_text=True)
    assert 'action="/registry/items/fund"' in page and 'id="fund-name"' in page
    for name in ("Furniture fund", "Sefarim fund", "Appliances fund", "Settling in fund"):
        assert f'data-fill-value="{name}"' in page
    he = client.get("/registry/items?lang=he").get_data(as_text=True)
    assert "הוספת קרן" in he and 'data-fill-value="קרן ספרים"' in he


def test_fund_refused_without_a_pay_link(client):
    _couple(client, pay=False)
    r = _fund(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/registry/edit#rf-payment")
    assert "needs a payment link" in client.get("/registry/edit").get_data(as_text=True)
    assert _items() == []
    assert "needs a payment link" in client.get("/registry/items").get_data(as_text=True)


def test_fund_goal_validation(client):
    _couple(client)
    for bad in ("", "99", "100000", "12.5", "-300", "abc"):
        r = _fund(client, goal=bad)
        assert r.status_code == 302 and r.headers["Location"].endswith("/registry/items#fund"), bad
    assert _items() == []
    assert "whole number of shekels" in client.get("/registry/items").get_data(as_text=True)
    _fund(client, name="  ", goal="500")
    assert _items() == []
    for ok in ("100", "99999"):
        _fund(client, name="Fund " + ok, goal=ok)
    assert sorted(i["price_nis"] for i in _items()) == [100, 99999]


def test_fund_needs_login_and_csrf(client):
    assert client.post("/registry/items/fund", data={}).status_code in (302, 400)
    _couple(client)
    r = client.post("/registry/items/fund", data=dict(name="X fund", goal="500"))
    assert r.status_code in (302, 400, 403) and _items() == []


def test_fund_is_a_chip_in_card_on_the_public_page_and_a_guest_can_chip_in(client, app_module):
    slug = _couple(client)
    _fund(client, name="Furniture fund", goal="2000", note="")
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert "Furniture fund" in html and "Chip in" in html
    assert "/go/i/" not in html and "buy at the store" not in html.lower()
    assert "ill-boxes" in html
    item_id = _items()[0]["id"]
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/claim/{item_id}", data=dict(
        csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name="Cousin Dov",
        give="chip", chip_amount="150"))
    assert r.status_code == 302 and "/g/" in r.headers["Location"]
    (c,) = _db().execute("SELECT * FROM claims WHERE kind='chip'").fetchall()
    assert c["amount_minor"] == 15000
    assert "₪150" in app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)


def test_fund_renders_in_hebrew_on_the_public_page(client, app_module):
    slug = _couple(client)
    _fund(client, name="קרן ספרים", goal="1800", note="")
    he = app_module.app.test_client().get(f"/r/{slug}?lang=he").get_data(as_text=True)
    assert "קרן ספרים" in he and "ill-boxes" in he and "/go/i/" not in he


def test_helper_can_add_a_fund(app):
    owner = app.test_client()
    signup(owner, email="rivka@example.com", name="Rivka")
    create_registry(owner, couple="Rivka & Yosef")
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/rivkayosef'")
    db.commit()
    helper = _join(app, _invite(owner))
    assert _fund(helper, name="Appliances fund", goal="4000").status_code == 302
    (it,) = _items()
    assert it["name"] == "Appliances fund" and it["chip_in"] == 1


def test_list_check_suggests_a_fund_until_there_is_a_chip_in_item(client):
    _couple(client)
    from conftest import add_item
    add_item(client, name="Hand towels", price_nis="80", url="https://example.com/towels")
    html = client.get("/registry/check").get_data(as_text=True)
    assert "Add a fund for the big things" in html and "/registry/items#fund" in html
    assert "הוסיפו קרן" in client.get("/registry/check?lang=he").get_data(as_text=True)
    _fund(client)
    assert "Add a fund for the big things" not in client.get("/registry/check").get_data(as_text=True)


def test_list_check_has_no_fund_suggestion_without_a_pay_link(client):
    _couple(client, pay=False)
    from conftest import add_item
    add_item(client, name="Hand towels", price_nis="80", url="https://example.com/towels")
    assert "Add a fund for the big things" not in client.get("/registry/check").get_data(as_text=True)


# ------------------------------------------------------------------ refresh-registry-links vs chip-ins
def test_refresh_registry_links_keeps_price_below_chipped_in_amount(client, app_module):
    import ob_db
    signup(client)
    create_registry(client)
    with app_module.app.app_context():
        db = app_module.get_db()
        cs = db.execute("SELECT * FROM catalog_items WHERE active=1 AND url='' LIMIT 2").fetchall()
        reg = db.execute("SELECT * FROM registries LIMIT 1").fetchone()
        ids = []
        for c in cs:
            with ob_db.write_txn(db):
                app_module._insert_registry_item_from_catalog(db, reg["id"], c)
            ids.append(db.execute("SELECT id FROM registry_items WHERE catalog_id=?", (c["id"],)).fetchone()[0])
        with ob_db.write_txn(db):
            for rid, c in zip(ids, cs):
                db.execute("UPDATE registry_items SET price_nis=1000, chip_in=1, qty_wanted=1, url=? WHERE id=?",
                           ("https://old.example/" + str(rid), rid))
                db.execute("UPDATE catalog_items SET url=?, price_nis=400, store='New Store' WHERE id=?",
                           ("https://new.example/" + str(c["id"]), c["id"]))
            # item 0: 600 shekels chipped in (400 is below that); item 1: only 300 (400 is fine)
            for rid, minor, status in ((ids[0], 40000, "received"), (ids[0], 20000, "reserved"),
                                       (ids[0], 90000, "cancelled"), (ids[1], 30000, "reported")):
                db.execute("INSERT INTO claims (registry_id, item_id, guest_name, kind, qty, amount_minor, status)"
                           " VALUES (?,?,?,?,?,?,?)", (reg["id"], rid, "Dov", "chip", 0, minor, status))
        notes = []
        with ob_db.write_txn(db):
            dry = ob_db.refresh_registry_links(db, dry_run=True, notes=notes)
        assert len(notes) == 1 and f"item {ids[0]} " in notes[0]
        assert not any(d[0] == ids[0] and d[1] == "price_nis" for d in dry)
        assert any(d[0] == ids[1] and d[1] == "price_nis" for d in dry)
        assert db.execute("SELECT price_nis FROM registry_items WHERE id=?", (ids[1],)).fetchone()[0] == 1000
        notes = []
        with ob_db.write_txn(db):
            ob_db.refresh_registry_links(db, notes=notes)
        funded, other = (db.execute("SELECT * FROM registry_items WHERE id=?", (i,)).fetchone() for i in ids)
        assert funded["price_nis"] == 1000 and funded["url"] == "https://new.example/" + str(cs[0]["id"])
        assert funded["store"] == "New Store"
        assert other["price_nis"] == 400
