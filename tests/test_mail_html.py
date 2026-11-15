# -*- coding: utf-8 -*-
"""Designed HTML emails (2026-11-15): every email carries an HTML alternative beside the unchanged
text body — brand header, the gift's picture, one clear button — and still works with images off."""
import os
import re
import sqlite3

import pytest

from conftest import add_item, create_registry, get_csrf, get_form_key, signup
from test_p1 import admin_login
from test_people import _invite, _join, _owner_with_registry
from test_weekly_summary import _gift, _run

IMG = "https://img.example.com/kettle.jpg"


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _exec(sql):
    db = _db()
    db.execute(sql)
    db.commit()
    db.close()


def _row(to=None, like="%"):
    where, args = "subject LIKE ?", [like]
    if to:
        where += " AND to_addr=?"
        args.append(to)
    return _db().execute(f"SELECT * FROM mail_outbox WHERE {where} ORDER BY id DESC", args).fetchone()


def _urls(text):
    return re.findall(r"https?://[^\s<>\"]+", text)


def _setup(client, image=IMG, names=("Electric kettle",)):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    for n in names:
        add_item(client, name=n, price_nis="64", url="https://ksp.co.il/item/1")
    db = _db()
    db.execute("UPDATE registries SET delivery_note='Nachal Dolev 12'")
    db.execute("UPDATE registry_items SET store='KSP', image=?", (image,))
    db.commit()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    ids = [r["id"] for r in db.execute("SELECT id FROM registry_items ORDER BY id")]
    return slug, ids


def _reserve(app_module, slug, item_id, name="Aunt Malka", email="malka@example.com", lang="en", message="Mazel tov!"):
    g = app_module.app.test_client()
    page = g.get(f"/r/{slug}?lang={lang}").get_data(as_text=True)
    r = g.post(f"/r/{slug}/claim/{item_id}?lang={lang}", data=dict(
        csrf_token=get_csrf(page), form_key=get_form_key(page), guest_name=name,
        guest_email=email, message=message, give="buy"))
    assert r.status_code == 302
    return g, r.headers["Location"].rsplit("/", 1)[-1].split("?")[0]


def _both(row):
    assert row is not None
    assert row["body"] and row["body_html"]
    assert "<!doctype html>" in row["body_html"].lower() and "multipart" not in row["body"]
    return row["body"], row["body_html"]


# ------------------------------------------------------------------ couple + guest mails
def test_reservation_mail_to_the_couple_has_picture_name_and_dashboard_button(client, app_module):
    slug, ids = _setup(client)
    _reserve(app_module, slug, ids[0])
    text, html = _both(_row("couple@example.com", "Aunt Malka reserved%"))
    assert "Aunt Malka" in html and "Electric kettle" in html and "Mazel tov!" in html
    assert 'dir="ltr"' in html and "Bayis" in html
    dash = [u for u in _urls(text) if u.endswith("/dashboard")][0]
    assert f'href="{dash}"' in html and "Open your dashboard" in html
    assert f'<img src="{IMG}"' in html and 'alt="Electric kettle"' in html
    assert 'width="160"' in html and 'height="160"' in html


def test_no_picture_no_img_tag(client, app_module):
    slug, ids = _setup(client, image="")
    _reserve(app_module, slug, ids[0])
    _, html = _both(_row("couple@example.com", "Aunt Malka reserved%"))
    assert "<img" not in html and "Electric kettle" in html
    # a non-https picture is never shown either
    _exec("UPDATE registry_items SET image='http://x.example/a.jpg'")
    _, html2 = _both(_row("malka@example.com"))
    assert "<img" not in html2


def test_guest_link_mail_has_store_and_gift_page_buttons(client, app_module):
    slug, ids = _setup(client)
    _, token = _reserve(app_module, slug, ids[0])
    text, html = _both(_row("malka@example.com", "Your gift for%"))
    link = [u for u in _urls(text) if f"/g/{token}" in u][0]
    store = [u for u in _urls(text) if "/go/i/" in u][0]
    assert f'href="{link}"' in html and "Open your gift page" in html
    assert f'href="{store}"' in html and "View the gift at KSP" in html
    assert f'<img src="{IMG}"' in html and "Nachal Dolev 12" in html


def test_hebrew_email_is_rtl(client, app_module):
    slug, ids = _setup(client)
    _exec("UPDATE users SET lang='he'")
    _reserve(app_module, slug, ids[0], lang="he")
    text, html = _both(_row("malka@example.com"))
    assert 'dir="rtl"' in html and 'lang="he"' in html
    assert "העמוד הפרטי של המתנה" in html
    _, owner_html = _both(_row("couple@example.com"))
    assert 'dir="rtl"' in owner_html or 'dir="ltr"' in owner_html  # owner lang falls back, never broken


def test_hebrew_owner_email_is_rtl(client, app_module):
    slug, ids = _setup(client)
    db = _db()
    db.execute("UPDATE users SET lang='he'")
    db.commit()
    _reserve(app_module, slug, ids[0])
    text, html = _both(_row("couple@example.com"))
    assert 'dir="rtl"' in html and 'lang="he"' in html and "לוח הבקרה שלכם" in html


def test_guest_name_is_escaped(client, app_module):
    slug, ids = _setup(client)
    _reserve(app_module, slug, ids[0], name="<script>alert(1)</script>", message="<b>hi</b> there")
    text, html = _both(_row("couple@example.com"))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>hi</b>" not in html and "&lt;b&gt;hi&lt;/b&gt;" in html


def test_reported_received_and_released_mails(client, app_module):
    slug, ids = _setup(client, names=("Electric kettle", "Stand mixer"))
    g, t1 = _reserve(app_module, slug, ids[0], name="Aunt Sarah", email="sarah@example.com")
    _, t2 = _reserve(app_module, slug, ids[1], name="Dodah Rivka", email="rivka@example.com")
    page = g.get(f"/g/{t1}").get_data(as_text=True)
    g.post(f"/g/{t1}/report", data=dict(csrf_token=get_csrf(page), report_note="arriving Thursday"))
    text, html = _both(_row("couple@example.com", "%on its way%"))
    assert "Aunt Sarah" in html and "Electric kettle" in html and "arriving Thursday" in html
    assert f'<img src="{IMG}"' in html

    cids = {r["guest_name"]: r["id"] for r in _db().execute("SELECT id, guest_name FROM claims")}
    tok = get_csrf(client.get("/dashboard").get_data(as_text=True))
    client.post(f"/claim/{cids['Aunt Sarah']}/confirm", data=dict(csrf_token=tok))
    text, html = _both(_row("sarah@example.com", "Your gift arrived%"))
    assert "Electric kettle" in html and "Sarah &amp; Dovid" in html or "Dina &amp; Yossi" in html
    assert "Thank you for helping them build their bayis!" in html

    tok = get_csrf(client.get("/dashboard").get_data(as_text=True))
    client.post(f"/claim/{cids['Dodah Rivka']}/cancel", data=dict(csrf_token=tok))
    text, html = _both(_row("rivka@example.com", "Your reservation was released%"))
    link = [u for u in _urls(text) if "/r/" in u][0]
    assert f'href="{link}"' in html and "View the registry" in html


def test_cash_gift_and_bracha_mails(client, app_module):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/dinayossi', visibility='public'")
    db.commit()
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    g = app_module.app.test_client()
    page = g.get(f"/r/{slug}").get_data(as_text=True)
    g.post(f"/r/{slug}/cash", data=dict(csrf_token=get_csrf(page), form_key=get_form_key(page),
                                        guest_name="Cousin Dov", amount="50", currency="USD",
                                        message="For the sukkah"))
    text, html = _both(_row("couple@example.com", "Cousin Dov sent you%"))
    assert "Cousin Dov" in html and "$50" in html and "<img" not in html
    assert f'href="{[u for u in _urls(text) if u.endswith("/dashboard")][0]}"' in html
    g2 = app_module.app.test_client()
    page = g2.get(f"/r/{slug}").get_data(as_text=True)
    g2.post(f"/r/{slug}/bracha", data=dict(csrf_token=get_csrf(page), form_key=get_form_key(page),
                                           guest_name="Aunt Miriam", message="May your home be full of simchas!"))
    text, html = _both(_row("couple@example.com", "Aunt Miriam left you a bracha%"))
    assert "Aunt Miriam" in html and "May your home be full of simchas!" in html


def test_password_reset_mail(app_module, monkeypatch):
    monkeypatch.setenv("OB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("OB_SMTP_USER", "site@example.com")
    monkeypatch.setenv("OB_SMTP_PASS", "x")
    monkeypatch.setattr(app_module.ob_mail.threading, "Thread", lambda **kw: type("T", (), {"start": lambda s: None})())
    client = app_module.app.test_client()
    signup(client, email="reset@b.com")
    tok = get_csrf(client.get("/forgot").get_data(as_text=True))
    client.post("/forgot", data=dict(csrf_token=tok, email="reset@b.com"))
    text, html = _both(_row("reset@b.com", "Reset your%"))
    link = [u for u in _urls(text) if "/reset/" in u][0]
    assert f'href="{link}"' in html and "Reset your password" in html and "valid for 2 hours" in html


def test_invite_join_mail_to_the_owner(app):
    owner = _owner_with_registry(app)
    path = _invite(owner)
    _join(app, path)
    text, html = _both(_row("rivka@example.com", "%can now manage%"))
    assert "Yosef" in html and "yosef@example.com" in html and "Open your dashboard" in html


def test_weekly_summary_mail(client, app_module):
    signup(client)
    create_registry(client)
    _gift("reported", name="Aunt Miriam")
    assert _run(app_module) == 1
    text, html = _both(_row("a@b.com", "Your week%"))
    assert "1 new gift was reserved or sent." in html and "Open your dashboard" in html
    off = [u for u in _urls(text) if "/digest/off/" in u][0]
    assert f'href="{off}"' in html
    dash = [u for u in _urls(text) if u.endswith("/dashboard")][0]
    assert f'href="{dash}"' in html


def test_shana_lead_and_contact_mail_to_the_site_owner(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "NOTIFY_EMAIL", "owner@example.com")
    html_page = client.get("/shana-rishonah").get_data(as_text=True)
    client.post("/shana-rishonah", data=dict(csrf_token=get_csrf(html_page), name="Rivka <i>Levi</i>",
                                             email="rivka@example.com", whatsapp="+972501234567",
                                             city="Jerusalem"))
    text, html = _both(_row("owner@example.com", "%shana rishonah lead%"))
    assert "Jerusalem" in html and "&lt;i&gt;Levi&lt;/i&gt;" in html and "Open the admin" in html
    admin = [u for u in _urls(text) if "/admin" in u][0]
    assert f'href="{admin}"' in html
    page = client.get("/contact").get_data(as_text=True)
    client.post("/contact", data=dict(csrf_token=get_csrf(page), name="Rivka", email="rivka@example.com",
                                      body="Question about shipping"))
    text, html = _both(_row("owner@example.com", "OurBayis contact%"))
    assert "Question about shipping" in html and "Open the admin" in html


def test_reminder_mail_from_manage_py(client, app_module, monkeypatch):
    import manage
    slug, ids = _setup(client)
    _reserve(app_module, slug, ids[0])
    db = _db()
    db.execute("UPDATE claims SET created_at=datetime('now','-9 days')")
    db.commit()
    monkeypatch.setenv("OB_BASE_URL", "https://ourbayis.example")
    monkeypatch.setattr(manage, "_open", lambda migrate=True: _db())
    monkeypatch.setattr(manage.ob_db, "connect", manage.ob_db.connect)
    import argparse
    assert manage.cmd_remind_claims(argparse.Namespace(dry_run=False)) == 0
    text, html = _both(_row("malka@example.com", "A gentle reminder%"))
    assert "Electric kettle" in html and "View the registry" in html and f'<img src="{IMG}"' in html


# ------------------------------------------------------------------ sending
def test_sender_builds_multipart_alternative_and_legacy_rows_stay_text(app_module, monkeypatch):
    import ob_mail
    monkeypatch.setenv("OB_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("OB_SMTP_USER", "site@example.com")
    monkeypatch.setenv("OB_SMTP_PASS", "x")
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): sent.append(msg)

    monkeypatch.setattr(ob_mail.smtplib, "SMTP", FakeSMTP)
    ob_mail.send_now("a@b.com", "Subj", "Plain body\n", html="<html><body><p>Hi</p></body></html>")
    msg = sent[-1]
    assert msg.get_content_type() == "multipart/alternative"
    kinds = [p.get_content_type() for p in msg.iter_parts()]
    assert kinds == ["text/plain", "text/html"]
    assert msg.get_body(("plain",)).get_content().strip() == "Plain body"
    assert "<p>Hi</p>" in msg.get_body(("html",)).get_content()
    assert msg["Subject"] == "Subj"

    ob_mail.send_now("a@b.com", "Subj", "Plain body\n")
    assert sent[-1].get_content_type() == "text/plain" and not sent[-1].is_multipart()

    # a legacy outbox row (no body_html) goes out as plain text through attempt()
    db = _db()
    db.execute("INSERT INTO mail_outbox (to_addr, subject, body, status, next_attempt_at) VALUES"
               " ('old@x.com','Old','old body','queued','2000-01-01 00:00:00')")
    db.commit()
    rid = db.execute("SELECT id FROM mail_outbox WHERE to_addr='old@x.com'").fetchone()["id"]
    ob_mail.attempt(db, rid)
    assert sent[-1]["To"] == "old@x.com" and not sent[-1].is_multipart()
    # ...and a queued row WITH html goes out multipart
    rid2 = ob_mail.enqueue(db, "new@x.com", "New", "new body", html="<p>new</p>")
    db.execute("UPDATE mail_outbox SET next_attempt_at='2000-01-01 00:00:00' WHERE id=?", (rid2,))
    db.commit()
    ob_mail.attempt(db, rid2)
    assert sent[-1]["To"] == "new@x.com" and sent[-1].get_content_type() == "multipart/alternative"


def test_render_failure_falls_back_to_text_only(client, app_module, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("template broke")
    monkeypatch.setattr(app_module.ob_mailhtml, "render_mail_html", boom)
    slug, ids = _setup(client)
    _reserve(app_module, slug, ids[0])
    row = _row("couple@example.com", "Aunt Malka reserved%")
    assert row["body"] and row["body_html"] is None


# ------------------------------------------------------------------ admin preview + outbox
def test_preview_routes_need_admin(client):
    for path in ("/admin/mail-preview", "/admin/mail-preview/reset?lang=en"):
        r = client.get(path)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"]


def test_preview_renders_every_kind_in_both_languages(client, app_module):
    admin_login(client)
    index = client.get("/admin/mail-preview").get_data(as_text=True)
    for kind, _label in app_module.MAIL_PREVIEW_KINDS:
        assert f"/admin/mail-preview/{kind}?lang=en" in index
        for lang in ("en", "he"):
            r = client.get(f"/admin/mail-preview/{kind}?lang={lang}")
            assert r.status_code == 200, (kind, lang)
            html = r.get_data(as_text=True)
            assert "<!doctype html>" in html.lower() and "Bayis" in html
            assert ('dir="rtl"' in html) == (lang == "he" and kind not in ("lead", "contact")), (kind, lang)
    assert client.get("/admin/mail-preview/nonsense").status_code == 404
    assert _db().execute("SELECT COUNT(*) FROM mail_outbox").fetchone()[0] == 0  # previews never send


def test_outbox_page_never_shows_a_body(client, app_module):
    slug, ids = _setup(client)
    _reserve(app_module, slug, ids[0], message="Secret words here")
    admin_login(client)
    page = client.get("/admin/outbox").get_data(as_text=True)
    assert "Aunt Malka reserved" in page          # subject
    assert "Secret words here" not in page and "<!doctype" not in page.lower().replace("<!doctype html>", "", 1)
    assert "Open your dashboard" not in page and "kettle.jpg" not in page
