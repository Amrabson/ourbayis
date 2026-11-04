# -*- coding: utf-8 -*-
"""Hebrew date (2026-11-04): the simcha date shows its Hebrew date, couples can pick the
date as a Hebrew date, and a wedding set on Shabbos / Yom Tov gets a "check the date" note."""
import os
import re
import sqlite3
from datetime import date, timedelta

import ob_hebcal as H
from conftest import create_registry, get_csrf, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _reg():
    return _db().execute("SELECT * FROM registries").fetchone()


def _edit(client, lang="en", **fields):
    page = client.get(f"/registry/edit?lang={lang}").get_data(as_text=True)
    was = re.search(r'name="hdate_was" value="([^"]*)"', page).group(1)
    data = dict(csrf_token=get_csrf(page), title="Our Home", couple_names="Sarah & Dovid",
                event_type="wedding", visibility="public", hdate_was=was)
    data.update(fields)
    return client.post(f"/registry/edit?lang={lang}", data=data, follow_redirects=True)


def test_conversion_matches_known_dates_and_round_trips():
    known = {"2026-04-02": (5786, 1, 15), "2026-09-12": (5787, 7, 1), "2000-01-01": (5760, 10, 23),
             "2024-03-24": (5784, 13, 14), "2027-03-23": (5787, 13, 14), "2026-07-23": (5786, 5, 9)}
    for iso, heb in known.items():
        assert H.to_hebrew(date.fromisoformat(iso)) == heb, iso
    d = date(2020, 1, 1)
    while d < date(2040, 1, 1):
        assert H.from_hebrew(*H.to_hebrew(d)) == d
        d += timedelta(days=1)
    assert H.format_hebrew("2026-12-05", "he") == "כ״ה בכסלו תשפ״ז"
    assert H.format_hebrew("2026-12-05") == "25 Kislev 5787"
    assert H.format_hebrew("2027-03-23") == "14 Adar II 5787"
    assert [H.numeral(n) for n in (1, 15, 16, 30)] == ["א׳", "ט״ו", "ט״ז", "ל׳"]
    assert H.day_note(date(2026, 12, 19)) == ("shabbos", None)
    assert H.day_note(date(2026, 4, 2)) == ("yomtov", "pesach")
    assert H.day_note(date(2026, 4, 4)) == ("chol_hamoed", "pesach")  # Chol Hamoed on Shabbos
    assert H.day_note(date(2026, 12, 15)) is None


def test_registry_and_dashboard_show_the_hebrew_date(client):
    signup(client)
    create_registry(client)
    _edit(client, event_date="2026-12-15")
    slug = _reg()["slug"]
    en = client.get(f"/r/{slug}?lang=en").get_data(as_text=True)
    assert "15 December 2026" in en and "5 Teves 5787" in en
    he = client.get(f"/r/{slug}?lang=he").get_data(as_text=True)
    assert "ה׳ בטבת תשפ״ז" in he
    dash = client.get("/dashboard?lang=en").get_data(as_text=True)
    assert "5 Teves 5787" in dash
    form = client.get("/registry/edit?lang=en").get_data(as_text=True)
    assert "That&#39;s 5 Teves 5787." in form or "That's 5 Teves 5787." in form
    assert 'name="hdate_was" value="5|10|5787"' in form


def test_couple_picks_the_date_as_a_hebrew_date(client):
    signup(client)
    create_registry(client)
    # 14 Adar (Purim) of the leap year 5787: plain "Adar" means Adar II
    _edit(client, hd_day="14", hd_month="adar", hd_year="5787")
    assert _reg()["event_date"] == "2027-03-23"
    # the picker now shows that date; editing only the calendar date still wins
    _edit(client, hd_day="14", hd_month="adar2", hd_year="5787", event_date="2027-01-10")
    assert _reg()["event_date"] == "2027-01-10"
    # a day the month doesn't have is an error, and nothing is saved
    r = _edit(client, hd_day="30", hd_month="10", hd_year="5787").get_data(as_text=True)
    assert "Teves 5787 has only 29 days" in r
    assert _reg()["event_date"] == "2027-01-10"
    r = _edit(client, hd_day="3", hd_month="", hd_year="5787").get_data(as_text=True)
    assert "Pick the day, month and year" in r


def test_wedding_on_shabbos_or_yom_tov_gets_a_gentle_note(client):
    signup(client)
    create_registry(client)
    r = _edit(client, event_date="2026-12-19").get_data(as_text=True)  # a Shabbos
    assert "flash-warn" in r and "motzei Shabbos" in r
    assert _reg()["event_date"] == "2026-12-19"  # never blocks
    r = _edit(client, event_date="2026-12-19").get_data(as_text=True)  # unchanged: no repeat
    assert "flash-warn" not in r
    r = _edit(client, lang="he", event_date="2027-04-22").get_data(as_text=True)  # Pesach 5787
    assert "flash-warn" in r and "פסח" in r
    r = _edit(client, event_date="2026-12-15").get_data(as_text=True)  # an ordinary Tuesday
    assert "flash-warn" not in r
    # a bar mitzvah on Shabbos is ordinary
    r = _edit(client, event_date="2026-12-26", event_type="bar").get_data(as_text=True)
    assert "flash-warn" not in r
