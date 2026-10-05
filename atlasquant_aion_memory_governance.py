"""Governed AION memory promotion with provenance and taint tracking.

This is the only contract that may declare a layered-memory entry PROMOTED.
External documents, web content, tool output, model output and imported memory
start tainted. Verification can clear only explicit taint classes and can never
turn memory into action authority.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

from atlasquant_aion_memory_layers import default_memory_layers, remember
from atlasquant_aion_independent_verifier import validate_verification_receipt
from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_MEMORY_GOVERNANCE_V1"
STATES = ("PROPOSED", "VERIFIED", "PROMOTED", "REJECTED", "SUPERSEDED")
SOURCE_TYPES = (
    "CANONICAL_DOC",
    "ADMIN_DECISION",
    "WEB",
    "DOCUMENT",
    "BOOK",
    "EMAIL",
    "TOOL_OUTPUT",
    "PLUGIN",
    "EXTERNAL_AI",
    "UPLOAD",
    "PASTED_TEXT",
    "GENERATED",
    "IMPORTED_MEMORY",
)
VERIFIER_KINDS = ("CODE", "SOURCE_REQUERY", "HUMAN", "INDEPENDENT_MODEL")
UNTRUSTED_SOURCE_TYPES = frozenset({
    "WEB", "DOCUMENT", "BOOK", "EMAIL", "TOOL_OUTPUT", "PLUGIN",
    "EXTERNAL_AI", "UPLOAD", "PASTED_TEXT", "GENERATED", "IMPORTED_MEMORY",
})
MODEL_SOURCE_TYPES = frozenset({"EXTERNAL_AI", "GENERATED"})
MAX_PROPOSALS = 1000


def _clean(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: Any = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _refs(values: Sequence[Any] | None, limit: int = 60) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[:limit * 2]:
        value = _clean(raw, 300)
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


def _trusted_scope(context: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(context or {})
    owner = _clean(raw.get("owner_id") or raw.get("actor_id"), 120)
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not owner or not tenant or not workspace:
        raise ValueError("trusted owner/tenant/workspace required")
    return {"owner_id": owner, "tenant_id": tenant, "workspace_id": workspace}


def _source_taint(source_type: str) -> list[str]:
    out = []
    if source_type in UNTRUSTED_SOURCE_TYPES:
        out.append("UNTRUSTED_EXTERNAL_SOURCE")
    if source_type in MODEL_SOURCE_TYPES:
        out.append("MODEL_GENERATED")
    if source_type == "TOOL_OUTPUT":
        out.append("TOOL_DERIVED")
    if source_type == "IMPORTED_MEMORY":
        out.append("IMPORTED_MEMORY")
    return out


def default_memory_governance() -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "proposals": proposals,
        "digest": _digest(proposals),
        "automatic_promotion": False,
        "memory_authority": "NONE",
        "executes_action": False,
    }


def normalize_memory_governance(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or (raw and raw.get("schema") != SCHEMA):
        return default_memory_governance()
    proposals = []
    seen = set()
    for candidate in list(raw.get("proposals") or [])[-MAX_PROPOSALS * 2:]:
        if not isinstance(candidate, Mapping):
            continue
        item = dict(candidate)
        proposal_id = _clean(item.get("proposal_id"), 120)
        state = _upper(item.get("state"), 30)
        if not proposal_id or state not in STATES:
            continue
        if proposal_id in seen:
            proposals = [row for row in proposals if row["proposal_id"] != proposal_id]
        seen.add(proposal_id)
        proposals.append(item)
    proposals = proposals[-MAX_PROPOSALS:]
    return {
        "schema": SCHEMA,
        "proposals": proposals,
        "digest": _digest(proposals),
        "automatic_promotion": False,
        "memory_authority": "NONE",
        "executes_action": False,
    }


def propose_memory(
    governance: Mapping[str, Any] | None,
    *,
    content: Any,
    source_type: Any,
    provenance_ref: Any,
    content_digest: Any = "",
    evidence_refs: Sequence[Any] | None = None,
    category: Any = "fact",
    layer: Any = "knowledge",
    domain: Any = "CORE",
    persona: Any = "",
    memory_key: Any = "",
    valid_until: Any = "",
    trusted_context: Mapping[str, Any] | None,
    created_at: Any = None,
) -> dict[str, Any]:
    state = normalize_memory_governance(governance)
    scope = _trusted_scope(trusted_context)
    source = _upper(source_type, 40)
    if source not in SOURCE_TYPES:
        raise ValueError("unsupported memory source type")
    raw_content = " ".join(str(content or "").replace("\x00", "").split())
    if not raw_content:
        raise ValueError("memory content required")
    safe_content = redact_text(raw_content)[:4000]
    if "[REDACTED]" in safe_content:
        raise ValueError("secret-like content cannot enter governed memory")
    provenance = _clean(provenance_ref, 500)
    if not provenance:
        raise ValueError("provenance_ref required")
    actual_digest = "sha256:" + sha256(raw_content.encode("utf-8")).hexdigest()
    supplied_digest = _clean(content_digest, 160)
    if supplied_digest and supplied_digest != actual_digest:
        raise ValueError("content digest mismatch")
    refs = _refs(evidence_refs)
    created = _aware(created_at)
    taint = _source_taint(source)
    seed = {
        "scope": scope,
        "content_digest": actual_digest,
        "source_type": source,
        "provenance_ref": provenance,
        "category": _clean(category, 100).lower(),
        "layer": _clean(layer, 40).lower(),
        "domain": _upper(domain, 40),
        "persona": _clean(persona, 80).lower(),
        "memory_key": _clean(memory_key, 180),
    }
    proposal_id = "MGP-" + _digest(seed)[:24].upper()
    existing = next(
        (row for row in state["proposals"] if row.get("proposal_id") == proposal_id),
        None,
    )
    if existing is not None:
        return {
            "schema": SCHEMA,
            "state": "IDEMPOTENT",
            "proposal": deepcopy(existing),
            "governance": state,
            "executes_action": False,
        }
    record = {
        "schema": SCHEMA,
        "proposal_id": proposal_id,
        "state": "PROPOSED",
        **scope,
        "content": safe_content,
        "content_digest": actual_digest,
        "source_type": source,
        "provenance_ref": provenance,
        "provenance_chain": [provenance],
        "evidence_refs": refs,
        "verification_refs": [],
        "verification_kind": "",
        "verification_digest": "",
        "verification_receipt_digest": "",
        "verification_receipt_validated": False,
        "verified_at": "",
        "verified_by": "",
        "taint_labels": taint,
        "resolved_taint": [],
        "category": seed["category"] or "fact",
        "layer": seed["layer"] or "knowledge",
        "domain": seed["domain"] or "CORE",
        "persona": seed["persona"],
        "memory_key": seed["memory_key"],
        "valid_until": _clean(valid_until, 100),
        "created_at": created.isoformat(),
        "review_approved": False,
        "reviewed_by": "",
        "reviewed_at": "",
        "promoted_memory_id": "",
        "promotion_proof_digest": "",
        "truth_state": "UNKNOWN",
        "authority": "NONE",
        "executes_action": False,
    }
    proposals = [*state["proposals"], record][-MAX_PROPOSALS:]
    next_state = normalize_memory_governance({"schema": SCHEMA, "proposals": proposals})
    return {
        "schema": SCHEMA,
        "state": "PROPOSED",
        "proposal": deepcopy(record),
        "governance": next_state,
        "executes_action": False,
    }


def verify_memory_proposal(
    governance: Mapping[str, Any] | None,
    proposal_id: Any,
    *,
    verifier_kind: Any,
    verifier_id: Any,
    verification_refs: Sequence[Any] | None,
    verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    verification_receipt: Mapping[str, Any] | None = None,
    verification_request: Mapping[str, Any] | None = None,
    verification_scope: Mapping[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    state = normalize_memory_governance(governance)
    target = _clean(proposal_id, 120)
    kind = _upper(verifier_kind, 40)
    if kind not in VERIFIER_KINDS:
        raise ValueError("independent verifier kind required")
    verifier_name = _clean(verifier_id, 160)
    if not verifier_name:
        raise ValueError("verifier_id required")
    refs = _refs(verification_refs)
    if not refs:
        raise ValueError("verification refs required")
    record = next((row for row in state["proposals"] if row["proposal_id"] == target), None)
    if record is None:
        raise LookupError("memory proposal unavailable")
    if record["state"] != "PROPOSED":
        raise ValueError("only PROPOSED memory may be verified")
    if not callable(verifier):
        raise TypeError("independent verifier callback required")

    result = dict(verifier(deepcopy(record)) or {})
    bound_refs = _refs(result.get("bound_refs") if isinstance(result.get("bound_refs"), (list, tuple)) else [])
    verified_digest = _clean(result.get("content_digest"), 160)
    blockers = []
    if _upper(result.get("state"), 40) != "VERIFIED":
        blockers.append("VERIFIER_DID_NOT_VERIFY")
    if sorted(bound_refs) != sorted(refs):
        blockers.append("VERIFICATION_REF_MISMATCH")
    if verified_digest != record["content_digest"]:
        blockers.append("CONTENT_DIGEST_MISMATCH")
    if result.get("independent") is not True:
        blockers.append("VERIFIER_NOT_INDEPENDENT")
    if _clean(result.get("verifier_id"), 160) != verifier_name:
        blockers.append("VERIFIER_ID_MISMATCH")

    receipt_validated = False
    receipt_digest = ""
    receipt_inputs = (
        isinstance(verification_receipt, Mapping),
        isinstance(verification_request, Mapping),
        isinstance(verification_scope, Mapping),
    )
    if any(receipt_inputs):
        if not all(receipt_inputs):
            blockers.append("VERIFICATION_RECEIPT_BINDING_INCOMPLETE")
        else:
            receipt_check = validate_verification_receipt(
                verification_receipt,
                request=verification_request,
                scope=verification_scope,
                now=now,
            )
            if receipt_check.get("valid") is not True:
                blockers.append("VERIFICATION_RECEIPT_INVALID")
            elif _clean(verification_receipt.get("verifier_id"), 160) != verifier_name:
                blockers.append("VERIFICATION_RECEIPT_VERIFIER_MISMATCH")
            elif _clean(verification_request.get("content_digest"), 160) != record["content_digest"]:
                blockers.append("VERIFICATION_RECEIPT_CONTENT_MISMATCH")
            elif sorted(_refs(verification_receipt.get("bound_refs"))) != sorted(refs):
                blockers.append("VERIFICATION_RECEIPT_REFS_MISMATCH")
            else:
                receipt_validated = True
                receipt_digest = _clean(verification_receipt.get("receipt_digest"), 160)
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "blockers": blockers,
            "proposal": deepcopy(record),
            "governance": state,
            "executes_action": False,
        }

    verified = deepcopy(record)
    verified["state"] = "VERIFIED"
    verified["verification_kind"] = kind
    verified["verification_refs"] = refs
    verified["verification_digest"] = _digest({
        "proposal_id": target,
        "content_digest": record["content_digest"],
        "verifier_kind": kind,
        "verifier_id": verifier_name,
        "verification_refs": refs,
        "verification_receipt_digest": receipt_digest,
    })
    verified["verification_receipt_digest"] = receipt_digest
    verified["verification_receipt_validated"] = receipt_validated
    verified["verified_at"] = _aware(now).isoformat()
    verified["verified_by"] = verifier_name
    verified["resolved_taint"] = list(verified.get("taint_labels") or [])
    verified["taint_labels"] = []
    verified["provenance_chain"] = list(dict.fromkeys([
        *list(record.get("provenance_chain") or []),
        *refs,
    ]))
    verified["truth_state"] = "CONFIRMED"

    proposals = [
        verified if row["proposal_id"] == target else row
        for row in state["proposals"]
    ]
    next_state = normalize_memory_governance({"schema": SCHEMA, "proposals": proposals})
    return {
        "schema": SCHEMA,
        "state": "VERIFIED",
        "proposal": deepcopy(verified),
        "governance": next_state,
        "executes_action": False,
    }


def promote_verified_memory(
    governance: Mapping[str, Any] | None,
    memory_layers: Mapping[str, Any] | None,
    proposal_id: Any,
    *,
    trusted_context: Mapping[str, Any] | None,
    review_approved: bool,
    reviewed_by: Any,
    now: Any = None,
) -> dict[str, Any]:
    state = normalize_memory_governance(governance)
    scope = _trusted_scope(trusted_context)
    target = _clean(proposal_id, 120)
    reviewer = _clean(reviewed_by, 160)
    record = next((row for row in state["proposals"] if row["proposal_id"] == target), None)
    if record is None:
        raise LookupError("memory proposal unavailable")

    blockers = []
    if record["state"] != "VERIFIED":
        blockers.append("PROPOSAL_NOT_VERIFIED")
    for key in ("owner_id", "tenant_id", "workspace_id"):
        if record.get(key) != scope[key]:
            blockers.append("SCOPE_MISMATCH")
            break
    if review_approved is not True or not reviewer:
        blockers.append("HUMAN_REVIEW_REQUIRED")
    if record.get("taint_labels"):
        blockers.append("TAINT_UNRESOLVED")
    if not record.get("verification_refs") or not record.get("verification_digest"):
        blockers.append("VERIFICATION_PROOF_MISSING")
    if record.get("verification_receipt_validated") is not True or not record.get("verification_receipt_digest"):
        blockers.append("VERIFICATION_RECEIPT_REQUIRED")
    if not record.get("provenance_ref") or not record.get("content_digest"):
        blockers.append("PROVENANCE_MISSING")
    if record.get("truth_state") != "CONFIRMED":
        blockers.append("CONFIRMED_TRUTH_REQUIRED")
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "blockers": sorted(set(blockers)),
            "proposal": deepcopy(record),
            "governance": state,
            "memory_layers": deepcopy(memory_layers or default_memory_layers()),
            "executes_action": False,
        }

    reviewed_at = _aware(now).isoformat()
    proof = {
        "schema": SCHEMA,
        "proposal_id": target,
        "content_digest": record["content_digest"],
        "verification_digest": record["verification_digest"],
        "verification_receipt_digest": record["verification_receipt_digest"],
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "scope": scope,
    }
    proof_digest = "sha256:" + _digest(proof)
    source_refs = list(dict.fromkeys([
        record["provenance_ref"],
        *list(record.get("evidence_refs") or []),
    ]))
    verification_refs = list(record.get("verification_refs") or [])
    next_layers = remember(
        memory_layers,
        layer=record.get("layer") or "knowledge",
        content=record["content"],
        origin="GOVERNED:" + record["source_type"],
        category=record.get("category") or "fact",
        confidence=100,
        truth_state="CONFIRMED",
        valid_until=record.get("valid_until") or "",
        version="governed-v1",
        persona=record.get("persona") or "",
        domain=record.get("domain") or "CORE",
        source_refs=source_refs,
        memory_key=record.get("memory_key") or target,
        promotion_state="PROMOTED",
        governance_ref=target,
        taint_labels=[],
        provenance_chain=record.get("provenance_chain") or [],
        verification_refs=verification_refs,
        promotion_proof_digest=proof_digest,
    )
    promoted_rows = [
        row for row in next_layers["entries"]
        if row.get("governance_ref") == target
        and row.get("promotion_state") == "PROMOTED"
    ]
    if len(promoted_rows) != 1:
        raise RuntimeError("governed promotion did not produce exactly one memory row")
    promoted = deepcopy(record)
    promoted["state"] = "PROMOTED"
    promoted["review_approved"] = True
    promoted["reviewed_by"] = reviewer
    promoted["reviewed_at"] = reviewed_at
    promoted["promotion_proof_digest"] = proof_digest
    promoted["promoted_memory_id"] = promoted_rows[0]["memory_id"]
    proposals = [
        promoted if row["proposal_id"] == target else row
        for row in state["proposals"]
    ]
    next_state = normalize_memory_governance({"schema": SCHEMA, "proposals": proposals})
    return {
        "schema": SCHEMA,
        "state": "PROMOTED",
        "proposal": deepcopy(promoted),
        "promoted_memory": deepcopy(promoted_rows[0]),
        "governance": next_state,
        "memory_layers": next_layers,
        "action_authorized": False,
        "may_expand_permissions": False,
        "executes_action": False,
    }


def supersede_promoted_memory(
    governance: Mapping[str, Any] | None,
    proposal_id: Any,
    *,
    superseded_by: Any,
    reason: Any,
) -> dict[str, Any]:
    state = normalize_memory_governance(governance)
    target = _clean(proposal_id, 120)
    successor = _clean(superseded_by, 120)
    note = _clean(reason, 800)
    if not successor or not note:
        raise ValueError("supersession reference and reason required")
    record = next((row for row in state["proposals"] if row["proposal_id"] == target), None)
    if record is None:
        raise LookupError("memory proposal unavailable")
    if record["state"] != "PROMOTED":
        raise ValueError("only PROMOTED memory can be superseded")
    updated = deepcopy(record)
    updated["state"] = "SUPERSEDED"
    updated["superseded_by"] = successor
    updated["supersession_reason"] = note
    proposals = [
        updated if row["proposal_id"] == target else row
        for row in state["proposals"]
    ]
    next_state = normalize_memory_governance({"schema": SCHEMA, "proposals": proposals})
    return {
        "schema": SCHEMA,
        "state": "SUPERSEDED",
        "proposal": deepcopy(updated),
        "governance": next_state,
        "executes_action": False,
    }


def governed_memory_summary(governance: Mapping[str, Any] | None) -> dict[str, Any]:
    state = normalize_memory_governance(governance)
    rows = state["proposals"]
    return {
        "schema": SCHEMA,
        "total": len(rows),
        "by_state": {name: sum(row["state"] == name for row in rows) for name in STATES},
        "tainted": sum(bool(row.get("taint_labels")) for row in rows),
        "promoted": sum(row["state"] == "PROMOTED" for row in rows),
        "digest": state["digest"],
        "automatic_promotion": False,
        "memory_authority": "NONE",
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "STATES",
    "SOURCE_TYPES",
    "VERIFIER_KINDS",
    "default_memory_governance",
    "normalize_memory_governance",
    "propose_memory",
    "verify_memory_proposal",
    "promote_verified_memory",
    "supersede_promoted_memory",
    "governed_memory_summary",
]
