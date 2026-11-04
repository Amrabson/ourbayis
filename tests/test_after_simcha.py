# -*- coding: utf-8 -*-
"""After the simcha (2026-11-04): "Mazel tov" once the date passes, a dashboard panel pointing at
thank-you notes, and closing the list (guests see a thank-you; brachos stay open)."""
import os
import sqlite3
from datetime import date, timedelta

from conftest import add_item, create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _set(sql, *args):
    db = _db()
    db.execute(sql, args)
    db.commit()


def _post(client, url, page="/dashboard", **data):
    tok = get_csrf(client.get(page).get_data(as_text=True))
    return client.post(url, data=dict(csrf_token=tok, **data), follow_redirects=True)


def test_after_the_date_registry_says_mazel_tov_and_dashboard_points_to_thanks(client):
    signup(client)
    create_registry(client)
    _set("UPDATE registries SET event_date=?", (date.today() - timedelta(days=3)).isoformat())
    slug = _db().execute("SELECT slug FROM registries").fetchone()["slug"]
    rid = _db().execute("SELECT id FROM registries").fetchone()["id"]
    _set("INSERT INTO claims (registry_id, guest_name, kind, status) VALUES (?,?,?,?)",
         rid, "Aunt Miriam", "cash", "received")
    guest = client.application.test_client()
    assert "Mazel tov! Gifts are still very welcome." in guest.get(f"/r/{slug}?lang=en").get_data(as_text=True)
    dash = client.get("/dashboard?lang=en").get_data(as_text=True)
    assert "The simcha was 3 days ago" in dash
    assert "1 gift is waiting for a thank-you note." in dash
    assert "Close the list" in dash
    he = client.get("/dashboard?lang=he").get_data(as_text=True)
    assert "השמחה הייתה לפני 3 ימים" in he
    # before the date: no panel
    _set("UPDATE registries SET event_date=?", (date.today() + timedelta(days=3)).isoformat())
    assert "The simcha was" not in client.get("/dashboard?lang=en").get_data(as_text=True)


def test_closed_list_shows_a_thank_you_refuses_new_gifts_and_keeps_brachos(client):
    signup(client)
    create_registry(client)
    add_item(client, name="Towels", price_nis="80")
    db = _db()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    item_id = db.execute("SELECT id FROM registry_items").fetchone()["id"]
    _set("UPDATE registries SET paypal_url='https://paypal.me/sarahdovid', visibility='public'")
    r = _post(client, "/registry/close", **{"lang": "en"})
    assert db.execute("SELECT closed_at FROM registries").fetchone()["closed_at"]
    assert "Your gift list is closed" in client.get("/dashboard?lang=en").get_data(as_text=True)

    guest = client.application.test_client()
    page = guest.get(f"/r/{slug}?lang=en").get_data(as_text=True)
    assert "have closed their gift list" in page
    assert "Towels" not in page and 'id="cash-modal"' not in page
    assert 'id="bracha"' in page
    # a stale form still can't reserve or record cash
    r = guest.post(f"/r/{slug}/claim/{item_id}", data=dict(
        csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name="Dov"), follow_redirects=True)
    assert "This gift list is closed" in r.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
    guest.post(f"/r/{slug}/cash", data=dict(csrf_token=get_csrf(page), guest_name="Dov", amount="100"))
    assert db.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
    # brachos still arrive
    guest.post(f"/r/{slug}/bracha", data=dict(csrf_token=get_csrf(page), form_key=get_form_key(page),
                                              guest_name="Dov", message="Mazel tov!"))
    assert db.execute("SELECT COUNT(*) FROM brachos").fetchone()[0] == 1
    # out of the sitemap, tagged in /find
    assert f"/r/{slug}" not in guest.get("/sitemap.xml").get_data(as_text=True)
    assert "Gift list closed" in guest.get("/find?q=Sarah&lang=en").get_data(as_text=True)

    # reopen from the edit page
    r = _post(client, "/registry/reopen", page="/registry/edit", back="edit")
    assert r.request.path == "/registry/edit"
    assert db.execute("SELECT closed_at FROM registries").fetchone()["closed_at"] is None
    assert "Towels" in guest.get(f"/r/{slug}?lang=en").get_data(as_text=True)
