"""Read-only recovery + traceability readiness gate for AION.

This module recomputes recovery preflight and binds it to safe local
traceability. It never restores, saves, retries, deploys, or authorizes action.
"""
from __future__ import annotations

from typing import Any, Mapping
import hashlib
import json
import re

from atlasquant_aion_recovery import recovery_preflight
from atlasquant_aion_local_traceability import SCHEMA as TRACE_SCHEMA, SOURCE_CATALOG

SCHEMA = "ATLASQUANT_AION_RECOVERY_TRACEABILITY_GATE_V1"

_TRACE_ID = re.compile(r"LCL-EV-[0-9A-F]{12}\Z")
_FINGERPRINT = re.compile(r"AION-LCL-[0-9A-F]{16}\Z")


def _trace_projection_coherent(trace: Mapping[str, Any]) -> bool:
    """Recompute ALL review-only summary projections from the local records.

    A digest of caller-supplied summary booleans is not evidence; neither a
    valid-looking trace nor this check authenticates an independent witness.
    """
    rows = trace.get("records")
    count = trace.get("record_count")
    if (type(rows) is not list or type(count) is not int
            or not 1 <= len(rows) <= 8 or count != len(rows)):
        return False
    for flag in (
        "raw_result_included", "tool_output_is_authority",
        "executes_action", "external_action_executed",
        "real_orders_enabled", "private_chain_of_thought_exposed",
    ):
        if trace.get(flag) is not False:
            return False
    if trace.get("contract_consistent") is not True or trace.get("contract_mismatch") is not False:
        return False
    fields = (
        "execution_refs", "confirmed_content_refs", "unknown_refs",
        "conflict_refs", "source_keys", "contract_fingerprints",
    )
    if any(type(trace.get(k)) is not list for k in fields):
        return False
    exec_refs, content_refs, unknown_refs, conflict_refs = [], [], [], []
    source_keys, fingerprints, all_ids = set(), set(), set()
    for row in rows:
        if type(row) is not dict:
            return False
        tid, tool_id = row.get("trace_id"), row.get("tool_id")
        if (type(tid) is not str or _TRACE_ID.fullmatch(tid) is None
                or tid in all_ids or type(tool_id) is not str
                or tool_id not in SOURCE_CATALOG):
            return False
        all_ids.add(tid)
        source = SOURCE_CATALOG[tool_id]
        if (row.get("source_key") != source["source_key"]
                or row.get("source_path") != source["source_path"]
                or row.get("local_only") is not True
                or row.get("security_state") != "SAFE_LOCAL"
                or row.get("authority") is not False
                or type(row.get("execution_confirmed")) is not bool
                or type(row.get("content_confirmed")) is not bool
                or row.get("security_issues") != []
                or row.get("blockers") != []):
            return False
        conflicts = row.get("conflicts")
        if type(conflicts) is not list or not all(type(v) is str for v in conflicts):
            return False
        fp = row.get("contract_fingerprint")
        if type(fp) is not str or _FINGERPRINT.fullmatch(fp) is None:
            return False
        fingerprints.add(fp)
        source_keys.add(source["source_key"])
        if row["execution_confirmed"]:
            exec_refs.append(tid)
        if row["content_confirmed"]:
            content_refs.append(tid)
        else:
            unknown_refs.append(tid)
        if conflicts:
            conflict_refs.append(tid)
    expected = {
        "execution_refs":exec_refs,
        "confirmed_content_refs":content_refs,
        "unknown_refs":unknown_refs,
        "conflict_refs":conflict_refs,
        "source_keys":sorted(source_keys),
        "contract_fingerprints":sorted(fingerprints),
    }
    if len(fingerprints)!=1:
        return False
    return all(trace.get(k)==v for k,v in expected.items())


def _safe_trace_security(trace: Mapping[str, Any]) -> bool:
    sec = trace.get("security")
    return bool(
        type(sec) is dict
        and sec.get("state") == "SAFE_LOCAL"
        and sec.get("issues") == []
        and sec.get("network_called") is False
        and sec.get("connector_called") is False
        and sec.get("external_side_effects") is False
    )


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def recovery_traceability_readiness(
    current_runtime: Mapping[str, Any] | None,
    candidate: Mapping[str, Any] | None,
    traceability: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = dict(current_runtime or {})
    selected = dict(candidate or {})
    # A126: callers may pass malformed trace summaries directly. Never
    # trust record_count, execution_refs, source_keys or SAFE_LOCAL labels
    # without reconstructing each claim from the actual records.
    trace = dict(traceability) if isinstance(traceability, Mapping) else {}
    preflight = recovery_preflight(current, selected)
    blockers: list[str] = []

    if preflight.get("allowed") is not True:
        blockers.append("RECOVERY_PREFLIGHT_BLOCKED")
    if trace.get("schema") != TRACE_SCHEMA:
        blockers.append("TRACEABILITY_SCHEMA_INVALID")
    if not _safe_trace_security(trace):
        blockers.append("TRACEABILITY_SECURITY_BLOCK")
    if trace.get("contract_consistent") is not True:
        blockers.append("TRACEABILITY_CONTRACT_INCONSISTENT")
    if trace.get("contract_mismatch") is True:
        blockers.append("TRACEABILITY_CONTRACT_MISMATCH")
    if not _trace_projection_coherent(trace):
        blockers.append("TRACEABILITY_RECORD_PROJECTION_MISMATCH")

    rows = trace.get("records") if type(trace.get("records")) is list else []
    count = trace.get("record_count")
    if type(count) is not int or count <= 0:
        blockers.append("TRACEABILITY_EVIDENCE_REQUIRED")
    refs = trace.get("execution_refs") if type(trace.get("execution_refs")) is list else []
    refs = [x for x in refs if type(x) is str]
    if not refs:
        blockers.append("TRACEABILITY_EXECUTION_REF_REQUIRED")
    conflicts = trace.get("conflict_refs") if type(trace.get("conflict_refs")) is list else []
    if conflicts:
        blockers.append("TRACEABILITY_CONFLICT")
    sources = trace.get("source_keys") if type(trace.get("source_keys")) is list else []
    sources = [x for x in sources if type(x) is str]
    if "checkpoint_master" not in sources:
        blockers.append("CHECKPOINT_TRACE_REQUIRED")
    if not isinstance(trace.get("security"), Mapping) or trace["security"].get("external_side_effects") is not False:
        blockers.append("TRACEABILITY_EXTERNAL_SIDE_EFFECT_UNKNOWN")
    if any(isinstance(row, Mapping) and row.get("authority") is not False for row in rows):
        blockers.append("TRACEABILITY_AUTHORITY_FORBIDDEN")

    receipt = {
        "current_runtime_sha": str(current.get("sha") or ""),
        "candidate_revision": str(preflight.get("candidate_revision") or ""),
        "candidate_digest": str(preflight.get("candidate_digest") or ""),
        "candidate_integrity": str(preflight.get("candidate_integrity") or ""),

        "trace_refs": sorted(refs),
        "trace_sources": sorted(sources),
        "requires_explicit_admin_approval": True,
        "automatic_restore": False,
    }
    receipt_digest = _digest(receipt)
    ready = not blockers
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_ADMIN_REVIEW" if ready else "BLOCKED",
        "blockers": list(dict.fromkeys(blockers)),
        "recovery_preflight": preflight,
        "traceability_state": str(trace.get("state") or "UNKNOWN"),
        "receipt": receipt,
        "receipt_digest": receipt_digest,
        "recovery_authorized": False,
        "automatic_restore": False,
        "automatic_retry": False,
        "checkpoint_saved": False,
        "external_action_executed": False,
        "network_called": False,
    }

def recovery_traceability_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "recovery_preflight_required": True,
        "traceability_required": True,
        "safe_local_trace_required": True,
        "checkpoint_source_required": True,
        "conflict_blocks_readiness": True,
        "explicit_admin_approval_required": True,
        "automatic_restore": False,
        "automatic_retry": False,
        "execution_authority": False,
    }

__all__ = [
    "SCHEMA",
    "recovery_traceability_readiness",
    "recovery_traceability_policy",
]
