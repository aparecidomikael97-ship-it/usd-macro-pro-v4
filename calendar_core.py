"""Pure calendar parsing/normalization helpers for USD Macro Pro.

No Streamlit import here. Keeping these rules pure makes them fast and easy to
unit-test without starting the UI.
"""
from __future__ import annotations

from datetime import date, timedelta
from html.parser import HTMLParser
import re
from typing import Any, Iterable, Mapping

import pandas as pd

MONTHS = {
    name: i + 1
    for i, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        )
    )
}
MONTHS.update(
    {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Jun": 6, "Jul": 7,
        "Aug": 8, "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }
)


class TextParser(HTMLParser):
    """Extract visible text while ignoring script/style blocks."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _meeting_row(year: int, start_month: int, end_month: int, end_day: int, projections: bool) -> dict[str, str] | None:
    # A Jan ending after a Dec start belongs to the following year.
    end_year = year + 1 if end_month < start_month else year
    try:
        dt = date(end_year, end_month, end_day)
    except ValueError:
        return None
    return {
        "date": dt.isoformat(),
        "event": "FOMC · Decisão de juros",
        "details": "Com projeções econômicas" if projections else "Reunião programada",
    }


def parse_fomc(html: str) -> list[dict[str, str]]:
    """Parse regular FOMC meeting decision dates from the Fed calendar HTML.

    Supports the Fed's visible forms such as ``September 15-16*`` and
    ``Apr/May 30-1`` plus the common textual variant ``April 30-May 1``.
    Unknown/blocked HTML returns an empty list rather than inventing dates.
    """
    if not isinstance(html, str) or not html.strip():
        return []

    parser = TextParser()
    try:
        parser.feed(html)
    except Exception:
        return []
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    sections = list(re.finditer(r"\b(20\d{2})\s+FOMC Meetings\b", text, flags=re.I))
    if not sections:
        return []

    names = "|".join(sorted(map(re.escape, MONTHS), key=len, reverse=True))
    # Official Fed form: Apr/May 30-1* or September 15-16*
    official = re.compile(
        rf"\b({names})(?:\s*/\s*({names}))?\s+(\d{{1,2}})\s*[-–—]\s*(\d{{1,2}})(\*)?",
        flags=re.I,
    )
    # Defensive alternative: April 30-May 1*
    alternative = re.compile(
        rf"\b({names})\s+(\d{{1,2}})\s*[-–—]\s*({names})\s+(\d{{1,2}})(\*)?",
        flags=re.I,
    )

    # Case-insensitive month lookup while preserving the compact constant.
    month_lookup = {k.lower(): v for k, v in MONTHS.items()}
    rows: list[dict[str, str]] = []

    for i, section in enumerate(sections):
        body = text[
            section.end() : sections[i + 1].start() if i + 1 < len(sections) else len(text)
        ]
        year = int(section.group(1))

        matches: list[tuple[int, dict[str, str] | None]] = []
        for item in official.finditer(body):
            m1 = month_lookup[item.group(1).lower()]
            m2 = month_lookup[(item.group(2) or item.group(1)).lower()]
            row = _meeting_row(year, m1, m2, int(item.group(4)), bool(item.group(5)))
            matches.append((item.start(), row))

        for item in alternative.finditer(body):
            m1 = month_lookup[item.group(1).lower()]
            m2 = month_lookup[item.group(3).lower()]
            row = _meeting_row(year, m1, m2, int(item.group(4)), bool(item.group(5)))
            matches.append((item.start(), row))

        for _, row in sorted(matches, key=lambda x: x[0]):
            if row is not None:
                rows.append(row)

    # Stable de-duplication by decision date.
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique.setdefault(row["date"], row)
    return list(unique.values())


def value_text(value: Any) -> str:
    """Render source values while preserving legitimate zero values."""
    if value is None:
        return "—"
    text = str(value).strip()
    return "—" if text in ("", "nan", "NaN", "None", "NaT") else text


def eod_row(raw: Mapping[str, Any], timezone: str) -> dict[str, Any] | None:
    """Normalize one EODHD economic-event row without guessing timezone."""
    if not isinstance(raw, Mapping):
        return None
    try:
        stamp = pd.Timestamp(raw.get("date"))
        if pd.isna(stamp):
            return None
    except Exception:
        return None

    known_zone = stamp.tzinfo is not None
    if known_zone:
        try:
            stamp = stamp.tz_convert(timezone)
        except Exception:
            return None

    raw_date = str(raw.get("date", ""))
    hour = stamp.strftime("%H:%M") if re.search(r"\d{1,2}:\d{2}", raw_date) else "Não informado"
    if not known_zone and hour != "Não informado":
        hour += " · fuso não informado"

    parts = [
        str(raw.get("type") or raw.get("event") or "Evento"),
        str(raw.get("comparison") or ""),
        str(raw.get("period") or ""),
    ]
    return {
        "Data": stamp.date(),
        "Evento": " · ".join(p for p in parts if p),
        "Horário": hour,
        "Prioridade": "Não classificada",
        "Fonte": "EODHD",
        "Anterior": value_text(raw.get("previous")),
        "Consenso": value_text(raw.get("estimate")),
        "Realizado": value_text(raw.get("actual")),
        "Detalhes": "EUA · unidade conforme a fonte",
    }


def upcoming(rows: Iterable[Mapping[str, Any]], today: date, days: int) -> list[dict[str, Any]]:
    """Filter, de-duplicate and sort events in the inclusive [today, today+days] window."""
    if days < 0:
        return []
    end = today + timedelta(days=days)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in rows or []:
        try:
            dt = pd.Timestamp(row["Data"]).date()
        except Exception:
            continue
        event = str(row.get("Evento", ""))
        source = str(row.get("Fonte", ""))
        key = (dt, event, source)
        if today <= dt <= end and key not in seen:
            seen.add(key)
            item = dict(row)
            item["Data"] = dt
            item["Em dias"] = (dt - today).days
            selected.append(item)

    return sorted(selected, key=lambda r: (r["Data"], str(r.get("Evento", "")), str(r.get("Fonte", ""))))
