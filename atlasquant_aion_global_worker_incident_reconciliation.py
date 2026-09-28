"""AION Global Worker Incident Center Closure Reconciliation V1.

Read-only reconciliation between:
- the current Global Worker Operational Supervision incident proposal; and
- durable human closure records stored in the shared runtime Checkpoint.

Safety rules:
- closure history never authorizes reactivation;
- invalid or unavailable durable evidence never suppresses an active incident;
- a signal observed after its durable closure is REOPENED;
- a different new Global Worker incident after a prior closure stays OPEN;
- only the exact incident evidence digest, observed no later than the durable
  closure persistence timestamp, may be presented as CLOSED_HUMAN_VERIFIED.

This module performs no write, containment, feature-flag mutation, worker tick,
workflow dispatch, deploy, merge, external action, or trading action.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.evidence import digest, utc
from atlasquant_aion_global_worker_durable_incident_closure import (
    RECORD_SCHEMA,
    load_closure_ledger,
)
from atlasquant_aion_global_worker_supervision import operational_incident


SCHEMA = "ATLASQUANT_AION_GLOBAL_WORKER_INCIDENT_RECONCILIATION_V1"
SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
_SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITIES)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return utc(parsed)
    except Exception:
        return None


def _payload_digest(value: Mapping[str, Any], field: str) -> str:
    raw = dict(value)
    raw.pop(field, None)
    return digest(raw)


def _valid_durable_record(
    row: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    item = deepcopy(dict(row or {}))
    if str(item.get("schema") or "") != RECORD_SCHEMA:
        return {}, {
            "state": "MISMATCH",
            "reason": "DURABLE_CLOSURE_RECORD_SCHEMA_MISMATCH",
        }

    stored = str(item.get("record_digest") or "")
    expected = _payload_digest(item, "record_digest")
    if not stored or stored != expected:
        return {}, {
            "state": "MISMATCH",
            "reason": "DURABLE_CLOSURE_RECORD_DIGEST_MISMATCH",
        }

    required = {
        "closure_record_id": str(item.get("closure_record_id") or ""),
        "closure_record_digest": str(item.get("closure_record_digest") or ""),
        "closure_package_digest": str(item.get("closure_package_digest") or ""),
        "incident_evidence_digest": str(
            item.get("incident_evidence_digest") or ""
        ),
        "remediation_digest": str(item.get("remediation_digest") or ""),
    }
    if (
        not required["closure_record_id"].startswith("GW-CLOSE-")
        or not all(required.values())
        or str(item.get("human_closure_decision") or "") != "APPROVED"
    ):
        return {}, {
            "state": "MISMATCH",
            "reason": "DURABLE_CLOSURE_RECORD_FIELDS_INVALID",
        }

    persisted_at = _parse_iso(item.get("persisted_at"))
    human_recorded_at = _parse_iso(item.get("human_recorded_at"))
    if (
        persisted_at is None
        or human_recorded_at is None
        or persisted_at < human_recorded_at
    ):
        return {}, {
            "state": "MISMATCH",
            "reason": "DURABLE_CLOSURE_RECORD_TIMESTAMP_INVALID",
        }

    for key in (
        "authoritative_incident_center_status_modified",
        "reactivation_authorized",
        "feature_flag_modified",
        "global_worker_modified",
        "real_trading_enabled",
    ):
        if item.get(key) is not False:
            return {}, {
                "state": "MISMATCH",
                "reason": "DURABLE_CLOSURE_RECORD_AUTHORITY_MISMATCH",
            }

    return item, {
        "state": "CONFIRMED",
        "reason": "",
        "persisted_at": persisted_at.isoformat(),
    }


def _closure_history(
    runtime_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runtime = dict(runtime_result or {})
    if str(runtime.get("status") or "").upper() != "CONFIRMED":
        return {
            "state": "UNAVAILABLE",
            "reason": "CONFIRMED_RUNTIME_REQUIRED_FOR_DURABLE_CLOSURES",
            "records": [],
        }
    checkpoint = runtime.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        return {
            "state": "UNAVAILABLE",
            "reason": "RUNTIME_CHECKPOINT_REQUIRED_FOR_DURABLE_CLOSURES",
            "records": [],
        }

    ledger, status = load_closure_ledger(checkpoint)
    if status.get("state") == "MISMATCH":
        return {
            "state": "BLOCKED",
            "reason": str(status.get("reason") or "CLOSURE_LEDGER_MISMATCH"),
            "records": [],
        }

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for row in list(ledger.get("records") or []):
        if not isinstance(row, Mapping):
            invalid.append({
                "reason": "DURABLE_CLOSURE_RECORD_NOT_MAPPING",
            })
            continue
        item, row_status = _valid_durable_record(row)
        if row_status.get("state") != "CONFIRMED":
            invalid.append({
                "closure_record_id": str(row.get("closure_record_id") or ""),
                "reason": str(row_status.get("reason") or ""),
            })
            continue
        valid.append(item)

    if invalid:
        return {
            "state": "BLOCKED",
            "reason": "DURABLE_CLOSURE_RECORD_INTEGRITY_MISMATCH",
            "records": [],
            "invalid_records": invalid,
        }

    valid.sort(
        key=lambda row: (
            str(row.get("persisted_at") or ""),
            str(row.get("closure_record_id") or ""),
        )
    )
    return {
        "state": "CONFIRMED",
        "reason": "",
        "records": valid,
        "ledger_state": str(status.get("state") or ""),
        "ledger_digest": str(ledger.get("digest") or ""),
    }


def _historical_closed_row(record: Mapping[str, Any]) -> dict[str, Any]:
    evidence_digest = str(record.get("incident_evidence_digest") or "")
    return {
        "incident_id": "INC-AION-GW-" + evidence_digest[:12].upper(),
        "kind": "OBSERVABILITY",
        "severity": "INFO",
        "title": "AION Global Worker · fechamento humano verificado",
        "detail": (
            "Incidente histórico com decisão humana de fechamento persistida "
            "e reconciliada por evidência."
        ),
        "source": "aion_global_worker_durable_incident_closure",
        "evidence_state": "CONFIRMED",
        "status": "CLOSED_HUMAN_VERIFIED",
        "response_key": "global_worker",
        "evidence_digest": evidence_digest,
        "closure_record_id": str(record.get("closure_record_id") or ""),
        "closure_record_digest": str(
            record.get("closure_record_digest") or ""
        ),
        "closed_at": str(record.get("persisted_at") or ""),
        "human_recorded_at": str(record.get("human_recorded_at") or ""),
        "reactivation_authorized": False,
        "automatic_reactivation": False,
        "automatic_containment": False,
        "real_orders_enabled": False,
    }


def _recount(rows: list[dict[str, Any]]) -> tuple[dict[str, int], str]:
    counts = {sev: 0 for sev in SEVERITIES}
    for row in rows:
        sev = str(row.get("severity") or "INFO").upper()
        if sev in counts:
            counts[sev] += 1
    highest = "INFO"
    for sev in SEVERITIES:
        if counts[sev]:
            highest = sev
    return counts, highest


def reconcile_global_worker_incident_center(
    base_snapshot: Mapping[str, Any] | None,
    supervision: Mapping[str, Any] | None,
    runtime_result: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a read-only Incident Center snapshot with Global Worker closure history."""
    current = utc(now or _now())
    base = deepcopy(dict(base_snapshot or {}))
    active = [
        deepcopy(dict(row))
        for row in list(base.get("incidents") or [])
        if isinstance(row, Mapping)
    ]

    history = _closure_history(runtime_result)
    closure_records = list(history.get("records") or [])
    closed_rows = [_historical_closed_row(row) for row in closure_records]
    current_proposal = operational_incident(supervision)
    incident = (
        deepcopy(dict(current_proposal.get("incident") or {}))
        if isinstance(current_proposal.get("incident"), Mapping)
        else None
    )

    reconciliation_state = "NO_GLOBAL_WORKER_INCIDENT"
    current_outcome = "NONE"
    prior_closure_record_id = ""

    if incident is not None:
        incident["evidence_digest"] = str(
            (supervision or {}).get("evidence_digest") or ""
        )
        incident["observed_at"] = str(
            (supervision or {}).get("generated_at") or ""
        )
        incident["reactivation_authorized"] = False
        incident["automatic_reactivation"] = False

        if history.get("state") != "CONFIRMED":
            incident["status"] = "OPEN"
            incident["closure_reconciliation"] = "UNAVAILABLE_FAIL_OPEN"
            active.append(incident)
            reconciliation_state = "FAIL_OPEN"
            current_outcome = "OPEN"
        else:
            evidence_digest = str(incident.get("evidence_digest") or "")
            observed_at = _parse_iso(incident.get("observed_at"))
            exact = [
                row
                for row in closure_records
                if str(row.get("incident_evidence_digest") or "")
                == evidence_digest
            ]
            exact.sort(key=lambda row: str(row.get("persisted_at") or ""))
            exact_closure = exact[-1] if exact else None

            if exact_closure is not None:
                persisted_at = _parse_iso(exact_closure.get("persisted_at"))
                prior_closure_record_id = str(
                    exact_closure.get("closure_record_id") or ""
                )
                incident["prior_closure_record_id"] = prior_closure_record_id
                incident["prior_closure_at"] = str(
                    exact_closure.get("persisted_at") or ""
                )
                if (
                    observed_at is not None
                    and persisted_at is not None
                    and observed_at <= persisted_at
                ):
                    incident["status"] = "CLOSED_HUMAN_VERIFIED"
                    incident["closure_reconciliation"] = (
                        "EXACT_EVIDENCE_CLOSED_AFTER_OBSERVATION"
                    )
                    incident["closed_at"] = persisted_at.isoformat()
                    closed_rows = [
                        row
                        for row in closed_rows
                        if str(row.get("closure_record_id") or "")
                        != prior_closure_record_id
                    ]
                    closed_rows.append(incident)
                    reconciliation_state = "CLOSED_HISTORY_RECOGNIZED"
                    current_outcome = "CLOSED_HISTORICAL"
                else:
                    incident["status"] = "REOPENED"
                    incident["closure_reconciliation"] = (
                        "SIGNAL_OBSERVED_AFTER_DURABLE_CLOSURE"
                    )
                    incident["recurrence_detected"] = True
                    active.append(incident)
                    reconciliation_state = "REOPENED"
                    current_outcome = "REOPENED"
            elif closure_records:
                latest = closure_records[-1]
                latest_at = _parse_iso(latest.get("persisted_at"))
                prior_closure_record_id = str(
                    latest.get("closure_record_id") or ""
                )
                incident["prior_closure_record_id"] = prior_closure_record_id
                incident["prior_closure_at"] = str(
                    latest.get("persisted_at") or ""
                )
                if (
                    observed_at is not None
                    and latest_at is not None
                    and observed_at > latest_at
                ):
                    incident["status"] = "OPEN_NEW_AFTER_CLOSURE"
                    incident["closure_reconciliation"] = (
                        "NEW_EVIDENCE_AFTER_PRIOR_CLOSURE"
                    )
                    incident["new_incident_after_closure"] = True
                    reconciliation_state = "NEW_INCIDENT_AFTER_CLOSURE"
                else:
                    incident["status"] = "OPEN"
                    incident["closure_reconciliation"] = (
                        "NO_EXACT_DURABLE_CLOSURE_MATCH"
                    )
                    reconciliation_state = "OPEN"
                active.append(incident)
                current_outcome = str(incident.get("status") or "OPEN")
            else:
                incident["status"] = "OPEN"
                incident["closure_reconciliation"] = "NO_DURABLE_CLOSURE"
                active.append(incident)
                reconciliation_state = "OPEN"
                current_outcome = "OPEN"

    # Deduplicate active rows by incident id while preserving the latest appended
    # Global Worker interpretation.
    dedup: dict[str, dict[str, Any]] = {}
    for row in active:
        incident_id = str(row.get("incident_id") or "")
        if incident_id:
            dedup[incident_id] = row
    active = list(dedup.values())
    active.sort(
        key=lambda row: (
            -_SEVERITY_RANK.get(
                str(row.get("severity") or "INFO").upper(),
                0,
            ),
            str(row.get("kind") or ""),
            str(row.get("incident_id") or ""),
        )
    )
    closed_rows.sort(
        key=lambda row: (
            str(row.get("closed_at") or ""),
            str(row.get("incident_id") or ""),
        ),
        reverse=True,
    )

    counts, highest = _recount(active)
    result = {
        **base,
        "incidents": active,
        "total": len(active),
        "counts": counts,
        "highest_severity": highest,
        "has_critical": counts["CRITICAL"] > 0,
        "closed_incidents": closed_rows,
        "closed_total": len(closed_rows),
        "global_worker_reconciliation": {
            "schema": SCHEMA,
            "state": reconciliation_state,
            "current_outcome": current_outcome,
            "durable_history_state": str(history.get("state") or "UNKNOWN"),
            "durable_history_reason": str(history.get("reason") or ""),
            "durable_closure_records": len(closure_records),
            "prior_closure_record_id": prior_closure_record_id,
            "reconciled_at": current.isoformat(),
            "fail_open": history.get("state") != "CONFIRMED",
            "reactivation_authorized": False,
            "automatic_reactivation": False,
            "feature_flag_modified": False,
            "runtime_modified": False,
            "global_worker_modified": False,
            "executes_action": False,
            "real_trading_enabled": False,
        },
        "automatic_containment": False,
        "automatic_rollback": False,
        "automatic_secret_rotation": False,
        "automatic_account_mutation": False,
        "automatic_reactivation": False,
        "real_orders_enabled": False,
        "executes_action": False,
    }
    return result


def closed_incident_rows(
    snapshot: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Compact human-readable closure history."""
    rows: list[dict[str, Any]] = []
    for item in list((snapshot or {}).get("closed_incidents") or []):
        if not isinstance(item, Mapping):
            continue
        rows.append({
            "Estado": str(item.get("status") or ""),
            "Incidente": str(item.get("title") or ""),
            "Fechado em": str(item.get("closed_at") or ""),
            "Closure record": str(item.get("closure_record_id") or ""),
            "Reativação autorizada": "NÃO",
        })
    return rows


__all__ = [
    "SCHEMA",
    "reconcile_global_worker_incident_center",
    "closed_incident_rows",
]
