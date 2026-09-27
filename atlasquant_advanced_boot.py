"""Open Modo Avançado from a validated snapshot without blocking on providers.

The interactive app already loaded ATLASQUANT_HOME_SNAPSHOT_V1 before this
decision. A fresh, safe snapshot is real data with a timestamp — it is not a
live fetch and it is not a fabricated number. Stale, incomplete or unsafe
snapshots fail closed so the caller keeps the existing live loaders.

This module does not send orders, change gates or invent market values.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import threading
import time
from typing import Any, Callable, Mapping

import pandas as pd

from atlasquant_fast_startup import validate_home_snapshot

CACHED_SNAPSHOT = "CACHED_SNAPSHOT"
STALE_REJECTED = "STALE_REJECTED"
LIVE_REQUIRED = "LIVE_REQUIRED"
LIVE_REFRESH = "LIVE_REFRESH"

_RANK_COLUMNS = ("Código", "Pontuação_Final")
_LOCK = threading.Lock()
_WARM: dict[str, Any] = {
    "status": "idle",
    "result": None,
    "error": "",
    "finished_at": "",
}


def reset_live_refresh_for_tests() -> None:
    """Clear the process-local refresh slot. Tests only."""
    with _LOCK:
        _WARM["status"] = "idle"
        _WARM["result"] = None
        _WARM["error"] = ""
        _WARM["finished_at"] = ""


def peek_live_refresh() -> dict[str, Any]:
    with _LOCK:
        result = _WARM.get("result")
        return {
            "status": str(_WARM.get("status") or "idle"),
            "result": dict(result) if isinstance(result, Mapping) else None,
            "error": str(_WARM.get("error") or ""),
            "finished_at": str(_WARM.get("finished_at") or ""),
        }


def publish_live_refresh(result: Mapping[str, Any], *, finished_at: str = "") -> None:
    """Remember a successful live read so the next rerun does not block again."""
    payload = {
        "macro_eua": dict(result.get("macro_eua") or {}),
        "fed": dict(result.get("fed") or {}),
        "dados_moedas": dict(result.get("dados_moedas") or {}),
    }
    if not payload["macro_eua"] or not payload["fed"] or not payload["dados_moedas"]:
        return
    with _LOCK:
        _WARM["status"] = "ready"
        _WARM["result"] = payload
        _WARM["error"] = ""
        _WARM["finished_at"] = finished_at or datetime.now().astimezone().isoformat(timespec="seconds")


def start_live_refresh(loaders: Mapping[str, Callable[[], Any]]) -> str:
    """Fetch independent sources on a daemon thread. Failures stay empty.

    The UI must already be showing a labeled snapshot. A failed refresh never
    replaces that snapshot with guessed values.
    """
    with _LOCK:
        status = str(_WARM.get("status") or "idle")
        if status in {"running", "ready"}:
            return status
        _WARM["status"] = "running"
        _WARM["error"] = ""
        _WARM["result"] = None

    def _job() -> None:
        try:
            payload = {name: loader() for name, loader in dict(loaders).items()}
        except Exception as exc:
            with _LOCK:
                _WARM["status"] = "failed"
                _WARM["result"] = None
                _WARM["error"] = f"{type(exc).__name__}: {exc}"
            return
        if not isinstance(payload.get("macro_eua"), Mapping) or not isinstance(payload.get("fed"), Mapping) or not isinstance(payload.get("dados_moedas"), Mapping):
            with _LOCK:
                _WARM["status"] = "failed"
                _WARM["result"] = None
                _WARM["error"] = "payload incompleto"
            return
        if not payload["macro_eua"] or not payload["fed"] or not payload["dados_moedas"]:
            with _LOCK:
                _WARM["status"] = "failed"
                _WARM["result"] = None
                _WARM["error"] = "fonte devolveu vazio"
            return
        publish_live_refresh(payload)

    threading.Thread(target=_job, name="aq-advanced-refresh", daemon=True).start()
    return "running"


def _ranking_frame(raw: Any) -> pd.DataFrame | None:
    if isinstance(raw, pd.DataFrame):
        frame = raw.copy()
    elif isinstance(raw, list) and raw and all(isinstance(row, Mapping) for row in raw):
        frame = pd.DataFrame([dict(row) for row in raw])
    else:
        return None
    if frame.empty or not set(_RANK_COLUMNS).issubset(frame.columns):
        return None
    return frame


def resolve_advanced_open(
    snapshot: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
    max_age_min: float = 90.0,
) -> dict[str, Any]:
    """Decide whether Advanced can paint from the validated snapshot."""
    started = time.perf_counter()
    check = validate_home_snapshot(snapshot, max_age_min=max_age_min, now=now)
    errors = list(check.get("errors") or [])
    base: dict[str, Any] = {
        "use_cache": False,
        "state": LIVE_REQUIRED,
        "generated_at": str(dict(snapshot or {}).get("generated_at") or ""),
        "runtime_generated_at": str(dict(snapshot or {}).get("runtime_generated_at") or ""),
        "age_minutes": check.get("age_minutes"),
        "input_age_minutes": check.get("input_age_minutes"),
        "errors": errors,
        "real_orders_enabled": False,
        "automatic_execution": False,
        "macro_eua": None,
        "fed": None,
        "dados_moedas": None,
        "ranking": None,
        "usd_detalhado": None,
        "status_fonte": None,
        "refresh_status": "não iniciada",
        "resolve_ms": 0.0,
    }
    if not check.get("valid"):
        if "stale" in errors or "generated_at" in errors:
            base["state"] = STALE_REJECTED
        base["resolve_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return base

    fast = dict(dict(check["snapshot"].get("inputs") or {}).get("fast_boot") or {})
    ranking = _ranking_frame(fast.get("ranking"))
    macro = fast.get("macro_eua")
    fed = fast.get("fed")
    currencies = fast.get("dados_moedas")
    usd = fast.get("usd_detalhado")
    if ranking is None or not isinstance(macro, Mapping) or not macro or not isinstance(fed, Mapping) or not fed or not isinstance(currencies, Mapping) or not currencies or not isinstance(usd, Mapping) or not usd:
        base["state"] = LIVE_REQUIRED
        base["errors"] = ["fast_boot.shape"]
        base["resolve_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return base

    base.update({
        "use_cache": True,
        "state": CACHED_SNAPSHOT,
        "generated_at": str(check["snapshot"].get("generated_at") or ""),
        "runtime_generated_at": str(check["snapshot"].get("runtime_generated_at") or ""),
        "errors": [],
        "macro_eua": dict(macro),
        "fed": dict(fed),
        "dados_moedas": {str(key): dict(value) if isinstance(value, Mapping) else value for key, value in dict(currencies).items()},
        "ranking": ranking,
        "usd_detalhado": dict(usd),
        "status_fonte": dict(fast.get("status_fonte") or {}) if isinstance(fast.get("status_fonte"), Mapping) else {},
        "refresh_status": "em segundo plano",
    })
    base["resolve_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return base


def provenance_banner_html(decision: Mapping[str, Any] | None) -> str:
    """High-contrast note. Cached data is never described as a live fetch."""
    item = dict(decision or {})
    state = str(item.get("state") or "")
    if state == CACHED_SNAPSHOT:
        generated = escape(str(item.get("generated_at") or "horário indisponível"))
        age = item.get("age_minutes")
        age_txt = f"{float(age):.0f} min" if isinstance(age, (int, float)) else "idade não calculada"
        refresh = escape(str(item.get("refresh_status") or "em segundo plano"))
        return (
            '<div class="aq-boot-banner" role="status" style="background:#fff6d8;color:#1a1406;border:1px solid #8a6412;border-radius:12px;padding:10px 12px;font-weight:750">'
            '<strong style="color:#1a1406">Leitura em cache.</strong> '
            f'<span style="color:#1a1406">Snapshot validado em {generated} · idade {age_txt}. '
            "Esta abertura não espera fontes externas e não trata o cache como coleta ao vivo. "
            f"Atualização em segundo plano: {refresh}.</span>"
            "</div>"
        )
    if state == STALE_REJECTED:
        return (
            '<div class="aq-boot-banner aq-boot-live" role="status">'
            "<strong>Snapshot antigo rejeitado.</strong> "
            "A tela não apresenta dado vencido como atual. A leitura segue o caminho ao vivo."
            "</div>"
        )
    if state == LIVE_REFRESH:
        finished = escape(str(item.get("generated_at") or item.get("runtime_generated_at") or ""))
        when = f" · concluída em {finished}" if finished else ""
        return (
            '<div class="aq-boot-banner aq-boot-live" role="status">'
            "<strong>Fontes atualizadas.</strong> "
            f"Esta leitura substituiu o snapshot em cache{when}. "
            "Ordens reais continuam bloqueadas."
            "</div>"
        )
    return ""


__all__ = [
    "CACHED_SNAPSHOT",
    "STALE_REJECTED",
    "LIVE_REQUIRED",
    "LIVE_REFRESH",
    "resolve_advanced_open",
    "provenance_banner_html",
    "start_live_refresh",
    "peek_live_refresh",
    "publish_live_refresh",
    "reset_live_refresh_for_tests",
]
