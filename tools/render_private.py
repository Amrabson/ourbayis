# -*- coding: utf-8 -*-
"""Render the logged-in / guest-only pages against a throwaway database with
synthetic data, so they can be screenshotted without a browser session.

    python tools/render_private.py --out /tmp/private [--base http://127.0.0.1:5001]

Writes dashboard.html, items.html, starter.html, registry.html (with claims in
every state), guest.html and their Hebrew twins. `--base` is only used to make
/static/ links absolute so a headless browser can load the CSS. Never touches
the real ourbayis.db (forces OB_DB_PATH to a temp file before importing app).
"""
import argparse
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "tests"))

TMP = Path(tempfile.mkdtemp(prefix="ourbayis-private-"))
os.environ["OB_DB_PATH"] = str(TMP / "demo.db")
os.environ["OB_SECRET_KEY"] = "render-private-only"
os.environ.setdefault("OB_RATES", '{"USD":3.7}')
os.environ.setdefault("OB_RATES_DATE", "2026-09-01")
os.environ.pop("OB_SMTP_HOST", None)

import app as A  # noqa: E402
from conftest import get_csrf, get_form_key  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", default="http://127.0.0.1:5001")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    A.app.config["TESTING"] = True
    c = A.app.test_client()

    def csrf():
        with c.session_transaction() as s:
            return s.get("_csrf")

    c.get("/signup")
    c.post("/signup", data=dict(csrf_token=csrf(), name="Sample Couple", email="sample@example.invalid",
                                password="sample-password-only", password2="sample-password-only"))
    c.get("/registry/new")
    c.post("/registry/new", data=dict(
        csrf_token=csrf(), title="Our new bayis in Yerushalayim", title_he="הבית החדש שלנו בירושלים",
        couple_names="Sample Couple", couple_names_he="זוג לדוגמה", event_type="wedding",
        event_date="2026-12-15", city="Yerushalayim",
        message="Thank you for helping us set up our first home.", visibility="public",
        paypal_url="https://paypal.me/samplecouple"))
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    reg = db.execute("SELECT * FROM registries").fetchone()
    ids = [r[0] for r in db.execute(
        "SELECT id FROM catalog_items WHERE active=1 AND featured=1 ORDER BY sort")]
    for i in ids:
        c.get("/registry/items")
        c.post("/registry/items/add", data=dict(csrf_token=csrf(), catalog_id=str(i)))
    items = db.execute("SELECT * FROM registry_items ORDER BY id").fetchall()
    db.execute("UPDATE registry_items SET qty_wanted=2 WHERE id=?", (items[1]["id"],))
    db.commit()
    db.close()

    # guests: one reserved (qty item), one reported, one received, one cash-for-item
    slug = reg["slug"]
    tokens = []
    for idx, give in ((1, "buy"), (2, "buy"), (3, "cash"), (0, "buy")):
        g = A.app.test_client()
        html = g.get(f"/r/{slug}").get_data(as_text=True)
        r = g.post(f"/r/{slug}/claim/{items[idx]['id']}", data=dict(
            csrf_token=get_csrf(html), form_key=get_form_key(html), guest_name=f"Guest {idx}",
            guest_email="", message="Mazel tov!", give=give))
        tokens.append(r.headers["Location"].rsplit("/", 1)[-1])
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.execute("UPDATE claims SET status='reported' WHERE id=2")
    db.execute("UPDATE claims SET status='received' WHERE id=3")
    db.commit()
    db.close()

    pages = {"dashboard": "/dashboard", "items": "/registry/items", "starter": "/registry/items/starter",
             "registry": f"/r/{slug}", "edit": "/registry/edit"}
    for lang in ("en", "he"):
        for name, url in pages.items():
            html = c.get(f"{url}?lang={lang}").get_data(as_text=True)
            _write(out / f"{name}-{lang}.html", html, args.base)
        g = A.app.test_client()
        html = g.get(f"/g/{tokens[0]}?lang={lang}").get_data(as_text=True)
        _write(out / f"guest-{lang}.html", html, args.base)
        html = g.get(f"/g/{tokens[2]}?lang={lang}").get_data(as_text=True)
        _write(out / f"guest-cash-{lang}.html", html, args.base)
    print("wrote", out)


def _write(path, html, base):
    html = re.sub(r'(href|src)="/static/', rf'\1="{base}/static/', html)
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
