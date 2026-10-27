"""Helpers for free-text, possibly incomplete dates.

Dates are stored as text so they can be incomplete. The date picker writes
"12.03.1923", "03.1923", "1923", optionally prefixed with "ca.", "before"
or "after"; older files may contain other free text, which is kept as is.
The year is extracted for sorting and for the lifespan shown on person cards.
"""

import calendar
import re

_QUALIFIERS = (
    ("c.", re.compile(r"^\s*(ca\.?|circa|c\.|abt\.?|about|approx\.?|~|um)\s*", re.I)),
    ("bef.", re.compile(r"^\s*(before|bef\.?|vor|<)\s*", re.I)),
    ("aft.", re.compile(r"^\s*(after|aft\.?|nach|>)\s*", re.I)),
)
_YEAR = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")


def parse_year(text):
    """Return (year or None, qualifier) where qualifier is '', 'c.', 'bef.' or 'aft.'."""
    text = (text or "").strip()
    if not text:
        return None, ""
    qualifier = ""
    for label, pattern in _QUALIFIERS:
        if pattern.match(text):
            qualifier = label
            break
    match = _YEAR.search(text)
    return (int(match.group(1)) if match else None), qualifier


def year_label(text):
    """Short year text for display, e.g. '1923', 'c. 1880', '?' (if text has no year)."""
    year, qualifier = parse_year(text)
    if year is None:
        return "?" if (text or "").strip() else ""
    return f"{qualifier} {year}" if qualifier else str(year)


def lifespan(birth, death, deceased):
    """Lifespan like '1923–1998', '?–1998', 'born 1950' (living) or '' if no years are known.

    Whether a person has died is shown separately with a † symbol.
    """
    born = year_label(birth)
    died = year_label(death)
    if deceased:
        if born in ("", "?") and died in ("", "?"):
            return ""
        return f"{born or '?'}–{died or '?'}"
    return f"born {born}" if born else ""


def sort_year(text, default=9999):
    year, _ = parse_year(text)
    return default if year is None else year


# --- structured dates for the date picker ----------------------------------------------

QUALIFIER_PREFIX = {"": "", "c.": "ca. ", "bef.": "before ", "aft.": "after "}


def parse_date(text):
    """Split a stored date into (qualifier, day, month, year), parts may be None.

    Returns None if the text is not in one of the forms the picker writes
    (d.m.yyyy, m.yyyy, yyyy, ISO yyyy-mm-dd / yyyy-mm, each with optional qualifier).
    """
    text = (text or "").strip()
    if not text:
        return "", None, None, None
    qualifier, rest = "", text
    for label, pattern in _QUALIFIERS:
        match = pattern.match(text)
        if match:
            qualifier, rest = label, text[match.end():].strip()
            break
    day = month = None
    if m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{3,4})", rest):
        day, month, year = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{3,4})-(\d{1,2})-(\d{1,2})", rest):
        year, month, day = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{1,2})\.(\d{3,4})", rest):
        month, year = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{3,4})-(\d{1,2})", rest):
        year, month = map(int, m.groups())
    elif m := re.fullmatch(r"(\d{3,4})", rest):
        year = int(m.group(1))
    else:
        return None
    if date_error(day, month, year):
        return None
    return qualifier, day, month, year


def date_error(day, month, year):
    """Message if day/month/year do not form a valid (partial) date, else None."""
    if (day or month) and not year:
        return "Please choose a year."
    if day and not month:
        return "Please choose a month (or remove the day)."
    if month and not 1 <= month <= 12:
        return "Invalid month."
    if day and not 1 <= day <= calendar.monthrange(year, month)[1]:
        return f"{calendar.month_name[month]} {year} has no day {day}."
    return None


def format_date(qualifier, day, month, year):
    """Inverse of parse_date: '12.03.1923', '03.1923', '1923', 'ca. 1880', …"""
    if not year:
        return ""
    if day:
        part = f"{day:02d}.{month:02d}.{year}"
    elif month:
        part = f"{month:02d}.{year}"
    else:
        part = str(year)
    return QUALIFIER_PREFIX.get(qualifier, "") + part
