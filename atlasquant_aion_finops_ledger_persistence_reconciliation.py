"""AION FinOps Ledger Persistence & Invoice Reconciliation V1.

Pure/read-only governance contracts for:
- versioning verified FinOps ledgers;
- binding each version to the previous version digest;
- detecting version gaps, replay and tampering;
- reconciling externally attested invoice totals against verified ledger entries.

This module does not persist files, write databases, call providers, pay invoices,
change subscriptions, move money, alter prices, deploy or activate runtime.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_finops_live_cost_ledger import (
    SCHEMA as LIVE_LEDGER_SCHEMA,
    GENESIS_DIGEST,
    verify_hash_chained_ledger,
)

SCHEMA = "ATLASQUANT_AION_FINOPS_LEDGER_PERSISTENCE_RECONCILIATION_V1"
VERSION = "1"
MAX_VERSION_CHAIN = 500
MAX_RECONCILIATION_TOLERANCE_BRL = 5.0


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _num(value: Any, *, minimum: float = 0.0, maximum: float | None = None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _parse_time(value: Any) -> datetime | None:
    token = _clean(value, 80)
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def persistence_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "VERSIONED_LEDGER_PERSISTENCE_CONTRACT_DEFINED",
        "storage_model": "IMMUTABLE_VERSION_MANIFEST_CHAIN",
        "physical_persistence_executed_here": False,
        "provider_called_here": False,
        "invoice_paid_here": False,
        "subscription_changed_here": False,
        "automatic_price_change": False,
        "automatic_reconciliation_writeback": False,
        "executes_action": False,
    }


def build_ledger_version_manifest(
    ledger: Mapping[str, Any] | None,
    *,
    version_number: Any,
    previous_version_manifest_digest: Any,
    storage_ref: Any,
    created_at: Any,
    created_by: Any,
) -> dict[str, Any]:
    ledger_row = _mapping(ledger)
    verified = verify_hash_chained_ledger(ledger_row)

    version_no = (
        version_number
        if isinstance(version_number, int)
        and not isinstance(version_number, bool)
        and 1 <= version_number <= MAX_VERSION_CHAIN
        else None
    )
    previous = _clean(previous_version_manifest_digest, 80).lower()
    storage = _clean(storage_ref, 300)
    created = _parse_time(created_at)
    actor = _clean(created_by, 120)

    blockers: list[str] = []
    if verified.get("valid") is not True:
        blockers.append("LEDGER_NOT_VERIFIED")
    if version_no is None:
        blockers.append("VERSION_NUMBER_INVALID")
    if len(previous) != 64 or any(ch not in "0123456789abcdef" for ch in previous):
        blockers.append("PREVIOUS_MANIFEST_DIGEST_INVALID")
    if version_no == 1 and previous != GENESIS_DIGEST:
        blockers.append("VERSION_ONE_MUST_BIND_GENESIS")
    if version_no and version_no > 1 and previous == GENESIS_DIGEST:
        blockers.append("NON_GENESIS_VERSION_CANNOT_BIND_GENESIS")
    if not storage:
        blockers.append("STORAGE_REF_REQUIRED")
    if created is None:
        blockers.append("CREATED_AT_INVALID")
    if not actor:
        blockers.append("CREATED_BY_REQUIRED")

    ready = not blockers
    payload = {
        "version_number": version_no,
        "previous_version_manifest_digest": previous,
        "storage_ref": storage,
        "created_at": created.isoformat() if created else "",
        "created_by": actor,
        "ledger_schema": ledger_row.get("schema"),
        "ledger_digest": ledger_row.get("ledger_digest"),
        "ledger_tail_digest": ledger_row.get("tail_digest"),
        "ledger_entry_count": ledger_row.get("entry_count"),
    } if ready else {}

    manifest_digest = _digest(payload) if ready else ""
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LEDGER_VERSION_MANIFEST_READY" if ready else "LEDGER_VERSION_MANIFEST_BLOCKED",
        **payload,
        "version_manifest_digest": manifest_digest,
        "blockers": blockers,
        "immutable_requested": True,
        "physical_persistence_confirmed": False,
        "persistence_authorized": False,
        "invoice_payment_authorized": False,
        "executes_action": False,
    }


def verify_version_manifest_chain(
    manifests: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = (
        [dict(x) for x in manifests if isinstance(x, Mapping)]
        if isinstance(manifests, Sequence) and not isinstance(manifests, (str, bytes, bytearray))
        else []
    )
    if not rows or len(rows) > MAX_VERSION_CHAIN:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "LEDGER_VERSION_CHAIN_INVALID",
            "valid": False,
            "reason": "CHAIN_SIZE_INVALID",
            "executes_action": False,
        }

    ordered = sorted(rows, key=lambda x: x.get("version_number") or 0)
    seen_digests: set[str] = set()
    previous_digest = GENESIS_DIGEST

    for expected_version, row in enumerate(ordered, start=1):
        if row.get("schema") != SCHEMA or row.get("state") != "LEDGER_VERSION_MANIFEST_READY":
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "LEDGER_VERSION_CHAIN_INVALID",
                "valid": False,
                "reason": "MANIFEST_STATE_INVALID",
                "executes_action": False,
            }
        if row.get("version_number") != expected_version:
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "LEDGER_VERSION_CHAIN_INVALID",
                "valid": False,
                "reason": "VERSION_GAP_OR_REORDER",
                "executes_action": False,
            }
        if row.get("previous_version_manifest_digest") != previous_digest:
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "LEDGER_VERSION_CHAIN_INVALID",
                "valid": False,
                "reason": "PREVIOUS_VERSION_DIGEST_MISMATCH",
                "executes_action": False,
            }

        payload = {
            "version_number": row.get("version_number"),
            "previous_version_manifest_digest": row.get("previous_version_manifest_digest"),
            "storage_ref": row.get("storage_ref"),
            "created_at": row.get("created_at"),
            "created_by": row.get("created_by"),
            "ledger_schema": row.get("ledger_schema"),
            "ledger_digest": row.get("ledger_digest"),
            "ledger_tail_digest": row.get("ledger_tail_digest"),
            "ledger_entry_count": row.get("ledger_entry_count"),
        }
        actual = _digest(payload)
        if actual != row.get("version_manifest_digest"):
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "LEDGER_VERSION_CHAIN_INVALID",
                "valid": False,
                "reason": "VERSION_MANIFEST_DIGEST_MISMATCH",
                "executes_action": False,
            }
        if actual in seen_digests:
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "LEDGER_VERSION_CHAIN_INVALID",
                "valid": False,
                "reason": "VERSION_REPLAY_DETECTED",
                "executes_action": False,
            }

        seen_digests.add(actual)
        previous_digest = actual

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LEDGER_VERSION_CHAIN_VERIFIED",
        "valid": True,
        "version_count": len(ordered),
        "latest_version_number": ordered[-1].get("version_number"),
        "latest_version_manifest_digest": previous_digest,
        "physical_persistence_confirmed": False,
        "executes_action": False,
    }


def invoice_attestation(
    *,
    provider_ref: Any,
    invoice_ref: Any,
    source_ref: Any,
    period_start: Any,
    period_end: Any,
    total_brl: Any,
    currency: Any,
    authentication_verified: Any,
    read_only_scope_verified: Any,
    signature_or_source_integrity_verified: Any,
    observed_at: Any,
) -> dict[str, Any]:
    provider = _clean(provider_ref, 160)
    invoice = _clean(invoice_ref, 180)
    source = _clean(source_ref, 300)
    start = _parse_time(period_start)
    end = _parse_time(period_end)
    total = _num(total_brl, maximum=100_000_000)
    curr = _clean(currency, 8).upper()
    observed = _parse_time(observed_at)

    gates = {
        "provider_ref_present": bool(provider),
        "invoice_ref_present": bool(invoice),
        "source_ref_present": bool(source),
        "period_valid": bool(start and end and end >= start),
        "total_valid": total is not None,
        "currency_brl": curr == "BRL",
        "authentication_verified": authentication_verified is True,
        "read_only_scope_verified": read_only_scope_verified is True,
        "source_integrity_verified": signature_or_source_integrity_verified is True,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())
    payload = {
        "provider_ref": provider,
        "invoice_ref": invoice,
        "source_ref": source,
        "period_start": start.isoformat() if start else "",
        "period_end": end.isoformat() if end else "",
        "total_brl": round(total, 2) if total is not None else None,
        "currency": curr,
        "observed_at": observed.isoformat() if observed else "",
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "INVOICE_ATTESTATION_READY" if ready else "INVOICE_ATTESTATION_BLOCKED",
        **payload,
        "gates": gates,
        "invoice_attestation_digest": _digest(payload) if ready else "",
        "invoice_paid": False,
        "automatic_payment": False,
        "executes_action": False,
    }


def reconcile_invoice_to_ledger(
    invoice: Mapping[str, Any] | None,
    ledger: Mapping[str, Any] | None,
    *,
    tolerance_brl: Any = 0.01,
) -> dict[str, Any]:
    inv = _mapping(invoice)
    ledger_row = _mapping(ledger)
    verified = verify_hash_chained_ledger(ledger_row)
    tolerance = _num(
        tolerance_brl,
        maximum=MAX_RECONCILIATION_TOLERANCE_BRL,
    )

    blockers: list[str] = []
    if inv.get("schema") != SCHEMA or inv.get("state") != "INVOICE_ATTESTATION_READY":
        blockers.append("INVOICE_NOT_ATTESTED")
    if verified.get("valid") is not True:
        blockers.append("LEDGER_NOT_VERIFIED")
    if tolerance is None:
        blockers.append("TOLERANCE_INVALID")

    provider = _clean(inv.get("provider_ref"), 160)
    start = _parse_time(inv.get("period_start"))
    end = _parse_time(inv.get("period_end"))
    expected_total = _num(inv.get("total_brl"), maximum=100_000_000)

    matched_entries: list[dict[str, Any]] = []
    ledger_total = 0.0
    if not blockers and isinstance(ledger_row.get("entries"), list):
        for raw in ledger_row["entries"]:
            entry = _mapping(raw)
            entry_start = _parse_time(entry.get("period_start"))
            entry_end = _parse_time(entry.get("period_end"))
            if (
                entry.get("provider_ref") == provider
                and entry_start == start
                and entry_end == end
            ):
                amount = _num(entry.get("amount_brl"), maximum=100_000_000)
                if amount is not None:
                    ledger_total += amount
                    matched_entries.append({
                        "entry_id": entry.get("entry_id"),
                        "entry_digest": entry.get("entry_digest"),
                        "amount_brl": amount,
                    })

    ledger_total = round(ledger_total, 2)
    difference = (
        round(ledger_total - expected_total, 2)
        if expected_total is not None
        else None
    )
    matched = bool(
        not blockers
        and matched_entries
        and difference is not None
        and abs(difference) <= tolerance
    )

    if not blockers and not matched_entries:
        blockers.append("NO_LEDGER_ENTRIES_FOR_INVOICE")
    elif not blockers and not matched:
        blockers.append("INVOICE_LEDGER_TOTAL_MISMATCH")

    payload = {
        "invoice_attestation_digest": inv.get("invoice_attestation_digest"),
        "ledger_digest": ledger_row.get("ledger_digest"),
        "matched_entry_digests": [x["entry_digest"] for x in matched_entries],
        "ledger_total_brl": ledger_total,
        "invoice_total_brl": expected_total,
        "difference_brl": difference,
        "tolerance_brl": tolerance,
    } if matched else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "INVOICE_LEDGER_RECONCILED" if matched else "INVOICE_LEDGER_RECONCILIATION_BLOCKED",
        "provider_ref": provider if matched else "",
        "invoice_ref": inv.get("invoice_ref") if matched else "",
        "matched_entry_count": len(matched_entries),
        "matched_entries": matched_entries,
        "ledger_total_brl": ledger_total,
        "invoice_total_brl": expected_total,
        "difference_brl": difference,
        "tolerance_brl": tolerance,
        "blockers": blockers,
        "reconciliation_digest": _digest(payload) if matched else "",
        "invoice_paid": False,
        "payment_authorized": False,
        "ledger_writeback_authorized": False,
        "executes_action": False,
    }


def persistence_and_reconciliation_review_packet(
    version_chain: Sequence[Mapping[str, Any]] | None,
    reconciliation: Mapping[str, Any] | None,
    *,
    requested_by: Any,
) -> dict[str, Any]:
    chain = verify_version_manifest_chain(version_chain)
    recon = _mapping(reconciliation)
    requester = _clean(requested_by, 120)

    gates = {
        "version_chain_verified": chain.get("valid") is True,
        "invoice_reconciled": recon.get("state") == "INVOICE_LEDGER_RECONCILED",
        "reconciliation_digest_present": bool(_clean(recon.get("reconciliation_digest"), 128)),
        "requester_present": bool(requester),
        "invoice_unpaid": recon.get("invoice_paid") is False,
        "payment_not_authorized": recon.get("payment_authorized") is False,
    }
    blockers = [name for name, passed in gates.items() if not passed]
    ready = not blockers

    payload = {
        "latest_version_manifest_digest": chain.get("latest_version_manifest_digest"),
        "reconciliation_digest": recon.get("reconciliation_digest"),
        "requested_by": requester,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": (
            "READY_FOR_ADMIN_PERSISTENCE_RECONCILIATION_REVIEW"
            if ready
            else "PERSISTENCE_RECONCILIATION_REVIEW_BLOCKED"
        ),
        "gates": gates,
        "blockers": blockers,
        "review_digest": _digest(payload) if ready else "",
        "physical_persistence_authorized": False,
        "invoice_payment_authorized": False,
        "subscription_change_authorized": False,
        "price_change_authorized": False,
        "runtime_authorized": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "MAX_VERSION_CHAIN",
    "MAX_RECONCILIATION_TOLERANCE_BRL",
    "persistence_policy",
    "build_ledger_version_manifest",
    "verify_version_manifest_chain",
    "invoice_attestation",
    "reconcile_invoice_to_ledger",
    "persistence_and_reconciliation_review_packet",
]
