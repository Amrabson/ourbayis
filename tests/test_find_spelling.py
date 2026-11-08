# -*- coding: utf-8 -*-
"""Find a registry by a name spelled another way (2026-11-08): Kohen finds Cohen, levy finds Levi."""
import os
import sqlite3

from conftest import create_registry, signup


def _public(app_module, *couples):
    for i, couple in enumerate(couples):
        c = app_module.app.test_client()
        signup(c, email=f"u{i}@example.com")
        create_registry(c, couple=couple)
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.execute("UPDATE registries SET visibility='public'")
    db.commit()


def test_name_sound_folds_the_usual_spellings(app_module):
    same = [("Cohen", "Kohen"), ("Cohen", "Kahn"), ("Levi", "Levy"), ("Chaya", "Haya"), ("Dovid", "David"),
            ("Yossi", "Yosi"), ("Sarah", "Sara"), ("Mendel", "Mendl"), ("Katz", "Kats")]
    for a, b in same:
        assert app_module.name_sound(a) == app_module.name_sound(b), (a, b)
    assert app_module.name_sound("Moshe") != app_module.name_sound("Mushka")


def test_find_falls_back_to_names_that_sound_the_same(client, app_module):
    _public(app_module, "Sarah & Dovid Cohen", "Chaya Mushka & Mendel Gurary")
    exact = client.get("/find?q=Cohen&lang=en").get_data(as_text=True)
    assert "Sarah &amp; Dovid Cohen" in exact and "sound the same" not in exact
    close = client.get("/find?q=Kohen&lang=en").get_data(as_text=True)
    assert "Sarah &amp; Dovid Cohen" in close and "sound the same" in close
    assert "Sarah &amp; Dovid Cohen" in client.get("/find?q=David+Kohen&lang=en").get_data(as_text=True)
    nothing = client.get("/find?q=Moshe&lang=en").get_data(as_text=True)
    assert "Gurary" not in nothing and "No registries found" in nothing
    he = client.get("/find?q=Kohen&lang=he").get_data(as_text=True)
    assert "שנשמעים אותו דבר" in he


def test_unlisted_registries_never_come_up_by_sound(client, app_module):
    _public(app_module, "Sarah & Dovid Cohen")
    db = sqlite3.connect(os.environ["OB_DB_PATH"])
    db.execute("UPDATE registries SET visibility='unlisted'")
    db.commit()
    assert "Sarah &amp; Dovid Cohen" not in client.get("/find?q=Kohen&lang=en").get_data(as_text=True)
