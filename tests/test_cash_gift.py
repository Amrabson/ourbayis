# -*- coding: utf-8 -*-
"""The "send a cash gift" dialog (2026-11-10): two numbered steps, pay buttons that show whose account they
open, the guest's own currency preselected, one report per tap, and the couple's email quotes the message."""
import os
import re
import sqlite3

from conftest import create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _registry(client):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/dinayossi', visibility='public'")
    db.commit()
    return db.execute("SELECT slug FROM registries").fetchone()["slug"]


def _cash_form(html):
    return re.search(r'<dialog class="modal" id="cash-modal".*?</dialog>', html, re.S).group(0)


def test_dialog_is_two_steps_and_shows_whose_account(client, app_module):
    slug = _registry(client)
    form = _cash_form(app_module.app.test_client().get(f"/r/{slug}?lang=en").get_data(as_text=True))
    assert 'class="gift-steps cash-steps"' in form
    assert "Send it through the couple&#39;s own link" in form and "Tell them it&#39;s from you" in form
    assert "paypal.me/dinayossi</small>" in form
    assert 'name="form_key"' in form and 'name="message"' in form and 'dir="auto"' in form
    he = _cash_form(app_module.app.test_client().get(f"/r/{slug}?lang=he").get_data(as_text=True))
    assert "שולחים דרך הקישור של הזוג" in he and "לספר להם שזה ממני" in he


def test_currency_follows_what_the_guest_is_browsing_in(client, app_module):
    slug = _registry(client)
    g = app_module.app.test_client()
    with g.session_transaction() as s:
        s["cur"] = "ILS"
    form = _cash_form(g.get(f"/r/{slug}").get_data(as_text=True))
    assert '<option value="ILS" selected>' in form
    with g.session_transaction() as s:
        s["cur"] = "USD"
    form = _cash_form(g.get(f"/r/{slug}").get_data(as_text=True))
    assert '<option value="USD" selected>' in form


def test_double_tap_records_one_gift_and_one_email(client, app_module):
    slug = _registry(client)
    g = app_module.app.test_client()
    page = g.get(f"/r/{slug}").get_data(as_text=True)
    data = dict(csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name="Cousin Dov",
                amount="50", currency="USD", message="Buy something for the sukkah!")
    first = g.post(f"/r/{slug}/cash", data=data)
    second = g.post(f"/r/{slug}/cash", data=data)
    assert first.status_code == second.status_code == 302
    assert first.headers["Location"] == second.headers["Location"]  # both land on the same private page
    db = _db()
    assert db.execute("SELECT COUNT(*) FROM claims WHERE guest_name='Cousin Dov'").fetchone()[0] == 1
    mails = db.execute("SELECT subject, body FROM mail_outbox WHERE to_addr='couple@example.com'").fetchall()
    assert len(mails) == 1
    assert mails[0]["subject"].startswith("Cousin Dov sent you $50")
    assert "“Buy something for the sukkah!”" in mails[0]["body"]
    assert "check your account" in mails[0]["body"]
