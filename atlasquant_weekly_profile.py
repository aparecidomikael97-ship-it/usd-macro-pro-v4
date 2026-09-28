"""AtlasQuant weekly profile research.

Measures when weekly highs and lows formed inside a historical daily sample.
Day-of-week frequencies come from that sample. Tuesday and Wednesday are never
assumed. Each extreme uses only the rows inside its own week, so a later week
cannot move an earlier extreme. An equal high or low keeps the first
observation in time; a tie is not institutional certainty.
"""
from __future__ import annotations

from math import isfinite

import pandas as pd

SCHEMA = "ATLASQUANT_WEEKLY_PROFILE_V1"
WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}
STATE_INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
STATE_RESEARCH_READY = "RESEARCH_READY"
_MIN_DAYS = 1
_MAX_DAYS = 7


def _require_min_days(value: object) -> int:
    if type(value) is not int or value < _MIN_DAYS or value > _MAX_DAYS:
        raise ValueError("min_days_per_week deve ser int exato entre 1 e 7")
    return value


def _price(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        number = float(value)
    else:
        return None
    if not isfinite(number):
        return None
    return number


def _stamp(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _observe(daily: pd.DataFrame) -> tuple[list[dict[str, object]], int]:
    kept: list[dict[str, object]] = []
    invalid = 0
    records = daily.loc[:, ["datetime", "high", "low"]].to_dict("records")
    for record in records:
        stamp = _stamp(record.get("datetime"))
        high = _price(record.get("high"))
        low = _price(record.get("low"))
        if stamp is None or high is None or low is None or high < low:
            invalid += 1
            continue
        kept.append({"datetime": stamp, "high": high, "low": low})
    kept.sort(key=lambda row: row["datetime"])
    return kept, invalid


def _boundaries(kept: list[dict[str, object]]) -> tuple[str | None, str | None]:
    if not kept:
        return None, None
    start = kept[0]["datetime"]
    end = kept[-1]["datetime"]
    return pd.Timestamp(start).isoformat(), pd.Timestamp(end).isoformat()


def _document(
    *,
    state: str,
    weeks: int,
    observations: int,
    invalid_rows: int,
    min_days: int,
    sample_start: str | None,
    sample_end: str | None,
    data_quality: str,
    high_freq: dict[str, float] | None = None,
    low_freq: dict[str, float] | None = None,
    tuesday_high: float | None = None,
    tuesday_low: float | None = None,
    rows: list[dict[str, object]] | None = None,
    interpretation: str,
) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "state": state,
        "weeks": weeks,
        "observations": observations,
        "invalid_rows": invalid_rows,
        "min_days_per_week": min_days,
        "sample_start": sample_start,
        "sample_end": sample_end,
        "data_quality": data_quality,
        "high_day_frequency_pct": high_freq or {},
        "low_day_frequency_pct": low_freq or {},
        "tuesday_wednesday_high_pct": tuesday_high,
        "tuesday_wednesday_low_pct": tuesday_low,
        "rows": rows or [],
        "extreme_tie_rule": "FIRST_OCCURRENCE",
        "fixed_day_rule_assumed": False,
        "institutional_intent_inferred": False,
        "automatic_strategy_change": False,
        "automatic_promotion": False,
        "interpretation": interpretation,
    }


def analyze_weekly_extremes(daily: pd.DataFrame, *, min_days_per_week: int = 4) -> dict[str, object]:
    """Describe weekly extremes in an observed daily sample.

    ``min_days_per_week`` is an exact integer from 1 to 7. Invalid OHLC rows
    are discarded and counted. They never become a fabricated extreme.
    """
    min_days = _require_min_days(min_days_per_week)
    required = {"datetime", "high", "low"}
    if not isinstance(daily, pd.DataFrame) or not required.issubset(daily.columns):
        return _document(
            state=STATE_INSUFFICIENT_SAMPLE,
            weeks=0,
            observations=0,
            invalid_rows=0,
            min_days=min_days,
            sample_start=None,
            sample_end=None,
            data_quality="INPUT_INVALID",
            interpretation="Dados insuficientes para estudo semanal.",
        )
    if daily.empty:
        return _document(
            state=STATE_INSUFFICIENT_SAMPLE,
            weeks=0,
            observations=0,
            invalid_rows=0,
            min_days=min_days,
            sample_start=None,
            sample_end=None,
            data_quality="EMPTY_SAMPLE",
            interpretation="Dados insuficientes para estudo semanal.",
        )

    kept, invalid_rows = _observe(daily)
    sample_start, sample_end = _boundaries(kept)
    observations = len(kept)
    if not kept:
        return _document(
            state=STATE_INSUFFICIENT_SAMPLE,
            weeks=0,
            observations=0,
            invalid_rows=invalid_rows,
            min_days=min_days,
            sample_start=None,
            sample_end=None,
            data_quality="NO_VALID_ROWS",
            interpretation="Dados insuficientes para estudo semanal.",
        )

    grouped: dict[pd.Timestamp, list[dict[str, object]]] = {}
    for row in kept:
        local = pd.Timestamp(row["datetime"]).tz_convert(None)
        week_start = (local - pd.Timedelta(days=int(local.weekday()))).normalize()
        grouped.setdefault(week_start, []).append({
            **row,
            "weekday": int(local.weekday()),
            "week_start": week_start,
        })

    rows: list[dict[str, object]] = []
    for week_start in sorted(grouped):
        group = grouped[week_start]
        if len(group) < min_days:
            continue
        # Extremes stay inside this week. The first equal print wins.
        high_value = max(float(item["high"]) for item in group)
        low_value = min(float(item["low"]) for item in group)
        high_row = next(item for item in group if float(item["high"]) == high_value)
        low_row = next(item for item in group if float(item["low"]) == low_value)
        rows.append({
            "week_start": pd.Timestamp(week_start).date().isoformat(),
            "days_observed": len(group),
            "high_day": WEEKDAY_NAMES[int(high_row["weekday"])],
            "low_day": WEEKDAY_NAMES[int(low_row["weekday"])],
            "high": high_value,
            "low": low_value,
        })

    weeks = len(rows)
    if not weeks:
        return _document(
            state=STATE_INSUFFICIENT_SAMPLE,
            weeks=0,
            observations=observations,
            invalid_rows=invalid_rows,
            min_days=min_days,
            sample_start=sample_start,
            sample_end=sample_end,
            data_quality="INSUFFICIENT_WEEKS",
            interpretation="Nenhuma semana completa o suficiente para o critério informado.",
        )

    def frequencies(key: str) -> dict[str, float]:
        counts = {name: 0 for name in WEEKDAY_NAMES.values()}
        for row in rows:
            counts[str(row[key])] += 1
        return {
            name: round(100.0 * count / weeks, 2)
            for name, count in counts.items()
            if count
        }

    tuesday_wednesday = {"Tuesday", "Wednesday"}
    return _document(
        state=STATE_RESEARCH_READY,
        weeks=weeks,
        observations=observations,
        invalid_rows=invalid_rows,
        min_days=min_days,
        sample_start=sample_start,
        sample_end=sample_end,
        data_quality="RESEARCH_SAMPLE",
        high_freq=frequencies("high_day"),
        low_freq=frequencies("low_day"),
        tuesday_high=round(
            100.0 * sum(1 for row in rows if row["high_day"] in tuesday_wednesday) / weeks,
            2,
        ),
        tuesday_low=round(
            100.0 * sum(1 for row in rows if row["low_day"] in tuesday_wednesday) / weeks,
            2,
        ),
        rows=rows,
        interpretation=(
            "Frequências históricas descrevem a amostra por ativo/período. "
            "Não provam comportamento institucional nem garantem repetição futura. "
            "Empate de extremo usa a primeira ocorrência e não é certeza institucional."
        ),
    )


__all__ = [
    "SCHEMA",
    "STATE_INSUFFICIENT_SAMPLE",
    "STATE_RESEARCH_READY",
    "WEEKDAY_NAMES",
    "analyze_weekly_extremes",
]
