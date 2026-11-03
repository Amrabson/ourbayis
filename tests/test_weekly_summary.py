# -*- coding: utf-8 -*-
"""The weekly summary email (2026-11-03): once a week, only when there's something new or waiting,
to the owner and to helpers who turned on the gift emails; off from the account page or the email."""
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone

from conftest import add_item, create_registry, get_csrf, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _run(app_module, when=None):
    with app_module.app.test_request_context("/"):
        return app_module.send_digests(app_module.get_db(), now=when)


def _mails():
    return _db().execute("SELECT * FROM mail_outbox WHERE subject LIKE '%week%' OR subject LIKE '%השבוע%'"
                         " ORDER BY id").fetchall()


def _gift(status="reported", thanked=0, name="Aunt Miriam"):
    db = _db()
    rid = db.execute("SELECT id FROM registries").fetchone()["id"]
    db.execute("INSERT INTO claims (registry_id, guest_name, kind, status, thanked) VALUES (?,?,?,?,?)",
               (rid, name, "cash", status, thanked))
    db.commit()


def test_summary_says_what_is_new_and_waiting_once_a_week(client, app_module):
    signup(client)
    create_registry(client)
    assert _run(app_module) == 0          # nothing to say: no email
    _gift("reported")
    db = _db()
    db.execute("INSERT INTO brachos (registry_id, guest_name, message) SELECT id, 'Dov', 'Mazel tov' FROM registries")
    db.commit()

    assert _run(app_module) == 1
    m = _mails()[-1]
    assert m["to_addr"] == "a@b.com" and m["subject"] == "Your week — Our Home"
    for line in ("1 new gift was reserved or sent.", "A guest left you a bracha.",
                 "1 gift is on its way: confirm it when it arrives.", "1 gift is waiting for a thank-you note."):
        assert "• " + line in m["body"]
    assert "/dashboard/thanks" in m["body"] and "/digest/off/" in m["body"]

    assert _run(app_module) == 0          # not twice in a week
    later = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    assert _run(app_module, later) == 1   # a week on, the gift is still waiting
    body = _mails()[-1]["body"]
    assert "new gift" not in body and "bracha" not in body and "waiting for a thank-you" in body


def test_close_to_the_day_it_points_at_budget_gaps(client, app_module):
    signup(client)
    create_registry(client)
    add_item(client, name="Towels", price_nis="80")
    db = _db()
    db.execute("UPDATE registries SET event_date=?", ((date.today() + timedelta(days=20)).isoformat(),))
    db.commit()
    assert _run(app_module) == 1
    body = _mails()[-1]["body"]
    assert "20 days to go!" in body and "₪200–500" in body and "nothing left to choose" in body


def test_turning_it_off_from_the_account_and_from_the_email(client, app, app_module):
    signup(client)
    create_registry(client)
    _gift("received")
    page = client.get("/account").get_data(as_text=True)
    assert "Weekly summary email" in page and "Turn off" in page
    client.post("/account/digest", data=dict(csrf_token=get_csrf(page), digest="0"))
    assert _run(app_module) == 0
    page = client.get("/account").get_data(as_text=True)
    client.post("/account/digest", data=dict(csrf_token=get_csrf(page), digest="1"))
    assert _run(app_module) == 1

    link = re.search(r"/digest/off/\S+", _mails()[-1]["body"]).group(0)
    anon = app.test_client()
    page = anon.get(link).get_data(as_text=True)    # opening the link changes nothing
    assert "Stop the weekly summary?" in page
    assert _db().execute("SELECT digest FROM users").fetchone()["digest"] == 1
    anon.post(link, data=dict(csrf_token=get_csrf(page)))
    assert _db().execute("SELECT digest FROM users").fetchone()["digest"] == 0
    assert "The weekly summary is off" in anon.get(link).get_data(as_text=True)
    assert anon.get("/digest/off/not-a-real-token").status_code == 404


def test_helpers_get_it_only_with_gift_emails_on_and_in_their_language(client, app, app_module):
    signup(client)
    create_registry(client)
    _gift("received")
    helper = app.test_client()
    signup(helper, email="h@b.com", name="Yosef")
    db = _db()
    hid = db.execute("SELECT id FROM users WHERE email='h@b.com'").fetchone()["id"]
    db.execute("INSERT INTO registry_members (registry_id, user_id) SELECT id, ? FROM registries", (hid,))
    db.execute("UPDATE users SET lang='he' WHERE id=?", (hid,))
    db.commit()
    assert _run(app_module) == 1                      # the owner only
    db.execute("UPDATE registry_members SET notify=1")
    db.execute("UPDATE users SET digest_at=NULL")
    db.commit()
    assert _run(app_module) == 2
    he = [m for m in _mails() if m["to_addr"] == "h@b.com"][0]
    assert he["subject"].startswith("השבוע שלכם") and "מתנה אחת מחכה למכתב תודה." in he["body"]


def test_manage_command_queues_with_full_links(client, app_module, monkeypatch):
    signup(client)
    create_registry(client)
    _gift("received")
    monkeypatch.setenv("OB_BASE_URL", "https://ourbayis.example")
    sys.modules.pop("manage", None)
    import manage
    assert manage.cmd_weekly_summary(None) == 0
    body = _mails()[-1]["body"]
    assert "https://ourbayis.example/dashboard" in body and "https://ourbayis.example/digest/off/" in body
