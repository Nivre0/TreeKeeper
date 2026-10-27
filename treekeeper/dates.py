"""Helpers for free-text, possibly incomplete dates.

Dates are stored exactly as the user typed them ("1923", "12.03.1923",
"ca. 1880", "before 1900", ...). These helpers only extract a year for
sorting and for the short lifespan shown on person cards.
"""

import re

_QUALIFIERS = (
    ("c.", re.compile(r"^\s*(ca\.?|circa|c\.|abt\.?|about|approx\.?|~|um)\s*", re.I)),
    ("bef.", re.compile(r"^\s*(bef\.?|before|vor|<)\s*", re.I)),
    ("aft.", re.compile(r"^\s*(aft\.?|after|nach|>)\s*", re.I)),
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
    """Lifespan like '1923–1998', '1950–' (living), '?–1998', '†' or ''."""
    born = year_label(birth)
    died = year_label(death)
    if deceased:
        if not born and not died:
            return "†"
        return f"{born or '?'}–{died or '?'}"
    return f"{born}–" if born else ""


def sort_year(text, default=9999):
    year, _ = parse_year(text)
    return default if year is None else year
