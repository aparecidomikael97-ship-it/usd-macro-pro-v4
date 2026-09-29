"""Session snapshot already loaded for AION specialists.

Specialists may describe evidence that the caller already holds. This module
does not open the network, read secrets, hydrate remote stores, or turn a
missing input into a market, macro, or production fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core import guardian_decision
from atlasquant_aion_developer_engine import definition_of_done
from atlasquant_aion_observability import is_secret_key, redact_text
from atlasquant_aion_specialists import SPECIALIST_MODULES
from atlasquant_aion_business_adapter import business_summary as _business_summary
from atlasquant_aion_investment_adapter import investment_product_comparison as _investment_comparison
from atlasquant_aion_truth import assess_truth
from atlasquant_content_pipeline import provider_readiness
from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_lab_matrix import evidence_rows_from_research_records, lab_matrix
from atlasquant_macro_briefing import build_macro_briefing
from atlasquant_scanner_queue import scanner_queue

def _approval_inbox(checkpoint):
    from atlasquant_aion_approval_inbox import collect_approval_inbox
    return collect_approval_inbox(checkpoint)


SCHEMA = "ATLASQUANT_AION_SPECIALIST_SESSION_SNAPSHOT_V1"
EVIDENCE_SCHEMA = "ATLASQUANT_AION_SPECIALIST_EVIDENCE_V1"
INPUT_STATES = ("ABSENT", "STALE", "CONFLICTING", "VALID", "UNVERIFIED")
ORIGINS = (
    "SESSION",
    "CHECKPOINT",
    "PERSISTED_SCANNER",
    "RESEARCH_EVIDENCE",
    "RADAR",
    "LOCAL_STATE",
)
_SLICE_KEYS = (
    "scanner", "radar", "macro", "calendar", "research", "lab", "ict",
    "checkpoint", "admin", "studio", "business", "invest", "risk", "dev",
)
_SLICE_ORIGIN = {
    "scanner": "PERSISTED_SCANNER",
    "radar": "RADAR",
    "research": "RESEARCH_EVIDENCE",
    "checkpoint": "CHECKPOINT",
    "admin": "CHECKPOINT",
    "studio": "LOCAL_STATE",
    "business": "LOCAL_STATE",
    "invest": "LOCAL_STATE",
}
_PRICE_KEYS = {"price", "preco", "bid", "ask", "close", "open", "mid"}
_PROVIDER_FLAGS = (
    "transcription", "video_render", "image", "aion_voice",
    "mikael_voice", "mikael_consent",
)


def _text(value: Any, limit: int = 240) -> str:
    return " ".join(str(value or "").split())[:limit]


def _origin(value: Any, fallback: str) -> str:
    item = _text(value, 40).upper()
    return item if item in ORIGINS else fallback


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


def _is_secret_key(key: Any) -> bool:
    """Same family rule as observability. Exact names and compounds both match."""
    return is_secret_key(key)


def _strip_secrets(value: Any, depth: int = 0) -> Any:
    if depth > 24:
        return None
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            if _is_secret_key(key):
                continue
            cleaned[str(key)] = _strip_secrets(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_strip_secrets(item, depth + 1) for item in list(value)[:300]]
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(_text(value, 200))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clock_claim(origin: str, observed_at: str, ttl: float | None, value: Any) -> dict[str, Any]:
    return {
        "claim": "session_snapshot",
        "value": value,
        "truth_state": "CONFIRMED",
        "source": "specialist_session_snapshot",
        "source_ref": origin or "SESSION",
        "source_tier": "PRIMARY",
        "timestamp": observed_at,
        "ttl_seconds": ttl,
        "time_sensitive": True,
    }


def _assess(claims: list[dict[str, Any]], now: datetime | None) -> dict[str, Any]:
    return assess_truth(claims, now=now)


def _input_state(present: bool, assessment: Mapping[str, Any], conflicts: list[dict[str, Any]]) -> str:
    if not present:
        return "ABSENT"
    if conflicts or assessment.get("conflict_state") == "CONFLICT":
        return "CONFLICTING"
    if assessment.get("freshness") == "STALE" or int(assessment.get("stale_count") or 0) > 0:
        return "STALE"
    if assessment.get("status") == "CONFIRMED" and assessment.get("freshness") in {"FRESH", "NOT_APPLICABLE"}:
        return "VALID"
    return "UNVERIFIED"


def _slice_view(raw: Mapping[str, Any], key: str, parent_origin: str, parent_at: str, parent_ttl: float | None) -> dict[str, Any]:
    if key not in raw or raw.get(key) is None:
        return {
            "present": False,
            "origin": _SLICE_ORIGIN.get(key, parent_origin),
            "observed_at": "",
            "ttl_seconds": None,
            "payload": None,
        }
    payload = _strip_secrets(raw.get(key))
    body = _mapping(payload)
    origin = _origin(
        body.get("origin"),
        parent_origin if parent_origin != "SESSION" else _SLICE_ORIGIN.get(key, parent_origin),
    )
    observed_at = _text(body.get("observed_at") or parent_at, 80)
    ttl = _ttl(body.get("ttl_seconds"))
    if ttl is None:
        ttl = parent_ttl
    return {
        "present": True,
        "origin": origin,
        "observed_at": observed_at,
        "ttl_seconds": ttl,
        "payload": payload,
    }


def build_specialist_session_snapshot(
    raw: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize evidence the caller already has. `now` is accepted and ignored.

    Passing `now` keeps the builder signature aligned with the reader. The
    builder does not fetch a clock from the network.
    """
    del now
    if not isinstance(raw, Mapping):
        raw = None
    if raw is None or raw.get("schema") == SCHEMA and isinstance(raw.get("slices"), Mapping):
        if isinstance(raw, Mapping) and raw.get("schema") == SCHEMA and isinstance(raw.get("slices"), Mapping):
            sanitized = _strip_secrets(raw)
            snapshot = dict(sanitized) if isinstance(sanitized, Mapping) else {}
            snapshot["schema"] = SCHEMA
            snapshot["network_called"] = False
            snapshot["provider_called"] = False
            snapshot["secrets_included"] = False
            return snapshot
        return {
            "schema": SCHEMA,
            "present": False,
            "origin": "",
            "observed_at": "",
            "ttl_seconds": None,
            "slices": {
                key: {
                    "present": False,
                    "origin": _SLICE_ORIGIN.get(key, "SESSION"),
                    "observed_at": "",
                    "ttl_seconds": None,
                    "payload": None,
                }
                for key in _SLICE_KEYS
            },
            "network_called": False,
            "secrets_included": False,
            "provider_called": False,
        }
    parent_origin = _origin(raw.get("origin"), "SESSION")
    parent_at = _text(raw.get("observed_at"), 80)
    parent_ttl = _ttl(raw.get("ttl_seconds"))
    return {
        "schema": SCHEMA,
        "present": True,
        "origin": parent_origin,
        "observed_at": parent_at,
        "ttl_seconds": parent_ttl,
        "slices": {
            key: _slice_view(raw, key, parent_origin, parent_at, parent_ttl)
            for key in _SLICE_KEYS
        },
        "network_called": False,
        "secrets_included": False,
        "provider_called": False,
    }


def loaded_session_from_checkpoint(checkpoint: Mapping[str, Any] | None) -> dict[str, Any]:
    """Wrap a checkpoint object that is already in memory. Does not load one."""
    if not isinstance(checkpoint, Mapping):
        return build_specialist_session_snapshot(None)
    payload: dict[str, Any] = {
        "origin": "CHECKPOINT",
        "observed_at": _text(checkpoint.get("updated_at"), 80),
        "checkpoint": checkpoint,
    }
    ttl = checkpoint.get("ttl_seconds")
    if ttl is not None:
        payload["ttl_seconds"] = ttl
    business = checkpoint.get("business") if isinstance(checkpoint.get("business"), Mapping) else None
    if isinstance(business, Mapping) and "products" in business:
        payload["business"] = {
            "origin": "CHECKPOINT",
            "observed_at": payload["observed_at"],
            "products": business.get("products"),
        }
    studio = checkpoint.get("studio") if isinstance(checkpoint.get("studio"), Mapping) else None
    if isinstance(studio, Mapping) and ("projects" in studio or "providers" in studio):
        payload["studio"] = {
            "origin": "LOCAL_STATE",
            "observed_at": payload["observed_at"],
            "projects": studio.get("projects") if "projects" in studio else None,
            "providers": studio.get("providers") if "providers" in studio else None,
        }
    return build_specialist_session_snapshot(payload)


def _seal(reading: dict[str, Any]) -> dict[str, Any]:
    reading["provider_called"] = False
    reading["network_called"] = False
    reading["tool_called"] = False
    reading["executes_action"] = False
    reading["real_orders_enabled"] = False
    reading["invented_values"] = False
    reading["secrets_included"] = False
    reading["permissions_expanded"] = False
    reading["answers_user_question"] = False
    reading["snapshot_schema"] = SCHEMA
    return reading


def _envelope(
    specialist: str,
    *,
    state: str,
    summary: str,
    observations: Mapping[str, Any],
    claims: list[dict[str, Any]],
    origin: str,
    observed_at: str,
    assessment: Mapping[str, Any],
    conflicts: list[dict[str, Any]],
    input_state: str,
) -> dict[str, Any]:
    usable = input_state == "VALID" and not conflicts
    truth = str(assessment.get("status") or "UNKNOWN")
    if not usable:
        truth = "UNKNOWN"
    return _seal({
        "schema": EVIDENCE_SCHEMA,
        "specialist": specialist,
        "module": SPECIALIST_MODULES.get(specialist, ""),
        "state": state,
        "summary": summary,
        "observations": dict(observations),
        "claims": claims,
        "scope": "SESSION_SNAPSHOT",
        "origin": origin,
        "observed_at": observed_at,
        "freshness": str(assessment.get("freshness") or "UNVERIFIED"),
        "truth_state": truth,
        "input_state": input_state,
        "conflicts": conflicts,
        "conflict_state": "CONFLICT" if conflicts or assessment.get("conflict_state") == "CONFLICT" else "NONE",
        "answer_truth": truth,
        "used_as_current_fact": usable and truth == "CONFIRMED",
    })


def _absent(
    specialist: str,
    summary: str,
    observations: Mapping[str, Any] | None = None,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    parent = _mapping(snapshot)
    assessment = _assess([], None)
    return _envelope(
        specialist,
        state="SNAPSHOT_INPUT_ABSENT",
        summary=summary,
        observations=observations or {},
        claims=[],
        origin=str(parent.get("origin") or ""),
        observed_at=str(parent.get("observed_at") or ""),
        assessment=assessment,
        conflicts=[],
        input_state="ABSENT",
    )


def _explicit_conflicts(payload: Any) -> list[dict[str, Any]]:
    body = _mapping(payload)
    rows = []
    for raw in list(body.get("conflicts") or []):
        if not isinstance(raw, Mapping):
            continue
        values = list(raw.get("values") or [])
        if len(values) < 2:
            continue
        rows.append({
            "claim": _text(raw.get("claim") or "snapshot_conflict"),
            "values": values[:8],
            "chosen": None,
        })
    return rows


def _pair_signature(raw: Mapping[str, Any]) -> tuple[str, str, str]:
    technical = raw.get("tecnico") if isinstance(raw.get("tecnico"), Mapping) else {}
    parts = []
    for timeframe in ("h4", "h1", "m15"):
        block = technical.get(timeframe) if isinstance(technical.get(timeframe), Mapping) else {}
        parts.append(_text(block.get("status"), 40).upper())
    return tuple(parts)  # type: ignore[return-value]


def _scanner_bundle(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(payload, Mapping):
        return {}, []
    if isinstance(payload.get("persisted_results"), Mapping):
        results = payload.get("persisted_results")
    elif isinstance(payload.get("results"), Mapping):
        results = payload.get("results")
    else:
        results = {
            key: value for key, value in payload.items()
            if key in OFFICIAL_PAIRS
        }
    conflicts = _explicit_conflicts(payload)
    chosen: dict[str, Any] = {}
    if isinstance(results, Mapping):
        for pair in OFFICIAL_PAIRS:
            if pair not in results:
                continue
            raw = results.get(pair)
            versions = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
            if isinstance(raw, Mapping) and isinstance(raw.get("alternatives"), list):
                versions = [raw] + [item for item in raw.get("alternatives") if isinstance(item, Mapping)]
            if versions:
                signatures = {_pair_signature(item) for item in versions}
                if len(signatures) > 1:
                    conflicts.append({
                        "claim": f"scanner.{pair}.timeframe_status",
                        "values": [list(item) for item in signatures],
                        "chosen": None,
                    })
                    continue
                chosen[pair] = versions[0]
            elif isinstance(raw, Mapping):
                chosen[pair] = raw
    return chosen, conflicts


def _ranking(payload: Any) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]], bool]:
    body = _mapping(payload)
    if "ranking" not in body and "top_10" not in body:
        return None, [], False
    raw_rows = body.get("ranking", body.get("top_10"))
    if not isinstance(raw_rows, list):
        return None, [], False
    conflicts: list[dict[str, Any]] = []
    cleaned = []
    seen: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, Mapping):
            return None, conflicts, False
        pair = _text(item.get("pair"), 16).upper()
        if pair in seen:
            conflicts.append({
                "claim": f"ranking.{pair}",
                "values": ["duplicate", "duplicate"],
                "chosen": None,
            })
            return None, conflicts, False
        if pair not in OFFICIAL_PAIRS or item.get("data_ready") is not True:
            return None, conflicts, False
        seen.add(pair)
        score = item.get("score", item.get("priority"))
        if score is not None:
            try:
                score = float(score)
            except (TypeError, ValueError):
                return None, conflicts, False
            if score != score:
                return None, conflicts, False
        cleaned.append({"pair": pair, "rank": len(cleaned) + 1, "score": score})
    return cleaned, conflicts, bool(cleaned)


def _slice_is_current(slice_body: Mapping[str, Any], now: datetime | None, marker: str) -> tuple[bool, dict[str, Any]]:
    """Judge one slice with its own clock. Never borrows another slice's TTL."""
    claim = _clock_claim(
        str(slice_body.get("origin") or ""),
        str(slice_body.get("observed_at") or ""),
        slice_body.get("ttl_seconds"),
        marker,
    )
    claim["claim"] = marker
    assessment = _assess([claim], now)
    current = (
        assessment.get("status") == "CONFIRMED"
        and assessment.get("freshness") == "FRESH"
        and assessment.get("conflict_state") != "CONFLICT"
    )
    return current, assessment


def _market(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    scanner = _mapping(snapshot.get("slices")).get("scanner") or {}
    radar = _mapping(snapshot.get("slices")).get("radar") or {}
    if not scanner.get("present") and not radar.get("present"):
        return _absent(
            "market",
            "Scanner persistido e Radar não estão neste snapshot. Ausência não é cotação, "
            "preço nem TOP 10.",
            {"ranking_valid": False, "price_invented": False, "profit_probability": False},
            snapshot,
        )
    chosen, conflicts = _scanner_bundle(scanner.get("payload") if scanner.get("present") else {})
    ranking, ranking_conflicts, ranking_well_formed = _ranking(
        radar.get("payload") if radar.get("present") else scanner.get("payload")
    )
    conflicts = conflicts + ranking_conflicts
    queue = scanner_queue(chosen, now_ts=(now or datetime.now(timezone.utc)).timestamp())
    by_pair = {row["pair"]: row for row in list(queue.get("pairs") or [])}
    observed = []
    stale_pairs = []
    for pair, row in by_pair.items():
        if pair not in chosen:
            continue
        item = {
            "pair": pair,
            "queue_status": row.get("status"),
            "source": row.get("source") or "",
            "age_minutes": row.get("age_minutes"),
        }
        if row.get("status") == "FRESH":
            observed.append(item)
        else:
            stale_pairs.append({"pair": pair, "queue_status": row.get("status")})
    scanner_current = False
    radar_current = False
    scanner_assessment: dict[str, Any] = {"status": "UNKNOWN", "freshness": "UNVERIFIED", "stale_count": 0, "conflict_state": "NONE"}
    radar_assessment = dict(scanner_assessment)
    if scanner.get("present"):
        scanner_current, scanner_assessment = _slice_is_current(scanner, now, "scanner.snapshot")
    if radar.get("present"):
        radar_current, radar_assessment = _slice_is_current(radar, now, "radar.ranking")
    if not scanner_current:
        for row in observed:
            stale_pairs.append({"pair": row["pair"], "queue_status": row.get("queue_status")})
        observed = []
    ranking_clock_current = radar_current if radar.get("present") else scanner_current
    ranking_current = bool(
        ranking_well_formed and ranking and not ranking_conflicts and ranking_clock_current
    )
    scanner_usable = bool(observed) and not conflicts
    if conflicts:
        clock = scanner if scanner.get("present") else radar
        origin = str(clock.get("origin") or "")
        observed_at = str(clock.get("observed_at") or "")
        ttl = clock.get("ttl_seconds")
        claims = []
        for conflict in conflicts[:4]:
            for value in list(conflict.get("values") or [])[:2]:
                claims.append(_clock_claim(origin, observed_at, ttl, value))
                claims[-1]["claim"] = conflict["claim"]
        if len(claims) < 2:
            claims = [
                _clock_claim(origin, observed_at, ttl, "side-a"),
                _clock_claim(origin, observed_at, ttl, "side-b"),
            ]
            claims[0]["claim"] = "market.conflict"
            claims[1]["claim"] = "market.conflict"
        assessment = _assess(claims, now)
        input_state = "CONFLICTING"
    else:
        claims = []
        if scanner_usable:
            claims.append(_clock_claim(
                str(scanner.get("origin") or ""),
                str(scanner.get("observed_at") or ""),
                scanner.get("ttl_seconds"),
                {"observed_pairs": [row["pair"] for row in observed]},
            ))
            claims[-1]["claim"] = "scanner.snapshot"
        if ranking_current:
            clock = radar if radar.get("present") else scanner
            claims.append(_clock_claim(
                str(clock.get("origin") or ""),
                str(clock.get("observed_at") or ""),
                clock.get("ttl_seconds"),
                {"ranking_pairs": [row["pair"] for row in ranking or []]},
            ))
            claims[-1]["claim"] = "radar.ranking"
        if claims:
            assessment = _assess(claims, now)
            input_state = "VALID"
        elif scanner.get("present") and scanner_assessment.get("freshness") == "STALE":
            assessment = dict(scanner_assessment)
            assessment["freshness"] = "STALE"
            assessment["status"] = "UNKNOWN"
            assessment["stale_count"] = max(1, int(assessment.get("stale_count") or 0))
            input_state = "STALE"
            origin = str(scanner.get("origin") or "")
            observed_at = str(scanner.get("observed_at") or "")
        elif radar.get("present") and radar_assessment.get("freshness") == "STALE":
            assessment = dict(radar_assessment)
            assessment["freshness"] = "STALE"
            assessment["status"] = "UNKNOWN"
            assessment["stale_count"] = max(1, int(assessment.get("stale_count") or 0))
            input_state = "STALE"
            origin = str(radar.get("origin") or "")
            observed_at = str(radar.get("observed_at") or "")
        else:
            assessment = _assess([], now)
            input_state = "UNVERIFIED"
            origin = str((scanner or radar).get("origin") or "")
            observed_at = str((scanner or radar).get("observed_at") or "")
    if input_state == "VALID":
        if scanner_usable:
            origin = str(scanner.get("origin") or "")
            observed_at = str(scanner.get("observed_at") or "")
        else:
            clock = radar if radar.get("present") else scanner
            origin = str(clock.get("origin") or "")
            observed_at = str(clock.get("observed_at") or "")
    elif input_state == "CONFLICTING":
        pass
    top_10 = [row["pair"] for row in ranking] if ranking_current and ranking and len(ranking) == 10 else None
    observations: dict[str, Any] = {
        "observed_pairs": observed if input_state == "VALID" and scanner_usable else [],
        "not_current_pairs": stale_pairs,
        "pairs_absent_from_snapshot": len(OFFICIAL_PAIRS) - len(chosen),
        "absence_is_not_a_market_fact": True,
        "ranking_valid": bool(top_10) and input_state == "VALID",
        "price_invented": False,
        "profit_probability": False,
        "score_is_profit_probability": False,
        "live_feed_consulted": False,
        "scanner_clock_current": bool(scanner_current),
        "radar_clock_current": bool(radar_current),
    }
    if input_state == "VALID" and ranking_current:
        observations["observed_ranking"] = ranking
    if top_10 and input_state == "VALID":
        observations["top_10"] = top_10
    if input_state == "STALE":
        summary = (
            "O scanner fornecido está stale. O conteúdo não foi usado como fato atual "
            "e nenhum preço foi inventado."
        )
    elif input_state == "CONFLICTING":
        summary = (
            "O snapshot de mercado contém leituras conflitantes. Nenhum lado foi escolhido "
            "e nenhum TOP 10 foi criado a partir do conflito."
        )
    elif input_state == "VALID" and scanner_usable:
        summary = (
            f"Scanner observado: {len(observed)} par(es) fresco(s) no conteúdo já carregado. "
            "Isto descreve o registro; não é preço nem probabilidade de lucro."
        )
    elif input_state == "VALID":
        summary = (
            "Ranking do Radar observado com o relógio do próprio Radar. "
            "Isto não é preço nem probabilidade de lucro."
        )
    else:
        summary = (
            "O snapshot de mercado não contém leitura fresca utilizável. "
            "Ausência ou incompletude não vira cotação nem TOP 10."
        )
    return _envelope(
        "market",
        state=input_state,
        summary=summary,
        observations=observations,
        claims=claims if input_state == "VALID" else [],
        origin=origin,
        observed_at=observed_at,
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state,
    )


def _macro_rows(payload: Any) -> list[dict[str, Any]]:
    body = _mapping(payload)
    rows = body.get("currency_rows", body.get("rows", []))
    return [dict(row) for row in list(rows or []) if isinstance(row, Mapping)]


def _macro_events(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    slices = _mapping(snapshot.get("slices"))
    events = []
    for key in ("macro", "calendar"):
        view = _mapping(slices.get(key))
        if not view.get("present"):
            continue
        body = _mapping(view.get("payload"))
        raw_events = body.get("events", body if key == "calendar" and isinstance(view.get("payload"), list) else [])
        if key == "calendar" and isinstance(view.get("payload"), list):
            raw_events = view.get("payload")
        for item in list(raw_events or []):
            if isinstance(item, Mapping):
                events.append(dict(item))
    return events


def _macro_conflicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, Any] = {}
    conflicts = []
    for row in rows:
        if row.get("stale") is True or row.get("data_ready") is False:
            continue
        code = _text(row.get("currency") or row.get("symbol"), 12).upper()
        if not code:
            continue
        score = row.get("score", row.get("strength"))
        if code in seen and seen[code] != score:
            conflicts.append({
                "claim": f"macro.{code}.score",
                "values": [seen[code], score],
                "chosen": None,
            })
        else:
            seen[code] = score
    return conflicts


def _macro(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    slices = _mapping(snapshot.get("slices"))
    macro = _mapping(slices.get("macro"))
    calendar = _mapping(slices.get("calendar"))
    if not macro.get("present") and not calendar.get("present"):
        briefing = build_macro_briefing(None)
        return _absent(
            "macro",
            "Nenhuma linha ou evento macro foi fornecido neste snapshot.",
            {"state": briefing["state"], "data_sufficient": False, "live_calendar_consulted": False},
            snapshot,
        )
    active = macro if macro.get("present") else calendar
    origin = str(active.get("origin") or "SESSION")
    observed_at = str(active.get("observed_at") or "")
    ttl = active.get("ttl_seconds")
    rows = _macro_rows(macro.get("payload")) if macro.get("present") else []
    events = _macro_events(snapshot)
    banks = []
    if macro.get("present"):
        for item in list(_mapping(macro.get("payload")).get("central_banks") or []):
            if isinstance(item, Mapping):
                banks.append(dict(item))
    conflicts = _macro_conflicts(rows) + _explicit_conflicts(macro.get("payload"))
    row_stale = bool(rows) and all(item.get("stale") is True or item.get("data_ready") is False for item in rows)
    if conflicts:
        claims = []
        for conflict in conflicts[:2]:
            for value in list(conflict.get("values") or [])[:2]:
                claim = _clock_claim(origin, observed_at, ttl, value)
                claim["claim"] = conflict["claim"]
                claims.append(claim)
        assessment = _assess(claims or [_clock_claim(origin, observed_at, ttl, "conflict")], now)
        return _envelope(
            "macro",
            state="CONFLICTING",
            summary=(
                "As linhas macro fornecidas divergem. Nenhum lado foi escolhido e o "
                "briefing permanece em DADOS INSUFICIENTES."
            ),
            observations={
                "state": "DADOS INSUFICIENTES",
                "data_sufficient": False,
                "live_calendar_consulted": False,
                "supplied_events": len(events),
            },
            claims=[],
            origin=origin,
            observed_at=observed_at,
            assessment=assessment,
            conflicts=conflicts,
            input_state="CONFLICTING",
        )
    briefing = build_macro_briefing(rows, events, banks, generated_at=observed_at or None)
    claim = _clock_claim(origin, observed_at, ttl, briefing.get("state"))
    assessment = _assess([claim], now)
    input_state = _input_state(True, assessment, [])
    if row_stale:
        input_state = "STALE"
        assessment = dict(assessment)
        assessment["freshness"] = "STALE"
        assessment["status"] = "UNKNOWN"
    sufficient = bool(briefing.get("data_sufficient")) and input_state == "VALID"
    if not sufficient and input_state == "VALID":
        input_state = "UNVERIFIED"
    if input_state == "STALE":
        summary = "Snapshot macro stale. Não foi usado como fato atual."
        state = "DADOS INSUFICIENTES"
    elif sufficient:
        summary = str(briefing.get("summary") or "")
        state = str(briefing.get("state") or "DADOS INSUFICIENTES")
    else:
        summary = "As linhas e eventos já fornecidos não bastam para um briefing macro."
        state = "DADOS INSUFICIENTES"
    return _envelope(
        "macro",
        state=state,
        summary=summary,
        observations={
            "state": state,
            "data_sufficient": sufficient,
            "currency_rows_supplied": len(rows),
            "supplied_events": len(events),
            "live_calendar_consulted": False,
        },
        claims=[claim] if sufficient else [],
        origin=origin,
        observed_at=observed_at,
        assessment=assessment,
        conflicts=[],
        input_state=input_state if sufficient or input_state in {"STALE", "CONFLICTING"} else "UNVERIFIED",
    )


def _evidence_rows(snapshot: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slices = _mapping(snapshot.get("slices"))
    for key in ("ict", "lab", "research"):
        view = _mapping(slices.get(key))
        if view.get("present"):
            return view, _rows_from_slice(view.get("payload"))
    return {}, []


def _rows_from_slice(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = [item for item in payload if isinstance(item, Mapping)]
        adapted = evidence_rows_from_research_records(records)
        return adapted or [dict(item) for item in records]
    body = _mapping(payload)
    if isinstance(body.get("evidence_rows"), list):
        return [dict(item) for item in body.get("evidence_rows") if isinstance(item, Mapping)]
    if isinstance(body.get("records"), list):
        records = [item for item in body.get("records") if isinstance(item, Mapping)]
        return evidence_rows_from_research_records(records) or [dict(item) for item in records]
    return []


def _ict(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view, rows = _evidence_rows(snapshot)
    matrix = lab_matrix(rows)
    blocked = sorted({
        str(cell.get("setup_id"))
        for cell in list(matrix.get("cells") or [])
        if cell.get("state") == "BLOQUEADO"
    })
    counts = dict(matrix.get("counts") or {})
    if not view:
        return _absent(
            "ict",
            "Nenhum backtest registrado foi fornecido neste snapshot. PPR permanece BLOQUEADO.",
            {
                "counts": counts,
                "blocked_setups": blocked,
                "ppr_blocked": "ppr" in blocked,
                "runs_backtest": False,
                "fabricated_values": False,
            },
            snapshot,
        )
    origin = str(view.get("origin") or "SESSION")
    observed_at = str(view.get("observed_at") or "")
    recorded = int(counts.get("EVIDENCIA_REGISTRADA") or 0)
    claim = _clock_claim(origin, observed_at, view.get("ttl_seconds"), recorded)
    assessment = _assess([claim], now)
    conflicts = _explicit_conflicts(view.get("payload"))
    input_state = _input_state(True, assessment, conflicts)
    usable = input_state == "VALID" and recorded > 0 and not conflicts
    if input_state == "VALID" and not usable:
        input_state = "UNVERIFIED"
    summary = (
        "Evidência de laboratório já registrada foi lida. PPR permanece BLOQUEADO "
        "enquanto a definição objetiva não estiver confirmada."
        if usable else
        "A evidência ICT/backtest fornecida não foi usada como fato atual. PPR permanece BLOQUEADO."
        if input_state in {"STALE", "CONFLICTING"} else
        "Não há evidência registrada utilizável neste snapshot. PPR permanece BLOQUEADO."
    )
    return _envelope(
        "ict",
        state=input_state,
        summary=summary,
        observations={
            "counts": counts if usable or input_state != "STALE" else {"EVIDENCIA_REGISTRADA": 0},
            "blocked_setups": blocked,
            "ppr_blocked": "ppr" in blocked,
            "recorded_setups": recorded if usable else 0,
            "runs_backtest": False,
            "fabricated_values": False,
            "real_orders_enabled": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=observed_at,
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state,
    )


def _research(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("research"))
    if not view.get("present"):
        return _absent(
            "research",
            "Evidência de pesquisa não está carregada neste snapshot. Busca web e modelo externo não foram chamados.",
            {"records_loaded": 0, "web_research_executed": False, "external_model_executed": False},
            snapshot,
        )
    payload = view.get("payload")
    records = payload if isinstance(payload, list) else list(_mapping(payload).get("records") or [])
    records = [item for item in records if isinstance(item, Mapping)]
    origin = str(view.get("origin") or "RESEARCH_EVIDENCE")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), len(records))
    assessment = _assess([claim], now)
    conflicts = _explicit_conflicts(payload)
    input_state = _input_state(True, assessment, conflicts)
    usable = input_state == "VALID" and not conflicts
    strategies = sorted({_text(item.get("strategy"), 80) for item in records if item.get("strategy")})
    return _envelope(
        "research",
        state=input_state,
        summary=(
            f"Evidência de pesquisa já carregada: {len(records)} registro(s). "
            "Nenhuma busca web ou modelo externo foi executado."
            if usable else
            "A evidência de pesquisa fornecida não foi usada como fato atual."
        ),
        observations={
            "records_loaded": len(records) if usable else 0,
            "strategies": strategies if usable else [],
            "web_research_executed": False,
            "external_model_executed": False,
            "remote_store_consulted": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state,
    )


def _admin(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    slices = _mapping(snapshot.get("slices"))
    view = _mapping(slices.get("admin"))
    if not view.get("present"):
        view = _mapping(slices.get("checkpoint"))
    if not view.get("present"):
        inbox = _approval_inbox(None)
        return _absent(
            "admin",
            "Nenhum checkpoint ou inbox foi fornecido à sessão. Isso não afirma que a produção está vazia.",
            {
                "pending_in_this_call": inbox["total"],
                "checkpoint_supplied": False,
                "production_inferred_from_empty": False,
                "automatic_approval": False,
            },
            snapshot,
        )
    payload = view.get("payload")
    body = _mapping(payload)
    if body.get("schema") == "ATLASQUANT_AION_APPROVAL_INBOX_V1":
        inbox = body
    else:
        checkpoint = body.get("checkpoint") if isinstance(body.get("checkpoint"), Mapping) else body
        inbox = _approval_inbox(checkpoint if isinstance(checkpoint, Mapping) else None)
    origin = str(view.get("origin") or "CHECKPOINT")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), inbox.get("total"))
    assessment = _assess([claim], now)
    conflicts = _explicit_conflicts(payload)
    input_state = _input_state(True, assessment, conflicts)
    total = int(inbox.get("total") or 0)
    usable = input_state == "VALID" and not conflicts
    return _envelope(
        "admin",
        state=input_state,
        summary=(
            f"Checkpoint fornecido à sessão contém {total} pendência(s) neste objeto. "
            "Isso não infere que a produção esteja vazia."
            if usable else
            "Checkpoint fornecido, mas não foi usado como fato atual de produção. "
            "Estrutura vazia não autoriza essa inferência."
        ),
        observations={
            "pending_in_this_call": total if usable else 0,
            "checkpoint_supplied": True,
            "production_inferred_from_empty": False,
            "automatic_approval": False,
            "real_orders_enabled": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state,
    )


def _studio(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("studio"))
    if not view.get("present"):
        return _absent(
            "studio",
            "Estado local de Studio não foi fornecido. Ausência não significa provedor desconfigurado.",
            {"providers_inferred": False, "publishing_executed": False},
            snapshot,
        )
    body = _mapping(view.get("payload"))
    providers = body.get("providers") if isinstance(body.get("providers"), Mapping) else {}
    described = {}
    if providers and set(_PROVIDER_FLAGS).issubset(set(providers)):
        ready = provider_readiness(
            transcription=bool(providers.get("transcription")),
            video_render=bool(providers.get("video_render")),
            image=bool(providers.get("image")),
            aion_voice=bool(providers.get("aion_voice")),
            mikael_voice=bool(providers.get("mikael_voice")),
            mikael_consent=bool(providers.get("mikael_consent")),
        )
        described = {name: row.get("state") for name, row in dict(ready.get("providers") or {}).items()}
    else:
        for name in _PROVIDER_FLAGS:
            if name in providers:
                described[name] = "CONFIGURED" if bool(providers.get(name)) else "NOT_CONFIGURED"
    projects = body.get("projects") if isinstance(body.get("projects"), list) else None
    origin = str(view.get("origin") or "LOCAL_STATE")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), described or projects)
    assessment = _assess([claim], now)
    input_state = _input_state(True, assessment, _explicit_conflicts(body))
    usable = input_state == "VALID" and (described or projects is not None)
    if input_state == "VALID" and not usable:
        input_state = "UNVERIFIED"
    return _envelope(
        "studio",
        state=input_state,
        summary=(
            "Estado local de Studio já fornecido foi lido. Nenhuma mídia foi gerada."
            if usable else
            "Estado de Studio não foi usado como fato atual."
        ),
        observations={
            "providers": described if usable else {},
            "projects_supplied": None if projects is None or not usable else len(projects),
            "providers_inferred": False,
            "publishing_executed": False,
            "executes_external_call": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=_explicit_conflicts(body),
        input_state=input_state,
    )


def _business(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("business"))
    if not view.get("present"):
        return _absent(
            "business",
            "Catálogo local de negócios não foi fornecido. Ausência não afirma produção vazia.",
            {"catalog_supplied": False, "production_inferred_from_empty": False, "publication_executed": False},
            snapshot,
        )
    body = _mapping(view.get("payload"))
    products = body.get("products") if "products" in body else body.get("rows")
    summary = _business_summary(products if isinstance(products, list) else None)
    origin = str(view.get("origin") or "LOCAL_STATE")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), summary.get("total"))
    assessment = _assess([claim], now)
    input_state = _input_state(True, assessment, _explicit_conflicts(body))
    usable = input_state == "VALID" and isinstance(products, list) and len(products) > 0
    if isinstance(products, list) and len(products) == 0:
        usable = False
        if input_state == "VALID":
            input_state = "UNVERIFIED"
    return _envelope(
        "business",
        state=input_state,
        summary=(
            f"Catálogo local fornecido: {summary['total']} produto(s) neste objeto. "
            "Publicação não foi executada."
            if usable else
            "O objeto de negócios fornecido não autoriza inferir produção vazia nem publicar."
        ),
        observations={
            "total": summary["total"] if usable else 0,
            "live": summary["live"] if usable else 0,
            "catalog_supplied": isinstance(products, list),
            "production_inferred_from_empty": False,
            "publication_executed": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=_explicit_conflicts(body),
        input_state=input_state,
    )


def _invest(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("invest"))
    if not view.get("present"):
        return _absent(
            "invest",
            "Nenhum produto de investimento foi fornecido neste snapshot.",
            {"rows": 0, "personalized_recommendation": False, "automatic_orders": False},
            snapshot,
        )
    body = _mapping(view.get("payload"))
    records = body.get("records", body.get("rows"))
    comparison = _investment_comparison(records if isinstance(records, list) else None)
    origin = str(view.get("origin") or "LOCAL_STATE")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), comparison.get("state"))
    assessment = _assess([claim], now)
    input_state = _input_state(True, assessment, _explicit_conflicts(body))
    usable = input_state == "VALID" and comparison.get("state") == "CONFIRMADO"
    if input_state == "VALID" and not usable:
        input_state = "UNVERIFIED"
    return _envelope(
        "invest",
        state=input_state,
        summary=(
            "Comparação limitada aos produtos já fornecidos. Sem recomendação personalizada."
            if usable else
            "Os produtos fornecidos não formam uma comparação confirmada e não foram estimados."
        ),
        observations={
            "state": comparison["state"],
            "rows": len(list(comparison.get("rows") or [])),
            "personalized_recommendation": False,
            "automatic_orders": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=_explicit_conflicts(body),
        input_state=input_state,
    )


def _risk(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("risk"))
    if not view.get("present"):
        return _absent(
            "risk",
            "Nenhum incidente ou postura foi fornecida neste snapshot. Isso não confirma um incidente.",
            {"incident_confirmed": False, "posture_inferred": False, "automatic_cutoff": False},
            snapshot,
        )
    body = _mapping(view.get("payload"))
    origin = str(view.get("origin") or "SESSION")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), body.get("state"))
    assessment = _assess([claim], now)
    conflicts = _explicit_conflicts(body)
    input_state = _input_state(True, assessment, conflicts)
    usable = input_state == "VALID" and not conflicts and bool(_text(body.get("state")))
    return _envelope(
        "risk",
        state=input_state,
        summary=(
            f"Postura fornecida à sessão: {_text(body.get('state'), 80)}. Não é ordem nem corte automático."
            if usable else
            "A postura de risco fornecida não foi usada como fato atual."
        ),
        observations={
            "posture": _text(body.get("state"), 80) if usable else "",
            "incident_confirmed": bool(body.get("incident_confirmed")) if usable else False,
            "posture_inferred": False,
            "automatic_cutoff": False,
            "real_orders_enabled": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state if usable or input_state != "VALID" else "UNVERIFIED",
    )


def _dev(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    view = _mapping(_mapping(snapshot.get("slices")).get("dev"))
    if not view.get("present"):
        return _absent(
            "dev",
            "Nenhum workflow de desenvolvimento foi fornecido. Ausência não é um estado de release.",
            {
                "workflow_supplied": False,
                "release_status_inferred": False,
                "automatic_merge": False,
                "automatic_deploy": False,
                "repository_mutated": False,
            },
            snapshot,
        )
    body = _mapping(view.get("payload"))
    workflow = body.get("workflow") if isinstance(body.get("workflow"), Mapping) else body
    done = definition_of_done(workflow)
    origin = str(view.get("origin") or "SESSION")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), done.get("status"))
    assessment = _assess([claim], now)
    input_state = _input_state(True, assessment, _explicit_conflicts(body))
    usable = input_state == "VALID"
    return _envelope(
        "dev",
        state=input_state,
        summary=(
            f"Workflow fornecido permanece {done['status']}. Merge e deploy automáticos continuam desligados."
            if usable else
            "O workflow fornecido não foi usado como fato atual. Merge e deploy continuam desligados."
        ),
        observations={
            "status": done["status"] if usable else "",
            "workflow_supplied": True,
            "release_status_inferred": False,
            "automatic_merge": False,
            "automatic_deploy": False,
            "production_change_allowed": False,
            "real_trading_enabled": False,
            "repository_mutated": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=_explicit_conflicts(body),
        input_state=input_state,
    )


def _lab(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    slices = _mapping(snapshot.get("slices"))
    view = _mapping(slices.get("lab"))
    if not view.get("present"):
        view = _mapping(slices.get("research"))
    if not view.get("present"):
        matrix = lab_matrix(None)
        blocked = sorted({
            str(cell.get("setup_id"))
            for cell in list(matrix.get("cells") or [])
            if cell.get("state") == "BLOQUEADO"
        })
        return _absent(
            "lab",
            "Evidência de laboratório não está carregada neste snapshot. A rede não foi chamada.",
            {
                "remote_store_consulted": False,
                "records_loaded": 0,
                "ppr_blocked": "ppr" in blocked,
                "runs_backtest": False,
            },
            snapshot,
        )
    rows = _rows_from_slice(view.get("payload"))
    matrix = lab_matrix(rows)
    blocked = sorted({
        str(cell.get("setup_id"))
        for cell in list(matrix.get("cells") or [])
        if cell.get("state") == "BLOQUEADO"
    })
    origin = str(view.get("origin") or "RESEARCH_EVIDENCE")
    claim = _clock_claim(origin, str(view.get("observed_at") or ""), view.get("ttl_seconds"), len(rows))
    assessment = _assess([claim], now)
    conflicts = _explicit_conflicts(view.get("payload"))
    input_state = _input_state(True, assessment, conflicts)
    usable = input_state == "VALID" and bool(rows) and not conflicts
    if input_state == "VALID" and not usable:
        input_state = "UNVERIFIED"
    return _envelope(
        "lab",
        state=input_state,
        summary=(
            "Evidência de pesquisa já carregada foi lida localmente. PPR permanece BLOQUEADO "
            "e a rede não foi chamada."
            if usable else
            "A evidência de laboratório fornecida não foi usada como fato atual. A rede não foi chamada."
        ),
        observations={
            "remote_store_consulted": False,
            "records_loaded": len(rows) if usable else 0,
            "ppr_blocked": "ppr" in blocked,
            "blocked_setups": blocked,
            "runs_backtest": False,
            "web_research_executed": False,
        },
        claims=[claim] if usable else [],
        origin=origin,
        observed_at=str(view.get("observed_at") or ""),
        assessment=assessment,
        conflicts=conflicts,
        input_state=input_state,
    )


def _core(snapshot: Mapping[str, Any], now: datetime | None) -> dict[str, Any]:
    del now
    denied = guardian_decision("real_trade", {"role": "ADMIN"}, approved=True)
    assessment = _assess([{
        "claim": "real_trade_guardian",
        "value": "DENIED",
        "truth_state": "CONFIRMED",
        "source": "atlasquant_aion_core.guardian_decision",
        "source_ref": "real_trade",
        "source_tier": "PRIMARY",
        "time_sensitive": False,
    }], None)
    return _envelope(
        "core",
        state="GUARDIAN_CONTRACT",
        summary=(
            "Guardian nega real_trade mesmo com papel ADMIN, aprovação e snapshot de sessão. "
            f"Motivo: {denied['reason']} Nenhum especialista recebe permissão própria."
        ),
        observations={
            "real_trade_allowed": bool(denied["allowed"]),
            "risk": denied["risk"],
            "approved_flag_ignored_for_real_trade": True,
            "real_orders_enabled": False,
            "permissions_expanded": False,
        },
        claims=[{
            "claim": "real_trade_guardian",
            "value": "DENIED",
            "truth_state": "CONFIRMED",
            "source": "atlasquant_aion_core.guardian_decision",
            "source_ref": "real_trade",
            "source_tier": "PRIMARY",
            "time_sensitive": False,
        }],
        origin=str(_mapping(snapshot).get("origin") or "SESSION"),
        observed_at=str(_mapping(snapshot).get("observed_at") or ""),
        assessment=assessment,
        conflicts=[],
        input_state="VALID",
    )


_READERS = {
    "core": _core,
    "dev": _dev,
    "research": _research,
    "market": _market,
    "macro": _macro,
    "ict": _ict,
    "risk": _risk,
    "lab": _lab,
    "invest": _invest,
    "business": _business,
    "studio": _studio,
    "admin": _admin,
}


def read_loaded_specialist_snapshot(
    specialist: Any,
    session: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read one specialist from an already loaded snapshot."""
    snapshot = build_specialist_session_snapshot(session, now=now)
    if not snapshot.get("present"):
        return _absent(
            str(specialist or "").strip().lower(),
            "Snapshot de sessão ausente. A resposta permanece UNKNOWN.",
        )
    key = str(specialist or "").strip().lower()
    reader = _READERS.get(key)
    if reader is None:
        return _absent(key, "Especialista não registrado. Nenhuma evidência foi inventada.")
    reading = reader(snapshot, now)
    reading["specialist"] = key
    return _seal(reading)


__all__ = [
    "SCHEMA",
    "EVIDENCE_SCHEMA",
    "INPUT_STATES",
    "ORIGINS",
    "build_specialist_session_snapshot",
    "loaded_session_from_checkpoint",
    "read_loaded_specialist_snapshot",
]
