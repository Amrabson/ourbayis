# -*- coding: utf-8 -*-
"""Brachos (2026-11-03): guests leave the couple a wish without a gift; only the couple reads them
(email, thank-you page, keepsake), never the registry page."""
import json
import os
import sqlite3

from conftest import create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _slug():
    return _db().execute("SELECT slug FROM registries").fetchone()["slug"]


def _leave(guest, slug, form_key=None, **data):
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    return guest.post(f"/r/{slug}/bracha", data=dict(
        csrf_token=get_csrf(page), form_key=form_key or get_form_key(page), **data))


def test_guest_leaves_a_bracha_and_only_the_couple_reads_it(client, app):
    signup(client)
    create_registry(client)
    slug = _slug()
    guest = app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    assert "Leave them a bracha" in page and f'action="/r/{slug}/bracha"' in page

    r = _leave(guest, slug, guest_name="Aunt Miriam", message="May your home be full of simchas!")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/r/{slug}?bracha=sent#bracha")
    page = guest.get(f"/r/{slug}?bracha=sent").get_data(as_text=True)
    assert "Your bracha is on its way" in page
    assert "May your home be full of simchas" not in page   # never shown on the registry

    db = _db()
    mail = db.execute("SELECT * FROM mail_outbox ORDER BY id DESC").fetchone()
    assert mail["to_addr"] == "a@b.com" and "Aunt Miriam" in mail["subject"]
    assert "May your home be full of simchas!" in mail["body"]

    thanks = client.get("/dashboard/thanks").get_data(as_text=True)
    assert "1 bracha" in thanks and "May your home be full of simchas!" in thanks
    assert "1 bracha" in client.get("/dashboard").get_data(as_text=True)
    assert "May your home be full of simchas!" in client.get("/dashboard/keepsake").get_data(as_text=True)
    assert json.loads(client.get("/account/export.json").get_data(as_text=True))["brachos"][0]["guest_name"] == "Aunt Miriam"
    # the couple sees a note instead of the form on their own page
    own = client.get(f"/r/{slug}").get_data(as_text=True)
    assert "Read your brachos" in own and f'action="/r/{slug}/bracha"' not in own

    bid = db.execute("SELECT id FROM brachos").fetchone()["id"]
    client.post(f"/dashboard/brachos/{bid}/delete", data=dict(csrf_token=get_csrf(thanks)))
    assert _db().execute("SELECT COUNT(*) FROM brachos").fetchone()[0] == 0


def test_double_submit_is_one_bracha_and_bad_input_none(client, app):
    signup(client)
    create_registry(client)
    slug = _slug()
    guest = app.test_client()
    _leave(guest, slug, form_key="k1", guest_name="Dov", message="Mazel tov")
    _leave(guest, slug, form_key="k1", guest_name="Dov", message="Mazel tov")
    _leave(guest, slug, guest_name="", message="no name")
    _leave(guest, slug, guest_name="No message", message="   ")
    _leave(guest, slug, guest_name="Bot", message="spam", website="http://spam")
    assert [r["guest_name"] for r in _db().execute("SELECT guest_name FROM brachos")] == ["Dov"]


def test_draft_registries_take_no_brachos_and_others_cant_delete(client, app):
    signup(client)
    create_registry(client)
    slug = _slug()
    _leave(app.test_client(), slug, guest_name="Dov", message="Mazel tov")
    bid = _db().execute("SELECT id FROM brachos").fetchone()["id"]

    other = app.test_client()
    signup(other, email="other@b.com")
    create_registry(other, title="Their Home")
    page = other.get("/dashboard/thanks").get_data(as_text=True)
    assert "Mazel tov" not in page
    assert other.post(f"/dashboard/brachos/{bid}/delete", data=dict(csrf_token=get_csrf(page))).status_code == 404

    db = _db()
    db.execute("UPDATE registries SET visibility='draft' WHERE slug=?", (slug,))
    db.commit()
    guest = app.test_client()
    page = guest.get("/contact").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/bracha", data=dict(csrf_token=get_csrf(page), guest_name="X", message="Y"))
    assert r.status_code == 404


def test_bracha_is_bilingual(client, app):
    signup(client)
    create_registry(client)
    slug = _slug()
    he = app.test_client().get(f"/r/{slug}?lang=he").get_data(as_text=True)
    assert "השאירו להם ברכה" in he and "שליחת הברכה" in he
    assert "ברכות" in client.get("/dashboard/thanks?lang=he").get_data(as_text=True)
