# -*- coding: utf-8 -*-
"""OurBayis designed emails: the HTML part that travels beside every plain-text body.

`render_mail_html()` fills templates/email/base.html (table layout, inline styles only). It uses its own
Jinja environment, so it works with no Flask request/app context (manage.py, tests). Callers keep the
text body exactly as it was and pass the same paragraphs here; building HTML must never stop a send,
so `safe_html()` swallows and logs any error and returns None (the mail then goes out as text only)."""
import logging
import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

log = logging.getLogger("ourbayis.mailhtml")

_ENV = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")),
    autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)

_URL = re.compile(r"https?://[^\s<>\"]+")
_TRAIL = ".,;:)!?”’"


def _linkify(text, typed=()):
    """Escape `text`, wrap anything the user typed in <bdi>, turn URLs into links, newlines into <br>."""
    out, pos = [], 0
    for m in _URL.finditer(text):
        url = m.group(0)
        tail = ""
        while url and url[-1] in _TRAIL:
            tail, url = url[-1] + tail, url[:-1]
        out.append(_typed(text[pos:m.start()], typed))
        out.append(Markup('<a href="{u}" style="color:#8a5f1e;word-break:break-all;">{u}</a>').format(u=url))
        out.append(_typed(tail, typed))
        pos = m.end()
    out.append(_typed(text[pos:], typed))
    return Markup(str(Markup("").join(out)).replace("\n", "<br>\n"))


def _typed(text, typed):
    """Escaped text with each string a person typed wrapped in <bdi>, so mixed Hebrew/English reads right."""
    s = str(escape(text))
    for t in sorted({str(x).strip() for x in typed if x and len(str(x).strip()) > 2}, key=len, reverse=True):
        # whole words only, so a short name never marks up the middle of another word
        s = re.sub(r"(?<!\w)" + re.escape(str(escape(t))) + r"(?!\w)",
                   lambda m: "\x00" + m.group(0) + "\x01", s)
    return Markup(s.replace("\x00", "<bdi>").replace("\x01", "</bdi>"))


def _buttons(button):
    if not button:
        return []
    if isinstance(button, tuple):
        return [button]
    return [b for b in button if b and b[1]]


def section(lang, paragraphs, button=None, item=None, typed=()):
    """One language's block: paragraphs (plain text) in order, each button placed right after the
    paragraph that contained its URL (the URL is lifted out of the text and shown under the button);
    buttons whose URL isn't in any paragraph go at the end."""
    btns = _buttons(button)
    placed = [False] * len(btns)
    blocks = []
    for para in paragraphs:
        para = (para or "").strip()
        if not para:
            continue
        here = []
        for i, (label, url) in enumerate(btns):
            if not placed[i] and url and url in para:
                para = para.replace(url, "", 1)
                placed[i] = True
                here.append((label, url))
        para = re.sub(r"[ \t]+\n", "\n", para).strip()
        if here and para.endswith(":"):
            # "… The registry: <url>" — the URL became the button, so its lead-in would dangle: drop a
            # bare label ("The registry:"), or end a real sentence ("Next: order it from KSP:") with "."
            head, _, last = para[:-1].rpartition(". ")
            if head and len(last.split()) <= 3:
                para = head + "."
            elif not head and len(last.split()) <= 3:
                para = ""
            else:
                para = para[:-1].rstrip() + "."
        if para:
            blocks.append({"html": _linkify(para, typed)})
        for b in here:
            blocks.append({"button": b})
    for i, b in enumerate(btns):
        if not placed[i]:
            blocks.append({"button": b})
    img = (item or {}).get("image") or ""
    return {"lang": lang, "dir": "rtl" if lang == "he" else "ltr", "blocks": blocks,
            "item_name": (item or {}).get("name") or "",
            "item_image": img if img.startswith("https://") else ""}


def render_mail_html(lang, paragraphs, button=None, item=None, footer=None, typed=(), also=None):
    """Designed HTML for one email. `paragraphs`: plain-text strings (the same i18n text the text body
    uses). `button`: (label, url) or a list of them. `item`: {"name", "image"} for a gift picture.
    `footer`: the email's own footer text (links are linkified). `typed`: strings people typed (guest
    names, messages, item names) to wrap in <bdi>. `also`: kwargs dict for a second language block
    (guests whose language was never recorded get both, like the text version)."""
    secs = [section(lang, paragraphs, button, item, typed)]
    if also:
        secs.append(section(also["lang"], also["paragraphs"], also.get("button"), also.get("item"),
                            also.get("typed", ())))
    foot = _linkify(footer.strip(), typed) if footer and footer.strip() else None
    return _ENV.get_template("email/base.html").render(
        lang=lang, dir="rtl" if lang == "he" else "ltr", sections=secs, footer=foot)


def split_body(body, footer=None):
    """(paragraphs, footer) from a finished text body: blank-line separated blocks, with `footer`
    (when the body ends with it) lifted off the end."""
    body = (body or "").strip()
    if footer and body.endswith(footer.strip()):
        body = body[:len(body) - len(footer.strip())].strip()
    return [p for p in re.split(r"\n\s*\n", body) if p.strip()], footer


def safe_html(*args, **kwargs):
    """render_mail_html that never raises: on any error log the class only and return None."""
    try:
        return render_mail_html(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — the text email must still go out
        log.warning("mail html failed: %s", type(e).__name__)
        return None
