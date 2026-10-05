"""Tamper-evident independent verification ledger for AION.

This module records verification evidence. It does not execute external actions,
grant authority, or replace Guardian/approval. The ledger is append-only by
contract and hash-chains every verification event.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_VERIFICATION_LEDGER_V1"
VERSION = 1
GENESIS_HASH = "0" * 64
MAX_ENTRIES = 2000
VERIFIER_KINDS = ("CODE", "SOURCE_REQUERY", "HUMAN", "INDEPENDENT_MODEL")
RESULT_STATES = ("VERIFIED", "REJECTED", "INCONCLUSIVE")


def _clean(value: Any, limit: int = 600) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _upper(value: Any, limit: int = 80) -> str:
    return _clean(value, limit).upper()


def _refs(values: Sequence[Any] | None, limit: int = 80) -> list[str]:
    out: list[str] = []
    for raw in list(values or [])[: limit * 2]:
        value = _clean(raw, 320)
        if value and value not in out:
            out.append(value)
        if len(out) >= limit:
            break
    return out


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


def _scope(context: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(context or {})
    owner = _clean(raw.get("owner_id") or raw.get("actor_id"), 120)
    tenant = _clean(raw.get("tenant_id"), 120)
    workspace = _clean(raw.get("workspace_id"), 120)
    if not owner or not tenant or not workspace:
        raise ValueError("trusted owner/tenant/workspace required")
    return {"owner_id": owner, "tenant_id": tenant, "workspace_id": workspace}


def _entry_hash_payload(entry: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(entry)
    payload.pop("entry_hash", None)
    return payload


def _ledger_digest(entries: Sequence[Mapping[str, Any]], tip_hash: str) -> str:
    return _digest({
        "schema": SCHEMA,
        "version": VERSION,
        "tip_hash": tip_hash,
        "entries": list(entries),
        "append_only": True,
    })


def default_verification_ledger() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "entries": entries,
        "tip_hash": GENESIS_HASH,
        "digest": _ledger_digest(entries, GENESIS_HASH),
        "integrity_state": "MATCH",
        "append_only": True,
        "automatic_authority": False,
        "executes_action": False,
    }


def verify_ledger_integrity(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "state": "MISMATCH",
            "reason": "LEDGER_MAPPING_REQUIRED",
            "expected_digest": "",
            "stored_digest": "",
            "tip_hash": "",
            "entries": 0,
        }
    if raw.get("schema") != SCHEMA or raw.get("version") != VERSION:
        return {
            "state": "MISMATCH",
            "reason": "LEDGER_SCHEMA_OR_VERSION_MISMATCH",
            "expected_digest": "",
            "stored_digest": _clean(raw.get("digest"), 128),
            "tip_hash": _clean(raw.get("tip_hash"), 128),
            "entries": 0,
        }
    entries = list(raw.get("entries") or [])
    if len(entries) > MAX_ENTRIES:
        return {
            "state": "MISMATCH",
            "reason": "LEDGER_TOO_LARGE",
            "expected_digest": "",
            "stored_digest": _clean(raw.get("digest"), 128),
            "tip_hash": _clean(raw.get("tip_hash"), 128),
            "entries": len(entries),
        }

    previous = GENESIS_HASH
    seen_ids: set[str] = set()
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, Mapping):
            return {
                "state": "MISMATCH",
                "reason": "ENTRY_NOT_MAPPING",
                "entry_index": index,
                "expected_digest": "",
                "stored_digest": _clean(raw.get("digest"), 128),
                "tip_hash": previous,
                "entries": len(entries),
            }
        row = dict(item)
        entry_id = _clean(row.get("entry_id"), 120)
        if not entry_id or entry_id in seen_ids:
            return {
                "state": "MISMATCH",
                "reason": "ENTRY_ID_INVALID_OR_DUPLICATE",
                "entry_index": index,
                "expected_digest": "",
                "stored_digest": _clean(raw.get("digest"), 128),
                "tip_hash": previous,
                "entries": len(entries),
            }
        seen_ids.add(entry_id)
        if row.get("sequence") != index:
            return {
                "state": "MISMATCH",
                "reason": "ENTRY_SEQUENCE_MISMATCH",
                "entry_index": index,
                "expected_digest": "",
                "stored_digest": _clean(raw.get("digest"), 128),
                "tip_hash": previous,
                "entries": len(entries),
            }
        if _clean(row.get("previous_hash"), 64) != previous:
            return {
                "state": "MISMATCH",
                "reason": "HASH_CHAIN_PREVIOUS_MISMATCH",
                "entry_index": index,
                "expected_digest": "",
                "stored_digest": _clean(raw.get("digest"), 128),
                "tip_hash": previous,
                "entries": len(entries),
            }
        expected_hash = _digest(_entry_hash_payload(row))
        if _clean(row.get("entry_hash"), 64) != expected_hash:
            return {
                "state": "MISMATCH",
                "reason": "ENTRY_HASH_MISMATCH",
                "entry_index": index,
                "expected_entry_hash": expected_hash,
                "stored_entry_hash": _clean(row.get("entry_hash"), 64),
                "expected_digest": "",
                "stored_digest": _clean(raw.get("digest"), 128),
                "tip_hash": previous,
                "entries": len(entries),
            }
        previous = expected_hash

    stored_tip = _clean(raw.get("tip_hash"), 64)
    if stored_tip != previous:
        return {
            "state": "MISMATCH",
            "reason": "LEDGER_TIP_MISMATCH",
            "expected_digest": "",
            "stored_digest": _clean(raw.get("digest"), 128),
            "tip_hash": previous,
            "entries": len(entries),
        }
    expected_digest = _ledger_digest(entries, previous)
    stored_digest = _clean(raw.get("digest"), 64)
    return {
        "state": "MATCH" if stored_digest == expected_digest else "MISMATCH",
        "reason": "OK" if stored_digest == expected_digest else "LEDGER_DIGEST_MISMATCH",
        "expected_digest": expected_digest,
        "stored_digest": stored_digest,
        "tip_hash": previous,
        "entries": len(entries),
    }


def normalize_verification_ledger(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or not raw:
        return default_verification_ledger()
    report = verify_ledger_integrity(raw)
    entries = [
        deepcopy(dict(row))
        for row in list(raw.get("entries") or [])[:MAX_ENTRIES]
        if isinstance(row, Mapping)
    ]
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "entries": entries,
        "tip_hash": _clean(raw.get("tip_hash"), 64) or GENESIS_HASH,
        "digest": _clean(raw.get("digest"), 64),
        "integrity_state": report["state"],
        "integrity_reason": report["reason"],
        "append_only": True,
        "automatic_authority": False,
        "executes_action": False,
    }


def record_independent_verification(
    ledger: Mapping[str, Any] | None,
    *,
    claim_id: Any,
    claim_kind: Any,
    claim_digest: Any,
    generator_id: Any,
    verifier_kind: Any,
    verifier_id: Any,
    evidence_refs: Sequence[Any] | None,
    trusted_context: Mapping[str, Any] | None,
    verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    created_at: Any = None,
) -> dict[str, Any]:
    current = normalize_verification_ledger(ledger)
    if current["integrity_state"] != "MATCH":
        raise ValueError("verification ledger integrity mismatch")

    cid = _clean(claim_id, 160)
    ckind = _upper(claim_kind, 80)
    cdigest = _clean(claim_digest, 160)
    generator = _clean(generator_id, 160)
    vkind = _upper(verifier_kind, 40)
    vid = _clean(verifier_id, 160)
    refs = _refs(evidence_refs)
    scope = _scope(trusted_context)
    if not cid or not ckind or not cdigest or not generator:
        raise ValueError("claim binding incomplete")
    if vkind not in VERIFIER_KINDS or not vid:
        raise ValueError("approved verifier identity required")
    if not refs:
        raise ValueError("verification evidence refs required")
    if vid == generator:
        raise ValueError("generator and verifier must be independent principals")
    if not callable(verifier):
        raise TypeError("verifier callback required")

    envelope = {
        "schema": SCHEMA,
        "claim_id": cid,
        "claim_kind": ckind,
        "claim_digest": cdigest,
        "generator_id": generator,
        "verifier_kind": vkind,
        "verifier_id": vid,
        "evidence_refs": refs,
        **scope,
    }
    try:
        result = dict(verifier(deepcopy(envelope)) or {})
    except Exception as exc:
        result = {
            "state": "INCONCLUSIVE",
            "bound_claim_digest": "",
            "bound_refs": [],
            "independent": False,
            "reason": "VERIFIER_EXCEPTION:" + type(exc).__name__,
        }

    result_state = _upper(result.get("state"), 40)
    blockers: list[str] = []
    if result_state not in RESULT_STATES:
        blockers.append("VERIFIER_RESULT_STATE_INVALID")
        result_state = "INCONCLUSIVE"
    if result.get("independent") is not True:
        blockers.append("VERIFIER_INDEPENDENCE_NOT_PROVED")
    if _clean(result.get("verifier_id"), 160) != vid:
        blockers.append("VERIFIER_ID_BINDING_MISMATCH")
    if _clean(result.get("bound_claim_digest"), 160) != cdigest:
        blockers.append("CLAIM_DIGEST_BINDING_MISMATCH")
    bound_refs = _refs(
        result.get("bound_refs")
        if isinstance(result.get("bound_refs"), (list, tuple))
        else []
    )
    if sorted(bound_refs) != sorted(refs):
        blockers.append("EVIDENCE_REF_BINDING_MISMATCH")
    if blockers:
        result_state = "INCONCLUSIVE"

    sequence = len(current["entries"]) + 1
    previous = current["tip_hash"]
    event = {
        "schema": SCHEMA,
        "sequence": sequence,
        "entry_id": "VFY-" + _digest({
            "claim_id": cid,
            "claim_digest": cdigest,
            "verifier_id": vid,
            "sequence": sequence,
            "previous_hash": previous,
        })[:24].upper(),
        "previous_hash": previous,
        "claim_id": cid,
        "claim_kind": ckind,
        "claim_digest": cdigest,
        "generator_id": generator,
        "verifier_kind": vkind,
        "verifier_id": vid,
        "evidence_refs": refs,
        **scope,
        "result_state": result_state,
        "result_reason": _clean(result.get("reason"), 800),
        "blockers": sorted(set(blockers)),
        "result_digest": _digest({
            "state": result_state,
            "reason": _clean(result.get("reason"), 800),
            "bound_claim_digest": _clean(result.get("bound_claim_digest"), 160),
            "bound_refs": bound_refs,
            "independent": result.get("independent") is True,
            "verifier_id": _clean(result.get("verifier_id"), 160),
        }),
        "created_at": _aware(created_at).isoformat(),
        "authority": "NONE",
        "action_authorized": False,
        "executes_action": False,
    }
    event["entry_hash"] = _digest(_entry_hash_payload(event))
    entries = [*current["entries"], event][-MAX_ENTRIES:]

    # MAX_ENTRIES is a hard audit capacity. Do not roll the chain by dropping
    # earlier rows because doing so would destroy append-only continuity.
    if len(current["entries"]) >= MAX_ENTRIES:
        raise OverflowError("verification ledger capacity reached")
    tip = event["entry_hash"]
    next_ledger = {
        "schema": SCHEMA,
        "version": VERSION,
        "entries": entries,
        "tip_hash": tip,
        "digest": _ledger_digest(entries, tip),
        "integrity_state": "MATCH",
        "append_only": True,
        "automatic_authority": False,
        "executes_action": False,
    }
    return {
        "schema": SCHEMA,
        "state": result_state,
        "entry": deepcopy(event),
        "ledger": next_ledger,
        "authority": "NONE",
        "action_authorized": False,
        "executes_action": False,
    }


def find_verified_entry(
    ledger: Mapping[str, Any] | None,
    entry_id: Any,
    *,
    claim_id: Any,
    claim_digest: Any,
    trusted_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = normalize_verification_ledger(ledger)
    report = verify_ledger_integrity(current)
    if report["state"] != "MATCH":
        return {
            "schema": SCHEMA,
            "state": "BLOCK",
            "reason": "LEDGER_INTEGRITY_MISMATCH",
            "verified": False,
            "authority": "NONE",
            "executes_action": False,
        }
    scope = _scope(trusted_context)
    target = _clean(entry_id, 120)
    for row in current["entries"]:
        if row.get("entry_id") != target:
            continue
        if (
            row.get("claim_id") != _clean(claim_id, 160)
            or row.get("claim_digest") != _clean(claim_digest, 160)
        ):
            return {
                "schema": SCHEMA,
                "state": "BLOCK",
                "reason": "CLAIM_BINDING_MISMATCH",
                "verified": False,
                "authority": "NONE",
                "executes_action": False,
            }
        if any(row.get(key) != scope[key] for key in scope):
            return {
                "schema": SCHEMA,
                "state": "BLOCK",
                "reason": "SCOPE_MISMATCH",
                "verified": False,
                "authority": "NONE",
                "executes_action": False,
            }
        if row.get("result_state") != "VERIFIED" or row.get("blockers"):
            return {
                "schema": SCHEMA,
                "state": "BLOCK",
                "reason": "VERIFICATION_NOT_CONFIRMED",
                "verified": False,
                "authority": "NONE",
                "executes_action": False,
            }
        return {
            "schema": SCHEMA,
            "state": "VERIFIED",
            "verified": True,
            "entry": deepcopy(row),
            "entry_hash": row.get("entry_hash"),
            "authority": "NONE",
            "action_authorized": False,
            "executes_action": False,
        }
    return {
        "schema": SCHEMA,
        "state": "BLOCK",
        "reason": "VERIFICATION_ENTRY_MISSING",
        "verified": False,
        "authority": "NONE",
        "executes_action": False,
    }


def verification_ledger_summary(ledger: Mapping[str, Any] | None) -> dict[str, Any]:
    current = normalize_verification_ledger(ledger)
    integrity = verify_ledger_integrity(current)
    rows = current["entries"]
    return {
        "schema": SCHEMA,
        "entries": len(rows),
        "verified": sum(row.get("result_state") == "VERIFIED" for row in rows),
        "rejected": sum(row.get("result_state") == "REJECTED" for row in rows),
        "inconclusive": sum(row.get("result_state") == "INCONCLUSIVE" for row in rows),
        "tip_hash": current["tip_hash"],
        "digest": current["digest"],
        "integrity_state": integrity["state"],
        "append_only": True,
        "automatic_authority": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "GENESIS_HASH",
    "MAX_ENTRIES",
    "VERIFIER_KINDS",
    "RESULT_STATES",
    "default_verification_ledger",
    "normalize_verification_ledger",
    "verify_ledger_integrity",
    "record_independent_verification",
    "find_verified_entry",
    "verification_ledger_summary",
]
