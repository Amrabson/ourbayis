# -*- coding: utf-8 -*-
"""/admin/insights and `manage.py insights`: read-only business view."""
import json
from datetime import datetime, timedelta, timezone

from conftest import signup, create_registry, add_item
from test_p1 import admin_login


def _today():
    return datetime.now(timezone.utc).date()


def _day(n_ago):
    return (_today() - timedelta(days=n_ago)).isoformat()


def _stamp(n_ago):
    return _day(n_ago) + " 12:00:00"


def _admin(app_module):
    c = app_module.app.test_client()
    admin_login(c)
    return c


def _seed(app_module, client):
    """One couple + registry with 5 items, a reservation, a chip-in, a cash gift, a quoted lead,
    and funnel rows inside (today, 3 days ago) and outside (20 / 60 days ago) the 7-day period."""
    signup(client)
    create_registry(client)
    for i in range(5):
        add_item(client, name=f"Item {i}", price_nis="300")
    with app_module.app.app_context():
        db = app_module.get_db()
        reg = db.execute("SELECT id FROM registries").fetchone()["id"]
        item = db.execute("SELECT id FROM registry_items ORDER BY id").fetchone()["id"]
        db.execute("UPDATE registries SET views=3")
        ins = ("INSERT INTO claims (registry_id, item_id, guest_name, qty, kind, status, amount_minor,"
               " currency, created_at) VALUES (?,?,?,?,?,?,?,?,?)")
        db.execute(ins, (reg, item, "G1", 1, "item", "reserved", None, None, _stamp(1)))
        db.execute(ins, (reg, item, "G2", 0, "chip", "reserved", 18000, "ILS", _stamp(1)))
        db.execute(ins, (reg, None, "G3", 1, "cash", "reported", 50000, "ILS", _stamp(1)))
        db.execute(ins, (reg, item, "Old", 1, "item", "reserved", None, None, _stamp(60)))
        db.execute("INSERT INTO shana_requests (name, status, quote_json, created_at, next_action,"
                   " next_action_date) VALUES (?,?,?,?,?,?)",
                   ("Lead Q", "quoted",
                    json.dumps(dict(quoted_price=10000, total_cost=7000, profit=3000, margin_pct=30.0)),
                    _stamp(2), "Call back", _day(5)))
        db.execute("INSERT INTO shana_requests (name, created_at) VALUES (?,?)", ("Old lead", _stamp(60)))
        for day, name, n in ((_day(0), "view:index", 10), (_day(3), "view:setup_cost", 4),
                             (_day(20), "view:index", 100), (_day(45), "view:index", 1000),
                             (_day(1), "handoff_click", 6), (_day(20), "handoff_click", 50),
                             (_day(1), "handoff_click_tagged", 2), (_day(1), "signup", 5)):
            db.execute("INSERT INTO funnel_events (day, name, n) VALUES (?,?,?)", (day, name, n))
    return reg


def _data(app_module, days):
    with app_module.app.app_context():
        return app_module.insights_data(app_module.get_db(), days)


def test_requires_admin(client):
    r = client.get("/admin/insights")
    assert r.status_code == 302 and "/admin/login" in r.headers["Location"]


def test_renders_on_empty_db(app_module):
    c = _admin(app_module)
    for q in ("", "?days=7", "?days=90", "?days=all", "?days=bogus"):
        r = c.get("/admin/insights" + q)
        assert r.status_code == 200, q
    html = c.get("/admin/insights").get_data(as_text=True)
    assert "No page views yet" in html and "Nothing overdue" in html and "SMTP configured" in html
    assert 'href="/admin/insights"' in c.get("/admin").get_data(as_text=True)


def test_post_not_allowed(app_module):
    c = _admin(app_module)
    assert c.post("/admin/insights").status_code in (400, 405)


def test_seeded_numbers(app_module, client):
    _seed(app_module, client)
    d = _data(app_module, 30)
    # 30 days: today(10) + 3 days ago(4) + 20 days ago(100) = 114; the 45-day-old row is the previous period
    assert d["views_total"] == 114
    assert d["views_prev"] == 1000
    assert {p["name"]: p["n"] for p in d["key_pages"]}["Setup cost calculator"] == 4
    assert d["top_pages"][0]["name"] == "Home" and d["top_pages"][0]["n"] == 110
    g = d["guests"]
    assert g["reservations"] == 1 and g["brachos"] == 0 and g["avg_per_registry"] == 1.0
    assert (g["chip"]["n"], g["chip"]["pledged"]) == (1, 180)
    assert (g["cash"]["n"], g["cash"]["reported"]) == (1, 500)
    f = {s["label"]: s for s in d["funnel"]}
    assert f["Signed up"]["n"] == 1 and f["Created a registry"]["n"] == 1 and f["Has 5+ gifts"]["n"] == 1
    assert f["Shared it"]["n"] == 1 and f["Got a first reservation"]["n"] == 1
    assert f["Got a first reservation"]["pct"] == 100 and f["Signed up"]["ev"] >= 5  # 5 seeded (the live signup may add one)
    L = d["leads"]
    assert L["total"] == 1 and L["quotes"] == 1 and (L["price"], L["cost"], L["profit"]) == (10000, 7000, 3000)
    assert L["avg_margin"] == 30.0 and [o["name"] for o in L["overdue"]] == ["Lead Q"]
    assert d["clicks"]["period"] == (56, 0) and d["clicks"]["tagged"][0] == 2

    html = _admin(app_module).get("/admin/insights").get_data(as_text=True)
    assert "Lead Q" in html and "Old lead" not in html
    assert "₪10,000" in html and "₪180" in html and "₪500" in html
    assert "lifetime totals" in html


def test_days_filter_and_bogus_fallback(app_module, client):
    _seed(app_module, client)
    d7 = _data(app_module, 7)
    assert d7["views_total"] == 14 and d7["views_prev"] == 0   # the 20-day-old row is older than the 7 days before
    assert d7["guests"]["reservations"] == 1
    assert _data(app_module, None)["views_total"] == 1114
    assert _data(app_module, None)["guests"]["reservations"] == 2
    assert _data(app_module, None)["views_prev"] is None
    c = _admin(app_module)
    h7 = c.get("/admin/insights?days=7").get_data(as_text=True)
    h30 = c.get("/admin/insights?days=30").get_data(as_text=True)
    hb = c.get("/admin/insights?days=bogus").get_data(as_text=True)
    assert "last 7 days" in h7 and "last 30 days" in hb
    assert h7 != h30 and hb == h30
    assert "all time" in c.get("/admin/insights?days=all").get_data(as_text=True)


def test_step_percentages_with_zeros(app_module):
    d = _data(app_module, 30)
    assert all(s["n"] == 0 for s in d["funnel"])
    assert all(s["pct"] is None for s in d["funnel"])
    assert d["guests"]["avg_per_registry"] == 0 and d["clicks"]["covered_pct"] is None
    assert d["leads"]["avg_margin"] is None


def test_catalog_health_and_mail(app_module):
    with app_module.app.app_context():
        db = app_module.get_db()
        db.execute("UPDATE catalog_items SET active=0")
        db.execute("DELETE FROM affiliate_rules")
        db.execute("UPDATE catalog_items SET active=1, url='https://shop.example.com/a', clicks=0,"
                   " price_status='verified', price_checked_at='2020-01-01' WHERE id=("
                   "SELECT MIN(id) FROM catalog_items)")
        db.execute("INSERT INTO mail_outbox (to_addr, subject, body, status) VALUES ('a@b.c','s','b','failed')")
    d = _data(app_module, 30)
    k = d["catalog"]
    assert (k["active"], k["with_link"], k["verified"], k["stale"], k["zero_clicks"]) == (1, 1, 1, 1, 1)
    assert k["hosts_without_rule"] == 1
    assert d["mail"] == dict(queued=0, failed=1, smtp=False)
    html = _admin(app_module).get("/admin/insights").get_data(as_text=True)
    assert "/admin/catalog?stale=1" in html and "/admin/outbox" in html


def test_manage_insights_prints_headlines(app_module, client, capsys, monkeypatch):
    _seed(app_module, client)
    import manage
    import argparse
    assert manage.cmd_insights(argparse.Namespace(days=30)) == 0
    out = capsys.readouterr().out
    assert "last 30 days" in out and "page views: 114" in out
    assert "reservations: 1" in out and "chip-ins: 1 (pledged 180" in out
    assert "Got a first reservation: 1 (100% of previous step)" in out
    assert manage.cmd_insights(argparse.Namespace(days=0)) == 0
    assert "all time" in capsys.readouterr().out
