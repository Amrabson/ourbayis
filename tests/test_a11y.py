# -*- coding: utf-8 -*-
"""Markup accessibility checks for the logged-in pages (couple + admin), 2026-09-27:
one h1, no skipped heading levels, unique ids, every visible form field labelled,
no unnamed icon-only buttons/links. Public pages are covered in test_p2."""
import collections
import os
import sqlite3
from html.parser import HTMLParser

from conftest import signup, create_registry, add_item
from test_p1 import admin_login


class _Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = collections.Counter()
        self.labels_for = set()
        self.unlabeled = []
        self.heads = []
        self.unnamed = []
        self.nested_labels = 0
        self._in_label = 0
        self._cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids[a["id"]] += 1
        if tag == "label":
            if self._in_label:
                self.nested_labels += 1  # a <label> inside a <label> is invalid HTML
            self._in_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if (tag in ("input", "select", "textarea")
                and a.get("type") not in ("hidden", "submit", "button")
                and "hp" not in (a.get("class") or "")
                and not self._in_label
                and not (a.get("aria-label") or a.get("aria-labelledby") or a.get("title"))):
            self.unlabeled.append((tag, a.get("name"), a.get("id")))
        if len(tag) == 2 and tag[0] == "h" and tag[1] in "123456":
            self.heads.append(int(tag[1]))
        if tag in ("button", "a"):
            self._cur = [tag, a, ""]

    def handle_endtag(self, tag):
        if tag == "label":
            self._in_label -= 1
        if self._cur and self._cur[0] == tag:
            t, a, text = self._cur
            if not text.strip() and not a.get("aria-label") and not a.get("title"):
                self.unnamed.append((t, a.get("href") or a.get("class")))
            self._cur = None

    def handle_data(self, d):
        if self._cur:
            self._cur[2] += d


def _check(path, resp):
    assert resp.status_code == 200, (path, resp.status_code)
    p = _Audit()
    p.feed(resp.get_data(as_text=True))
    assert p.heads.count(1) == 1, (path, p.heads)
    assert not [(a, b) for a, b in zip(p.heads, p.heads[1:]) if b > a + 1], (path, p.heads)
    assert not [k for k, v in p.ids.items() if v > 1], path
    assert not [f for f in p.unlabeled if f[2] not in p.labels_for], (path, p.unlabeled)
    assert not p.unnamed, (path, p.unnamed)
    assert not p.nested_labels, path


def test_logged_in_pages_markup(client, app_module):
    signup(client)
    _check("/registry/new", client.get("/registry/new"))
    create_registry(client)
    add_item(client)
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    iid = db.execute("SELECT id FROM registry_items ORDER BY id").fetchone()[0]
    for path in ["/dashboard", "/dashboard?lang=he", "/registry/items", "/registry/items?lang=he",
                 "/registry/items/starter", f"/registry/items/{iid}/edit", "/registry/edit",
                 "/account", "/dashboard/print"]:
        _check(path, client.get(path))

    admin = app_module.app.test_client()
    admin_login(admin)
    for path in ["/admin", "/admin/catalog", "/admin/catalog/new", "/admin/catalog/1/edit",
                 "/admin/catalog/import", "/admin/bundles", "/admin/bundles/1/edit",
                 "/admin/ads", "/admin/outbox"]:
        _check(path, admin.get(path))


def test_admin_password_form_matches_server_minimum(client, app_module):
    """The form used to say 10+ while the server required 12+."""
    admin_login(client)
    html = client.get("/admin").get_data(as_text=True)
    assert 'minlength="12"' in html and "10+" not in html
