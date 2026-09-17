# -*- coding: utf-8 -*-
"""Export a static, read-only preview of the public site into docs/ (for GitHub Pages).

    python tools/export_static.py            # writes ./docs
    python tools/export_static.py --out /tmp/site

What it does:
- boots the app against a throwaway temp database; the "registry" preview is the
  app's own canonical /sample fixture (no real people, no real payment links);
- renders every public page in English and Hebrew through the Flask test client;
- rewrites internal links to relative paths so the export works from a sub-path
  (GitHub project pages live at /<repo>/);
- drops server-only bits (canonical/hreflang/og:image absolute URLs, the currency toggle)
  and injects a banner + a tiny script that turns every form into a "demo only" notice.

Nothing here touches the real ourbayis.db.
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

# --- env must be set before importing app (it opens the DB at import time) ---
TMP = Path(tempfile.mkdtemp(prefix="ourbayis-static-"))
os.environ["OB_DB_PATH"] = str(TMP / "demo.db")
os.environ["OB_SECRET_KEY"] = "static-export-only"
os.environ["OB_RATES_DATE"] = os.environ.get("OB_RATES_DATE", "2026-09-01")
os.environ.pop("OB_SMTP_HOST", None)

import app as A  # noqa: E402

PAGES = {  # url -> output dir (relative)
    "/": "",
    "/catalog": "catalog",
    "/how-it-works": "how-it-works",
    "/about": "about",
    "/shana-rishonah": "shana-rishonah",
    "/find": "find",
    "/privacy": "privacy",
    "/contact": "contact",
    "/sample": "sample",
}
AUTH_STUBS = ("signup", "login", "forgot", "dashboard", "account", "registry/new")


def rel_prefix(out_dir):
    depth = len([p for p in out_dir.split("/") if p])
    return "../" * depth


def rewrite(html, out_dir, lang, go_map):
    """Turn absolute internal links into relative ones for this page's depth."""
    pre = rel_prefix(out_dir)
    lang_root = "" if lang == "en" else "he/"
    pre_root = pre  # to the docs root
    pre_lang = pre + lang_root

    def page_path(path, query):
        if path == "/":
            return ""
        if path == "/catalog":
            m = re.search(r"cat=([a-z]+)", query or "")
            pg = re.search(r"page=(\d+)", query or "")
            out = f"catalog/{m.group(1)}/" if m else "catalog/"
            if pg and int(pg.group(1)) > 1:
                out += f"page-{pg.group(1)}/"
            return out
        if path.startswith("/r/") or path == "/sample":
            return "sample/"
        stripped = path.strip("/")
        if stripped in PAGES.values():
            return stripped + "/"
        if stripped.startswith(AUTH_STUBS) or stripped.startswith("registry/") or stripped.startswith("g/"):
            return "demo-only/"
        return None

    def sub(m):
        attr, url = m.group(1), m.group(2)
        if url.startswith("/static/"):
            return f'{attr}="{pre_root}{url[1:]}"'
        if url.startswith("/go/"):
            return f'{attr}="{go_map.get(url, url)}"'
        if url.startswith("/lang/"):
            code = url.rsplit("/", 1)[1]
            here = out_dir.split("/", 1)[1] if out_dir.startswith("he/") else out_dir
            here = (here + "/") if here else ""
            return f'{attr}="{pre_root}{"he/" if code == "he" else ""}{here}"'
        if url.startswith("/currency/"):
            return f'{attr}="#"'
        path, _, query = url.partition("?")
        path = path.split("#")[0]
        frag = ("#" + url.split("#", 1)[1]) if "#" in url else ""
        target = page_path(path, query)
        if target is None:
            return m.group(0)
        return f'{attr}="{pre_lang}{target}{frag}"'

    html = re.sub(r'(href|action|src)="(/[^"]*)"', sub, html)
    # server-only head tags that carry localhost URLs
    html = re.sub(r'<link rel="(canonical|alternate)"[^>]*>\n?', "", html)
    html = re.sub(r'<meta property="og:image"[^>]*>\n?', "", html)
    html = html.replace("http://localhost", "")
    # currency toggle is meaningless without a server
    html = re.sub(r'<a class="lang-toggle cur-toggle"[^>]*>.*?</a>\s*', "", html, flags=re.S)
    html = re.sub(r'<form class="cur-form".*?</form>\s*', "", html, flags=re.S)
    banner = ('<div class="demo-banner" dir="auto">Static preview — read-only demo of OurBayis. '
              'Forms, sign-up and gifting are disabled here; the sample registry is synthetic.</div>'
              if lang == "en" else
              '<div class="demo-banner" dir="auto">תצוגה סטטית — הדגמה לקריאה בלבד של OurBayis. '
              'טפסים, הרשמה ומתנות אינם פעילים כאן; הרשימה לדוגמה סינתטית.</div>')
    html = html.replace("<body>", "<body>" + banner, 1)
    html = html.replace("</body>", f'<script src="{pre_root}demo.js"></script></body>', 1)
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BASE / "docs"))
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(BASE / "static", out / "static")
    (out / ".nojekyll").write_text("")
    (out / "demo.js").write_text(
        "document.addEventListener('submit',function(e){e.preventDefault();"
        "alert(document.documentElement.lang==='he'?'זו תצוגה סטטית — הטופס אינו פעיל.':"
        "'This is a static preview — forms are disabled.');},true);\n", encoding="utf-8")
    (out / "static" / "style.css").open("a", encoding="utf-8").write(
        "\n.demo-banner{background:#223354;color:#f3e9cf;text-align:center;font-size:.9rem;"
        "padding:8px 16px;letter-spacing:.2px}\n")

    A.app.config["TESTING"] = True
    import sqlite3
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    go_map = {}
    for cid, url in db.execute("SELECT id, url FROM catalog_items WHERE url != ''"):
        go_map[f"/go/c/{cid}"] = url
    n_active = db.execute("SELECT COUNT(*) FROM catalog_items WHERE active=1").fetchone()[0]
    per_cat = dict(db.execute(
        "SELECT category, COUNT(*) FROM catalog_items WHERE active=1 GROUP BY category"))
    db.close()

    from i18n import CATEGORIES
    pages = dict(PAGES)
    page_size = A.CATALOG_PAGE_SIZE
    for n in range(2, (n_active + page_size - 1) // page_size + 1):
        pages[f"/catalog?page={n}"] = f"catalog/page-{n}"
    for cat in CATEGORIES:
        pages[f"/catalog?cat={cat}"] = f"catalog/{cat}"
        for n in range(2, (per_cat.get(cat, 0) + page_size - 1) // page_size + 1):
            pages[f"/catalog?cat={cat}&page={n}"] = f"catalog/{cat}/page-{n}"
    pages["/signup"] = "demo-only"

    written = 0
    for lang in ("en", "he"):
        c = A.app.test_client()
        for url, sub_dir in pages.items():
            sep = "&" if "?" in url else "?"
            r = c.get(f"{url}{sep}lang={lang}")
            if r.status_code != 200:
                print(f"skip {url} ({lang}): {r.status_code}")
                continue
            html = r.get_data(as_text=True)
            out_dir = sub_dir if lang == "en" else ("he/" + sub_dir if sub_dir else "he")
            if sub_dir == "demo-only":
                html = html  # signup page itself becomes the "demo only" stub (forms disabled)
            html = rewrite(html, out_dir, lang, go_map)
            target = out / out_dir / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding="utf-8")
            written += 1
    # the previous export published the sample at /registry/ — keep that URL alive
    for old_dir, new_rel in (("registry", "../sample/"), ("he/registry", "../sample/")):
        target = out / old_dir / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" '
                          f'content="0; url={new_rel}"><a href="{new_rel}">Sample registry</a>',
                          encoding="utf-8")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"wrote {written} pages to {out}")


if __name__ == "__main__":
    main()
