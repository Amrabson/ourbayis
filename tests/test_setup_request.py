# -*- coding: utf-8 -*-
"""/setup-cost/request: carry the ticked list into a Shana Rishonah request."""
import os
import sqlite3

from conftest import get_csrf
from test_p1 import admin_login


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _ids(app_module, n=3):
    with app_module.app.app_context():
        rows = app_module.get_db().execute(
            "SELECT id FROM catalog_items WHERE active=1 AND starter_group != ''"
            " AND price_nis > 0 ORDER BY id LIMIT ?", (n,)).fetchall()
    return [r[0] for r in rows]


def _items(ids):
    db = _db()
    return [db.execute("SELECT * FROM catalog_items WHERE id=?", (i,)).fetchone() for i in ids]


def _post(client, ids, token=True, **extra):
    client.get("/setup-cost")
    with client.session_transaction() as s:
        tok = s.get("_csrf")
    data = {f"add_{i}": "1" for i in ids}
    if token:
        data["csrf_token"] = tok
    data.update(extra)
    return client.post("/setup-cost/request", data=data)


def _session_list(client):
    with client.session_transaction() as s:
        return s.get("shana_list")


def test_post_stores_ids_and_redirects_to_request_anchor(client, app_module):
    ids = _ids(app_module)
    r = _post(client, ids)
    assert r.status_code == 302 and r.headers["Location"].endswith("/shana-rishonah#request")
    assert sorted(_session_list(client)) == sorted(ids)


def test_invalid_and_inactive_ids_dropped(client, app_module):
    ids = _ids(app_module, 2)
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("UPDATE catalog_items SET active=0 WHERE id=?", (ids[1],))
        db.commit()
    r = _post(client, [ids[0], ids[1], 99999999], **{"add_x1": "1", "add_٣": "1", "add_": "1"})
    assert r.status_code == 302
    assert _session_list(client) == [ids[0]]


def test_no_valid_ids_just_redirects(client):
    r = _post(client, [99999999])
    assert r.status_code == 302 and r.headers["Location"].endswith("/shana-rishonah#request")
    assert _session_list(client) is None


def test_csrf_enforced_and_honeypot(client, app_module):
    ids = _ids(app_module)
    assert _post(client, ids, token=False).status_code in (400, 403)
    assert _session_list(client) is None
    r = _post(client, ids, website="spam")
    assert r.status_code == 302 and _session_list(client) is None


def test_cap_respected(client, app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        ids = [r[0] for r in db.execute("SELECT id FROM catalog_items WHERE active=1 ORDER BY id")]
    assert len(ids) > 60
    _post(client, ids)
    assert len(_session_list(client)) == 60


def test_shana_page_summary_en_and_he(client, app_module):
    ids = _ids(app_module)
    total = sum(r["price_nis"] or 0 for r in _items(ids))
    _post(client, ids)
    en = client.get("/shana-rishonah?lang=en").get_data(as_text=True)
    assert f"Your list from the cost calculator: 3 items, about ₪{total:,} at store prices" in en
    assert 'name="with_list"' in en
    he = client.get("/shana-rishonah?lang=he").get_data(as_text=True)
    assert "הרשימה שלכם ממחשבון העלויות: 3" in he
    assert f"₪{total:,}" in he


def test_no_list_no_summary(client):
    html = client.get("/shana-rishonah").get_data(as_text=True)
    assert "cost calculator" not in html and 'name="with_list"' not in html


def test_remove_list_clears_session(client, app_module):
    _post(client, _ids(app_module))
    html = client.get("/shana-rishonah").get_data(as_text=True)
    tok = get_csrf(html)
    assert client.post("/shana-rishonah/list/remove", data={}).status_code in (400, 403)
    assert _session_list(client) is not None
    r = client.post("/shana-rishonah/list/remove", data=dict(csrf_token=tok))
    assert r.status_code == 302 and r.headers["Location"].endswith("#request")
    assert _session_list(client) is None
    assert 'name="with_list"' not in client.get("/shana-rishonah").get_data(as_text=True)


def _submit(client, with_list=True):
    html = client.get("/shana-rishonah").get_data(as_text=True)
    data = dict(csrf_token=get_csrf(html), name="Dana", email="dana@example.com")
    if with_list:
        data["with_list"] = "1"
    return client.post("/shana-rishonah", data=data)


def test_lead_saves_list_emails_it_and_clears_session(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "NOTIFY_EMAIL", "owner@example.com")
    ids = _ids(app_module)
    items = _items(ids)
    _post(client, ids)
    assert _submit(client).status_code == 302
    row = _db().execute("SELECT * FROM shana_requests").fetchone()
    wl = row["wanted_list"]
    total = sum(r["price_nis"] or 0 for r in items)
    for r in items:
        assert f"{r['name']} — ₪{r['price_nis']:,} ({r['store'] or 'store'})" in wl
    assert f"Total at store prices: ₪{total:,}" in wl and "Items: 3" in wl
    assert row["notes"] == ""
    body = _db().execute("SELECT body FROM mail_outbox WHERE to_addr='owner@example.com'").fetchone()[0]
    assert items[0]["name"] in body and f"₪{total:,}" in body
    assert _session_list(client) is None
    admin_login(client)
    page = client.get(f"/admin/lead/{row['id']}").get_data(as_text=True)
    assert "List from the cost calculator" in page and "Copy list" in page and "data-copy=" in page


def test_lead_without_marker_has_empty_list(client, app_module):
    _post(client, _ids(app_module))
    assert _submit(client, with_list=False).status_code == 302
    assert _db().execute("SELECT wanted_list FROM shana_requests").fetchone()[0] == ""


def test_dashboard_prefill_still_works(client, app_module):
    from conftest import signup, create_registry
    signup(client)
    create_registry(client)
    html = client.get("/shana-rishonah").get_data(as_text=True)
    assert 'value="a@b.com"' in html


def test_absurdly_long_id_is_ignored_not_a_500(client, app_module):
    page = client.get("/setup-cost").get_data(as_text=True)
    data = {"csrf_token": get_csrf(page), "add_" + "9" * 34: "on", "add_" + "9" * 5000: "on"}
    assert client.post("/setup-cost/request", data=data).status_code == 302
    assert client.post("/setup-cost/start", data=data).status_code == 302
