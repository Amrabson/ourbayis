# -*- coding: utf-8 -*-
"""manage.py check-prices, ob_pricecheck and /admin/prices. NO network: ob_linkinfo.lookup is patched."""
import json
import re
import shutil
import sys
from datetime import date, timedelta

import pytest

from conftest import BASE, create_registry, get_csrf, signup
from test_p1 import admin_login

TODAY = date.today().isoformat()
OLD = (date.today() - timedelta(days=60)).isoformat()


class Fake:
    """Stands in for ob_linkinfo.lookup: url -> result dict (or callable)."""
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        r = self.results.get(url)
        if callable(r):
            r = r(url)
        return r if r is not None else page(error="fetch_failed")


def page(name="Tefal frying pan 28cm", price=100, currency="ILS", image=None, error=None, status=None, brand=None):
    r = {"ok": error is None, "error": error, "url": "", "host": "", "name": None if error else name,
         "price": price, "currency": currency, "image": image, "brand": brand, "site_name": None}
    if status:
        r["status"] = status
    return r


@pytest.fixture
def env(app_module, monkeypatch):
    fake = Fake()
    monkeypatch.setattr(app_module.ob_linkinfo, "lookup", fake)
    monkeypatch.setattr(app_module.ob_pricecheck.time, "sleep", lambda s: None)
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("DELETE FROM catalog_items")
        yield app_module, db, fake


def mk(db, name, host="www.vardinon.co.il", price=100, checked=OLD, seed_key=None, status="verified",
       brand="Tefal", model="", image="", n=[0]):
    n[0] += 1
    url = "https://%s/p/%d" % (host, n[0])
    cur = db.execute(
        "INSERT INTO catalog_items (name, brand, model, category, price_nis, store, url, image, active,"
        " price_status, price_checked_at, price_source, seed_key) VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?)",
        (name, brand, model, "kitchen", price, host, url, image, status, checked, "orig", seed_key))
    return cur.lastrowid, url


def row(db, i):
    return db.execute("SELECT * FROM catalog_items WHERE id=?", (i,)).fetchone()


def statuses(res):
    return {r["item"]["id"]: r["status"] for r in res["rows"]}


# ---------------------------------------------------------------- classification
def test_classification(env):
    m, db, fake = env
    same, u1 = mk(db, "Frying pan", price=100)
    chg, u2 = mk(db, "Frying pan 2", price=100)
    nop, u3 = mk(db, "Frying pan 3")
    usd, u4 = mk(db, "Frying pan 4")
    bad, u5 = mk(db, "Frying pan 5")
    mis, u6 = mk(db, "Frying pan 6")
    fake.results = {
        u1: page(price=100), u2: page(price=119.6), u3: page(price=None),
        u4: page(price=30, currency="USD"), u5: page(error="no_data"),
        u6: page(name="Samsung television 55 inch"),
    }
    res = m.ob_pricecheck.run(db, delay=2)
    s = statuses(res)
    assert s == {same: "same", chg: "changed", nop: "no price", usd: "no price", bad: "failed", mis: "mismatch"}
    by = {r["item"]["id"]: r for r in res["rows"]}
    assert by[chg]["new"] == 120 and round(by[chg]["pct"]) == 20
    assert "currency USD" in by[usd]["detail"]
    assert "different product" in by[mis]["detail"]
    n = db.execute("SELECT COUNT(*) FROM price_checks").fetchone()[0]
    assert n == 6


def test_picture_difference_reported_not_replaced(env):
    m, db, fake = env
    i, u = mk(db, "Frying pan", image="https://img.example/a.jpg")
    fake.results = {u: page(image="https://img.example/b.jpg")}
    res = m.ob_pricecheck.run(db, delay=2)
    assert "picture differs" in res["rows"][0]["detail"]
    m.ob_pricecheck.apply_rows(db, [res["rows"][0]["check_id"]])
    assert row(db, i)["image"] == "https://img.example/a.jpg"


def test_hebrew_name_matches(env):
    m, db, fake = env
    i, u = mk(db, "Frying pan", brand="")
    db.execute("UPDATE catalog_items SET name_he='מחבת טפאל' WHERE id=?", (i,))
    fake.results = {u: page(name="מחבת טפאל 28 ס\"מ")}
    assert statuses(m.ob_pricecheck.run(db, delay=2))[i] == "same"


def test_older_than_and_store_filters(env):
    m, db, fake = env
    fresh, u1 = mk(db, "Frying pan", checked=TODAY)
    empty, u2 = mk(db, "Frying pan b", checked="")
    other, u3 = mk(db, "Frying pan c", host="www.bug.co.il")
    fake.results = {u2: page(price=100), u3: page(price=100)}
    res = m.ob_pricecheck.run(db, stores=["vardinon.co.il"], delay=2)
    assert set(statuses(res)) == {empty}
    res = m.ob_pricecheck.run(db, delay=2)
    assert set(statuses(res)) == {empty, other}
    assert u1 not in fake.calls
    assert len(m.ob_pricecheck.run(db, limit=1, delay=2)["rows"]) == 1


# ---------------------------------------------------------------- never fetch / cut-offs
def test_no_fetch_hosts_never_looked_up(env):
    m, db, fake = env
    for h in ("ksp.co.il", "www.payngo.co.il", "www.homecenter.co.il"):
        mk(db, "Frying pan", host=h)
    ok, u = mk(db, "Frying pan ok")
    fake.results = {u: page()}
    res = m.ob_pricecheck.run(db, delay=2)
    assert fake.calls == [u]
    assert res["skipped"] == {"ksp.co.il": 1, "payngo.co.il": 1, "homecenter.co.il": 1}
    res = m.ob_pricecheck.run(db, stores=["ksp.co.il"], delay=2)    # even when asked for explicitly
    assert fake.calls == [u] and res["rows"] == []


def test_two_consecutive_failures_cut_host_off(env):
    m, db, fake = env
    ids = [mk(db, "Frying pan %d" % i) for i in range(4)]
    other, ou = mk(db, "Frying pan z", host="www.bug.co.il")
    fake.results = {ou: page(), **{u: page(error="fetch_failed") for _, u in ids}}
    res = m.ob_pricecheck.run(db, delay=2)
    s = statuses(res)
    assert [s[i] for i, _ in ids] == ["failed", "failed", "skipped", "skipped"]
    assert s[other] == "same"
    assert len(fake.calls) == 3                      # 2 vardinon + 1 bug
    assert db.execute("SELECT COUNT(*) FROM price_checks").fetchone()[0] == 3   # skipped aren't logged


def test_failure_streak_resets_on_success(env):
    m, db, fake = env
    a, ua = mk(db, "Frying pan a")
    b, ub = mk(db, "Frying pan b")
    c, uc = mk(db, "Frying pan c")
    fake.results = {ua: page(error="fetch_failed"), ub: page(), uc: page(error="fetch_failed")}
    s = statuses(m.ob_pricecheck.run(db, delay=2))
    assert s == {a: "failed", b: "same", c: "failed"}


@pytest.mark.parametrize("code", [429, 403, 999])
def test_hard_status_stops_host_immediately(env, code):
    m, db, fake = env
    a, ua = mk(db, "Frying pan a")
    b, ub = mk(db, "Frying pan b")
    fake.results = {ua: page(error="fetch_failed", status=code), ub: page()}
    s = statuses(m.ob_pricecheck.run(db, delay=2))
    assert s == {a: "failed", b: "skipped"} and fake.calls == [ua]


def test_delay_honoured_and_minimum_enforced(env, monkeypatch):
    m, db, fake = env
    for i in range(3):
        mk(db, "Frying pan %d" % i)
    for i in range(2):
        mk(db, "Frying pan %d" % i, host="www.bug.co.il")
    sleeps = []
    monkeypatch.setattr(m.ob_pricecheck.time, "sleep", sleeps.append)
    fake.results = {}
    for r in db.execute("SELECT url FROM catalog_items"):
        fake.results[r["url"]] = page()
    m.ob_pricecheck.run(db, delay=5.0)
    assert sleeps == [5.0] * 3                       # between requests to the same host only
    sleeps.clear()
    res = m.ob_pricecheck.run(db, delay=0.1)
    assert res["delay"] == 2.0 and sleeps and all(s >= 2.0 for s in sleeps)


# ---------------------------------------------------------------- CLI: dry run / apply / seed
def run_cli(m, monkeypatch, *argv):
    sys.modules.pop("manage", None)
    import manage
    monkeypatch.setattr(sys, "argv", ["manage.py", "check-prices", *argv])
    with pytest.raises(SystemExit) as e:
        manage.main()
    return e.value.code


def test_dry_run_changes_nothing(env, monkeypatch, capsys):
    m, db, fake = env
    i, u = mk(db, "Frying pan", price=100)
    fake.results = {u: page(price=150)}
    before = dict(row(db, i))
    assert run_cli(m, monkeypatch) in (0, None)
    out = capsys.readouterr().out
    assert "changed" in out and "+50.0%" in out and "Dry run" in out
    assert dict(row(db, i)) == before
    assert db.execute("SELECT applied FROM price_checks").fetchone()[0] == 0


def test_apply_updates_exact_rows_and_fields(env, monkeypatch):
    m, db, fake = env
    same, us = mk(db, "Frying pan", price=100, seed_key="s1")
    chg, uc = mk(db, "Frying pan b", price=100, status="estimate")
    mis, um = mk(db, "Frying pan c", price=100)
    bad, ub = mk(db, "Frying pan d", price=100)
    fake.results = {us: page(price=100), uc: page(price=130), um: page(name="Television"), ub: page(error="fetch_failed")}
    b_mis, b_bad = dict(row(db, mis)), dict(row(db, bad))
    run_cli(m, monkeypatch, "--apply")
    r = row(db, same)
    assert (r["price_nis"], r["price_checked_at"], r["price_status"], r["price_source"]) == (100, TODAY, "verified", "orig")
    r = row(db, chg)
    assert (r["price_nis"], r["price_checked_at"], r["price_status"]) == (130, TODAY, "verified")
    assert r["price_source"] == "vardinon.co.il page re-read %s by check-prices (was ₪100)" % TODAY
    assert dict(row(db, mis)) == b_mis and dict(row(db, bad)) == b_bad
    applied = {x["item_id"]: x["applied"] for x in db.execute("SELECT * FROM price_checks")}
    assert applied == {same: 1, chg: 1, mis: 0, bad: 0}
    pc = db.execute("SELECT * FROM price_checks WHERE item_id=?", (chg,)).fetchone()
    assert (pc["old_minor"], pc["new_minor"], pc["host"], pc["status"]) == (10000, 13000, "www.vardinon.co.il", "changed")


def test_write_seed_edits_only_targets_and_keeps_crlf(env, monkeypatch, tmp_path):
    m, db, fake = env
    seed_copy = tmp_path / "seed_catalog.json"
    shutil.copy(BASE / "seed_catalog.json", seed_copy)
    original = seed_copy.read_bytes()
    seed = json.loads(original.decode("utf-8"))["items"]
    target = next(x for x in seed if x["seed_key"])
    other = next(x for x in seed if x is not target)
    t_i, tu = mk(db, target["name"], price=target["price_nis"], seed_key=target["seed_key"])
    fake.results = {tu: page(name=target["name"], price=target["price_nis"] + 25)}
    run_cli(m, monkeypatch, "--apply", "--write-seed", "--seed-file", str(seed_copy))
    new = seed_copy.read_bytes()
    assert new != original and b"\r\n" in new and new.count(b"\n") == new.count(b"\r\n")
    got = {x["seed_key"]: x for x in json.loads(new.decode("utf-8"))["items"]}
    g = got[target["seed_key"]]
    assert g["price_nis"] == target["price_nis"] + 25 and g["price_checked_at"] == TODAY
    assert g["price_status"] == "verified" and "check-prices" in g["price_source"]
    for k in target:
        if k not in ("price_nis", "price_checked_at", "price_status", "price_source"):
            assert g[k] == target[k]
    # the unrelated item's raw bytes are untouched
    def block(raw, key):
        txt = raw.decode("utf-8")
        i = txt.index('"seed_key": "%s"' % key)
        return txt[txt.rindex("    {", 0, i):txt.index("    }", i)]
    assert block(new, other["seed_key"]) == block(original, other["seed_key"])
    # exactly four lines differ
    a, b = original.split(b"\r\n"), new.split(b"\r\n")
    assert len(a) == len(b) and sum(1 for x, y in zip(a, b) if x != y) <= 4


def test_patch_seed_inserts_missing_field(app_module):
    pc = app_module.ob_pricecheck
    text = '{\r\n  "items": [\r\n    {\r\n      "seed_key": "a",\r\n      "price_nis": 5\r\n    }\r\n  ]\r\n}\r\n'
    new, done = pc.patch_seed_text(text, {"a": {"price_nis": 7, "price_status": "verified"}})
    assert done == {"a"} and json.loads(new)["items"][0] == {"seed_key": "a", "price_nis": 7, "price_status": "verified"}
    assert "\n" not in new.replace("\r\n", "")


def test_write_seed_requires_apply(env, monkeypatch):
    m, db, fake = env
    assert run_cli(m, monkeypatch, "--write-seed") == 2


# ---------------------------------------------------------------- couples' items page
def test_couples_see_store_price_after_apply(env, monkeypatch, client):
    m, db, fake = env
    cid, u = mk(db, "Frying pan", price=100, checked="2026-01-01")
    signup(client)
    create_registry(client)
    tok = get_csrf(client.get("/registry/items").get_data(as_text=True))
    client.post("/registry/items/add", data=dict(csrf_token=tok, catalog_id=cid), follow_redirects=True)
    html = client.get("/registry/items").get_data(as_text=True)
    assert "Store price now" not in html
    db.execute("UPDATE registry_items SET price_checked_at='2026-01-01'")
    fake.results = {u: page(price=140)}
    run_cli(m, monkeypatch, "--apply")
    html = client.get("/registry/items").get_data(as_text=True)
    assert "Store price now ₪140" in html


# ---------------------------------------------------------------- admin page
def admin(app_module):
    c = app_module.app.test_client()
    admin_login(c)
    return c


def test_admin_prices_requires_admin(env, client):
    m, db, fake = env
    for path in ("/admin/prices",):
        assert client.get(path).status_code == 302
    for path in ("/admin/prices/1/apply", "/admin/prices/apply-all"):
        r = client.post(path, data={})
        assert r.status_code in (302, 400)
        assert "admin/login" in (r.headers.get("Location") or "") or r.status_code == 400


def test_admin_prices_lists_and_applies(env, monkeypatch):
    m, db, fake = env
    a, ua = mk(db, "Frying pan", price=100)
    b, ub = mk(db, "Frying pan b", price=100)
    c, uc = mk(db, "Frying pan c", price=100, host="www.bug.co.il")
    d, ud = mk(db, "Frying pan d", price=100)
    fake.results = {ua: page(price=100), ub: page(price=120), uc: page(name="Television"), ud: page(error="fetch_failed")}
    m.ob_pricecheck.run(db, delay=2)
    cl = admin(m)
    html = cl.get("/admin/prices").get_data(as_text=True)
    assert "Price checks" in html and "Frying pan b" in html and "python manage.py check-prices" in html
    assert "ksp.co.il" not in html.split("Never requested")[0]
    assert f"/admin/catalog/{b}/edit" in html and "public page" in html
    only = cl.get("/admin/prices?status=changed").get_data(as_text=True)
    assert "Frying pan b" in only and "Frying pan c" not in only
    assert "Frying pan c" in cl.get("/admin/prices?store=www.bug.co.il").get_data(as_text=True)
    assert "Frying pan d" not in cl.get("/admin/prices?store=www.bug.co.il").get_data(as_text=True)
    # CSRF
    assert cl.post("/admin/prices/apply-all", data={}).status_code == 400
    tok = get_csrf(html)
    pcb = db.execute("SELECT id FROM price_checks WHERE item_id=?", (b,)).fetchone()[0]
    cl.post(f"/admin/prices/{pcb}/apply", data=dict(csrf_token=tok))
    assert row(db, b)["price_nis"] == 120 and row(db, a)["price_checked_at"] == OLD
    cl.post(f"/admin/prices/{pcb}/apply", data=dict(csrf_token=tok))          # idempotent
    assert row(db, b)["price_nis"] == 120
    cl.post("/admin/prices/apply-all", data=dict(csrf_token=tok))
    assert row(db, a)["price_checked_at"] == TODAY
    assert row(db, c)["price_checked_at"] == OLD and row(db, d)["price_checked_at"] == OLD   # mismatch / failed untouched
    cl.post("/admin/prices/apply-all", data=dict(csrf_token=tok))
    assert db.execute("SELECT COUNT(*) FROM price_checks WHERE applied=1").fetchone()[0] == 2
    assert "Apply all" not in cl.get("/admin/prices").get_data(as_text=True)


def test_admin_apply_refuses_when_price_moved(env):
    m, db, fake = env
    a, ua = mk(db, "Frying pan", price=100)
    fake.results = {ua: page(price=120)}
    m.ob_pricecheck.run(db, delay=2)
    db.execute("UPDATE catalog_items SET price_nis=111 WHERE id=?", (a,))     # admin edited meanwhile
    cl = admin(m)
    tok = get_csrf(cl.get("/admin/prices").get_data(as_text=True))
    pcid = db.execute("SELECT id FROM price_checks").fetchone()[0]
    cl.post(f"/admin/prices/{pcid}/apply", data=dict(csrf_token=tok))
    assert row(db, a)["price_nis"] == 111


def test_admin_prices_makes_no_outbound_request(env):
    m, db, fake = env
    mk(db, "Frying pan")
    cl = admin(m)
    cl.get("/admin/prices")
    assert fake.calls == []


def test_insights_shows_last_check(env):
    m, db, fake = env
    cl = admin(m)
    assert "Last price check: never run" in cl.get("/admin/insights").get_data(as_text=True)
    a, ua = mk(db, "Frying pan")
    b, ub = mk(db, "Frying pan b")
    c, uc = mk(db, "Frying pan c")
    fake.results = {ua: page(price=150), ub: page(error="no_data"), uc: page(price=100)}
    m.ob_pricecheck.run(db, delay=2)
    html = cl.get("/admin/insights").get_data(as_text=True)
    assert "Last price check: %s, 1 changed, 1 failed" % TODAY in html


def test_migration_idempotent(env):
    m, db, fake = env
    m.ob_db._m038_price_checks(db)
    m.ob_db._m038_price_checks(db)
    cols = [r[1] for r in db.execute("PRAGMA table_info(price_checks)")]
    assert cols[:8] == ["id", "run_at", "item_id", "host", "old_minor", "new_minor", "status", "applied"]
