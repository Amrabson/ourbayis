# -*- coding: utf-8 -*-
"""Share kit (2026-11-04): ready-made messages in English and Hebrew, each opening the registry
in its own language, with WhatsApp / email / copy; cash mention and reminder only when they apply."""
import html
import os
import sqlite3
from datetime import date, timedelta

from conftest import create_registry, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def test_share_kit_messages_link_to_their_own_language(client):
    signup(client)
    create_registry(client, couple="Sarah & Dovid")
    db = _db()
    db.execute("UPDATE registries SET couple_names_he='שרה ודוד'")
    db.commit()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    page = html.unescape(client.get("/registry/share?lang=en").get_data(as_text=True))
    assert "Send your list" in page
    # English messages first, Hebrew folded below; each language links to its own page
    assert page.index("Hi everyone!") < page.index("שלום לכולם!")
    assert f"/r/{slug}\n" in page and f"/r/{slug}?lang=he\n" in page
    assert "Sarah & Dovid" in page and "שרה ודוד" in page
    # WhatsApp and email carry the same text
    assert "wa.me/?text=Our%20gift%20list%3A%20http" in page.replace("+", "%20")
    assert "mailto:?subject=Our%20gift%20list&body=" in page
    # no payment link, no date: no cash line, no reminder
    assert "gift of money" not in page and "the simcha is in" not in page
    he = client.get("/registry/share?lang=he").get_data(as_text=True)
    assert he.index("שלום לכולם!") < he.index("Hi everyone!")


def test_cash_line_and_reminder_appear_only_when_they_apply(client):
    signup(client)
    create_registry(client)
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/sarahdovid', event_date=?",
               ((date.today() + timedelta(days=20)).isoformat(),))
    db.commit()
    page = client.get("/registry/share?lang=en").get_data(as_text=True)
    assert "a gift of money" in page
    assert "the simcha is in 20 days" in page
    db.execute("UPDATE registries SET event_date=?", ((date.today() + timedelta(days=2)).isoformat(),))
    db.commit()
    assert "the simcha is in" not in client.get("/registry/share?lang=en").get_data(as_text=True)


def test_share_kit_is_couple_only_and_warns_on_a_draft(client):
    assert client.get("/registry/share").status_code == 302  # login
    signup(client)
    assert "/registry/new" in client.get("/registry/share").headers["Location"]
    create_registry(client)
    db = _db()
    db.execute("UPDATE registries SET visibility='draft'")
    db.commit()
    page = client.get("/registry/share?lang=en").get_data(as_text=True)
    assert "still a draft" in page
    assert "/registry/share" in client.get("/dashboard?lang=en").get_data(as_text=True)
