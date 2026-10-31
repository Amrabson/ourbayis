# -*- coding: utf-8 -*-
"""List check (2026-10-31): every guest budget, every room, nothing guests can't give — with
catalog suggestions that add straight back to the list."""
import os
import re
import sqlite3

from conftest import add_item, create_registry, get_csrf, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def test_empty_list_points_at_the_starter_pack(client):
    signup(client)
    create_registry(client)
    html = client.get("/registry/check").get_data(as_text=True)
    assert "How your list looks to guests" in html and "/registry/items/starter" in html


def test_list_check_finds_the_gaps_and_suggestions_fill_them(client):
    signup(client)
    create_registry(client)
    add_item(client, name="Hand towels", price_nis="80", url="https://example.com/towels")
    add_item(client, name="Bath mat", price_nis="120", url="")      # no link, no payment link
    add_item(client, name="Mystery gift", price_nis="0", url="https://example.com/m")
    html = client.get("/registry/check").get_data(as_text=True)

    # budgets: two open gifts under 200 = only a few; nothing at 200-500 or 500-1500
    budgets = html.split('id="budgets"')[1].split('id="rooms"')[0]
    rows = re.findall(r'<div class="check-row check-(\w+)">', budgets)
    assert rows == ["few", "none", "none", "quiet"]
    assert "Hand towels" in budgets and "Mystery gift" not in budgets
    # every gap below the top band offers catalog gifts at that price, each with an Add button
    assert budgets.count('name="catalog_id"') >= 6
    # rooms: everything so far is "home" -> only the entrance has gifts
    rooms = html.split('id="rooms"')[1].split('id="giving"')[0]
    assert re.findall(r'<div class="check-row check-(\w+)">', rooms) == ["empty", "empty", "empty", "listed"]
    assert "1/4" in html.replace("<small>", "").replace("</small>", "")
    # giving: the unlinked gift can't be given, the unpriced one is invisible to budget filters
    giving = html.split('id="giving"')[1]
    assert "Bath mat" in giving and "Mystery gift" in giving and "Add a payment link" in giving

    # add the first 200-500 suggestion: it lands on the list and we come back to the check
    m = re.search(r'<div class="check-row check-none">.*?name="catalog_id" value="(\d+)"', budgets, re.S)
    r = client.post("/registry/items/add?back=check&sec=budgets",
                    data=dict(csrf_token=get_csrf(html), catalog_id=m.group(1)))
    assert r.status_code == 302 and r.headers["Location"].endswith("/registry/check#budgets")
    assert _db().execute("SELECT 1 FROM registry_items WHERE catalog_id=?", (m.group(1),)).fetchone()
    again = client.get("/registry/check").get_data(as_text=True)
    assert 'value="%s"' % m.group(1) not in again  # never suggested once it's on the list


def test_list_check_counts_open_gifts_not_given_ones_and_is_bilingual(client):
    signup(client)
    create_registry(client)
    for n in range(4):
        add_item(client, name=f"Mug {n}", price_nis="50", url="https://example.com/mug")
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/x'")
    db.commit()
    html = client.get("/registry/check").get_data(as_text=True)
    assert re.findall(r'<div class="check-row check-(\w+)">', html.split('id="budgets"')[1])[0] == "good"
    assert "send money any time" in html
    he = client.get("/registry/check?lang=he").get_data(as_text=True)
    assert "איך הרשימה נראית לאורחים" in he and "מבחר טוב" in he
    # linked from the dashboard and the gifts page
    assert "/registry/check" in client.get("/dashboard").get_data(as_text=True)
    assert "/registry/check" in client.get("/registry/items").get_data(as_text=True)
