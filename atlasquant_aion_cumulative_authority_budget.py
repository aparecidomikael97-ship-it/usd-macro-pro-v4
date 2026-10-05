"""Persistent cumulative-authority budget for staged AION execution.

This module is a guard/ledger only. It does not authorize an action, dispatch an
adapter or grant capabilities. It limits how much already-approved external
authority may accumulate within one transaction and within a rolling scope
window.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from aion_chat.models import Scope
from aion_chat.store import SQLiteChatStore

SCHEMA = "ATLASQUANT_AION_CUMULATIVE_AUTHORITY_BUDGET_V1"
DEFAULT_WINDOW_SECONDS = 900
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CAPABILITY_CLASSES = ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "CRITICAL")


def _clean(value: Any, limit: int = 300) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _token(value: Any, name: str) -> str:
    text = _clean(value, 128)
    if not _SAFE_TOKEN.fullmatch(text):
        raise ValueError(f"invalid {name}")
    return text


def _utc(value: Any | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if out.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return out.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _scope(scope: Scope) -> tuple[str, str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id


class CumulativeAuthorityBudget:
    """Fail-closed budget ledger bound to one trusted Scope."""

    def __init__(
        self,
        store: SQLiteChatStore,
        scope: Scope,
        *,
        authority_budget_ref: str,
        policy_version: str,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_window_effects: int = 8,
        max_window_risk_points: int = 16,
        max_window_distinct_capabilities: int = 4,
        max_transaction_effects: int = 5,
        max_transaction_risk_points: int = 10,
    ):
        if not isinstance(store, SQLiteChatStore):
            raise TypeError("SQLiteChatStore required")
        store.require_healthy()
        self.store = store
        self.db = store.db
        self.scope = scope
        _scope(scope)
        self.authority_budget_ref = _token(authority_budget_ref, "authority_budget_ref")
        self.policy_version = _token(policy_version, "policy_version")
        limits = {
            "window_seconds": window_seconds,
            "max_window_effects": max_window_effects,
            "max_window_risk_points": max_window_risk_points,
            "max_window_distinct_capabilities": max_window_distinct_capabilities,
            "max_transaction_effects": max_transaction_effects,
            "max_transaction_risk_points": max_transaction_risk_points,
        }
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"invalid {name}")
        if window_seconds > 86400:
            raise ValueError("authority window too large")
        self.window_seconds = window_seconds
        self.max_window_effects = max_window_effects
        self.max_window_risk_points = max_window_risk_points
        self.max_window_distinct_capabilities = max_window_distinct_capabilities
        self.max_transaction_effects = max_transaction_effects
        self.max_transaction_risk_points = max_transaction_risk_points
        self.policy_digest = _digest({
            "schema": SCHEMA,
            "authority_budget_ref": self.authority_budget_ref,
            "policy_version": self.policy_version,
            **limits,
        })
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS aion_authority_spend(
                idempotency_key TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                tenant TEXT NOT NULL,
                workspace TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                authority_budget_ref TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                capability_class TEXT NOT NULL,
                action TEXT NOT NULL,
                risk_points INTEGER NOT NULL,
                effect_ref TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                decision_digest TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS aion_authority_spend_scope_time
              ON aion_authority_spend(owner,tenant,workspace,confirmed_at);
            CREATE INDEX IF NOT EXISTS aion_authority_spend_transaction
              ON aion_authority_spend(owner,tenant,workspace,transaction_id,confirmed_at);
            """)

    def _scope_args(self) -> tuple[str, str, str]:
        return _scope(self.scope)

    def _validate_decision(self, decision: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(decision or {})
        transaction = _token(row.get("transaction_id"), "transaction_id")
        budget_ref = _token(row.get("authority_budget_ref"), "authority_budget_ref")
        capability = _clean(row.get("capability_class"), 80).upper()
        action = _token(row.get("action"), "action")
        risk = row.get("risk_points")
        if isinstance(risk, bool) or not isinstance(risk, int) or risk < 1 or risk > 100:
            raise ValueError("invalid risk_points")
        if budget_ref != self.authority_budget_ref:
            raise ValueError("authority budget ref mismatch")
        if _clean(row.get("policy_version"), 128) != self.policy_version:
            raise ValueError("authority budget policy version mismatch")
        if capability not in CAPABILITY_CLASSES:
            raise ValueError("invalid capability_class")
        for field, expected in (
            ("owner_id", self.scope.owner_id),
            ("tenant_id", self.scope.tenant_id),
            ("workspace_id", self.scope.workspace_id),
        ):
            if _clean(row.get(field), 128) != expected:
                raise ValueError("authority budget scope mismatch")
        return {
            "transaction_id": transaction,
            "authority_budget_ref": budget_ref,
            "capability_class": capability,
            "action": action,
            "risk_points": risk,
        }

    def _snapshot(self, *, transaction_id: str, now: datetime) -> dict[str, Any]:
        cutoff = _iso(now - timedelta(seconds=self.window_seconds))
        scope_args = self._scope_args()
        window_rows = self.db.execute(
            """SELECT capability_class,risk_points FROM aion_authority_spend
               WHERE owner=? AND tenant=? AND workspace=? AND confirmed_at>=?""",
            (*scope_args, cutoff),
        ).fetchall()
        tx_rows = self.db.execute(
            """SELECT capability_class,risk_points FROM aion_authority_spend
               WHERE owner=? AND tenant=? AND workspace=? AND transaction_id=?""",
            (*scope_args, transaction_id),
        ).fetchall()
        return {
            "window_effects": len(window_rows),
            "window_risk_points": sum(int(row["risk_points"]) for row in window_rows),
            "window_distinct_capabilities": len({row["capability_class"] for row in window_rows}),
            "transaction_effects": len(tx_rows),
            "transaction_risk_points": sum(int(row["risk_points"]) for row in tx_rows),
            "transaction_distinct_capabilities": len({row["capability_class"] for row in tx_rows}),
        }

    def guard(
        self,
        decision: Mapping[str, Any],
        *,
        now: Any | None = None,
    ) -> dict[str, Any]:
        current = _utc(now)
        try:
            bound = self._validate_decision(decision)
        except Exception as exc:
            return {
                "schema": SCHEMA,
                "allowed": False,
                "reason": "AUTHORITY_BUDGET_BINDING_INVALID:" + type(exc).__name__,
                "authority_budget_ref": self.authority_budget_ref,
                "transaction_id": _clean((decision or {}).get("transaction_id"), 128),
                "scope": {
                    "owner_id": self.scope.owner_id,
                    "tenant_id": self.scope.tenant_id,
                    "workspace_id": self.scope.workspace_id,
                },
                "grants_authority": False,
                "executes_action": False,
            }
        before = self._snapshot(transaction_id=bound["transaction_id"], now=current)
        capability_set = {
            row["capability_class"]
            for row in self.db.execute(
                """SELECT capability_class FROM aion_authority_spend
                   WHERE owner=? AND tenant=? AND workspace=? AND confirmed_at>=?""",
                (*self._scope_args(), _iso(current - timedelta(seconds=self.window_seconds))),
            ).fetchall()
        }
        capability_set.add(bound["capability_class"])
        after = {
            "window_effects": before["window_effects"] + 1,
            "window_risk_points": before["window_risk_points"] + bound["risk_points"],
            "window_distinct_capabilities": len(capability_set),
            "transaction_effects": before["transaction_effects"] + 1,
            "transaction_risk_points": before["transaction_risk_points"] + bound["risk_points"],
        }
        blockers: list[str] = []
        if bound["capability_class"] == "CRITICAL":
            blockers.append("CRITICAL_CAPABILITY_REQUIRES_SEPARATE_HUMAN_GATE")
        if after["window_effects"] > self.max_window_effects:
            blockers.append("WINDOW_EFFECT_LIMIT")
        if after["window_risk_points"] > self.max_window_risk_points:
            blockers.append("WINDOW_RISK_LIMIT")
        if after["window_distinct_capabilities"] > self.max_window_distinct_capabilities:
            blockers.append("WINDOW_CAPABILITY_DIVERSITY_LIMIT")
        if after["transaction_effects"] > self.max_transaction_effects:
            blockers.append("TRANSACTION_EFFECT_LIMIT")
        if after["transaction_risk_points"] > self.max_transaction_risk_points:
            blockers.append("TRANSACTION_RISK_LIMIT")
        return {
            "schema": SCHEMA,
            "allowed": not blockers,
            "reason": "ALLOW" if not blockers else "CUMULATIVE_AUTHORITY_BUDGET_EXCEEDED:" + ",".join(blockers),
            "blockers": blockers,
            "authority_budget_ref": self.authority_budget_ref,
            "transaction_id": bound["transaction_id"],
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "scope": {
                "owner_id": self.scope.owner_id,
                "tenant_id": self.scope.tenant_id,
                "workspace_id": self.scope.workspace_id,
            },
            "before": before,
            "projected_after": after,
            "grants_authority": False,
            "execution_allowed_by_this_component": False,
            "executes_action": False,
        }

    def record_confirmed(
        self,
        decision: Mapping[str, Any],
        *,
        idempotency_key: Any,
        effect_ref: Any,
        confirmed_at: Any | None = None,
    ) -> dict[str, Any]:
        bound = self._validate_decision(decision)
        key = _token(idempotency_key, "idempotency_key")
        effect = _token(effect_ref, "effect_ref")
        at = _utc(confirmed_at)
        digest = _digest(dict(decision))
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute(
                "SELECT * FROM aion_authority_spend WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if existing is not None:
                same = (
                    existing["owner"] == self.scope.owner_id
                    and existing["tenant"] == self.scope.tenant_id
                    and existing["workspace"] == self.scope.workspace_id
                    and existing["transaction_id"] == bound["transaction_id"]
                    and existing["authority_budget_ref"] == self.authority_budget_ref
                    and existing["effect_ref"] == effect
                    and existing["risk_points"] == bound["risk_points"]
                    and existing["decision_digest"] == digest
                )
                if not same:
                    raise ValueError("authority spend idempotency collision")
                self.db.commit()
                return {
                    "schema": SCHEMA,
                    "state": "IDEMPOTENT",
                    "idempotency_key": key,
                    "transaction_id": bound["transaction_id"],
                    "effect_ref": effect,
                    "grants_authority": False,
                    "executes_action": False,
                }
            self.db.execute(
                """INSERT INTO aion_authority_spend(
                    idempotency_key,owner,tenant,workspace,transaction_id,
                    authority_budget_ref,policy_version,capability_class,action,
                    risk_points,effect_ref,confirmed_at,decision_digest
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    key,
                    *self._scope_args(),
                    bound["transaction_id"],
                    self.authority_budget_ref,
                    self.policy_version,
                    bound["capability_class"],
                    bound["action"],
                    bound["risk_points"],
                    effect,
                    _iso(at),
                    digest,
                ),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "schema": SCHEMA,
            "state": "RECORDED",
            "idempotency_key": key,
            "transaction_id": bound["transaction_id"],
            "effect_ref": effect,
            "risk_points": bound["risk_points"],
            "grants_authority": False,
            "executes_action": False,
        }

    def snapshot(
        self,
        transaction_id: Any,
        *,
        now: Any | None = None,
    ) -> dict[str, Any]:
        tx = _token(transaction_id, "transaction_id")
        current = _utc(now)
        data = self._snapshot(transaction_id=tx, now=current)
        return {
            "schema": SCHEMA,
            "authority_budget_ref": self.authority_budget_ref,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "transaction_id": tx,
            "scope": {
                "owner_id": self.scope.owner_id,
                "tenant_id": self.scope.tenant_id,
                "workspace_id": self.scope.workspace_id,
            },
            **data,
            "grants_authority": False,
            "executes_action": False,
        }


__all__ = [
    "SCHEMA",
    "DEFAULT_WINDOW_SECONDS",
    "CAPABILITY_CLASSES",
    "CumulativeAuthorityBudget",
]
