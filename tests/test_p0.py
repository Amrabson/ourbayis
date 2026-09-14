# -*- coding: utf-8 -*-
"""Phase 1 (P0) test suite. See SPEC_V3.md "Definition of done per phase"."""
import os
import re
import shutil
import threading
import time

import pytest

from conftest import get_csrf, get_form_key, signup, create_registry, add_item

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ migrations / check
def test_fresh_install_migrates(app_module):
    import ob_db
    db = app_module.get_db.__wrapped__ if False else None  # unused, kept simple below
    with app_module.app.app_context():
        db = app_module.get_db()
        n = db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        assert n == len(ob_db.MIGRATIONS)
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_manage_check_on_fresh_db(app_module, tmp_path, monkeypatch):
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, os.path.join(BASE, "manage.py"), "create-admin", "owner"],
        cwd=BASE, env={**os.environ, "OB_DB_PATH": os.environ["OB_DB_PATH"],
                       "OB_ADMIN_PASSWORD": "a-very-long-admin-password"},
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [sys.executable, os.path.join(BASE, "manage.py"), "check"],
        cwd=BASE, env={**os.environ, "OB_DB_PATH": os.environ["OB_DB_PATH"]},
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


# ------------------------------------------------------------------ snapshot migration
def test_snapshot_migration_legacy_claims(tmp_path):
    import ob_db
    snap_src = os.path.join(BASE, "backups", "ourbayis-snapshot-2026-09-14.db")
    if not os.path.exists(snap_src):
        pytest.skip("snapshot db not present")
    copy = tmp_path / "snapshot-copy.db"
    shutil.copy(snap_src, copy)
    src_hash_before = os.path.getsize(snap_src)  # never modify the original
    db = ob_db.connect(str(copy))
    before = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    ob_db.migrate(db)
    after = db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    assert after == before  # never deletes claims
    rows = {r["amount"]: r for r in db.execute(
        "SELECT amount, amount_minor, currency, status, legacy FROM claims")}
    if "₪180" in rows:
        assert rows["₪180"]["amount_minor"] == 18000
        assert rows["₪180"]["currency"] == "ILS"
    if "$180" in rows:
        assert rows["$180"]["amount_minor"] == 18000
        assert rows["$180"]["currency"] == "USD"
    assert all(r["legacy"] == 1 for r in rows.values())
    assert os.path.getsize(snap_src) == src_hash_before
    db.close()


# ------------------------------------------------------------------ ob_security
def test_safe_next():
    from ob_security import safe_next
    assert safe_next("/dashboard") == "/dashboard"
    assert safe_next("//evil.com") is None
    assert safe_next("/\\evil.com") is None
    assert safe_next("https://x") is None
    assert safe_next("%2F%2Fevil") is None
    assert safe_next("javascript:alert(1)") is None
    assert safe_next("") is None
    assert safe_next(None) is None


def test_classify_pay_url():
    from ob_security import classify_pay_url
    assert classify_pay_url("paypal.me/x")[0] == "paypal"
    assert classify_pay_url("https://www.paypal.com/paypalme/x")[0] == "paypal"
    assert classify_pay_url("https://buy.stripe.com/abc")[0] == "stripe"
    with pytest.raises(ValueError):
        classify_pay_url("https://paypal.me.evil.com/x")
    with pytest.raises(ValueError):
        classify_pay_url("https://evil.com/paypal.me/x")
    with pytest.raises(ValueError):
        classify_pay_url("http://127.0.0.1/")


def test_parse_legacy_amount():
    from ob_money import parse_legacy_amount
    assert parse_legacy_amount("₪180") == (18000, "ILS")
    assert parse_legacy_amount("$180") == (18000, "USD")
    assert parse_legacy_amount("about 180 bucks") is None
    assert parse_legacy_amount("") is None


# ------------------------------------------------------------------ reservation flow
def _setup_registry(app_module, price=300, qty=1):
    client = app_module.app.test_client()
    signup(client)
    create_registry(client)
    add_item(client, price_nis=str(price))
    with app_module.app.app_context():
        db = app_module.get_db()
        reg = db.execute("SELECT * FROM registries").fetchone()
        item = db.execute("SELECT * FROM registry_items").fetchone()
        if qty != 1:
            db.execute("UPDATE registry_items SET qty_wanted=? WHERE id=?", (qty, item["id"]))
    return client, reg, item


def _claim(app_module, slug, item_id, name="Guest", form_key=None, **extra):
    guest = app_module.app.test_client()
    r = guest.get(f"/r/{slug}")
    html = r.get_data(as_text=True)
    tok = get_csrf(html)
    fk = form_key or get_form_key(html)
    data = dict(csrf_token=tok, form_key=fk, guest_name=name, give="buy")
    data.update(extra)
    return guest.post(f"/r/{slug}/claim/{item_id}", data=data, follow_redirects=False), fk


def test_claim_and_guest_manage(app_module):
    client, reg, item = _setup_registry(app_module)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    assert resp.status_code == 302
    assert "/g/" in resp.headers["Location"]
    token = resp.headers["Location"].rsplit("/", 1)[-1]
    guest = app_module.app.test_client()
    r = guest.get(f"/g/{token}")
    assert r.status_code == 200
    assert b"guest" not in r.data  # sanity: no stray debug text


def test_duplicate_form_key_one_claim(app_module):
    client, reg, item = _setup_registry(app_module, qty=5)
    guest = app_module.app.test_client()
    r = guest.get(f"/r/{reg['slug']}")
    html = r.get_data(as_text=True)
    tok, fk = get_csrf(html), get_form_key(html)
    data = dict(csrf_token=tok, form_key=fk, guest_name="G", give="buy")
    guest.post(f"/r/{reg['slug']}/claim/{item['id']}", data=data)
    guest.post(f"/r/{reg['slug']}/claim/{item['id']}", data=data)
    with app_module.app.app_context():
        n = app_module.get_db().execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    assert n == 1


def test_qty_over_left_clamped(app_module):
    client, reg, item = _setup_registry(app_module, qty=2)
    resp, _ = _claim(app_module, reg["slug"], item["id"], qty="99")
    with app_module.app.app_context():
        claim = app_module.get_db().execute("SELECT * FROM claims").fetchone()
    assert claim["qty"] == 2  # clamped to what's left, never rejected outright


def test_concurrent_last_item_reservation(app_module):
    """Two guests race for the last unit of a qty=1 item — exactly one wins."""
    client, reg, item = _setup_registry(app_module, qty=1)
    results = []
    barrier = threading.Barrier(2)

    def worker(name):
        guest = app_module.app.test_client()
        r = guest.get(f"/r/{reg['slug']}")
        html = r.get_data(as_text=True)
        tok, fk = get_csrf(html), name + "-" + (get_form_key(html) or "")
        barrier.wait()
        resp = guest.post(f"/r/{reg['slug']}/claim/{item['id']}",
                          data=dict(csrf_token=tok, form_key=fk, guest_name=name, give="buy"))
        results.append(resp)

    threads = [threading.Thread(target=worker, args=(f"G{i}",)) for i in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    with app_module.app.app_context():
        n = app_module.get_db().execute(
            "SELECT COALESCE(SUM(qty),0) FROM claims WHERE status IN"
            " ('reserved','reported','received')").fetchone()[0]
    assert n == 1


def test_cancel_report_late_report_transitions(app_module):
    client, reg, item = _setup_registry(app_module)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    token = resp.headers["Location"].rsplit("/", 1)[-1]
    guest = app_module.app.test_client()
    r = guest.get(f"/g/{token}")
    tok = get_csrf(r.get_data(as_text=True))
    r = guest.post(f"/g/{token}/report", data=dict(csrf_token=tok), follow_redirects=True)
    assert r.status_code == 200
    with app_module.app.app_context():
        claim = app_module.get_db().execute("SELECT * FROM claims").fetchone()
    assert claim["status"] == "reported"

    # cancel is now invalid (status is 'reported', not reserved/expired)
    r = guest.get(f"/g/{token}")
    tok = get_csrf(r.get_data(as_text=True))
    r = guest.post(f"/g/{token}/cancel", data=dict(csrf_token=tok), follow_redirects=True)
    with app_module.app.app_context():
        claim = app_module.get_db().execute("SELECT * FROM claims").fetchone()
    assert claim["status"] == "reported"  # unchanged


def test_expired_claim_frees_quantity(app_module):
    client, reg, item = _setup_registry(app_module, qty=1)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("UPDATE claims SET expires_at='2000-01-01 00:00:00'")
        left = item["qty_wanted"] - app_module.item_claim_counts(reg["id"]).get(item["id"], 0)
    assert left == 1  # freed up


def test_get_guest_manage_never_mutates(app_module):
    client, reg, item = _setup_registry(app_module)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    token = resp.headers["Location"].rsplit("/", 1)[-1]
    guest = app_module.app.test_client()
    with app_module.app.app_context():
        before = dict(app_module.get_db().execute("SELECT * FROM claims").fetchone())
    guest.get(f"/g/{token}")
    guest.get(f"/g/{token}")
    with app_module.app.app_context():
        after = dict(app_module.get_db().execute("SELECT * FROM claims").fetchone())
    assert before == after


def test_bad_token_404(app_module):
    guest = app_module.app.test_client()
    r = guest.get("/g/this-token-does-not-exist")
    assert r.status_code == 404


def test_owner_cannot_confirm_other_owners_claim(app_module):
    client, reg, item = _setup_registry(app_module)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    with app_module.app.app_context():
        claim = app_module.get_db().execute("SELECT * FROM claims").fetchone()

    other = app_module.app.test_client()
    signup(other, email="other@b.com")
    create_registry(other, couple="Other Couple")
    r = other.get("/dashboard")
    tok = get_csrf(r.get_data(as_text=True))
    r = other.post(f"/claim/{claim['id']}/confirm", data=dict(csrf_token=tok))
    assert r.status_code == 404


def test_item_delete_with_claims_archives(app_module):
    client, reg, item = _setup_registry(app_module)
    _claim(app_module, reg["slug"], item["id"])
    r = client.get("/registry/items")
    tok = get_csrf(r.get_data(as_text=True))
    client.post(f"/registry/items/{item['id']}/update",
               data=dict(csrf_token=tok, delete="1"), follow_redirects=True)
    with app_module.app.app_context():
        db = app_module.get_db()
        row = db.execute("SELECT * FROM registry_items WHERE id=?", (item["id"],)).fetchone()
        n_claims = db.execute("SELECT COUNT(*) FROM claims WHERE item_id=?", (item["id"],)).fetchone()[0]
    assert row is not None and row["archived"] == 1
    assert n_claims == 1


def test_qty_reduction_below_committed_rejected(app_module):
    client, reg, item = _setup_registry(app_module, qty=3)
    _claim(app_module, reg["slug"], item["id"], qty="2")
    r = client.get("/registry/items")
    tok = get_csrf(r.get_data(as_text=True))
    client.post(f"/registry/items/{item['id']}/update",
               data=dict(csrf_token=tok, qty_wanted="1"), follow_redirects=True)
    with app_module.app.app_context():
        row = app_module.get_db().execute(
            "SELECT * FROM registry_items WHERE id=?", (item["id"],)).fetchone()
    assert row["qty_wanted"] == 3  # unchanged — rejected (2 already committed > 1)


def test_registry_page_html_has_no_guest_pii(app_module):
    client, reg, item = _setup_registry(app_module)
    _claim(app_module, reg["slug"], item["id"], name="SuperSecretGuestName")
    r = app_module.app.test_client().get(f"/r/{reg['slug']}")
    html = r.get_data(as_text=True)
    assert "SuperSecretGuestName" not in html
    assert "@b.com" not in html  # owner's own email also shouldn't leak


# ------------------------------------------------------------------ auth / reset
def test_logout_requires_post(app_module):
    client = app_module.app.test_client()
    signup(client)
    r = client.get("/logout")
    assert r.status_code == 405


def test_reset_token_single_use_and_session_invalidation(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "SMTP_HOST", "smtp.example.com")
    client = app_module.app.test_client()
    signup(client, email="reset@b.com")
    with app_module.app.app_context():
        db = app_module.get_db()
        import ob_security
        token = ob_security.new_token()
        from datetime import datetime, timedelta
        db.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES"
            " ((SELECT id FROM users WHERE email='reset@b.com'), ?, ?)",
            (ob_security.hash_token(token), (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")))

    r = client.get(f"/reset/{token}")
    assert r.status_code == 200
    tok = get_csrf(r.get_data(as_text=True))
    r = client.post(f"/reset/{token}", data=dict(
        csrf_token=tok, password="newpassword1", password2="newpassword1"), follow_redirects=True)
    assert r.status_code == 200

    # old session (uid + old sv) must now be treated as logged out
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]

    # token is single-use
    r2 = app_module.app.test_client().get(f"/reset/{token}")
    assert r2.status_code == 302  # redirected to /forgot — invalid/used


# ------------------------------------------------------------------ rate limiting / csv
def test_rate_limit_429_with_retry_after(app_module):
    client = app_module.app.test_client()
    for _ in range(6):
        r = client.post("/contact", data=dict(csrf_token=get_csrf(
            client.get("/contact").get_data(as_text=True)), body="hi " * 3))
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "120"


def test_csv_safety():
    from app import csv_safe
    assert csv_safe("=cmd|'/c calc'!A1").startswith("'=")
    assert csv_safe("+1+1").startswith("'+")
    assert csv_safe("Normal Name") == "Normal Name"
    assert csv_safe(None) == ""


# ------------------------------------------------------------------ bilingual smoke
@pytest.mark.parametrize("lang", ["en", "he"])
def test_public_pages_render(app_module, lang):
    client = app_module.app.test_client()
    for path in ("/", "/catalog", f"/find", "/signup", "/login"):
        r = client.get(f"{path}?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        if lang == "he":
            assert 'dir="rtl"' in html
        else:
            assert 'dir="ltr"' in html


def test_registry_and_guest_page_bilingual(app_module):
    client, reg, item = _setup_registry(app_module)
    resp, _ = _claim(app_module, reg["slug"], item["id"])
    token = resp.headers["Location"].rsplit("/", 1)[-1]
    for lang in ("en", "he"):
        r = app_module.app.test_client().get(f"/r/{reg['slug']}?lang={lang}")
        assert r.status_code == 200
        r = app_module.app.test_client().get(f"/g/{token}?lang={lang}")
        assert r.status_code == 200


def test_dashboard_bilingual(app_module):
    client, reg, item = _setup_registry(app_module)
    for lang in ("en", "he"):
        r = client.get(f"/dashboard?lang={lang}")
        assert r.status_code == 200


def test_error_pages(app_module):
    client = app_module.app.test_client()
    r = client.get("/this-route-does-not-exist")
    assert r.status_code == 404
    html = r.get_data(as_text=True)
    assert "OurBayis" in html
