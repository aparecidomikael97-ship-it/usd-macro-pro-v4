"""Validation and historical-price rules shared by USD Macro Pro.

This module is intentionally independent from Streamlit so it can be tested in
isolation. Public function names/signatures are kept compatible with the
previous app modules.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable, Iterable, Mapping

import pandas as pd

MONTHLY_INDICATORS = {
    "IPC anual",
    "IPC Núcleo anual",
    "PCE anual",
    "PCE Núcleo anual",
    "Payroll variação mensal (mil)",
    "Desemprego",
}
INTERVAL_MINUTES = {"15min": 15, "1h": 60, "4h": 240}
PAIR_RE = re.compile(r"^[A-Z]{3}/[A-Z]{3}$")


def _utc_timestamp(value: Any) -> pd.Timestamp:
    """Return a timezone-aware UTC Timestamp or raise ValueError."""
    try:
        stamp = pd.Timestamp(value)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValueError("Data/hora inválida.") from exc
    if pd.isna(stamp):
        raise ValueError("Data/hora inválida.")
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _naive_day(value: Any) -> pd.Timestamp | None:
    """Parse a date for cadence calculations, ignoring timezone-of-day."""
    try:
        # ISO dates are unambiguous and should not be parsed with dayfirst=True;
        # Brazilian-style strings keep day-first behavior.
        if isinstance(value, str) and re.match(r"^\s*\d{4}-\d{2}-\d{2}(?:[ T]|$)", value):
            stamp = pd.to_datetime(value, dayfirst=False, errors="coerce")
        else:
            stamp = pd.to_datetime(value, dayfirst=True, errors="coerce")
    except Exception:
        return None
    if pd.isna(stamp):
        return None
    stamp = pd.Timestamp(stamp)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC").tz_localize(None)
    return stamp.normalize()


def period_age(indicator: str, observation: Any, now: Any = None) -> int | None:
    """Days after the *reference period*, not days since publication.

    FRED monthly/quarterly timestamps generally identify the beginning of the
    reference period. This function therefore moves monthly observations to
    month-end and GDP observations to quarter-end before calculating age.

    It is a cadence heuristic; it does not verify a release calendar.
    """
    if observation in (None, ""):
        return None
    obs = _naive_day(observation)
    if obs is None:
        return None

    today = _naive_day(pd.Timestamp.now(tz="UTC") if now is None else now)
    if today is None:
        return None

    if indicator in MONTHLY_INDICATORS:
        obs = obs + pd.offsets.MonthEnd(0)
    elif indicator == "PIB":
        obs = obs.to_period("Q").end_time.normalize()

    return max(0, int((today - obs).days))


def audit_quality(rows: Iterable[Mapping[str, Any]]) -> tuple[int, str]:
    """Return (0-100 score, label) based on fresh official FRED observations."""
    rows = list(rows or [])
    if not rows:
        return 0, "BAIXA"

    valid = 0
    for row in rows:
        status = str(row.get("Status", ""))
        source = str(row.get("Fonte", ""))
        if "Atual" in status and source.startswith("FRED"):
            valid += 1

    score = round(100 * valid / len(rows))
    label = "ALTA" if score >= 90 else "MÉDIA" if score >= 70 else "BAIXA"
    return score, label


def pair_ready(pair: str, rows: Iterable[Mapping[str, Any]], currencies: Mapping[str, Mapping[str, Any]]) -> bool:
    """Block a pair when required macro inputs are incomplete or fallback-based."""
    pair = str(pair or "").strip().upper()
    if not PAIR_RE.match(pair):
        return False
    base, quote = pair.split("/")

    rows = list(rows or [])
    if "USD" in (base, quote) and audit_quality(rows)[0] != 100:
        return False

    for code in (base, quote):
        if code == "USD":
            continue
        source = str(currencies.get(code, {}).get("fonte", "")).strip().lower()
        if not source or "fallback" in source or "segurança" in source:
            return False
    return True


def closed_candles(frame: pd.DataFrame, interval: str, now: Any = None) -> pd.DataFrame:
    """Return only valid, closed, de-duplicated OHLC candles.

    - Numeric strings are accepted and normalized to float.
    - Invalid dates/NaN/inf/non-positive prices are dropped.
    - Impossible OHLC geometry is dropped.
    - The still-open candle is excluded.
    - Very stale last data raises ValueError instead of silently producing a
      technical signal.
    """
    if interval not in INTERVAL_MINUTES:
        raise ValueError(f"Intervalo inválido: {interval!r}.")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame deve ser um pandas.DataFrame.")

    required = {"datetime", "open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Colunas OHLC ausentes: " + ", ".join(sorted(missing)))

    minutes = INTERVAL_MINUTES[interval]
    now_utc = _utc_timestamp(pd.Timestamp.now(tz="UTC") if now is None else now)

    d = frame.copy()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close"):
        d[col] = pd.to_numeric(d[col], errors="coerce")

    finite_positive = pd.Series(True, index=d.index)
    for col in ("open", "high", "low", "close"):
        finite_positive &= d[col].map(lambda x: pd.notna(x) and math.isfinite(float(x)) and float(x) > 0)

    geometry = (
        (d["high"] >= d[["open", "close", "low"]].max(axis=1))
        & (d["low"] <= d[["open", "close", "high"]].min(axis=1))
    )
    close_time = d["datetime"] + pd.Timedelta(minutes=minutes)
    closed = d["datetime"].notna() & (close_time <= now_utc)

    d = d[finite_positive & geometry & closed]
    d = d.sort_values("datetime").drop_duplicates("datetime", keep="last").reset_index(drop=True)

    if not d.empty:
        last_close = d.iloc[-1]["datetime"] + pd.Timedelta(minutes=minutes)
        if now_utc - last_close > pd.Timedelta(minutes=minutes * 2):
            raise ValueError(
                "Candles antigos: aguarde atualização da fonte ou a reabertura do mercado."
            )
    return d


def historical_close(
    pair: str,
    target: Any,
    key: str,
    get: Callable[..., Any],
    now: Any = None,
) -> tuple[float | None, str | None, str]:
    """Fetch the first 15-minute close that belongs to the requested horizon.

    The provider is explicitly asked for UTC. A candle timestamp represents its
    opening time, so 15 minutes are added before comparing with the target.
    A price is accepted only when its close lies in [target, target+15min), is
    already closed, finite and positive. Anything else stays pending instead of
    being guessed from a distant candle.
    """
    if not key:
        return None, None, "CHAVE_TWELVE_DATA ausente."

    pair = str(pair or "").strip().upper()
    if not PAIR_RE.match(pair):
        return None, None, "Par inválido. Use o formato AAA/BBB."

    try:
        target_utc = _utc_timestamp(target)
        now_utc = _utc_timestamp(pd.Timestamp.now(tz="UTC") if now is None else now)
    except ValueError:
        return None, None, "Data/hora inválida."

    if now_utc < target_utc:
        return None, None, "Horizonte ainda não venceu."

    try:
        response = get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": pair,
                "interval": "15min",
                "apikey": key,
                "timezone": "UTC",
                "start_date": (target_utc - pd.Timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": target_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "outputsize": 4,
                "order": "ASC",
                "format": "JSON",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return None, None, "Resposta inesperada da fonte histórica."
        if payload.get("status") == "error":
            return None, None, "Fonte não disponibilizou o histórico solicitado."

        values = payload.get("values", [])
        if not isinstance(values, list):
            return None, None, "Resposta histórica sem lista de candles."

        candidates: list[tuple[pd.Timestamp, float]] = []
        for value in values:
            if not isinstance(value, Mapping):
                continue
            try:
                open_at = pd.to_datetime(value.get("datetime"), utc=True, errors="raise")
                close_at = pd.Timestamp(open_at) + pd.Timedelta(minutes=15)
                price = float(value.get("close"))
            except Exception:
                continue
            if (
                target_utc <= close_at < target_utc + pd.Timedelta(minutes=15)
                and close_at <= now_utc
                and math.isfinite(price)
                and price > 0
            ):
                candidates.append((close_at, price))

        if not candidates:
            return None, None, "Sem fechamento no horizonte exato; resultado mantido pendente."

        dt, price = min(candidates, key=lambda item: item[0])
        return price, dt.isoformat(), ""
    except Exception as exc:
        return None, None, f"Falha na consulta: {type(exc).__name__}"
