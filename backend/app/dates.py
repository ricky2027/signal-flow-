"""Literal full-date corroboration. Never infer dates from retrieval or copyright."""
import calendar
import re


def date_in_text(value, text):
    if value is None:
        return False
    if re.search(r'(?<!\d)' + re.escape(value.isoformat()) + r'(?:[T\s]|\b)', text):
        return True
    month = '(?:' + '|'.join({calendar.month_name[value.month], calendar.month_abbr[value.month]}) + r')\.?'
    day = rf'0?{value.day}(?:st|nd|rd|th)?'
    year = str(value.year)
    return bool(re.search(rf'\b(?:{month}\s+{day},?\s+{year}|{day}\s+{month},?\s+{year})\b', text, re.I))
