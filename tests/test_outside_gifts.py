# -*- coding: utf-8 -*-
"""Gifts from outside the list (2026-11-03): the couple notes envelopes and hand-delivered gifts on
the thank-you page, gets a note started for each, and their card's words join the keepsake."""
import html as htmllib
import json
import os
import sqlite3

from conftest import create_registry, get_csrf, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _post(client, url, **data):
    page = client.get("/dashboard/thanks").get_data(as_text=True)
    return client.post(url, data=dict(csrf_token=get_csrf(page), **data))


def test_add_one_gift_thank_it_and_keep_their_card(client):
    signup(client)
    create_registry(client)
    page = client.get("/dashboard/thanks").get_data(as_text=True)
    assert 'id="outside-add" open' in page  # nothing to thank yet: the form starts open
    r = _post(client, "/dashboard/thanks/outside", giver_name="The Cohen family", gift="a salad bowl",
              message="Mazel tov from all of us!", email="cohen@example.com", lang="en")
    gid = _db().execute("SELECT id FROM outside_gifts").fetchone()["id"]
    assert r.status_code == 302 and r.headers["Location"].endswith(f"#thanks-o{gid}")

    page = htmllib.unescape(client.get("/dashboard/thanks").get_data(as_text=True))
    card = page.split(f'id="thanks-o{gid}"')[1].split("</article>")[0]
    assert "The Cohen family" in card and "Outside the list" in card and "Their card" in card
    assert "Thank you so much for a salad bowl" in card       # their own article is kept
    assert "Dear Cohen family," in card                        # not "Dear The Cohen family"
    assert "mailto:cohen@example.com" in card
    assert "1 to thank" in page

    _post(client, f"/dashboard/thanks/outside/{gid}/thanked")
    page = client.get("/dashboard/thanks").get_data(as_text=True)
    assert "0 to thank · 1 thanked" in page and f'<li id="thanks-o{gid}">' in page
    assert "Mazel tov from all of us!" in client.get("/dashboard/keepsake").get_data(as_text=True)

    data = json.loads(client.get("/account/export.json").get_data(as_text=True))
    assert data["outside_gifts"][0]["giver_name"] == "The Cohen family"

    _post(client, f"/dashboard/thanks/outside/{gid}/delete")
    assert _db().execute("SELECT COUNT(*) FROM outside_gifts").fetchone()[0] == 0


def test_paste_a_list(client):
    signup(client)
    create_registry(client)
    r = _post(client, "/dashboard/thanks/outside",
              lines="Cohen family - Shabbos candlesticks\n\n  Savta Rachel, a check \nDov and Shira\nמשפחת לוי - קערת סלט\n")
    assert r.status_code == 302
    rows = [tuple(r) for r in _db().execute("SELECT giver_name, gift FROM outside_gifts ORDER BY id")]
    assert rows == [("Cohen family", "Shabbos candlesticks"), ("Savta Rachel", "a check"),
                    ("Dov and Shira", ""), ("משפחת לוי", "קערת סלט")]
    page = htmllib.unescape(client.get("/dashboard/thanks").get_data(as_text=True))
    assert "Added 4 gifts" in page and "Thank you so much for the Shabbos candlesticks" in page
    assert "your generous gift" in page   # a bare name still gets a note
    # a line written in Hebrew starts its note in Hebrew
    assert [r[0] for r in _db().execute("SELECT lang FROM outside_gifts ORDER BY id")] == ["en", "en", "en", "he"]
    he = client.get("/dashboard/thanks?lang=he").get_data(as_text=True)
    assert "מחוץ לרשימה" in he and "הוספת מתנה שהגיעה מחוץ לרשימה" in he


def test_bad_input_adds_nothing(client):
    signup(client)
    create_registry(client)
    _post(client, "/dashboard/thanks/outside", giver_name="  ", gift="vase")
    _post(client, "/dashboard/thanks/outside", giver_name="Dov", email="not-an-email")
    _post(client, "/dashboard/thanks/outside", lines="\n  \n")
    assert _db().execute("SELECT COUNT(*) FROM outside_gifts").fetchone()[0] == 0


def test_only_the_couple_can_touch_their_outside_gifts(client, app):
    signup(client)
    create_registry(client)
    _post(client, "/dashboard/thanks/outside", giver_name="Uncle Mendel", gift="a vase")
    gid = _db().execute("SELECT id FROM outside_gifts").fetchone()["id"]

    other = app.test_client()
    signup(other, email="other@b.com")
    create_registry(other, title="Their Home")
    page = other.get("/dashboard/thanks").get_data(as_text=True)
    assert "Uncle Mendel" not in page
    for url in (f"/dashboard/thanks/outside/{gid}/thanked", f"/dashboard/thanks/outside/{gid}/delete"):
        assert other.post(url, data=dict(csrf_token=get_csrf(page))).status_code == 404
    assert _db().execute("SELECT thanked FROM outside_gifts").fetchone()["thanked"] == 0
    # and guests never see them
    slug = _db().execute("SELECT slug FROM registries WHERE title='Our Home'").fetchone()["slug"]
    assert "a vase" not in app.test_client().get(f"/r/{slug}").get_data(as_text=True)
