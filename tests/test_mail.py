# -*- coding: utf-8 -*-
"""Mail outbox hardening, 2026-09-27: one recipient per message, single-line
headers, and a lease so two senders never deliver the same row twice."""
import os
import sqlite3

import pytest

import ob_security
from test_p2 import _claim, _couple_with_catalog_items


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


@pytest.mark.parametrize("addr,ok", [
    ("a@b.co", True), ("o'brien@x.org", True), ("dvora.levi+ob@gmail.com", True),
    ("a@x.com,b", False), ("a@x.com, b@y.com", False), ("a@x.com;b@y.com", False),
    ("Name <a@b.com>", False), ("a@b.com\nBcc: c@d.com", False), ("x@y", False), ("", False),
])
def test_valid_email_accepts_one_address_only(addr, ok):
    assert ob_security.valid_email(addr) is ok


def test_crafted_guest_email_is_neither_stored_nor_mailed(client, app_module):
    """The browser's type=email was the only check; a hand-made POST could list several
    recipients. The reservation still goes through — the address is just ignored."""
    keys = [r[0] for r in _db().execute(
        "SELECT seed_key FROM catalog_items WHERE active=1 ORDER BY id LIMIT 2")]
    reg, items = _couple_with_catalog_items(client, app_module, keys)
    first, second = [r["id"] for r in items.values()]
    _claim(app_module, reg["slug"], first, guest_email="me@x.com, victim@y.com")
    db = _db()
    assert db.execute("SELECT guest_email FROM claims").fetchone()[0] == ""
    assert not db.execute("SELECT 1 FROM mail_outbox WHERE to_addr LIKE '%victim%'").fetchone()
    _claim(app_module, reg["slug"], second, name="Aunt", guest_email="aunt@example.com")
    assert _db().execute("SELECT 1 FROM mail_outbox WHERE to_addr='aunt@example.com'").fetchone()


def test_enqueue_refuses_bad_recipient_and_flattens_subject(app_module):
    import ob_mail
    with app_module.app.app_context():
        db = app_module.get_db()
        assert ob_mail.enqueue(db, "a@x.com,b@y.com", "s", "b") is None
        rid = ob_mail.enqueue(db, "a@x.com", "Line one\r\nBcc: z@z.com", "body")
        assert db.execute("SELECT subject FROM mail_outbox WHERE id=?", (rid,)).fetchone()[0] \
            == "Line one Bcc: z@z.com"


def test_two_senders_never_deliver_the_same_row_twice(app_module, monkeypatch):
    """enqueue()'s background thread and `manage.py send-mail` can reach one row at once."""
    import ob_db
    import ob_mail
    monkeypatch.setenv("OB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("OB_SMTP_USER", "u@example.com")
    monkeypatch.setenv("OB_SMTP_PASS", "x")
    monkeypatch.setattr(ob_mail.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: None})())
    sent = []
    path = os.environ["OB_DB_PATH"]

    def fake_send(to, subject, body, **kw):
        sent.append(to)
        if len(sent) == 1:  # a second sender arrives while the first is mid-send
            other = ob_db.connect(path)
            try:
                ob_mail.attempt(other, rid)
            finally:
                other.close()

    monkeypatch.setattr(ob_mail, "send_now", fake_send)
    with app_module.app.app_context():
        db = app_module.get_db()
        rid = ob_mail.enqueue(db, "guest@example.com", "s", "b")
        ob_mail.attempt(db, rid)
        ob_mail.flush(db)
        assert sent == ["guest@example.com"]
        assert db.execute("SELECT status FROM mail_outbox WHERE id=?", (rid,)).fetchone()[0] == "sent"


def test_failed_send_is_retried_after_backoff_not_lease(app_module, monkeypatch):
    import ob_mail
    monkeypatch.setenv("OB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("OB_SMTP_USER", "u@example.com")
    monkeypatch.setenv("OB_SMTP_PASS", "x")
    monkeypatch.setattr(ob_mail.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: None})())

    def boom(*a, **kw):
        raise OSError("down")

    monkeypatch.setattr(ob_mail, "send_now", boom)
    with app_module.app.app_context():
        db = app_module.get_db()
        rid = ob_mail.enqueue(db, "guest@example.com", "s", "b")
        ob_mail.attempt(db, rid)
        row = db.execute("SELECT status, attempts, last_error FROM mail_outbox WHERE id=?", (rid,)).fetchone()
        assert (row["status"], row["attempts"], row["last_error"]) == ("queued", 1, "OSError")


def test_owner_notifications_reply_to_the_sender(client, app_module, monkeypatch):
    """Contact messages and Shana leads: hitting Reply answers the person, not the site."""
    import ob_mail
    monkeypatch.setattr(app_module, "NOTIFY_EMAIL", "owner@example.com")
    from conftest import get_csrf
    html = client.get("/contact").get_data(as_text=True)
    client.post("/contact", data=dict(csrf_token=get_csrf(html), name="Rivka",
                                      email="rivka@example.com", body="Question about shipping"))
    html = client.get("/shana-rishonah").get_data(as_text=True)
    client.post("/shana-rishonah", data=dict(csrf_token=get_csrf(html), name="Lead",
                                             email="bad, list@x.com", whatsapp="+972501234567"))
    rows = _db().execute("SELECT subject, reply_to FROM mail_outbox WHERE to_addr='owner@example.com'"
                         " ORDER BY id").fetchall()
    assert [r["reply_to"] for r in rows] == ["rivka@example.com", ""]    # invalid address dropped

    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setenv("OB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("OB_SMTP_USER", "site@example.com")
    monkeypatch.setenv("OB_SMTP_PASS", "x")
    monkeypatch.setattr(ob_mail.smtplib, "SMTP", FakeSMTP)
    ob_mail.send_now("owner@example.com", "s", "b", reply_to="rivka@example.com")
    assert sent["msg"]["Reply-To"] == "rivka@example.com"
    ob_mail.send_now("owner@example.com", "s", "b", reply_to="x@y.com, z@w.com")
    assert sent["msg"]["Reply-To"] is None
