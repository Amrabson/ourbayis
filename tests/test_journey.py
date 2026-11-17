# -*- coding: utf-8 -*-
"""Whole-journey checks (2026-11-17): the couple and the guest walked end to end, plus regression tests for the
small friction fixes found on the way. Expectations come from the DB at test time, never from fixed seed contents."""
import os
import re
import sqlite3

import i18n
from conftest import create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _couple(client, pay=True, public=True):
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    db = _db()
    if pay:
        db.execute("UPDATE registries SET paypal_url='https://paypal.me/dinayossi'")
    if public:
        db.execute("UPDATE registries SET visibility='public'")
    db.commit()
    return db.execute("SELECT slug FROM registries").fetchone()["slug"]


def _add_catalog(client, n=3):
    """Add the first n active catalog items the plain way; returns the registry_items ids."""
    db = _db()
    ids = [r["id"] for r in db.execute("SELECT id FROM catalog_items WHERE active=1 AND url<>'' ORDER BY id LIMIT ?", (n,))]
    page = client.get("/registry/items").get_data(as_text=True)
    for cid in ids:
        client.post("/registry/items/add", data=dict(csrf_token=get_csrf(page), catalog_id=cid))
    return [r["id"] for r in db.execute("SELECT id FROM registry_items ORDER BY id")]


# ------------------------------------------------------------------ owner view of the guest page
def test_owner_sees_a_banner_with_a_way_back_guests_do_not(client, app_module):
    slug = _couple(client)
    for lang in ("en", "he"):
        page = client.get(f"/r/{slug}?preview=1&lang={lang}").get_data(as_text=True)
        assert 'owner-notice' in page and i18n.t("owner_view_note", lang) in page
        assert i18n.t("back_to_dashboard", lang) in page and 'href="/dashboard"' in page
        guest = app_module.app.test_client().get(f"/r/{slug}?lang={lang}").get_data(as_text=True)
        assert 'owner-notice' not in guest


def test_view_as_guest_link_counts_as_the_preview_step(client):
    slug = _couple(client)
    dash = client.get("/dashboard?lang=en").get_data(as_text=True)
    link = re.search(r'<a class="link-arrow" href="([^"]+)">See your registry as guests see it</a>', dash).group(1)
    assert link == f"/r/{slug}?preview=1"
    assert "previewed_at" not in (_db().execute("SELECT preferences_json FROM registries").fetchone()[0] or "")
    client.get(link)
    assert "previewed_at" in _db().execute("SELECT preferences_json FROM registries").fetchone()[0]


def test_items_and_share_pages_lead_back_to_the_dashboard(client):
    _couple(client)
    for path in ("/registry/items", "/registry/share"):
        for lang in ("en", "he"):
            page = client.get(f"{path}?lang={lang}").get_data(as_text=True)
            assert f'href="/dashboard">{i18n.t("back_to_dashboard", lang)}' in page, (path, lang)


# ------------------------------------------------------------------ removing a gift says so
def test_removing_a_gift_confirms(client):
    _couple(client)
    _add_catalog(client, 2)
    for lang in ("en", "he"):
        ids = [r["id"] for r in _db().execute("SELECT id FROM registry_items ORDER BY id")]
        page = client.get(f"/registry/items?lang={lang}").get_data(as_text=True)
        r = client.post(f"/registry/items/{ids[0]}/update?lang={lang}", data=dict(csrf_token=get_csrf(page), delete="1"),
                        follow_redirects=True)
        assert r.status_code == 200 and i18n.t("item_removed", lang) in r.get_data(as_text=True)
    assert _db().execute("SELECT COUNT(*) FROM registry_items").fetchone()[0] == 0


# ------------------------------------------------------------------ "Build my list" keeps the answers
def test_quiz_start_with_nothing_ticked_comes_back_with_the_draft(client):
    page = client.get("/build-my-list?start=partly&bed=singles&host=most&kitchen=one&quality=nicer&yomtov=yes").get_data(as_text=True)
    for key, val in dict(start="partly", bed="singles", host="most", kitchen="one", quality="nicer", yomtov="yes").items():
        assert f'name="a_{key}" value="{val}"' in page
    r = client.post("/build-my-list/start", data=dict(
        csrf_token=get_csrf(page), a_start="partly", a_bed="singles", a_host="most",
        a_kitchen="one", a_quality="nicer", a_yomtov="yes"))
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "start=partly" in loc and "bed=singles" in loc and "yomtov=yes" in loc
    back = client.get(loc).get_data(as_text=True)
    assert 'name="add_' in back  # the draft list is shown again, not an empty quiz


def test_quiz_start_with_junk_answers_falls_back_to_defaults(client):
    page = client.get("/build-my-list?start=empty").get_data(as_text=True)
    r = client.post("/build-my-list/start", data=dict(csrf_token=get_csrf(page), a_start="<x>"))
    assert r.status_code == 302 and "<x>" not in r.headers["Location"] and "%3Cx" not in r.headers["Location"]


# ------------------------------------------------------------------ the happy path, couple then guest
def test_end_to_end_couple_and_guest(client, app_module):
    home = client.get("/")
    assert home.status_code == 200 and "Create your registry" in home.get_data(as_text=True)
    sp = client.get("/signup")
    assert sp.status_code == 200
    r = client.post("/signup", data=dict(csrf_token=get_csrf(sp.get_data(as_text=True)), name="Dina Levi",
                                         email="couple@example.com", password="password1", password2="password1"),
                    follow_redirects=True)
    assert r.status_code == 200 and "Set up your registry" in r.get_data(as_text=True)
    r = create_registry(client, couple="Dina & Yossi")
    assert r.status_code == 200 and "Your registry is live" in r.get_data(as_text=True)
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "Next step" in dash and "Put some gifts on the registry" in dash and "Pick from the starter lists" in dash

    starter = client.get("/registry/items/starter")
    assert starter.status_code == 200
    page = starter.get_data(as_text=True)
    picks = re.findall(r'name="add_(\d+)"', page)[:3]
    assert len(picks) == 3
    r = client.post("/registry/items/starter", data=dict([("csrf_token", get_csrf(page))] + [(f"add_{p}", "1") for p in picks]),
                    follow_redirects=True)
    assert r.status_code == 200 and "On your registry (3)" in r.get_data(as_text=True)

    db = _db()
    reg = db.execute("SELECT * FROM registries").fetchone()
    edit = client.get("/registry/edit")
    assert edit.status_code == 200
    r = client.post("/registry/edit", data=dict(
        csrf_token=get_csrf(edit.get_data(as_text=True)), title=reg["title"], couple_names="Dina & Yossi",
        event_type="wedding", delivery_note="Herzl 5, Jerusalem", paypal_url="https://paypal.me/dinayossi",
        current_password="password1", visibility="public"), follow_redirects=True)
    assert r.status_code == 200 and "Registry saved." in r.get_data(as_text=True)
    slug = db.execute("SELECT slug FROM registries").fetchone()["slug"]
    assert client.get("/registry/share").status_code == 200
    prev = client.get(f"/r/{slug}?preview=1")
    assert prev.status_code == 200 and "owner-notice" in prev.get_data(as_text=True)

    items_page = client.get("/registry/items").get_data(as_text=True)
    r = client.post("/registry/items/fund", data=dict(csrf_token=get_csrf(items_page), name="Sefarim fund", goal="1000"),
                    follow_redirects=True)
    assert "Fund added" in r.get_data(as_text=True)

    guest = app_module.app.test_client()
    reg_page = guest.get(f"/r/{slug}")
    assert reg_page.status_code == 200
    body = reg_page.get_data(as_text=True)
    assert "Dina &amp; Yossi" in body and "Send a cash gift" in body
    store_item = db.execute("SELECT id, name FROM registry_items WHERE url<>'' AND chip_in=0 ORDER BY id").fetchone()
    r = guest.post(f"/r/{slug}/claim/{store_item['id']}", data=dict(
        csrf_token=get_csrf(body), form_key=get_form_key(body), guest_name="Uncle Moshe",
        guest_email="moshe@example.com", message="Mazel tov!", qty="1", give="store"))
    assert r.status_code == 302 and r.headers["Location"].startswith("/g/")
    token_path = r.headers["Location"].split("?")[0]
    gpage = guest.get(token_path)
    gbody = gpage.get_data(as_text=True)
    assert gpage.status_code == 200 and "Herzl 5, Jerusalem" in gbody and "Mazel tov!" in gbody
    assert "bought/sent it" in gbody
    r = guest.post(token_path + "/report", data=dict(csrf_token=get_csrf(gbody), report_note="Sent Sunday"),
                   follow_redirects=True)
    assert r.status_code == 200 and "Thanks for letting us know!" in r.get_data(as_text=True)

    body = guest.get(f"/r/{slug}").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/cash", data=dict(csrf_token=get_csrf(body), form_key="k-cash", guest_name="Cousin Dov",
                                                amount="180", currency="ILS", message="Mazel tov"), follow_redirects=True)
    assert r.status_code == 200 and "Open PayPal" in r.get_data(as_text=True)
    fund = db.execute("SELECT id FROM registry_items WHERE chip_in=1").fetchone()
    body = guest.get(f"/r/{slug}").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/claim/{fund['id']}", data=dict(csrf_token=get_csrf(body), form_key="k-fund", guest_name="Leah",
                                                              give="chip", chip_amount="100"), follow_redirects=True)
    assert r.status_code == 200 and "toward Sefarim fund" in r.get_data(as_text=True)
    r = guest.post(f"/r/{slug}/bracha", data=dict(csrf_token=get_csrf(body), form_key="k-br", guest_name="Zeidy",
                                                  message="Bracha v'hatzlacha"), follow_redirects=True)
    assert r.status_code == 200 and "Your bracha is on its way" in r.get_data(as_text=True)

    mails = {m["to_addr"]: m for m in db.execute("SELECT * FROM mail_outbox")}
    assert "moshe@example.com" in mails and token_path in mails["moshe@example.com"]["body"]
    assert any("Uncle Moshe" in m["subject"] for m in db.execute("SELECT * FROM mail_outbox WHERE to_addr='couple@example.com'"))

    dash = client.get("/dashboard").get_data(as_text=True)
    assert "Needs you" in dash and "Uncle Moshe" in dash and "Cousin Dov" in dash
    claim = db.execute("SELECT id FROM claims WHERE guest_name='Uncle Moshe'").fetchone()
    r = client.post(f"/claim/{claim['id']}/confirm", data=dict(csrf_token=get_csrf(dash)), follow_redirects=True)
    assert "Marked as received" in r.get_data(as_text=True)
    thanks = client.get("/dashboard/thanks")
    assert thanks.status_code == 200 and "Zeidy" in thanks.get_data(as_text=True)
    keep = client.get("/dashboard/keepsake")
    assert keep.status_code == 200 and "Mazel tov" in keep.get_data(as_text=True)
    r = client.post("/registry/close", data=dict(csrf_token=get_csrf(dash)), follow_redirects=True)
    assert "The registry is closed" in r.get_data(as_text=True)
    closed = guest.get(f"/r/{slug}").get_data(as_text=True)
    assert "closed their registry" in closed and "Leave them a bracha" in closed
    assert guest.get(token_path).status_code == 200
