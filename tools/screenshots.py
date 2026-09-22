# -*- coding: utf-8 -*-
"""Headless-Chrome screenshots of the public pages for review notes.

    python tools/screenshots.py --base http://127.0.0.1:5001 --out shots/after

Needs Google Chrome or Edge installed (no pip deps). Fonts load from Google
Fonts if the machine is online, so the renders match the live site. Pages are
captured at desktop (1280), tablet (768) and narrow (520) widths in English and
Hebrew. Nothing here touches a database.
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chrome",
]
PAGES = {"home": "/", "sample": "/sample", "catalog": "/catalog", "shana": "/shana-rishonah",
         "how": "/how-it-works", "about": "/about", "privacy": "/privacy", "advertise": "/advertise", "guides": "/guides",
         "guide": "/guides/sizes-plugs-delivery"}
# headless Chrome on Windows won't lay out narrower than ~500px, so phone-width
# checks are done in the in-app Browser pane (resize_window "mobile") instead.
WIDTHS = {"desktop": (1280, 2400), "tablet": (768, 2400), "narrow": (520, 2200)}


def find_browser():
    for c in CANDIDATES:
        if os.path.isfile(c) or shutil.which(c):
            return c
    raise SystemExit("no Chrome/Edge found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5001")
    ap.add_argument("--out", default="shots")
    ap.add_argument("--pages", default=",".join(PAGES))
    ap.add_argument("--widths", default=",".join(WIDTHS))
    ap.add_argument("--langs", default="en,he")
    args = ap.parse_args()
    exe = find_browser()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in args.pages.split(","):
        path = PAGES[name]
        for lang in args.langs.split(","):
            for wname in args.widths.split(","):
                w, h = WIDTHS[wname]
                sep = "&" if "?" in path else "?"
                url = f"{args.base}{path}{sep}lang={lang}"
                target = out / f"{name}-{lang}-{wname}.png"
                cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                       "--virtual-time-budget=4000", f"--window-size={w},{h}",
                       f"--screenshot={target}", url]
                subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=90)
                print("wrote", target)


if __name__ == "__main__":
    main()
