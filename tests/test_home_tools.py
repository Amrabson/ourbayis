# -*- coding: utf-8 -*-
"""Homepage 'Start with what you have' tools section."""
import re

import i18n


def _hrefs(html):
    sec = html.split('class="tools-sec', 1)[1].split("</section>", 1)[0]
    return re.findall(r'<a class="link-arrow" href="([^"]+)"', sec)


def test_section_renders_in_both_languages_with_working_links(client):
    for lang, table in (("en", i18n.T_EN), ("he", i18n.T_HE)):
        html = client.get(f"/?lang={lang}").get_data(as_text=True)
        for k in ("home_tools_title", "home_tools_cost_t", "home_tools_link_t", "home_tools_fund_t"):
            assert table[k] in html
        hrefs = _hrefs(html)
        assert len(hrefs) == 3
        assert hrefs[0] == "/setup-cost" and hrefs[2] == "/sample"
        for h in hrefs:
            r = client.get(h)
            assert r.status_code == 200 or (r.status_code == 302 and "/signup" in r.headers["Location"]), h


def test_section_sits_between_how_and_rooms(client):
    html = client.get("/").get_data(as_text=True)
    assert html.index('class="route-sec') < html.index('class="tools-sec')
    if 'class="rooms-sec' in html:
        assert html.index('class="tools-sec') < html.index('class="rooms-sec')


def test_signed_in_link_goes_to_items(client):
    from conftest import signup, create_registry
    signup(client)
    create_registry(client)
    assert "/registry/items" in _hrefs(client.get("/").get_data(as_text=True))[1]


def test_keys_in_both_languages_and_wording():
    keys = [k for k in i18n.T_EN if k.startswith("home_tools_")]
    assert keys and all(k in i18n.T_HE for k in keys)
    assert "Shabbat" not in " ".join(i18n.T_EN[k] for k in keys)
    assert "paste a link" in i18n.T_EN["step1_b"]
