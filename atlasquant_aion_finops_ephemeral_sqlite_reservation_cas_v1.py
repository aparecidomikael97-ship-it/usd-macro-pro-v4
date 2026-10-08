"""AION BRL200 FinOps: atomic ephemeral SQLite reservation exercise V1.

CI-only scratch-file writes on GitHub-hosted Windows/Linux runners; never
run against the HUMAN_OWNER computer, production storage or a billing service.
Reservations are accounting candidates and DO NOT approve any paid call.
SQL transactions serialize competing requests and preserve conservative
reserved liability even after settlement; no refund/cancel/release API.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping
import os
import re
import sqlite3

from atlasquant_aion_owner_brl200_finops_ceiling_v1 import (
    SCHEMA as BUDGET_SCHEMA, HARD_CAP_CENTS, SOFT_CAP_CENTS,
    CRITICAL_CAP_CENTS, _digest,
    preflight_owner_paid_request,
)

SCHEMA = "ATLASQUANT_AION_FINOPS_CI_ATOMIC_RESERVATION_SQLITE_V1"
STATE_BLOCKED = "BLOCKED"
ID = re.compile(r"ci-finops-[a-z0-9][a-z0-9-]{2,70}\Z")
TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{2,70}\Z")
BUDGET_FIELDS = {
    "schema", "state", "blockers", "expected_month", "owner_id",
    "hard_cap_brl_cents", "soft_cap_brl_cents", "critical_cap_brl_cents",
    "forecast_brl_cents", "headroom_brl_cents", "entries_count",
    "evidence_digest", "forecast_snapshot_digest",
    "unknown_other_bills_possible", "input_costs_independently_reconciled",
    "completeness_of_subscriptions_verified",
    "cap_is_real_payment_enforcement", "auto_spending_enabled",
    "automatic_paid_fallback_enabled", "executes_action",
}
FALSE_FLAGS = (
    "input_costs_independently_reconciled",
    "completeness_of_subscriptions_verified",
    "cap_is_real_payment_enforcement", "auto_spending_enabled",
    "automatic_paid_fallback_enabled", "executes_action",
)

def _response(state: str, reasons: list[str] | None = None, **data: Any) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": state, "blockers": list(dict.fromkeys(reasons or [])),
        **data, "paid_call_authorized": False, "charges_money": False,
        "production_enforcement_active": False,
        "owner_approval_consumed": False, "auto_provider_fallback": False,
        "worker_activated": False, "executes_action": False,
    }

def _validate_budget(raw: Any) -> list[str]:
    b = dict(raw) if isinstance(raw, Mapping) else {}
    errors = []
    if set(b) != BUDGET_FIELDS:
        errors.append("BUDGET_EXACT_FIELDS_REQUIRED")
    if b.get("schema") != BUDGET_SCHEMA or b.get("state") not in (
        "WITHIN_TARGET_PROVISIONAL", "DEGRADE", "CRITICAL"
    ) or b.get("blockers") != []:
        errors.append("PROVISIONAL_BUDGET_REQUIRED")
    if type(b.get("forecast_brl_cents")) is not int or not 0 <= b["forecast_brl_cents"] <= HARD_CAP_CENTS:
        errors.append("BASE_FORECAST_INVALID")
    if (b.get("hard_cap_brl_cents") != HARD_CAP_CENTS or
        b.get("soft_cap_brl_cents") != SOFT_CAP_CENTS or
        b.get("critical_cap_brl_cents") != CRITICAL_CAP_CENTS):
        errors.append("BUDGET_CAP_CONFIGURATION_INVALID")
    if not isinstance(b.get("owner_id"), str) or not b["owner_id"].strip():
        errors.append("OWNER_SCOPE_REQUIRED")
    if not isinstance(b.get("expected_month"), str) or not re.fullmatch(
        r"20[0-9]{2}-(0[1-9]|1[0-2])", b["expected_month"]
    ):
        errors.append("BUDGET_MONTH_INVALID")
    if (type(b.get("entries_count")) is not int or b["entries_count"] < 0 or
        type(b.get("headroom_brl_cents")) is not int or
        type(b.get("forecast_brl_cents")) is not int or
        b["headroom_brl_cents"] != HARD_CAP_CENTS - b["forecast_brl_cents"]):
        errors.append("BUDGET_HEADROOM_INVALID")
    if b.get("unknown_other_bills_possible") is not True:
        errors.append("BUDGET_UNKNOWN_BILLS_MUST_REMAIN_VISIBLE")
    for flag in FALSE_FLAGS:
        if b.get(flag) is not False:
            errors.append("UNTRUSTED_BUDGET_AUTHORITY:" + flag)
    evidence = b.get("evidence_digest")
    if not isinstance(evidence, str) or not re.fullmatch("[a-f0-9]{64}", evidence):
        errors.append("BUDGET_EVIDENCE_DIGEST_INVALID")
    if b.get("forecast_snapshot_digest") != _digest({
        "owner_id":b.get("owner_id"), "month":b.get("expected_month"),
        "forecast":b.get("forecast_brl_cents"), "count":b.get("entries_count"),
        "evidence":b.get("evidence_digest"),
        "state":b.get("state"), "blockers":b.get("blockers"),
    }):
        errors.append("BUDGET_SNAPSHOT_DIGEST_INVALID")
    return list(dict.fromkeys(errors))

def _check_ci_path(filename: Any) -> Path:
    """Guard against accidental execution on the owner's Windows workstation.

    Environment variables are forgeable; this is test-only friction, NOT a
    security sandbox or permissioned installation boundary.
    """
    if (os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
        or os.environ.get("RUNNER_OS") not in ("Windows", "Linux")
        or os.environ.get("AION_FINOPS_CI_EPHEMERAL") != "1"):
        raise PermissionError("ONLY_PULL_REQUEST_EPHEMERAL_CI_ALLOWED")
    root_string = os.environ.get("RUNNER_TEMP")
    if not root_string:
        raise PermissionError("RUNNER_TEMP_REQUIRED")
    root = Path(root_string).resolve(strict=True)
    p = Path(filename)
    if not p.is_absolute() or p.name.startswith("aion-finops-ci-") is False or p.suffix != ".sqlite3":
        raise PermissionError("CI_DB_PATH_NOT_ALLOWLISTED")
    if p.is_symlink() or p.parent.is_symlink():
        raise PermissionError("CI_DB_SYMLINK_FORBIDDEN")
    resolved = p.resolve(strict=False)
    if root == resolved or root not in resolved.parents:
        raise PermissionError("CI_DB_OUTSIDE_RUNNER_TEMP")
    if not resolved.parent.exists() or not resolved.parent.is_dir():
        raise PermissionError("CI_DB_PARENT_REQUIRED")
    return resolved

class EphemeralFinOpsReservationStore:
    """Disposable CI SQLite CAS engine. No production code may import and enable."""

    def __init__(self, db_filename: str):
        self.path = _check_ci_path(db_filename)
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS month_state (
                    owner_id TEXT NOT NULL,
                    month TEXT NOT NULL,
                    baseline_cents INTEGER NOT NULL CHECK(baseline_cents BETWEEN 0 AND 20000),
                    forecast_snapshot_digest TEXT NOT NULL,
                    total_reserved_cents INTEGER NOT NULL CHECK(total_reserved_cents BETWEEN 0 AND 20000),
                    revision INTEGER NOT NULL CHECK(revision >= 1),
                    PRIMARY KEY(owner_id, month)
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    month TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('RESERVED', 'SETTLED')),
                    actual_cents INTEGER,
                    CHECK(actual_cents IS NULL OR actual_cents BETWEEN 0 AND amount_cents)
                );
            """)

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def _check_accounting(self, conn, owner_id: str, month: str) -> tuple | None:
        state = conn.execute(
            "SELECT baseline_cents,forecast_snapshot_digest,total_reserved_cents,revision "
            "FROM month_state WHERE owner_id=? AND month=?", (owner_id,month)
        ).fetchone()
        if state is None:
            return None
        actual = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM reservations WHERE owner_id=? AND month=?",
            (owner_id,month)
        ).fetchone()[0]
        if actual != state[2] or state[0] + state[2] > HARD_CAP_CENTS:
            raise ValueError("ACCOUNTING_DIVERGENCE")
        return state

    def initialize_month(self, budget: Mapping[str, Any]) -> dict[str, Any]:
        errors = _validate_budget(budget)
        if errors:
            return _response(STATE_BLOCKED, errors)
        b = dict(budget)
        try:
            with self._transaction() as conn:
                old = self._check_accounting(conn, b["owner_id"], b["expected_month"])
                if old:
                    if old[0] != b["forecast_brl_cents"] or old[1] != b["forecast_snapshot_digest"]:
                        return _response(STATE_BLOCKED, ["FROZEN_MONTH_BASELINE_MISMATCH"])
                    return _response("CI_MONTH_ALREADY_INITIALIZED", [], revision=old[3])
                conn.execute(
                    "INSERT INTO month_state VALUES (?,?,?,?,?,?)",
                    (b["owner_id"],b["expected_month"],b["forecast_brl_cents"],
                     b["forecast_snapshot_digest"],0,1)
                )
                return _response("CI_MONTH_INITIALIZED_UNTRUSTED",[],revision=1)
        except (sqlite3.DatabaseError, ValueError):
            return _response(STATE_BLOCKED, ["CI_DATABASE_OR_ACCOUNTING_ERROR"])

    def reserve(self, budget: Mapping[str, Any], *, reservation_id: str,
                tenant_id: str, provider_id: str, quote: Mapping[str, Any],
                fx_snapshot: Mapping[str, Any] | None, as_of: str) -> dict[str, Any]:
        errors = _validate_budget(budget)
        if type(reservation_id) is not str or not ID.fullmatch(reservation_id):
            errors.append("RESERVATION_ID_INVALID")
        for field, val in (("TENANT",tenant_id),("PROVIDER",provider_id)):
            if type(val) is not str or not TOKEN.fullmatch(val):
                errors.append(field+"_ID_INVALID")
        upstream = preflight_owner_paid_request(
            budget, quote=quote, fx_snapshot=fx_snapshot, as_of=as_of
        )
        if upstream.get("decision") != "REQUIRES_SEPARATE_OWNER_APPROVAL":
            errors.append("PAID_PREFLIGHT_NOT_ELIGIBLE")
            errors.extend(upstream.get("blockers",[]))
        amount = upstream.get("requested_brl_cents_with_fx_buffer")
        if type(amount) is not int or not 0 < amount <= HARD_CAP_CENTS:
            errors.append("RESERVATION_AMOUNT_INVALID")
        if errors:
            return _response(STATE_BLOCKED, errors)
        b = dict(budget)
        request_material = {
            "reservation_id":reservation_id, "owner_id":b["owner_id"],
            "month":b["expected_month"], "tenant_id":tenant_id,
            "provider_id":provider_id, "amount_cents":amount,
            "quote":dict(quote), "snapshot_digest":b["forecast_snapshot_digest"],
        }
        digest = _digest(request_material)
        try:
            with self._transaction() as conn:
                state = self._check_accounting(conn, b["owner_id"], b["expected_month"])
                if state is None:
                    return _response(STATE_BLOCKED, ["MONTH_NOT_INITIALIZED"])
                baseline, pinned, used, revision = state
                if baseline != b["forecast_brl_cents"] or pinned != b["forecast_snapshot_digest"]:
                    return _response(STATE_BLOCKED, ["FROZEN_MONTH_BASELINE_MISMATCH"])
                old = conn.execute(
                    "SELECT owner_id,month,request_digest,amount_cents,state FROM reservations "
                    "WHERE reservation_id=?", (reservation_id,)
                ).fetchone()
                if old:
                    if old[0] == b["owner_id"] and old[1] == b["expected_month"] and old[2] == digest:
                        return _response("CI_RESERVATION_REPLAY_IDENTICAL_UNTRUSTED",[],
                                         reservation_id=reservation_id, amount_cents=old[3],
                                         reservation_state=old[4],revision=revision)
                    return _response(STATE_BLOCKED, ["RESERVATION_ID_REUSE_OR_SCOPE_CONFLICT"])
                if baseline + used + amount > HARD_CAP_CENTS:
                    return _response(STATE_BLOCKED, ["ATOMIC_OWNER_HARD_CAP_EXCEEDED"])
                conn.execute(
                    "INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?)",
                    (reservation_id,b["owner_id"],b["expected_month"],tenant_id,
                     provider_id,amount,digest,"RESERVED",None)
                )
                conn.execute(
                    "UPDATE month_state SET total_reserved_cents=?,revision=? "
                    "WHERE owner_id=? AND month=?",
                    (used+amount,revision+1,b["owner_id"],b["expected_month"])
                )
                return _response("CI_RESERVATION_RECORDED_UNTRUSTED",[],
                                 reservation_id=reservation_id,amount_cents=amount,
                                 revision=revision+1)
        except (sqlite3.DatabaseError, ValueError):
            return _response(STATE_BLOCKED, ["CI_DATABASE_OR_ACCOUNTING_ERROR"])

    def settle(self, *, owner_id: str, month: str, reservation_id: str,
               measured_actual_cents: int) -> dict[str, Any]:
        if (type(owner_id) is not str or not owner_id or
            type(month) is not str or not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])",month)
            or type(reservation_id) is not str or not ID.fullmatch(reservation_id)
            or type(measured_actual_cents) is not int or measured_actual_cents < 0):
            return _response(STATE_BLOCKED, ["SETTLEMENT_INPUT_INVALID"])
        try:
            with self._transaction() as conn:
                state = self._check_accounting(conn, owner_id, month)
                if state is None:
                    return _response(STATE_BLOCKED,["MONTH_NOT_INITIALIZED"])
                old = conn.execute(
                    "SELECT owner_id,month,amount_cents,state,actual_cents FROM reservations "
                    "WHERE reservation_id=?", (reservation_id,)
                ).fetchone()
                if old is None or old[0] != owner_id or old[1] != month:
                    return _response(STATE_BLOCKED,["RESERVATION_SCOPE_OR_ID_INVALID"])
                if measured_actual_cents > old[2]:
                    return _response(STATE_BLOCKED,["ACTUAL_COST_EXCEEDS_RESERVED"])
                if old[3] == "SETTLED":
                    if old[4] == measured_actual_cents:
                        return _response("CI_SETTLEMENT_REPLAY_IDENTICAL_UNTRUSTED",[],
                                         reservation_id=reservation_id)
                    return _response(STATE_BLOCKED,["CONFLICTING_SETTLEMENT_REPLAY"])
                conn.execute(
                    "UPDATE reservations SET state='SETTLED',actual_cents=? "
                    "WHERE reservation_id=?", (measured_actual_cents,reservation_id)
                )
                conn.execute(
                    "UPDATE month_state SET revision=revision+1 "
                    "WHERE owner_id=? AND month=?", (owner_id,month)
                )
                # Intentionally never release unused reserved budget on the
                # basis of an unverified caller-supplied provider measurement.
                return _response("CI_SETTLEMENT_RECORDED_NO_BUDGET_RELEASE",[],
                                 reservation_id=reservation_id)
        except (sqlite3.DatabaseError, ValueError):
            return _response(STATE_BLOCKED, ["CI_DATABASE_OR_ACCOUNTING_ERROR"])

    def report(self, *, owner_id: str, month: str) -> dict[str, Any]:
        if type(owner_id) is not str or not owner_id or type(month) is not str:
            return _response(STATE_BLOCKED, ["REPORT_SCOPE_INVALID"])
        try:
            with self._connection() as conn:
                state = self._check_accounting(conn, owner_id,month)
                if state is None:
                    return _response(STATE_BLOCKED, ["MONTH_NOT_INITIALIZED"])
                count = conn.execute(
                    "SELECT COUNT(*) FROM reservations WHERE owner_id=? AND month=?",
                    (owner_id,month)
                ).fetchone()[0]
                return _response("CI_SNAPSHOT_UNTRUSTED",[],
                                 baseline_cents=state[0], reserved_cents=state[2],
                                 remaining_cents=HARD_CAP_CENTS-state[0]-state[2],
                                 revision=state[3],reservation_count=count)
        except (sqlite3.DatabaseError, ValueError):
            return _response(STATE_BLOCKED, ["CI_DATABASE_OR_ACCOUNTING_ERROR"])

def ephemeral_finops_policy() -> dict[str, Any]:
    return {
        "schema": SCHEMA, "scratch_sqlite_written_on_ci_runner": True,
        "ephemeral_github_ci_only": True, "atomic_sqlite_begin_immediate": True,
        "monthly_owner_ceiling_brl_cents": HARD_CAP_CENTS,
        "real_owner_billing_sources_authenticated": False,
        "real_provider_integration_live": False,
        "human_owner_approval_consumed": False,
        "production_payment_enforcement": False,
        "production_ledger_deployed": False,
        "refund_or_released_funds_authorized": False,
        "real_provider_bill_paid": False,
        "automatic_paid_fallback": False,
        "owner_workstation_accessed": False,
        "worker_activated": False, "deploy_executed": False,
    }
