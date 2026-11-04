"""Hebrew calendar for the simcha date: Gregorian <-> Hebrew conversion, Hebrew-numeral
formatting ("כ״ד בכסלו תשפ״ז" / "24 Kislev 5787") and the days a wedding date is worth a
second look (Shabbos, Yom Tov, Chol Hamoed, Tisha B'Av). Pure Python, no dependency.

The arithmetic is the standard fixed-day calendar (Dershowitz & Reingold, "Calendrical
Calculations"): a Python `date.toordinal()` is the same day count they call R.D. Months
are numbered from Nisan as the Torah counts them: 1 Nisan … 7 Tishrei … 12 Adar (Adar I
in a leap year), 13 Adar II. The Hebrew date shown is the daytime date — an evening
chuppah is already the next Hebrew day, but invitations name the day itself."""
from datetime import date

EPOCH = -1373427  # R.D. of 1 Tishrei, year 1

NISAN, TISHREI, ADAR, ADAR_II = 1, 7, 12, 13

_NAMES_EN = {1: "Nissan", 2: "Iyar", 3: "Sivan", 4: "Tammuz", 5: "Av", 6: "Elul",
             7: "Tishrei", 8: "Cheshvan", 9: "Kislev", 10: "Teves", 11: "Shevat", 12: "Adar"}
_NAMES_HE = {1: "ניסן", 2: "אייר", 3: "סיוון", 4: "תמוז", 5: "אב", 6: "אלול",
             7: "תשרי", 8: "חשוון", 9: "כסלו", 10: "טבת", 11: "שבט", 12: "אדר"}

# Month choices for a form, in the order of the year (Tishrei first). "adar" is Adar in an
# ordinary year (and Adar II in a leap year, the one that holds Purim); "adar1"/"adar2"
# name the leap-year months and fall back to plain Adar in an ordinary year.
MONTH_CHOICES = ("7", "8", "9", "10", "11", "adar", "adar1", "adar2", "1", "2", "3", "4", "5", "6")


def is_leap(year):
    return (7 * year + 1) % 19 < 7


def _last_month(year):
    return ADAR_II if is_leap(year) else ADAR


def _elapsed_days(year):
    months = (235 * year - 234) // 19
    parts = 12084 + 13753 * months
    day = months * 29 + parts // 25920
    return day + 1 if (3 * (day + 1)) % 7 < 3 else day


def _correction(year):
    ny0, ny1, ny2 = _elapsed_days(year - 1), _elapsed_days(year), _elapsed_days(year + 1)
    if ny2 - ny1 == 356:
        return 2
    if ny1 - ny0 == 382:
        return 1
    return 0


def _new_year(year):
    return EPOCH + _elapsed_days(year) + _correction(year)


def year_days(year):
    return _new_year(year + 1) - _new_year(year)


def month_days(month, year):
    """29 or 30 days in this Hebrew month of this year."""
    length = year_days(year)
    if (month in (2, 4, 6, 10, ADAR_II) or (month == ADAR and not is_leap(year))
            or (month == 8 and length % 10 != 5) or (month == 9 and length % 10 == 3)):
        return 29
    return 30


def _fixed(year, month, day):
    rd = _new_year(year) + day - 1
    if month < TISHREI:
        rd += sum(month_days(m, year) for m in range(TISHREI, _last_month(year) + 1))
        rd += sum(month_days(m, year) for m in range(NISAN, month))
    else:
        rd += sum(month_days(m, year) for m in range(TISHREI, month))
    return rd


def to_hebrew(d):
    """(year, month, day) of a Gregorian `date`."""
    rd = d.toordinal()
    year = (rd - EPOCH) * 98496 // 35975351  # never more than one year short
    while _new_year(year + 1) <= rd:
        year += 1
    month = TISHREI if rd < _fixed(year, NISAN, 1) else NISAN
    while rd > _fixed(year, month, month_days(month, year)):
        month += 1
    return year, month, rd - _fixed(year, month, 1) + 1


def from_hebrew(year, month, day):
    """Gregorian `date` of a Hebrew date; ValueError if that day doesn't exist that year."""
    if not (1 <= month <= _last_month(year)) or not (1 <= day <= month_days(month, year)):
        raise ValueError("no such Hebrew date")
    return date.fromordinal(_fixed(year, month, day))


def resolve_month(choice, year):
    """A MONTH_CHOICES value -> this year's month number (None if unknown)."""
    if choice == "adar":
        return ADAR_II if is_leap(year) else ADAR
    if choice == "adar1":
        return ADAR
    if choice == "adar2":
        return ADAR_II if is_leap(year) else ADAR
    try:
        m = int(choice)
    except (TypeError, ValueError):
        return None
    return m if 1 <= m <= 11 else None


def month_choice(year, month):
    """The MONTH_CHOICES value that shows this month (inverse of resolve_month)."""
    if month == ADAR:
        return "adar1" if is_leap(year) else "adar"
    if month == ADAR_II:
        return "adar2"
    return str(month)


def month_name(year, month, lang="en"):
    if month in (ADAR, ADAR_II) and is_leap(year):
        return ("אדר א׳" if month == ADAR else "אדר ב׳") if lang == "he" else (
            "Adar I" if month == ADAR else "Adar II")
    return (_NAMES_HE if lang == "he" else _NAMES_EN)[min(month, ADAR)]


def choice_label(choice, lang="en"):
    """Form label for a MONTH_CHOICES value."""
    if choice in ("adar", "adar1", "adar2"):
        return {"adar": ("Adar", "אדר"), "adar1": ("Adar I", "אדר א׳"),
                "adar2": ("Adar II", "אדר ב׳")}[choice][lang == "he"]
    return (_NAMES_HE if lang == "he" else _NAMES_EN)[int(choice)]


_ONES = "אבגדהוזחט"
_TENS = "יכלמנסעפצ"
_HUNDREDS = "קרשת"


def numeral(n):
    """Hebrew numeral with geresh/gershayim: 5 -> ה׳, 15 -> ט״ו, 787 -> תשפ״ז."""
    letters = ""
    hundreds, n = divmod(n % 1000, 100)
    while hundreds >= 4:
        letters += "ת"
        hundreds -= 4
    if hundreds:
        letters += _HUNDREDS[hundreds - 1]
    if n in (15, 16):  # never spell a Name: 15 = 9+6, 16 = 9+7
        letters += "ט" + ("ו" if n == 15 else "ז")
    else:
        tens, ones = divmod(n, 10)
        if tens:
            letters += _TENS[tens - 1]
        if ones:
            letters += _ONES[ones - 1]
    if len(letters) == 1:
        return letters + "׳"
    return letters[:-1] + "״" + letters[-1]


def format_hebrew(d, lang="en"):
    """"24 Kislev 5787" / "כ״ד בכסלו תשפ״ז" for a Gregorian date (or ISO string);
    '' when it isn't a date."""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d[:10])
        except ValueError:
            return ""
    if not isinstance(d, date):
        return ""
    year, month, day = to_hebrew(d)
    if lang == "he":
        return f"{numeral(day)} ב{month_name(year, month, 'he')} {numeral(year)}"
    return f"{day} {month_name(year, month)} {year}"


# Yom Tov in Israel; outside Israel each festival also has a second day (for Sukkos and
# Pesach that day is Chol Hamoed in Israel, which day_note already flags)
_YOM_TOV = {(7, 1): "rosh_hashanah", (7, 2): "rosh_hashanah", (7, 10): "yom_kippur",
            (7, 15): "sukkos", (7, 22): "shemini_atzeres", (1, 15): "pesach",
            (1, 21): "pesach_7", (3, 6): "shavuos"}
_YOM_TOV_SHENI = {(7, 23): "simchas_torah", (1, 22): "pesach_8", (3, 7): "shavuos_2"}


def day_note(d):
    """Why a wedding on this day is worth a second look, as (kind, holiday) — kind is
    'shabbos', 'yomtov', 'yomtov_sheni' (outside Israel only), 'chol_hamoed' or
    'tisha_bav' — or None. Shabbos is checked last so a Yom Tov on Shabbos names the
    Yom Tov."""
    year, month, day = to_hebrew(d)
    if (month, day) in _YOM_TOV:
        return "yomtov", _YOM_TOV[(month, day)]
    if (month == TISHREI and 16 <= day <= 21) or (month == NISAN and 16 <= day <= 20):
        return "chol_hamoed", "sukkos" if month == TISHREI else "pesach"
    if (month, day) in _YOM_TOV_SHENI:
        return "yomtov_sheni", _YOM_TOV_SHENI[(month, day)]
    # 9 Av; pushed to the 10th when the 9th is Shabbos
    if month == 5 and (day == 9 and d.weekday() != 5
                       or day == 10 and date.fromordinal(d.toordinal() - 1).weekday() == 5):
        return "tisha_bav", None
    if d.weekday() == 5:
        return "shabbos", None
    return None
