# -*- coding: utf-8 -*-
"""Chip in (2026-11-11): several guests fund one big gift through the couple's own payment links.
A contribution is a claims row with kind='chip', qty=0 (so every SUM(qty) count ignores it) and the
guest's amount; a fully funded item counts as taken, a partly funded one stays open."""
import os
import re
import sqlite3

from conftest import add_item, create_registry, get_csrf, get_form_key, signup


def _db():
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.row_factory = sqlite3.Row
    return db


def _setup(client, price="4000", chip=True, pay=True):
    """A couple with one 'Fridge' (price, qty 1); returns (slug, item_id)."""
    signup(client, email="couple@example.com")
    create_registry(client, couple="Dina & Yossi")
    add_item(client, name="Fridge", price_nis=price, url="https://example.com/fridge")
    db = _db()
    db.execute("UPDATE registries SET visibility='public'" + (", paypal_url='https://paypal.me/dinayossi'" if pay else ""))
    if chip:
        db.execute("UPDATE registry_items SET chip_in=1")
    db.commit()
    return (db.execute("SELECT slug FROM registries").fetchone()["slug"],
            db.execute("SELECT id FROM registry_items").fetchone()["id"])


def _chip(app_module, slug, item_id, amount=None, preset=None, name="Cousin Dov", guest=None, form_key=None, **extra):
    guest = guest or app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    data = dict(csrf_token=get_csrf(page), form_key=form_key or get_form_key(page), guest_name=name, give="chip", **extra)
    if amount is not None:
        data["chip_amount"] = str(amount)
    if preset is not None:
        data["chip_preset"] = str(preset)
    return guest, guest.post(f"/r/{slug}/claim/{item_id}", data=data)


def _chips(db=None):
    return (db or _db()).execute("SELECT * FROM claims WHERE kind='chip' ORDER BY id").fetchall()


def _edit(client, item_id, **over):
    tok = get_csrf(client.get(f"/registry/items/{item_id}/edit").get_data(as_text=True))
    data = dict(csrf_token=tok, name="Fridge", price_nis="4000", qty_wanted="1", url="https://example.com/fridge")
    data.update(over)
    return client.post(f"/registry/items/{item_id}/edit", data=data, follow_redirects=True)


# ------------------------------------------------------------------ the couple turns it on
def test_cannot_enable_without_a_pay_link_or_with_qty_two(client):
    slug, item_id = _setup(client, chip=False, pay=False)
    page = client.get(f"/registry/items/{item_id}/edit").get_data(as_text=True)
    box = re.search(r'<input type="checkbox" name="chip_in"[^>]*>', page).group(0)
    assert "disabled" in box and "Add a payment link" in page
    r = _edit(client, item_id, chip_in="1")
    assert "needs a working payment link" in r.get_data(as_text=True)
    assert _db().execute("SELECT chip_in FROM registry_items").fetchone()[0] == 0
    # with a link, a quantity of 2 is still refused
    db = _db()
    db.execute("UPDATE registries SET paypal_url='https://paypal.me/dinayossi'")
    db.commit()
    assert "needs a working payment link" in _edit(client, item_id, chip_in="1", qty_wanted="2").get_data(as_text=True)
    assert _db().execute("SELECT chip_in FROM registry_items").fetchone()[0] == 0
    page = client.get(f"/registry/items/{item_id}/edit").get_data(as_text=True)
    assert "disabled" not in re.search(r'<input type="checkbox" name="chip_in"[^>]*>', page).group(0)
    r = _edit(client, item_id, chip_in="1")
    assert "needs a working payment link" not in r.get_data(as_text=True)
    assert _db().execute("SELECT chip_in FROM registry_items").fetchone()[0] == 1


def test_price_needed_to_enable(client):
    slug, item_id = _setup(client, chip=False, price="0")
    page = client.get(f"/registry/items/{item_id}/edit").get_data(as_text=True)
    assert "disabled" in re.search(r'<input type="checkbox" name="chip_in"[^>]*>', page).group(0)
    assert "Give the gift a price" in page
    _edit(client, item_id, chip_in="1", price_nis="0")
    assert _db().execute("SELECT chip_in FROM registry_items").fetchone()[0] == 0


# ------------------------------------------------------------------ a guest chips in
def test_chip_creates_a_chip_claim_and_goes_to_the_private_page(client, app_module):
    slug, item_id = _setup(client)
    guest, r = _chip(app_module, slug, item_id, amount=180)
    assert r.status_code == 302 and "/g/" in r.headers["Location"]
    (c,) = _chips()
    assert (c["kind"], c["qty"], c["amount_minor"], c["currency"], c["status"]) == ("chip", 0, 18000, "ILS", "reserved")
    assert c["expires_at"] and c["item_id"] == item_id
    page = guest.get(r.headers["Location"]).get_data(as_text=True)
    assert "Your ₪180 toward Fridge" in page and "paypal.me/dinayossi" in page
    assert 'class="gift-steps"' not in page and "Order it" not in page  # never store-order steps
    assert "I&#39;ve bought/sent it" in page
    mail = _db().execute("SELECT subject FROM mail_outbox WHERE to_addr='couple@example.com'").fetchone()
    assert mail["subject"] == "Cousin Dov plans to chip in ₪180 toward Fridge"


def test_preset_radio_is_used_unless_the_custom_field_is_filled(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, preset=100, name="A")
    _chip(app_module, slug, item_id, preset=100, amount=250, name="B")
    _chip(app_module, slug, item_id, preset="rest", name="C")
    assert [c["amount_minor"] for c in _chips()] == [10000, 25000, 365000]


def test_progress_shows_on_the_public_page_in_both_languages(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=1000, name="A")
    _chip(app_module, slug, item_id, amount=240, name="B")
    en = app_module.app.test_client().get(f"/r/{slug}?lang=en").get_data(as_text=True)
    assert "₪1,240 of ₪4,000 given · 2 guests" in en and 'class="chip-fill" style="width: 31%"' in en
    assert "Chip in" in en and "₪2,760 still needed" in en
    assert "₪100</span>" in en and "The rest (₪2,760)" in en and 'name="chip_amount"' in en
    he = app_module.app.test_client().get(f"/r/{slug}?lang=he").get_data(as_text=True)
    assert "₪1,240 מתוך ₪4,000 נאספו · שני אורחים" in he and "להשתתף במתנה" in he
    # the guest's own page, in Hebrew
    guest, r = _chip(app_module, slug, item_id, amount=50, name="C")
    assert "ההשתתפות שלכם: ₪50 עבור Fridge" in guest.get(r.headers["Location"] + "?lang=he").get_data(as_text=True)


def test_amount_below_minimum_or_above_remaining_is_refused(client, app_module):
    slug, item_id = _setup(client)
    for bad in ("5", "0", "-3", "abc", "12.5", ""):
        guest, r = _chip(app_module, slug, item_id, amount=bad)
        assert r.status_code == 302 and "/g/" not in r.headers["Location"], bad
    assert _chips() == []
    guest, r = _chip(app_module, slug, item_id, amount=4001)
    page = guest.get(r.headers["Location"]).get_data(as_text=True)
    assert "Only ₪4,000 is still needed" in page and "#item-" in r.headers["Location"]
    assert _chips() == []
    # the minimum is whatever is left when that is less than ₪20
    _chip(app_module, slug, item_id, amount=3990, name="A")
    assert len(_chips()) == 1
    _, r = _chip(app_module, slug, item_id, amount=5, name="B")  # below ₪10 left -> refused, 10 is the minimum
    assert "/g/" not in r.headers["Location"]
    _, r = _chip(app_module, slug, item_id, amount=10, name="C")
    assert "/g/" in r.headers["Location"]


def test_two_chips_fill_the_goal_then_a_third_is_refused(client, app_module):
    slug, item_id = _setup(client, price="400")
    _chip(app_module, slug, item_id, amount=150, name="A")
    g, r = _chip(app_module, slug, item_id, amount=250, name="B")
    assert "/g/" in r.headers["Location"]
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert "stamp stamp-reserved" in page and 'data-available="0"' in page
    assert "Chip in" not in page.split('id="gifts"')[1].split("</article>")[0]
    _, r = _chip(app_module, slug, item_id, amount=20, name="C")
    assert "/g/" not in r.headers["Location"] and len(_chips()) == 2
    # the registry counts the fully funded gift as taken
    with app_module.app.test_request_context("/"):
        bd = app_module.item_claim_breakdown(_db().execute("SELECT id FROM registries").fetchone()[0])
    assert bd[item_id]["committed"] == 1 and bd[item_id]["chip_minor"] == 40000 and bd[item_id]["chip_count"] == 2


def test_partly_funded_item_counts_as_open_everywhere(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=3000, name="A")
    reg_id = _db().execute("SELECT id FROM registries").fetchone()[0]
    with app_module.app.test_request_context("/"):
        bd = app_module.item_claim_breakdown(reg_id)
        st = app_module.gift_status(_db().execute("SELECT * FROM registry_items").fetchone(), bd)
    assert bd[item_id]["committed"] == 0
    assert st["state"] == "partial" and st["left"] == 1
    assert st["chip"] == dict(funded_minor=300000, goal_minor=400000, remaining_minor=100000, pct=75, count=1)
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "chipped in ₪3,000 toward Fridge" in dash


def test_a_whole_item_claim_is_refused_while_chips_are_active(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=100)
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    for give in ("buy", "cash"):
        r = guest.post(f"/r/{slug}/claim/{item_id}", data=dict(
            csrf_token=get_csrf(page), form_key=f"k-{give}", guest_name="Aunt", give=give))
        assert "/g/" not in r.headers["Location"]
    assert _db().execute("SELECT COUNT(*) FROM claims WHERE kind != 'chip'").fetchone()[0] == 0
    assert "chipping in" in guest.get(f"/r/{slug}").get_data(as_text=True)


def test_chip_refused_when_the_item_is_already_wholly_claimed(client, app_module):
    slug, item_id = _setup(client)
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    r = guest.post(f"/r/{slug}/claim/{item_id}", data=dict(
        csrf_token=get_csrf(page), form_key="whole", guest_name="Aunt", give="buy"))
    assert "/g/" in r.headers["Location"]
    _, r = _chip(app_module, slug, item_id, amount=100)
    assert "/g/" not in r.headers["Location"] and _chips() == []


def test_chip_not_offered_on_an_item_without_chip_in(client, app_module):
    slug, item_id = _setup(client, chip=False)
    _, r = _chip(app_module, slug, item_id, amount=100)
    assert "/g/" not in r.headers["Location"] and _chips() == []
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert "chip-track" not in page and "Gift this" in page


def test_expired_reserved_chip_frees_its_amount_and_cancel_too(client, app_module):
    slug, item_id = _setup(client, price="400")
    _chip(app_module, slug, item_id, amount=400, name="A")
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert 'data-available="0"' in page
    db = _db()
    db.execute("UPDATE claims SET expires_at='2000-01-01 00:00:00'")
    db.commit()
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert 'data-available="1"' in page and "₪0 of" not in page and "to go · open for guests" in page
    # cancelled by the guest
    guest, r = _chip(app_module, slug, item_id, amount=200, name="B")
    token_url = r.headers["Location"]
    gp = guest.get(token_url).get_data(as_text=True)
    guest.post(token_url + "/cancel", data=dict(csrf_token=get_csrf(gp)))
    assert "to go · open for guests" in app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)


def test_couple_sees_chips_as_chips_not_x0(client, app_module):
    slug, item_id = _setup(client)
    guest, r = _chip(app_module, slug, item_id, amount=180, message="Mazel tov!")
    dash = client.get("/dashboard").get_data(as_text=True)
    assert "chipped in ₪180 toward Fridge" in dash and "×0" not in dash and "× 0" not in dash
    csv = client.get("/dashboard/claims.csv").get_data(as_text=True)
    row = [ln for ln in csv.splitlines() if "chip" in ln][0].split(",")
    assert row[3] == "Fridge" and row[4] == "" and row[5] == "chip" and row[7] == "18000"
    # confirm it -> thanks page + drafted note
    cid = _db().execute("SELECT id FROM claims").fetchone()[0]
    tok = get_csrf(dash)
    client.post(f"/claim/{cid}/confirm", data=dict(csrf_token=tok))
    thanks = client.get("/dashboard/thanks").get_data(as_text=True)
    assert "₪180 toward Fridge" in thanks and "×0" not in thanks and "× 0" not in thanks
    assert "chipping in toward the fridge" in thanks
    assert "Mazel tov!" in client.get("/dashboard/keepsake").get_data(as_text=True)
    assert "toward Fridge" in client.get("/dashboard/keepsake").get_data(as_text=True)
    he = client.get("/dashboard/thanks?lang=he").get_data(as_text=True)
    assert "₪180 עבור Fridge" in he


def test_item_cannot_be_unchipped_or_changed_below_whats_given(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=1000)
    page = client.get(f"/registry/items/{item_id}/edit").get_data(as_text=True)
    box = re.search(r'<input type="checkbox" name="chip_in"[^>]*>', page).group(0)
    assert "disabled" in box and "checked" in box and "already chipped in" in page
    _edit(client, item_id)  # a disabled box posts nothing: still on
    assert _db().execute("SELECT chip_in FROM registry_items").fetchone()[0] == 1
    assert "can&#39;t go below" in _edit(client, item_id, price_nis="900").get_data(as_text=True)
    assert _db().execute("SELECT price_nis FROM registry_items").fetchone()[0] == 4000
    assert "quantity stays at 1" in _edit(client, item_id, qty_wanted="2").get_data(as_text=True)
    assert _db().execute("SELECT qty_wanted FROM registry_items").fetchone()[0] == 1
    # removing the item archives it (it has claims) instead of deleting it
    tok = get_csrf(client.get("/registry/items").get_data(as_text=True))
    client.post(f"/registry/items/{item_id}/update", data=dict(csrf_token=tok, delete="1"))
    assert _db().execute("SELECT archived FROM registry_items").fetchone()[0] == 1
    assert len(_chips()) == 1


def test_closed_registry_refuses_chips(client, app_module):
    slug, item_id = _setup(client)
    db = _db()
    db.execute("UPDATE registries SET closed_at='2026-11-01 00:00:00'")
    db.commit()
    _, r = _chip(app_module, slug, item_id, amount=100)
    assert "/g/" not in r.headers["Location"] and _chips() == []


def test_duplicate_form_key_records_one_chip(client, app_module):
    slug, item_id = _setup(client)
    guest = app_module.app.test_client()
    page = guest.get(f"/r/{slug}").get_data(as_text=True)
    key = get_form_key(page)
    _, a = _chip(app_module, slug, item_id, amount=100, guest=guest, form_key=key)
    _, b = _chip(app_module, slug, item_id, amount=100, guest=guest, form_key=key)
    assert a.headers["Location"] == b.headers["Location"] and "/g/" in a.headers["Location"]
    assert len(_chips()) == 1


def test_honeypot_blocks_bots(client, app_module):
    slug, item_id = _setup(client)
    _, r = _chip(app_module, slug, item_id, amount=100, website="http://spam")
    assert _chips() == []


def test_reported_and_received_chips_show_the_right_state(client, app_module):
    slug, item_id = _setup(client, price="400")
    g1, r1 = _chip(app_module, slug, item_id, amount=200, name="A")
    _, r2 = _chip(app_module, slug, item_id, amount=200, name="B")
    reg_id = _db().execute("SELECT id FROM registries").fetchone()[0]

    def state():
        with app_module.app.test_request_context("/"):
            bd = app_module.item_claim_breakdown(reg_id)
            return app_module.gift_status(_db().execute("SELECT * FROM registry_items").fetchone(), bd)["state"]
    assert state() == "reserved"
    db = _db()
    db.execute("UPDATE claims SET status='reported' WHERE guest_name='A'")
    db.commit()
    assert state() == "reserved"  # B is still only reserved
    db.execute("UPDATE claims SET status='reported'")
    db.commit()
    assert state() == "reported"
    db.execute("UPDATE claims SET status='received'")
    db.commit()
    assert state() == "received"


def test_list_check_suggests_chip_in_for_a_big_open_gift(client):
    slug, item_id = _setup(client, price="2000", chip=False)
    html = client.get("/registry/check").get_data(as_text=True)
    assert "Let guests chip in toward the Fridge" in html and f"/registry/items/{item_id}/edit" in html
    db = _db()
    db.execute("UPDATE registry_items SET chip_in=1")
    db.commit()
    assert "Let guests chip in toward" not in client.get("/registry/check").get_data(as_text=True)


def test_items_page_shows_what_was_chipped_in(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=500)
    assert "₪500 of ₪4,000 chipped in" in client.get("/registry/items").get_data(as_text=True)


def test_sample_page_shows_a_partly_funded_chip_item(client):
    en = client.get("/sample").get_data(as_text=True)
    assert 'class="chip-track"' in en and "given · 4 guests" in en and "Chip in" in en
    assert "<dialog" not in en
    he = client.get("/sample?lang=he").get_data(as_text=True)
    assert 'class="chip-track"' in he and "נאספו · 4 אורחים" in he
    assert client.get("/").status_code == 200  # the homepage preview still renders


def test_migration_adds_chip_in_column(app_module):
    cols = {r[1] for r in _db().execute("PRAGMA table_info(registry_items)")}
    assert "chip_in" in cols


def test_whole_gift_from_the_store_while_nobody_has_chipped_in(client, app_module):
    slug, item_id = _setup(client)
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert 'value="store"' in page and "The whole gift" in page
    _, r = _chip(app_module, slug, item_id, preset="store")
    assert r.status_code == 302 and "/g/" in r.headers["Location"]
    row = _db().execute("SELECT kind, qty FROM claims").fetchone()
    assert (row["kind"], row["qty"]) == ("item", 1)


def test_store_option_goes_once_someone_chipped_in(client, app_module):
    slug, item_id = _setup(client)
    _chip(app_module, slug, item_id, amount=180)
    page = app_module.app.test_client().get(f"/r/{slug}").get_data(as_text=True)
    assert 'value="store"' not in page and "The rest" in page
    _chip(app_module, slug, item_id, preset="store", name="Aunt Miri")
    assert _db().execute("SELECT COUNT(*) FROM claims WHERE kind='item'").fetchone()[0] == 0


def test_guest_can_report_a_chip_and_the_couple_is_told(client, app_module):
    slug, item_id = _setup(client)
    guest, r = _chip(app_module, slug, item_id, amount=180)
    page = guest.get(r.headers["Location"]).get_data(as_text=True)
    token = r.headers["Location"].rsplit("/", 1)[-1]
    r2 = guest.post(f"/g/{token}/report", data=dict(csrf_token=get_csrf(page)))
    assert r2.status_code == 302
    assert _chips()[0]["status"] == "reported"
    bodies = " ".join(m["body"] for m in _db().execute("SELECT body FROM mail_outbox"))
    assert "toward Fridge" in bodies
