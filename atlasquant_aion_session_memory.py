"""Adapt already-resident AtlasQuant state into a specialist session snapshot.

This module only copies an explicit whitelist. It does not read session state
on its own, open the network, call market or calendar loaders, or turn a
missing clock, score, or incomplete matrix into a confirmed fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from itertools import islice
import re
from typing import Any, Mapping

from atlasquant_aion_specialist_session import SCHEMA, build_specialist_session_snapshot
from atlasquant_aion_truth import assess_truth
from atlasquant_fx_universe import OFFICIAL_PAIRS

SESSION_WHITELIST = (
    "atlasquant_advanced_boot",
    "atlasquant_pair_matrix_status",
    "aion_working_checkpoint_v2",
    "atlasquant_research_evidence_records",
)
GLOBAL_WHITELIST = (
    "macro_eua",
    "ranking",
    "fed",
    "_fast_snapshot",
    "_aq_pair_matrix_result",
    "_aq_pair_context",
)
_INPUT_KEYS = (
    "boot",
    "pair_matrix_status",
    "pair_matrix_result",
    "checkpoint",
    "research_records",
    "lab_records",
    "evidence_rows",
    "macro_eua",
    "macro_event",
    "fed",
    "ranking",
    "radar_ranking",
    "scanner",
    "persisted_scanner",
    "persisted_results",
    "runtime_snapshot",
    "source_mesh",
    "market_context",
    "studio",
    "business",
    "invest",
)
_SECRET_PARTS = {
    "token", "password", "passwd", "secret", "cookie", "cookies",
    "authorization", "bearer", "credential", "credentials", "apikey",
}
_SECRET_EXACT = _SECRET_PARTS | {
    "api_key", "access_token", "refresh_token", "github_token",
    "github_token_historico", "private_key", "client_secret", "headers",
    "set_cookie", "session_token", "jwt",
}
_SEMESTER = re.compile(
    r"(?i)(\bsemestre\b|\bsemestral\b|"
    r"\b20\d{2}\s*[-_/]?\s*[sh][12]\b|"
    r"\b[sh][12]\s*[-_/]?\s*20\d{2}\b|"
    r"\b[12]\s*[ºo°]?\s*semestre\b)"
)
_OFFICIAL = set(OFFICIAL_PAIRS)


def _text(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _secret_key(name: Any) -> bool:
    key = str(name or "").strip().lower().replace("-", "_")
    if not key or key in _SECRET_EXACT:
        return True if key in _SECRET_EXACT else False
    if "api_key" in key or "access_token" in key or "refresh_token" in key:
        return True
    return bool(set(key.split("_")) & _SECRET_PARTS)


def _strip(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            if _secret_key(key):
                continue
            cleaned[str(key)] = _strip(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [
            _strip(item, depth + 1)
            for item in islice(value, 300)
        ]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return _verifiable_clock(value)
    records = _records(value)
    if records is not None and not isinstance(value, (str, bytes)):
        return _strip(records, depth + 1)
    return _text(value, 200)


def _records(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    to_dict = getattr(value, "to_dict", None)
    if not callable(to_dict):
        return None
    try:
        rows = to_dict("records")
    except (TypeError, ValueError):
        return None
    return rows if isinstance(rows, list) else None


def _ttl(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number != number:
        return None
    return number


def _verifiable_clock(value: Any) -> str:
    """Return an ISO clock already present on the object.

    A semester label is not a timestamp. Nothing is synthesized in its place.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return ""
        return value.astimezone(timezone.utc).isoformat()
    text = _text(value, 80)
    if not text or _SEMESTER.search(text):
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        return ""
    return text


def _first_clock(*values: Any) -> str:
    for value in values:
        clock = _verifiable_clock(value)
        if clock:
            return clock
    return ""


def _clock_fields(body: Mapping[str, Any]) -> str:
    return _first_clock(
        body.get("observed_at"),
        body.get("generated_at"),
        body.get("runtime_generated_at"),
        body.get("updated_at"),
        body.get("checked_at"),
        body.get("timestamp"),
    )


def _mark(origin: str, observed_at: str, ttl: float | None, source_ref: str, *, now: datetime | None) -> dict[str, Any]:
    assessment = assess_truth([{
        "claim": "resident_memory",
        "value": source_ref or origin,
        "truth_state": "CONFIRMED",
        "source": source_ref or origin,
        "source_ref": source_ref or origin,
        "source_tier": "PRIMARY",
        "timestamp": observed_at,
        "ttl_seconds": ttl,
        "time_sensitive": True,
    }], now=now)
    freshness = str(assessment.get("freshness") or "UNVERIFIED")
    truth = str(assessment.get("status") or "UNKNOWN")
    if freshness != "FRESH":
        truth = "UNKNOWN" if truth == "CONFIRMED" else truth
    return {
        "origin": origin,
        "observed_at": observed_at,
        "ttl_seconds": ttl,
        "source_ref": source_ref,
        "freshness": freshness,
        "truth_state": truth,
        "time_mark_state": "UNVERIFIED" if freshness == "UNVERIFIED" or not observed_at else freshness,
    }


def _with_mark(payload: dict[str, Any], mark: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body.update(mark)
    if body.get("ttl_seconds") is None:
        body.pop("ttl_seconds", None)
    return body


def _get(mapping: Any, key: str) -> Any:
    getter = getattr(mapping, "get", None)
    if not callable(getter):
        return None
    try:
        return getter(key)
    except Exception:
        return None


def _project_runtime_snapshot(raw: Any) -> dict[str, Any] | None:
    body = _mapping(raw)
    if not body:
        return None
    inputs = _mapping(body.get("inputs"))
    fast = _mapping(inputs.get("fast_boot"))
    macro_ctx = _mapping(inputs.get("macro_context"))
    names: list[str] = []
    for pack in islice(body.get("packs") or (), 40):
        if not isinstance(pack, Mapping):
            continue
        pair = _text(pack.get("pair"), 16).upper()
        if pair in _OFFICIAL and pair not in names:
            names.append(pair)
    event = _mapping(macro_ctx.get("event"))
    macro = _mapping(fast.get("macro_eua"))
    return {
        "generated_at": body.get("generated_at") or "",
        "runtime_generated_at": body.get("runtime_generated_at") or "",
        "schema": _text(body.get("schema"), 80),
        "pair_names": names,
        "packs_observed": len(names),
        "macro_eua": macro,
        "event": event,
        "source": "runtime_snapshot",
        "fallback": True,
        "live_ready": False,
        "identity": "runtime_snapshot",
    }


def _project_matrix(raw: Any) -> dict[str, Any] | None:
    body = _mapping(raw)
    if not body:
        return None
    missing = body.get("missing_codes")
    return {
        "ready": bool(body.get("ready", False)),
        "live_ready": bool(body.get("live_ready", False)),
        "source": _text(body.get("source"), 80) or "none",
        "reason": _text(body.get("reason"), 240),
        "pairs_built": body.get("pairs_built"),
        "pairs_expected": body.get("pairs_expected"),
        "fallback_age_minutes": body.get("fallback_age_minutes"),
        "missing_codes": list(islice(missing, 16))
        if isinstance(missing, (list, tuple))
        else [],
    }


def collect_resident_specialist_inputs(
    session_state: Any = None,
    globals_map: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Copy whitelist entries already held by the caller. No remote reads."""
    loaded: dict[str, Any] = {}
    boot = _get(session_state, "atlasquant_advanced_boot")
    if isinstance(boot, Mapping):
        loaded["boot"] = {
            "state": boot.get("state"),
            "generated_at": boot.get("generated_at"),
            "runtime_generated_at": boot.get("runtime_generated_at"),
            "age_minutes": boot.get("age_minutes"),
            "refresh_status": boot.get("refresh_status"),
        }
    status = _project_matrix(_get(session_state, "atlasquant_pair_matrix_status"))
    if status is not None:
        loaded["pair_matrix_status"] = status
    checkpoint = _get(session_state, "aion_working_checkpoint_v2")
    if isinstance(checkpoint, Mapping) and checkpoint:
        loaded["checkpoint"] = checkpoint
    research = _get(session_state, "atlasquant_research_evidence_records")
    if isinstance(research, list) and research:
        loaded["research_records"] = research

    globals_map = globals_map or {}
    macro = _get(globals_map, "macro_eua")
    if isinstance(macro, Mapping) and macro:
        loaded["macro_eua"] = macro
    ranking = _get(globals_map, "ranking")
    if ranking is not None:
        loaded["ranking"] = ranking
    fed = _mapping(_get(globals_map, "fed"))
    if fed:
        loaded["fed"] = {"tom": fed.get("tom"), "forca": fed.get("forca")}
    snapshot = _project_runtime_snapshot(_get(globals_map, "_fast_snapshot"))
    if snapshot is not None:
        loaded["runtime_snapshot"] = snapshot
    matrix = _project_matrix(_get(globals_map, "_aq_pair_matrix_result"))
    if matrix is not None:
        loaded["pair_matrix_result"] = matrix
    context = _mapping(_get(globals_map, "_aq_pair_context"))
    event = _mapping(context.get("event"))
    if event:
        loaded["macro_event"] = event
    return _strip(loaded)


def _pair_ranking(value: Any) -> list[dict[str, Any]] | None:
    body = _mapping(value)
    if body and ("ranking" in body or "top_10" in body):
        value = body.get("ranking", body.get("top_10"))
    rows = _records(value)
    if not rows:
        return None
    if any(
        isinstance(row, Mapping) and ("Código" in row or "codigo" in row) and "pair" not in row
        for row in rows
    ):
        return None
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        pair = _text(row.get("pair"), 16).upper()
        if pair not in _OFFICIAL or pair in seen or row.get("data_ready") is not True:
            return None
        seen.add(pair)
        item: dict[str, Any] = {"pair": pair, "data_ready": True}
        if "score" in row or "priority" in row:
            item["score"] = row.get("score", row.get("priority"))
        cleaned.append(item)
    return cleaned or None


def _persisted_results(loaded: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    for key in ("scanner", "persisted_scanner"):
        body = _mapping(loaded.get(key))
        if not body:
            continue
        results = body.get("persisted_results", body.get("results"))
        if isinstance(results, Mapping):
            return body, dict(results)
        pair_map = {
            str(name): value
            for name, value in body.items()
            if str(name).upper() in _OFFICIAL
        }
        if pair_map:
            return body, pair_map
    results = loaded.get("persisted_results")
    if isinstance(results, Mapping):
        return _mapping(loaded), dict(results)
    return {}, {}


def _macro_indicators(macro: Mapping[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key, value in macro.items():
        name = str(key)
        if name.startswith("_") or _secret_key(name):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            body[name] = value
    return body


def _loaded_event(loaded: Mapping[str, Any], macro: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    for candidate in (
        loaded.get("macro_event"),
        macro.get("event") if isinstance(macro.get("event"), Mapping) else None,
        runtime.get("event"),
    ):
        event = _mapping(candidate)
        if event.get("disponivel") is True or event.get("available") is True:
            return event
    return {}


def _record_bundle(value: Any) -> tuple[list[dict[str, Any]] | None, str, float | None]:
    if isinstance(value, list):
        rows = [dict(item) for item in value if isinstance(item, Mapping)]
        return (rows if rows else None), "", None
    body = _mapping(value)
    rows = body.get("records", body.get("evidence_rows", body.get("rows")))
    if not isinstance(rows, list):
        return None, "", None
    cleaned = [dict(item) for item in rows if isinstance(item, Mapping)]
    if not cleaned:
        return None, "", None
    return cleaned, _clock_fields(body), _ttl(body.get("ttl_seconds"))


def _checkpoint_block(checkpoint: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        block = checkpoint.get(key)
        if isinstance(block, Mapping):
            return dict(block)
    return {}


def adapt_loaded_memory_to_specialist_snapshot(
    loaded: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize resident objects into the specialist snapshot contract."""
    if isinstance(loaded, Mapping) and loaded.get("schema") == SCHEMA and isinstance(loaded.get("slices"), Mapping):
        snapshot = build_specialist_session_snapshot(loaded, now=now)
        snapshot["network_called"] = False
        snapshot["secrets_included"] = False
        snapshot["provider_called"] = False
        return snapshot
    if not isinstance(loaded, Mapping):
        return build_specialist_session_snapshot(None, now=now)

    picked = _strip({key: loaded[key] for key in _INPUT_KEYS if key in loaded})
    boot = _mapping(picked.get("boot"))
    runtime = _mapping(picked.get("runtime_snapshot"))
    package_clock = _first_clock(
        boot.get("runtime_generated_at"),
        boot.get("generated_at"),
        runtime.get("runtime_generated_at"),
        runtime.get("generated_at"),
    )
    raw: dict[str, Any] = {"origin": "SESSION", "observed_at": ""}

    scanner_body, results = _persisted_results(picked)
    if results:
        clock = _first_clock(_clock_fields(scanner_body), package_clock)
        ttl = _ttl(scanner_body.get("ttl_seconds"))
        identity = _text(scanner_body.get("identity") or scanner_body.get("source"), 80) or "persisted_scanner"
        fallback = bool(scanner_body.get("fallback")) or identity == "runtime_snapshot"
        raw["scanner"] = _with_mark({
            "persisted_results": results,
            "conflicts": list(scanner_body.get("conflicts") or []) if isinstance(scanner_body.get("conflicts"), list) else [],
            "identity": identity,
            "source": identity,
            "fallback": fallback,
            "live_ready": bool(scanner_body.get("live_ready", False)) and not fallback,
        }, _mark("PERSISTED_SCANNER", clock, ttl, "resident_scanner", now=now))

    ranking = _pair_ranking(picked.get("radar_ranking", picked.get("ranking")))
    matrix = _mapping(picked.get("pair_matrix_result")) or _mapping(picked.get("pair_matrix_status"))
    matrix_ready = bool(matrix.get("ready", False))
    matrix_source = _text(matrix.get("source"), 80).lower() or "none"
    pair_names = [pair for pair in list(runtime.get("pair_names") or []) if pair in _OFFICIAL]
    mesh = _mapping(picked.get("source_mesh"))
    market_context = _mapping(picked.get("market_context"))
    radar_payload: dict[str, Any] | None = None
    radar_clock = ""
    radar_ttl = None
    if ranking:
        radar_body = _mapping(picked.get("radar_ranking")) or _mapping(picked.get("ranking"))
        radar_clock = _first_clock(_clock_fields(radar_body), package_clock)
        radar_ttl = _ttl(radar_body.get("ttl_seconds") if radar_body else None)
        radar_payload = {
            "ranking": ranking,
            "identity": "pair_ranking",
            "fallback": False,
            "source": "resident_ranking",
            "score_is_profit_probability": False,
        }
    elif matrix_ready or pair_names or mesh or market_context:
        if matrix_ready and matrix_source == "live":
            fallback = False
            radar_source = "live"
        elif matrix_source == "runtime_snapshot" or pair_names:
            fallback = True
            radar_source = "runtime_snapshot"
        elif mesh or market_context:
            fallback = True
            radar_source = "source_mesh"
        else:
            fallback = True
            radar_source = "resident_radar"
        radar_clock = _first_clock(_clock_fields(matrix), _clock_fields(runtime), package_clock)
        radar_payload = {
            "identity": radar_source,
            "fallback": fallback,
            "source": radar_source,
            "live_ready": bool(matrix.get("live_ready", False)) and not fallback,
            "pairs_built": matrix.get("pairs_built"),
            "pairs_expected": matrix.get("pairs_expected"),
            "pair_names": pair_names if radar_source == "runtime_snapshot" else [],
            "packs_observed": len(pair_names) if radar_source == "runtime_snapshot" else 0,
            "incomplete": bool(matrix_ready and _finite_count(matrix.get("pairs_built")) < _finite_count(matrix.get("pairs_expected") or 7)),
            "score_is_profit_probability": False,
            "market_live_confirmed": False,
            "market_state": _text(mesh.get("market_state") or market_context.get("source_mesh_state"), 80),
        }
    if radar_payload is not None:
        raw["radar"] = _with_mark(
            radar_payload,
            _mark("RADAR", radar_clock, radar_ttl, "resident_radar", now=now),
        )

    macro = _mapping(picked.get("macro_eua"))
    if not macro:
        macro = _mapping(runtime.get("macro_eua"))
    event = _loaded_event(picked, macro, runtime)
    explicit_rows = macro.get("currency_rows", macro.get("rows"))
    currency_rows = explicit_rows if isinstance(explicit_rows, list) else None
    explicit_events = macro.get("events") if isinstance(macro.get("events"), list) else None
    fed = _mapping(picked.get("fed"))
    banks = []
    if _text(fed.get("tom"), 80):
        banks.append({"bank": "Fed", "tone": _text(fed.get("tom"), 80), "source_ref": "fed"})
    if macro or event or currency_rows or explicit_events:
        clock = _first_clock(_clock_fields(macro), _clock_fields(event), package_clock)
        ttl = _ttl(macro.get("ttl_seconds"))
        payload: dict[str, Any] = {
            "identity": "macro_eua" if macro else "macro_event",
            "indicators": _macro_indicators(macro),
            "fallback_count": macro.get("_fallbacks"),
            "central_banks": banks,
            "live_calendar_consulted": False,
        }
        if isinstance(currency_rows, list):
            payload["currency_rows"] = currency_rows
        if isinstance(explicit_events, list):
            payload["events"] = explicit_events
        elif event:
            payload["events"] = [event]
        if isinstance(macro.get("conflicts"), list):
            payload["conflicts"] = macro.get("conflicts")
        raw["macro"] = _with_mark(payload, _mark("LOCAL_STATE", clock, ttl, "macro_eua", now=now))

    checkpoint = _mapping(picked.get("checkpoint"))
    research, research_clock, research_ttl = _record_bundle(picked.get("research_records"))
    if research is None:
        research, research_clock, research_ttl = _record_bundle(_checkpoint_block(checkpoint, "research"))
    evidence_rows, evidence_clock, evidence_ttl = _record_bundle(picked.get("evidence_rows"))
    lab_records, lab_clock, lab_ttl = _record_bundle(picked.get("lab_records"))
    if research:
        raw["research"] = _with_mark(
            {"records": research, "identity": "research_records"},
            _mark(
                "RESEARCH_EVIDENCE",
                _first_clock(research_clock, _record_clock(research), package_clock),
                research_ttl,
                "research_records",
                now=now,
            ),
        )
    if evidence_rows or lab_records:
        lab_observed = _first_clock(evidence_clock, lab_clock, _record_clock((evidence_rows or []) + (lab_records or [])), package_clock)
        lab_ttl_value = evidence_ttl if evidence_ttl is not None else lab_ttl
        raw["lab"] = _with_mark(
            {
                "evidence_rows": evidence_rows or [],
                "records": lab_records or [],
                "identity": "lab_records",
                "runs_backtest": False,
            },
            _mark("RESEARCH_EVIDENCE", lab_observed, lab_ttl_value, "lab_records", now=now),
        )
        if evidence_rows:
            raw["ict"] = _with_mark(
                {"evidence_rows": evidence_rows, "identity": "lab_records", "runs_backtest": False},
                _mark("RESEARCH_EVIDENCE", lab_observed, lab_ttl_value, "lab_records", now=now),
            )

    if checkpoint:
        clock = _first_clock(checkpoint.get("updated_at"), checkpoint.get("observed_at"))
        ttl = _ttl(checkpoint.get("ttl_seconds"))
        mark = _mark("CHECKPOINT", clock, ttl, "checkpoint", now=now)
        raw["checkpoint"] = _with_mark({"checkpoint": checkpoint, "identity": "checkpoint"}, mark)
        raw["admin"] = _with_mark({
            "checkpoint": checkpoint,
            "identity": "checkpoint",
            "production_inferred_from_empty": False,
        }, mark)
        business = _mapping(checkpoint.get("business"))
        business_products = business.get("products")
        top_business = _mapping(picked.get("business"))
        if "products" in top_business:
            business_products = top_business.get("products")
        if isinstance(business_products, list):
            raw["business"] = _with_mark(
                {"products": business_products, "identity": "checkpoint"},
                _mark("CHECKPOINT", clock, ttl, "checkpoint.business", now=now),
            )
        studio = _mapping(checkpoint.get("studio"))
        top_studio = _mapping(picked.get("studio"))
        studio_body = dict(studio)
        studio_body.update(top_studio)
        if "projects" in studio_body or "providers" in studio_body:
            raw["studio"] = _with_mark(
                {
                    "projects": studio_body.get("projects") if "projects" in studio_body else None,
                    "providers": studio_body.get("providers") if "providers" in studio_body else None,
                    "identity": "checkpoint",
                },
                _mark("LOCAL_STATE", clock, ttl, "checkpoint.studio", now=now),
            )
        invest = _checkpoint_block(checkpoint, "invest", "investments", "investimento")
        top_invest = _mapping(picked.get("invest"))
        records = top_invest.get("records", top_invest.get("rows", invest.get("records", invest.get("rows", invest.get("products")))))
        if isinstance(records, list):
            raw["invest"] = _with_mark(
                {"records": records, "identity": "checkpoint"},
                _mark("LOCAL_STATE", clock, ttl, "checkpoint.invest", now=now),
            )

    snapshot = build_specialist_session_snapshot(raw, now=now)
    snapshot["network_called"] = False
    snapshot["secrets_included"] = False
    snapshot["provider_called"] = False
    return snapshot


def _finite_count(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _record_clock(rows: list[Mapping[str, Any]]) -> str:
    clocks = []
    for row in rows:
        clock = _first_clock(row.get("captured_at"), row.get("executed_at"), row.get("observed_at"), row.get("updated_at"))
        if clock:
            clocks.append(clock)
    unique = set(clocks)
    if len(unique) == 1:
        return clocks[0]
    return ""


def evidence_scope_label(reading: Mapping[str, Any] | None) -> str:
    """Describe how much evidence the specialist reading actually observed."""
    obs = reading.get("observations") if isinstance(reading, Mapping) and isinstance(reading.get("observations"), Mapping) else {}
    parts: list[str] = []
    pairs = obs.get("observed_pairs")
    if isinstance(pairs, list):
        names = [
            _text(item.get("pair"), 16)
            for item in pairs
            if isinstance(item, Mapping) and item.get("pair")
        ]
        if names:
            parts.append(f"{len(pairs)} par(es) observado(s): {', '.join(names[:7])}")
        else:
            parts.append(f"{len(pairs)} par(es) observado(s)")
    ranking = obs.get("observed_ranking")
    if isinstance(ranking, list):
        parts.append(f"{len(ranking)} linha(s) de ranking")
    if obs.get("ranking_valid") is False:
        parts.append("TOP 10 não gerado")
    elif isinstance(obs.get("top_10"), list):
        parts.append(f"TOP 10 com {len(obs['top_10'])} par(es)")
    labels = (
        ("records_loaded", "registro(s) de pesquisa"),
        ("currency_rows_supplied", "linha(s) macro"),
        ("supplied_events", "evento(s) macro"),
        ("pending_in_this_call", "pendência(s) neste objeto"),
        ("recorded_setups", "setup(s) registrado(s)"),
        ("projects_supplied", "projeto(s)"),
        ("rows", "linha(s) de investimento"),
    )
    for key, label in labels:
        if key in obs and obs.get(key) is not None:
            parts.append(f"{obs.get(key)} {label}")
    if not parts:
        return "nenhum fato quantificado neste objeto"
    return " · ".join(parts)


__all__ = [
    "GLOBAL_WHITELIST",
    "SESSION_WHITELIST",
    "adapt_loaded_memory_to_specialist_snapshot",
    "collect_resident_specialist_inputs",
    "evidence_scope_label",
]
