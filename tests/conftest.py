# -*- coding: utf-8 -*-
"""pytest fixtures. Sets OB_DB_PATH to a fresh temp file (and OB_SECRET_KEY,
no SMTP) BEFORE importing app, so app.py's import-time init_db() never
touches the real ourbayis.db in the repo root."""
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """Import app fresh against a temp DB for this test. app.py runs init_db()
    at import time, so we remove any cached import and re-import per test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("OB_DB_PATH", str(db_path))
    monkeypatch.setenv("OB_SECRET_KEY", "test-secret-key")
    monkeypatch.delenv("OB_SMTP_HOST", raising=False)
    monkeypatch.setenv("OB_RATES", '{"USD": 3.7}')  # pin: never read instance/rates.json in tests
    monkeypatch.delenv("OB_RATES_DATE", raising=False)
    monkeypatch.delenv("OB_SECURE_COOKIES", raising=False)
    monkeypatch.delenv("OB_TRUST_PROXY", raising=False)
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("ob_"):
            del sys.modules[mod]
    import app as app_mod
    app_mod.app.config["TESTING"] = True
    return app_mod


@pytest.fixture
def app(app_module):
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


def get_csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None


def get_form_key(html):
    m = re.search(r'name="form_key" value="([^"]+)"', html)
    return m.group(1) if m else None


def signup(client, email="a@b.com", name="Test User", password="password1"):
    r = client.get("/signup")
    tok = get_csrf(r.get_data(as_text=True))
    return client.post("/signup", data=dict(
        csrf_token=tok, name=name, email=email, password=password, password2=password),
        follow_redirects=True)


def create_registry(client, title="Our Home", couple="Sarah & Dovid", is_public="1"):
    r = client.get("/registry/new")
    tok = get_csrf(r.get_data(as_text=True))
    return client.post("/registry/new", data=dict(
        csrf_token=tok, title=title, couple_names=couple, event_type="wedding",
        is_public=is_public), follow_redirects=True)


def add_item(client, name="Platta", price_nis="300", url="https://example.com/x"):
    r = client.get("/registry/items")
    tok = get_csrf(r.get_data(as_text=True))
    return client.post("/registry/items/add", data=dict(
        csrf_token=tok, name=name, price_nis=price_nis, url=url), follow_redirects=True)
