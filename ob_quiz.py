# -*- coding: utf-8 -*-
"""The "Build my list" quiz: six answers -> a draft list of ACTIVE catalog items.

Pure logic, no Flask: `quiz_pick(db, answers)` returns catalog rows; `quiz_build` also returns
per-item quantities and the "why these" note keys. Every item comes from the live catalog (matched
by seed_key / option_group / name), never invented, so a catalog edit can only make the list
shorter, not break it. Rules are documented in PROJECT_KNOWLEDGE.md ("Build my list").
"""
import re

STARTER_ORDER = ("first_week", "kitchen", "shabbos", "bedbath", "furniture", "appliances")

QUESTIONS = (  # (answer key, allowed values; the first is the default)
    ("start", ("empty", "partly", "furnished")),
    ("bed", ("double", "singles", "unsure")),
    ("host", ("us", "some", "most")),
    ("kitchen", ("separate", "one")),
    ("quality", ("simple", "mid", "nicer")),
    ("yomtov", ("no", "yes", "unsure")),
)
DEFAULTS = {k: vals[0] for k, vals in QUESTIONS}
DEFAULTS["quality"] = "mid"
ANSWER_KEYS = tuple(k for k, _ in QUESTIONS)

START_GROUPS = {
    "empty": ("first_week", "kitchen", "shabbos", "bedbath", "furniture", "appliances"),
    "partly": ("first_week", "kitchen", "shabbos", "bedbath", "appliances"),
    "furnished": ("first_week", "shabbos", "bedbath"),
}
# partly furnished: the big appliances that stay with the flat (matched on the English name)
BIG_APPLIANCE = re.compile(r"\b(fridge|refrigerator|washing machine|dryer|dishwasher|air condition\w*)\b|^oven\b", re.I)
QUALITY_MATTERS = {"pots-set", "chef-knife", "pillow", "duvet", "sheet-set", "towels", "kettle", "coffee-machine",
                   "mattress", "mattress-single"}
BED_SIZE_GROUPS = {"sheet-set", "mattress-protector", "duvet", "bed-frame", "mattress"}
# two single beds: the double frame / mattress in the furniture starter group become two singles
SINGLES_SWAP = {"bed-frame": "bed-frame-single", "mattress": "mattress-single"}
PER_BED_GROUPS = {"duvet", "mattress-protector", "sheet-set", "bed-frame-single", "mattress-single"}
ALREADY_PAIR = re.compile(r"[x×]\s?2\b|protectors", re.I)

# starter items that duplicate another starter item (bundle vs parts, two versions of one thing)
SKIP_ALWAYS = ("duvet-pillows-set", "bath-mat-non-slip", "shower-shelf")
GUEST_LINEN = "guest-linen-set"
PLATTA = ("shabbos-hot-plate-platta", "shabbos-hot-plate-large-family-size")  # small, large
CUTTING_SET = "cutting-boards-milchig-fleishig-set"
CUTTING_SINGLES = ("cutting-board-fleishig-red", "cutting-board-milchig-blue")
HOST_SOME_ADD = ("folding-table-6-chairs-shabbos-guests",)
HOST_MOST_ADD = ("serving-platters-bowls", "glass-serving-bowls")
YOMTOV_ADD = ("seder-plate", "matzah-cover-afikomen-bag", "rosh-hashanah-honey-dish",
              "kiddush-cups-for-guests-6", "menorah-chanukah")
MAX_NOTES = 4
CAT_ORDER = ("kitchen", "appliances", "dining", "bedding", "judaica", "home")


def normalise(args):
    """Whitelist every answer; anything missing or unknown falls back to its default."""
    out = {}
    for key, vals in QUESTIONS:
        v = (args.get(key) or "") if args is not None else ""
        out[key] = v if v in vals else DEFAULTS[key]
    return out


def _price(r):
    return r["price_nis"] or 0


def _low(r):
    return ((r["name"] or "") + " " + (r["seed_key"] or "")).lower()


def _size_pref(r, bed):
    low = _low(r)
    if bed == "singles":
        return 0 if "single" in low else (1 if "double" not in low else 2)
    return 0 if "double" in low else (1 if "single" not in low else 2)


def _choose(members, quality, group, bed):
    """ONE member of an option group for the quality answer (see module docstring)."""
    by_price = sorted(members, key=lambda r: (_price(r), r["id"]))
    tiers = {}
    for r in members:
        tiers.setdefault(r["tier"] or "standard", []).append(r)

    def best(tier):
        lst = tiers.get(tier)
        return min(lst, key=lambda r: (_size_pref(r, bed), _price(r), r["id"])) if lst else None

    middle = by_price[(len(by_price) - 1) // 2]
    if quality == "simple":
        return best("basic") or by_price[0]
    if quality == "nicer" and group in QUALITY_MATTERS:
        return best("premium") or best("standard") or by_price[0]
    return best("standard") or middle


def _kind(r):
    low = _low(r)
    f, m = "fleishig" in low, "milchig" in low
    return "dual" if f and m else ("f" if f else ("m" if m else None))


def quiz_build(db, answers):
    """-> dict(rows=[catalog rows, grouped by category], qty={id: n}, notes=[note keys])."""
    a = normalise(answers)
    active = db.execute("SELECT * FROM catalog_items WHERE active=1 ORDER BY sort, id").fetchall()
    by_key = {r["seed_key"]: r for r in active if r["seed_key"]}
    members = {}
    for r in active:
        if r["option_group"]:
            members.setdefault(r["option_group"], []).append(r)

    rows, seen = [], set()

    def add(r):
        if r is not None and r["id"] not in seen:
            seen.add(r["id"])
            rows.append(r)

    def drop(pred):
        nonlocal rows
        gone = [r for r in rows if pred(r)]
        rows = [r for r in rows if not pred(r)]
        for r in gone:
            seen.discard(r["id"])
        return gone

    starters = {g: [r for r in active if r["starter_group"] == g] for g in STARTER_ORDER}
    for g in START_GROUPS[a["start"]]:
        for r in starters[g]:
            add(r)

    # 1. duplicates inside the starter groups
    drop(lambda r: r["seed_key"] in SKIP_ALWAYS)
    if a["host"] == "us":
        drop(lambda r: r["seed_key"] == GUEST_LINEN)
    if a["start"] == "partly":
        drop(lambda r: BIG_APPLIANCE.search(r["name"] or "") is not None)

    # 2. beds: no bed size, no bed linen
    notes_beds_unsure = False
    if a["bed"] == "unsure":
        notes_beds_unsure = bool(drop(lambda r: r["option_group"] in BED_SIZE_GROUPS
                                      or re.search(r"\bsheet", r["name"] or "", re.I)))
    elif a["bed"] == "singles":  # swap the 160x200 frame / mattress for 90x200 singles (qty 2 below)
        for dbl, sgl in SINGLES_SWAP.items():
            if drop(lambda r, g=dbl: r["option_group"] == g) and members.get(sgl):
                add(members[sgl][0])  # step 5 picks the tier

    # 3. hosting and Yom Tov additions (option groups below pick the tier)
    if a["host"] in ("some", "most"):
        for k in HOST_SOME_ADD:
            add(by_key.get(k))
    if a["host"] == "most":
        for k in HOST_MOST_ADD:
            add(by_key.get(k))
    if a["yomtov"] == "yes":
        for k in YOMTOV_ADD:
            add(by_key.get(k))

    # 4. platta: the small one for just-us, the large one when hosting
    small, large = by_key.get(PLATTA[0]), by_key.get(PLATTA[1])
    if small is not None or large is not None:
        want = (small or large) if a["host"] == "us" else (large or small)
        had = any(r["seed_key"] in PLATTA for r in rows)
        drop(lambda r: r["seed_key"] in PLATTA)
        if had or a["host"] != "us":
            add(want)

    # 5. one member per option group, by the quality answer
    for grp in list(dict.fromkeys(r["option_group"] for r in rows if r["option_group"])):
        mem = members.get(grp) or []
        if not mem:
            continue
        pool = mem
        if grp == "shabbos-urn" and a["host"] != "us":  # the larger urn when hosting
            sized = [r for r in mem if re.search(r"\b(\d+)\s*cup", r["name"] or "", re.I)]
            if sized:
                pool = [max(sized, key=lambda r: int(re.search(r"(\d+)\s*cup", r["name"], re.I).group(1)))]
        pick_ = _choose(pool, a["quality"], grp, a["bed"])
        idx = next(i for i, r in enumerate(rows) if r["option_group"] == grp)
        drop(lambda r: r["option_group"] == grp)
        rows.insert(min(idx, len(rows)), pick_)
        seen.add(pick_["id"])

    # 6. one kitchen or two
    second_set_dropped = False
    cut_set = by_key.get(CUTTING_SET)
    if a["kitchen"] == "separate":
        if cut_set is not None and any(r["id"] == cut_set["id"] for r in rows):
            drop(lambda r: r["seed_key"] in CUTTING_SINGLES)
    else:
        if cut_set is not None and any(r["id"] == cut_set["id"] for r in rows):
            drop(lambda r: r["id"] == cut_set["id"])
            add(by_key.get(CUTTING_SINGLES[1]))
            second_set_dropped = True
        gone = drop(lambda r: _kind(r) == "f")
        second_set_dropped = second_set_dropped or bool(gone)

    # 7. order by room, quantities
    order = {c: i for i, c in enumerate(CAT_ORDER)}
    rows.sort(key=lambda r: (order.get(r["category"], len(order)), r["sort"] or 0, r["id"]))
    qty, bed_doubled = {}, False
    for r in rows:
        n = 1
        low = (r["name"] or "")
        if not ALREADY_PAIR.search(low):
            if r["option_group"] == "pillow":
                n = 2
            elif a["bed"] == "singles" and r["option_group"] in PER_BED_GROUPS:
                n, bed_doubled = 2, True
        qty[r["id"]] = n

    notes = ["quiz_why_start_" + a["start"]]
    if notes_beds_unsure:
        notes.append("quiz_why_bed_unsure")
    elif bed_doubled:
        notes.append("quiz_why_bed_singles")
    if second_set_dropped:
        notes.append("quiz_why_kitchen_one")
    if a["host"] != "us":
        notes.append("quiz_why_host_" + a["host"])
    if a["yomtov"] == "yes":
        notes.append("quiz_why_yt_yes")
    elif a["yomtov"] == "unsure":
        notes.append("quiz_why_yt_unsure")
    notes.append("quiz_why_quality_" + a["quality"])
    return dict(rows=rows, qty=qty, notes=notes[:MAX_NOTES], answers=a)


def quiz_pick(db, answers):
    """The draft list's active catalog rows for `answers` (a dict of the six answers)."""
    return quiz_build(db, answers)["rows"]
