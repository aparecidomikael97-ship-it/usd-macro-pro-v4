"""AION FinOps Live Cost Ledger V1.

Read-only / pure contracts for externally verified cost observations and an
append-only, hash-chained FinOps ledger.

This module does not call providers, read invoices from the network, persist the
ledger, pay bills, alter subscriptions, move money, change prices, or activate
runtime. Persistence and provider connectors remain separate gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import math

from atlasquant_aion_finops_budget_governor import (
    INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
    evaluate_monthly_budget,
)

SCHEMA = "ATLASQUANT_AION_FINOPS_LIVE_COST_LEDGER_V1"
VERSION = "1"

COST_CATEGORIES = (
    "AI_PROVIDER",
    "HOSTING",
    "MARKET_DATA",
    "INTEGRATION",
    "VOICE",
    "VIDEO",
    "MESSAGING",
    "STORAGE",
    "OBSERVABILITY",
    "PAYMENT_FEES",
    "OTHER",
)

MAX_ENTRIES = 2000
MAX_AGE_HOURS = 24 * 45
GENESIS_DIGEST = "0" * 64


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


def live_cost_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "FINOPS_LIVE_COST_CONTRACT_DEFINED",
        "categories": list(COST_CATEGORIES),
        "ledger_model": "APPEND_ONLY_HASH_CHAIN",
        "genesis_digest": GENESIS_DIGEST,
        "monthly_cap_brl": INITIAL_MONTHLY_ECOSYSTEM_CAP_BRL,
        "provider_connector_executes_here": False,
        "ledger_persisted_here": False,
        "raw_credentials_allowed": False,
        "automatic_payment": False,
        "automatic_subscription_change": False,
        "automatic_price_change": False,
        "executes_action": False,
    }


def provider_cost_attestation(
    *,
    provider_ref: Any,
    connection_ref: Any,
    authentication_verified: Any,
    read_only_scope_verified: Any,
    write_scope_present: Any,
    credential_value_present: Any,
    observed_at: Any,
) -> dict[str, Any]:
    provider = _clean(provider_ref, 160)
    connection = _clean(connection_ref, 240)
    observed = _parse_time(observed_at)
    gates = {
        "provider_ref_present": bool(provider),
        "connection_ref_present": bool(connection),
        "authentication_verified": authentication_verified is True,
        "read_only_scope_verified": read_only_scope_verified is True,
        "write_scope_absent": write_scope_present is False,
        "credential_value_absent": credential_value_present is False,
        "observed_at_valid": observed is not None,
    }
    ready = all(gates.values())
    payload = {
        "provider_ref": provider,
        "connection_ref": connection,
        "observed_at": observed.isoformat() if observed else "",
        "read_only_scope_verified": True,
    } if ready else {}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "PROVIDER_COST_ATTESTATION_READY" if ready else "PROVIDER_COST_ATTESTATION_BLOCKED",
        "provider_ref": provider if ready else "",
        "connection_ref": connection if ready else "",
        "observed_at": observed.isoformat() if ready and observed else "",
        "gates": gates,
        "attestation_digest": _digest(payload) if payload else "",
        "provider_called_by_module": False,
        "write_scope_present": False if ready else None,
        "credential_value_present": False if ready else None,
        "executes_action": False,
    }


def normalize_cost_observations(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    attestations: Sequence[Mapping[str, Any]] | None,
    now: datetime | None = None,
    max_age_hours: Any = MAX_AGE_HOURS,
) -> dict[str, Any]:
    current = now.astimezone(timezone.utc) if isinstance(now, datetime) else datetime.now(timezone.utc)
    age_limit = _num(max_age_hours, minimum=0.01, maximum=MAX_AGE_HOURS)
    blockers: list[str] = []
    if age_limit is None:
        blockers.append("MAX_AGE_INVALID")
        age_limit = MAX_AGE_HOURS

    attested: dict[str, dict[str, Any]] = {}
    raw_attestations = (
        list(attestations)
        if isinstance(attestations, Sequence) and not isinstance(attestations, (str, bytes, bytearray))
        else []
    )
    for raw in raw_attestations:
        item = _mapping(raw)
        if item.get("schema") == SCHEMA and item.get("state") == "PROVIDER_COST_ATTESTATION_READY":
            ref = _clean(item.get("provider_ref"), 160)
            if ref:
                attested[ref] = item

    raw_rows = (
        list(rows)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes, bytearray))
        else []
    )
    if not raw_rows:
        blockers.append("COST_OBSERVATIONS_REQUIRED")
    if len(raw_rows) > MAX_ENTRIES:
        blockers.append("COST_OBSERVATION_LIMIT_EXCEEDED")
        raw_rows = raw_rows[:MAX_ENTRIES]

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_rows, start=1):
        row = _mapping(raw)
        entry_id = _clean(row.get("entry_id"), 160)
        provider_ref = _clean(row.get("provider_ref"), 160)
        source_ref = _clean(row.get("source_ref"), 300)
        category = _clean(row.get("category"), 80).upper()
        tenant_id = _clean(row.get("tenant_id"), 120)
        period_start = _parse_time(row.get("period_start"))
        period_end = _parse_time(row.get("period_end"))
        observed = _parse_time(row.get("observed_at"))
        amount = _num(row.get("amount_brl"), maximum=100_000_000)
        recurring = row.get("recurring") is True
        shared = row.get("shared_cost") is True

        if not entry_id or entry_id in seen_ids:
            blockers.append(f"row_{index}_entry_id_invalid_or_duplicate")
            continue
        seen_ids.add(entry_id)

        if provider_ref not in attested:
            blockers.append(f"row_{index}_provider_not_attested")
            continue
        if not source_ref:
            blockers.append(f"row_{index}_source_ref_required")
            continue
        if category not in COST_CATEGORIES:
            blockers.append(f"row_{index}_category_invalid")
            continue
        if amount is None:
            blockers.append(f"row_{index}_amount_invalid")
            continue
        if observed is None or period_start is None or period_end is None or period_end < period_start:
            blockers.append(f"row_{index}_time_window_invalid")
            continue
        age_hours = max(0.0, (current - observed).total_seconds() / 3600)
        if age_hours > age_limit:
            blockers.append(f"row_{index}_stale")
            continue
        if not shared and not tenant_id:
            blockers.append(f"row_{index}_tenant_required_for_direct_cost")
            continue
        if shared and tenant_id:
            blockers.append(f"row_{index}_shared_cost_cannot_name_tenant")
            continue

        normalized.append({
            "entry_id": entry_id,
            "provider_ref": provider_ref,
            "source_ref": source_ref,
            "category": category,
            "tenant_id": tenant_id,
            "shared_cost": shared,
            "amount_brl": round(amount, 2),
            "recurring": recurring,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "observed_at": observed.isoformat(),
            "age_hours": round(age_hours, 3),
            "raw_credential_present": False,
        })

    ready = bool(normalized and not blockers)
    payload = {
        "rows": normalized,
        "attestation_digests": sorted(
            str(x.get("attestation_digest") or "") for x in attested.values()
        ),
        "max_age_hours": age_limit,
    } if ready else {}

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LIVE_COST_SNAPSHOT_READY" if ready else "LIVE_COST_SNAPSHOT_BLOCKED",
        "rows": normalized,
        "entry_count": len(normalized),
        "blockers": blockers,
        "snapshot_digest": _digest(payload) if payload else "",
        "truth_state": "EXTERNALLY_ATTESTED_COST_INPUT" if ready else "UNVERIFIED",
        "provider_connector_executed_by_module": False,
        "automatic_payment": False,
        "executes_action": False,
    }


def build_hash_chained_ledger(
    snapshot: Mapping[str, Any] | None,
    *,
    previous_ledger_digest: Any = GENESIS_DIGEST,
) -> dict[str, Any]:
    snap = _mapping(snapshot)
    previous = _clean(previous_ledger_digest, 80).lower()
    rows = snap.get("rows")

    if (
        snap.get("schema") != SCHEMA
        or snap.get("state") != "LIVE_COST_SNAPSHOT_READY"
        or not isinstance(rows, list)
        or len(previous) != 64
        or any(ch not in "0123456789abcdef" for ch in previous)
    ):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "FINOPS_LEDGER_BUILD_BLOCKED",
            "entries": [],
            "ledger_digest": "",
            "ledger_persisted": False,
            "executes_action": False,
        }

    ordered = sorted(
        (dict(x) for x in rows if isinstance(x, Mapping)),
        key=lambda x: (
            str(x.get("period_start") or ""),
            str(x.get("provider_ref") or ""),
            str(x.get("entry_id") or ""),
        ),
    )

    entries: list[dict[str, Any]] = []
    prev = previous
    for position, row in enumerate(ordered, start=1):
        canonical = {
            "position": position,
            "previous_digest": prev,
            "entry_id": row.get("entry_id"),
            "provider_ref": row.get("provider_ref"),
            "source_ref": row.get("source_ref"),
            "category": row.get("category"),
            "tenant_id": row.get("tenant_id"),
            "shared_cost": row.get("shared_cost"),
            "amount_brl": row.get("amount_brl"),
            "recurring": row.get("recurring"),
            "period_start": row.get("period_start"),
            "period_end": row.get("period_end"),
            "observed_at": row.get("observed_at"),
        }
        entry_digest = _digest(canonical)
        entries.append({**canonical, "entry_digest": entry_digest})
        prev = entry_digest

    ledger_payload = {
        "previous_ledger_digest": previous,
        "snapshot_digest": snap.get("snapshot_digest"),
        "entries": entries,
        "tail_digest": prev,
    }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "FINOPS_LEDGER_READY_FOR_PERSISTENCE_REVIEW",
        "previous_ledger_digest": previous,
        "snapshot_digest": snap.get("snapshot_digest"),
        "entries": entries,
        "entry_count": len(entries),
        "tail_digest": prev,
        "ledger_digest": _digest(ledger_payload),
        "ledger_persisted": False,
        "persistence_authorized": False,
        "automatic_payment": False,
        "executes_action": False,
    }


def verify_hash_chained_ledger(ledger: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(ledger)
    entries = row.get("entries")
    previous = _clean(row.get("previous_ledger_digest"), 80).lower()
    if (
        row.get("schema") != SCHEMA
        or row.get("state") != "FINOPS_LEDGER_READY_FOR_PERSISTENCE_REVIEW"
        or not isinstance(entries, list)
        or len(previous) != 64
    ):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "FINOPS_LEDGER_INVALID",
            "valid": False,
            "reason": "LEDGER_ENVELOPE_INVALID",
            "executes_action": False,
        }

    prev = previous
    for expected_position, raw in enumerate(entries, start=1):
        item = _mapping(raw)
        if item.get("position") != expected_position or item.get("previous_digest") != prev:
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "FINOPS_LEDGER_INVALID",
                "valid": False,
                "reason": "HASH_CHAIN_POSITION_OR_PREVIOUS_MISMATCH",
                "executes_action": False,
            }
        canonical = {
            key: item.get(key)
            for key in (
                "position",
                "previous_digest",
                "entry_id",
                "provider_ref",
                "source_ref",
                "category",
                "tenant_id",
                "shared_cost",
                "amount_brl",
                "recurring",
                "period_start",
                "period_end",
                "observed_at",
            )
        }
        actual = _digest(canonical)
        if actual != item.get("entry_digest"):
            return {
                "schema": SCHEMA,
                "version": VERSION,
                "state": "FINOPS_LEDGER_INVALID",
                "valid": False,
                "reason": "ENTRY_DIGEST_MISMATCH",
                "executes_action": False,
            }
        prev = actual

    if prev != row.get("tail_digest"):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "FINOPS_LEDGER_INVALID",
            "valid": False,
            "reason": "TAIL_DIGEST_MISMATCH",
            "executes_action": False,
        }

    ledger_payload = {
        "previous_ledger_digest": row.get("previous_ledger_digest"),
        "snapshot_digest": row.get("snapshot_digest"),
        "entries": entries,
        "tail_digest": row.get("tail_digest"),
    }
    if _digest(ledger_payload) != row.get("ledger_digest"):
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "FINOPS_LEDGER_INVALID",
            "valid": False,
            "reason": "LEDGER_DIGEST_MISMATCH",
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "FINOPS_LEDGER_VERIFIED",
        "valid": True,
        "entry_count": len(entries),
        "ledger_digest": row.get("ledger_digest"),
        "tail_digest": row.get("tail_digest"),
        "ledger_persisted": False,
        "executes_action": False,
    }


def monthly_budget_from_live_ledger(
    ledger: Mapping[str, Any] | None,
    *,
    planned_new_commitment_brl: Any = 0.0,
) -> dict[str, Any]:
    verified = verify_hash_chained_ledger(ledger)
    if verified.get("valid") is not True:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "LIVE_BUDGET_REVIEW_BLOCKED",
            "reason": "FINOPS_LEDGER_NOT_VERIFIED",
            "executes_action": False,
        }

    entries = _mapping(ledger).get("entries")
    by_category: dict[str, float] = {}
    if isinstance(entries, list):
        for raw in entries:
            item = _mapping(raw)
            category = _clean(item.get("category"), 80).casefold()
            amount = _num(item.get("amount_brl"), maximum=100_000_000)
            if category and amount is not None:
                by_category[category] = round(by_category.get(category, 0.0) + amount, 2)

    budget = evaluate_monthly_budget(
        [
            {"category": category, "amount_brl": amount, "recurring": True}
            for category, amount in sorted(by_category.items())
        ],
        planned_new_commitment_brl=planned_new_commitment_brl,
    )
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "LIVE_BUDGET_REVIEW_READY",
        "ledger_digest": verified.get("ledger_digest"),
        "budget": budget,
        "automatic_spending": False,
        "automatic_budget_increase": False,
        "executes_action": False,
    }


def tenant_cost_summary(
    ledger: Mapping[str, Any] | None,
    *,
    tenant_id: Any,
    shared_cost_allocation_pct: Any,
) -> dict[str, Any]:
    verified = verify_hash_chained_ledger(ledger)
    tenant = _clean(tenant_id, 120)
    pct = _num(shared_cost_allocation_pct, maximum=100)
    if verified.get("valid") is not True or not tenant or pct is None:
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "state": "TENANT_COST_SUMMARY_BLOCKED",
            "executes_action": False,
        }

    direct = 0.0
    shared_total = 0.0
    entries = _mapping(ledger).get("entries")
    if isinstance(entries, list):
        for raw in entries:
            item = _mapping(raw)
            amount = _num(item.get("amount_brl"), maximum=100_000_000)
            if amount is None:
                continue
            if item.get("shared_cost") is True:
                shared_total += amount
            elif item.get("tenant_id") == tenant:
                direct += amount

    allocated_shared = round(shared_total * pct / 100, 2)
    total = round(direct + allocated_shared, 2)
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "state": "TENANT_COST_SUMMARY_READY",
        "tenant_id": tenant,
        "ledger_digest": verified.get("ledger_digest"),
        "direct_cost_brl": round(direct, 2),
        "shared_cost_pool_brl": round(shared_total, 2),
        "shared_cost_allocation_pct": pct,
        "allocated_shared_cost_brl": allocated_shared,
        "estimated_total_cost_brl": total,
        "allocation_is_admin_input": True,
        "automatic_price_change": False,
        "automatic_charge": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "VERSION",
    "COST_CATEGORIES",
    "MAX_ENTRIES",
    "GENESIS_DIGEST",
    "live_cost_policy",
    "provider_cost_attestation",
    "normalize_cost_observations",
    "build_hash_chained_ledger",
    "verify_hash_chained_ledger",
    "monthly_budget_from_live_ledger",
    "tenant_cost_summary",
]
