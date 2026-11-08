# -*- coding: utf-8 -*-
"""Share-card images (1200x630) in the site's own design, drawn by headless Chrome:

    python tools/make_og_cards.py

writes static/og-home-en.png, og-home-he.png (homepage and every page without its own card) and
static/og-registry-en.png, og-registry-he.png (any couple's registry link). The apartment drawing is
the real `plan_svg` macro and the styles are static/style.css, so the cards match the site. Needs
Chrome or Edge (like tools/screenshots.py) and network for the Google Fonts; no pip dependencies.
Rerun after changing the plan drawing or these words (i18n `og_*`).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = Path(tempfile.mkdtemp())
os.environ["OB_DB_PATH"] = str(_tmp / "og.db")  # never touch the real database
os.environ.setdefault("OB_SECRET_KEY", "og-cards")
os.environ["OB_ENV_FILE"] = str(_tmp / "none.env")

import app as A  # noqa: E402
from flask import render_template_string, session  # noqa: E402
from tools.screenshots import find_browser  # noqa: E402

FILLS = {"salon": dict(done=5, total=8, pct=.62), "kitchen": dict(done=4, total=9, pct=.44),
         "bedroom": dict(done=3, total=4, pct=.75), "entry": dict(done=1, total=3, pct=.33)}

PAGE = """<!doctype html>
<html lang="{{ lang }}" dir="{{ 'rtl' if rtl else 'ltr' }}"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;600;700&family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,300..500&family=Frank+Ruhl+Libre:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ css }}">
<style>
  html, body { margin: 0; width: 1200px; height: 630px; overflow: hidden; }
  .og { width: 1200px; height: 630px; box-sizing: border-box; display: grid; grid-template-columns: 560px 1fr;
        align-items: center; gap: 40px; padding: 56px 64px; }
  .og .kicker { margin: 0 0 18px; font-size: 1rem; }
  .og h1 { font-family: var(--ed); font-weight: 400; color: var(--navy); font-size: 78px; line-height: 1.02; margin: 0 0 22px; }
  .og h1 em { color: var(--gold); }
  .og p.line { font-size: 26px; line-height: 1.35; color: var(--ink-soft); margin: 0 0 34px; }
  .og .mark { font-family: var(--ed); font-size: 34px; color: var(--navy); margin: 0; }
  .og .mark em { color: var(--gold); }
  .og .plan-sheet { animation: none !important; }
  .og .plan-sheet * { animation: none !important; opacity: 1 !important; stroke-dashoffset: 0 !important; }
</style></head>
<body class="home"><div class="og">
  <div>
    <p class="kicker">{{ t('og_' ~ kind ~ '_kicker') }}</p>
    <h1>{{ t('og_' ~ kind ~ '_a') }} <em>{{ t('og_' ~ kind ~ '_em') }}</em></h1>
    <p class="line">{{ t('og_' ~ kind ~ '_line') }}</p>
    <p class="mark">Our<em>Bayis</em></p>
  </div>
  <div class="plan-sheet">{{ plan_svg(t('og_' ~ kind ~ '_a'), fills=fills) }}</div>
</div></body></html>
"""


def main():
    exe = find_browser()
    out = _tmp / "cards"
    out.mkdir()
    css = (ROOT / "static" / "style.css").as_uri()
    for kind in ("home", "registry"):
        for lang in ("en", "he"):
            with A.app.test_request_context(f"/?lang={lang}"):
                session["lang"] = lang
                html = render_template_string(
                    '{% from "_plan.html" import plan_svg with context %}' + PAGE,
                    kind=kind, css=css, fills=FILLS if kind == "registry" else None)
            src = out / f"{kind}-{lang}.html"
            src.write_text(html, encoding="utf-8")
            target = ROOT / "static" / f"og-{kind}-{lang}.png"
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000",
                            "--window-size=1200,630", f"--screenshot={target}", src.as_uri()],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            print("wrote", target, target.stat().st_size if target.exists() else "MISSING")
    shutil.rmtree(_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
