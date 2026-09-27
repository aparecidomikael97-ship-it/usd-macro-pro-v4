"""Open Modo Avançado from a validated snapshot without blocking on providers.

The interactive app already loaded ATLASQUANT_HOME_SNAPSHOT_V1 before this
decision. A fresh, safe snapshot is real data with a timestamp — it is not a
live fetch and it is not a fabricated number. Stale, incomplete or unsafe
snapshots fail closed so the caller keeps the existing live loaders.

This module does not send orders, change gates or invent market values.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
_SOURCE_NAMES = ("macro_eua", "fed", "dados_moedas")
# Each source has its own budget. Wall time is the slowest budget, not the sum.
DEFAULT_SOURCE_TIMEOUTS = {
    "macro_eua": 25.0,
    "fed": 25.0,
    "dados_moedas": 50.0,
}

_RANK_COLUMNS = ("Código", "Pontuação_Final")
_LOCK = threading.Lock()
_WARM: dict[str, Any] = {
    "status": "idle",
    "result": None,
    "error": "",
    "finished_at": "",
    "sources": {},
}


def reset_live_refresh_for_tests() -> None:
    """Clear the process-local refresh slot. Tests only."""
    with _LOCK:
        _WARM["status"] = "idle"
        _WARM["result"] = None
        _WARM["error"] = ""
        _WARM["finished_at"] = ""
        _WARM["sources"] = {}


def peek_live_refresh() -> dict[str, Any]:
    with _LOCK:
        result = _WARM.get("result")
        sources = _WARM.get("sources")
        return {
            "status": str(_WARM.get("status") or "idle"),
            "result": dict(result) if isinstance(result, Mapping) else None,
            "error": str(_WARM.get("error") or ""),
            "finished_at": str(_WARM.get("finished_at") or ""),
            "sources": dict(sources) if isinstance(sources, Mapping) else {},
            "real_orders_enabled": False,
            "automatic_execution": False,
        }


def _clean_status(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(k)[:40]: str(v)[:160] for k, v in raw.items() if str(k).strip()}


def publish_live_refresh(
    result: Mapping[str, Any],
    *,
    finished_at: str = "",
    status_fonte: Mapping[str, Any] | None = None,
) -> None:
    """Remember a successful live read so the next rerun does not block again.

    ``status_fonte`` travels with the package so the provenance line shown next
    to the data describes that exact read (for example, safety values without FRED).
    """
    payload = {
        "macro_eua": dict(result.get("macro_eua") or {}),
        "fed": dict(result.get("fed") or {}),
        "dados_moedas": dict(result.get("dados_moedas") or {}),
    }
    if not payload["macro_eua"] or not payload["fed"] or not payload["dados_moedas"]:
        return
    status = _clean_status(status_fonte)
    if status:
        payload["status_fonte"] = status
    with _LOCK:
        _WARM["status"] = "ready"
        _WARM["result"] = payload
        _WARM["error"] = ""
        _WARM["sources"] = {}
        _WARM["finished_at"] = finished_at or datetime.now().astimezone().isoformat(timespec="seconds")


def _timeout_for(name: str, timeout_s: float | None, timeouts: Mapping[str, float] | None) -> float:
    if timeouts and name in timeouts:
        return max(0.05, float(timeouts[name]))
    if timeout_s is not None:
        return max(0.05, float(timeout_s))
    return max(0.05, float(DEFAULT_SOURCE_TIMEOUTS.get(name, 25.0)))


def _format_source_report(sources: Mapping[str, Mapping[str, Any]]) -> str:
    labels = {
        "ok": "ok",
        "failed": "falhou",
        "slow": "lenta",
        "empty": "vazia",
        "missing": "ausente",
    }
    parts = []
    for name in _SOURCE_NAMES:
        item = dict(sources.get(name) or {})
        state = str(item.get("state") or "missing")
        detail = str(item.get("detail") or "")
        label = labels.get(state, state)
        parts.append(f"{name}: {label}" + (f" ({detail})" if detail else ""))
    return "; ".join(parts)


def _call_loader(loader: Callable[[], Any]) -> tuple[str, Any]:
    try:
        value = loader()
    except Exception as exc:
        return "failed", f"{type(exc).__name__}: {exc}"
    if not isinstance(value, Mapping) or len(value) == 0:
        return "empty", "retorno vazio" if value in ({}, None) else "retorno inválido"
    return "ok", dict(value)


def collect_source_refresh(
    loaders: Mapping[str, Callable[[], Any]],
    *,
    timeout_s: float | None = None,
    timeouts: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Run macro, Fed and currency loaders at the same time.

    A slow or failing source is recorded on its own. Missing values are not
    invented, and an incomplete read is not publishable. Safety flags stay off.
    """
    selected = {name: loaders[name] for name in _SOURCE_NAMES if name in loaders}
    reports: dict[str, dict[str, Any]] = {}
    for name in _SOURCE_NAMES:
        if name not in selected:
            reports[name] = {"state": "missing", "detail": "loader ausente", "elapsed_ms": 0.0}

    executor = ThreadPoolExecutor(max_workers=max(1, len(selected)), thread_name_prefix="aq-src")
    started = time.perf_counter()
    futures = {name: executor.submit(_call_loader, loader) for name, loader in selected.items()}
    future_names = {future: name for name, future in futures.items()}
    deadlines = {
        name: time.perf_counter() + _timeout_for(name, timeout_s, timeouts)
        for name in futures
    }
    pending = dict(futures)
    while pending:
        remaining = min(deadlines[name] - time.perf_counter() for name in pending)
        done, _ = wait(
            list(pending.values()),
            timeout=max(0.0, remaining),
            return_when=FIRST_COMPLETED,
        )
        for future in done:
            name = future_names[future]
            pending.pop(name, None)
            state, payload = future.result()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            if state == "ok":
                reports[name] = {"state": "ok", "detail": "", "elapsed_ms": elapsed_ms, "value": payload}
            elif state == "failed":
                reports[name] = {"state": "failed", "detail": str(payload), "elapsed_ms": elapsed_ms}
            else:
                reports[name] = {"state": "empty", "detail": str(payload), "elapsed_ms": elapsed_ms}
        now = time.perf_counter()
        for name in [name for name in list(pending) if now >= deadlines[name]]:
            pending.pop(name)
            reports[name] = {
                "state": "slow",
                "detail": f"timeout {_timeout_for(name, timeout_s, timeouts):.2f}s",
                "elapsed_ms": round((now - started) * 1000, 1),
            }
    executor.shutdown(wait=False, cancel_futures=True)

    publishable = all(reports.get(name, {}).get("state") == "ok" for name in _SOURCE_NAMES)
    payload = None
    if publishable:
        payload = {name: dict(reports[name]["value"]) for name in _SOURCE_NAMES}
    public_sources = {
        name: {
            "state": str(item.get("state") or "missing"),
            "detail": str(item.get("detail") or ""),
            "elapsed_ms": item.get("elapsed_ms") or 0.0,
        }
        for name, item in reports.items()
    }
    return {
        "publishable": publishable,
        "payload": payload,
        "sources": public_sources,
        "error": "" if publishable else _format_source_report(public_sources),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "real_orders_enabled": False,
        "automatic_execution": False,
    }


def start_live_refresh(
    loaders: Mapping[str, Callable[[], Any]],
    *,
    force: bool = False,
    timeout_s: float | None = None,
    timeouts: Mapping[str, float] | None = None,
    status_snapshot: Callable[[], Mapping[str, Any]] | None = None,
) -> str:
    """Refresh sources off the UI thread. A failed attempt keeps the last good package.

    ``status_snapshot`` is read after the loaders finish, because loaders record
    their source status in the globals of the rerun that started the job.

    The three loaders run together. One exception, timeout or empty payload does
    not erase a package that already passed validation, and it does not fill
    the gap with guessed values.
    """
    with _LOCK:
        status = str(_WARM.get("status") or "idle")
        if status == "running":
            return status
        if status == "ready" and not force:
            return status
        previous = dict(_WARM["result"]) if isinstance(_WARM.get("result"), Mapping) else None
        _WARM["status"] = "running"
        _WARM["error"] = ""
        _WARM["sources"] = {}

    def _job() -> None:
        try:
            outcome = collect_source_refresh(loaders, timeout_s=timeout_s, timeouts=timeouts)
        except Exception as exc:
            outcome = {
                "publishable": False,
                "payload": None,
                "sources": {},
                "error": f"atualização: {type(exc).__name__}: {exc}",
            }
        if outcome["publishable"] and isinstance(outcome.get("payload"), Mapping):
            status: Mapping[str, Any] | None = None
            if status_snapshot is not None:
                try:
                    status = status_snapshot()
                except Exception:
                    status = None
            publish_live_refresh(outcome["payload"], status_fonte=status)
            with _LOCK:
                _WARM["sources"] = dict(outcome["sources"])
                _WARM["error"] = ""
            return
        with _LOCK:
            _WARM["sources"] = dict(outcome["sources"])
            _WARM["error"] = str(outcome["error"] or "payload incompleto")
            if previous:
                _WARM["result"] = previous
                _WARM["status"] = "retained"
            else:
                _WARM["result"] = None
                _WARM["status"] = "failed"

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
        refresh = str(item.get("refresh_status") or "")
        if refresh.startswith("pacote anterior"):
            detail = escape(refresh)
            return (
                '<div class="aq-boot-banner" role="status" style="background:#fff6d8;color:#1a1406;border:1px solid #8a6412;border-radius:12px;padding:10px 12px;font-weight:750">'
                '<strong style="color:#1a1406">Pacote anterior mantido.</strong> '
                f'<span style="color:#1a1406">A atualização nova não passou na validação e não substituiu a última leitura íntegra. {detail}. '
                "Ordens reais continuam bloqueadas.</span>"
                "</div>"
            )
        finished = escape(str(item.get("generated_at") or item.get("runtime_generated_at") or ""))
        when = f" · concluída em {finished}" if finished else ""
        degraded = [str(x) for x in list(item.get("degraded_sources") or []) if str(x).strip()]
        partial = (
            " Fontes com fallback ou valores de segurança: "
            + escape(", ".join(degraded[:12]))
            + ". Veja Fontes/estado."
            if degraded else ""
        )
        return (
            '<div class="aq-boot-banner aq-boot-live" role="status">'
            "<strong>Fontes atualizadas.</strong> "
            f"Esta leitura substituiu o snapshot em cache{when}.{partial} "
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
    "collect_source_refresh",
    "peek_live_refresh",
    "publish_live_refresh",
    "reset_live_refresh_for_tests",
    "DEFAULT_SOURCE_TIMEOUTS",
]
