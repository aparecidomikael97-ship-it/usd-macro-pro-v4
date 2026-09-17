"""AtlasQuant V11.1 — Twelve Data quota-saving runner.

Mantém o Autopilot V11.0 intacto, mas reduz chamadas externas reutilizando
uma única série M15 por par para derivar H1 e H4 localmente. O endpoint
/time_series continua sendo usado para M15 e D1; H1/H4 derivados não fazem
novas chamadas ao provedor.
"""
from __future__ import annotations

import pandas as pd

import autopilot_v107 as base

# 1.200 candles M15 = 300 H1 e 75 H4. Isso preserva margem acima dos
# 60 candles mínimos usados pelos analisadores H1/H4 do motor atual.
M15_DERIVATION_OUTPUTSIZE = 1200

_ORIGINAL_TD_FETCH = base.td_fetch
_ORIGINAL_STATUS_SUMMARY = base.status_summary
_M15_SOURCE_CACHE: dict[str, pd.DataFrame] = {}


def _normalize_quota_block_type() -> None:
    """Corrige o rótulo se um retry de limite/minuto terminar em cota diária."""
    reason = str(getattr(base, "_TD_DAILY_BLOCK_REASON", "") or "")
    if reason and base._td_is_daily_quota(reason):
        base._TD_BLOCK_TYPE = "COTA_DIARIA"


def _fetch_m15_source(pair: str, outputsize: int = M15_DERIVATION_OUTPUTSIZE) -> tuple[pd.DataFrame, str]:
    cached = _M15_SOURCE_CACHE.get(pair)
    if cached is not None and not cached.empty:
        return cached.copy(), ""

    size = max(int(outputsize or 0), M15_DERIVATION_OUTPUTSIZE)
    frame, err = _ORIGINAL_TD_FETCH(pair, "15min", size)
    _normalize_quota_block_type()
    if err or frame is None or frame.empty:
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(), err

    clean = base.normalize_ohlc(frame)
    if clean.empty:
        return clean, "M15 sem OHLC válido para derivação."
    _M15_SOURCE_CACHE[pair] = clean.copy()
    return clean, ""


def quota_saver_td_fetch(pair: str, interval: str, outputsize: int) -> tuple[pd.DataFrame, str]:
    """Compatível com td_fetch, porém H1/H4 são derivados da mesma leitura M15."""
    tf = str(interval or "").strip().lower()

    if tf == "15min":
        return _fetch_m15_source(pair, max(int(outputsize or 0), M15_DERIVATION_OUTPUTSIZE))

    if tf in {"1h", "4h"}:
        source, err = _fetch_m15_source(pair)
        if err or source.empty:
            return pd.DataFrame(), err or f"M15 indisponível para derivar {tf}."
        try:
            derived = base.aggregate_ohlc(source, tf)
            if derived.empty:
                return derived, f"Derivação local {tf} sem dados."
            return derived, ""
        except Exception as exc:
            return pd.DataFrame(), f"DERIVACAO_{tf.upper()}: {type(exc).__name__}: {exc}"

    # D1 e qualquer outro timeframe continuam no provedor original.
    frame, err = _ORIGINAL_TD_FETCH(pair, interval, outputsize)
    _normalize_quota_block_type()
    return frame, err


def quota_saver_status_summary(*args, **kwargs):
    """Acrescenta evidência observável de que a camada V11.1 está ativa."""
    status = _ORIGINAL_STATUS_SUMMARY(*args, **kwargs)
    if isinstance(status, dict):
        status["twelve_quota_saver_v111"] = {
            "enabled": True,
            "m15_source_pairs_this_run": len(_M15_SOURCE_CACHE),
            "derived_timeframes": ["1h", "4h"],
            "m15_outputsize": M15_DERIVATION_OUTPUTSIZE,
        }
    return status


def install_quota_guard() -> None:
    """Instala a camada de economia apenas no processo atual."""
    _M15_SOURCE_CACHE.clear()
    base.td_fetch = quota_saver_td_fetch
    base.status_summary = quota_saver_status_summary


def main() -> int:
    install_quota_guard()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
