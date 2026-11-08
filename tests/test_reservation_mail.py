# -*- coding: utf-8 -*-
"""Reservation emails (2026-11-08): the couple gets the guest's message; the guest gets the store link and
the delivery address in the email itself, so they can order from it."""
import os
import sqlite3

from conftest import add_item, create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _reserve(client, app_module, delivery_note="Nachal Dolev 12, Ramat Beit Shemesh", lang="en"):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    add_item(client, name="Electric kettle", price_nis="64", url="https://ksp.co.il/item/1")
    db = _db()
    db.execute("UPDATE registries SET delivery_note=?", (delivery_note,))
    db.execute("UPDATE registry_items SET store='KSP'")
    db.commit()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    item_id = db.execute("SELECT id FROM registry_items").fetchone()["id"]
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}?lang={lang}").get_data(as_text=True)
    guest.post(f"/r/{slug}/claim/{item_id}?lang={lang}", data=dict(
        csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name="Aunt Malka",
        guest_email="malka@example.com", message="Mazel tov from all of us!", give="buy"))
    return item_id, {r["to_addr"]: r for r in db.execute("SELECT * FROM mail_outbox")}


def test_couple_email_says_who_what_and_quotes_the_message(client, app_module):
    _, mail = _reserve(client, app_module)
    couple = mail["couple@example.com"]
    assert couple["subject"] == "Aunt Malka reserved Electric kettle"
    assert "“Mazel tov from all of us!”" in couple["body"]


def test_guest_email_carries_the_store_link_and_address(client, app_module):
    item_id, mail = _reserve(client, app_module)
    body = mail["malka@example.com"]["body"]
    assert f"/go/i/{item_id}" in body and "order it from KSP" in body
    assert "Have it delivered to:\nNachal Dolev 12, Ramat Beit Shemesh" in body


def test_guest_email_without_an_address_says_to_ask(client, app_module):
    _, mail = _reserve(client, app_module, delivery_note="")
    assert "hasn't added a delivery address yet" in mail["malka@example.com"]["body"]
