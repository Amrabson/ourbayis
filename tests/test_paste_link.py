# -*- coding: utf-8 -*-
"""Paste a link from any store: POST /registry/items/lookup prefills the custom gift form.
ob_linkinfo.lookup is always monkeypatched here, so no test touches the network."""
import html as htmllib
import re

import pytest

from conftest import add_item, create_registry, get_csrf, signup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def info(**kw):
    base = {"ok": True, "error": None, "url": "https://www.ksp.co.il/web/item/123", "host": "ksp.co.il",
            "name": "Philips Air Fryer", "price": "499.90", "currency": "ILS",
            "image": "https://img.ksp.co.il/a.jpg", "brand": "Philips", "site_name": "KSP Store"}
    base.update(kw)
    return base


@pytest.fixture
def fake(app_module, monkeypatch):
    calls = []
    state = {"result": info()}

    def _lookup(url, **kw):
        calls.append(url)
        return dict(state["result"])
    monkeypatch.setattr(app_module.ob_linkinfo, "lookup", _lookup)
    return type("Fake", (), {"calls": calls, "set": staticmethod(lambda **kw: state.update(result=info(**kw))),
                             "raw": staticmethod(lambda d: state.update(result=d))})


@pytest.fixture
def couple(client):
    signup(client)
    create_registry(client)
    return client


def _count(app_module):
    with app_module.app.app_context():
        return app_module.get_db().execute("SELECT COUNT(*) FROM registry_items").fetchone()[0]


def lookup(client, link="https://www.ksp.co.il/web/item/123", csrf=True, follow=True, path=""):
    tok = get_csrf(client.get("/registry/items" + path).get_data(as_text=True))
    data = {"link": link}
    if csrf:
        data["csrf_token"] = tok
    return client.post("/registry/items/lookup", data=data, follow_redirects=follow)


def field(page, name):
    """value of the custom-form input called `name` (the one inside the items_add form)"""
    form = page[page.index('action="/registry/items/add"'):]
    form = form[:form.index("</form>")]
    m = re.search(r'<input name="%s"[^>]*?value="([^"]*)"' % name, form)
    return htmllib.unescape(m.group(1)) if m else None


def custom_form(page):
    i = page.index('id="custom"')
    return page[i:]


def test_login_required(client, fake):
    tok = get_csrf(client.get("/login").get_data(as_text=True))
    r = client.post("/registry/items/lookup", data={"link": "https://ksp.co.il/x", "csrf_token": tok})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert fake.calls == []


def test_csrf_enforced(couple, fake):
    r = lookup(couple, csrf=False)
    assert r.status_code == 400
    assert fake.calls == []


def test_get_never_fetches(couple, fake):
    assert couple.get("/registry/items/lookup").status_code == 405
    couple.get("/registry/items")
    assert fake.calls == []


def test_success_prefills_and_saves_nothing_until_add(couple, app_module, fake):
    before = _count(app_module)
    r = lookup(couple)
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Filled in from ksp.co.il. Check the details, then add it." in page
    assert field(page, "name") == "Philips Air Fryer"
    assert field(page, "url") == "https://www.ksp.co.il/web/item/123"
    assert field(page, "store") == "KSP"
    assert field(page, "price_nis") == "500"
    assert field(page, "image") == "https://img.ksp.co.il/a.jpg"
    assert field(page, "name_he") == ""
    assert 'loading="lazy" referrerpolicy="no-referrer"' in custom_form(page)
    assert _count(app_module) == before
    # now the couple presses Add with what the form holds
    tok = get_csrf(page)
    couple.post("/registry/items/add", data=dict(
        csrf_token=tok, name=field(page, "name"), url=field(page, "url"), store=field(page, "store"),
        price_nis=field(page, "price_nis"), image=field(page, "image")))
    assert _count(app_module) == before + 1
    with app_module.app.app_context():
        row = app_module.get_db().execute("SELECT * FROM registry_items ORDER BY id DESC LIMIT 1").fetchone()
    assert row["image"] == "https://img.ksp.co.il/a.jpg"
    assert row["url"] == "https://www.ksp.co.il/web/item/123"
    assert row["price_nis"] == 500 and row["store"] == "KSP"


def test_refresh_does_not_refetch(couple, fake):
    lookup(couple)
    assert len(fake.calls) == 1
    second = couple.get("/registry/items").get_data(as_text=True)
    assert len(fake.calls) == 1
    assert field(second, "name") in (None, "")       # prefill is shown once


def test_ils_price_rounds(couple, fake):
    fake.set(price="1234.50")
    assert field(lookup(couple).get_data(as_text=True), "price_nis") == "1235"
    fake.set(price="1234.49")
    assert field(lookup(couple).get_data(as_text=True), "price_nis") == "1234"


def test_usd_price_converted_with_notice(couple, fake):
    fake.set(price="48", currency="USD", url="https://example.com/p", host="example.com", site_name="Example Shop")
    page = lookup(couple).get_data(as_text=True)
    assert field(page, "price_nis") == str(round(48 * 3.7))   # OB_RATES pinned at 3.7 in conftest
    assert "Price converted from $48 — check it." in page
    assert field(page, "store") == "Example Shop"


def test_unknown_or_missing_currency_leaves_price_empty(couple, fake):
    for cur in ("XYZ", None):
        fake.set(price="48", currency=cur)
        page = lookup(couple).get_data(as_text=True)
        assert field(page, "price_nis") == ""
        assert "converted" not in page
        assert field(page, "name") == "Philips Air Fryer"


def test_fetch_failed_keeps_url_and_store(couple, fake):
    fake.raw({"ok": False, "error": "fetch_failed", "url": "https://www.ksp.co.il/web/item/9", "host": "ksp.co.il",
              "name": None, "price": None, "currency": None, "image": None, "brand": None, "site_name": None})
    page = lookup(couple, "https://www.ksp.co.il/web/item/9").get_data(as_text=True)
    assert "We couldn&#39;t read that page, so we kept the link." in page
    assert field(page, "url") == "https://www.ksp.co.il/web/item/9"
    assert field(page, "store") == "KSP"
    assert field(page, "name") == ""


@pytest.mark.parametrize("err", ["bad_url", "blocked_host"])
def test_bad_url_prefills_nothing(couple, fake, err):
    fake.raw({"ok": False, "error": err, "url": "http://localhost/x", "host": "localhost", "name": None,
              "price": None, "currency": None, "image": None, "brand": None, "site_name": None})
    page = lookup(couple, "http://localhost/x").get_data(as_text=True)
    assert "That doesn&#39;t look like a store link." in page
    assert field(page, "url") == "" and field(page, "name") == "" and field(page, "store") == ""


def test_hebrew_name_fills_both(couple, fake):
    fake.set(name="מיקסר קיצ'ן אייד")
    page = lookup(couple).get_data(as_text=True)
    assert field(page, "name") == "מיקסר קיצ'ן אייד"
    assert field(page, "name_he") == "מיקסר קיצ'ן אייד"


def test_overlong_cleaned_url_falls_back_to_pasted_link(couple, fake):
    fake.set(url="https://www.ksp.co.il/web/item/" + "a" * 600)
    page = lookup(couple, "https://www.ksp.co.il/web/item/1").get_data(as_text=True)
    assert field(page, "url") == "https://www.ksp.co.il/web/item/1"
    assert "Filled in from" in page


def test_overlong_everything_leaves_url_empty_with_message(couple, fake):
    long = "https://www.ksp.co.il/web/item/" + "a" * 600
    fake.set(url=long)
    page = lookup(couple, long).get_data(as_text=True)
    assert field(page, "url") == ""
    assert "We couldn&#39;t read that page" in page


def test_non_https_image_dropped_on_save(couple, app_module):
    tok = get_csrf(couple.get("/registry/items").get_data(as_text=True))
    couple.post("/registry/items/add", data=dict(
        csrf_token=tok, name="Lamp", url="https://example.com/l", image="http://example.com/l.jpg"))
    couple.post("/registry/items/add", data=dict(
        csrf_token=tok, name="Lamp2", url="https://example.com/l2", image="javascript:alert(1)"))
    with app_module.app.app_context():
        rows = app_module.get_db().execute("SELECT image FROM registry_items").fetchall()
    assert [r["image"] for r in rows] == ["", ""]


def test_item_edit_can_remove_picture(couple, app_module):
    tok = get_csrf(couple.get("/registry/items").get_data(as_text=True))
    couple.post("/registry/items/add", data=dict(
        csrf_token=tok, name="Lamp", url="https://example.com/l", image="https://example.com/l.jpg"))
    with app_module.app.app_context():
        iid = app_module.get_db().execute("SELECT id FROM registry_items").fetchone()["id"]
    page = couple.get(f"/registry/items/{iid}/edit").get_data(as_text=True)
    assert 'name="image"' in page and "https://example.com/l.jpg" in page
    couple.post(f"/registry/items/{iid}/edit", data=dict(
        csrf_token=get_csrf(page), name="Lamp", url="https://example.com/l", image="", qty_wanted="1"))
    with app_module.app.app_context():
        assert app_module.get_db().execute("SELECT image FROM registry_items").fetchone()["image"] == ""


def test_rate_limit_after_twenty(couple, fake):
    for _ in range(20):
        assert "Filled in from" in lookup(couple).get_data(as_text=True)
    assert len(fake.calls) == 20
    page = lookup(couple).get_data(as_text=True)
    assert "That&#39;s a lot of links in a short time" in page
    assert len(fake.calls) == 20


def test_helper_can_use_it(couple, app, app_module, fake):
    helper = app.test_client()
    signup(helper, email="h@b.com", name="Yosef")
    with app_module.app.app_context():
        db = app_module.get_db()
        hid = db.execute("SELECT id FROM users WHERE email='h@b.com'").fetchone()["id"]
        db.execute("INSERT INTO registry_members (registry_id, user_id) SELECT id, ? FROM registries", (hid,))
    page = lookup(helper).get_data(as_text=True)
    assert "Filled in from ksp.co.il" in page
    assert field(page, "name") == "Philips Air Fryer"


def test_registry_page_shows_picture(couple, app_module, fake):
    page = lookup(couple).get_data(as_text=True)
    couple.post("/registry/items/add", data=dict(
        csrf_token=get_csrf(page), name="Philips Air Fryer", url="https://www.ksp.co.il/x",
        image="https://img.ksp.co.il/a.jpg"))
    with app_module.app.app_context():
        slug = app_module.get_db().execute("SELECT slug FROM registries").fetchone()["slug"]
    body = couple.get(f"/r/{slug}").get_data(as_text=True)
    assert 'src="https://img.ksp.co.il/a.jpg"' in body
    assert 'referrerpolicy="no-referrer"' in body


def test_pasted_amazon_link_is_tagged_on_click(couple, app_module, fake):
    with app_module.app.app_context():
        app_module.get_db().execute(
            "INSERT INTO affiliate_rules (host, kind, param, value, active) VALUES ('amazon.com','param','tag','ob-20',1)")
    fake.set(url="https://www.amazon.com/dp/B0ABC", host="amazon.com", currency="USD", price="20",
             site_name="Amazon.com")
    page = lookup(couple, "https://www.amazon.com/dp/B0ABC").get_data(as_text=True)
    assert field(page, "store") == "Amazon"
    couple.post("/registry/items/add", data=dict(
        csrf_token=get_csrf(page), name=field(page, "name"), url=field(page, "url"), store="Amazon"))
    with app_module.app.app_context():
        iid = app_module.get_db().execute("SELECT id FROM registry_items").fetchone()["id"]
    r = couple.get(f"/go/i/{iid}", headers=UA)
    assert r.status_code == 302
    assert r.headers["Location"] == "https://www.amazon.com/dp/B0ABC?tag=ob-20"


def test_store_names(app_module):
    f = app_module.store_name_for
    assert f("ksp.co.il") == "KSP" and f("shop.ksp.co.il") == "KSP"
    assert f("notksp.co.il", "") == "Notksp"
    assert f("amazon.co.uk") == "Amazon" and f("www.amazon.de") == "Amazon"
    assert f("zarahome.com") == "Zara Home" and f("ikea.co.il") == "IKEA"
    assert f("shop.example.co.il") == "Example"
    assert f("example.com", "My Shop") == "My Shop"


@pytest.mark.parametrize("lang", ["en", "he"])
def test_renders_in_both_languages(couple, fake, lang):
    couple.get(f"/registry/items?lang={lang}")
    page = lookup(couple, path=f"?lang={lang}").get_data(as_text=True)
    want = "Paste a link from any store" if lang == "en" else "הדביקו קישור מכל חנות"
    assert want in page
    assert ("Filled in from" if lang == "en" else "הפרטים מולאו מ") in page
    assert 'action="/registry/items/lookup"' in page
