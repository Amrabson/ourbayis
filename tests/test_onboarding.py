# -*- coding: utf-8 -*-
"""Onboarding (2026-11-08): one password field, first-time setup asks only for the details,
and an expired form explains itself instead of "something went wrong"."""
import html
import json
import os
import sqlite3

from conftest import get_csrf


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _signup_one_field(client):
    page = client.get("/signup?lang=en").get_data(as_text=True)
    assert 'name="password2"' not in page and "Show password" in page
    return client.post("/signup", data=dict(csrf_token=get_csrf(page), name="Rivka", email="rivka@example.com",
                                            password="password1"), follow_redirects=True)


def test_signup_needs_the_password_once(client):
    r = _signup_one_field(client)
    assert r.request.path == "/registry/new"
    assert _db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_first_setup_asks_only_for_the_details_and_defaults_the_title(client):
    _signup_one_field(client)
    page = html.unescape(client.get("/registry/new?lang=en").get_data(as_text=True))
    assert 'id="rf-details"' in page
    for later in ('id="rf-prefs"', 'id="rf-payment"', 'id="rf-visibility"', 'class="form-rail"'):
        assert later not in page
    assert "on your dashboard whenever you're ready" in page
    r = client.post("/registry/new", data=dict(csrf_token=get_csrf(page), couple_names="Rivka & Shmuel",
                                               event_type="wedding"), follow_redirects=True)
    assert r.request.path == "/registry/items"
    reg = _db().execute("SELECT * FROM registries").fetchone()
    assert (reg["title"], reg["title_he"], reg["visibility"]) == ("Our new home", "הבית החדש שלנו", "unlisted")
    # visibility wasn't on the page, so the dashboard checklist still asks about it
    assert "visibility_reviewed_at" not in json.loads(reg["preferences_json"] or "{}")
    edit = client.get("/registry/edit?lang=en").get_data(as_text=True)
    assert 'id="rf-payment"' in edit and 'id="rf-visibility"' in edit


def test_expired_form_explains_itself(client):
    page = client.get("/contact?lang=en").get_data(as_text=True)
    with client.session_transaction() as s:
        s.clear()  # the session behind the open page is gone (sign-out, restart, new browser session)
    r = client.post("/contact?lang=en", data=dict(csrf_token=get_csrf(page), name="x", email="x@example.com",
                                                  message="hello"))
    html = r.get_data(as_text=True)
    assert r.status_code == 400
    assert "That page was open too long" in html and "nothing was saved" in html
    assert "Log in again" in html


def test_dashboard_names_the_one_next_step(client):
    _signup_one_field(client)
    page = client.get("/registry/new").get_data(as_text=True)
    client.post("/registry/new", data=dict(csrf_token=get_csrf(page), couple_names="Rivka & Shmuel", event_type="wedding"))
    dash = html.unescape(client.get("/dashboard?lang=en").get_data(as_text=True))
    assert 'class="dash-next"' in dash and "Put some gifts on the list" in dash
    assert dash.index('class="dash-next"') < dash.index('class="dash-actions"')
    assert 'href="/registry/items/starter"' in dash
    assert 'class="stat-row"' not in dash  # four zeros say nothing to a couple who just started
    he = client.get("/dashboard?lang=he").get_data(as_text=True)
    assert "השלב הבא" in he and "שימו כמה מתנות ברשימה" in he
