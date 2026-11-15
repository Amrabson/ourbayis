# -*- coding: utf-8 -*-
"""Add to OurBayis from any site: GET /add?url=... (confirmation page, no fetching on GET), the bookmarklet
on /registry/items, and the Web Share Target manifest. ob_linkinfo.lookup is always monkeypatched."""
import html as htmllib
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote

import pytest

from conftest import create_registry, get_csrf, signup
from test_people import _invite, _join, _owner_with_registry

LINK = "https://www.ksp.co.il/web/item/123"
INFO = {"ok": True, "error": None, "url": LINK, "host": "ksp.co.il", "name": "Philips Air Fryer",
        "price": "499.90", "currency": "ILS", "image": "https://img.ksp.co.il/a.jpg", "brand": "Philips",
        "site_name": "KSP Store"}


@pytest.fixture
def fake(app_module, monkeypatch):
    calls = []

    def _lookup(url, **kw):
        calls.append(url)
        return dict(INFO)
    monkeypatch.setattr(app_module.ob_linkinfo, "lookup", _lookup)
    return calls


@pytest.fixture
def no_fetch(app_module, monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("GET /add must never fetch the link")
    monkeypatch.setattr(app_module.ob_linkinfo, "lookup", _boom)


@pytest.fixture
def couple(client):
    signup(client)
    create_registry(client)
    return client


def add_url(link=LINK):
    return "/add?url=" + quote(link, safe="")


def test_logged_out_goes_to_login_and_the_link_survives_login(app, no_fetch):
    c = app.test_client()
    signup(c)
    create_registry(c)
    c.post("/logout", data=dict(csrf_token=get_csrf(c.get("/registry/items").get_data(as_text=True))))
    c = app.test_client()  # a fresh, logged-out browser
    r = c.get(add_url())
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    login = c.get(r.headers["Location"])
    body = login.get_data(as_text=True)
    r = c.post(r.headers["Location"], data=dict(csrf_token=get_csrf(body), email="a@b.com", password="password1"))
    assert r.status_code == 302 and r.headers["Location"].endswith("/add")
    r = c.get("/add")  # no query: the link comes back from the session
    assert r.status_code == 302 and "url=" in r.headers["Location"]
    page = c.get(r.headers["Location"]).get_data(as_text=True)
    assert "Add this to your list?" in page and LINK in htmllib.unescape(page)


def test_link_survives_signup_and_registry_creation(client, no_fetch):
    r = client.get(add_url())
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    r = signup(client)  # redirects to registry/new, followed
    assert "/registry/new" in r.request.path
    r = create_registry(client)
    assert r.request.path == "/add"
    assert LINK in htmllib.unescape(r.get_data(as_text=True))
    # and shown once: a later bare /add has nothing pending
    assert "find a product link" in client.get("/add").get_data(as_text=True)


def test_logged_in_without_registry_is_sent_to_create_one_and_resumes(client, no_fetch):
    signup(client)
    r = client.get(add_url())
    assert r.status_code == 302 and r.headers["Location"].endswith("/registry/new")
    r = create_registry(client)
    assert r.request.path == "/add" and LINK in htmllib.unescape(r.get_data(as_text=True))


def test_get_shows_escaped_url_and_post_form_with_csrf(couple, no_fetch):
    evil = 'https://shop.example/p?x="><script>alert(1)</script>'
    r = couple.get("/add", query_string={"url": evil})
    page = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert 'dir="ltr"' in page
    form = page[page.index('action="/registry/items/lookup"'):]
    form = form[:form.index("</form>")]
    assert 'method="post"' in page and get_csrf(form) and 'name="link"' in form
    assert htmllib.unescape(re.search(r'name="link" value="([^"]*)"', form).group(1)) == evil
    assert 'href="/registry/items"' in form  # Cancel


def test_text_param_with_words_around_the_url(couple, no_fetch):
    r = couple.get("/add", query_string={"text": f"Look at this air fryer {LINK}/ it is great.", "title": "x"})
    page = htmllib.unescape(r.get_data(as_text=True))
    assert f'value="{LINK}/"' in page


def test_no_url_gives_a_helpful_message(couple, no_fetch):
    for qs in ({}, {"url": "javascript:alert(1)"}, {"text": "no link here"}):
        page = couple.get("/add", query_string=qs).get_data(as_text=True)
        assert "We couldn&#39;t find a product link" in page or "We couldn't find a product link" in page
        assert "javascript:alert" not in page and 'name="link"' not in page
        assert 'href="/registry/items#custom"' in page


def test_noindex_and_no_store(couple, no_fetch):
    r = couple.get(add_url())
    assert "noindex" in r.headers.get("X-Robots-Tag", "") + r.get_data(as_text=True)
    assert "no-store" in r.headers.get("Cache-Control", "")


def test_the_button_posts_to_the_normal_lookup_and_prefills(couple, fake):
    page = couple.get(add_url()).get_data(as_text=True)
    assert not fake, "GET /add fetched nothing"
    r = couple.post("/registry/items/lookup", data=dict(csrf_token=get_csrf(page), link=LINK), follow_redirects=True)
    assert fake == [LINK]
    body = r.get_data(as_text=True)
    assert r.request.path == "/registry/items"
    assert "Philips Air Fryer" in body and "ksp.co.il" in body


def test_a_helper_can_use_it(app, fake):
    owner = _owner_with_registry(app)
    helper = _join(app, _invite(owner))
    page = helper.get(add_url()).get_data(as_text=True)
    assert "Add this to your list?" in page
    r = helper.post("/registry/items/lookup", data=dict(csrf_token=get_csrf(page), link=LINK), follow_redirects=True)
    assert fake == [LINK] and "Philips Air Fryer" in r.get_data(as_text=True)


def test_bookmarklet_href(couple):
    page = couple.get("/registry/items").get_data(as_text=True)
    m = re.search(r'<a class="btn btn-ghost" href="([^"]+)" data-bookmarklet', page)
    assert m
    href = htmllib.unescape(m.group(1))
    assert href.startswith("javascript:") and " " not in href and '"' not in href
    code = unquote(href[len("javascript:"):])
    assert "window.open('http://localhost/add?url='+encodeURIComponent(location.href)" in code
    assert "data-bookmarklet-hint" in page and "On Android:" in page


def test_bookmarklet_uses_base_url(app_module, couple, monkeypatch):
    monkeypatch.setattr(app_module, "BASE_URL", "https://ourbayis.example")
    page = couple.get("/registry/items").get_data(as_text=True)
    href = htmllib.unescape(re.search(r'href="(javascript:[^"]+)"', page).group(1))
    assert "'https://ourbayis.example/add?url='+encodeURIComponent(location.href)" in unquote(href)


def test_manifest(client):
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200 and r.mimetype == "application/manifest+json"
    data = json.loads(r.get_data(as_text=True))
    assert data["start_url"] == "/dashboard" and data["display"] == "standalone"
    assert data["background_color"] == "#faf6ec" and data["theme_color"] == "#223354"
    st = data["share_target"]
    assert st["action"] == "/add" and st["method"] == "GET"
    assert st["params"] == {"url": "url", "text": "text", "title": "title"}
    sizes = {i["sizes"] for i in data["icons"]}
    assert {"192x192", "512x512"} <= sizes
    root = Path(__file__).resolve().parent.parent
    for icon in data["icons"]:
        assert (root / icon["src"].lstrip("/")).is_file(), icon["src"]
    assert '<link rel="manifest" href="/static/manifest.webmanifest' in client.get("/").get_data(as_text=True)


def test_renders_in_english_and_hebrew(couple, no_fetch):
    en = couple.get(add_url()).get_data(as_text=True)
    assert "Add this to your list?" in en and "Yes, fill in the details" in en
    he = couple.get(add_url() + "&lang=he").get_data(as_text=True)
    assert "להוסיף את זה לרשימה?" in he and "כן, למלא את הפרטים" in he
    items = couple.get("/registry/items").get_data(as_text=True)
    assert "הוספה ל-OurBayis" in items and "באנדרואיד:" in items
    for text in (en, he):
        assert "Shabbat" not in text
