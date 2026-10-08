"""AION FinOps V1: declared inventory, claimed invoice reconciliation and dry-run provider boundary.

All financial records are SYNTHETIC / CALLER-SUPPLIED; no bank, provider,
invoice or payment source is authenticated. CI-only SQLite readback is
allowed exclusively through #1071's guarded ephemeral reservation store.
No network, real paid provider execution, automatic spend, or approval.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Mapping

from atlasquant_aion_owner_brl200_finops_ceiling_v1 import (
    SCHEMA as BUDGET_SCHEMA, HARD_CAP_CENTS, CATEGORIES, _digest,
)
from atlasquant_aion_finops_ephemeral_sqlite_reservation_cas_v1 import (
    SCHEMA as STORE_SCHEMA,
    EphemeralFinOpsReservationStore, _check_ci_path,
)

SCHEMA = "ATLASQUANT_AION_FINOPS_CI_INVENTORY_RECON_PROVIDER_GATE_V1"
INVENTORY_READY = "CI_OWNER_INVENTORY_DECLARED_ONLY"
RECONCILED = "CI_CLAIMED_INVOICES_EXACT_MATCH_UNTRUSTED"
DRY_READY = "CI_PROVIDER_BOUNDARY_DRY_RUN_UNTRUSTED"
BLOCKED = "BLOCKED"
IDENTITY = re.compile(r"[a-z0-9][a-z0-9_-]{2,79}\Z")
MONTH = re.compile(r"20[0-9]{2}-(0[1-9]|1[0-2])\Z")
HEXDIGEST = re.compile(r"[0-9a-f]{64}\Z")
CADENCES = ("MONTHLY", "ANNUAL", "USAGE_MONTHLY", "FREE")
SOURCES = ("OWNER_DECLARED", "USER_REVIEWED_DOCUMENT")
INVOICE_EVIDENCE = ("USER_IMPORTED", "CLAIMED_PROVIDER_INVOICE")
OBLIGATION_FIELDS = {
    "obligation_id", "provider_id", "owner_id", "month", "category",
    "cadence", "declared_charge_brl_cents", "evidence", "status",
}
INVOICE_FIELDS = {
    "invoice_id", "obligation_id", "provider_id", "owner_id", "month",
    "claimed_charge_brl_cents", "evidence",
}
BOUNDARY_FIELDS = {
    "reservation_id", "owner_id", "month", "tenant_id", "provider_id",
    "quoted_brl_cents", "inventory_digest", "reconciliation_digest",
    "budget_digest",
}
INVENTORY_FLAGS = (
    "all_real_providers_independently_discovered",
    "invoice_sources_authenticated", "budget_is_bank_authority",
    "real_paid_spend_authorized", "execution_performed",
)
RECON_FLAGS = (
    "actual_paid_invoice_verified", "real_provider_invoice_authenticated",
    "provider_bank_debits_reconciled", "refund_or_credit_confirmed",
    "actual_spend_within_budget_guaranteed",
)
GATE_FLAGS = (
    "paid_provider_call_authorized", "paid_call_executed",
    "real_invoice_source_authenticated", "owner_approval_consumed",
    "real_financial_enforcement_deployed", "money_transferred",
    "automatic_paid_fallback_enabled", "worker_activated",
    "deploy_executed", "owner_device_accessed",
)

def _is_id(s: Any) -> bool:
    return type(s) is str and bool(IDENTITY.fullmatch(s))

def _is_month(s: Any) -> bool:
    return type(s) is str and bool(MONTH.fullmatch(s))

def _is_cent(n: Any) -> bool:
    return type(n) is int and 0 <= n <= 10**11

def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)

def _safe_digest(obj: Any) -> str:
    try:
        return sha256(_canonical(obj).encode("ascii")).hexdigest()
    except (ValueError, TypeError, OverflowError, RecursionError):
        return ""

def _row_dict(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, Mapping) else {}

def _itemize(rows: Any, *, limit: int = 150) -> list:
    return rows if type(rows) in (list, tuple) and len(rows) <= limit else []

def _base_response(state: str, blockers: list[str], **fields: Any) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": state,
            "blockers": list(dict.fromkeys(blockers)), **fields}

def _valid_declared_obligation(row: dict, owner_id: Any, month: Any) -> list[str]:
    errors = []
    if set(row) != OBLIGATION_FIELDS:
        errors.append("OBLIGATION_EXACT_FIELDS_REQUIRED")
    for name in ("obligation_id", "provider_id"):
        if not _is_id(row.get(name)):
            errors.append("OBLIGATION_ID_INVALID:" + name)
    if row.get("owner_id") != owner_id or row.get("month") != month:
        errors.append("OBLIGATION_SCOPE_MISMATCH")
    category = row.get("category")
    if type(category) is not str or category not in CATEGORIES:
        errors.append("CATEGORY_INVALID")
    cadence = row.get("cadence")
    if type(cadence) is not str or cadence not in CADENCES:
        errors.append("CADENCE_INVALID")
    source = row.get("evidence")
    if type(source) is not str or source not in SOURCES:
        errors.append("OBLIGATION_COST_EVIDENCE_MISSING")
    status = row.get("status")
    if type(status) is not str or status not in ("COMMITTED", "RESERVED", "SETTLED"):
        errors.append("OBLIGATION_STATUS_INVALID")
    amount = row.get("declared_charge_brl_cents")
    if not _is_cent(amount):
        errors.append("CHARGE_AMOUNT_UNKNOWN_OR_INVALID")
    elif cadence == "FREE" and amount != 0:
        errors.append("FREE_CADENCE_REQUIRES_ZERO")
    elif cadence != "FREE" and amount == 0:
        errors.append("PAID_CADENCE_REQUIRES_POSITIVE")
    return errors

def _monthly_amount(amount: int, cadence: str) -> int:
    # Conservative forecast; annual subscriptions must count every month.
    return (amount + 11) // 12 if cadence == "ANNUAL" else amount

def build_declared_owner_inventory(
    obligations: Any, *,
    expected_owner_id: str, expected_month: str,
    expected_provider_ids: Any,
) -> dict[str, Any]:
    errors = []
    if not _is_id(expected_owner_id) or not _is_month(expected_month):
        errors.append("INVENTORY_SCOPE_INVALID")
    if (type(expected_provider_ids) not in (list, tuple)
        or len(expected_provider_ids) > 100
        or any(not _is_id(x) for x in expected_provider_ids)
        or list(expected_provider_ids) != sorted(set(expected_provider_ids))):
        errors.append("EXPECTED_PROVIDER_SET_INVALID")
        provider_set: set[str] = set()
    else:
        provider_set = set(expected_provider_ids)
    if type(obligations) not in (list, tuple) or len(obligations) > 150:
        errors.append("OBLIGATION_LIST_INVALID")
    rows = _itemize(obligations)
    normalized: list[dict] = []
    seen: set[str] = set()
    seen_providers: set[str] = set()
    total = 0
    for i, obj in enumerate(rows):
        row = _row_dict(obj)
        row_errors = _valid_declared_obligation(row, expected_owner_id, expected_month)
        errors.extend(f"{msg}:{i}" for msg in row_errors)
        oid = row.get("obligation_id")
        if not _is_id(oid):
            continue
        if oid in seen:
            errors.append("DUPLICATE_OBLIGATION_ID:" + oid)
            continue
        seen.add(oid)
        provider = row.get("provider_id")
        if _is_id(provider):
            seen_providers.add(provider)
            if provider not in provider_set:
                errors.append("UNLISTED_PROVIDER:" + provider)
        if row_errors:
            continue
        cents = _monthly_amount(row["declared_charge_brl_cents"], row["cadence"])
        total += cents
        normalized.append({
            "obligation_id":oid, "provider_id":provider, "category":row["category"],
            "cadence":row["cadence"], "declared_charge_brl_cents":row["declared_charge_brl_cents"],
            "monthly_forecast_brl_cents":cents, "evidence":row["evidence"],
            "status":row["status"],
        })
    if seen_providers != provider_set:
        errors.append("DECLARED_PROVIDER_COVERAGE_INCOMPLETE")
    if not normalized:
        errors.append("NO_DECLARED_OBLIGATIONS")
    if total > HARD_CAP_CENTS:
        errors.append("DECLARED_OWNER_HARD_CAP_EXCEEDED")
    normalized.sort(key=lambda r:r["obligation_id"])
    errors = list(dict.fromkeys(errors))
    envelope = {
        "owner_id":expected_owner_id, "month":expected_month,
        "expected_provider_ids":sorted(provider_set),
        "monthly_total_brl_cents":total, "rows":normalized,
    }
    digest = _safe_digest(envelope)
    if not digest:
        errors.append("INVENTORY_NONJSON_DATA")
    return _base_response(
        INVENTORY_READY if not errors else BLOCKED, errors,
        **envelope, inventory_digest=digest if not errors else "",
        real_provider_bills_verified=False,
        **{flag: False for flag in INVENTORY_FLAGS},
    )

def reconcile_claimed_owner_invoices(
    inventory: Any, invoices: Any, *,
    expected_owner_id: str, expected_month: str,
) -> dict[str, Any]:
    errors = []
    inv = _row_dict(inventory)
    if (inv.get("schema") != SCHEMA or inv.get("state") != INVENTORY_READY
        or inv.get("blockers") != [] or inv.get("owner_id") != expected_owner_id
        or inv.get("month") != expected_month):
        errors.append("INVENTORY_NOT_READY_OR_SCOPE_WRONG")
    expected = {
        "owner_id": inv.get("owner_id"), "month": inv.get("month"),
        "expected_provider_ids": inv.get("expected_provider_ids"),
        "monthly_total_brl_cents": inv.get("monthly_total_brl_cents"),
        "rows": inv.get("rows"),
    }
    if inv.get("inventory_digest") != _safe_digest(expected):
        errors.append("INVENTORY_DIGEST_MISMATCH")
    rows = inv.get("rows")
    if type(rows) is not list or not all(type(x) is dict for x in rows):
        errors.append("INVENTORY_ROWS_INVALID")
        rows=[]
    index = {x.get("obligation_id"):x for x in rows if _is_id(x.get("obligation_id"))}
    if len(index) != len(rows):
        errors.append("INVENTORY_DUPLICATE_OR_INVALID_ROWS")
    if type(invoices) not in (list, tuple) or len(invoices) > 150:
        errors.append("INVOICE_LIST_INVALID")
    checked: list[dict] = []
    seen_ids: set[str] = set()
    seen_obligations: set[str] = set()
    declared_total = 0
    for i, raw in enumerate(_itemize(invoices)):
        r = _row_dict(raw)
        if set(r) != INVOICE_FIELDS:
            errors.append("INVOICE_EXACT_FIELDS_REQUIRED:"+str(i))
        iid, oid = r.get("invoice_id"),r.get("obligation_id")
        if not _is_id(iid) or not _is_id(oid) or not _is_id(r.get("provider_id")):
            errors.append("INVOICE_IDENTIFIERS_INVALID:"+str(i))
            continue
        if iid in seen_ids or oid in seen_obligations:
            errors.append("INVOICE_DUPLICATE_ID_OR_OBLIGATION:"+str(i))
        seen_ids.add(iid)
        seen_obligations.add(oid)
        if r.get("owner_id") != expected_owner_id or r.get("month") != expected_month:
            errors.append("INVOICE_SCOPE_INVALID:"+str(i))
        if type(r.get("evidence")) is not str or r.get("evidence") not in INVOICE_EVIDENCE:
            errors.append("INVOICE_EVIDENCE_UNKNOWN:"+str(i))
        actual = r.get("claimed_charge_brl_cents")
        if not _is_cent(actual):
            errors.append("INVOICE_AMOUNT_INVALID:"+str(i))
            continue
        obligation = index.get(oid)
        if not obligation:
            errors.append("INVOICE_FOR_UNKNOWN_OBLIGATION:"+str(i))
            continue
        if obligation["provider_id"] != r.get("provider_id"):
            errors.append("INVOICE_PROVIDER_MISMATCH:"+str(i))
        if obligation["declared_charge_brl_cents"] != actual:
            errors.append("CLAIMED_INVOICE_VS_DECLARED_COST_DIVERGENCE:"+str(i))
        declared_total += actual
        checked.append({
            "invoice_id":iid,"obligation_id":oid,
            "provider_id":r["provider_id"],"claimed_charge_brl_cents":actual,
            "evidence":r.get("evidence"),
        })
    if seen_obligations != set(index):
        errors.append("INVOICE_COVERAGE_INCOMPLETE")
    checked.sort(key=lambda x:x["obligation_id"])
    errors=list(dict.fromkeys(errors))
    material={
        "inventory_digest":inv.get("inventory_digest"),
        "owner_id":expected_owner_id, "month":expected_month,
        "invoice_count":len(checked), "rows":checked,
    }
    return _base_response(
        RECONCILED if not errors else BLOCKED, errors,
        owner_id=expected_owner_id, month=expected_month,
        inventory_digest=inv.get("inventory_digest"),
        claimed_invoices_digest=_safe_digest(material) if not errors else "",
        claimed_total_raw_brl_cents=declared_total,
        invoices_checked=len(checked),
        **{flag:False for flag in RECON_FLAGS},
    )

def dry_run_ci_provider_execution_boundary(
    store: EphemeralFinOpsReservationStore,
    inventory: Any, reconciliation: Any, request: Any,
) -> dict[str, Any]:
    """Mandatory dry-run denial of real execution even when test proofs match.

    Queries the guarded #1071 temporary SQLite reservation in a read-only
    connection. Does NOT connect to or invoke the named external provider.
    """
    errors=[]
    inv=_row_dict(inventory)
    rec=_row_dict(reconciliation)
    req=_row_dict(request)
    if set(req) != BOUNDARY_FIELDS:
        errors.append("BOUNDARY_EXACT_FIELDS_REQUIRED")
    for name in ("reservation_id","tenant_id","provider_id","owner_id"):
        if not _is_id(req.get(name)):
            errors.append("BOUNDARY_ID_INVALID:"+name)
    if not _is_month(req.get("month")):
        errors.append("BOUNDARY_MONTH_INVALID")
    if not _is_cent(req.get("quoted_brl_cents")) or req.get("quoted_brl_cents")==0:
        errors.append("BOUNDARY_PAID_AMOUNT_INVALID")
    if (inv.get("schema") != SCHEMA or inv.get("state") != INVENTORY_READY
        or inv.get("blockers") != [] or inv.get("owner_id") != req.get("owner_id")
        or inv.get("month") != req.get("month")
        or req.get("inventory_digest") != inv.get("inventory_digest")):
        errors.append("BOUNDARY_INVENTORY_INVALID")
    expected_inv = {
        "owner_id":inv.get("owner_id"), "month":inv.get("month"),
        "expected_provider_ids":inv.get("expected_provider_ids"),
        "monthly_total_brl_cents":inv.get("monthly_total_brl_cents"),
        "rows":inv.get("rows"),
    }
    if not inv.get("inventory_digest") or inv.get("inventory_digest")!=_safe_digest(expected_inv):
        errors.append("BOUNDARY_INVENTORY_REHASH_FAILED")
    if (rec.get("schema") != SCHEMA or rec.get("state") != RECONCILED
        or rec.get("blockers") != [] or rec.get("owner_id") != req.get("owner_id")
        or rec.get("month") != req.get("month")
        or rec.get("inventory_digest") != inv.get("inventory_digest")
        or req.get("reconciliation_digest") != rec.get("claimed_invoices_digest")
        or not rec.get("claimed_invoices_digest")):
        errors.append("BOUNDARY_CLAIMED_RECON_INVALID")
    for proof, names in ((inv,INVENTORY_FLAGS),(rec,RECON_FLAGS)):
        for flag in names:
            if proof.get(flag) is not False:
                errors.append("FALSE_EXTERNAL_FINANCIAL_TRUST_REQUIRED:"+flag)
    if req.get("provider_id") not in (
        [r["provider_id"] for r in inv.get("rows",[]) if type(r) is dict]
        if type(inv.get("rows")) is list else []
    ):
        errors.append("BOUNDARY_PROVIDER_NOT_IN_INVENTORY")
    if not isinstance(store,EphemeralFinOpsReservationStore):
        errors.append("CI_STORE_REQUIRED")
    else:
        try:
            _check_ci_path(store.path)
            with store._connection() as conn:
                state=store._check_accounting(conn,req.get("owner_id"),req.get("month"))
                if state is None:
                    errors.append("MONTH_NOT_INITIALIZED")
                else:
                    baseline,pinned,used,revision=state
                    if baseline!=inv.get("monthly_total_brl_cents") or pinned!=req.get("budget_digest"):
                        errors.append("BOUNDARY_BUDGET_INVENTORY_BASELINE_MISMATCH")
                    reservation=conn.execute(
                        "SELECT owner_id,month,tenant_id,provider_id,amount_cents,state "
                        "FROM reservations WHERE reservation_id=?",
                        (req.get("reservation_id"),)
                    ).fetchone()
                    if (reservation is None or reservation != (
                        req.get("owner_id"),req.get("month"),req.get("tenant_id"),
                        req.get("provider_id"),req.get("quoted_brl_cents"),"RESERVED"
                    )):
                        errors.append("ATOMIC_RESERVATION_MISSING_OR_MISMATCHED")
        except (ValueError, sqlite3.DatabaseError, PermissionError, TypeError):
            errors.append("CI_STORE_ACCOUNTING_OR_SCOPE_ERROR")
    return _base_response(
        DRY_READY if not errors else BLOCKED, errors,
        request_digest=_safe_digest(req) if not errors else "",
        inventory_digest=inv.get("inventory_digest"),
        reconciliation_digest=rec.get("claimed_invoices_digest"),
        quoted_brl_cents=req.get("quoted_brl_cents")
            if _is_cent(req.get("quoted_brl_cents")) else None,
        **{flag:False for flag in GATE_FLAGS},
    )

def boundary_policy() -> dict[str, Any]:
    return {
        "schema":SCHEMA,
        "synthetic_ci_inventory_only":True,
        "sqlite_ci_readback_only":True,
        "no_real_provider_requests":True,
        "monthly_owner_cap_brl_cents":HARD_CAP_CENTS,
        "all_provider_bills_discovered":False,
        "real_invoices_authenticated":False,
        "real_subscription_inventory_complete":False,
        "real_provider_boundary_enforcing":False,
        "real_owner_approval_consumed":False,
        "production_payment_or_provider_call_allowed":False,
        "production_deploy_enabled":False,
        "worker_activated":False,
    }
