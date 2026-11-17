# -*- coding: utf-8 -*-
"""ob_pricecheck - re-read catalog store pages and report/apply price changes.

Driven by `manage.py check-prices` and by the apply buttons on /admin/prices.
The ONLY outbound fetching is ob_linkinfo.lookup() (the SSRF boundary); this module
never opens a socket itself and the web app never calls run() - only the CLI does.

Politeness: one request in flight at all times (single thread), hosts are processed
one after another, and `delay` seconds (never less than MIN_DELAY) pass between
consecutive requests to the same host. A host is dropped for the rest of the run after
CUTOFF_FAILS consecutive fetch_failed results, or at once on HTTP 429/403/999.
"""
import json
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import ob_db
import ob_linkinfo

NO_FETCH_HOSTS = {"ksp.co.il", "payngo.co.il", "homecenter.co.il"}
NO_FETCH_WHY = "store blocks reading or returns wrong products"
MIN_DELAY = 2.0
DEFAULT_DELAY = 3.0
DEFAULT_OLDER_THAN = 21
DEFAULT_LIMIT = 60
CUTOFF_FAILS = 2
HARD_STOP_STATUSES = (429, 403, 999)
STATUSES = ("same", "changed", "no price", "failed", "mismatch", "skipped")

_WORD_RE = re.compile(r"[0-9a-z֐-׿]+")
_STOP = {"the", "and", "with", "for", "set", "pcs", "piece", "pieces", "pack", "size", "from",
         "של", "עם", "סט", "את", "או"}


def norm_host(host):
    host = (host or "").lower().strip().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def url_host(url):
    try:
        return (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        return ""


def is_no_fetch(host):
    return norm_host(host) in NO_FETCH_HOSTS


def _words(*texts):
    out = set()
    for t in texts:
        for w in _WORD_RE.findall((t or "").lower()):
            if len(w) >= 3 and w not in _STOP:
                out.add(w)
    return out


def name_matches(item, page_name, page_brand=""):
    """True when the page's product name shares at least one significant word with the catalog
    item's name/model/brand (English or Hebrew). Lenient on purpose: it only catches pages that
    are about something else entirely. No words on either side -> can't tell -> True."""
    mine = _words(item["name"], item["name_he"], item["model"], item["model_he"], item["brand"])
    page = (page_name or "") + " " + (page_brand or "")
    if not mine or not page.strip():
        return True
    page_l = page.lower()
    page_w = _words(page)
    for w in mine:
        if w in page_w or w in page_l:
            return True
    return any(p in " ".join(mine) for p in page_w)


def _img_key(u):
    try:
        p = urlsplit(u or "")
        return (p.hostname or "").lower() + p.path
    except ValueError:
        return u or ""


def classify(item, r):
    """(status, new_price_or_None, detail) for one catalog row and the lookup() result."""
    if not r or not r.get("ok"):
        return "failed", None, (r or {}).get("error") or "fetch_failed"
    notes = []
    if r.get("image") and item["image"] and _img_key(r["image"]) != _img_key(item["image"]):
        notes.append("picture differs")
    if not name_matches(item, r.get("name"), r.get("brand")):
        return "mismatch", None, "page shows a different product? (" + (r.get("name") or "")[:60] + ")"
    cur = (r.get("currency") or "ILS").upper()
    if r.get("price") is None:
        return "no price", None, "; ".join(["no price on page"] + notes)
    if cur not in ("ILS", "NIS"):
        return "no price", None, "; ".join(["currency %s, not compared" % cur] + notes)
    new = int(round(float(r["price"])))
    if new <= 0:
        return "no price", None, "; ".join(["no price on page"] + notes)
    old = item["price_nis"] or 0
    if new == old:
        return "same", new, "; ".join(notes)
    return "changed", new, "; ".join(notes)


def pct(old, new):
    if not old or new is None:
        return None
    return (new - old) * 100.0 / old


# ------------------------------------------------------------------ selection
def select_items(db, stores=None, older_than=DEFAULT_OLDER_THAN, today=None):
    """Active catalog rows with a store link whose price_checked_at is empty or older than
    `older_than` days, oldest first. `stores` is a list of hosts (www. optional) or None."""
    today = today or date.today()
    cutoff = (today - timedelta(days=older_than)).isoformat()
    want = {norm_host(s) for s in stores} if stores else None
    rows = db.execute("SELECT * FROM catalog_items WHERE active=1 AND url!='' ORDER BY id").fetchall()
    out = []
    for r in rows:
        h = norm_host(url_host(r["url"]))
        if not h or (want is not None and h not in want):
            continue
        ca = (r["price_checked_at"] or "")[:10]
        if ca and ca >= cutoff:
            continue
        out.append(r)
    out.sort(key=lambda r: ((r["price_checked_at"] or "")[:10], r["id"]))
    return out


def active_hosts(db):
    """{normalised host: item count} over active items with a link."""
    c = {}
    for r in db.execute("SELECT url FROM catalog_items WHERE active=1 AND url!=''"):
        h = norm_host(url_host(r["url"]))
        if h:
            c[h] = c.get(h, 0) + 1
    return c


# ------------------------------------------------------------------ running
def run(db, stores=None, older_than=DEFAULT_OLDER_THAN, limit=DEFAULT_LIMIT,
        delay=DEFAULT_DELAY, today=None):
    """Fetch and classify; writes only the price_checks log. Returns
    {'rows': [...], 'skipped': {host: n}, 'delay': used_delay}. Each row is a dict:
    item, host, old, new, pct, status, detail, check_id."""
    today = today or date.today()
    delay = max(MIN_DELAY, float(delay))
    items = select_items(db, stores, older_than, today)
    skipped, todo = {}, []
    for it in items:
        h = norm_host(url_host(it["url"]))
        if h in NO_FETCH_HOSTS:
            skipped[h] = skipped.get(h, 0) + 1
        else:
            todo.append(it)
    todo = todo[:max(0, int(limit))]
    by_host = {}
    for it in todo:
        by_host.setdefault(url_host(it["url"]), []).append(it)
    run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for host in sorted(by_host):
        fails, stopped, first = 0, False, True
        for it in by_host[host]:
            if stopped:
                rows.append(_row(it, host, "skipped", None, "host stopped after repeated failures / rate limit"))
                continue
            if not first:
                time.sleep(delay)
            first = False
            r = ob_linkinfo.lookup(it["url"])
            status, new, detail = classify(it, r)
            if status == "failed" and (r or {}).get("error") == "fetch_failed":
                fails += 1
            else:
                fails = 0
            http = (r or {}).get("status")
            if status == "failed" and http in HARD_STOP_STATUSES:
                stopped = True
                detail = "HTTP %s; host stopped" % http
            elif fails >= CUTOFF_FAILS:
                stopped = True
                detail = (detail + "; host stopped").strip("; ")
            rows.append(_row(it, host, status, new, detail))
    with ob_db.write_txn(db):
        for row in rows:
            if row["status"] == "skipped":
                continue          # never attempted: nothing to record
            cur = db.execute(
                "INSERT INTO price_checks (run_at, item_id, host, old_minor, new_minor, status, applied, detail)"
                " VALUES (?,?,?,?,?,?,0,?)",
                (run_at, row["item"]["id"], row["host"], (row["old"] or 0) * 100,
                 None if row["new"] is None else row["new"] * 100, row["status"], row["detail"]))
            row["check_id"] = cur.lastrowid
    return {"rows": rows, "skipped": skipped, "delay": delay}


def _row(item, host, status, new, detail):
    old = item["price_nis"] or 0
    return {"item": item, "host": host, "old": old, "new": new, "pct": pct(old, new),
            "status": status, "detail": detail, "check_id": None}


# ------------------------------------------------------------------ applying
def _source(host, today, old):
    return "%s page re-read %s by check-prices (was ₪%s)" % (host, today, old)


def apply_check(db, check_id, today=None):
    """Apply one price_checks row. Returns (outcome, fields) where outcome is one of
    'applied', 'already', 'not-applicable', 'stale' (catalog price moved since the check,
    or a newer check exists) and fields is the dict written (for the seed)."""
    today = (today or date.today()).isoformat()
    with ob_db.write_txn(db):
        pc = db.execute("SELECT * FROM price_checks WHERE id=?", (check_id,)).fetchone()
        if not pc or pc["status"] not in ("same", "changed"):
            return "not-applicable", {}
        if pc["applied"]:
            return "already", {}
        latest = db.execute("SELECT MAX(id) FROM price_checks WHERE item_id=?", (pc["item_id"],)).fetchone()[0]
        item = db.execute("SELECT * FROM catalog_items WHERE id=?", (pc["item_id"],)).fetchone()
        if not item or latest != pc["id"] or (item["price_nis"] or 0) * 100 != (pc["old_minor"] or 0):
            return "stale", {}
        if pc["status"] == "same":
            fields = {"price_checked_at": today, "price_status": "verified"}
        else:
            old = item["price_nis"] or 0
            fields = {"price_nis": int(pc["new_minor"]) // 100, "price_checked_at": today,
                      "price_status": "verified",
                      "price_source": _source(norm_host(url_host(item["url"])) or pc["host"], today, old)}
        sets = ", ".join(k + "=?" for k in fields)
        db.execute("UPDATE catalog_items SET " + sets + " WHERE id=?", list(fields.values()) + [item["id"]])
        db.execute("UPDATE price_checks SET applied=1 WHERE id=?", (pc["id"],))
        return "applied", dict(fields, seed_key=item["seed_key"])


def apply_rows(db, check_ids, today=None):
    """Apply several; returns (counts dict, [(seed_key, fields)])."""
    counts = {"applied": 0, "already": 0, "not-applicable": 0, "stale": 0}
    seed = []
    for cid in check_ids:
        outcome, fields = apply_check(db, cid, today)
        counts[outcome] += 1
        if outcome == "applied" and fields.get("seed_key"):
            seed.append((fields["seed_key"], {k: v for k, v in fields.items() if k != "seed_key"}))
    return counts, seed


def latest_checks(db):
    """Latest price_checks row per item joined with the catalog row, newest run first."""
    return db.execute(
        "SELECT pc.*, c.name AS item_name, c.url AS item_url, c.store AS store, c.price_nis AS now_nis,"
        " c.seed_key AS seed_key, c.active AS active FROM price_checks pc"
        " JOIN catalog_items c ON c.id = pc.item_id"
        " WHERE pc.id = (SELECT MAX(id) FROM price_checks p2 WHERE p2.item_id = pc.item_id)"
        " ORDER BY CASE pc.status WHEN 'changed' THEN 0 WHEN 'mismatch' THEN 1 WHEN 'failed' THEN 2 ELSE 3 END,"
        " c.name").fetchall()


def last_run_summary(db):
    """{'run_at','changed','failed'} for the most recent run, or None."""
    last = db.execute("SELECT MAX(run_at) FROM price_checks").fetchone()[0]
    if not last:
        return None
    q = "SELECT COUNT(*) FROM price_checks WHERE run_at=? AND status=?"
    return {"run_at": last, "changed": db.execute(q, (last, "changed")).fetchone()[0],
            "failed": db.execute(q, (last, "failed")).fetchone()[0]}


# ------------------------------------------------------------------ seed file
def patch_seed_text(text, changes):
    """Edit only the given fields of the given items in the seed file's text, line by line, so
    every other byte (formatting, key order, CRLF) stays as it was. `changes` is
    {seed_key: {field: value}}. Returns (new_text, set of seed_keys patched)."""
    lines = text.splitlines(keepends=True)
    done = set()
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\r\n") != "    {":
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].rstrip("\r\n") not in ("    }", "    },"):
            j += 1
        key = None
        for k in range(i + 1, min(j, len(lines))):
            m = re.match(r'^      "seed_key": (".*?")\s*,?\s*$', lines[k])
            if m:
                key = json.loads(m.group(1))
                break
        if key in changes:
            eol = "\r\n" if lines[i].endswith("\r\n") else "\n"
            for field, value in changes[key].items():
                lit = json.dumps(value, ensure_ascii=False)
                pat = re.compile(r'^(      "%s": )(.*?)(,?)(\r?\n?)$' % re.escape(field))
                for k in range(i + 1, j):
                    m = pat.match(lines[k])
                    if m:
                        lines[k] = m.group(1) + lit + m.group(3) + m.group(4)
                        break
                else:
                    last = j - 1                      # last field line: gains a comma
                    body = lines[last].rstrip("\r\n")
                    lines[last] = body + "," + eol
                    lines.insert(j, '      "%s": %s%s' % (field, lit, eol))
                    j += 1
            done.add(key)
        i = j + 1
    new = "".join(lines)
    json.loads(new)                                   # still valid JSON or we raise
    return new, done


def write_seed(path, changes):
    """Apply patch_seed_text to the file at `path` (bytes in, bytes out, no newline translation)."""
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    new, done = patch_seed_text(text, changes)
    if new != text:
        with open(path, "wb") as fh:
            fh.write(new.encode("utf-8"))
    return done


def merge_changes(pairs):
    out = {}
    for key, fields in pairs:
        out.setdefault(key, {}).update(fields)
    return out
