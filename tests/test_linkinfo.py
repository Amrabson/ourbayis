import gzip
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ob_linkinfo as li  # noqa: E402
from ob_linkinfo import LinkError, check_url, lookup, parse_html  # noqa: E402

PUBLIC = "93.184.216.34"


def res_public(host):
    return [PUBLIC]


def mk_res(mapping, default=PUBLIC):
    def r(host):
        v = mapping.get(host, default)
        return v if isinstance(v, list) else [v]
    return r


# ---------------------------------------------------------------- check_url

def test_check_url_ok():
    url, ips = check_url("https://www.Example.com/p/1?a=1#frag", resolver=res_public)
    assert url == "https://www.example.com/p/1?a=1"
    assert ips == [PUBLIC]


def test_check_url_ports_ok():
    check_url("http://example.com:80/x", resolver=res_public)
    check_url("https://example.com:443/x", resolver=res_public)


@pytest.mark.parametrize("url,ip,code", [
    ("file:///etc/passwd", PUBLIC, "bad_url"),
    ("ftp://example.com/x", PUBLIC, "bad_url"),
    ("https://user:pw@example.com/", PUBLIC, "bad_url"),
    ("https://user@example.com/", PUBLIC, "bad_url"),
    ("https://example.com:8080/", PUBLIC, "bad_url"),
    ("http://localhost/", PUBLIC, "blocked_host"),
    ("http://127.0.0.1/", PUBLIC, "blocked_host"),
    ("http://[::1]/", PUBLIC, "blocked_host"),
    ("http://2130706433/", PUBLIC, "blocked_host"),
    ("http://0x7f.1/", PUBLIC, "blocked_host"),
    ("http://0177.0.0.1/", PUBLIC, "blocked_host"),
    ("http://intranet/", PUBLIC, "blocked_host"),
    ("http://printer.local/", PUBLIC, "blocked_host"),
    ("http://a.internal/", PUBLIC, "blocked_host"),
    ("http://a.localhost/", PUBLIC, "blocked_host"),
    ("http://a.lan/", PUBLIC, "blocked_host"),
    ("http://a.test/", PUBLIC, "blocked_host"),
    ("http://example.com/" + "a" * 2000, PUBLIC, "bad_url"),
    ("", PUBLIC, "bad_url"),
    ("http://", PUBLIC, "bad_url"),
    ("https://example.com/\\@127.0.0.1", PUBLIC, "bad_url"),
    ("https://shop.example.com/", "10.0.0.5", "blocked_host"),
    ("https://shop.example.com/", "192.168.1.20", "blocked_host"),
    ("https://shop.example.com/", "172.16.0.1", "blocked_host"),
    ("https://shop.example.com/", "127.0.0.1", "blocked_host"),
    ("https://shop.example.com/", "169.254.169.254", "blocked_host"),
    ("https://shop.example.com/", "100.64.0.1", "blocked_host"),
    ("https://shop.example.com/", "0.0.0.0", "blocked_host"),
    ("https://shop.example.com/", "224.0.0.1", "blocked_host"),
    ("https://shop.example.com/", "::1", "blocked_host"),
    ("https://shop.example.com/", "fe80::1", "blocked_host"),
    ("https://shop.example.com/", "fc00::1", "blocked_host"),
    ("https://shop.example.com/", "::ffff:127.0.0.1", "blocked_host"),
    ("https://shop.example.com/", "::ffff:10.1.2.3", "blocked_host"),
    ("https://shop.example.com/", "64:ff9b::7f00:1", "blocked_host"),
    ("https://shop.example.com/", "2002:7f00:1::", "blocked_host"),
])
def test_check_url_rejects(url, ip, code):
    with pytest.raises(LinkError) as ei:
        check_url(url, resolver=lambda h: [ip])
    assert ei.value.code == code


def test_mixed_public_private_rejected():
    with pytest.raises(LinkError) as ei:
        check_url("https://example.com/", resolver=lambda h: [PUBLIC, "10.0.0.1"])
    assert ei.value.code == "blocked_host"


def test_resolver_failure_and_empty():
    def boom(h):
        raise OSError("nx")
    with pytest.raises(LinkError) as ei:
        check_url("https://example.com/", resolver=boom)
    assert ei.value.code == "fetch_failed"
    with pytest.raises(LinkError):
        check_url("https://example.com/", resolver=lambda h: [])


def test_public_ipv6_ok():
    _, ips = check_url("https://example.com/", resolver=lambda h: ["2606:2800:220:1::1"])
    assert ips == ["2606:2800:220:1::1"]


# ------------------------------------------------------------------ lookup

PRODUCT_HTML = """<html><head><title>Fallback | Shop</title>
<meta property="og:site_name" content="Shop">
<link rel="canonical" href="https://www.shop.co.il/item/5">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Kettle &amp; Co",
 "image":"https://img.shop.co.il/k.jpg","brand":{"@type":"Brand","name":"Zed"},
 "offers":{"@type":"Offer","price":"1,861.00","priceCurrency":"ILS"}}
</script></head><body></body></html>"""


def html_opener(body=PRODUCT_HTML, ctype="text/html; charset=utf-8", status=200,
                extra=None, calls=None):
    def op(url, host, ip, headers, deadline):
        if calls is not None:
            calls.append((url, host, ip, headers))
        h = {"content-type": ctype}
        h.update(extra or {})
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        return status, h, b
    return op


def test_lookup_happy_path():
    calls = []
    r = lookup("https://www.shop.co.il/item/5?utm_source=x&color=red",
               resolver=res_public, opener=html_opener(calls=calls))
    assert r["ok"] and r["error"] is None
    assert r["name"] == "Kettle & Co"
    assert r["price"] == "1861" and r["currency"] == "ILS"
    assert r["image"] == "https://img.shop.co.il/k.jpg"
    assert r["brand"] == "Zed" and r["site_name"] == "Shop"
    assert r["host"] == "shop.co.il"
    assert r["url"] == "https://www.shop.co.il/item/5"
    # pinned ip + browser-ish headers, no cookies
    url, host, ip, headers = calls[0]
    assert ip == PUBLIC and host == "www.shop.co.il"
    assert "Mozilla" in headers["User-Agent"]
    assert "gzip" in headers["Accept-Encoding"]
    assert not any(k.lower() in ("cookie", "authorization") for k in headers)


def test_tracking_params_stripped():
    html = "<title>Thing</title>"
    r = lookup("https://example.com/p?id=3&utm_medium=a&gclid=1&fbclid=2&msclkid=3"
               "&mc_cid=4&mc_eid=5&igshid=6&srsltid=7&keep=1",
               resolver=res_public, opener=html_opener(html))
    assert r["url"] == "https://example.com/p?id=3&keep=1"


def test_canonical_other_host_ignored():
    html = '<title>T</title><link rel="canonical" href="https://evil.com/x">'
    r = lookup("https://example.com/p", resolver=res_public, opener=html_opener(html))
    assert r["url"] == "https://example.com/p"


def test_redirect_followed_and_rechecked():
    seen = []

    def op(url, host, ip, headers, deadline):
        seen.append(url)
        if url.startswith("https://short.example.com"):
            return 301, {"location": "https://www.shop.example.org/final?utm_x=1"}, b""
        return 200, {"content-type": "text/html"}, b"<title>Final</title>"

    r = lookup("https://short.example.com/a", resolver=res_public, opener=op)
    assert r["ok"] and r["name"] == "Final"
    assert r["url"] == "https://www.shop.example.org/final"
    assert r["host"] == "shop.example.org"
    assert len(seen) == 2


def test_relative_redirect():
    def op(url, host, ip, headers, deadline):
        if url.endswith("/a"):
            return 302, {"location": "/b"}, b""
        return 200, {"content-type": "text/html"}, b"<title>B</title>"
    r = lookup("https://example.com/a", resolver=res_public, opener=op)
    assert r["ok"] and r["url"] == "https://example.com/b"


def test_redirect_to_private_blocked():
    def op(url, host, ip, headers, deadline):
        return 302, {"location": "https://internal.example.net/x"}, b""
    r = lookup("https://example.com/a", opener=op,
               resolver=mk_res({"internal.example.net": "10.0.0.5"}))
    assert not r["ok"] and r["error"] == "blocked_host"


def test_redirect_to_ip_literal_blocked():
    def op(url, host, ip, headers, deadline):
        return 302, {"location": "http://169.254.169.254/latest/meta-data/"}, b""
    r = lookup("https://example.com/a", opener=op, resolver=res_public)
    assert r["error"] == "blocked_host"


def test_too_many_redirects():
    n = []

    def op(url, host, ip, headers, deadline):
        n.append(url)
        return 302, {"location": "https://example.com/%d" % len(n)}, b""
    r = lookup("https://example.com/", resolver=res_public, opener=op)
    assert r["error"] == "fetch_failed" and not r["ok"]
    assert len(n) == 5     # original + 4 followed redirects


def test_four_redirects_ok():
    n = []

    def op(url, host, ip, headers, deadline):
        n.append(url)
        if len(n) <= 4:
            return 302, {"location": "https://example.com/%d" % len(n)}, b""
        return 200, {"content-type": "text/html"}, b"<title>Done</title>"
    r = lookup("https://example.com/", resolver=res_public, opener=op)
    assert r["ok"] and r["name"] == "Done"


def test_404():
    r = lookup("https://example.com/", resolver=res_public,
               opener=html_opener("<title>x</title>", status=404))
    assert r["error"] == "fetch_failed" and not r["ok"]
    assert r["host"] == "example.com"


def test_not_html():
    r = lookup("https://example.com/i.png", resolver=res_public,
               opener=html_opener(b"\x89PNG", ctype="image/png"))
    assert r["error"] == "not_html"


@pytest.mark.parametrize("exc", [OSError("boom"), TimeoutError("t"),
                                 ConnectionResetError(), RuntimeError("weird")])
def test_opener_exceptions_swallowed(exc):
    def op(*a):
        raise exc
    r = lookup("https://example.com/", resolver=res_public, opener=op)
    assert r["ok"] is False and r["error"] == "fetch_failed"


def test_bad_inputs_never_raise():
    for u in ("", None, "javascript:alert(1)", "http://[::1", 123):
        r = lookup(u, resolver=res_public, opener=html_opener())
        assert r["ok"] is False and r["error"] in ("bad_url", "blocked_host")


def test_gzip_body():
    body = gzip.compress(PRODUCT_HTML.encode("utf-8"))
    r = lookup("https://www.shop.co.il/x", resolver=res_public,
               opener=html_opener(body, extra={"content-encoding": "gzip"}))
    assert r["ok"] and r["price"] == "1861"


def test_gzip_bomb_capped():
    page = b"<title>Bomb</title>" + b"<!--" + b"a" * (50 * 1024 * 1024) + b"-->"
    body = gzip.compress(page)
    r = lookup("https://example.com/", resolver=res_public,
               opener=html_opener(body, extra={"content-encoding": "gzip"}))
    assert r["ok"] and r["name"] == "Bomb"


def test_bad_gzip():
    r = lookup("https://example.com/", resolver=res_public,
               opener=html_opener(b"not gzip", extra={"content-encoding": "gzip"}))
    assert r["error"] == "fetch_failed"


def test_big_body_truncated_but_parsed():
    body = b"<title>Big</title>" + b" " * (5 * 1024 * 1024)
    r = lookup("https://example.com/", resolver=res_public, opener=html_opener(body))
    assert r["ok"] and r["name"] == "Big"


def test_no_metadata():
    r = lookup("https://www.example.com/p?utm_source=z", resolver=res_public,
               opener=html_opener("<html><body><p>hi</p></body></html>"))
    assert r["ok"] is False and r["error"] == "no_data"
    assert r["url"] == "https://www.example.com/p" and r["host"] == "example.com"


def test_hebrew_utf8():
    html = "<title>קומקום חשמלי</title>"
    r = lookup("https://example.co.il/", resolver=res_public, opener=html_opener(html))
    assert r["name"] == "קומקום חשמלי"


def test_hebrew_windows_1255_header_and_meta():
    text = "<title>קומקום חשמלי</title>"
    raw = text.encode("windows-1255")
    r = lookup("https://example.co.il/", resolver=res_public,
               opener=html_opener(raw, ctype="text/html; charset=windows-1255"))
    assert r["name"] == "קומקום חשמלי"
    raw2 = ('<meta charset="windows-1255">' + text).encode("windows-1255")
    r = lookup("https://example.co.il/", resolver=res_public,
               opener=html_opener(raw2, ctype="text/html"))
    assert r["name"] == "קומקום חשמלי"


def test_unknown_charset_falls_back():
    r = lookup("https://example.com/", resolver=res_public,
               opener=html_opener("<title>Ok</title>", ctype="text/html; charset=bogus-9"))
    assert r["name"] == "Ok"


def test_resolver_used_per_hop_and_ip_pinned():
    ips = []

    def op(url, host, ip, headers, deadline):
        ips.append(ip)
        return 200, {"content-type": "text/html"}, b"<title>x</title>"
    lookup("https://example.com/", resolver=lambda h: ["1.1.1.1", "8.8.8.8"], opener=op)
    assert ips == ["1.1.1.1"]


def test_falls_over_to_second_ip():
    ips = []

    def op(url, host, ip, headers, deadline):
        ips.append(ip)
        if ip == "1.1.1.1":
            raise OSError("refused")
        return 200, {"content-type": "text/html"}, b"<title>x</title>"
    r = lookup("https://example.com/", resolver=lambda h: ["1.1.1.1", "8.8.8.8"], opener=op)
    assert r["ok"] and ips == ["1.1.1.1", "8.8.8.8"]


# -------------------------------------------------------------- parse_html

BASE = "https://www.shop.com/item/1"


def ld(obj):
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj)


def test_name_fallbacks():
    assert parse_html(ld({"@type": "Product", "name": "JL"}) +
                      '<meta property="og:title" content="OG">', BASE)["name"] == "JL"
    assert parse_html('<meta property="og:title" content="OG">'
                      '<meta name="twitter:title" content="TW"><title>T</title>',
                      BASE)["name"] == "OG"
    assert parse_html('<meta name="twitter:title" content="TW"><title>T</title>',
                      BASE)["name"] == "TW"
    assert parse_html("<title>  Only\n  Title </title>", BASE)["name"] == "Only Title"


def test_name_cleaning_entities_tags_length():
    assert parse_html('<meta property="og:title" content="Tom &amp;amp; <b>Jerry</b>">',
                      BASE)["name"] == "Tom & Jerry"
    long = parse_html("<title>%s</title>" % ("x" * 500), BASE)["name"]
    assert len(long) == 200
    assert parse_html("<title>a\x00b\x07c</title>", BASE)["name"] == "abc"


@pytest.mark.parametrize("title,site,expected", [
    ("Red Kettle | Shop Name", "shop name", "Red Kettle"),
    ("Red Kettle - Shop Name", "Shop Name", "Red Kettle"),
    ("Red Kettle – Shop Name", "Shop Name", "Red Kettle"),
    ("Red Kettle | Shop", None, "Red Kettle"),            # matches hostname label
    ("Red Kettle - Other Brand", None, "Red Kettle - Other Brand"),
    ("Red Kettle - Other Brand", "Shop Name", "Red Kettle - Other Brand"),
    ("Anti-rust spray", None, "Anti-rust spray"),          # no spaced separator
])
def test_title_suffix(title, site, expected):
    meta = '<meta property="og:site_name" content="%s">' % site if site else ""
    html = meta + '<meta property="og:title" content="%s">' % title
    assert parse_html(html, BASE)["name"] == expected


def test_price_jsonld_variants():
    p = parse_html(ld({"@type": "Product", "name": "a", "offers": [
        {"@type": "Offer"}, {"@type": "Offer", "price": 49.9, "priceCurrency": "usd"}]}), BASE)
    assert (p["price"], p["currency"]) == ("49.90", "USD")
    p = parse_html(ld({"@type": "Product", "name": "a", "offers": {
        "@type": "AggregateOffer", "lowPrice": "20", "priceCurrency": "EUR"}}), BASE)
    assert (p["price"], p["currency"]) == ("20", "EUR")
    p = parse_html(ld({"@type": "Product", "name": "a", "offers": {
        "price": "5", "priceSpecification": {"priceCurrency": "GBP"}}}), BASE)
    assert p["price"] == "5"
    p = parse_html(ld({"@type": "Product", "name": "a", "offers": {
        "priceSpecification": {"price": "7.5", "priceCurrency": "GBP"}}}), BASE)
    assert (p["price"], p["currency"]) == ("7.50", "GBP")


def test_price_meta_fallbacks():
    p = parse_html('<meta property="product:price:amount" content="12.5">'
                   '<meta property="product:price:currency" content="ils">', BASE)
    assert (p["price"], p["currency"]) == ("12.50", "ILS")
    p = parse_html('<meta property="og:price:amount" content="30">'
                   '<meta property="og:price:currency" content="EUR">', BASE)
    assert (p["price"], p["currency"]) == ("30", "EUR")
    p = parse_html('<span itemprop="price" content="99.99"></span>'
                   '<meta itemprop="priceCurrency" content="USD">', BASE)
    assert (p["price"], p["currency"]) == ("99.99", "USD")
    p = parse_html('<span itemprop="price">₪ 1,861</span>', BASE)
    assert (p["price"], p["currency"]) == ("1861", "ILS")


@pytest.mark.parametrize("raw,expected", [
    ("1,861.00", "1861"), ("1.861,00", "1861"), ("₪ 1,861", "1861"),
    (1861, "1861"), ("48.5", "48.50"), (48.5, "48.50"), ("48,50", "48.50"),
    ("1,234,567.89", "1234567.89"), ("48.50", "48.50"), ("$19.99", "19.99"),
    ("0", None), ("-5", None), ("abc", None), ("", None), ("10000001", None),
    ("10000000", "10000000"), (True, None), (None, None), ([], None),
])
def test_price_normalisation(raw, expected):
    assert li._norm_price(raw) == expected


def test_price_via_jsonld_string_formats():
    for raw, exp in (("1,861.00", "1861"), ("1.861,00", "1861"), ("48.5", "48.50")):
        p = parse_html(ld({"@type": "Product", "name": "a",
                           "offers": {"price": raw, "priceCurrency": "ILS"}}), BASE)
        assert p["price"] == exp


def test_currency_symbols():
    assert li._currency_from_text("₪100") == "ILS"
    assert li._currency_from_text("100 NIS") == "ILS"
    assert li._currency_from_text('100 ש"ח') == "ILS"
    assert li._currency_from_text("£5") == "GBP"
    assert li._currency_from_text("5€") == "EUR"
    assert li._currency_from_text("$5") == "USD"
    assert li._currency_from_text("CA$5") is None
    assert li._currency_from_text("5") is None


def test_image_fallbacks_and_rules():
    assert parse_html(ld({"@type": "Product", "name": "a",
                          "image": ["", "https://c.example/a.jpg"]}) +
                      '<meta property="og:image" content="https://x/o.jpg">',
                      BASE)["image"] == "https://c.example/a.jpg"
    assert parse_html(ld({"@type": "Product", "name": "a",
                          "image": {"@type": "ImageObject", "url": "/i/x.jpg"}}),
                      BASE)["image"] == "https://www.shop.com/i/x.jpg"
    assert parse_html('<meta property="og:image" content="https://x/o.jpg">'
                      '<meta property="og:image:secure_url" content="https://x/s.jpg">',
                      BASE)["image"] == "https://x/s.jpg"
    assert parse_html('<meta property="og:image" content="https://x/o.jpg">',
                      BASE)["image"] == "https://x/o.jpg"
    assert parse_html('<meta name="twitter:image" content="https://x/t.jpg">',
                      BASE)["image"] == "https://x/t.jpg"
    assert parse_html('<meta property="og:image" content="/rel/a.png">',
                      BASE)["image"] == "https://www.shop.com/rel/a.png"
    assert parse_html('<meta property="og:image" content="//cdn.x.com/a.png">',
                      BASE)["image"] == "https://cdn.x.com/a.png"
    assert parse_html('<meta property="og:image" content="http://x.com/a.png">',
                      BASE)["image"] == "https://x.com/a.png"


def test_image_rejected():
    assert parse_html('<meta property="og:image" content="data:image/png;base64,AAA">',
                      BASE)["image"] is None
    assert parse_html('<meta property="og:image" content="javascript:alert(1)">',
                      BASE)["image"] is None
    assert parse_html('<meta property="og:image" content="https://x.com/%s">' % ("a" * 1001),
                      BASE)["image"] is None
    # first bad og:image:secure_url does not hide a good og:image
    assert parse_html('<meta property="og:image:secure_url" content="data:x">'
                      '<meta property="og:image" content="https://x/o.jpg">',
                      BASE)["image"] == "https://x/o.jpg"


def test_brand_and_site_name():
    p = parse_html(ld({"@type": "Product", "name": "a", "brand": "Acme"}), BASE)
    assert p["brand"] == "Acme"
    p = parse_html(ld({"@type": "Product", "name": "a", "brand": {"name": "Zed"}}), BASE)
    assert p["brand"] == "Zed"
    p = parse_html('<meta property="product:brand" content="PB">'
                   '<meta property="og:site_name" content="My Shop">', BASE)
    assert p["brand"] == "PB" and p["site_name"] == "My Shop"


def test_jsonld_graph_list_nested_and_type_list():
    graph = {"@context": "x", "@graph": [
        {"@type": "WebSite", "name": "Site"},
        {"@type": ["Product", "Thing"], "name": "Graph Item",
         "offers": {"price": "10", "priceCurrency": "USD"}}]}
    p = parse_html(ld(graph), BASE)
    assert (p["name"], p["price"], p["currency"]) == ("Graph Item", "10", "USD")
    p = parse_html(ld([{"@type": "Organization"},
                       {"@type": "ItemPage", "mainEntity": {"@type": "Product", "name": "Deep"}}]),
                   BASE)
    assert p["name"] == "Deep"


def test_broken_json_block_then_good():
    html = ('<script type="application/ld+json">{ not json,, }</script>' +
            ld({"@type": "Product", "name": "Good One"}))
    assert parse_html(html, BASE)["name"] == "Good One"


def test_canonical_returned():
    assert parse_html('<link rel="canonical" href="/c/1">', BASE)["canonical"] == \
        "https://www.shop.com/c/1"
    assert parse_html('<link rel="canonical" href="javascript:x">', BASE)["canonical"] is None
    assert parse_html("<p>", BASE)["canonical"] is None


@pytest.mark.parametrize("html", [
    "", "<<<>>>", "<title>unclosed", "<meta property=og:title content=Hi>",
    '<script type="application/ld+json">{"@type":"Product"', "<div <p ><<title>",
    "\x00\x01\x02", "<a href='x>\"<b>", "<![CDATA[ x ]]>", None, 12,
])
def test_malformed_html_does_not_raise(html):
    out = parse_html(html, BASE)
    assert set(out) == {"name", "price", "currency", "image", "brand",
                        "site_name", "canonical"}


def test_unquoted_attrs():
    assert parse_html("<meta property=og:title content=Hi>", BASE)["name"] == "Hi"


def test_deeply_nested_json_does_not_crash():
    nested = "[" * 5000 + "]" * 5000
    html = '<script type="application/ld+json">%s</script><title>T</title>' % nested
    assert parse_html(html, BASE)["name"] == "T"
