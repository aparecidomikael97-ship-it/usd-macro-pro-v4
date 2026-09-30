"""AION BUSINESS expansion cycle audit ledger V1.

Pure administrative ledger for verified BUSINESS expansion cycles. It records
only receipts already verified and frozen by the post-expansion boundary.

The ledger never expands tenants, changes runtime, deploys, rolls back, bills,
publishes, contacts clients, or calls external systems.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

VERIFICATION_SCHEMA = "ATLASQUANT_AION_BUSINESS_POST_EXPANSION_CYCLE_FREEZE_V1"
BOUNDARY_SCHEMA = "ATLASQUANT_AION_BUSINESS_SCOPE_EXPANSION_BOUNDARY_PACKET_V1"
SCHEMA = "ATLASQUANT_AION_BUSINESS_EXPANSION_CYCLE_AUDIT_LEDGER_V1"
VERSION = "1"

_DIGEST64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_SCOPES = ("sandbox", "pilot", "bounded_production")
MAX_BOUNDED_TENANTS = 10
MAX_LEDGER_ENTRIES = 1000


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _tenant_ids(value: Any) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    result: list[str] = []
    for item in value:
        text = _clean(item, 120)
        if text and text not in result:
            result.append(text)
        if len(result) > MAX_BOUNDED_TENANTS:
            break
    return result


def _scope_rank(scope: str) -> int:
    try:
        return ALLOWED_SCOPES.index(scope)
    except ValueError:
        return -1


def _valid_scope_tenants(scope: str, tenants: Sequence[str]) -> bool:
    return bool(
        (scope == "sandbox" and not tenants)
        or (
            scope in {"pilot", "bounded_production"}
            and 1 <= len(tenants) <= MAX_BOUNDED_TENANTS
        )
    )


def _valid_transition(
    previous_scope: str,
    previous_tenants: Sequence[str],
    verified_scope: str,
    verified_tenants: Sequence[str],
) -> bool:
    previous_rank = _scope_rank(previous_scope)
    verified_rank = _scope_rank(verified_scope)
    return bool(
        previous_rank >= 0
        and verified_rank >= 0
        and verified_scope in {"pilot", "bounded_production"}
        and _valid_scope_tenants(previous_scope, previous_tenants)
        and _valid_scope_tenants(verified_scope, verified_tenants)
        and set(previous_tenants).issubset(set(verified_tenants))
        and verified_rank in {previous_rank, previous_rank + 1}
        and (
            verified_rank == previous_rank + 1
            or len(verified_tenants) > len(previous_tenants)
        )
        and not (
            previous_scope == "sandbox"
            and verified_scope != "pilot"
        )
        and not (
            previous_scope == "bounded_production"
            and verified_scope != "bounded_production"
        )
    )


def expansion_cycle_ledger_template(
    genesis_boundary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    boundary = _mapping(genesis_boundary)
    genesis_digest = _clean(
        boundary.get("activation_verification_digest"), 128
    ).lower()
    genesis_scope = _clean(boundary.get("current_scope"), 80).lower()
    genesis_tenants = _tenant_ids(boundary.get("current_tenant_ids"))

    genesis_bound = bool(
        boundary.get("schema") == BOUNDARY_SCHEMA
        and boundary.get("state") == "EXPLICIT_EXPANSION_DECISION_REQUIRED"
        and _DIGEST64.fullmatch(genesis_digest)
        and _valid_scope_tenants(genesis_scope, genesis_tenants)
        and boundary.get("generic_confirmation_is_authorization") is False
        and boundary.get("automatic_expansion_allowed") is False
        and boundary.get("scope_expansion_authorized") is False
        and boundary.get("expansion_execution_authorized") is False
        and boundary.get("client_actions_authorized") is False
        and boundary.get("billing_authorized") is False
        and boundary.get("executes_action") is False
    )

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "EXPANSION_CYCLE_AUDIT_LEDGER_EMPTY"
            if genesis_bound
            else "EXPANSION_CYCLE_LEDGER_GENESIS_REQUIRED"
        ),
        "genesis_bound": genesis_bound,
        "genesis_verification_digest": genesis_digest if genesis_bound else "",
        "genesis_scope": genesis_scope if genesis_bound else "",
        "genesis_tenant_ids": genesis_tenants if genesis_bound else [],
        "entry_count": 0,
        "entries": [],
        "ledger_digest": "",
        "integrity_verified": True,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def audit_expansion_cycle_ledger(
    ledger: Mapping[str, Any] | None,
) -> dict[str, Any]:
    row = _mapping(ledger)
    entries = row.get("entries")
    if not isinstance(entries, list):
        entries = []

    blockers: list[str] = []
    genesis_bound = row.get("genesis_bound") is True
    genesis_digest = _clean(row.get("genesis_verification_digest"), 128).lower()
    genesis_scope = _clean(row.get("genesis_scope"), 80).lower()
    genesis_tenants = _tenant_ids(row.get("genesis_tenant_ids"))

    if genesis_bound:
        if not _DIGEST64.fullmatch(genesis_digest):
            blockers.append("genesis_digest_invalid")
        if not _valid_scope_tenants(genesis_scope, genesis_tenants):
            blockers.append("genesis_scope_invalid")
    elif entries:
        blockers.append("genesis_required_for_entries")

    if row.get("schema") != SCHEMA:
        blockers.append("schema_invalid")
    if row.get("version") != VERSION:
        blockers.append("version_invalid")
    if len(entries) > MAX_LEDGER_ENTRIES:
        blockers.append("entry_limit_exceeded")
    if row.get("entry_count") != len(entries):
        blockers.append("entry_count_mismatch")
    for flag in (
        "automatic_expansion_allowed",
        "scope_expansion_authorized",
        "expansion_execution_authorized",
        "client_actions_authorized",
        "billing_authorized",
        "executes_action",
    ):
        if row.get(flag) is not False:
            blockers.append(f"{flag}_must_be_false")

    previous_entry_digest = ""
    previous_verified_scope = ""
    previous_verified_tenants: list[str] = []
    seen_verification_digests: set[str] = set()

    for index, raw_entry in enumerate(entries, start=1):
        entry = _mapping(raw_entry)
        verification_digest = _clean(
            entry.get("expansion_verification_digest"), 128
        ).lower()
        entry_digest = _clean(entry.get("entry_digest"), 128).lower()
        previous_scope = _clean(entry.get("previous_scope"), 80).lower()
        verified_scope = _clean(entry.get("verified_scope"), 80).lower()
        previous_tenants = _tenant_ids(entry.get("previous_tenant_ids"))
        verified_tenants = _tenant_ids(entry.get("verified_tenant_ids"))

        if entry.get("sequence") != index:
            blockers.append(f"entry_{index}_sequence_invalid")
        if not _DIGEST64.fullmatch(verification_digest):
            blockers.append(f"entry_{index}_verification_digest_invalid")
        if verification_digest in seen_verification_digests:
            blockers.append(f"entry_{index}_verification_replay")
        seen_verification_digests.add(verification_digest)

        if entry.get("previous_entry_digest") != previous_entry_digest:
            blockers.append(f"entry_{index}_previous_digest_mismatch")

        if not _valid_transition(
            previous_scope,
            previous_tenants,
            verified_scope,
            verified_tenants,
        ):
            blockers.append(f"entry_{index}_transition_invalid")

        if index == 1 and genesis_bound:
            if previous_scope != genesis_scope:
                blockers.append("entry_1_genesis_scope_mismatch")
            if sorted(previous_tenants) != sorted(genesis_tenants):
                blockers.append("entry_1_genesis_tenant_mismatch")
        elif index > 1:
            if previous_scope != previous_verified_scope:
                blockers.append(f"entry_{index}_scope_continuity_broken")
            if sorted(previous_tenants) != sorted(previous_verified_tenants):
                blockers.append(f"entry_{index}_tenant_continuity_broken")

        payload = {
            "sequence": index,
            "previous_entry_digest": previous_entry_digest,
            "expansion_verification_digest": verification_digest,
            "authorization_digest": _clean(
                entry.get("authorization_digest"), 128
            ).lower(),
            "previous_scope": previous_scope,
            "previous_tenant_ids": sorted(previous_tenants),
            "verified_scope": verified_scope,
            "verified_tenant_ids": sorted(verified_tenants),
        }
        expected_entry_digest = _digest(payload)
        if entry_digest != expected_entry_digest:
            blockers.append(f"entry_{index}_digest_mismatch")

        previous_entry_digest = entry_digest
        previous_verified_scope = verified_scope
        previous_verified_tenants = verified_tenants

    expected_ledger_digest = previous_entry_digest if entries else ""
    if _clean(row.get("ledger_digest"), 128).lower() != expected_ledger_digest:
        blockers.append("ledger_digest_mismatch")

    expected_state = (
        "EXPANSION_CYCLE_AUDIT_LEDGER_VERIFIED"
        if entries
        else (
            "EXPANSION_CYCLE_AUDIT_LEDGER_EMPTY"
            if genesis_bound
            else "EXPANSION_CYCLE_LEDGER_GENESIS_REQUIRED"
        )
    )
    if row.get("state") != expected_state:
        blockers.append("state_mismatch")

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LEDGER_INTEGRITY_VERIFIED" if not blockers else "LEDGER_INTEGRITY_BLOCKED",
        "integrity_verified": not blockers,
        "entry_count": len(entries),
        "genesis_bound": genesis_bound,
        "genesis_verification_digest": genesis_digest if genesis_bound and not blockers else "",
        "genesis_scope": genesis_scope if genesis_bound and not blockers else "",
        "genesis_tenant_ids": genesis_tenants if genesis_bound and not blockers else [],
        "ledger_digest": expected_ledger_digest if not blockers else "",
        "last_verified_scope": previous_verified_scope if entries and not blockers else "",
        "last_verified_tenant_ids": (
            previous_verified_tenants if entries and not blockers else []
        ),
        "blockers": blockers,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


def append_verified_expansion_cycle(
    ledger: Mapping[str, Any] | None,
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = _mapping(ledger)
    verification_row = _mapping(verification)

    audit = audit_expansion_cycle_ledger(current)
    if not audit.get("integrity_verified"):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "EXPANSION_CYCLE_APPEND_BLOCKED",
            "blockers": ["ledger_integrity_invalid"],
            "ledger": current,
            "automatic_expansion_allowed": False,
            "scope_expansion_authorized": False,
            "expansion_execution_authorized": False,
            "client_actions_authorized": False,
            "billing_authorized": False,
            "executes_action": False,
        }

    if current.get("genesis_bound") is not True:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "EXPANSION_CYCLE_APPEND_BLOCKED",
            "blockers": ["genesis_boundary_required"],
            "ledger": current,
            "automatic_expansion_allowed": False,
            "scope_expansion_authorized": False,
            "expansion_execution_authorized": False,
            "client_actions_authorized": False,
            "billing_authorized": False,
            "executes_action": False,
        }

    entries = [dict(item) for item in current.get("entries", []) if isinstance(item, Mapping)]
    if len(entries) >= MAX_LEDGER_ENTRIES:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "EXPANSION_CYCLE_APPEND_BLOCKED",
            "blockers": ["entry_limit_reached"],
            "ledger": current,
            "automatic_expansion_allowed": False,
            "scope_expansion_authorized": False,
            "expansion_execution_authorized": False,
            "client_actions_authorized": False,
            "billing_authorized": False,
            "executes_action": False,
        }

    verification_digest = _clean(
        verification_row.get("expansion_verification_digest"), 128
    ).lower()
    authorization_digest = _clean(
        verification_row.get("authorization_digest"), 128
    ).lower()
    previous_scope = _clean(verification_row.get("previous_scope"), 80).lower()
    verified_scope = _clean(verification_row.get("verified_scope"), 80).lower()
    previous_tenants = _tenant_ids(verification_row.get("previous_tenant_ids"))
    verified_tenants = _tenant_ids(verification_row.get("verified_tenant_ids"))

    verification_ok = bool(
        verification_row.get("schema") == VERIFICATION_SCHEMA
        and verification_row.get("state") == "SCOPE_EXPANSION_VERIFIED_AND_FROZEN"
        and verification_row.get("scope_expansion_verified") is True
        and verification_row.get("scope_frozen") is True
        and _DIGEST64.fullmatch(verification_digest)
        and _DIGEST64.fullmatch(authorization_digest)
        and verification_row.get("automatic_expansion_allowed") is False
        and verification_row.get("scope_expansion_authorized") is False
        and verification_row.get("expansion_execution_authorized") is False
        and verification_row.get("client_actions_authorized") is False
        and verification_row.get("billing_authorized") is False
        and verification_row.get("executes_action") is False
        and _valid_transition(
            previous_scope,
            previous_tenants,
            verified_scope,
            verified_tenants,
        )
    )

    blockers: list[str] = []
    if not verification_ok:
        blockers.append("verification_invalid")

    existing_digests = {
        _clean(item.get("expansion_verification_digest"), 128).lower()
        for item in entries
    }
    if verification_digest in existing_digests:
        blockers.append("verification_replay")

    if entries:
        last = _mapping(entries[-1])
        last_scope = _clean(last.get("verified_scope"), 80).lower()
        last_tenants = _tenant_ids(last.get("verified_tenant_ids"))
        if previous_scope != last_scope:
            blockers.append("scope_continuity_broken")
        if sorted(previous_tenants) != sorted(last_tenants):
            blockers.append("tenant_continuity_broken")
    else:
        genesis_scope = _clean(current.get("genesis_scope"), 80).lower()
        genesis_tenants = _tenant_ids(current.get("genesis_tenant_ids"))
        if previous_scope != genesis_scope:
            blockers.append("genesis_scope_mismatch")
        if sorted(previous_tenants) != sorted(genesis_tenants):
            blockers.append("genesis_tenant_mismatch")

    if blockers:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "EXPANSION_CYCLE_APPEND_BLOCKED",
            "blockers": blockers,
            "ledger": current,
            "automatic_expansion_allowed": False,
            "scope_expansion_authorized": False,
            "expansion_execution_authorized": False,
            "client_actions_authorized": False,
            "billing_authorized": False,
            "executes_action": False,
        }

    sequence = len(entries) + 1
    previous_entry_digest = _clean(current.get("ledger_digest"), 128).lower()
    payload = {
        "sequence": sequence,
        "previous_entry_digest": previous_entry_digest,
        "expansion_verification_digest": verification_digest,
        "authorization_digest": authorization_digest,
        "previous_scope": previous_scope,
        "previous_tenant_ids": sorted(previous_tenants),
        "verified_scope": verified_scope,
        "verified_tenant_ids": sorted(verified_tenants),
    }
    entry = dict(payload)
    entry["entry_digest"] = _digest(payload)
    entries.append(entry)

    next_ledger = {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "EXPANSION_CYCLE_AUDIT_LEDGER_VERIFIED",
        "genesis_bound": True,
        "genesis_verification_digest": current.get("genesis_verification_digest"),
        "genesis_scope": current.get("genesis_scope"),
        "genesis_tenant_ids": list(current.get("genesis_tenant_ids") or []),
        "entry_count": len(entries),
        "entries": entries,
        "ledger_digest": entry["entry_digest"],
        "integrity_verified": True,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }
    final_audit = audit_expansion_cycle_ledger(next_ledger)
    if not final_audit.get("integrity_verified"):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "EXPANSION_CYCLE_APPEND_BLOCKED",
            "blockers": ["post_append_integrity_failed"],
            "ledger": current,
            "automatic_expansion_allowed": False,
            "scope_expansion_authorized": False,
            "expansion_execution_authorized": False,
            "client_actions_authorized": False,
            "billing_authorized": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "VERIFIED_EXPANSION_CYCLE_RECORDED",
        "blockers": [],
        "ledger": next_ledger,
        "automatic_expansion_allowed": False,
        "scope_expansion_authorized": False,
        "expansion_execution_authorized": False,
        "client_actions_authorized": False,
        "billing_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "VERIFICATION_SCHEMA",
    "BOUNDARY_SCHEMA",
    "ALLOWED_SCOPES",
    "MAX_BOUNDED_TENANTS",
    "MAX_LEDGER_ENTRIES",
    "expansion_cycle_ledger_template",
    "audit_expansion_cycle_ledger",
    "append_verified_expansion_cycle",
]
