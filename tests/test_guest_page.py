# -*- coding: utf-8 -*-
"""The guest's private gift page (2026-11-10): a store gift still to buy is three numbered steps (order it,
where to send it with a copy button, tell the couple), with the simcha date, the guest's own message, and a
heads-up when the simcha is close."""
import os
import sqlite3
from datetime import date, timedelta

import pytest

from conftest import add_item, create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _reserve(client, app_module, give="buy", days_away=40, address="Nachal Dolev 12, Ramat Beit Shemesh"):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    add_item(client, name="Electric kettle", price_nis="64", url="https://ksp.co.il/item/1")
    db = _db()
    db.execute("UPDATE registries SET delivery_note=?, event_date=?, paypal_url='https://paypal.me/dinayossi'",
               (address, (date.today() + timedelta(days=days_away)).isoformat()))
    db.execute("UPDATE registry_items SET store='KSP'")
    db.commit()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    item_id = db.execute("SELECT id FROM registry_items").fetchone()["id"]
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/claim/{item_id}", data=dict(
        csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name="Aunt Malka",
        message="Mazel tov from all of us!", give=give))
    token = r.headers["Location"].rsplit("/", 1)[-1]
    return guest, token


def test_store_gift_is_three_steps_with_the_address_to_copy(client, app_module):
    guest, token = _reserve(client, app_module)
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert 'class="gift-steps"' in html and "Order it from KSP" in html and "Tell the couple it&#39;s on its way" in html
    assert 'data-copy="Nachal Dolev 12, Ramat Beit Shemesh"' in html and "Copy address" in html
    assert "Reserved for you until" in html and "Held until" not in html  # said once, at the top
    assert "Not bought yet" not in html
    assert html.count(f'action="/g/{token}/report"') == 1  # the report form lives in step 3 only
    assert "Mazel tov from all of us!" in html and "Your message with the gift:" in html
    assert 'class="gift-when"' in html and "Wedding" in html


def test_store_gift_steps_in_hebrew(client, app_module):
    guest, token = _reserve(client, app_module)
    he = guest.get(f"/g/{token}?lang=he").get_data(as_text=True)
    assert "להזמין ב-KSP" in he and "העתקת הכתובת" in he and "לספר לזוג שהמתנה בדרך" in he


def test_no_address_says_to_ask_and_offers_nothing_to_copy(client, app_module):
    guest, token = _reserve(client, app_module, address="")
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert "added delivery details yet" in html and "Copy address" not in html


def test_cash_gift_has_no_store_steps(client, app_module):
    guest, token = _reserve(client, app_module, give="cash")
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert "gift-steps" not in html and "paypal.me/dinayossi" in html


@pytest.mark.parametrize("days,expect", [(40, None), (5, "The simcha is in 5 days"), (1, "almost here"),
                                         (-3, None)])
def test_heads_up_when_the_simcha_is_close(client, app_module, days, expect):
    guest, token = _reserve(client, app_module, days_away=days)
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    if expect:
        assert expect in html
    else:
        assert "gift-rush" not in html


def test_no_heads_up_once_the_gift_is_on_its_way(client, app_module):
    guest, token = _reserve(client, app_module, days_away=5)
    db = _db()
    db.execute("UPDATE claims SET status='reported'")
    db.commit()
    html = guest.get(f"/g/{token}").get_data(as_text=True)
    assert "gift-rush" not in html and "gift-steps" not in html
