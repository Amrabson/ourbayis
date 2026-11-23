# -*- coding: utf-8 -*-
"""/build-my-list: the six-question quiz, ob_quiz.quiz_pick, and its start / Shana handoff POSTs.
Expectations are built from the DB at test time, never from fixed seed contents."""
import re

import i18n
import ob_quiz

from conftest import signup, create_registry

BASE = dict(start="empty", bed="double", host="us", kitchen="separate", quality="mid", yomtov="no")
BIG = re.compile(r"\b(fridge|refrigerator|washing machine|dryer|dishwasher|air condition\w*)\b|^oven\b", re.I)
PAIR = re.compile(r"[x×]\s?2\b")


def _build(app_module, **kw):
    with app_module.app.app_context():
        b = ob_quiz.quiz_build(app_module.get_db(), dict(BASE, **kw))
    b["rows"] = [dict(r) for r in b["rows"]]
    return b


def _pick(app_module, **kw):
    with app_module.app.app_context():
        return [dict(r) for r in app_module.quiz_pick(app_module.get_db(), dict(BASE, **kw))]


def _members(app_module, group):
    with app_module.app.app_context():
        return [dict(r) for r in app_module.get_db().execute(
            "SELECT * FROM catalog_items WHERE active=1 AND option_group=?", (group,))]


def _ids(rows):
    return [r["id"] for r in rows]


def test_all_active_unique_one_per_option_group(app_module):
    for kw in (dict(), dict(start="partly", quality="nicer"),
               dict(start="furnished", quality="simple", host="most", yomtov="yes"),
               dict(bed="singles", kitchen="one")):
        rows = _pick(app_module, **kw)
        assert rows and len(_ids(rows)) == len(set(_ids(rows)))
        assert all(r["active"] == 1 for r in rows)
        groups = [r["option_group"] for r in rows if r["option_group"]]
        assert len(groups) == len(set(groups))


def test_furnished_drops_kitchen_and_appliances(app_module):
    with app_module.app.app_context():
        only = {r["id"] for r in app_module.get_db().execute(
            "SELECT id FROM catalog_items WHERE active=1 AND starter_group IN ('kitchen','appliances')")}
    furnished = _pick(app_module, start="furnished")
    assert len(furnished) < len(_pick(app_module, start="empty"))
    assert not any(r["id"] in only and not r["option_group"] for r in furnished)
    assert not any(BIG.search(r["name"]) for r in furnished)


def test_partly_drops_big_appliances_only(app_module):
    empty, partly = _pick(app_module, start="empty"), _pick(app_module, start="partly")
    assert not any(BIG.search(r["name"]) for r in partly)
    assert any(BIG.search(r["name"]) for r in empty)
    assert len(partly) < len(empty)


def test_quality_picks_the_tier(app_module):
    by_q = {q: _pick(app_module, quality=q) for q in ("simple", "mid", "nicer")}
    checked = 0
    for grp in ("pots-set", "towels", "sheet-set"):
        mem = _members(app_module, grp)
        if len(mem) < 2:
            continue
        got = {q: [r for r in rows if r["option_group"] == grp] for q, rows in by_q.items()}
        assert all(len(v) == 1 for v in got.values()), grp
        tiers = {m["tier"] for m in mem}
        checked += 1
        if "basic" in tiers:
            assert got["simple"][0]["tier"] == "basic"
        if "standard" in tiers:
            assert got["mid"][0]["tier"] == "standard"
        if "premium" in tiers:
            assert got["nicer"][0]["tier"] == "premium"
    assert checked


def test_kitchen_one_set_keeps_a_single_set(app_module):
    def fleishig_only(rows):
        return [r for r in rows if "fleishig" in r["name"].lower() and "milchig" not in r["name"].lower()]
    sep, one = _pick(app_module, kitchen="separate"), _pick(app_module, kitchen="one")
    assert fleishig_only(sep) and not fleishig_only(one)
    assert any("milchig" in r["name"].lower() for r in one)
    assert "quiz_why_kitchen_one" in _build(app_module, kitchen="one")["notes"]
    assert "quiz_why_kitchen_one" not in _build(app_module, kitchen="separate")["notes"]


def test_beds(app_module):
    unsure = _build(app_module, bed="unsure")
    assert not any(r["option_group"] in ob_quiz.BED_SIZE_GROUPS for r in unsure["rows"])
    assert "quiz_why_bed_unsure" in unsure["notes"]
    singles, double = _build(app_module, bed="singles"), _build(app_module, bed="double")
    assert max(singles["qty"].values()) >= 2
    for r in singles["rows"]:
        if PAIR.search(r["name"]):
            assert singles["qty"][r["id"]] == 1  # already sold as a pair: never doubled
    for r in double["rows"]:
        if r["option_group"] in ob_quiz.PER_BED_GROUPS:
            assert double["qty"][r["id"]] == 1


def test_hosting_and_yomtov_add_items(app_module):
    us, some, most = (_pick(app_module, host=h) for h in ("us", "some", "most"))
    assert len(most) >= len(some) >= len(us) and len(most) > len(us)
    no, yes, unsure = (_build(app_module, yomtov=y) for y in ("no", "yes", "unsure"))
    assert len(yes["rows"]) > len(no["rows"]) and len(unsure["rows"]) == len(no["rows"])
    assert "quiz_why_yt_unsure" in unsure["notes"] and "quiz_why_yt_yes" in yes["notes"]


def test_notes_count_and_normalise(app_module):
    for kw in (dict(), dict(bed="unsure", kitchen="one", host="most", yomtov="yes")):
        assert 2 <= len(_build(app_module, **kw)["notes"]) <= 4
    assert ob_quiz.normalise({"start": "x", "bed": "<b>", "quality": "nicer"}) == dict(BASE, quality="nicer")


def test_page_renders_both_languages_and_bogus_falls_back(client):
    r = client.get("/build-my-list")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Six questions, one draft list" in html and 'id="draft"' not in html
    assert html.count("<fieldset") == 6
    he = client.get("/build-my-list?lang=he").get_data(as_text=True)
    assert "שש שאלות, טיוטה אחת" in he
    bogus = client.get("/build-my-list?start=zzz&bed=%3Cx%3E&quality=").get_data(as_text=True)
    assert 'id="draft"' in bogus and "<x>" not in bogus
    assert re.search(r'value="empty"\s+checked', bogus)


def test_results_noindex_canonical_and_total(client, app_module):
    kw = dict(start="empty", bed="singles", host="some", kitchen="separate", quality="nicer", yomtov="yes")
    html = client.get("/build-my-list?" + "&".join(f"{k}={v}" for k, v in kw.items())).get_data(as_text=True)
    assert 'id="draft"' in html and "noindex" in html
    assert "?" not in "".join(re.findall(r'rel="canonical" href="([^"]*)"', html))  # base.html drops it when noindex
    b = _build(app_module, **kw)
    total = sum((r["price_nis"] or 0) * b["qty"][r["id"]] for r in b["rows"])
    tally = re.search(r'id="starter-tally"[^>]*>([^<]*)<', html).group(1)
    assert f"₪{total:,}" in tally and str(len(b["rows"])) in tally
    assert html.count('type="checkbox"') == len(b["rows"])
    he = client.get("/build-my-list?lang=he&start=empty").get_data(as_text=True)
    assert 'id="draft"' in he and "הטיוטה שלכם" in he
    bare = client.get("/build-my-list?lang=en").get_data(as_text=True)
    assert "noindex" not in bare and re.search(r'rel="canonical" href="[^"?]*/build-my-list"', bare)


def test_sitemap(client):
    sm = client.get("/sitemap.xml").get_data(as_text=True)
    assert "/build-my-list</loc>" in sm and "/build-my-list?lang=he</loc>" in sm


def _post(client, ids, path="/build-my-list/start", qty=None, **extra):
    client.get("/build-my-list?start=empty")
    with client.session_transaction() as s:
        tok = s.get("_csrf")
    data = {f"add_{i}": "1" for i in ids}
    for i, q in (qty or {}).items():
        data[f"qty_{i}"] = str(q)
    data.update(csrf_token=tok, **extra)
    return client.post(path, data=data)


def test_start_logged_out_pending_then_signup_adds(client, app_module):
    b = _build(app_module, bed="singles")
    ids = _ids(b["rows"])[:50]
    r = _post(client, ids, qty=b["qty"])
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")
    with client.session_transaction() as s:
        assert s["pending_add"] == ids
    signup(client, email="quiz@example.com")
    create_registry(client, couple="Quiz Couple")
    with app_module.app.app_context():
        rows = {r["catalog_id"]: r["qty_wanted"] for r in app_module.get_db().execute(
            "SELECT catalog_id, qty_wanted FROM registry_items")}
    assert set(ids) <= set(rows)
    for i in ids:
        assert rows[i] == b["qty"][i]


def test_start_logged_in_no_duplicates(client, app_module):
    signup(client, email="quiz2@example.com")
    create_registry(client)
    ids = _ids(_pick(app_module))[:50]
    r = _post(client, ids[:3])
    assert r.status_code == 302 and "/registry/items" in r.headers["Location"]
    assert _post(client, ids).status_code == 302
    with app_module.app.app_context():
        got = [r[0] for r in app_module.get_db().execute("SELECT catalog_id FROM registry_items")]
    assert sorted(got) == sorted(ids)


def test_shana_handoff_carries_ids(client, app_module):
    ids = _ids(_pick(app_module))[:10]
    r = _post(client, ids, path="/setup-cost/request")
    assert r.status_code == 302 and "/shana-rishonah" in r.headers["Location"]
    with client.session_transaction() as s:
        assert s["shana_list"] == ids


def test_csrf_honeypot_and_empty(client, app_module):
    ids = _ids(_pick(app_module))[:2]
    client.get("/build-my-list")
    r = client.post("/build-my-list/start", data={f"add_{ids[0]}": "1", "csrf_token": "nope"})
    assert r.status_code == 400
    _post(client, ids, website="http://spam.example")
    _post(client, [])
    with client.session_transaction() as s:
        assert not s.get("pending_add")


def test_links_present(client):
    for url in ("/", "/setup-cost", "/signup"):
        assert "/build-my-list" in client.get(url).get_data(as_text=True), url


def test_dashboard_empty_list_links_quiz(client):
    signup(client, email="quiz3@example.com")
    create_registry(client)
    assert "/build-my-list" in client.get("/dashboard").get_data(as_text=True)


def test_copy_rules_and_parity():
    banned = re.compile(r"shabbat|\bsafe|secure|\bbest\b|perfect", re.I)
    en = {k: v for k, v in i18n.T_EN.items() if k.startswith("quiz_")}
    assert en and set(en) == {k for k in i18n.T_HE if k.startswith("quiz_")}
    for k, v in en.items():
        assert not banned.search(v), k


def test_furniture_for_an_empty_flat_and_bed_frame_only_for_a_double(app_module):
    """2026-11-23: an empty flat gets the furniture starter group; the catalog's bed frames are 160x200
    doubles, so a couple choosing two single beds (or unsure) doesn't get one."""
    groups = lambda rows: {r["option_group"] for r in rows}  # noqa: E731
    empty = _pick(app_module, start="empty")
    assert any(r["starter_group"] == "furniture" for r in empty)
    assert "bed-frame" in groups(empty)
    assert "bed-frame" not in groups(_pick(app_module, start="empty", bed="singles"))
    assert "bed-frame" not in groups(_pick(app_module, start="empty", bed="unsure"))
    assert not any(r["starter_group"] == "furniture" for r in _pick(app_module, start="furnished"))


def test_two_single_beds_get_two_single_frames_and_mattresses(app_module):
    """2026-11-23: "two singles" swaps the 160x200 frame and mattress for 90x200 ones, two of each;
    "unsure" leaves beds and mattresses out; "nicer" picks the premium mattress."""
    dbl = _build(app_module, start="empty")
    groups = {r["option_group"] for r in dbl["rows"]}
    assert {"bed-frame", "mattress"} <= groups and not groups & {"bed-frame-single", "mattress-single"}
    sgl = _build(app_module, start="empty", bed="singles")
    by_group = {r["option_group"]: r for r in sgl["rows"] if r["option_group"]}
    assert "bed-frame" not in by_group and "mattress" not in by_group
    for g in ("bed-frame-single", "mattress-single"):
        assert sgl["qty"][by_group[g]["id"]] == 2, g
    unsure = {r["option_group"] for r in _build(app_module, start="empty", bed="unsure")["rows"]}
    assert not unsure & {"bed-frame", "mattress", "bed-frame-single", "mattress-single"}
    nicer = [r for r in _build(app_module, start="empty", quality="nicer")["rows"] if r["option_group"] == "mattress"]
    assert nicer and nicer[0]["tier"] == "premium"
