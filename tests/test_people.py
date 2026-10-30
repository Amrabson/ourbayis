# -*- coding: utf-8 -*-
"""Managing a registry together (2026-10-30): owner invites, a helper joins with their own account,
payment links stay the owner's, removal / leaving / handing over the registry."""
import os
import re
import sqlite3

from conftest import create_registry, get_csrf, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _invite(client, label="Yosef"):
    html = client.get("/registry/people").get_data(as_text=True)
    r = client.post("/registry/people/invite", data=dict(csrf_token=get_csrf(html), label=label))
    assert r.status_code == 302
    page = client.get("/registry/people").get_data(as_text=True)
    m = re.search(r'data-copy="(https?://[^"]+/join/[^"]+)"', page)
    assert m, "the fresh invite link is shown once on the people page"
    # ...and only once: a reload no longer carries it
    assert "/join/" not in client.get("/registry/people").get_data(as_text=True).split("people-list")[0]
    return m.group(1).split("://", 1)[1].split("/", 1)[1]  # path


def _owner_with_registry(app):
    owner = app.test_client()
    signup(owner, email="rivka@example.com", name="Rivka")
    create_registry(owner, title="Our Home", couple="Rivka & Yosef")
    return owner


def _join(app, path, email="yosef@example.com", name="Yosef"):
    helper = app.test_client()
    page = helper.get("/" + path).get_data(as_text=True)
    assert "Rivka invited you" in page and "Sign in to accept" in page
    # signing up from the invite comes straight back to it (not to "create your registry")
    r = signup(helper, email=email, name=name)
    body = r.get_data(as_text=True)
    assert "Join and start helping" in body
    r = helper.post("/" + path, data=dict(csrf_token=get_csrf(body)))
    assert r.status_code == 302 and r.headers["Location"].endswith("/dashboard")
    return helper


def test_invite_link_lets_a_helper_manage_the_registry_once(app):
    owner = _owner_with_registry(app)
    path = _invite(owner)
    helper = _join(app, path)

    dash = helper.get("/dashboard").get_data(as_text=True)
    assert "Our Home" in dash and "Helping Rivka" in dash
    db = _db()
    reg = db.execute("SELECT id, user_id FROM registries").fetchone()
    yosef = db.execute("SELECT id FROM users WHERE email='yosef@example.com'").fetchone()["id"]
    assert db.execute("SELECT 1 FROM registry_members WHERE registry_id=? AND user_id=?",
                      (reg["id"], yosef)).fetchone()
    assert db.execute("SELECT 1 FROM registries WHERE user_id=?", (yosef,)).fetchone() is None
    # the owner hears about it right away
    mail = db.execute("SELECT subject, body FROM mail_outbox WHERE to_addr='rivka@example.com'"
                      " AND subject LIKE '%can now manage%'").fetchone()
    assert mail and "yosef@example.com" in mail["body"]
    # only the hash of the token is stored, and the link is single-use
    token = path.rsplit("/", 1)[1]
    assert not db.execute("SELECT 1 FROM registry_invites WHERE token_hash=?", (token,)).fetchone()
    third = app.test_client()
    assert "This invite has closed" in third.get("/" + path).get_data(as_text=True)
    # the people page lists both, and the helper can't invite or remove anyone
    people = helper.get("/registry/people").get_data(as_text=True)
    assert "Rivka" in people and "Yosef" in people and "Stop helping" in people
    assert helper.post("/registry/people/invite", data=dict(csrf_token=get_csrf(people))).status_code == 403
    assert helper.post(f"/registry/people/{yosef}/remove",
                       data=dict(csrf_token=get_csrf(people))).status_code == 403


def test_a_helper_edits_the_registry_but_never_the_payment_links(app):
    owner = _owner_with_registry(app)
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/rivka'")
    db.commit()
    helper = _join(app, _invite(owner))
    form = helper.get("/registry/edit").get_data(as_text=True)
    assert "Only Rivka can change these" in form
    assert re.search(r'name="paypal_url"[^>]*disabled', form)
    r = helper.post("/registry/edit", data=dict(
        csrf_token=get_csrf(form), title="Our Bayis", couple_names="Rivka & Yosef", event_type="wedding",
        visibility="unlisted", paypal_url="https://paypal.me/someone-else"))
    assert r.status_code == 302
    row = _db().execute("SELECT title, paypal_url FROM registries").fetchone()
    assert row["title"] == "Our Bayis" and row["paypal_url"] == "https://paypal.me/rivka"


def test_owner_removes_a_helper_and_they_lose_access(app):
    owner = _owner_with_registry(app)
    helper = _join(app, _invite(owner))
    yosef = _db().execute("SELECT id FROM users WHERE email='yosef@example.com'").fetchone()["id"]
    page = owner.get("/registry/people").get_data(as_text=True)
    assert owner.post(f"/registry/people/{yosef}/remove",
                      data=dict(csrf_token=get_csrf(page))).status_code == 302
    dash = helper.get("/dashboard").get_data(as_text=True)
    assert "Helping Rivka" not in dash and "/registry/new" in dash
    assert helper.get("/dashboard/thanks").status_code == 302


def test_handing_over_keeps_the_registry_when_the_old_owner_deletes_their_account(app):
    owner = _owner_with_registry(app)
    helper = _join(app, _invite(owner))
    db = _db()
    yosef = db.execute("SELECT id FROM users WHERE email='yosef@example.com'").fetchone()["id"]
    page = owner.get("/registry/people").get_data(as_text=True)
    # needs the owner's password
    owner.post(f"/registry/people/{yosef}/owner", data=dict(csrf_token=get_csrf(page), current_password="nope"))
    assert _db().execute("SELECT user_id FROM registries").fetchone()[0] != yosef
    owner.post(f"/registry/people/{yosef}/owner", data=dict(csrf_token=get_csrf(page), current_password="password1"))
    assert _db().execute("SELECT user_id FROM registries").fetchone()[0] == yosef
    assert "Only Rivka" not in helper.get("/registry/edit").get_data(as_text=True)
    assert "Helping Yosef" in owner.get("/dashboard").get_data(as_text=True)
    acct = owner.get("/account").get_data(as_text=True)
    assert "stays with Yosef" in acct
    owner.post("/account/delete", data=dict(csrf_token=get_csrf(acct), current_password="password1"))
    assert _db().execute("SELECT COUNT(*) FROM registries").fetchone()[0] == 1
    assert "Our Home" in helper.get("/dashboard").get_data(as_text=True)


def test_invites_refuse_accounts_that_already_manage_a_registry_and_can_be_cancelled(app):
    owner = _owner_with_registry(app)
    path = _invite(owner)
    other = app.test_client()
    signup(other, email="dov@example.com", name="Dov")
    create_registry(other, title="Dov's Home", couple="Dov & Chana")
    page = other.get("/" + path).get_data(as_text=True)
    assert "already has a registry of its own" in page and "Join and start helping" not in page
    assert other.post("/" + path, data=dict(csrf_token=get_csrf(page))).status_code == 200
    assert _db().execute("SELECT COUNT(*) FROM registry_members").fetchone()[0] == 0
    # the owner cancels it: the link closes
    inv = _db().execute("SELECT id FROM registry_invites").fetchone()["id"]
    people = owner.get("/registry/people").get_data(as_text=True)
    assert "Invite for Yosef" in people
    owner.post(f"/registry/people/invite/{inv}/revoke", data=dict(csrf_token=get_csrf(people)))
    assert "This invite has closed" in app.test_client().get("/" + path).get_data(as_text=True)


def test_a_helper_can_leave(app):
    owner = _owner_with_registry(app)
    helper = _join(app, _invite(owner))
    page = helper.get("/registry/people").get_data(as_text=True)
    assert helper.post("/registry/people/leave", data=dict(csrf_token=get_csrf(page))).status_code == 302
    assert _db().execute("SELECT COUNT(*) FROM registry_members").fetchone()[0] == 0
    assert owner.post("/registry/people/leave",
                      data=dict(csrf_token=get_csrf(owner.get("/registry/people").get_data(as_text=True)))
                      ).status_code == 403


def test_people_and_join_pages_are_bilingual(app):
    owner = _owner_with_registry(app)
    he = owner.get("/registry/people?lang=he").get_data(as_text=True)
    assert "מי מנהל את הרשימה" in he and "יצירת קישור הזמנה" in he
    path = _invite(owner)
    assert "ההזמנה הזו נסגרה" in app.test_client().get("/join/nope?lang=he").get_data(as_text=True)
    assert "הזמינו אתכם" in app.test_client().get("/" + path + "?lang=he").get_data(as_text=True)
