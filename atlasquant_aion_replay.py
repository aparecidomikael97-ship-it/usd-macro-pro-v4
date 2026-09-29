"""AION Replay Mode V1 — point-in-time training contract.

Replay is a training/review surface only. It reconstructs the information set
that can be proven to have been available at a historical cutoff and masks
anything that became available later.

The contract is intentionally fail-closed:
- `available_at` governs whether evidence was knowable at the replay cutoff;
- future revisions are masked even when they describe an older observation;
- missing/invalid availability is never treated as visible evidence;
- later revisions do not overwrite the version that was actually knowable then;
- outcomes are hidden until a decision is recorded and the outcome itself has
  become available;
- no broker order, live score mutation, feature change, deployment, publication,
  billing, entitlement change or automatic setup promotion can occur here.

This module is pure/offline and performs no network or persistence I/O.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math
import re


SCHEMA = "ATLASQUANT_AION_REPLAY_MODE_V1"

REPLAY_MODES = (
    "GENERAL",
    "DECISION_REVIEW",
    "MARKET_REPLAY",
    "NEWS_REPLAY",
)
FRAME_STATES = ("VERIFIED", "PARTIAL", "EMPTY", "BLOCKED")
SESSION_STATES = ("ACTIVE", "DECISION_RECORDED", "REVEALED", "BLOCKED")
TRUTH_STATES = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")

MAX_RECORDS = 1000
MAX_COLLECTION = 200
MAX_DEPTH = 6
MAX_TEXT = 4000
MAX_PAYLOAD_JSON = 100_000

_SECRET_KEYS = frozenset({
    "secret",
    "token",
    "password",
    "credential",
    "credentials",
    "api_key",
    "apikey",
    "api_token",
    "access_token",
    "auth_token",
    "private_key",
})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(api[_ -]?key|token|password|secret|credential)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{6,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _clean(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _truth(value: Any) -> str:
    raw = _clean(value, 40).upper()
    return raw if raw in TRUTH_STATES else "UNKNOWN"


def _mode(value: Any) -> str:
    raw = _clean(value, 40).upper()
    return raw if raw in REPLAY_MODES else "GENERAL"


def _secret_key(value: Any) -> bool:
    raw = _clean(value, 120).lower().replace("-", "_").replace(" ", "_")
    return raw in _SECRET_KEYS


def _contains_secret(value: Any, depth: int = 0) -> bool:
    if depth > MAX_DEPTH:
        return False
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)
    if isinstance(value, Mapping):
        for key, item in list(value.items())[:MAX_COLLECTION]:
            if _secret_key(key) or _contains_secret(item, depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(
            _contains_secret(item, depth + 1)
            for item in list(value)[:MAX_COLLECTION]
        )
    return False


def _canonical(value: Any, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        raise ValueError("PAYLOAD_TOO_DEEP")
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            return _clean(value, MAX_TEXT)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_NUMBER")
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_COLLECTION:
            raise ValueError("COLLECTION_TOO_LARGE")
        out: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            name = _clean(str(key), 180)
            if not name:
                raise ValueError("EMPTY_PAYLOAD_KEY")
            out[name] = _canonical(value[key], depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_COLLECTION:
            raise ValueError("COLLECTION_TOO_LARGE")
        return [_canonical(item, depth + 1) for item in value]
    raise ValueError("UNSUPPORTED_PAYLOAD_TYPE")


def _stable_digest(payload: Any, *, length: int = 24) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:length]


def _force_training_safety(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(dict(payload or {}))
    out["training_only"] = True
    out["live_data_used"] = False
    out["future_evidence_exposed"] = False
    out["automatic_promotion"] = False
    out["execution_authorized"] = False
    out["executes_action"] = False
    out["real_trading_enabled"] = False
    return out


def _safe_record_metadata(
    *,
    record_id: str,
    knowledge_key: str,
    source: str,
    available_at: datetime | None,
    state: str,
    reason: str = "",
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "knowledge_key": knowledge_key,
        "source": source,
        "available_at": _iso(available_at),
        "state": state,
        "reason": reason,
    }


def _normalize_visible_record(
    raw: Mapping[str, Any],
    *,
    available_at: datetime,
    observed_at: datetime | None,
) -> dict[str, Any]:
    record_id = _clean(raw.get("record_id"), 120)
    knowledge_key = _clean(raw.get("knowledge_key"), 180) or record_id
    source = _clean(raw.get("source"), 180)
    payload = _canonical(raw.get("payload", {}))
    payload_size = len(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if payload_size > MAX_PAYLOAD_JSON:
        raise ValueError("PAYLOAD_TOO_LARGE")
    return {
        "record_id": record_id,
        "knowledge_key": knowledge_key,
        "kind": _clean(raw.get("kind"), 80),
        "label": _clean(raw.get("label"), 240),
        "source": source,
        "truth_state": _truth(raw.get("truth_state")),
        "observed_at": _iso(observed_at),
        "available_at": _iso(available_at),
        "payload": payload,
    }


def build_replay_frame(
    records: Sequence[Mapping[str, Any]] | None,
    *,
    replay_at: Any,
) -> dict[str, Any]:
    """Build the exact evidence frame knowable at `replay_at`.

    Future record content is never returned. Only safe metadata is exposed for
    masked/invalid rows so the training surface cannot leak later information.
    """
    cutoff = _utc(replay_at)
    if cutoff is None:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "REPLAY_AT_INVALID",
            "replay_at": "",
            "visible_records": [],
            "masked_records": [],
            "invalid_records": [],
            "counts": {
                "input": 0,
                "visible": 0,
                "future_masked": 0,
                "unknown_availability": 0,
                "invalid": 0,
                "superseded": 0,
            },
            "frame_digest": "",
            "point_in_time_verified": False,
            "future_evidence_exposed": False,
            "training_only": True,
            "executes_action": False,
            "real_trading_enabled": False,
        }

    rows = list(records or [])
    if len(rows) > MAX_RECORDS:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "TOO_MANY_RECORDS",
            "replay_at": _iso(cutoff),
            "visible_records": [],
            "masked_records": [],
            "invalid_records": [],
            "counts": {
                "input": len(rows),
                "visible": 0,
                "future_masked": 0,
                "unknown_availability": 0,
                "invalid": 0,
                "superseded": 0,
            },
            "frame_digest": "",
            "point_in_time_verified": False,
            "future_evidence_exposed": False,
            "training_only": True,
            "executes_action": False,
            "real_trading_enabled": False,
        }

    seen_ids: set[str] = set()
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    masked: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    unknown_availability = 0

    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            invalid.append({
                "index": index,
                "state": "INVALID",
                "reason": "RECORD_NOT_MAPPING",
            })
            continue

        if _contains_secret(raw):
            return {
                "schema": SCHEMA,
                "state": "BLOCKED",
                "reason": "SECRET_MATERIAL_REJECTED",
                "replay_at": _iso(cutoff),
                "visible_records": [],
                "masked_records": [],
                "invalid_records": [],
                "counts": {
                    "input": len(rows),
                    "visible": 0,
                    "future_masked": 0,
                    "unknown_availability": 0,
                    "invalid": 0,
                    "superseded": 0,
                },
                "frame_digest": "",
                "point_in_time_verified": False,
                "future_evidence_exposed": False,
                "training_only": True,
                "executes_action": False,
                "real_trading_enabled": False,
            }

        record_id = _clean(raw.get("record_id"), 120)
        knowledge_key = _clean(raw.get("knowledge_key"), 180) or record_id
        source = _clean(raw.get("source"), 180)
        if not record_id or not knowledge_key or not source:
            invalid.append({
                "index": index,
                "record_id": record_id,
                "state": "INVALID",
                "reason": "IDENTITY_OR_SOURCE_REQUIRED",
            })
            continue
        if record_id in seen_ids:
            invalid.append({
                "index": index,
                "record_id": record_id,
                "state": "INVALID",
                "reason": "DUPLICATE_RECORD_ID",
            })
            continue
        seen_ids.add(record_id)

        if "available_at" not in raw or raw.get("available_at") in (None, ""):
            unknown_availability += 1
            masked.append(
                _safe_record_metadata(
                    record_id=record_id,
                    knowledge_key=knowledge_key,
                    source=source,
                    available_at=None,
                    state="UNKNOWN_AVAILABILITY",
                    reason="AVAILABLE_AT_REQUIRED",
                )
            )
            continue

        available = _utc(raw.get("available_at"))
        if available is None:
            invalid.append({
                "index": index,
                "record_id": record_id,
                "state": "INVALID",
                "reason": "AVAILABLE_AT_INVALID",
            })
            continue

        observed = None
        if raw.get("observed_at") not in (None, ""):
            observed = _utc(raw.get("observed_at"))
            if observed is None:
                invalid.append({
                    "index": index,
                    "record_id": record_id,
                    "state": "INVALID",
                    "reason": "OBSERVED_AT_INVALID",
                })
                continue

        if available > cutoff:
            masked.append(
                _safe_record_metadata(
                    record_id=record_id,
                    knowledge_key=knowledge_key,
                    source=source,
                    available_at=available,
                    state="FUTURE_MASKED",
                    reason="NOT_YET_AVAILABLE_AT_REPLAY",
                )
            )
            continue

        try:
            normalized = _normalize_visible_record(
                raw,
                available_at=available,
                observed_at=observed,
            )
        except ValueError as exc:
            invalid.append({
                "index": index,
                "record_id": record_id,
                "state": "INVALID",
                "reason": str(exc),
            })
            continue
        candidates.append((available, normalized))

    latest_by_key: dict[str, tuple[datetime, dict[str, Any]]] = {}
    superseded = 0
    for available, item in sorted(
        candidates,
        key=lambda pair: (
            pair[1]["knowledge_key"],
            pair[0],
            pair[1]["record_id"],
        ),
    ):
        key = item["knowledge_key"]
        if key in latest_by_key:
            superseded += 1
        latest_by_key[key] = (available, item)

    visible = [
        pair[1]
        for pair in sorted(
            latest_by_key.values(),
            key=lambda pair: (
                pair[1]["knowledge_key"],
                pair[0],
                pair[1]["record_id"],
            ),
        )
    ]

    counts = {
        "input": len(rows),
        "visible": len(visible),
        "future_masked": sum(1 for item in masked if item["state"] == "FUTURE_MASKED"),
        "unknown_availability": unknown_availability,
        "invalid": len(invalid),
        "superseded": superseded,
    }

    if invalid or unknown_availability:
        state = "PARTIAL" if visible else "EMPTY"
    elif visible:
        state = "VERIFIED"
    else:
        state = "EMPTY"

    digest_payload = {
        "replay_at": _iso(cutoff),
        "visible_records": visible,
    }
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": "",
        "replay_at": _iso(cutoff),
        "visible_records": visible,
        "masked_records": masked,
        "invalid_records": invalid,
        "counts": counts,
        "frame_digest": _stable_digest(digest_payload) if visible else _stable_digest(digest_payload),
        "point_in_time_verified": state == "VERIFIED",
        "future_evidence_exposed": False,
        "training_only": True,
        "executes_action": False,
        "real_trading_enabled": False,
    }


def start_replay_session(
    *,
    scenario_id: Any,
    title: Any,
    domain: Any,
    mode: Any,
    replay_at: Any,
    records: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    frame = build_replay_frame(records, replay_at=replay_at)
    scenario = _clean(scenario_id, 120)
    name = _clean(title, 240)
    area = _clean(domain, 80).lower() or "general"
    replay_mode = _mode(mode)

    if not scenario or not name or frame["state"] == "BLOCKED":
        return {
            "schema": SCHEMA,
            "session_id": "",
            "scenario_id": scenario,
            "title": name,
            "domain": area,
            "mode": replay_mode,
            "state": "BLOCKED",
            "reason": frame.get("reason") or "SCENARIO_ID_AND_TITLE_REQUIRED",
            "replay_at": frame.get("replay_at") or "",
            "frame": frame,
            "decision": None,
            "outcome": None,
            "evaluation": "UNREVEALED",
            "training_only": True,
            "live_data_used": False,
            "future_evidence_exposed": False,
            "automatic_promotion": False,
            "execution_authorized": False,
            "executes_action": False,
            "real_trading_enabled": False,
        }

    session_id = "REPLAY-" + _stable_digest({
        "scenario_id": scenario,
        "replay_at": frame["replay_at"],
        "frame_digest": frame["frame_digest"],
        "mode": replay_mode,
    }, length=16).upper()

    return {
        "schema": SCHEMA,
        "session_id": session_id,
        "scenario_id": scenario,
        "title": name,
        "domain": area,
        "mode": replay_mode,
        "state": "ACTIVE",
        "reason": "",
        "replay_at": frame["replay_at"],
        "frame": frame,
        "decision": None,
        "outcome": None,
        "evaluation": "UNREVEALED",
        "training_only": True,
        "live_data_used": False,
        "future_evidence_exposed": False,
        "automatic_promotion": False,
        "execution_authorized": False,
        "executes_action": False,
        "real_trading_enabled": False,
    }


def submit_replay_decision(
    session: Mapping[str, Any] | None,
    *,
    choice: Any,
    rationale: Any = "",
    confidence_pct: Any = None,
    submitted_at: Any,
) -> dict[str, Any]:
    current = _force_training_safety(session)
    if current.get("state") != "ACTIVE":
        current["state"] = "BLOCKED"
        current["reason"] = "SESSION_NOT_ACTIVE"
        return current

    decision = _clean(choice, 500)
    stamp = _utc(submitted_at)
    replay_cutoff = _utc(current.get("replay_at"))
    if not decision or stamp is None or replay_cutoff is None:
        current["state"] = "BLOCKED"
        current["reason"] = "DECISION_OR_SUBMITTED_AT_INVALID"
        return current
    if stamp < replay_cutoff:
        current["state"] = "BLOCKED"
        current["reason"] = "DECISION_BEFORE_REPLAY_CUTOFF"
        return current
    if _contains_secret({"choice": choice, "rationale": rationale}):
        current["state"] = "BLOCKED"
        current["reason"] = "SECRET_MATERIAL_REJECTED"
        return current

    confidence = None
    if confidence_pct is not None:
        if isinstance(confidence_pct, bool):
            current["state"] = "BLOCKED"
            current["reason"] = "CONFIDENCE_INVALID"
            return current
        try:
            confidence = float(confidence_pct)
        except (TypeError, ValueError):
            current["state"] = "BLOCKED"
            current["reason"] = "CONFIDENCE_INVALID"
            return current
        if not math.isfinite(confidence) or confidence < 0 or confidence > 100:
            current["state"] = "BLOCKED"
            current["reason"] = "CONFIDENCE_INVALID"
            return current
        confidence = round(confidence, 2)

    decision_payload = {
        "choice": decision,
        "rationale": _clean(rationale, 1600),
        "confidence_pct": confidence,
        "confidence_meaning": "TRAINEE_SELF_CONFIDENCE_NOT_PROFIT_PROBABILITY",
        "submitted_at": _iso(stamp),
    }
    decision_payload["decision_digest"] = _stable_digest(decision_payload)

    current["decision"] = decision_payload
    current["state"] = "DECISION_RECORDED"
    current["reason"] = ""
    current["outcome"] = None
    current["evaluation"] = "UNREVEALED"
    current["automatic_promotion"] = False
    current["execution_authorized"] = False
    current["executes_action"] = False
    current["real_trading_enabled"] = False
    return current


def reveal_replay_outcome(
    session: Mapping[str, Any] | None,
    *,
    outcome: Mapping[str, Any] | None,
    available_at: Any,
    revealed_at: Any,
) -> dict[str, Any]:
    current = _force_training_safety(session)
    if current.get("state") != "DECISION_RECORDED":
        current["state"] = "BLOCKED"
        current["reason"] = "DECISION_REQUIRED_BEFORE_REVEAL"
        return current

    replay_cutoff = _utc(current.get("replay_at"))
    available = _utc(available_at)
    revealed = _utc(revealed_at)
    if replay_cutoff is None or available is None or revealed is None:
        current["state"] = "BLOCKED"
        current["reason"] = "OUTCOME_TIME_INVALID"
        return current
    if available <= replay_cutoff:
        current["state"] = "BLOCKED"
        current["reason"] = "OUTCOME_WAS_AVAILABLE_AT_REPLAY"
        return current
    if revealed < available:
        current["state"] = "BLOCKED"
        current["reason"] = "OUTCOME_NOT_YET_AVAILABLE"
        return current

    raw = dict(outcome or {})
    if _contains_secret(raw):
        current["state"] = "BLOCKED"
        current["reason"] = "SECRET_MATERIAL_REJECTED"
        return current
    try:
        safe_outcome = _canonical(raw)
    except ValueError as exc:
        current["state"] = "BLOCKED"
        current["reason"] = str(exc)
        return current

    expected = _clean(safe_outcome.get("expected_decision"), 500).casefold()
    actual = _clean((current.get("decision") or {}).get("choice"), 500).casefold()
    if expected:
        evaluation = "MATCH" if expected == actual else "MISMATCH"
    else:
        evaluation = "UNSCORED"

    current["outcome"] = {
        "available_at": _iso(available),
        "revealed_at": _iso(revealed),
        "payload": safe_outcome,
    }
    current["evaluation"] = evaluation
    current["evaluation_meaning"] = (
        "DESCRIPTIVE_TRAINING_COMPARISON_NOT_PROFIT_PROBABILITY"
    )
    current["decision_quality_inferred"] = False
    current["state"] = "REVEALED"
    current["reason"] = ""
    current["automatic_promotion"] = False
    current["execution_authorized"] = False
    current["executes_action"] = False
    current["real_trading_enabled"] = False
    return current


def compact_replay_rows(frame: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Presentation-only rows from evidence that was visible at the cutoff."""
    out: list[dict[str, Any]] = []
    for item in list((frame or {}).get("visible_records") or []):
        if not isinstance(item, Mapping):
            continue
        out.append({
            "Quando ficou disponível": item.get("available_at"),
            "Fonte": item.get("source"),
            "Tipo": item.get("kind"),
            "Evidência": item.get("label") or item.get("knowledge_key"),
            "Verdade": item.get("truth_state"),
        })
    return out


__all__ = [
    "SCHEMA",
    "REPLAY_MODES",
    "FRAME_STATES",
    "SESSION_STATES",
    "TRUTH_STATES",
    "build_replay_frame",
    "start_replay_session",
    "submit_replay_decision",
    "reveal_replay_outcome",
    "compact_replay_rows",
]
