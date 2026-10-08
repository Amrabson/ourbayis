"""Catalog search: forgiving word matching for the catalog and the couple's "add gifts" list.

Every word the person types must match somewhere (name, Hebrew name, brand, model line), but each
word may match in several spellings: plurals are folded ("sheets" -> "sheet", "knives" -> "knife",
"מגבות" -> "מגב"), and common alternative words/transliterations map to the catalog's own wording
("shabbat" -> "shabbos", "plata" -> "platta", "refrigerator" -> "fridge", "פלטה" -> "פלטת").
Pure SQL LIKE — no FTS table to keep in sync for ~120 rows.
"""
import re

# alternative word -> extra spellings to try (the catalog's own words). Keys are lowercase.
SYNONYMS = {
    "shabbat": ("shabbos",), "shabbas": ("shabbos",), "shabbes": ("shabbos",), "sabbath": ("shabbos",),
    "plata": ("platta", "hot plate"), "hotplate": ("hot plate", "platta"),
    "warming": ("hot plate", "platta"), "blech": ("hot plate", "platta"),
    "urn": ("meicham", "urn"), "mechem": ("meicham",), "hot water": ("urn", "meicham", "pump pot"),
    "refrigerator": ("fridge",), "frig": ("fridge",),
    "silverware": ("cutlery",), "flatware": ("cutlery",), "utensil": ("cutlery",), "fork": ("cutlery",),
    "spoon": ("cutlery", "spoon"),
    "dish": ("dinnerware", "dish"), "plates": ("dinnerware", "platter"), "china": ("porcelain", "dinnerware"),
    "becher": ("kiddush",), "goblet": ("kiddush",),
    "candle": ("candlestick", "candle"), "leichter": ("candlestick",),
    "washer": ("washing", "washer"), "laundry": ("washing", "laundry", "dryer"),
    "linen": ("linen", "sheet", "duvet"), "bedding": ("sheet", "duvet", "pillow", "blanket", "bedspread"),
    "comforter": ("duvet",), "quilt": ("duvet", "quilted"),
    "sofa": ("couch",), "settee": ("couch",), "carpet": ("rug",),
    "cholent": ("slow cooker", "cholent"), "crockpot": ("slow cooker",), "crock pot": ("slow cooker",),
    "airfryer": ("air fryer",), "nespresso": ("coffee",), "espresso": ("coffee",),
    "pan": ("pan", "pots"), "skillet": ("frying pan",), "pot": ("pots", "pot"),
    "glasses": ("glass",), "cups": ("cup", "glass"),
    "seforim": ("sefarim",), "sforim": ("sefarim",), "bookshelf": ("bookcase",), "books": ("bookcase", "sefarim"),
    "siddur": ("siddurim",), "chumash": ("chumashim",), "bencher": ("bentcher",), "bentscher": ("bentcher",),
    "etrog": ("esrog",), "hanukkah": ("chanukah", "menorah"), "chanukiah": ("menorah",),
    "hanukiah": ("menorah",), "netilat": ("netilas",), "washing cup": ("netilas",), "havdala": ("havdalah",),
    "mezuza": ("mezuzah",), "mezuzos": ("mezuzah",), "mezuzot": ("mezuzah",),
    "challa": ("challah",), "chala": ("challah",), "hallah": ("challah",),
    "squeegee": ("sponja",), "mop": ("sponja",), "sponga": ("sponja",),
    "heater": ("heater",), "radiator": ("heater",), "ac": ("fan",),
    # Hebrew: everyday words -> the wording used in name_he
    "פלטה": ("פלטת",), "פלאטה": ("פלטת",), "מיחם": ("מיחם",), "סכום": ("סכו״ם",), "סכו\"ם": ("סכו״ם",),
    "מקרר": ("מקרר",), "צלחות": ("כלי אוכל", "פורצלן"), "כלים": ("כלי אוכל", "כלים"),
    "מצעים": ("מצעים",), "שמיכה": ("שמיכ",), "כוס": ("כוס", "גביע"), "גביע": ("גביע",),
    "ספונג'ה": ("ספונג׳ה",), "ספונגה": ("ספונג׳ה",), "חנוכיה": ("חנוכייה",), "פמוטים": ("פמוט",),
    "שבת": ("שבת", "לשבת"), "ספרים": ("ספרי", "ספרייה"),
}

_HE = re.compile(r"[֐-׿]")
# names + brand take every spelling; the long model line only the word as typed, or a stem like
# "glass" would hit every "ceramic glass" / "tempered glass" description
SEARCH_FIELDS = ("name", "name_he", "brand")
LITERAL_FIELDS = ("model", "model_he")


def _singular(w):
    """English/Hebrew plural -> a shorter stem that still appears inside the singular."""
    out = []
    if _HE.search(w):
        if len(w) > 5 and w.endswith(("ות", "ים")):   # stems >= 4 letters: מגבות must not hit מגב (squeegee)
            out.append(w[:-2])
        if len(w) > 2 and w.endswith("ה"):
            out.append(w[:-1] + "ת")       # construct form: פלטה -> פלטת שבת
        return out
    if len(w) > 4 and w.endswith("ves"):
        out += [w[:-3] + "fe", w[:-3] + "f"]   # knives -> knife, shelves -> shelf
    if len(w) > 4 and w.endswith("ies"):
        out.append(w[:-3] + "y")
    if len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes")):
        out.append(w[:-2])
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        out.append(w[:-1])
    return out


def word_variants(word):
    w = word.lower()
    vs = [w] + list(SYNONYMS.get(w, ()))
    for s in _singular(w):
        vs += [s] + list(SYNONYMS.get(s, ()))
    seen, out = set(), []
    for v in vs:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _like(v):
    return "%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search_clause(q, fields=SEARCH_FIELDS, literal_fields=LITERAL_FIELDS):
    """(" AND (...) AND (...)", params) for a free-text query; ("", []) when there's nothing to match.
    Two-word synonyms ("hot water", "crock pot") are tried on the whole phrase first."""
    q = (q or "").strip().lower()
    words = [w for w in re.split(r"[\s,/]+", q) if w][:8]   # bounded SQL size
    if not words:
        return "", []
    phrase = " ".join(words)
    if len(words) > 1 and phrase in SYNONYMS:
        groups = [(phrase, word_variants(phrase))]
    else:
        long_enough = [w for w in words if len(w) > 1] or words
        groups = [(w, word_variants(w)) for w in long_enough]
    sql, params = "", []
    for typed, variants in groups:
        ors = []
        for v in variants:
            for f in fields:
                ors.append(f"{f} LIKE ? ESCAPE '\\'")
                params.append(_like(v))
        for f in literal_fields:
            ors.append(f"{f} LIKE ? ESCAPE '\\'")
            params.append(_like(typed))
        sql +=" AND (" + " OR ".join(ors) + ")"
    return sql, params
