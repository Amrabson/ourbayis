# -*- coding: utf-8 -*-
"""Affiliate engine: ob_affiliate.tag_url / validate_rule, /go/ tagging, admin page, Amazon disclosure."""
import pytest

from conftest import signup, create_registry, add_item
from test_p1 import admin_login

AMZ = dict(id=1, host="amazon.com", kind="param", param="tag", value="ob-20", active=1)


def _tag(url, *rules):
    import ob_affiliate
    return ob_affiliate.tag_url(url, list(rules))


# ------------------------------------------------------------------ unit
def test_param_adds_tag_and_keeps_everything_else(app_module):
    url, rid = _tag("https://www.amazon.com/dp/B0?x=1&y=a%20b#frag", AMZ)
    assert rid == 1
    assert url == "https://www.amazon.com/dp/B0?x=1&y=a%20b&tag=ob-20#frag"


def test_param_replaces_existing_and_is_idempotent(app_module):
    url, _ = _tag("https://amazon.com/dp/B0?tag=someone-else&a=1", AMZ)
    assert url == "https://amazon.com/dp/B0?tag=ob-20&a=1"
    again, _ = _tag(url, AMZ)
    assert again == url


def test_host_match_boundaries(app_module):
    assert _tag("https://smile.amazon.com/x", AMZ)[1] == 1
    assert _tag("https://AMAZON.COM/x", AMZ)[1] == 1
    assert _tag("https://evil-amazon.com/x", AMZ) == ("https://evil-amazon.com/x", None)
    assert _tag("https://amazon.com.evil.net/x", AMZ)[1] is None


def test_longest_host_wins(app_module):
    broad = dict(id=1, host="amazon.com", kind="param", param="tag", value="broad", active=1)
    narrow = dict(id=2, host="smile.amazon.com", kind="param", param="tag", value="narrow", active=1)
    url, rid = _tag("https://smile.amazon.com/x", broad, narrow)
    assert rid == 2 and "tag=narrow" in url


def test_inactive_rule_ignored(app_module):
    assert _tag("https://amazon.com/x", dict(AMZ, active=0)) == ("https://amazon.com/x", None)


def test_wrap_percent_encodes_original(app_module):
    rule = dict(id=3, host="aliexpress.com", kind="wrap", param="",
                value="https://portal.example.com/go?id=9&u={url}", active=1)
    url, rid = _tag("https://www.aliexpress.com/item/1.html?a=b&c=d", rule)
    assert rid == 3
    assert url == ("https://portal.example.com/go?id=9&u="
                   "https%3A%2F%2Fwww.aliexpress.com%2Fitem%2F1.html%3Fa%3Db%26c%3Dd")


@pytest.mark.parametrize("tpl", ["http://portal.example.com/?u={url}", "https://portal.example.com/?u=x",
                                 "https://bad host/?u={url}", "javascript:alert({url})"])
def test_wrap_with_bad_template_ignored(app_module, tpl):
    rule = dict(id=3, host="aliexpress.com", kind="wrap", param="", value=tpl, active=1)
    assert _tag("https://aliexpress.com/i", rule) == ("https://aliexpress.com/i", None)


@pytest.mark.parametrize("bad", ["", "not a url", "ftp://amazon.com/x", "javascript:alert(1)", "https://"])
def test_bad_urls_untouched(app_module, bad):
    assert _tag(bad, AMZ) == (bad, None)


def test_validate_rule(app_module):
    import ob_affiliate as a
    assert a.validate_rule("Amazon.com", "param", "tag", "ob-20") == ("amazon.com", "param", "tag", "ob-20")
    for args in [("https://amazon.com", "param", "tag", "x"), ("amazon.com/x", "param", "tag", "x"),
                 ("amazon", "param", "tag", "x"), ("amazon.com", "param", "bad param", "x"),
                 ("amazon.com", "param", "tag", "has space"), ("amazon.com", "param", "tag", "x" * 301),
                 ("amazon.com", "wrap", "", "https://p.example.com/"), ("amazon.com", "other", "tag", "x")]:
        with pytest.raises(ValueError):
            a.validate_rule(*args)


# ------------------------------------------------------------------ routes
def _add_rule(app_module, host="example.com", param="tag", value="ob-20", active=1):
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("INSERT INTO affiliate_rules (host, kind, param, value, active) VALUES (?, 'param', ?, ?, ?)",
                   (host, param, value, active))
        return db.execute("SELECT id FROM affiliate_rules WHERE host=?", (host,)).fetchone()[0]


def _catalog_id(app_module, url="https://shop.example.com/p?a=1"):
    with app_module.app.app_context():
        db = app_module.get_db()
        cid = db.execute("SELECT id FROM catalog_items ORDER BY id LIMIT 1").fetchone()[0]
        db.execute("UPDATE catalog_items SET url=? WHERE id=?", (url, cid))
        return cid


def _rule_clicks(app_module, rid):
    with app_module.app.app_context():
        return app_module.get_db().execute("SELECT clicks FROM affiliate_rules WHERE id=?", (rid,)).fetchone()[0]


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def test_go_catalog_redirects_tagged_and_counts(app_module, client):
    rid = _add_rule(app_module)
    cid = _catalog_id(app_module)
    r = client.get(f"/go/c/{cid}", headers=UA)
    assert r.status_code == 302
    assert r.headers["Location"] == "https://shop.example.com/p?a=1&tag=ob-20"
    assert _rule_clicks(app_module, rid) == 1
    with app_module.app.app_context():
        db = app_module.get_db()
        assert db.execute("SELECT url FROM catalog_items WHERE id=?", (cid,)).fetchone()[0] == "https://shop.example.com/p?a=1"
        names = {r[0] for r in db.execute("SELECT name FROM funnel_events")}
        assert {"handoff_click", "handoff_click_tagged"} <= names


def test_bot_does_not_count(app_module, client):
    rid = _add_rule(app_module)
    cid = _catalog_id(app_module)
    r = client.get(f"/go/c/{cid}", headers={"User-Agent": "Googlebot/2.1"})
    assert r.status_code == 302 and "tag=ob-20" in r.headers["Location"]
    assert _rule_clicks(app_module, rid) == 0


def test_no_matching_rule_leaves_url_alone(app_module, client):
    rid = _add_rule(app_module, host="other.com")
    cid = _catalog_id(app_module)
    r = client.get(f"/go/c/{cid}", headers=UA)
    assert r.headers["Location"] == "https://shop.example.com/p?a=1"
    assert _rule_clicks(app_module, rid) == 0


def test_go_item_tags_couple_added_links(app_module, client):
    rid = _add_rule(app_module)
    signup(client)
    create_registry(client)
    add_item(client, url="https://shop.example.com/thing")
    with app_module.app.app_context():
        iid = app_module.get_db().execute("SELECT id FROM registry_items ORDER BY id DESC LIMIT 1").fetchone()[0]
    r = client.get(f"/go/i/{iid}", headers=UA)
    assert r.status_code == 302 and r.headers["Location"] == "https://shop.example.com/thing?tag=ob-20"
    assert _rule_clicks(app_module, rid) == 1


def test_overlong_tagged_url_falls_back(app_module, client):
    _add_rule(app_module, value="v" * 300)
    cid = _catalog_id(app_module, "https://shop.example.com/" + "p" * 400)
    r = client.get(f"/go/c/{cid}", headers=UA)
    assert r.headers["Location"] == "https://shop.example.com/" + "p" * 400


# ------------------------------------------------------------------ admin
def test_admin_page_requires_login(client):
    for path in ("/admin/affiliates",):
        r = client.get(path)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"]
    r = client.post("/admin/affiliates/1/toggle")
    assert r.status_code in (302, 400)


def test_admin_add_edit_toggle_delete_and_test(app_module, client):
    from conftest import get_csrf
    admin_login(client)
    html = client.get("/admin/affiliates").get_data(as_text=True)
    assert "Where clicks go" in html
    tok = get_csrf(html)
    r = client.post("/admin/affiliates", data=dict(csrf_token=tok, host="Amazon.com", kind="param",
                                                   param="tag", value="ob-20", label="US"), follow_redirects=True)
    assert "Rule added" in r.get_data(as_text=True)
    r = client.post("/admin/affiliates", data=dict(csrf_token=tok, host="https://bad.com", kind="param",
                                                   param="tag", value="x"), follow_redirects=True)
    assert "Rule not saved" in r.get_data(as_text=True)
    with app_module.app.app_context():
        rid = app_module.get_db().execute("SELECT id FROM affiliate_rules").fetchone()[0]
    r = client.post("/admin/affiliates/test", data=dict(csrf_token=tok, test_url="amazon.com/dp/B0"))
    assert "tag=ob-20" in r.get_data(as_text=True)
    client.post(f"/admin/affiliates/{rid}/edit", data=dict(csrf_token=tok, host="amazon.com", kind="param",
                                                           param="tag", value="new-21"))
    r = client.post("/admin/affiliates/test", data=dict(csrf_token=tok, test_url="https://amazon.com/x"))
    assert "tag=new-21" in r.get_data(as_text=True)
    client.post(f"/admin/affiliates/{rid}/toggle", data=dict(csrf_token=tok))
    r = client.post("/admin/affiliates/test", data=dict(csrf_token=tok, test_url="https://amazon.com/x"))
    assert "No active rule" in r.get_data(as_text=True)
    client.post(f"/admin/affiliates/{rid}/delete", data=dict(csrf_token=tok))
    with app_module.app.app_context():
        assert app_module.get_db().execute("SELECT COUNT(*) FROM affiliate_rules").fetchone()[0] == 0


def test_where_clicks_go_groups_by_host(app_module, client):
    _catalog_id(app_module)
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("UPDATE catalog_items SET clicks=5 WHERE id=(SELECT MIN(id) FROM catalog_items)")
    _add_rule(app_module, host="example.com")
    admin_login(client)
    html = client.get("/admin/affiliates").get_data(as_text=True)
    assert "shop.example.com" in html and "Yes (example.com)" in html


# ------------------------------------------------------------------ disclosure
SENTENCE = "As an Amazon Associate OurBayis earns from qualifying purchases."


def test_amazon_sentence_only_with_active_amazon_rule(app_module, client):
    page = "/catalog"
    assert SENTENCE not in client.get(page).get_data(as_text=True)
    _add_rule(app_module, host="example.com")
    assert SENTENCE not in client.get(page).get_data(as_text=True)
    rid = _add_rule(app_module, host="amazon.com", active=0)
    assert SENTENCE not in client.get(page).get_data(as_text=True)
    with app_module.app.app_context():
        app_module.get_db().execute("UPDATE affiliate_rules SET active=1 WHERE id=?", (rid,))
    body = client.get(page).get_data(as_text=True)
    assert SENTENCE in body
    assert SENTENCE in client.get(page + "?lang=he").get_data(as_text=True)


# ------------------------------------------------------------------ direct links (no /go/ redirect)
def _direct_setup(app_module, client, direct, url="https://www.amazon.com/dp/B0"):
    with app_module.app.app_context():
        app_module.get_db().execute(
            "INSERT INTO affiliate_rules (host, kind, param, value, active, direct) VALUES ('amazon.com','param','tag','ob-20',1,?)",
            (direct,))
    signup(client)
    create_registry(client)
    add_item(client, url=url)
    with app_module.app.app_context():
        db = app_module.get_db()
        iid = db.execute("SELECT id FROM registry_items ORDER BY id DESC LIMIT 1").fetchone()[0]
        slug = db.execute("SELECT slug FROM registries").fetchone()[0]
        db.execute("UPDATE registries SET visibility='public'")
    return slug, iid


def test_direct_rule_links_the_tagged_url_with_a_ping(app_module, client):
    slug, iid = _direct_setup(app_module, client, direct=1)
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert ('href="https://www.amazon.com/dp/B0?tag=ob-20" data-go-ping="/go/i/%d/ping" target="_blank" '
            'rel="nofollow sponsored noopener"' % iid) in html
    assert f'href="/go/i/{iid}"' not in html


def test_non_direct_rule_still_goes_through_go(app_module, client):
    slug, iid = _direct_setup(app_module, client, direct=0)
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert f'href="/go/i/{iid}"' in html and "data-go-ping" not in html and "tag=ob-20" not in html


def test_direct_flag_needs_an_active_matching_param_rule(app_module, client):
    slug, iid = _direct_setup(app_module, client, direct=1, url="https://shop.example.com/x")
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert f'href="/go/i/{iid}"' in html and "data-go-ping" not in html  # another host: no rule
    with app_module.app.app_context():
        app_module.get_db().execute("UPDATE affiliate_rules SET kind='wrap', value='https://p.example.com/?u={url}', param=''")
        app_module.get_db().execute("UPDATE registry_items SET url='https://www.amazon.com/dp/B0'")
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert f'href="/go/i/{iid}"' in html  # a wrap rule is never linked directly
    with app_module.app.app_context():
        app_module.get_db().execute("UPDATE affiliate_rules SET kind='param', param='tag', value='ob-20', active=0")
    html = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert f'href="/go/i/{iid}"' in html  # a rule that is off tags nothing


def test_ping_counts_like_the_redirect(app_module, client):
    from conftest import get_csrf
    slug, iid = _direct_setup(app_module, client, direct=1)
    guest = app_module.app.test_client()
    tok = get_csrf(guest.get(f"/r/{slug}").get_data(as_text=True))
    assert guest.post(f"/go/i/{iid}/ping", data={}, headers=UA).status_code == 400  # no CSRF token, no count
    r = guest.post(f"/go/i/{iid}/ping", data=dict(csrf_token=tok), headers=UA)
    assert r.status_code == 204 and r.data == b""
    with app_module.app.app_context():
        db = app_module.get_db()
        assert db.execute("SELECT clicks FROM registry_items WHERE id=?", (iid,)).fetchone()[0] == 1
        assert db.execute("SELECT clicks FROM affiliate_rules").fetchone()[0] == 1
        names = {x[0] for x in db.execute("SELECT name FROM funnel_events")}
        assert {"handoff_click", "handoff_click_tagged"} <= names
    # a crawler's ping counts nothing
    guest.post(f"/go/i/{iid}/ping", data=dict(csrf_token=tok), headers={"User-Agent": "Googlebot/2.1"})
    with app_module.app.app_context():
        assert app_module.get_db().execute("SELECT clicks FROM affiliate_rules").fetchone()[0] == 1
    assert guest.post("/go/i/99999/ping", data=dict(csrf_token=tok), headers=UA).status_code == 404


def test_catalog_ping_counts_and_is_rate_limited(app_module, client):
    from conftest import get_csrf
    rid = _add_rule(app_module)
    cid = _catalog_id(app_module)
    tok = get_csrf(client.get("/catalog").get_data(as_text=True))
    assert client.post(f"/go/c/{cid}/ping", data=dict(csrf_token=tok), headers=UA).status_code == 204
    assert _rule_clicks(app_module, rid) == 1
    codes = [client.post(f"/go/c/{cid}/ping", data=dict(csrf_token=tok), headers=UA).status_code for _ in range(70)]
    assert 429 in codes


def test_admin_direct_checkbox_and_amazon_presets(app_module, client):
    from conftest import get_csrf
    admin_login(client)
    html = client.get("/admin/affiliates").get_data(as_text=True)
    assert "Link directly (no /go/ redirect)" in html and html.count('data-direct="1"') == 2
    tok = get_csrf(html)
    client.post("/admin/affiliates", data=dict(csrf_token=tok, host="amazon.com", kind="param", param="tag",
                                               value="ob-20", direct="1"))
    client.post("/admin/affiliates", data=dict(csrf_token=tok, host="example.com", kind="param", param="tag", value="x"))
    with app_module.app.app_context():
        rows = {r["host"]: r["direct"] for r in app_module.get_db().execute("SELECT host, direct FROM affiliate_rules")}
        rid = app_module.get_db().execute("SELECT id FROM affiliate_rules WHERE host='amazon.com'").fetchone()[0]
    assert rows == {"amazon.com": 1, "example.com": 0}
    client.post(f"/admin/affiliates/{rid}/edit", data=dict(csrf_token=tok, host="amazon.com", kind="param",
                                                           param="tag", value="ob-20"))  # box left unticked
    with app_module.app.app_context():
        assert app_module.get_db().execute("SELECT direct FROM affiliate_rules WHERE id=?", (rid,)).fetchone()[0] == 0
